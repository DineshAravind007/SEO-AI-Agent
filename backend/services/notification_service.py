import os
import smtplib
import logging
from email.message import EmailMessage
from datetime import datetime
from sqlalchemy.orm import Session
from backend.database.models import NotificationHistory, NotificationPreference, User

logger = logging.getLogger(__name__)

class EmailNotificationProvider:
    def __init__(self):
        self.host = os.getenv("EMAIL_HOST")
        self.port = int(os.getenv("EMAIL_PORT", 587))
        self.username = os.getenv("EMAIL_USERNAME")
        self.password = os.getenv("EMAIL_PASSWORD")
        self.from_email = os.getenv("EMAIL_FROM", "noreply@seo-agent.com")

    def is_configured(self) -> bool:
        return bool(self.host and self.username and self.password)

    def send(self, to_email: str, subject: str, html_body: str) -> bool:
        if not self.is_configured():
            logger.warning("Email provider not configured. Skipping email to %s", to_email)
            return False

        msg = EmailMessage()
        msg['Subject'] = subject
        msg['From'] = self.from_email
        msg['To'] = to_email
        msg.set_content("Please enable HTML to view this email.")
        msg.add_alternative(html_body, subtype='html')

        try:
            with smtplib.SMTP(self.host, self.port) as server:
                server.starttls()
                server.login(self.username, self.password)
                server.send_message(msg)
            return True
        except Exception as e:
            logger.error("Failed to send email to %s: %s", to_email, e)
            raise e

class NotificationService:
    def __init__(self):
        self.email_provider = EmailNotificationProvider()

    def get_preferences(self, db: Session, user_id: int) -> NotificationPreference:
        prefs = db.query(NotificationPreference).filter(NotificationPreference.user_id == user_id).first()
        if not prefs:
            prefs = NotificationPreference(user_id=user_id)
            db.add(prefs)
            db.commit()
            db.refresh(prefs)
        return prefs

    def update_preferences(self, db: Session, user_id: int, data: dict) -> NotificationPreference:
        prefs = self.get_preferences(db, user_id)
        for k, v in data.items():
            if hasattr(prefs, k):
                setattr(prefs, k, v)
        db.commit()
        db.refresh(prefs)
        return prefs

    def send_alert(self, db: Session, user: User, project_id: int, alert_type: str, severity: str, subject: str, html_body: str):
        prefs = self.get_preferences(db, user.id)
        
        # Check preferences
        if not prefs.email_enabled:
            return self._record_history(db, user.id, project_id, alert_type, severity, user.email, "skipped", "Email disabled by user")

        if alert_type == "score_drop" and not prefs.score_drop_alert:
            return self._record_history(db, user.id, project_id, alert_type, severity, user.email, "skipped", "Score drop alert disabled")
            
        if alert_type == "critical_issue" and not prefs.critical_issue_alert:
            return self._record_history(db, user.id, project_id, alert_type, severity, user.email, "skipped", "Critical issue alert disabled")
            
        if alert_type == "high_issue" and not prefs.high_issue_alert:
            return self._record_history(db, user.id, project_id, alert_type, severity, user.email, "skipped", "High issue alert disabled")

        if not self.email_provider.is_configured():
            return self._record_history(db, user.id, project_id, alert_type, severity, user.email, "skipped", "Email provider not configured")

        try:
            self.email_provider.send(user.email, subject, html_body)
            self._record_history(db, user.id, project_id, alert_type, severity, user.email, "sent", None)
        except Exception as e:
            self._record_history(db, user.id, project_id, alert_type, severity, user.email, "failed", str(e))

    def _record_history(self, db: Session, user_id: int, project_id: int, notification_type: str, severity: str, recipient: str, status: str, error_message: str = None):
        history = NotificationHistory(
            user_id=user_id,
            monitoring_project_id=project_id,
            notification_type=notification_type,
            severity=severity,
            recipient=recipient,
            status=status,
            error_message=error_message
        )
        db.add(history)
        db.commit()

notification_service = NotificationService()
