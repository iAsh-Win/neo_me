"""Workflow engine: the only place that moves a project forward.

A project has one or more *active runs* (a step waiting for someone). Everything – finishing a step, sending
it back, asking for more time, giving a task – goes through the functions here, so the rules from the flow
chart apply the same way for the screens, the tests and the demo data.
"""
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import mailer
from . import workflow as wf
from .models import Document, Event, Notification, Project, Request, StepRun, Task, User

CLOSED = ("rejected", "cancelled", "completed")
DIRECTORS = ("otc_director", "india_director")


class WorkflowError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message = message
        self.status = status


# ---- lookups ------------------------------------------------------------------
def short(role: str) -> str:
    return wf.ROLES[role]["short"]


def active_runs(p: Project) -> list:
    return [r for r in p.runs if r.status == "active"]


def latest_run(p: Project, key: str):
    for r in reversed(p.runs):
        if r.step_key == key:
            return r
    return None


def step_done(p: Project, key: str) -> bool:
    r = latest_run(p, key)
    return bool(r and r.status == "done")


def get_run(p: Project, run_id: int) -> StepRun:
    for r in p.runs:
        if r.id == run_id:
            return r
    raise WorkflowError("That step was not found.", 404)


def signed_roles(p: Project, run: StepRun) -> set:
    return {e.role for e in p.events if e.action == "signoff" and e.run_id == run.id}


def _role_matches(p: Project, user: User, role: str) -> bool:
    if user.role != role:
        return False
    if role == "initiator":          # the project's own initiator only
        return user.id == p.initiator_id
    return True


def can_act_run(p: Project, run: StepRun, user: User) -> bool:
    if p.status != "active" or run.status != "active" or not user.active:
        return False
    step = wf.STEP_BY_KEY[run.step_key]
    if run.assignee_id and run.assignee_id != user.id:      # handed to one chosen person
        return False
    done = signed_roles(p, run)
    for role in wf.actor_roles(step):
        if _role_matches(p, user, role):
            if step.get("all") and role in done:
                return False
            return True
    return False


def acting_runs(p: Project, user: User) -> list:
    return [r for r in active_runs(p) if can_act_run(p, r, user)]


def is_manager_of_involved(p: Project, user: User) -> bool:
    """A manager (anywhere up the reporting line) of anyone working on the project is responsible for it too –
    escalations reach them, so they must be able to open it and see all of it."""
    from sqlalchemy.orm import object_session
    db = object_session(p)
    if db is None:
        return False
    ids = {e.user_id for e in p.events if e.user_id} | {r.assignee_id for r in p.runs if r.assignee_id} |         {t.assignee_id for t in p.tasks}
    for r in active_runs(p):
        ids |= {u.id for u in people_for_roles(db, p, waiting_roles(p, r))}
    for uid in ids:
        cur, depth = db.get(User, uid), 0
        while cur and cur.manager_id and depth < 8:
            if cur.manager_id == user.id:
                return True
            cur, depth = db.get(User, cur.manager_id), depth + 1
    return False


def can_see(p: Project, user: User) -> bool:
    """People only see projects they work on. Directors, the Office Admin, the owner and the managers of the
    people working on it see everything."""
    if user.role == "admin" or user.role in DIRECTORS or p.initiator_id == user.id:
        return True
    if is_manager_of_involved(p, user):
        return True
    if acting_runs(p, user):
        return True
    if any(e.user_id == user.id for e in p.events):
        return True
    return any(t.assignee_id == user.id for t in p.tasks) or any(r.approver_id == user.id for r in p.requests)


def waiting_roles(p: Project, run: StepRun) -> list:
    if p.status in CLOSED or run.status != "active":
        return []
    step = wf.STEP_BY_KEY[run.step_key]
    if step.get("all"):
        done = signed_roles(p, run)
        return [r for r in step["roles"] if r not in done]
    return list(step["roles"])


def people_for_roles(db: Session, p: Project, roles: list) -> list:
    out = []
    for role in roles:
        if role == "initiator":
            out.append(p.initiator)
        else:
            out += list(db.scalars(select(User).where(User.role == role, User.active == True).order_by(User.name)))  # noqa: E712
    return out


def owners_text(db: Session, p: Project, keys: list) -> str:
    parts = []
    for k in keys:
        step = wf.STEP_BY_KEY[k]
        names = ", ".join(f"{u.name}" for u in people_for_roles(db, p, step["roles"])) or "—"
        parts.append(f"{names} ({' + '.join(short(r) for r in step['roles'])})")
    return " · ".join(parts)


def due_of(run: StepRun) -> datetime:
    return run.due_at


def can_pick_person(step: dict) -> bool:
    """A step can be handed to one chosen person when exactly one role works on it."""
    return len(step["roles"]) == 1 and not step.get("all") and step["roles"][0] != "initiator"


def _check_assignee(db: Session, p: Project, step: dict, assignee_id) -> int | None:
    if not assignee_id:
        return None
    u = db.get(User, assignee_id)
    if not can_pick_person(step) or not u or not u.active or u.role != step["roles"][0]:
        raise WorkflowError("That person cannot do this step. Please choose someone from the list.")
    return u.id


def _check_due(value, at: datetime) -> datetime:
    due = _parse_due(value)
    if due.date() < at.date():
        raise WorkflowError("Please choose a date from today onwards.")
    return due


# ---- notifications ------------------------------------------------------------------
def _notify(db: Session, p: Project, user_ids, text: str, at: datetime, kind="info", skip=None):
    for uid in dict.fromkeys(user_ids):
        if uid and uid != skip:
            db.add(Notification(user_id=uid, project_id=p.id, text=text[:400], kind=kind, created_at=at,
                                email_status="pending" if mailer.configured() else "off"))


def _director_ids(db: Session) -> list:
    return [u.id for u in db.scalars(select(User).where(User.role.in_(DIRECTORS), User.active == True))]  # noqa: E712


def _owner_ids(db: Session, p: Project, run: StepRun) -> list:
    if run.assignee_id and run.status == "active":
        return [run.assignee_id]
    return [u.id for u in people_for_roles(db, p, waiting_roles(p, run))]


