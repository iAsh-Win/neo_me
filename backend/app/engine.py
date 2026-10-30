"""Workflow engine: the only place that moves a project from one step to the next.

All approvals go through `act()`, so the rules from the flow chart
(who may act, loops, hold/reject, two-director sign-offs) are applied the same
way for the UI, the tests and the demo data.
"""
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import mailer
from . import workflow as wf
from .models import Document, Event, Notification, Project, User

CLOSED = ("rejected", "cancelled", "completed")
DIRECTORS = ("otc_director", "india_director")


class WorkflowError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message = message
        self.status = status


# ---- roles and permissions ------------------------------------------------
def role_label(role: str) -> str:
    return wf.ROLES[role]["label"]


def _step(project: Project) -> dict:
    return wf.STEP_BY_KEY[project.current_step]


def signed_roles(project: Project) -> set:
    """Roles that have already signed the current step in the current round."""
    return {e.role for e in project.events
            if e.kind == "step" and e.action == "signoff"
            and e.step_key == project.current_step and e.round == project.step_round}


def _role_matches(project: Project, user: User, role: str) -> bool:
    if user.role != role:
        return False
    if role == "initiator":          # the project's own initiator only
        return user.id == project.initiator_id
    return True


def can_act(project: Project, user: User) -> bool:
    if project.status != "active" or not user.active:
        return False
    step = _step(project)
    done = signed_roles(project)
    for role in wf.actor_roles(step):
        if _role_matches(project, user, role):
            if step.get("all") and role in done:
                return False
            return True
    return False


def can_see(project: Project, user: User) -> bool:
    """People only see projects they work on: Directors and the Office Admin see everything;
    everyone else sees a project when it is theirs, waiting on them, or they have already worked on it."""
    if user.role == "admin" or user.role in DIRECTORS:
        return True
    if project.initiator_id == user.id:
        return True
    if can_act(project, user):
        return True
    return any(e.user_id == user.id for e in project.events)


def waiting_roles(project: Project) -> list:
    """Roles still expected to act on the current step."""
    if project.status in CLOSED:
        return []
    step = _step(project)
    if step.get("all"):
        done = signed_roles(project)
        return [r for r in step["roles"] if r not in done]
    return list(step["roles"])


def due_at(project: Project) -> datetime:
    return project.step_entered_at + timedelta(days=wf.sla_days(project.current_step))


# ---- notifications --------------------------------------------------------
def _notify(db: Session, project: Project, user_ids, text: str, at: datetime, kind="info", skip=None):
    for uid in dict.fromkeys(user_ids):          # unique, keep order
        if uid and uid != skip:
            db.add(Notification(user_id=uid, project_id=project.id, text=text, kind=kind, created_at=at,
                                email_status="pending" if mailer.configured() else "off"))


def _owner_ids(db: Session, project: Project) -> list:
    ids = []
    for role in waiting_roles(project):
        if role == "initiator":
            ids.append(project.initiator_id)
        else:
            ids += [u.id for u in db.scalars(select(User).where(User.role == role, User.active == True))]  # noqa: E712
    return ids


def _notify_step_owners(db: Session, project: Project, at: datetime, skip: int | None = None):
    if project.status != "active":
        return
    _notify(db, project, _owner_ids(db, project), f"{project.title} – your turn: {_step(project)['name']}",
            at, "turn", skip)


def _director_ids(db: Session) -> list:
    return [u.id for u in db.scalars(select(User).where(User.role.in_(DIRECTORS), User.active == True))]  # noqa: E712


def _enter(db: Session, project: Project, key: str, at: datetime, actor: User | None):
    project.current_step = key
    project.step_round += 1
    project.step_entered_at = at
    project.updated_at = at
    project.reminder_level = 0
    if key == "updated_brief":
        project.clarification_pending = False
    db.flush()
    _notify_step_owners(db, project, at, skip=actor.id if actor else None)


def _make_code(db: Session, project: Project, at: datetime) -> str:
    prefix = "NHO-" + ("DEV" if project.ptype == "development" else "INL") + f"-{at.year}-"
    codes = db.scalars(select(Project.code).where(Project.code.like(prefix + "%"))).all()
    n = max([int(c.rsplit("-", 1)[1]) for c in codes] + [0]) + 1
    return f"{prefix}{n:03d}"


