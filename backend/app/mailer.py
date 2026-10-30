"""Optional e-mail copy of every notification.

Set NEO_SMTP_HOST (and NEO_SMTP_PORT / NEO_SMTP_USER / NEO_SMTP_PASSWORD / NEO_SMTP_FROM / NEO_BASE_URL) to switch it on.
Without it, notifications still appear inside the app and are marked "off" for e-mail.
"""
import os
import smtplib
from email.message import EmailMessage

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Notification, Project, User


def configured() -> bool:
    return bool(os.environ.get("NEO_SMTP_HOST"))


def _link(project_id: int) -> str:
    return f"{os.environ.get('NEO_BASE_URL', 'http://localhost:8090').rstrip('/')}/projects/{project_id}"


def send_pending(db: Session, limit: int = 50) -> dict:
    """Send queued notifications. Returns counts; safe to call repeatedly."""
    rows = db.scalars(select(Notification).where(Notification.email_status == "pending")
                      .order_by(Notification.id).limit(limit)).all()
    sent = failed = 0
    if not rows:
        return {"sent": 0, "failed": 0}
    host, port = os.environ["NEO_SMTP_HOST"], int(os.environ.get("NEO_SMTP_PORT", "587"))
    user, pw = os.environ.get("NEO_SMTP_USER"), os.environ.get("NEO_SMTP_PASSWORD")
    sender = os.environ.get("NEO_SMTP_FROM", user or "noreply@neo-project-flow.local")
    try:
        with smtplib.SMTP(host, port, timeout=20) as smtp:
            if os.environ.get("NEO_SMTP_TLS", "1") == "1":
                smtp.starttls()
            if user:
                smtp.login(user, pw or "")
            for n in rows:
                to = db.get(User, n.user_id)
                project = db.get(Project, n.project_id)
                try:
                    msg = EmailMessage()
                    msg["Subject"] = n.text[:120]
                    msg["From"], msg["To"] = sender, to.email
                    msg.set_content(f"{n.text}\n\nOpen the project: {_link(n.project_id)}\n\n— Neo Project Flow"
                                    + (f"\nProject: {project.title}" if project else ""))
                    smtp.send_message(msg)
                    n.email_status = "sent"
                    sent += 1
                except Exception:
                    n.email_status = "failed"
                    failed += 1
    except Exception:
        for n in rows:
            n.email_status = "failed"
        failed = len(rows)
    db.commit()
    return {"sent": sent, "failed": failed}