def _event(p: Project, **kw) -> Event:
    ev = Event(**kw)
    p.events.append(ev)
    return ev


def _make_code(db: Session, p: Project, at: datetime) -> str:
    prefix = "NHO-" + ("DEV" if p.ptype == "development" else "INL") + f"-{at.year}-"
    codes = db.scalars(select(Project.code).where(Project.code.like(prefix + "%"))).all()
    n = max([int(c.rsplit("-", 1)[1]) for c in codes] + [0]) + 1
    return f"{prefix}{n:03d}"


# ---- runs ---------------------------------------------------------------------------------
def _start_run(db: Session, p: Project, key: str, at: datetime, actor: User | None, note: str = "",
               kind: str = "normal", return_to: str = "", notify: bool = True, assignee_id: int | None = None,
               due=None, handover: dict | None = None, return_user_id: int | None = None) -> StepRun:
    seq = 1 + sum(1 for r in p.runs if r.step_key == key)
    due_at = _check_due(due, at) if due else at + timedelta(days=wf.sla_days(key))
    run = StepRun(step_key=key, seq=seq, status="active", kind=kind, entered_at=at, due_at=due_at,
                  from_user_id=actor.id if actor else None, from_note=note, return_to=return_to,
                  return_user_id=return_user_id or None, assignee_id=_check_assignee(db, p, wf.STEP_BY_KEY[key], assignee_id), handover=handover or {})
    p.runs.append(run)
    if key == "updated_brief":
        p.clarification_pending = False
    p.updated_at = at
    db.flush()
    if notify and p.status == "active":
        step = wf.STEP_BY_KEY[key]
        who = f" – from {actor.name} ({short(actor.role)})" if actor else ""
        msg = f"{p.title} · your turn: {step['name']}{who}" + (f": {note}" if note else "")
        _notify(db, p, _owner_ids(db, p, run), msg, at, "turn", skip=actor.id if actor else None)
    return run


def _next_keys(p: Project, run: StepRun, target: str | None = None):
    """(keys to start, group entered, mode, finished) after `run` is completed."""
    step = wf.STEP_BY_KEY[run.step_key]
    if run.return_to:
        return [run.return_to], None, None, False
    if target:
        return [target], None, None, False
    if step.get("to"):
        return [step["to"]], None, None, False
    if run.step_key == "submission" and p.clarification_pending:
        return ["updated_brief"], None, None, False
    return wf.successors(run.step_key, p.ptype, p.fast_track, p.group_mode,
                         lambda k: k == run.step_key or step_done(p, k))


def preview_next(db: Session, p: Project, run: StepRun, option: str | None = None) -> dict:
    """Where a finished step goes next – shown on the button so nobody is surprised."""
    step = wf.STEP_BY_KEY[run.step_key]
    target = None
    if option and step["mode"] == "decision":
        o = step["options"][option]
        target = o.get("to") if o["kind"] in ("approve", "back") else None
    keys, _, _, finished = _next_keys(p, run, target)
    if finished or (not keys and step["key"] == "completion"):
        return {"end": True, "steps": []}
    if not keys:
        return {"end": False, "wait": True, "steps": []}
    now = datetime.utcnow()
    return {"end": False, "wait": False, "steps": [
        {"key": k, "name": wf.STEP_BY_KEY[k]["name"], "sla": wf.sla_days(k),
         "pick": can_pick_person(wf.STEP_BY_KEY[k]) and len(people_for_roles(db, p, wf.STEP_BY_KEY[k]["roles"])) > 1,
         "default_due": (now + timedelta(days=wf.sla_days(k))).date().isoformat(),
         "people": [{"id": u.id, "name": u.name, "short": short(u.role)}
                    for u in people_for_roles(db, p, wf.STEP_BY_KEY[k]["roles"])]}
        for k in keys]}


# ---- create ----------------------------------------------------------------------------------
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
    p = Project(title=data["title"].strip(), description=(data.get("description") or "").strip(),
                ptype=data["ptype"], market=(data.get("market") or "").strip(), est_value=data.get("est_value"),
                target_date=data.get("target_date") or "", initiator_id=initiator.id, created_at=at, updated_at=at,
                group_mode={})
    db.add(p)
    db.flush()
    p.initiator = initiator
    first = StepRun(step_key="opportunity", seq=1, status="done", entered_at=at, due_at=at, completed_at=at,
                    completed_by_id=user.id, from_user_id=user.id)
    p.runs.append(first)
    db.flush()
    _event(p, kind="step", action="done", step_key="opportunity", run_id=first.id, role="initiator", user_id=user.id,
           note="Opportunity identified", created_at=at, to_text=owners_text(db, p, ["screening"]),
           meta={"data": [], "checks": [], "docs": []})
    _start_run(db, p, "screening", at, user, notify=False)
    db.commit()
    return p


# ---- completion checks -------------------------------------------------------------------------
def _validate(p: Project, run: StepRun, step: dict, role: str, data: dict | None, checks: list | None) -> dict:
    for d in step.get("docs", []):
        if d.get("role") not in (None, role):                    # another team's document on a joint step
            continue
        if d["required"] and not any(x.step_key == step["key"] and x.doc_type == d["key"] for x in p.documents):
            raise WorkflowError(f"Please add: {d['label']} (a file or a link).")
    data = data or {}
    out = []
    for f in step.get("fields", []):
        v = data.get(f["key"])
        v = "" if v is None else str(v).strip()
        if not v:
            if f["required"]:
                raise WorkflowError(f"Please fill in: {f['label']}.")
            continue
        if f["type"] == "number":
            try:
                float(v)
            except ValueError:
                raise WorkflowError(f"{f['label']} must be a number.")
        elif f["type"] == "date":
            try:
                datetime.strptime(v, "%Y-%m-%d")
            except ValueError:
                raise WorkflowError(f"{f['label']} must be a date.")
        elif f["type"] == "select" and v not in (f.get("options") or []):
            raise WorkflowError(f"Please choose: {f['label']}.")
        out.append({"key": f["key"], "label": f["label"], "value": v, "unit": f.get("unit")})
    ticked = set(checks or [])
    need = wf.required_checks(step, role)
    for c in need:
        if c["key"] not in ticked:
            raise WorkflowError(f"Please tick: {c['label']}.")
    docs = [d.id for d in p.documents if d.step_key == step["key"] and d.created_at >= run.entered_at]
    return {"data": out, "checks": [c["label"] for c in need], "docs": docs}