def _add_event(project: Project, **kw) -> Event:
    ev = Event(**kw)
    project.events.append(ev)  # cascades into the session with the project
    return ev


# ---- create --------------------------------------------------------------
def create_project(db: Session, user: User, data: dict, at: datetime | None = None) -> Project:
    at = at or datetime.utcnow()
    if user.role not in ("initiator", "admin"):
        raise WorkflowError("Only a Project Initiator can add a new project.", 403)
    if data.get("ptype") not in wf.PROJECT_TYPES:
        raise WorkflowError("Please choose Development or In-Licence.")
    if not (data.get("title") or "").strip():
        raise WorkflowError("Please give the project a name.")
    initiator = user
    if user.role == "admin":
        initiator = db.get(User, data.get("initiator_id") or 0)
        if not initiator or initiator.role != "initiator":
            raise WorkflowError("Please choose who the Project Initiator is.")
    p = Project(
        title=data["title"].strip(), description=(data.get("description") or "").strip(),
        ptype=data["ptype"], market=(data.get("market") or "").strip(),
        est_value=data.get("est_value"), target_date=data.get("target_date") or "",
        initiator_id=initiator.id, current_step="opportunity", created_at=at,
        step_entered_at=at, updated_at=at,
    )
    db.add(p)
    db.flush()
    p.initiator = initiator
    _add_event(p, kind="step", action="done", step_key="opportunity", role="initiator", round=1,
               user_id=user.id, created_at=at, note="Opportunity identified")
    _enter(db, p, "screening", at, user)
    db.commit()
    return p


# ---- act on the current step ----------------------------------------------
def act(db: Session, project: Project, user: User, option: str | None = None, note: str = "",
        text: str | None = None, at: datetime | None = None) -> dict:
    at = at or datetime.utcnow()
    note = (note or "").strip()
    if project.status != "active":
        raise WorkflowError(f"This project is {project.status.replace('_', ' ')}. Nothing can be done on it right now.")
    step = _step(project)
    if not can_act(project, user):
        who = " / ".join(role_label(r) for r in waiting_roles(project))
        raise WorkflowError(f"This step is waiting for {who}. You cannot act on it.", 403)
    role = next(r for r in wf.actor_roles(step) if _role_matches(project, user, r))
    ctype = project.ptype

    # --- decision steps ---
    if step["mode"] == "decision":
        if option not in step["options"]:
            raise WorkflowError("Please choose one of the decision buttons.")
        opt = step["options"][option]
        if opt.get("note") and not note:
            raise WorkflowError("Please write a short reason for this decision.")
        base = dict(kind="step", step_key=step["key"], option=option, role=role, round=project.step_round,
                    user_id=user.id, note=note, created_at=at)
        if opt["kind"] == "approve":
            if step.get("all"):
                _add_event(project, action="signoff", **base)
                db.flush()
                if set(step["roles"]) - signed_roles(project):
                    project.updated_at = at
                    db.commit()
                    left = ", ".join(wf.ROLES[r]["short"] for r in waiting_roles(project))
                    return {"moved": False, "message": f"Your approval is saved. Waiting for {left}."}
            _add_event(project, action="approve", **base)
            target = wf.decision_target(step["key"], option, ctype)
            if option == "incomplete":
                project.clarification_pending = True
            _notify(db, project, [project.initiator_id], f"{project.title} – approved: {step['name']}", at,
                    "done", user.id)
            _enter(db, project, target, at, user)
            db.commit()
            return {"moved": True, "message": f"Approved. Next: {_step(project)['name']}."}
        if opt["kind"] == "back":
            _add_event(project, action="back", **base)
            _enter(db, project, opt["to"], at, user)
            _notify(db, project, [project.initiator_id],
                    f"{project.title} – sent back to {_step(project)['name']}: {note}", at, "back", user.id)
            db.commit()
            return {"moved": True, "message": f"Sent back to: {_step(project)['name']}."}
        if opt["kind"] == "hold":
            _add_event(project, action="hold", **base)
            project.status, project.status_note, project.updated_at = "on_hold", note, at
            _notify(db, project, [project.initiator_id] + _director_ids(db),
                    f"{project.title} – put on hold: {note}", at, "hold", user.id)
            db.commit()
            return {"moved": False, "message": "Project put on hold."}
        if opt["kind"] == "reject":
            _add_event(project, action="reject", **base)
            project.status, project.status_note, project.updated_at = "rejected", note, at
            _notify(db, project, [project.initiator_id] + _director_ids(db),
                    f"{project.title} – rejected: {note}", at, "reject", user.id)
            db.commit()
            return {"moved": False, "message": "Project rejected and closed."}
        raise WorkflowError("Unknown decision.")

    # --- action steps ---
    if step.get("needs_note") and not note:
        raise WorkflowError(step["needs_note"])
    if step.get("needs_text"):
        field, question = step["needs_text"]
        if not (text or "").strip():
            raise WorkflowError(question)
        setattr(project, field, text.strip())
    if step.get("needs_file"):
        has = any(d.step_key == step["key"] for d in project.documents)
        if not has:
            raise WorkflowError(f"Please attach the file first: {step['needs_file']}.")
    if step["key"] == "code" and not project.code:
        project.code = _make_code(db, project, at)
        note = note or f"Code {project.code} generated"

    base = dict(kind="step", step_key=step["key"], role=role, round=project.step_round,
                user_id=user.id, note=note, created_at=at)
    if step.get("all"):
        _add_event(project, action="signoff", **base)
        db.flush()
        if set(step["roles"]) - signed_roles(project):
            project.updated_at = at
            db.commit()
            left = ", ".join(wf.ROLES[r]["short"] for r in waiting_roles(project))
            return {"moved": False, "message": f"Your sign-off is saved. Waiting for {left}."}
    _add_event(project, action="done", **base)
    for k, v in (step.get("sets") or {}).items():
        setattr(project, k, v)
    nxt = wf.next_step_key(step["key"], ctype, clarification_pending=project.clarification_pending)
    if nxt is None:
        project.status, project.updated_at = "completed", at
        _notify(db, project, [project.initiator_id] + _director_ids(db),
                f"{project.title} – project completed", at, "done", user.id)
        db.commit()
        return {"moved": False, "message": "Project completed. Well done!"}
    if step["key"] == "clarification":
        _notify(db, project, [project.initiator_id], f"{project.title} – clarification needed: {note}", at,
                "back", user.id)
    _enter(db, project, nxt, at, user)
    db.commit()
    return {"moved": True, "message": f"Done. Next: {_step(project)['name']}."}


