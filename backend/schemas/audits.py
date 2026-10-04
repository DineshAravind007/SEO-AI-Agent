from pydantic import BaseModel, HttpUrl, Field, field_validator
from typing import Optional
from backend.crawler.validator import normalize_url, is_safe_url

class AuditRequest(BaseModel):
    url: str
    max_pages: Optional[int] = Field(default=10, ge=1, le=50)
    max_depth: Optional[int] = Field(default=2, ge=0, le=3)

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        v = normalize_url(v)
        if not is_safe_url(v):
            raise ValueError("Invalid or unsafe URL.")
        return v

class AuditResponse(BaseModel):
    id: int
    url: str
    status: str
    max_pages: int
    max_depth: int
    error_message: Optional[str] = None

    class Config:
        from_attributes = True

class PageResponse(BaseModel):
    id: int
    url: str
    status_code: Optional[int]
    title: Optional[str]
    crawl_status: str

    class Config:
        from_attributes = True

class SEOIssueResponse(BaseModel):
    id: int
    page_url: str
    category: str
    severity: str
    issue_code: str
    title: str
    description: str
    recommendation_summary: str
    impact: str

    class Config:
        from_attributes = True