def _apply_maps(p: Project, step: dict, meta: dict):
    for item in meta["data"]:
        fdef = next(f for f in step["fields"] if f["key"] == item["key"])
        if fdef.get("maps") == "est_value":
            p.est_value = float(item["value"])
        elif fdef.get("maps") in ("target_date", "manufacturer"):
            setattr(p, fdef["maps"], item["value"])


def _blocking_tasks(p: Project, run: StepRun) -> list:
    return [t for t in p.tasks if t.status == "open" and t.blocking and t.step_key == run.step_key]


# ---- act on a step ---------------------------------------------------------------------------------
def act(db: Session, p: Project, user: User, run_id: int, option: str | None = None, note: str = "",
        data: dict | None = None, checks: list | None = None, at: datetime | None = None,
        nexts: dict | None = None) -> dict:
    """`nexts` lets the person pick who gets each next step and by when: {step_key: {assignee_id, due}}."""
    at = at or datetime.utcnow()
    note = (note or "").strip()
    run = get_run(p, run_id)
    if p.status != "active":
        raise WorkflowError(f"This project is {p.status.replace('_', ' ')}. Nothing can be done on it right now.")
    if run.status != "active":
        raise WorkflowError("This step is no longer waiting. Please refresh.")
    step = wf.STEP_BY_KEY[run.step_key]
    if not can_act_run(p, run, user):
        who = " / ".join(wf.ROLES[r]["label"] for r in waiting_roles(p, run))
        raise WorkflowError(f"This step is waiting for {who}. You cannot act on it.", 403)
    role = next(r for r in wf.actor_roles(step) if _role_matches(p, user, r))
    base = dict(kind="step", step_key=step["key"], run_id=run.id, role=role, user_id=user.id, created_at=at)

    if step["mode"] == "decision":
        if option not in step["options"]:
            raise WorkflowError("Please choose one of the decision buttons.")
        opt = step["options"][option]
        if opt.get("note") and not note:
            raise WorkflowError("Please write a short reason for this decision.")
        base["option"] = option
        if opt["kind"] == "back":
            return _send_back(db, p, user, run, opt["to"], note, [], at, chart=True, option=option,
                              nxt=(nexts or {}).get(opt["to"]))
        if opt["kind"] == "hold":
            _event(p, action="hold", note=note, **base)
            p.status, p.status_note, p.updated_at = "on_hold", note, at
            _notify(db, p, [p.initiator_id] + _director_ids(db), f"{p.title} – put on hold: {note}", at, "hold", user.id)
            db.commit()
            return {"moved": False, "message": "Project put on hold."}
        if opt["kind"] == "reject":
            _event(p, action="reject", note=note, **base)
            p.status, p.status_note, p.updated_at = "rejected", note, at
            _notify(db, p, [p.initiator_id] + _director_ids(db), f"{p.title} – rejected: {note}", at, "reject", user.id)
            db.commit()
            return {"moved": False, "message": "Project rejected and closed."}
        target = opt.get("to")
        action = "approve"
    else:
        target, action = None, "done"

    blocking = _blocking_tasks(p, run)
    if blocking:
        raise WorkflowError(f"Please finish this task first: {blocking[0].title}.")
    meta = _validate(p, run, step, role, data, checks)
    _apply_maps(p, step, meta)
    if step["key"] == "code" and not p.code:
        p.code = _make_code(db, p, at)
        note = note or f"Code {p.code} generated"
    if option == "incomplete" or step.get("sets"):
        for k, v in ({"clarification_pending": True} if option == "incomplete" else step["sets"]).items():
            setattr(p, k, v)

    if step.get("all"):
        _event(p, action="signoff", note=note, meta=meta, to_text="", **{k: v for k, v in base.items() if k != "option"},
               option=option or "")
        db.flush()
        left = waiting_roles(p, run)
        if left:
            p.updated_at = at
            db.commit()
            return {"moved": False, "message": "Saved. Waiting for " + ", ".join(short(r) for r in left) + "."}
    return _finish(db, p, run, user, role, action, option or "", note, meta, at, target, nexts or {})


def _submitted(p: Project, run: StepRun, meta: dict) -> dict:
    """Everything this step handed over: details, ticks and documents (all signers' on a joint step)."""
    data, checks, docs = list(meta["data"]), list(meta["checks"]), list(meta["docs"])
    for e in p.events:
        if e.action == "signoff" and e.run_id == run.id:
            for key, src in (("data", data), ("checks", checks), ("docs", docs)):
                for x in (e.meta or {}).get(key, []):
                    if x not in src:
                        src.append(x)
    return {"data": data, "checks": checks, "docs": docs}