# ---- project-level controls -----------------------------------------------
def _is_director(user: User) -> bool:
    return user.role in DIRECTORS


def hold_project(db, project, user, note, at=None):
    at = at or datetime.utcnow()
    if not _is_director(user):
        raise WorkflowError("Only a Director can put a project on hold.", 403)
    if project.status != "active":
        raise WorkflowError("Only an active project can be put on hold.")
    if not note.strip():
        raise WorkflowError("Please write a short reason.")
    _add_event(project, kind="system", action="hold", step_key=project.current_step, role=user.role,
               user_id=user.id, note=note.strip(), created_at=at)
    project.status, project.status_note, project.updated_at = "on_hold", note.strip(), at
    _notify(db, project, [project.initiator_id] + _owner_ids(db, project),
            f"{project.title} – put on hold: {note.strip()}", at, "hold", user.id)
    db.commit()


def resume_project(db, project, user, note="", at=None):
    at = at or datetime.utcnow()
    if not _is_director(user):
        raise WorkflowError("Only a Director can restart a project that is on hold.", 403)
    if project.status != "on_hold":
        raise WorkflowError("This project is not on hold.")
    _add_event(project, kind="system", action="resume", step_key=project.current_step, role=user.role,
               user_id=user.id, note=note.strip(), created_at=at)
    project.status, project.status_note = "active", ""
    project.step_entered_at, project.updated_at, project.reminder_level = at, at, 0
    db.flush()
    _notify_step_owners(db, project, at, skip=user.id)
    db.commit()


