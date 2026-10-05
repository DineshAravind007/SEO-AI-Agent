import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
from sqlalchemy import or_
from sqlalchemy.orm import Session
from backend.database.models import MonitoringProject, MonitoringReport, Audit, SEOIssue, Page, User
from backend.schemas.monitoring import MonitoringProjectCreate, MonitoringProjectUpdate
from backend.services.audit_service import run_audit_task
from backend.services.change_detection_service import detect_changes
from backend.services.notification_service import notification_service

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


def create_project(db: Session, req: MonitoringProjectCreate, user_id: Optional[int] = None) -> MonitoringProject:
    proj = MonitoringProject(
        user_id=user_id,
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


def list_projects(db: Session, user_id: Optional[int] = None):
    query = db.query(MonitoringProject)
    if user_id is not None:
        query = query.filter(or_(MonitoringProject.user_id == user_id, MonitoringProject.user_id.is_(None)))
    return query.order_by(MonitoringProject.id.asc()).all()


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

    # 4. Compare with previous audit if available
    changes_data = {}
    score_change = 0
    change_severity = "NO_CHANGE"
    
    if previous_audit_id:
        old_audit = db.query(Audit).filter(Audit.id == previous_audit_id).first()
        if old_audit and old_audit.status == "completed":
            old_pages = db.query(Page).filter(Page.audit_id == old_audit.id).all()
            old_issues = db.query(SEOIssue).join(Page).filter(Page.audit_id == old_audit.id).all()

            changes_data = detect_changes(old_audit, new_audit, old_pages, new_pages, old_issues, new_issues)
            score_change = changes_data.get("score_change", 0)
            change_severity = changes_data.get("change_severity", "NO_CHANGE")
    else:
        # First run - no old audit
        changes_data = detect_changes(None, new_audit, [], new_pages, [], new_issues)
        score_change = changes_data.get("score_change", 0)
        change_severity = changes_data.get("change_severity", "NO_CHANGE")

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

    # 7. Notifications
    user = db.query(User).filter(User.id == proj.user_id).first()
    if user and change_severity in ["CRITICAL", "HIGH"] or score_change < -5:
        subject = f"SEO Alert: {proj.name} ({change_severity})"
        body = f"""
        <html>
        <body>
            <h2>SEO Alert for {proj.name}</h2>
            <p>Score changed by <strong>{score_change}</strong> (Now {new_audit.score}).</p>
            <p>Severity: <strong>{change_severity}</strong></p>
            <p>Please check your monitoring dashboard for more details.</p>
        </body>
        </html>
        """
        
        # Determine notification type
        alert_type = "high_issue"
        if change_severity == "CRITICAL":
            alert_type = "critical_issue"
        if score_change <= -5:
            alert_type = "score_drop"
            
        notification_service.send_alert(db, user, proj.id, alert_type, change_severity, subject, body)
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