def _finish(db, p, run, user, role, action, option, note, meta, at, target=None, nexts=None) -> dict:
    nexts = nexts or {}
    run.status, run.completed_at, run.completed_by_id = "done", at, user.id
    keys, group, mode, finished = _next_keys(p, run, target)
    ev = _event(p, kind="step", action=action, step_key=run.step_key, run_id=run.id, option=option, role=role,
                user_id=user.id, note=note, meta=meta, created_at=at)
    if group:
        p.group_mode = {**p.group_mode, group: mode}
    if run.step_key == "completion":
        p.status, p.updated_at = "completed", at
        ev.to_text = "Project closed"
        _notify(db, p, [p.initiator_id] + _director_ids(db), f"{p.title} – project completed", at, "done", user.id)
        db.commit()
        return {"moved": False, "message": "Project completed. Well done!"}
    handoff = ("Fixed – back to you: " + note) if run.return_to and note else note
    step = wf.STEP_BY_KEY[run.step_key]
    given = {"step_key": run.step_key, "step_name": step["name"], "by": user.name, "role": short(role),
             "kind": "fixed" if run.return_to else "done", "note": note, **_submitted(p, run, meta)}
    for k in keys:
        nx = nexts.get(k) or {}
        who, kind, again, again_user = nx.get("assignee_id"), "normal", "", None
        if run.return_to and k == run.return_to:
            if not who and run.return_user_id:                    # straight back to whoever sent it
                who = run.return_user_id if _can_return_to(db, wf.STEP_BY_KEY[k], run.return_user_id) else None
            sent = next((r for r in reversed(p.runs) if r.step_key == k and r.status == "returned"), None)
            if sent and sent.return_to:                           # it had itself been sent back: keep that way home
                kind, again, again_user = sent.kind, sent.return_to, sent.return_user_id
        _start_run(db, p, k, at, user, note=handoff, kind=kind, assignee_id=who, due=nx.get("due"), handover=given,
                   return_to=again, return_user_id=again_user)
    ev.to_text = owners_text(db, p, keys) if keys else "Waiting for the other tracks to finish"
    if action == "approve" or run.step_key in ("clarification",):
        _notify(db, p, [p.initiator_id], f"{p.title} – {wf.STEP_BY_KEY[run.step_key]['name']}: "
                f"{'approved' if action == 'approve' else 'done'} by {user.name} ({short(role)})", at, "done", user.id)
    p.updated_at = at
    db.commit()
    if not keys:
        return {"moved": False, "message": "Done. Waiting for the other tracks to finish."}
    names = " and ".join(wf.STEP_BY_KEY[k]["name"] for k in keys)
    return {"moved": True, "message": f"Done. Next: {names}."}


def _can_return_to(db: Session, step: dict, user_id: int) -> bool:
    u = db.get(User, user_id)
    return bool(u and u.active and can_pick_person(step) and u.role == step["roles"][0])


# ---- send back ---------------------------------------------------------------------------------------
def send_back_targets(db: Session, p: Project, run: StepRun) -> list:
    """Earlier steps this step can be sent back to (with who did them), nearest first."""
    order = wf.flat_order(p.ptype)
    if run.step_key not in order:
        return []
    idx = order.index(run.step_key)
    pool = order[:idx]
    gi = wf.group_of(run.step_key)
    if gi and p.group_mode.get(gi[0]) == "fast":          # parallel track: only within its own track
        track = wf.GROUPS[gi[0]]["tracks"][gi[1]]["steps"]
        pool = [k for k in track if k in order and order.index(k) < idx]
    out = []
    for k in reversed(pool):
        lr = latest_run(p, k)
        if lr and lr.status == "done" and k not in ("opportunity", "code"):
            step = wf.STEP_BY_KEY[k]
            out.append({"key": k, "name": step["name"], "phase": step["phase"],
                        "done_by": lr.completed_by.name if lr.completed_by else "",
                        "pick": can_pick_person(step) and len(people_for_roles(db, p, step["roles"])) > 1,
                        "default_due": (datetime.utcnow() + timedelta(days=wf.sla_days(k))).date().isoformat(),
                        "people": [{"id": u.id, "name": u.name, "short": short(u.role)}
                                   for u in people_for_roles(db, p, step["roles"])]})
    return out


def send_back(db: Session, p: Project, user: User, run_id: int, target: str, note: str,
              doc_ids: list | None = None, at: datetime | None = None, assignee_id: int | None = None,
              due=None) -> dict:
    at = at or datetime.utcnow()
    run = get_run(p, run_id)
    if p.status != "active" or run.status != "active":
        raise WorkflowError("This step is not waiting any more. Please refresh.")
    if not can_act_run(p, run, user):
        raise WorkflowError("Only the person this step is waiting for can send it back.", 403)
    return _send_back(db, p, user, run, target, (note or "").strip(), doc_ids or [], at,
                      nxt={"assignee_id": assignee_id, "due": due})


def _send_back(db, p, user, run, target, note, doc_ids, at, chart=False, option="", nxt=None) -> dict:
    nxt = nxt or {}
    if not note:
        raise WorkflowError("Please write why you are sending it back.")
    step = wf.STEP_BY_KEY[run.step_key]
    if not chart and target not in [t["key"] for t in send_back_targets(db, p, run)]:
        raise WorkflowError("It cannot be sent back to that step.")
    role = next((r for r in wf.actor_roles(step) if _role_matches(p, user, r)), user.role)
    run.status, run.completed_at = "returned", at
    tstep = wf.STEP_BY_KEY[target]
    docs = [d.id for d in p.documents if d.id in set(doc_ids or [])]
    new = _start_run(db, p, target, at, user, note=note, kind="rework", return_to="" if chart else run.step_key,
                     return_user_id=None if chart else user.id, notify=False, assignee_id=nxt.get("assignee_id"), due=nxt.get("due"),
                     handover={"step_key": run.step_key, "step_name": step["name"], "by": user.name, "role": short(role),
                               "kind": "sendback", "note": note, "data": [], "checks": [], "docs": docs})
    _event(p, kind="step", action="sendback", step_key=run.step_key, run_id=run.id, option=option, role=role,
           user_id=user.id, note=note, created_at=at, to_text=owners_text(db, p, [target]),
           meta={"target": target, "target_name": tstep["name"], "docs": docs, "chart": chart})
    msg = f"{p.title} · sent back to you by {user.name} ({short(role)}): {tstep['name']} – {note}"
    _notify(db, p, _owner_ids(db, p, new), msg, at, "back", user.id)
    _notify(db, p, [p.initiator_id], f"{p.title} – {step['name']} sent back to {tstep['name']} by {user.name}", at,
            "back", user.id)
    p.updated_at = at
    db.commit()
    return {"moved": True, "message": f"Sent back to: {tstep['name']}."}


# ---- project-level controls ----------------------------------------------------------------------------------
def _is_director(user: User) -> bool:
    return user.role in DIRECTORS


