from pydantic import BaseModel, Field
from typing import List, Optional

class AIRecommendationItem(BaseModel):
    issue_type: str = Field(description="The underlying issue code, e.g., MISSING_META_DESCRIPTION")
    severity: str = Field(description="The severity level: CRITICAL, HIGH, MEDIUM, LOW")
    title: str = Field(description="A concise title for the recommendation")
    explanation: str = Field(description="Why this issue matters for SEO/users in understandable language")
    recommendation: str = Field(description="Practical recommendation for fixing the issue")
    suggested_action: str = Field(description="What the developer/content owner should do")
    example: Optional[str] = Field(default=None, description="A suitable example if enough context exists")
    confidence: Optional[int] = Field(default=100, description="Confidence level of the recommendation 0-100")

    class Config:
        from_attributes = True

class AIRecommendationResponse(BaseModel):
    audit_id: int
    recommendations: List[AIRecommendationItem]
