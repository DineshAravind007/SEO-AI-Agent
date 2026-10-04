from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.database.connection import get_db
from backend.schemas.ai import AIRecommendationResponse
from backend.ai.service import generate_and_save_recommendations

router = APIRouter(prefix="/api/audits", tags=["ai-recommendations"])

@router.post("/{audit_id}/recommendations", response_model=AIRecommendationResponse)
def create_recommendations(audit_id: int, db: Session = Depends(get_db)):
    """Generate or return existing AI recommendations for a completed audit."""
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
def get_recommendations(audit_id: int, db: Session = Depends(get_db)):
    """Return existing AI recommendations for an audit. Triggers generation if missing."""
    try:
        recommendations = generate_and_save_recommendations(audit_id, db)
        return AIRecommendationResponse(audit_id=audit_id, recommendations=recommendations)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="An unexpected error occurred while retrieving recommendations.")