def hold_project(db, p, user, note, at=None):
    at = at or datetime.utcnow()
    if not _is_director(user):
        raise WorkflowError("Only a Director can put a project on hold.", 403)
    if p.status != "active":
        raise WorkflowError("Only an active project can be put on hold.")
    if not (note or "").strip():
        raise WorkflowError("Please write a short reason.")
    _event(p, kind="system", action="hold", role=user.role, user_id=user.id, note=note.strip(), created_at=at)
    p.status, p.status_note, p.updated_at = "on_hold", note.strip(), at
    owners = [i for r in active_runs(p) for i in _owner_ids(db, p, r)]
    p.status = "on_hold"
    _notify(db, p, [p.initiator_id] + owners, f"{p.title} – put on hold by {user.name}: {note.strip()}", at, "hold", user.id)
    db.commit()


def resume_project(db, p, user, note="", at=None):
    at = at or datetime.utcnow()
    if not _is_director(user):
        raise WorkflowError("Only a Director can restart a project that is on hold.", 403)
    if p.status != "on_hold":
        raise WorkflowError("This project is not on hold.")
    _event(p, kind="system", action="resume", role=user.role, user_id=user.id, note=(note or "").strip(), created_at=at)
    p.status, p.status_note, p.updated_at = "active", "", at
    for r in active_runs(p):
        r.due_at, r.reminder_level = at + timedelta(days=wf.sla_days(r.step_key)), 0
    db.flush()
    for r in active_runs(p):
        _notify(db, p, _owner_ids(db, p, r), f"{p.title} · restarted – your turn: {wf.STEP_BY_KEY[r.step_key]['name']}",
                at, "turn", user.id)
    db.commit()


def cancel_project(db, p, user, note, at=None):
    at = at or datetime.utcnow()
    if not _is_director(user):
        raise WorkflowError("Only a Director can cancel a project.", 403)
    if p.status in CLOSED:
        raise WorkflowError("This project is already closed.")
    if not (note or "").strip():
        raise WorkflowError("Please write a short reason.")
    _event(p, kind="system", action="cancel", role=user.role, user_id=user.id, note=note.strip(), created_at=at)
    owners = [i for r in active_runs(p) for i in _owner_ids(db, p, r)]
    p.status, p.status_note, p.updated_at = "cancelled", note.strip(), at
    _notify(db, p, [p.initiator_id] + owners, f"{p.title} – cancelled by {user.name}: {note.strip()}", at, "reject", user.id)
    db.commit()


def move_project(db, p, user, step_key, note, at=None):
    """Office Admin correction: put the project back on one chosen step."""
    at = at or datetime.utcnow()
    if user.role != "admin":
        raise WorkflowError("Only the Office Admin can correct the step.", 403)
    if step_key not in wf.flat_order(p.ptype):
        raise WorkflowError("That step does not exist for this project type.")
    if not (note or "").strip():
        raise WorkflowError("Please write why the step is being corrected.")
    for r in active_runs(p):
        r.status, r.completed_at = "returned", at
    _event(p, kind="system", action="moved", step_key=step_key, role="admin", user_id=user.id, note=note.strip(),
           created_at=at, meta={"target_name": wf.STEP_BY_KEY[step_key]["name"]})
    if p.status in ("on_hold", "completed"):
        p.status = "active"
    _start_run(db, p, step_key, at, user, note=note.strip())
    db.commit()


def set_fast_track(db, p, user, on: bool, at=None):
    at = at or datetime.utcnow()
    if not _is_director(user):
        raise WorkflowError("Only a Director can switch Fast track on or off.", 403)
    if p.status in CLOSED:
        raise WorkflowError("This project is closed.")
    if p.fast_track == on:
        return
    p.fast_track = on
    _event(p, kind="system", action="fasttrack", role=user.role, user_id=user.id, created_at=at,
           note="Fast track on: parallel steps run side by side from now on" if on else "Fast track off: back to the chart order")
    _notify(db, p, [p.initiator_id], f"{p.title} – Fast track {'on' if on else 'off'} (set by {user.name})", at, "info", user.id)
    p.updated_at = at
    db.commit()


# ---- notes and documents -------------------------------------------------------------------------------------
def add_comment(db, p, user, text, at=None):
    text = (text or "").strip()
    if not text:
        raise WorkflowError("Please type a note first.")
    at = at or datetime.utcnow()
    cur = active_runs(p)
    _event(p, kind="comment", action="comment", step_key=cur[0].step_key if cur else "", role=user.role,
           user_id=user.id, note=text, created_at=at)
    p.updated_at = at
    owners = [i for r in cur for i in _owner_ids(db, p, r)]
    _notify(db, p, [p.initiator_id] + owners, f"{user.name} wrote a note on {p.title}: {text[:90]}", at, "note", user.id)
    db.commit()


def _check_doc_target(p: Project, step_key: str, doc_type: str, task_id=None):
    if step_key and step_key not in wf.STEP_BY_KEY:
        raise WorkflowError("Unknown step.")
    if task_id and not any(t.id == task_id for t in p.tasks):
        raise WorkflowError("That task was not found.", 404)


def _check_slot_owner(user: User, step_key: str, doc_type: str):
    slot = next((d for d in wf.STEP_BY_KEY.get(step_key, {}).get("docs", []) if d["key"] == doc_type), None)
    if slot and slot.get("role") and user.role not in (slot["role"], "admin"):
        raise WorkflowError(f"This document is added by {wf.ROLES[slot['role']]['label']}.", 403)


def _clean_url(url: str) -> str:
    url = (url or "").strip()
    if url and not url.lower().startswith(("http://", "https://")):
        raise WorkflowError("The link must start with http:// or https://")
    return url[:1000]


def add_document(db, p, user, title="", url="", filename="", stored="", size=0, step_key="", doc_type="",
                 task_id=None, at=None) -> Document:
    """One kind of thing: a document with a name, and a file, a link, or both."""
    _check_doc_target(p, step_key, doc_type, task_id)
    _check_slot_owner(user, step_key, doc_type)
    url = _clean_url(url)
    if not url and not stored:
        raise WorkflowError("Please choose a file or paste a link.")
    at = at or datetime.utcnow()
    kind = "both" if (url and stored) else "file" if stored else "link"
    d = Document(kind=kind, step_key=step_key or "", doc_type=doc_type or "", task_id=task_id or None,
                 title=(title or "").strip() or filename or url, filename=filename, stored_name=stored, size=size,
                 url=url, user_id=user.id, created_at=at)
    p.documents.append(d)
    db.flush()
    _doc_event(p, user, d, "doc_added", at)
    p.updated_at = at
    db.commit()
    return d


