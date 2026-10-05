from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class NotificationPreferenceBase(BaseModel):
    email_enabled: bool = True
    score_drop_alert: bool = True
    critical_issue_alert: bool = True
    high_issue_alert: bool = True
    weekly_summary: bool = False

class NotificationPreferenceUpdate(NotificationPreferenceBase):
    pass

class NotificationPreferenceResponse(NotificationPreferenceBase):
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class NotificationHistoryResponse(BaseModel):
    id: int
    user_id: int
    monitoring_project_id: Optional[int]
    notification_type: str
    severity: str
    recipient: str
    status: str
    error_message: Optional[str]
    sent_at: datetime

    class Config:
        from_attributes = True
