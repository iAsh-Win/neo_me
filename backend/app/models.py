from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def utcnow():
    return datetime.utcnow()


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(160), unique=True)
    password_hash: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(30))
    title: Mapped[str] = mapped_column(String(120), default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    manager_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)  # reporting line
    last_login: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Project(Base):
    __tablename__ = "projects"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str | None] = mapped_column(String(40), unique=True, nullable=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    ptype: Mapped[str] = mapped_column(String(20))              # development | in_licence
    market: Mapped[str] = mapped_column(String(80), default="")
    est_value: Mapped[float | None] = mapped_column(Float, nullable=True)   # AUD, yearly sales estimate
    target_date: Mapped[str] = mapped_column(String(20), default="")
    manufacturer: Mapped[str] = mapped_column(String(160), default="")
    initiator_id: Mapped[int] = mapped_column(ForeignKey("users.id"))

    current_step: Mapped[str] = mapped_column(String(40))
    step_round: Mapped[int] = mapped_column(Integer, default=1)  # bumps every time a step is (re)entered
    step_entered_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    status: Mapped[str] = mapped_column(String(20), default="active")  # active|on_hold|rejected|cancelled|completed
    clarification_pending: Mapped[bool] = mapped_column(Boolean, default=False)
    reminder_level: Mapped[int] = mapped_column(Integer, default=0)   # 0 none, 1 owner reminded, 2 manager told
    last_nudge_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status_note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    initiator: Mapped[User] = relationship(foreign_keys=[initiator_id])
    events: Mapped[list["Event"]] = relationship(back_populates="project", order_by="Event.id",
                                                 cascade="all, delete-orphan")
    documents: Mapped[list["Document"]] = relationship(back_populates="project", order_by="Document.id",
                                                       cascade="all, delete-orphan")


class Event(Base):
    """Everything that happens on a project: step results, notes, status changes."""
    __tablename__ = "events"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    kind: Mapped[str] = mapped_column(String(10))       # step | comment | system
    action: Mapped[str] = mapped_column(String(20), default="")  # done|signoff|approve|back|hold|reject|resume|created|moved...
    step_key: Mapped[str] = mapped_column(String(40), default="")
    option: Mapped[str] = mapped_column(String(30), default="")
    role: Mapped[str] = mapped_column(String(30), default="")
    round: Mapped[int] = mapped_column(Integer, default=0)
    note: Mapped[str] = mapped_column(Text, default="")
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    project: Mapped[Project] = relationship(back_populates="events")
    user: Mapped[User | None] = relationship()


class Document(Base):
    __tablename__ = "documents"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    step_key: Mapped[str] = mapped_column(String(40), default="")
    filename: Mapped[str] = mapped_column(String(255))
    stored_name: Mapped[str] = mapped_column(String(255))
    size: Mapped[int] = mapped_column(Integer, default=0)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    project: Mapped[Project] = relationship(back_populates="documents")
    user: Mapped[User] = relationship()


class Notification(Base):
    __tablename__ = "notifications"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    text: Mapped[str] = mapped_column(String(300))
    kind: Mapped[str] = mapped_column(String(12), default="info")  # turn|back|hold|reject|done|remind|escalate|note|info
    email_status: Mapped[str] = mapped_column(String(10), default="off")  # off|pending|sent|failed
    read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
