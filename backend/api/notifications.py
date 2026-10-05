from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from backend.database.connection import get_db
from backend.database.models import User, NotificationHistory
from backend.schemas.notifications import NotificationPreferenceResponse, NotificationPreferenceUpdate, NotificationHistoryResponse
from backend.services.notification_service import notification_service
from backend.security.auth import get_current_user

router = APIRouter(prefix="/api/notifications", tags=["notifications"])

@router.get("/preferences", response_model=NotificationPreferenceResponse)
def get_notification_preferences(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get the current user's notification preferences."""
    prefs = notification_service.get_preferences(db, current_user.id)
    return prefs

@router.put("/preferences", response_model=NotificationPreferenceResponse)
def update_notification_preferences(
    req: NotificationPreferenceUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update the current user's notification preferences."""
    prefs = notification_service.update_preferences(db, current_user.id, req.model_dump())
    return prefs

@router.get("/history", response_model=List[NotificationHistoryResponse])
def get_notification_history(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get the current user's notification history."""
    history = db.query(NotificationHistory).filter(NotificationHistory.user_id == current_user.id).order_by(NotificationHistory.sent_at.desc()).all()
    return history
