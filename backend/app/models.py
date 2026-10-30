from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
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
    est_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    target_date: Mapped[str] = mapped_column(String(20), default="")
    manufacturer: Mapped[str] = mapped_column(String(160), default="")
    initiator_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String(20), default="active")  # active|on_hold|rejected|cancelled|completed
    status_note: Mapped[str] = mapped_column(Text, default="")
    clarification_pending: Mapped[bool] = mapped_column(Boolean, default=False)
    fast_track: Mapped[bool] = mapped_column(Boolean, default=False)   # Directors: run parallel tracks side by side
    group_mode: Mapped[dict] = mapped_column(JSON, default=dict)       # group id -> "fast" | "seq" (decided on entry)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    initiator: Mapped[User] = relationship(foreign_keys=[initiator_id])
    runs: Mapped[list["StepRun"]] = relationship(back_populates="project", order_by="StepRun.id",
                                                 cascade="all, delete-orphan")
    events: Mapped[list["Event"]] = relationship(back_populates="project", order_by="Event.id",
                                                 cascade="all, delete-orphan")
    documents: Mapped[list["Document"]] = relationship(back_populates="project", order_by="Document.id",
                                                       cascade="all, delete-orphan")
    tasks: Mapped[list["Task"]] = relationship(back_populates="project", order_by="Task.id",
                                               cascade="all, delete-orphan")
    requests: Mapped[list["Request"]] = relationship(back_populates="project", order_by="Request.id",
                                                     cascade="all, delete-orphan")


class StepRun(Base):
    """One turn of a step. A step normally has one run; a send-back creates another."""
    __tablename__ = "step_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    step_key: Mapped[str] = mapped_column(String(40))
    seq: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(12), default="active")  # active|done|returned
    kind: Mapped[str] = mapped_column(String(10), default="normal")    # normal|rework
    entered_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    due_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    from_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)  # who handed it over
    from_note: Mapped[str] = mapped_column(Text, default="")
    return_to: Mapped[str] = mapped_column(String(40), default="")   # step to come straight back to when fixed
    return_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)  # who it returns to
    reminder_level: Mapped[int] = mapped_column(Integer, default=0)
    last_nudge_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    assignee_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)  # handed to one chosen person
    handover: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # what the previous person sent along

    project: Mapped[Project] = relationship(back_populates="runs")
    from_user: Mapped[User | None] = relationship(foreign_keys=[from_user_id])
    completed_by: Mapped[User | None] = relationship(foreign_keys=[completed_by_id])
    assignee: Mapped[User | None] = relationship(foreign_keys=[assignee_id])
    return_user: Mapped[User | None] = relationship(foreign_keys=[return_user_id])


class Event(Base):
    """The history: everything that happens on a project."""
    __tablename__ = "events"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    kind: Mapped[str] = mapped_column(String(10))       # step | comment | system | task | request | doc
    action: Mapped[str] = mapped_column(String(20), default="")
    step_key: Mapped[str] = mapped_column(String(40), default="")
    run_id: Mapped[int | None] = mapped_column(ForeignKey("step_runs.id"), nullable=True)
    option: Mapped[str] = mapped_column(String(30), default="")
    role: Mapped[str] = mapped_column(String(30), default="")
    note: Mapped[str] = mapped_column(Text, default="")
    to_text: Mapped[str] = mapped_column(String(300), default="")   # who it went to, in words
    meta: Mapped[dict] = mapped_column(JSON, default=dict)          # details: data, checks, docs, dates, target
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    project: Mapped[Project] = relationship(back_populates="events")
    user: Mapped[User | None] = relationship()


class Document(Base):
    """A document: a file, a link, or both (kind = file | link | both). Attached to a step slot or a task.
    Using an existing document somewhere else makes a reference row (source_id points to the original)."""
    __tablename__ = "documents"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    step_key: Mapped[str] = mapped_column(String(40), default="")
    doc_type: Mapped[str] = mapped_column(String(40), default="")
    kind: Mapped[str] = mapped_column(String(6), default="file")
    important: Mapped[bool] = mapped_column(Boolean, default=False)         # pinned as a key document
    source_id: Mapped[int | None] = mapped_column(Integer, nullable=True)   # original document, when this is a reference
    task_id: Mapped[int | None] = mapped_column(Integer, nullable=True)     # attached to a task
    title: Mapped[str] = mapped_column(String(255), default="")
    url: Mapped[str] = mapped_column(String(1000), default="")
    filename: Mapped[str] = mapped_column(String(255), default="")
    stored_name: Mapped[str] = mapped_column(String(255), default="")
    size: Mapped[int] = mapped_column(Integer, default=0)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    project: Mapped[Project] = relationship(back_populates="documents")
    user: Mapped[User] = relationship()


class Task(Base):
    """A small piece of work someone gives to someone else inside a project."""
    __tablename__ = "tasks"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    title: Mapped[str] = mapped_column(String(200))
    details: Mapped[str] = mapped_column(Text, default="")
    assignee_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    creator_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    step_key: Mapped[str] = mapped_column(String(40), default="")
    blocking: Mapped[bool] = mapped_column(Boolean, default=False)   # the linked step cannot finish before this is done
    due_at: Mapped[datetime] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(10), default="open")  # open|done|cancelled
    done_note: Mapped[str] = mapped_column(Text, default="")
    reminder_level: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    project: Mapped[Project] = relationship(back_populates="tasks")
    assignee: Mapped[User] = relationship(foreign_keys=[assignee_id])
    creator: Mapped[User] = relationship(foreign_keys=[creator_id])


class Request(Base):
    """A request for more time on a step or a task. Goes to whoever gave the date."""
    __tablename__ = "requests"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    kind: Mapped[str] = mapped_column(String(8))                    # step | task
    run_id: Mapped[int | None] = mapped_column(ForeignKey("step_runs.id"), nullable=True)
    task_id: Mapped[int | None] = mapped_column(ForeignKey("tasks.id"), nullable=True)
    requested_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    approver_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    old_due: Mapped[datetime] = mapped_column(DateTime)
    new_due: Mapped[datetime] = mapped_column(DateTime)
    reason: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(10), default="pending")  # pending|approved|declined
    decided_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    decision_note: Mapped[str] = mapped_column(Text, default="")
    reminded: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    project: Mapped[Project] = relationship(back_populates="requests")
    requested_by: Mapped[User] = relationship(foreign_keys=[requested_by_id])
    approver: Mapped[User] = relationship(foreign_keys=[approver_id])
    decided_by: Mapped[User | None] = relationship(foreign_keys=[decided_by_id])


class Notification(Base):
    __tablename__ = "notifications"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    text: Mapped[str] = mapped_column(String(400))
    kind: Mapped[str] = mapped_column(String(12), default="info")  # turn|back|hold|reject|done|remind|escalate|note|request|info
    email_status: Mapped[str] = mapped_column(String(10), default="off")  # off|pending|sent|failed
    read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
