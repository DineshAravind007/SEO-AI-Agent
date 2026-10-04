import json
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from backend.database.connection import get_db
from backend.database.models import Audit, Page, SEOIssue
from backend.schemas.audits import AuditRequest, AuditResponse, SEOIssueResponse, ScoreResponse
from backend.services.audit_service import run_audit_task
from typing import List, Any

router = APIRouter(prefix="/api/audits", tags=["audits"])


def _serialize_page(p: Page) -> dict:
    """Serialize a Page ORM object to a JSON-safe dict."""
    return {
        "id": p.id,
        "audit_id": p.audit_id,
        "url": p.url,
        "final_url": p.final_url,
        "depth": p.depth,
        "status_code": p.status_code,
        "content_type": p.content_type,
        "title": p.title,
        "title_length": p.title_length,
        "meta_description": p.meta_description,
        "meta_description_length": p.meta_description_length,
        "h1_list": json.loads(p.h1_list) if p.h1_list else [],
        "h1_count": p.h1_count,
        "h2_list": json.loads(p.h2_list) if p.h2_list else [],
        "h2_count": p.h2_count,
        "canonical_url": p.canonical_url,
        "meta_robots": p.meta_robots,
        "x_robots_tag": p.x_robots_tag,
        "html_language": p.html_language,
        "viewport_meta_presence": p.viewport_meta_presence,
        "word_count": p.word_count,
        "image_count": p.image_count,
        "images_missing_alt": p.images_missing_alt,
        "internal_link_count": p.internal_link_count,
        "external_link_count": p.external_link_count,
        "open_graph_presence": p.open_graph_presence,
        "structured_data_presence": p.structured_data_presence,
        "crawl_status": p.crawl_status,
        "error_message": p.error_message,
    }


def _serialize_issue(i: SEOIssue) -> dict:
    return {
        "id": i.id,
        "page_url": i.page_url,
        "category": i.category,
        "severity": i.severity,
        "issue_code": i.issue_code,
        "title": i.title,
        "description": i.description,
        "recommendation_summary": i.recommendation_summary,
        "impact": i.impact,
    }


@router.post("", response_model=AuditResponse)
def create_audit(
    audit_req: AuditRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    db_audit = Audit(
        url=audit_req.url,
        max_pages=audit_req.max_pages,
        max_depth=audit_req.max_depth,
        status="pending",
    )
    db.add(db_audit)
    db.commit()
    db.refresh(db_audit)

    background_tasks.add_task(run_audit_task, db_audit.id)

    return db_audit


@router.get("/{audit_id}", response_model=AuditResponse)
def get_audit(audit_id: int, db: Session = Depends(get_db)):
    db_audit = db.query(Audit).filter(Audit.id == audit_id).first()
    if not db_audit:
        raise HTTPException(status_code=404, detail="Audit not found")
    return db_audit


@router.get("/{audit_id}/pages")
def get_audit_pages(audit_id: int, db: Session = Depends(get_db)):
    pages = db.query(Page).filter(Page.audit_id == audit_id).all()
    return {"pages": [_serialize_page(p) for p in pages]}


@router.get("/{audit_id}/issues")
def get_audit_issues(audit_id: int, db: Session = Depends(get_db)):
    issues = (
        db.query(SEOIssue)
        .join(Page, SEOIssue.page_id == Page.id)
        .filter(Page.audit_id == audit_id)
        .all()
    )
    return {"issues": [_serialize_issue(i) for i in issues]}

@router.get("/{audit_id}/score", response_model=ScoreResponse)
def get_audit_score(audit_id: int, db: Session = Depends(get_db)):
    db_audit = db.query(Audit).filter(Audit.id == audit_id).first()
    if not db_audit:
        raise HTTPException(status_code=404, detail="Audit not found")
        
    if db_audit.status != "completed":
        raise HTTPException(status_code=400, detail="Score is not available until the audit is completed.")
        
    if not db_audit.score_data:
        raise HTTPException(status_code=404, detail="Score data not found for this audit.")
        
    return json.loads(db_audit.score_data)
