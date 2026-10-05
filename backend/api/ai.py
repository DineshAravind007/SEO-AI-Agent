from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.database.connection import get_db
from backend.database.models import Audit, User
from backend.schemas.ai import AIRecommendationResponse
from backend.ai.service import generate_and_save_recommendations
from backend.security.auth import get_current_user

router = APIRouter(prefix="/api/audits", tags=["ai-recommendations"])

def _verify_audit_ai_access(audit_id: int, db: Session, user: User) -> Audit:
    db_audit = db.query(Audit).filter(Audit.id == audit_id).first()
    if not db_audit:
        raise HTTPException(status_code=404, detail="Audit not found")
    if db_audit.user_id is not None and db_audit.user_id != user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access recommendations for this audit")
    return db_audit

@router.post("/{audit_id}/recommendations", response_model=AIRecommendationResponse)
def create_recommendations(
    audit_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate or return existing AI recommendations for a completed audit."""
    _verify_audit_ai_access(audit_id, db, current_user)
    try:
        recommendations = generate_and_save_recommendations(audit_id, db)
        return AIRecommendationResponse(audit_id=audit_id, recommendations=recommendations)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="An unexpected error occurred while generating recommendations.")

@router.get("/{audit_id}/recommendations", response_model=AIRecommendationResponse)
def get_recommendations(
    audit_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return existing AI recommendations for an audit. Triggers generation if missing."""
    _verify_audit_ai_access(audit_id, db, current_user)
    try:
        recommendations = generate_and_save_recommendations(audit_id, db)
        return AIRecommendationResponse(audit_id=audit_id, recommendations=recommendations)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="An unexpected error occurred while retrieving recommendations.")
