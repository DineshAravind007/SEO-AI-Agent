import json
import logging
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from backend.database.models import MonitoringProject, MonitoringReport, Audit, SEOIssue, Page
from backend.schemas.monitoring import MonitoringProjectCreate, MonitoringProjectUpdate
from backend.services.audit_service import run_audit_task

logger = logging.getLogger(__name__)

# Track in-memory to prevent duplicate concurrent runs (project_id → True)
_running: set = set()


def _get_next_audit_date(frequency: str) -> datetime:
    """Calculate next scheduled audit time from now based on frequency."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if frequency == "daily":
        return now + timedelta(days=1)
    elif frequency == "weekly":
        return now + timedelta(days=7)
    elif frequency == "monthly":
        return now + timedelta(days=30)
    return now + timedelta(days=7)


def create_project(db: Session, req: MonitoringProjectCreate) -> MonitoringProject:
    proj = MonitoringProject(
        url=req.url,
        name=req.name,
        frequency=req.frequency,
        max_pages=req.max_pages,
        max_depth=req.max_depth,
        next_audit_date=datetime.utcnow(),  # Schedule immediately on creation
    )
    db.add(proj)
    db.commit()
    db.refresh(proj)
    return proj


def update_project(db: Session, project_id: int, req: MonitoringProjectUpdate) -> MonitoringProject:
    proj = db.query(MonitoringProject).filter(MonitoringProject.id == project_id).first()
    if not proj:
        return None
    if req.name is not None:
        proj.name = req.name
    if req.frequency is not None:
        proj.frequency = req.frequency
        proj.next_audit_date = _get_next_audit_date(proj.frequency)
    if req.is_active is not None:
        proj.is_active = req.is_active
    if req.max_pages is not None:
        proj.max_pages = req.max_pages
    if req.max_depth is not None:
        proj.max_depth = req.max_depth
    db.commit()
    db.refresh(proj)
    return proj


def delete_project(db: Session, project_id: int) -> bool:
    proj = db.query(MonitoringProject).filter(MonitoringProject.id == project_id).first()
    if not proj:
        return False
    # Remove associated reports first to avoid FK issues
    db.query(MonitoringReport).filter(MonitoringReport.project_id == project_id).delete()
    db.delete(proj)
    db.commit()
    return True


def get_project(db: Session, project_id: int) -> MonitoringProject:
    return db.query(MonitoringProject).filter(MonitoringProject.id == project_id).first()


def list_projects(db: Session):
    return db.query(MonitoringProject).order_by(MonitoringProject.id.asc()).all()


def execute_monitoring_run(project_id: int, db: Session):
    """
    Background task:
    1. Creates a new Audit using the project's settings
    2. Runs the existing run_audit_task pipeline (no duplication)
    3. Compares with the previous audit
    4. Creates a MonitoringReport
    5. Updates the MonitoringProject timestamps

    Duplicate-run protection: if the same project is already running, skip.
    """
    if project_id in _running:
        logger.warning("Monitoring run for project %s is already in progress — skipping duplicate", project_id)
        return

    _running.add(project_id)
    try:
        _do_monitoring_run(project_id, db)
    finally:
        _running.discard(project_id)


def _do_monitoring_run(project_id: int, db: Session):
    proj = db.query(MonitoringProject).filter(MonitoringProject.id == project_id).first()
    if not proj:
        logger.error("execute_monitoring_run: project %s not found", project_id)
        return
    if not proj.is_active:
        logger.info("execute_monitoring_run: project %s is paused — skipping", project_id)
        return

    previous_audit_id = proj.last_audit_id

    # 1. Create a new Audit record
    new_audit = Audit(
        url=proj.url,
        max_pages=proj.max_pages,
        max_depth=proj.max_depth,
        status="pending",
    )
    db.add(new_audit)
    db.commit()
    db.refresh(new_audit)

    # 2. Run the existing audit pipeline (reuse — do NOT duplicate crawler/analysis)
    try:
        run_audit_task(new_audit.id)
    except Exception as e:
        logger.error("Monitoring audit %s failed during run_audit_task: %s", new_audit.id, e)

    # Re-fetch to get updated status/score after run_audit_task closes its own session
    db.expire_all()
    new_audit = db.query(Audit).filter(Audit.id == new_audit.id).first()
    proj = db.query(MonitoringProject).filter(MonitoringProject.id == project_id).first()

    if not new_audit or new_audit.status != "completed":
        logger.error(
            "Monitoring audit %s did not complete successfully (status=%s)",
            new_audit.id if new_audit else "?",
            new_audit.status if new_audit else "unknown",
        )
        # Update project's next audit date even on failure to avoid hammering a down site
        if proj:
            proj.next_audit_date = _get_next_audit_date(proj.frequency)
            db.commit()
        return

    # 3. Gather current audit metrics
    new_pages = db.query(Page).filter(Page.audit_id == new_audit.id).all()
    new_issues = db.query(SEOIssue).join(Page).filter(Page.audit_id == new_audit.id).all()

    changes_data = {
        "score_old": None,
        "score_new": new_audit.score,
        "critical_old": 0,
        "critical_new": sum(1 for i in new_issues if i.severity.lower() == "critical"),
        "high_old": 0,
        "high_new": sum(1 for i in new_issues if i.severity.lower() == "high"),
        "medium_old": 0,
        "medium_new": sum(1 for i in new_issues if i.severity.lower() == "medium"),
        "low_old": 0,
        "low_new": sum(1 for i in new_issues if i.severity.lower() == "low"),
        "pages_old": 0,
        "pages_new": len(new_pages),
        "resolved_issues": [],
        "new_issues": [],
    }

    score_change = 0

    # 4. Compare with previous audit if available
    if previous_audit_id:
        old_audit = db.query(Audit).filter(Audit.id == previous_audit_id).first()
        if old_audit and old_audit.status == "completed":
            changes_data["score_old"] = old_audit.score
            if old_audit.score is not None and new_audit.score is not None:
                score_change = new_audit.score - old_audit.score

            old_pages = db.query(Page).filter(Page.audit_id == old_audit.id).all()
            old_issues = db.query(SEOIssue).join(Page).filter(Page.audit_id == old_audit.id).all()

            changes_data["pages_old"] = len(old_pages)
            changes_data["critical_old"] = sum(1 for i in old_issues if i.severity.lower() == "critical")
            changes_data["high_old"] = sum(1 for i in old_issues if i.severity.lower() == "high")
            changes_data["medium_old"] = sum(1 for i in old_issues if i.severity.lower() == "medium")
            changes_data["low_old"] = sum(1 for i in old_issues if i.severity.lower() == "low")

            # Detect new and resolved issues by (issue_code, page_url) pair
            old_keys = {f"{i.issue_code}:{i.page_url}" for i in old_issues}
            new_keys = {f"{i.issue_code}:{i.page_url}" for i in new_issues}

            resolved_keys = old_keys - new_keys
            added_keys = new_keys - old_keys

            # De-duplicate by issue_code for summary display (take first occurrence)
            seen_resolved = set()
            resolved_list = []
            for i in old_issues:
                k = f"{i.issue_code}:{i.page_url}"
                if k in resolved_keys and i.issue_code not in seen_resolved:
                    seen_resolved.add(i.issue_code)
                    resolved_list.append({"code": i.issue_code, "title": i.title or i.issue_code, "url": i.page_url})

            seen_added = set()
            added_list = []
            for i in new_issues:
                k = f"{i.issue_code}:{i.page_url}"
                if k in added_keys and i.issue_code not in seen_added:
                    seen_added.add(i.issue_code)
                    added_list.append({"code": i.issue_code, "title": i.title or i.issue_code, "url": i.page_url})

            changes_data["resolved_issues"] = resolved_list
            changes_data["new_issues"] = added_list

    # 5. Persist monitoring report
    report = MonitoringReport(
        project_id=proj.id,
        audit_id=new_audit.id,
        previous_audit_id=previous_audit_id,
        score_change=score_change,
        changes_data=json.dumps(changes_data),
    )
    db.add(report)

    # 6. Update project pointers
    proj.last_audit_id = new_audit.id
    proj.last_audit_date = datetime.utcnow()
    proj.next_audit_date = _get_next_audit_date(proj.frequency)

    db.commit()
    logger.info(
        "Monitoring run for project %s complete. New audit=%s score=%s change=%s",
        project_id, new_audit.id, new_audit.score, score_change,
    )


def run_scheduler_tick(db: Session):
    """
    Find all active monitoring projects whose next_audit_date is <= now
    and trigger their audits sequentially.

    Safe to call from a cron job, background task, or health-check endpoint.
    Will never raise — failures are logged and skipped.
    """
    now = datetime.utcnow()
    due_projects = (
        db.query(MonitoringProject)
        .filter(
            MonitoringProject.is_active == True,
            MonitoringProject.next_audit_date <= now,
        )
        .all()
    )

    if not due_projects:
        logger.debug("Scheduler tick: no projects due.")
        return

    logger.info("Scheduler tick: %s project(s) due for audit", len(due_projects))
    for proj in due_projects:
        try:
            logger.info("Scheduler: triggering project %s (%s)", proj.id, proj.name)
            execute_monitoring_run(proj.id, db)
        except Exception as exc:
            logger.error("Scheduler: project %s failed: %s", proj.id, exc)
