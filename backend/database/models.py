from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime
from sqlalchemy.orm import relationship
import datetime
from backend.database.connection import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    name = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    audits = relationship("Audit", back_populates="user")
    monitoring_projects = relationship("MonitoringProject", back_populates="user")
    competitor_analyses = relationship("CompetitorAnalysis", back_populates="user")
    keyword_analyses = relationship("KeywordAnalysis", back_populates="user")
    notification_preference = relationship("NotificationPreference", back_populates="user", uselist=False)

class Audit(Base):
    __tablename__ = "audits"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    url = Column(String, index=True)
    max_pages = Column(Integer, default=10)
    max_depth = Column(Integer, default=2)
    status = Column(String, default="pending") # pending, crawling, analyzing, completed, failed
    error_message = Column(String, nullable=True)
    score = Column(Integer, nullable=True)
    score_data = Column(String, nullable=True) # Stored as JSON string
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    is_competitor = Column(Boolean, default=False)
    
    user = relationship("User", back_populates="audits")
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
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    base_audit_id = Column(Integer, ForeignKey("audits.id"))
    competitor_audit_id = Column(Integer, ForeignKey("audits.id"))
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    user = relationship("User", back_populates="competitor_analyses")
    base_audit = relationship("Audit", foreign_keys=[base_audit_id])
    competitor_audit = relationship("Audit", foreign_keys=[competitor_audit_id])

class KeywordAnalysis(Base):
    __tablename__ = "keyword_analyses"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    audit_id = Column(Integer, ForeignKey("audits.id"))
    keyword = Column(String, index=True)
    opportunity_score = Column(Integer, nullable=True)
    intent = Column(String, nullable=True)
    analysis_data = Column(String, nullable=True) # JSON storing metrics, gap data, etc.
    suggestions_data = Column(String, nullable=True) # JSON storing related keyword suggestions
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    user = relationship("User", back_populates="keyword_analyses")
    audit = relationship("Audit")

class GSCCredentials(Base):
    __tablename__ = "gsc_credentials"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True, default="default_user")
    credentials_json = Column(String)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

class MonitoringProject(Base):
    __tablename__ = "monitoring_projects"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    url = Column(String, index=True)
    name = Column(String)
    frequency = Column(String, default="weekly") # daily, weekly, monthly
    is_active = Column(Boolean, default=True)
    last_audit_id = Column(Integer, ForeignKey("audits.id"), nullable=True)
    last_audit_date = Column(DateTime, nullable=True)
    next_audit_date = Column(DateTime, default=datetime.datetime.utcnow)
    max_pages = Column(Integer, default=10)
    max_depth = Column(Integer, default=2)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    user = relationship("User", back_populates="monitoring_projects")
    last_audit = relationship("Audit", foreign_keys=[last_audit_id])
    reports = relationship("MonitoringReport", back_populates="project")

class MonitoringReport(Base):
    __tablename__ = "monitoring_reports"
    
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("monitoring_projects.id"))
    audit_id = Column(Integer, ForeignKey("audits.id"))
    previous_audit_id = Column(Integer, ForeignKey("audits.id"), nullable=True)
    score_change = Column(Integer, nullable=True)
    changes_data = Column(String, nullable=True) # JSON of changes
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    project = relationship("MonitoringProject", back_populates="reports")
    audit = relationship("Audit", foreign_keys=[audit_id])
    previous_audit = relationship("Audit", foreign_keys=[previous_audit_id])

class NotificationPreference(Base):
    __tablename__ = "notification_preferences"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, index=True)
    email_enabled = Column(Boolean, default=True)
    score_drop_alert = Column(Boolean, default=True)
    critical_issue_alert = Column(Boolean, default=True)
    high_issue_alert = Column(Boolean, default=True)
    weekly_summary = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    
    user = relationship("User", back_populates="notification_preference")

class NotificationHistory(Base):
    __tablename__ = "notification_history"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    monitoring_project_id = Column(Integer, ForeignKey("monitoring_projects.id"), nullable=True)
    notification_type = Column(String) # "score_drop", "critical_issue", "weekly_summary"
    severity = Column(String) # CRITICAL, HIGH, MEDIUM, LOW
    recipient = Column(String) # email address
    status = Column(String) # sent, skipped, failed
    error_message = Column(String, nullable=True)
    sent_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    user = relationship("User")
    project = relationship("MonitoringProject")
