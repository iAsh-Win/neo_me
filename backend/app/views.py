"""Turns database rows into the plain dicts the UI shows. Every list here is already limited to what the
signed-in person is allowed to see."""
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import engine as eng
from . import workflow as wf
from .models import Event, Project, User


def iso(dt):
    return dt.isoformat() + "Z" if dt else None


def directory(db: Session) -> dict:
    """role -> active people holding it."""
    out: dict = {}
    for u in db.scalars(select(User).where(User.active == True).order_by(User.name)):  # noqa: E712
        out.setdefault(u.role, []).append(u.name)
    return out


def user_brief(u: User | None):
    return {"id": u.id, "name": u.name, "role": u.role, "role_label": wf.ROLES[u.role]["label"],
            "short": wf.ROLES[u.role]["short"], "title": u.title} if u else None


def user_full(u: User):
    return {**user_brief(u), "email": u.email, "active": u.active, "org": wf.ROLES[u.role]["org"],
            "manager_id": u.manager_id, "last_login": iso(u.last_login)}


def visible_projects(db: Session, user: User) -> list:
    rows = db.scalars(select(Project).order_by(Project.updated_at.desc())).all()
    return [p for p in rows if eng.can_see(p, user)]


def _owner_chips(p: Project, roles: list, dirx: dict) -> list:
    return [{"role": r, "short": wf.ROLES[r]["short"], "label": wf.ROLES[r]["label"],
             "people": [p.initiator.name] if r == "initiator" else dirx.get(r, [])} for r in roles]


