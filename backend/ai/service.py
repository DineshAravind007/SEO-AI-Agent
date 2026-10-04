from typing import List, Dict, Any
import logging
from sqlalchemy.orm import Session

from backend.database.models import Audit, SEOIssue, AIRecommendation
from backend.ai.provider import get_llm_provider
from backend.ai.prompts import build_system_prompt, build_user_prompt
from backend.schemas.ai import AIRecommendationItem

logger = logging.getLogger(__name__)

# Maximum number of unique issues to send to the LLM to save tokens and latency
MAX_ISSUES_PER_REQUEST = 15

def generate_and_save_recommendations(audit_id: int, db: Session) -> List[AIRecommendationItem]:
    audit = db.query(Audit).filter(Audit.id == audit_id).first()
    if not audit:
        raise ValueError(f"Audit {audit_id} not found")
        
    if audit.status != "completed":
        raise ValueError(f"Audit {audit_id} is not completed. Current status: {audit.status}")

    # Check if we already generated recommendations for this audit
    existing_recs = db.query(AIRecommendation).filter(AIRecommendation.audit_id == audit_id).all()
    if existing_recs:
        logger.info(f"Returning {len(existing_recs)} existing recommendations for audit {audit_id}.")
        return [
            AIRecommendationItem(
                issue_type=r.issue_type,
                severity=r.severity,
                title=r.title,
                explanation=r.explanation,
                recommendation=r.recommendation,
                suggested_action=r.suggested_action,
                example=r.example,
                confidence=r.confidence
            ) for r in existing_recs
        ]

    # Gather unique issues to avoid duplicate processing
    from backend.database.models import Page
    all_issues = db.query(SEOIssue).join(Page, SEOIssue.page_id == Page.id).filter(Page.audit_id == audit_id).all()
    
    unique_issues_map: Dict[str, SEOIssue] = {}
    for issue in all_issues:
        if issue.issue_code not in unique_issues_map:
            unique_issues_map[issue.issue_code] = issue
            
    # Sort by severity: CRITICAL > HIGH > MEDIUM > LOW
    severity_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    sorted_issues = sorted(
        unique_issues_map.values(), 
        key=lambda i: severity_order.get(i.severity, 4)
    )
    
    # Apply limit
    limited_issues = sorted_issues[:MAX_ISSUES_PER_REQUEST]
    
    if not limited_issues:
        logger.info(f"No issues found for audit {audit_id}. Skipping AI recommendation.")
        return []

    # Build Context
    audit_context = {
        "url": audit.url,
        "score": audit.score
    }
    issues_context = [
        {
            "issue_code": i.issue_code,
            "severity": i.severity,
            "category": i.category,
            "title": i.title,
            "description": i.description,
            "impact": i.impact
        }
        for i in limited_issues
    ]

    # Build prompts
    system_prompt = build_system_prompt()
    user_prompt = build_user_prompt(audit_context, issues_context)

    # Call LLM
    provider = get_llm_provider()
    logger.info(f"Calling LLM provider for audit {audit_id} with {len(issues_context)} issues.")
    
    try:
        recommendation_items = provider.generate_recommendations(system_prompt, user_prompt)
    except Exception as e:
        logger.error(f"Failed to generate recommendations: {e}")
        raise RuntimeError("Failed to generate AI recommendations from provider.")

    # Save to database
    db_recs = []
    for item in recommendation_items:
        db_rec = AIRecommendation(
            audit_id=audit_id,
            issue_type=item.issue_type,
            severity=item.severity,
            title=item.title,
            explanation=item.explanation,
            recommendation=item.recommendation,
            suggested_action=item.suggested_action,
            example=item.example,
            confidence=item.confidence
        )
        db.add(db_rec)
        db_recs.append(item)
        
    db.commit()
    logger.info(f"Saved {len(db_recs)} AI recommendations for audit {audit_id}.")
    
    return db_recs