def cancel_project(db, project, user, note, at=None):
    at = at or datetime.utcnow()
    if not _is_director(user):
        raise WorkflowError("Only a Director can cancel a project.", 403)
    if project.status in CLOSED:
        raise WorkflowError("This project is already closed.")
    if not note.strip():
        raise WorkflowError("Please write a short reason.")
    _add_event(project, kind="system", action="cancel", step_key=project.current_step, role=user.role,
               user_id=user.id, note=note.strip(), created_at=at)
    project.status, project.status_note, project.updated_at = "cancelled", note.strip(), at
    _notify(db, project, [project.initiator_id] + _owner_ids(db, project),
            f"{project.title} – cancelled: {note.strip()}", at, "reject", user.id)
    db.commit()


def move_project(db, project, user, step_key, note, at=None):
    """Office Admin correction: put the project back on a chosen step."""
    at = at or datetime.utcnow()
    if user.role != "admin":
        raise WorkflowError("Only the Office Admin can correct the step.", 403)
    if step_key not in [s["key"] for s in wf.steps_for(project.ptype)]:
        raise WorkflowError("That step does not exist for this project type.")
    if not note.strip():
        raise WorkflowError("Please write why the step is being corrected.")
    _add_event(project, kind="system", action="moved", step_key=step_key, role="admin", user_id=user.id,
               note=note.strip(), created_at=at)
    if project.status in ("on_hold", "completed"):
        project.status = "active"
    _enter(db, project, step_key, at, user)
    db.commit()


def add_comment(db, project, user, text, at=None):
    text = (text or "").strip()
    if not text:
        raise WorkflowError("Please type a note first.")
    at = at or datetime.utcnow()
    _add_event(project, kind="comment", action="comment", step_key=project.current_step, role=user.role,
               user_id=user.id, note=text, created_at=at)
    project.updated_at = at
    _notify(db, project, [project.initiator_id] + _owner_ids(db, project),
            f"{user.name} wrote a note on {project.title}: {text[:90]}", at, "note", user.id)
    db.commit()


def add_document(db, project, user, filename, stored, size, step_key="", at=None) -> Document:
    d = Document(step_key=step_key or "", filename=filename, stored_name=stored,
                 size=size, user_id=user.id, created_at=at or datetime.utcnow())
    project.documents.append(d)
    db.commit()
    return d


# ---- reminders and escalation ---------------------------------------------
def nudge(db: Session, project: Project, user: User, at: datetime | None = None) -> str:
    """Ask the people a project is waiting for to please act. At most once every 12 hours."""
    at = at or datetime.utcnow()
    if project.status != "active":
        raise WorkflowError("This project is not waiting for anyone.")
    if can_act(project, user):
        raise WorkflowError("It is your turn on this project.")
    if project.last_nudge_at and at - project.last_nudge_at < timedelta(hours=12):
        raise WorkflowError("A reminder was already sent a short while ago.")
    owners = _owner_ids(db, project)
    _notify(db, project, owners, f"{user.name} reminds you: {project.title} – {_step(project)['name']}",
            at, "remind", user.id)
    project.last_nudge_at = at
    _add_event(project, kind="system", action="nudge", step_key=project.current_step, role=user.role,
               user_id=user.id, note="Reminder sent", created_at=at)
    db.commit()
    return "Reminder sent."


def run_reminders(db: Session, now: datetime | None = None) -> dict:
    """Level 1: step is past its due date → remind the owners.
    Level 2: still waiting a further full SLA period → tell the owners' managers (or the Directors)."""
    now = now or datetime.utcnow()
    reminded = escalated = 0
    for p in db.scalars(select(Project).where(Project.status == "active")):
        sla = timedelta(days=wf.sla_days(p.current_step))
        late = now - due_at(p)
        if late.total_seconds() <= 0:
            continue
        step = _step(p)
        if p.reminder_level < 1:
            _notify(db, p, _owner_ids(db, p), f"Overdue: {p.title} – {step['name']}", now, "remind")
            p.reminder_level, reminded = 1, reminded + 1
        if p.reminder_level < 2 and late >= sla:
            bosses = []
            for uid in _owner_ids(db, p):
                owner = db.get(User, uid)
                bosses.append(owner.manager_id if owner and owner.manager_id else None)
            bosses = [b for b in bosses if b] or _director_ids(db)
            _notify(db, p, bosses, f"Escalation: {p.title} has waited {(now - p.step_entered_at).days} days at "
                                   f"{step['name']}", now, "escalate")
            p.reminder_level, escalated = 2, escalated + 1
    db.commit()
    return {"reminded": reminded, "escalated": escalated}