def summary(p: Project, user: User, dirx: dict) -> dict:
    steps = wf.steps_for(p.ptype)
    keys = [s["key"] for s in steps]
    idx = keys.index(p.current_step)
    step = wf.STEP_BY_KEY[p.current_step]
    now = datetime.utcnow()
    due_days = None
    if p.status == "active":
        secs = (eng.due_at(p) - now).total_seconds()
        due_days = int(secs // 86400)          # negative = days late
    return {
        "id": p.id, "code": p.code, "title": p.title, "ptype": p.ptype,
        "ptype_label": wf.PROJECT_TYPES[p.ptype], "market": p.market, "status": p.status,
        "status_note": p.status_note, "current_step": p.current_step, "step_name": step["name"],
        "mode": step["mode"], "phase": step["phase"], "phase_name": wf.PHASE_BY_KEY[step["phase"]]["name"],
        "phase_no": [ph["key"] for ph in wf.PHASES].index(step["phase"]) + 1,
        "step_no": idx + 1, "step_total": len(keys),
        "progress": 100 if p.status == "completed" else round(idx / len(keys) * 100),
        "waiting": _owner_chips(p, eng.waiting_roles(p), dirx),
        "days_in_step": max(0, (now - p.step_entered_at).days),
        "due_days": due_days, "overdue": due_days is not None and due_days < 0,
        "initiator": user_brief(p.initiator), "est_value": p.est_value, "manufacturer": p.manufacturer,
        "target_date": p.target_date, "can_act": eng.can_act(p, user),
        "clarification_pending": p.clarification_pending,
        "created_at": iso(p.created_at), "updated_at": iso(p.updated_at),
    }


_RESULT = {"done": "Done", "signoff": "Signed", "approve": "Approved", "back": "Sent back",
           "hold": "On hold", "reject": "Rejected"}


def _event(e: Event) -> dict:
    step = wf.STEP_BY_KEY.get(e.step_key)
    opt = (step or {}).get("options", {}).get(e.option) if e.option else None
    return {
        "id": e.id, "kind": e.kind, "action": e.action, "step_key": e.step_key,
        "step_name": step["name"] if step else "", "option": e.option,
        "option_label": opt["label"] if opt else "", "result": _RESULT.get(e.action, e.action),
        "role": e.role, "role_label": wf.ROLES[e.role]["label"] if e.role in wf.ROLES else "",
        "user": user_brief(e.user), "note": e.note, "at": iso(e.created_at),
    }


def detail(db: Session, p: Project, user: User) -> dict:
    dirx = directory(db)
    base = summary(p, user, dirx)
    steps = wf.steps_for(p.ptype)
    keys = [s["key"] for s in steps]
    cur = keys.index(p.current_step)
    events = [_event(e) for e in p.events]
    step_events: dict = {}
    for e in events:
        if e["kind"] == "step":
            step_events.setdefault(e["step_key"], []).append(e)

    rows = []
    for i, s in enumerate(steps):
        evs = step_events.get(s["key"], [])
        results = [e for e in evs if e["action"] != "signoff"]
        last = results[-1] if results else (evs[-1] if evs else None)
        if p.status == "completed":
            state = "done"
        elif i < cur:
            state = "done" if evs else "skipped"
        elif i == cur:
            state = {"active": "current", "on_hold": "hold"}.get(p.status, "stopped")
        else:
            state = "upcoming"
        rows.append({
            "key": s["key"], "name": s["name"], "phase": s["phase"], "mode": s["mode"],
            "owners": _owner_chips(p, s["roles"], dirx), "all": bool(s.get("all")),
            "coordinator": wf.ROLES[s["coordinator"]]["short"] if s.get("coordinator") else None,
            "only": s.get("only"), "state": state, "last": last,
            "attempts": len([e for e in results if e["action"] in ("done", "approve")]),
            "sent_back": len([e for e in results if e["action"] == "back"]),
            "options": [{"key": k, "kind": v["kind"], "label": v["label"],
                         "to_name": wf.STEP_BY_KEY[v["to"]]["name"] if v.get("to") else None}
                        for k, v in s.get("options", {}).items()],
        })

    step = wf.STEP_BY_KEY[p.current_step]
    signed = eng.signed_roles(p)
    action = {
        "key": step["key"], "name": step["name"], "mode": step["mode"], "hint": step.get("hint"),
        "button": step.get("button") or "Done", "all": bool(step.get("all")),
        "owners": _owner_chips(p, step["roles"], dirx),
        "signed": [r for r in step["roles"] if r in signed],
        "consult": wf.ROLES[step["consult"]]["short"] if step.get("consult") else None,
        "coordinator": wf.ROLES[step["coordinator"]]["short"] if step.get("coordinator") else None,
        "needs_note": step.get("needs_note"), "needs_file": step.get("needs_file"),
        "has_file": any(d.step_key == step["key"] for d in p.documents),
        "needs_text": step["needs_text"][1] if step.get("needs_text") else None,
        "options": [{"key": k, "label": v["label"], "short": v.get("short"), "kind": v["kind"],
                     "note": bool(v.get("note")),
                     "to_name": wf.STEP_BY_KEY[v["to"]]["name"] if v.get("to") else None}
                    for k, v in step.get("options", {}).items()],
        "can_act": base["can_act"],
        "sla": wf.sla_days(step["key"]),
    }
    is_dir = user.role in eng.DIRECTORS
    base.update({
        "description": p.description, "action": action, "steps": rows, "events": events,
        "documents": [{"id": d.id, "filename": d.filename, "size": d.size, "step_key": d.step_key,
                       "step_name": wf.STEP_BY_KEY[d.step_key]["name"] if d.step_key in wf.STEP_BY_KEY else "",
                       "user": user_brief(d.user), "at": iso(d.created_at)} for d in p.documents],
        "permissions": {
            "hold": is_dir and p.status == "active",
            "resume": is_dir and p.status == "on_hold",
            "cancel": is_dir and p.status in ("active", "on_hold"),
            "edit": user.role == "admin" or user.id == p.initiator_id,
            "move": user.role == "admin",
            "nudge": p.status == "active" and not base["can_act"],
        },
        "step_options": [{"key": s["key"], "name": s["name"]} for s in steps],
    })
    return base


def dashboard(db: Session, user: User) -> dict:
    dirx = directory(db)
    mine_all = visible_projects(db, user)
    sums = [summary(p, user, dirx) for p in mine_all]
    oversight = user.role == "admin" or user.role in eng.DIRECTORS
    mine = sorted([s for s in sums if s["can_act"]], key=lambda s: (s["due_days"] if s["due_days"] is not None else 99))
    others = [s for s in sums if not s["can_act"] and s["status"] in ("active", "on_hold")]
    out = {
        "view": "admin" if user.role == "admin" else "director" if user.role in eng.DIRECTORS else "staff",
        "mine": mine,
        "following": others,
        "counts": {
            "waiting_me": len(mine),
            "active": sum(s["status"] == "active" for s in sums),
            "on_hold": sum(s["status"] == "on_hold" for s in sums),
            "completed": sum(s["status"] == "completed" for s in sums),
            "overdue": sum(bool(s["overdue"]) for s in sums),
        },
    }
    if oversight:
        pipeline = {ph["key"]: 0 for ph in wf.PHASES}
        for s in sums:
            if s["status"] in ("active", "on_hold"):
                pipeline[s["phase"]] += 1
        out["pipeline"] = [{**ph, "count": pipeline[ph["key"]]} for ph in wf.PHASES]
        out["overdue"] = sorted([s for s in sums if s["overdue"]], key=lambda s: s["due_days"])
    return out
