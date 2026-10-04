from pydantic import BaseModel, Field, field_validator
from typing import List, Optional

class KeywordAnalyzeRequest(BaseModel):
    keywords: List[str] = Field(..., min_length=1, max_length=10)

    @field_validator("keywords")
    @classmethod
    def validate_keywords(cls, v):
        cleaned = []
        for kw in v:
            kw = kw.strip().lower()
            if kw and kw not in cleaned:
                cleaned.append(kw)
        if not cleaned:
            raise ValueError("Must provide at least one valid keyword.")
        return cleaned

class KeywordGap(BaseModel):
    type: str
    description: str

class KeywordUsage(BaseModel):
    title_matches: int
    meta_matches: int
    h1_matches: int
    h2_matches: int
    body_matches: int
    pages_containing: int
    total_pages_crawled: int

class KeywordAnalysisResult(BaseModel):
    id: int
    audit_id: int
    keyword: str
    opportunity_score: int
    intent: str
    usage: KeywordUsage
    gaps: List[KeywordGap]
    suggestions: List[str]

    class Config:
        from_attributes = True
