from pydantic import BaseModel, HttpUrl, Field, field_validator
from typing import List, Optional
from backend.crawler.validator import normalize_url, is_safe_url
from backend.schemas.audits import AuditResponse

class CompetitorRequest(BaseModel):
    urls: List[str] = Field(..., min_length=1, max_length=3)
    
    @field_validator("urls")
    @classmethod
    def validate_urls(cls, v: List[str]) -> List[str]:
        normalized = []
        for url in v:
            url_norm = normalize_url(url)
            if not is_safe_url(url_norm):
                raise ValueError(f"Invalid or unsafe URL: {url}")
            normalized.append(url_norm)
        # Ensure uniqueness
        if len(set(normalized)) != len(normalized):
            raise ValueError("Duplicate competitor URLs are not allowed.")
        return normalized

class CompetitorResult(BaseModel):
    id: int
    competitor_audit: AuditResponse
    
    class Config:
        from_attributes = True

class MetricComparison(BaseModel):
    metric: str
    user_value: str
    competitor_value: str
    difference: str

class GapAnalysis(BaseModel):
    category: str
    metric: str
    user_value: str
    competitor_value: str
    difference: str
    severity: str
    explanation: str
    recommended_action: str

class ComparisonData(BaseModel):
    competitor_url: str
    competitor_audit_id: int
    seo_score: Optional[int]
    seo_grade: Optional[str]
    total_issues: int
    severity_counts: dict
    category_counts: dict
    metrics: List[MetricComparison]
    gaps: List[GapAnalysis]

class ComparisonResponse(BaseModel):
    base_audit_id: int
    base_url: str
    base_seo_score: Optional[int]
    base_seo_grade: Optional[str]
    base_total_issues: int
    base_severity_counts: dict
    base_category_counts: dict
    competitors: List[ComparisonData]
