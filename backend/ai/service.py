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


def generate_and_save_recommendations(
    audit_id: int,
    db: Session,
    force: bool = False,
) -> List[AIRecommendationItem]:
    """Generate AI recommendations for a completed audit and persist them.

    When *force* is False (default) cached recommendations are returned
    immediately so duplicate requests are cheap and idempotent.

    When *force* is True any previously stored recommendations are safely
    replaced only after fresh provider generation succeeds. If provider
    generation fails, existing recommendations are preserved.
    """
    audit = db.query(Audit).filter(Audit.id == audit_id).first()
    if not audit:
        raise ValueError(f"Audit {audit_id} not found")

    if audit.status != "completed":
        raise ValueError(f"Audit {audit_id} is not completed. Current status: {audit.status}")

    # ------------------------------------------------------------------ #
    # Cache handling                                                     #
    # ------------------------------------------------------------------ #
    existing_recs = (
        db.query(AIRecommendation)
        .filter(AIRecommendation.audit_id == audit_id)
        .all()
    )

    if existing_recs and not force:
        logger.info(
            "Returning %d existing recommendations for audit %d.",
            len(existing_recs), audit_id,
        )
        return [
            AIRecommendationItem(
                issue_type=r.issue_type,
                severity=r.severity,
                title=r.title,
                explanation=r.explanation,
                recommendation=r.recommendation,
                suggested_action=r.suggested_action,
                example=r.example,
                confidence=r.confidence,
            )
            for r in existing_recs
        ]

    # ------------------------------------------------------------------ #
    # Gather unique issues                                               #
    # ------------------------------------------------------------------ #
    from backend.database.models import Page

    all_issues = (
        db.query(SEOIssue)
        .join(Page, SEOIssue.page_id == Page.id)
        .filter(Page.audit_id == audit_id)
        .all()
    )

    unique_issues_map: Dict[str, SEOIssue] = {}
    for issue in all_issues:
        if issue.issue_code not in unique_issues_map:
            unique_issues_map[issue.issue_code] = issue

    # Sort by severity: CRITICAL > HIGH > MEDIUM > LOW
    severity_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    sorted_issues = sorted(
        unique_issues_map.values(),
        key=lambda i: severity_order.get(i.severity, 4),
    )

    # Apply limit
    limited_issues = sorted_issues[:MAX_ISSUES_PER_REQUEST]

    if not limited_issues:
        logger.info("No issues found for audit %d. Skipping AI recommendation.", audit_id)
        return []

    # ------------------------------------------------------------------ #
    # Build prompts                                                      #
    # ------------------------------------------------------------------ #
    audit_context = {"url": audit.url, "score": audit.score}
    issues_context = [
        {
            "issue_code": i.issue_code,
            "severity": i.severity,
            "category": i.category,
            "title": i.title,
            "description": i.description,
            "impact": i.impact,
        }
        for i in limited_issues
    ]

    system_prompt = build_system_prompt()
    user_prompt = build_user_prompt(audit_context, issues_context)

    # ------------------------------------------------------------------ #
    # Call LLM provider                                                 #
    # ------------------------------------------------------------------ #
    provider = get_llm_provider()
    logger.info(
        "Calling LLM provider (%s) for audit %d with %d issues.",
        type(provider).__name__, audit_id, len(issues_context),
    )

    try:
        recommendation_items = provider.generate_recommendations(system_prompt, user_prompt)
    except Exception as e:
        logger.error("Failed to generate recommendations: %s", e)
        raise RuntimeError("Failed to generate AI recommendations from provider.")

    # ------------------------------------------------------------------ #
    # Persist to database (safely replace if force=True)                 #
    # ------------------------------------------------------------------ #
    if existing_recs and force:
        logger.info(
            "force=True: replacing %d stale recommendations for audit %d.",
            len(existing_recs), audit_id,
        )
        for rec in existing_recs:
            db.delete(rec)

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
            confidence=item.confidence,
        )
        db.add(db_rec)
        db_recs.append(item)

    db.commit()
    logger.info("Saved %d AI recommendations for audit %d.", len(db_recs), audit_id)

    return db_recs
