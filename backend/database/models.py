from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime
from sqlalchemy.orm import relationship
import datetime
from backend.database.connection import Base

class Audit(Base):
    __tablename__ = "audits"

    id = Column(Integer, primary_key=True, index=True)
    url = Column(String, index=True)
    max_pages = Column(Integer, default=10)
    max_depth = Column(Integer, default=2)
    status = Column(String, default="pending") # pending, crawling, analyzing, completed, failed
    error_message = Column(String, nullable=True)
    score = Column(Integer, nullable=True)
    score_data = Column(String, nullable=True) # Stored as JSON string
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    is_competitor = Column(Boolean, default=False)
    
    pages = relationship("Page", back_populates="audit")
    recommendations = relationship("AIRecommendation", back_populates="audit")

class Page(Base):
    __tablename__ = "pages"

    id = Column(Integer, primary_key=True, index=True)
    audit_id = Column(Integer, ForeignKey("audits.id"))
    url = Column(String)
    final_url = Column(String, nullable=True)
    depth = Column(Integer)
    status_code = Column(Integer, nullable=True)
    content_type = Column(String, nullable=True)
    title = Column(String, nullable=True)
    title_length = Column(Integer, nullable=True)
    meta_description = Column(String, nullable=True)
    meta_description_length = Column(Integer, nullable=True)
    h1_list = Column(String, nullable=True) # Stored as JSON string
    h1_count = Column(Integer, nullable=True)
    h2_list = Column(String, nullable=True) # Stored as JSON string
    h2_count = Column(Integer, nullable=True)
    canonical_url = Column(String, nullable=True)
    meta_robots = Column(String, nullable=True)
    x_robots_tag = Column(String, nullable=True)
    html_language = Column(String, nullable=True)
    viewport_meta_presence = Column(Boolean, default=False)
    word_count = Column(Integer, nullable=True)
    image_count = Column(Integer, nullable=True)
    images_missing_alt = Column(Integer, nullable=True)
    internal_link_count = Column(Integer, nullable=True)
    external_link_count = Column(Integer, nullable=True)
    open_graph_presence = Column(Boolean, default=False)
    structured_data_presence = Column(Boolean, default=False)
    crawl_status = Column(String) # success, error, skipped
    error_message = Column(String, nullable=True)

    audit = relationship("Audit", back_populates="pages")
    issues = relationship("SEOIssue", back_populates="page")

class SEOIssue(Base):
    __tablename__ = "seo_issues"

    id = Column(Integer, primary_key=True, index=True)
    page_id = Column(Integer, ForeignKey("pages.id"))
    page_url = Column(String)
    category = Column(String)
    severity = Column(String)
    issue_code = Column(String)
    title = Column(String)
    description = Column(String)
    recommendation_summary = Column(String)
    impact = Column(String)

    page = relationship("Page", back_populates="issues")

class AIRecommendation(Base):
    __tablename__ = "ai_recommendations"
    
    id = Column(Integer, primary_key=True, index=True)
    audit_id = Column(Integer, ForeignKey("audits.id"))
    issue_type = Column(String)
    severity = Column(String)
    title = Column(String)
    explanation = Column(String)
    recommendation = Column(String)
    suggested_action = Column(String)
    example = Column(String, nullable=True)
    confidence = Column(Integer, nullable=True)
    
    audit = relationship("Audit", back_populates="recommendations")

class CompetitorAnalysis(Base):
    __tablename__ = "competitor_analyses"

    id = Column(Integer, primary_key=True, index=True)
    base_audit_id = Column(Integer, ForeignKey("audits.id"))
    competitor_audit_id = Column(Integer, ForeignKey("audits.id"))
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    base_audit = relationship("Audit", foreign_keys=[base_audit_id])
    competitor_audit = relationship("Audit", foreign_keys=[competitor_audit_id])

class KeywordAnalysis(Base):
    __tablename__ = "keyword_analyses"

    id = Column(Integer, primary_key=True, index=True)
    audit_id = Column(Integer, ForeignKey("audits.id"))
    keyword = Column(String, index=True)
    opportunity_score = Column(Integer, nullable=True)
    intent = Column(String, nullable=True)
    analysis_data = Column(String, nullable=True) # JSON storing metrics, gap data, etc.
    suggestions_data = Column(String, nullable=True) # JSON storing related keyword suggestions
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    audit = relationship("Audit")