def add_file(db, p, user, filename, stored, size, step_key="", doc_type="", at=None, task_id=None) -> Document:
    return add_document(db, p, user, filename=filename, stored=stored, size=size, step_key=step_key, doc_type=doc_type,
                        task_id=task_id, at=at)


def add_link(db, p, user, title, url, step_key="", doc_type="", at=None, task_id=None) -> Document:
    if not (url or "").strip():
        raise WorkflowError("Please paste the link.")
    return add_document(db, p, user, title=title, url=url, step_key=step_key, doc_type=doc_type, task_id=task_id, at=at)


def attach_documents(db, p, user, doc_ids, step_key="", doc_type="", task_id=None, at=None) -> list:
    """Use documents that are already in the project (no need to upload again)."""
    _check_doc_target(p, step_key, doc_type, task_id)
    _check_slot_owner(user, step_key, doc_type)
    at = at or datetime.utcnow()
    by_id = {d.id: d for d in p.documents}
    made = []
    for i in doc_ids:
        src = by_id.get(i)
        if not src:
            raise WorkflowError("That document was not found.", 404)
        src = by_id.get(src.source_id, src)
        if any((x.source_id or x.id) == src.id and x.step_key == (step_key or "") and x.doc_type == (doc_type or "")
               and x.task_id == (task_id or None) for x in p.documents):
            continue                                   # already there
        d = Document(kind=src.kind, step_key=step_key or "", doc_type=doc_type or "", task_id=task_id or None,
                     title=src.title, filename=src.filename, stored_name=src.stored_name, size=src.size, url=src.url,
                     source_id=src.id, important=False, user_id=user.id, created_at=at)
        p.documents.append(d)
        db.flush()
        _doc_event(p, user, d, "doc_added", at)
        made.append(d.id)
    p.updated_at = at
    db.commit()
    return made


def _doc_event(p, user, d, action, at):
    step = wf.STEP_BY_KEY.get(d.step_key)
    label = next((x["label"] for x in (step or {}).get("docs", []) if x["key"] == d.doc_type), "")
    task = next((t for t in p.tasks if t.id == d.task_id), None) if d.task_id else None
    _event(p, kind="doc", action=action, step_key=d.step_key, role=user.role, user_id=user.id, created_at=at,
           note=d.title, meta={"doc_id": d.id, "kind": d.kind, "doc_label": label,
                               "task": task.title if task else "", "task_id": d.task_id, "reuse": bool(d.source_id)})


def remove_document(db, p, user, d: Document, at=None) -> bool:
    """Returns True when the stored file is no longer used by anything and can be deleted from disk."""
    at = at or datetime.utcnow()
    if not (user.role == "admin" or d.user_id == user.id):
        raise WorkflowError("Only the person who added it (or the Office Admin) can remove it.", 403)
    if not d.source_id and any(x.source_id == d.id for x in p.documents):
        raise WorkflowError("This document is used in other places. Remove it there first.")
    _doc_event(p, user, d, "doc_removed", at)
    stored = d.stored_name
    p.documents.remove(d)
    db.delete(d)
    db.flush()
    still = bool(stored) and any(x.stored_name == stored for x in p.documents if x.id != d.id)
    db.commit()
    return bool(stored) and not still


def set_important(db, p, user, d: Document, on: bool, at=None):
    at = at or datetime.utcnow()
    if not (user.role == "admin" or _is_director(user) or user.id == p.initiator_id or d.user_id == user.id):
        raise WorkflowError("Only the person who added it, the initiator, a Director or the Office Admin can mark a key document.", 403)
    d = next((x for x in p.documents if x.id == (d.source_id or d.id)), d)
    if d.important == on:
        return
    d.important = on
    _event(p, kind="doc", action="doc_key" if on else "doc_unkey", step_key=d.step_key, role=user.role, user_id=user.id,
           created_at=at, note=d.title, meta={"doc_id": d.id, "kind": d.kind})
    db.commit()


# ---- due dates, requests ------------------------------------------------------------------------------------------
def _approver_for(db: Session, requester: User, assigner_id: int | None) -> User:
    """Time requests go to whoever gave the date; if that is not possible, to the manager, then a Director."""
    if assigner_id and assigner_id != requester.id:
        a = db.get(User, assigner_id)
        if a and a.active:
            return a
    if requester.manager_id:
        m = db.get(User, requester.manager_id)
        if m and m.active:
            return m
    want = "otc_director" if wf.ROLES[requester.role]["org"] == "Neo Health (OTC)" else "india_director"
    d = db.scalar(select(User).where(User.role == want, User.active == True))  # noqa: E712
    return d or db.scalar(select(User).where(User.role.in_(DIRECTORS), User.active == True))  # noqa: E712


def _parse_due(value) -> datetime:
    if isinstance(value, datetime):
        return value
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d") + timedelta(hours=17)
    except ValueError:
        raise WorkflowError("Please choose a valid date.")


