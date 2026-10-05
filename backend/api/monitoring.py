import json
import logging
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List

from backend.database.connection import get_db
from backend.database.models import MonitoringProject, MonitoringReport, Audit
from backend.schemas.monitoring import (
    MonitoringProjectCreate,
    MonitoringProjectUpdate,
    MonitoringProjectResponse,
    MonitoringReportResponse,
)
from backend.services import monitoring_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/monitoring", tags=["monitoring"])


def _augment_project(proj: MonitoringProject, db: Session) -> dict:
    """Convert a MonitoringProject ORM to a dict augmented with last_score / score_change."""
    data = {
        "id": proj.id,
        "url": proj.url,
        "name": proj.name,
        "frequency": proj.frequency,
        "is_active": proj.is_active,
        "last_audit_id": proj.last_audit_id,
        "last_audit_date": proj.last_audit_date,
        "next_audit_date": proj.next_audit_date,
        "max_pages": proj.max_pages,
        "max_depth": proj.max_depth,
        "created_at": proj.created_at,
        "last_score": None,
        "score_change": None,
    }
    if proj.last_audit_id:
        last_audit = db.query(Audit).filter(Audit.id == proj.last_audit_id).first()
        if last_audit:
            data["last_score"] = last_audit.score

    # Find score change from the most recent monitoring report
    latest_report = (
        db.query(MonitoringReport)
        .filter(MonitoringReport.project_id == proj.id)
        .order_by(MonitoringReport.created_at.desc())
        .first()
    )
    if latest_report:
        data["score_change"] = latest_report.score_change

    return data


@router.post("", response_model=MonitoringProjectResponse)
def create_monitoring_project(req: MonitoringProjectCreate, db: Session = Depends(get_db)):
    proj = monitoring_service.create_project(db, req)
    return _augment_project(proj, db)


@router.get("", response_model=List[MonitoringProjectResponse])
def list_monitoring_projects(db: Session = Depends(get_db)):
    projects = monitoring_service.list_projects(db)
    return [_augment_project(p, db) for p in projects]


@router.get("/{project_id}", response_model=MonitoringProjectResponse)
def get_monitoring_project(project_id: int, db: Session = Depends(get_db)):
    proj = monitoring_service.get_project(db, project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Monitoring project not found")
    return _augment_project(proj, db)


@router.put("/{project_id}", response_model=MonitoringProjectResponse)
def update_monitoring_project(project_id: int, req: MonitoringProjectUpdate, db: Session = Depends(get_db)):
    proj = monitoring_service.update_project(db, project_id, req)
    if not proj:
        raise HTTPException(status_code=404, detail="Monitoring project not found")
    return _augment_project(proj, db)


@router.delete("/{project_id}")
def delete_monitoring_project(project_id: int, db: Session = Depends(get_db)):
    success = monitoring_service.delete_project(db, project_id)
    if not success:
        raise HTTPException(status_code=404, detail="Monitoring project not found")
    return {"status": "deleted"}


@router.post("/{project_id}/run")
def run_monitoring_audit_now(
    project_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    proj = monitoring_service.get_project(db, project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Monitoring project not found")
    if not proj.is_active:
        raise HTTPException(status_code=400, detail="Cannot run audit for a paused project. Resume it first.")

    background_tasks.add_task(monitoring_service.execute_monitoring_run, project_id, db)
    return {"status": "Audit triggered"}


@router.get("/{project_id}/history")
def get_monitoring_history(project_id: int, db: Session = Depends(get_db)):
    """Returns per-audit score / issue data for charting."""
    proj = monitoring_service.get_project(db, project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Monitoring project not found")

    reports = (
        db.query(MonitoringReport)
        .filter(MonitoringReport.project_id == project_id)
        .order_by(MonitoringReport.created_at.asc())
        .all()
    )
    history = []
    for r in reports:
        if r.changes_data:
            try:
                data = json.loads(r.changes_data)
                history.append({
                    "date": r.created_at.isoformat(),
                    "audit_id": r.audit_id,
                    "score": data.get("score_new"),
                    "critical_issues": data.get("critical_new", 0),
                    "high_issues": data.get("high_new", 0),
                    "medium_issues": data.get("medium_new", 0),
                    "low_issues": data.get("low_new", 0),
                    "page_count": data.get("pages_new", 0),
                })
            except (json.JSONDecodeError, Exception) as exc:
                logger.warning("Could not parse changes_data for report %s: %s", r.id, exc)
    return history


@router.get("/{project_id}/changes")
def get_monitoring_changes(project_id: int, db: Session = Depends(get_db)):
    """Returns the latest change summary (score delta, new/resolved issues)."""
    proj = monitoring_service.get_project(db, project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Monitoring project not found")

    latest_report = (
        db.query(MonitoringReport)
        .filter(MonitoringReport.project_id == project_id)
        .order_by(MonitoringReport.created_at.desc())
        .first()
    )
    if not latest_report:
        return {"has_changes": False}

    changes = {}
    if latest_report.changes_data:
        try:
            changes = json.loads(latest_report.changes_data)
        except (json.JSONDecodeError, Exception):
            pass

    return {
        "has_changes": True,
        "report_id": latest_report.id,
        "audit_id": latest_report.audit_id,
        "previous_audit_id": latest_report.previous_audit_id,
        "score_change": latest_report.score_change,
        "created_at": latest_report.created_at.isoformat(),
        **changes,
    }


@router.get("/{project_id}/reports", response_model=List[MonitoringReportResponse])
def list_reports(project_id: int, db: Session = Depends(get_db)):
    proj = monitoring_service.get_project(db, project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Monitoring project not found")

    reports = (
        db.query(MonitoringReport)
        .filter(MonitoringReport.project_id == project_id)
        .order_by(MonitoringReport.created_at.desc())
        .all()
    )
    return reports


@router.post("/scheduler/tick")
def trigger_scheduler_tick(db: Session = Depends(get_db)):
    """
    Trigger the monitoring scheduler manually (for cron/health-check integration).
    Finds all active projects that are due and runs their audits.
    """
    try:
        monitoring_service.run_scheduler_tick(db)
        return {"status": "Scheduler tick executed"}
    except Exception as exc:
        logger.error("Scheduler tick error: %s", exc)
        raise HTTPException(status_code=500, detail="Scheduler tick failed")
