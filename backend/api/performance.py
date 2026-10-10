"""
Performance API endpoints.

All endpoints require authentication via JWT.
All endpoints verify audit ownership — users cannot access other users' data.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Dict, Any

from backend.database.connection import get_db
from backend.database.models import User, Audit, AuditPerformance, PagePerformance, Page, SEOIssue
from backend.security.auth import get_current_user
from backend.services.performance_analyzer import CWV_UNAVAILABLE_NOTE

router = APIRouter(prefix="/api/audits", tags=["performance"])


def _verify_audit_ownership(audit_id: int, current_user: User, db: Session) -> Audit:
    """
    Fetch the audit and verify ownership.
    Raises 404 if not found, 403 if user doesn't own it.
    """
    audit = db.query(Audit).filter(Audit.id == audit_id).first()
    if not audit:
        raise HTTPException(status_code=404, detail="Audit not found")
    if audit.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access this audit")
    return audit


@router.get("/{audit_id}/performance", response_model=Dict[str, Any])
def get_audit_performance(
    audit_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get aggregated performance analysis for an entire audit.

    Returns:
    - performance_score: 0-100, null if not yet analyzed
    - avg_response_time_ms: average across all crawled pages
    - total_html_size_bytes: sum of HTML sizes
    - pages_analyzed: count of pages with performance data
    - pages_count: total pages in audit
    - CWV: all UNAVAILABLE (requires browser) with explanation
    - performance_issues: all detected performance issues
    - opportunities_count: total number of performance issues
    - audit_status: for UI to detect incomplete audits
    """
    audit = _verify_audit_ownership(audit_id, current_user, db)

    # Return structured response even for incomplete audits
    if audit.status not in ("completed",):
        return {
            "audit_status": audit.status,
            "audit_id": audit_id,
            "performance_score": None,
            "avg_response_time_ms": None,
            "total_html_size_bytes": None,
            "pages_analyzed": 0,
            "pages_count": 0,
            "lcp_status": "UNAVAILABLE",
            "inp_status": "UNAVAILABLE",
            "cls_status": "UNAVAILABLE",
            "cwv_note": CWV_UNAVAILABLE_NOTE,
            "performance_issues": [],
            "opportunities_count": 0,
            "score_categories": {},
        }

    # Fetch aggregated performance
    perf = db.query(AuditPerformance).filter(AuditPerformance.audit_id == audit_id).first()
    pages_count = db.query(Page).filter(Page.audit_id == audit_id).count()
    pages_analyzed = (
        db.query(PagePerformance)
        .join(Page)
        .filter(Page.audit_id == audit_id)
        .count()
    )

    # Fetch all performance issues for this audit
    perf_issues = (
        db.query(SEOIssue)
        .join(Page)
        .filter(Page.audit_id == audit_id, SEOIssue.category == "Performance")
        .all()
    )

    issues_data = [
        {
            "id": i.id,
            "page_url": i.page_url,
            "issue_code": i.issue_code,
            "severity": i.severity,
            "title": i.title,
            "description": i.description,
            "recommendation_summary": i.recommendation_summary,
            "impact": i.impact,
        }
        for i in perf_issues
    ]

    # Score category breakdown — count issues by code
    from collections import Counter
    issue_code_counts = Counter(i.issue_code for i in perf_issues)

    score_categories = {
        "server_response": {
            "label": "Server Response Time",
            "issues": issue_code_counts.get("SLOW_SERVER_RESPONSE", 0),
        },
        "document_size": {
            "label": "Document Size",
            "issues": issue_code_counts.get("LARGE_HTML_DOCUMENT", 0),
        },
        "images": {
            "label": "Image Optimization",
            "issues": issue_code_counts.get("MISSING_IMAGE_DIMENSIONS", 0),
        },
        "compression": {
            "label": "Compression",
            "issues": issue_code_counts.get("MISSING_COMPRESSION", 0),
        },
        "caching": {
            "label": "Caching",
            "issues": issue_code_counts.get("MISSING_CACHE_CONTROL", 0),
        },
        "security": {
            "label": "HTTPS",
            "issues": issue_code_counts.get("NOT_HTTPS", 0),
        },
        "mobile": {
            "label": "Mobile Readiness",
            "issues": issue_code_counts.get("MISSING_VIEWPORT_META", 0),
        },
    }

    if not perf:
        return {
            "audit_status": audit.status,
            "audit_id": audit_id,
            "performance_score": None,
            "avg_response_time_ms": None,
            "total_html_size_bytes": None,
            "pages_analyzed": pages_analyzed,
            "pages_count": pages_count,
            "lcp_status": "UNAVAILABLE",
            "inp_status": "UNAVAILABLE",
            "cls_status": "UNAVAILABLE",
            "cwv_note": CWV_UNAVAILABLE_NOTE,
            "performance_issues": issues_data,
            "opportunities_count": len(issues_data),
            "score_categories": score_categories,
        }

    return {
        "audit_status": audit.status,
        "audit_id": audit_id,
        "performance_score": perf.performance_score,
        "avg_response_time_ms": perf.avg_response_time_ms,
        "total_html_size_bytes": perf.total_page_size_bytes,
        "pages_analyzed": pages_analyzed,
        "pages_count": pages_count,
        "lcp_status": perf.lcp_status,
        "inp_status": perf.inp_status,
        "cls_status": perf.cls_status,
        "cwv_note": CWV_UNAVAILABLE_NOTE,
        "performance_issues": issues_data,
        "opportunities_count": len(issues_data),
        "score_categories": score_categories,
    }


@router.get("/{audit_id}/pages-performance", response_model=List[Dict[str, Any]])
def get_pages_performance(
    audit_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get page-level performance metrics for all pages in an audit.
    Only authenticated users can access their own audits.
    """
    _verify_audit_ownership(audit_id, current_user, db)

    rows = (
        db.query(PagePerformance, Page.url)
        .join(Page)
        .filter(Page.audit_id == audit_id)
        .all()
    )

    return [
        {
            "page_id": perf.page_id,
            "url": url,
            "response_time_ms": perf.response_time_ms,
            "html_size_bytes": perf.html_size_bytes,
            "is_compressed": perf.is_compressed,
            "has_cache_control": perf.has_cache_control,
            "image_count": perf.image_count,
            "missing_dimensions_count": perf.missing_dimensions_count,
            "lcp_status": perf.lcp_status,
            "inp_status": perf.inp_status,
            "cls_status": perf.cls_status,
            "ttfb_ms": perf.ttfb_ms,
            "fcp_ms": perf.fcp_ms,
            "performance_score": perf.performance_score,
        }
        for perf, url in rows
    ]