def request_time(db, p, user, run_id=None, task_id=None, new_due=None, reason="", at=None) -> Request:
    at = at or datetime.utcnow()
    reason = (reason or "").strip()
    new = _parse_due(new_due)
    if not reason:
        raise WorkflowError("Please say why you need more time.")
    if run_id:
        run = get_run(p, run_id)
        if not can_act_run(p, run, user):
            raise WorkflowError("Only the person this step is waiting for can ask for more time.", 403)
        old, kind, assigner, label = run.due_at, "step", run.from_user_id, wf.STEP_BY_KEY[run.step_key]["name"]
        pending = [r for r in p.requests if r.status == "pending" and r.run_id == run.id]
    else:
        task = next((t for t in p.tasks if t.id == task_id), None)
        if not task or task.status != "open":
            raise WorkflowError("That task was not found.", 404)
        if task.assignee_id != user.id:
            raise WorkflowError("Only the person the task is given to can ask for more time.", 403)
        run = None
        old, kind, assigner, label = task.due_at, "task", task.creator_id, task.title
        pending = [r for r in p.requests if r.status == "pending" and r.task_id == task.id]
    if new <= old:
        raise WorkflowError("The new date must be later than the current date.")
    if pending:
        raise WorkflowError("A request for more time is already waiting for an answer.")
    approver = _approver_for(db, user, assigner)
    req = Request(kind=kind, run_id=run.id if run else None, task_id=None if run else task.id,
                  requested_by_id=user.id, approver_id=approver.id, old_due=old, new_due=new, reason=reason,
                  created_at=at)
    p.requests.append(req)
    db.flush()
    _event(p, kind="request", action="ext_ask", step_key=run.step_key if run else task.step_key, role=user.role,
           user_id=user.id, note=reason, created_at=at, to_text=f"{approver.name} ({short(approver.role)})",
           meta={"request_id": req.id, "label": label, "old": old.isoformat(), "new": new.isoformat()})
    _notify(db, p, [approver.id], f"{user.name} asks for more time on “{label}” ({p.title}): "
            f"{old:%d %b} → {new:%d %b}. Reason: {reason}", at, "request", user.id)
    p.updated_at = at
    db.commit()
    return req


def decide_request(db, p, user, req_id, approve: bool, note="", at=None):
    at = at or datetime.utcnow()
    req = next((r for r in p.requests if r.id == req_id), None)
    if not req:
        raise WorkflowError("That request was not found.", 404)
    if req.status != "pending":
        raise WorkflowError("This request has already been answered.")
    if not (user.id == req.approver_id or _is_director(user)) or user.id == req.requested_by_id:
        raise WorkflowError("This request was not sent to you.", 403)
    note = (note or "").strip()
    if not approve and not note:
        raise WorkflowError("Please say why you are declining.")
    req.status, req.decided_by_id, req.decided_at, req.decision_note = ("approved" if approve else "declined"), user.id, at, note
    label = ""
    if req.run_id:
        run = get_run(p, req.run_id)
        label = wf.STEP_BY_KEY[run.step_key]["name"]
        if approve:
            run.due_at, run.reminder_level = req.new_due, 0
    else:
        task = next(t for t in p.tasks if t.id == req.task_id)
        label = task.title
        if approve:
            task.due_at, task.reminder_level = req.new_due, 0
    _event(p, kind="request", action="ext_yes" if approve else "ext_no", step_key=wf.STEP_BY_KEY.get(
        get_run(p, req.run_id).step_key if req.run_id else "", {}).get("key", ""), role=user.role, user_id=user.id,
           note=note, created_at=at, to_text=f"{req.requested_by.name} ({short(req.requested_by.role)})",
           meta={"request_id": req.id, "label": label, "old": req.old_due.isoformat(), "new": req.new_due.isoformat()})
    _notify(db, p, [req.requested_by_id], f"{user.name} {'approved' if approve else 'declined'} your request for more "
            f"time on “{label}”" + (f" – new date {req.new_due:%d %b}" if approve else f": {note}"), at,
            "done" if approve else "back", user.id)
    p.updated_at = at
    db.commit()


def set_due(db, p, user, run_id, new_due, note="", at=None):
    """Change a due date straight away – by whoever gave it, a Director or the Office Admin."""
    at = at or datetime.utcnow()
    run = get_run(p, run_id)
    if run.status != "active":
        raise WorkflowError("This step is not waiting any more.")
    if not (user.id == run.from_user_id or _is_director(user) or user.role == "admin"):
        raise WorkflowError("Only the person who gave the date, a Director or the Office Admin can change it.", 403)
    new = _parse_due(new_due)
    old = run.due_at
    run.due_at, run.reminder_level = new, 0
    _event(p, kind="step", action="due", step_key=run.step_key, run_id=run.id, role=user.role, user_id=user.id,
           note=(note or "").strip(), created_at=at, meta={"old": old.isoformat(), "new": new.isoformat()})
    _notify(db, p, _owner_ids(db, p, run), f"{user.name} changed the date of “{wf.STEP_BY_KEY[run.step_key]['name']}” "
            f"({p.title}) to {new:%d %b}", at, "info", user.id)
    db.commit()


def reassign_run(db, p, user, run_id, assignee_id, at=None):
    """Change who a waiting step is handed to (the sender, a Director or the Office Admin)."""
    at = at or datetime.utcnow()
    run = get_run(p, run_id)
    if run.status != "active":
        raise WorkflowError("This step is not waiting any more.")
    if not (user.id == run.from_user_id or _is_director(user) or user.role == "admin" or can_act_run(p, run, user)):
        raise WorkflowError("Only the person who handed it over, the person it is with, a Director or the Office Admin can change this.", 403)
    step = wf.STEP_BY_KEY[run.step_key]
    old = run.assignee_id
    new = _check_assignee(db, p, step, assignee_id)
    if old == new:
        return
    run.assignee_id = new
    run.reminder_level = 0
    text = owners_text(db, p, [run.step_key]) if not new else f"{db.get(User, new).name} ({short(step['roles'][0])})"
    _event(p, kind="step", action="assign", step_key=run.step_key, run_id=run.id, role=user.role, user_id=user.id,
           created_at=at, to_text=text, note="")
    _notify(db, p, _owner_ids(db, p, run), f"{p.title} · your turn: {step['name']} – handed to you by {user.name}", at, "turn", user.id)
    db.commit()


