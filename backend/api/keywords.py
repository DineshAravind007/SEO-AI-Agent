import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from backend.database.connection import get_db
from backend.database.models import Audit, KeywordAnalysis
from backend.schemas.keywords import KeywordAnalyzeRequest, KeywordAnalysisResult, KeywordUsage, KeywordGap
from backend.services.keyword_service import analyze_keyword

router = APIRouter(prefix="/api/audits/{audit_id}/keywords", tags=["keywords"])

@router.post("/analyze", response_model=List[KeywordAnalysisResult])
def analyze_keywords(
    audit_id: int,
    req: KeywordAnalyzeRequest,
    db: Session = Depends(get_db)
):
    audit = db.query(Audit).filter(Audit.id == audit_id).first()
    if not audit:
        raise HTTPException(status_code=404, detail="Audit not found")
        
    if audit.status != "completed":
        raise HTTPException(status_code=400, detail="Cannot analyze keywords for an incomplete audit.")

    results = []
    for kw in req.keywords:
        # Check if already analyzed
        existing = db.query(KeywordAnalysis).filter(KeywordAnalysis.audit_id == audit_id, KeywordAnalysis.keyword == kw).first()
        if existing:
            # Reconstruct result
            analysis_data = json.loads(existing.analysis_data) if existing.analysis_data else {}
            results.append(KeywordAnalysisResult(
                id=existing.id,
                audit_id=existing.audit_id,
                keyword=existing.keyword,
                opportunity_score=existing.opportunity_score or 0,
                intent=existing.intent or "Informational",
                usage=KeywordUsage(
                    title_matches=analysis_data.get("title_matches", 0),
                    meta_matches=analysis_data.get("meta_matches", 0),
                    h1_matches=analysis_data.get("h1_matches", 0),
                    h2_matches=analysis_data.get("h2_matches", 0),
                    body_matches=analysis_data.get("body_matches", 0),
                    pages_containing=analysis_data.get("pages_containing", 0),
                    total_pages_crawled=analysis_data.get("total_pages_crawled", 0)
                ),
                gaps=[KeywordGap(**g) for g in analysis_data.get("gaps", [])],
                suggestions=json.loads(existing.suggestions_data) if existing.suggestions_data else []
            ))
        else:
            result = analyze_keyword(db, audit, kw)
            results.append(result)
            
    return results

@router.get("", response_model=List[KeywordAnalysisResult])
def get_keywords(audit_id: int, db: Session = Depends(get_db)):
    audit = db.query(Audit).filter(Audit.id == audit_id).first()
    if not audit:
        raise HTTPException(status_code=404, detail="Audit not found")
        
    analyses = db.query(KeywordAnalysis).filter(KeywordAnalysis.audit_id == audit_id).all()
    results = []
    
    for existing in analyses:
        analysis_data = json.loads(existing.analysis_data) if existing.analysis_data else {}
        results.append(KeywordAnalysisResult(
            id=existing.id,
            audit_id=existing.audit_id,
            keyword=existing.keyword,
            opportunity_score=existing.opportunity_score or 0,
            intent=existing.intent or "Informational",
            usage=KeywordUsage(
                title_matches=analysis_data.get("title_matches", 0),
                meta_matches=analysis_data.get("meta_matches", 0),
                h1_matches=analysis_data.get("h1_matches", 0),
                h2_matches=analysis_data.get("h2_matches", 0),
                body_matches=analysis_data.get("body_matches", 0),
                pages_containing=analysis_data.get("pages_containing", 0),
                total_pages_crawled=analysis_data.get("total_pages_crawled", 0)
            ),
            gaps=[KeywordGap(**g) for g in analysis_data.get("gaps", [])],
            suggestions=json.loads(existing.suggestions_data) if existing.suggestions_data else []
        ))
        
    return results
