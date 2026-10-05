from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Any
from datetime import datetime

from backend.crawler.validator import normalize_url, is_safe_url

_VALID_FREQUENCIES = {"daily", "weekly", "monthly"}


class MonitoringProjectCreate(BaseModel):
    url: str
    name: str = Field(..., min_length=1, max_length=200)
    frequency: str = Field("weekly", description="daily, weekly, monthly")
    max_pages: int = Field(10, ge=1, le=50)
    max_depth: int = Field(2, ge=1, le=5)

    @field_validator("frequency")
    @classmethod
    def validate_frequency(cls, v: str) -> str:
        v = v.lower().strip()
        if v not in _VALID_FREQUENCIES:
            raise ValueError(f"frequency must be one of: {', '.join(sorted(_VALID_FREQUENCIES))}")
        return v

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        v = normalize_url(v.strip())
        if not is_safe_url(v):
            raise ValueError("Invalid or unsafe URL.")
        return v


class MonitoringProjectUpdate(BaseModel):
    name: Optional[str] = None
    frequency: Optional[str] = None
    is_active: Optional[bool] = None
    max_pages: Optional[int] = Field(None, ge=1, le=50)
    max_depth: Optional[int] = Field(None, ge=1, le=5)

    @field_validator("frequency")
    @classmethod
    def validate_frequency(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.lower().strip()
        if v not in _VALID_FREQUENCIES:
            raise ValueError(f"frequency must be one of: {', '.join(sorted(_VALID_FREQUENCIES))}")
        return v


class MonitoringProjectResponse(BaseModel):
    id: int
    url: str
    name: str
    frequency: str
    is_active: bool
    last_audit_id: Optional[int]
    last_audit_date: Optional[datetime]
    next_audit_date: Optional[datetime]
    max_pages: int
    max_depth: int
    created_at: datetime

    # Augmented fields resolved in the service/API layer
    last_score: Optional[int] = None
    score_change: Optional[int] = None

    class Config:
        from_attributes = True


class MonitoringReportResponse(BaseModel):
    id: int
    project_id: int
    audit_id: int
    previous_audit_id: Optional[int]
    score_change: Optional[int]
    changes_data: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True