# ---- tasks --------------------------------------------------------------------------------------------------------------
def create_task(db, p, user, title, assignee_id, due, details="", step_key="", blocking=False, at=None) -> Task:
    at = at or datetime.utcnow()
    if p.status in CLOSED:
        raise WorkflowError("This project is closed.")
    if not (user.role == "admin" or _is_director(user) or user.id == p.initiator_id or acting_runs(p, user)):
        raise WorkflowError("Only people working on this project can give tasks.", 403)
    title = (title or "").strip()
    if not title:
        raise WorkflowError("Please write what needs to be done.")
    assignee = db.get(User, assignee_id or 0)
    if not assignee or not assignee.active or assignee.role == "admin":
        raise WorkflowError("Please choose who should do it.")
    due_dt = _parse_due(due)
    if step_key and step_key not in wf.STEP_BY_KEY:
        raise WorkflowError("Unknown step.")
    t = Task(title=title, details=(details or "").strip(), assignee_id=assignee.id, creator_id=user.id,
             step_key=step_key or "", blocking=bool(blocking and step_key), due_at=due_dt, created_at=at)
    p.tasks.append(t)
    db.flush()
    _event(p, kind="task", action="task_new", step_key=t.step_key, role=user.role, user_id=user.id, created_at=at,
           note=title, to_text=f"{assignee.name} ({short(assignee.role)})",
           meta={"task_id": t.id, "due": due_dt.isoformat(), "blocking": t.blocking})
    _notify(db, p, [assignee.id], f"New task from {user.name} ({short(user.role)}) on {p.title}: {title} – due {due_dt:%d %b}",
            at, "turn", user.id)
    p.updated_at = at
    db.commit()
    return t


def _get_task(p, task_id) -> Task:
    t = next((x for x in p.tasks if x.id == task_id), None)
    if not t:
        raise WorkflowError("That task was not found.", 404)
    return t


def complete_task(db, p, user, task_id, note="", at=None):
    at = at or datetime.utcnow()
    t = _get_task(p, task_id)
    if t.status != "open":
        raise WorkflowError("This task is already closed.")
    if t.assignee_id != user.id:
        raise WorkflowError("Only the person the task is given to can finish it.", 403)
    t.status, t.completed_at, t.done_note = "done", at, (note or "").strip()
    _event(p, kind="task", action="task_done", step_key=t.step_key, role=user.role, user_id=user.id, created_at=at,
           note=t.done_note or t.title, to_text=f"{t.creator.name} ({short(t.creator.role)})",
           meta={"task_id": t.id, "title": t.title})
    _notify(db, p, [t.creator_id], f"{user.name} finished the task “{t.title}” ({p.title})", at, "done", user.id)
    p.updated_at = at
    db.commit()


def cancel_task(db, p, user, task_id, at=None):
    at = at or datetime.utcnow()
    t = _get_task(p, task_id)
    if t.status != "open":
        raise WorkflowError("This task is already closed.")
    if not (user.id == t.creator_id or _is_director(user) or user.role == "admin"):
        raise WorkflowError("Only the person who gave the task can cancel it.", 403)
    t.status = "cancelled"
    _event(p, kind="task", action="task_cancel", step_key=t.step_key, role=user.role, user_id=user.id, created_at=at,
           note=t.title, to_text=f"{t.assignee.name} ({short(t.assignee.role)})", meta={"task_id": t.id})
    _notify(db, p, [t.assignee_id], f"{user.name} cancelled the task “{t.title}” ({p.title})", at, "info", user.id)
    db.commit()


# ---- reminders and escalation ---------------------------------------------------------------------------------------------
def nudge(db: Session, p: Project, user: User, run_id: int, at: datetime | None = None) -> str:
    at = at or datetime.utcnow()
    run = get_run(p, run_id)
    if p.status != "active" or run.status != "active":
        raise WorkflowError("This is not waiting for anyone.")
    if can_act_run(p, run, user):
        raise WorkflowError("It is your turn on this step.")
    if run.last_nudge_at and at - run.last_nudge_at < timedelta(hours=12):
        raise WorkflowError("A reminder was already sent a short while ago.")
    _notify(db, p, _owner_ids(db, p, run), f"{user.name} ({short(user.role)}) reminds you: {p.title} · "
            f"{wf.STEP_BY_KEY[run.step_key]['name']}", at, "remind", user.id)
    run.last_nudge_at = at
    _event(p, kind="system", action="nudge", step_key=run.step_key, role=user.role, user_id=user.id, note="Reminder sent",
           created_at=at, to_text=owners_text(db, p, [run.step_key]))
    db.commit()
    return "Reminder sent."


def run_reminders(db: Session, now: datetime | None = None) -> dict:
    """Past due → remind the owners. A further full period → tell their managers (or the Directors).
    Also nudges approvers of time requests that wait more than 2 days."""
    now = now or datetime.utcnow()
    reminded = escalated = 0
    for p in db.scalars(select(Project).where(Project.status == "active")):
        for run in active_runs(p):
            sla = timedelta(days=wf.sla_days(run.step_key))
            late = now - run.due_at
            if late.total_seconds() <= 0:
                continue
            name = wf.STEP_BY_KEY[run.step_key]["name"]
            if run.reminder_level < 1:
                _notify(db, p, _owner_ids(db, p, run), f"Overdue: {p.title} · {name}", now, "remind")
                run.reminder_level, reminded = 1, reminded + 1
            if run.reminder_level < 2 and late >= sla:
                bosses = [db.get(User, uid).manager_id for uid in _owner_ids(db, p, run)]
                bosses = [b for b in bosses if b] or _director_ids(db)
                _notify(db, p, bosses, f"Escalation: {p.title} has waited {(now - run.entered_at).days} days at {name}",
                        now, "escalate")
                run.reminder_level, escalated = 2, escalated + 1
        for t in p.tasks:
            if t.status == "open" and now > t.due_at and t.reminder_level < 1:
                _notify(db, p, [t.assignee_id], f"Overdue task: {t.title} ({p.title})", now, "remind")
                _notify(db, p, [t.creator_id], f"{t.assignee.name} is late on the task “{t.title}” ({p.title})", now, "escalate")
                t.reminder_level, reminded = 1, reminded + 1
        for r in p.requests:
            if r.status == "pending" and not r.reminded and now - r.created_at > timedelta(days=2):
                _notify(db, p, [r.approver_id], f"Waiting for your answer: {r.requested_by.name} asked for more time "
                        f"({p.title})", now, "request")
                r.reminded = True
    db.commit()
    return {"reminded": reminded, "escalated": escalated}
