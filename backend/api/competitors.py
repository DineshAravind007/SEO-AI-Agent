from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
import json

from backend.database.connection import get_db
from backend.database.models import Audit, CompetitorAnalysis, Page, SEOIssue
from backend.schemas.competitors import CompetitorRequest, CompetitorResult, ComparisonResponse
from backend.schemas.audits import AuditResponse
from backend.services.audit_service import run_audit_task
from backend.services.comparison_service import compare_audits

router = APIRouter(prefix="/api/audits/{audit_id}/competitors", tags=["competitors"])

@router.post("", response_model=list[CompetitorResult])
def add_competitors(
    audit_id: int,
    req: CompetitorRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    base_audit = db.query(Audit).filter(Audit.id == audit_id).first()
    if not base_audit:
        raise HTTPException(status_code=404, detail="Base audit not found")
        
    results = []
    
    # Check if any requested URL is same as base audit URL
    for url in req.urls:
        if url.rstrip('/') == base_audit.url.rstrip('/'):
            raise HTTPException(status_code=400, detail="Cannot add the base website as its own competitor.")
            
    for url in req.urls:
        # Check if already exists for this base audit
        existing = db.query(CompetitorAnalysis).join(Audit, CompetitorAnalysis.competitor_audit_id == Audit.id).filter(
            CompetitorAnalysis.base_audit_id == audit_id,
            Audit.url == url
        ).first()
        
        if existing:
            comp_audit = existing.competitor_audit
        else:
            comp_audit = Audit(
                url=url,
                max_pages=base_audit.max_pages,
                max_depth=base_audit.max_depth,
                status="pending",
                is_competitor=True
            )
            db.add(comp_audit)
            db.flush()
            
            comp_link = CompetitorAnalysis(
                base_audit_id=audit_id,
                competitor_audit_id=comp_audit.id
            )
            db.add(comp_link)
            
            background_tasks.add_task(run_audit_task, comp_audit.id)
            
        results.append(CompetitorResult(
            id=comp_audit.id,
            competitor_audit=comp_audit
        ))
        
    db.commit()
    return results

@router.get("", response_model=list[CompetitorResult])
def get_competitors(audit_id: int, db: Session = Depends(get_db)):
    base_audit = db.query(Audit).filter(Audit.id == audit_id).first()
    if not base_audit:
        raise HTTPException(status_code=404, detail="Base audit not found")
        
    links = db.query(CompetitorAnalysis).filter(CompetitorAnalysis.base_audit_id == audit_id).all()
    results = []
    for link in links:
        results.append(CompetitorResult(
            id=link.competitor_audit_id,
            competitor_audit=link.competitor_audit
        ))
    return results

@router.get("/comparison", response_model=ComparisonResponse)
def compare_competitors(audit_id: int, db: Session = Depends(get_db)):
    base_audit = db.query(Audit).filter(Audit.id == audit_id).first()
    if not base_audit:
        raise HTTPException(status_code=404, detail="Base audit not found")
        
    if base_audit.status != "completed":
        raise HTTPException(status_code=400, detail="Base audit must be completed to generate comparison.")
        
    links = db.query(CompetitorAnalysis).filter(CompetitorAnalysis.base_audit_id == audit_id).all()
    
    competitors_data = []
    for link in links:
        if link.competitor_audit.status == "completed":
            comp_data = compare_audits(db, base_audit, link.competitor_audit)
            competitors_data.append(comp_data)
            
    base_score_data = json.loads(base_audit.score_data) if base_audit.score_data else {}
    base_issues_count = db.query(SEOIssue).join(Page).filter(Page.audit_id == base_audit.id).count()
    
    return ComparisonResponse(
        base_audit_id=base_audit.id,
        base_url=base_audit.url,
        base_seo_score=base_audit.score,
        base_seo_grade=base_score_data.get("grade"),
        base_total_issues=base_issues_count,
        base_severity_counts=base_score_data.get("severity_counts", {}),
        base_category_counts=base_score_data.get("category_counts", {}),
        competitors=competitors_data
    )
