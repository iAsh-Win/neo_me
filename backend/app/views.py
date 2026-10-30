"""Turns database rows into the plain dicts the screens show. Everything here is already limited to what the
signed-in person is allowed to see."""
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import engine as eng
from . import workflow as wf
from .models import Event, Project, Task, User


def iso(dt):
    return dt.isoformat() + "Z" if dt else None


def directory(db: Session) -> dict:
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


def _owner_chips(p: Project, roles: list, dirx: dict, signed=()) -> list:
    return [{"role": r, "short": wf.ROLES[r]["short"], "label": wf.ROLES[r]["label"],
             "people": [p.initiator.name] if r == "initiator" else dirx.get(r, []), "signed": r in signed}
            for r in roles]


def _days_to(dt: datetime, now: datetime) -> int:
    return int((dt - now).total_seconds() // 86400)


def _doc(d, uses=None, tasks=None) -> dict:
    step = wf.STEP_BY_KEY.get(d.step_key)
    slot = next((x for x in (step or {}).get("docs", []) if x["key"] == d.doc_type), None)
    src = d.source_id or d.id
    return {"id": d.id, "kind": d.kind, "title": d.title, "url": d.url, "filename": d.filename, "size": d.size,
            "has_file": bool(d.stored_name), "step_key": d.step_key, "step_name": step["name"] if step else "",
            "doc_type": d.doc_type, "doc_label": slot["label"] if slot else "", "task_id": d.task_id,
            "task_title": (tasks or {}).get(d.task_id, ""), "important": d.important or bool(slot and slot["required"]),
            "pinned": d.important, "source_id": d.source_id, "original_id": src,
            "used_in": (uses or {}).get(d.id, []), "user": user_brief(d.user), "at": iso(d.created_at)}


def _health(p: Project, actives: list, now: datetime) -> str:
    if p.status == "completed":
        return "done"
    if p.status == "on_hold":
        return "hold"
    if p.status in ("rejected", "cancelled"):
        return "stopped"
    if any(r.due_at < now for r in actives):
        return "late"
    if any(r.due_at - now < timedelta(days=1) for r in actives) or \
            any(q.status == "pending" for q in p.requests):
        return "risk"
    return "ok"


def summary(p: Project, user: User, dirx: dict) -> dict:
    now = datetime.utcnow()
    order = wf.flat_order(p.ptype)
    actives = eng.active_runs(p)
    scored = [k for k in order if k != "clarification"]
    done_n = sum(1 for k in scored if eng.step_done(p, k))
    if actives:
        main = min(actives, key=lambda r: order.index(r.step_key))
        phase = wf.STEP_BY_KEY[main.step_key]["phase"]
    else:
        last = next((r for r in reversed(p.runs) if r.status == "done"), None)
        phase = wf.STEP_BY_KEY[last.step_key]["phase"] if last else wf.PHASES[0]["key"]
    items = []
    for r in actives:
        step = wf.STEP_BY_KEY[r.step_key]
        d = _days_to(r.due_at, now)
        items.append({"run_id": r.id, "step_key": r.step_key, "step_name": step["name"], "mode": step["mode"],
                      "due_days": d, "overdue": d < 0, "can_act": eng.can_act_run(p, r, user),
                      "owners": run_chips(p, r, dirx), "rework": r.kind == "rework"})
    seen, waiting = set(), []
    for it in items:
        for o in it["owners"]:
            if o["role"] not in seen:
                seen.add(o["role"])
                waiting.append(o)
    notes = [e for e in p.events if e.kind == "comment"]
    ln = notes[-1] if notes else None
    due_days = min((i["due_days"] for i in items), default=None)
    return {
        "id": p.id, "code": p.code, "title": p.title, "ptype": p.ptype, "ptype_label": wf.PROJECT_TYPES[p.ptype],
        "market": p.market, "status": p.status, "status_note": p.status_note, "health": _health(p, actives, now),
        "phase": phase, "phase_name": wf.PHASE_BY_KEY[phase]["name"],
        "phase_no": [x["key"] for x in wf.PHASES].index(phase) + 1,
        "progress": 100 if p.status == "completed" else round(done_n / len(scored) * 100),
        "steps_done": done_n, "steps_total": len(scored),
        "active": items, "step_name": " + ".join(i["step_name"] for i in items) or wf.STEP_BY_KEY["completion"]["name"],
        "mode": items[0]["mode"] if items else "action",
        "waiting": waiting, "can_act": any(i["can_act"] for i in items),
        "due_days": due_days, "overdue": any(i["overdue"] for i in items),
        "days_in_step": max((max(0, (now - r.entered_at).days) for r in actives), default=0),
        "initiator": user_brief(p.initiator), "est_value": p.est_value, "manufacturer": p.manufacturer,
        "target_date": p.target_date, "fast_track": p.fast_track,
        "tasks_open": sum(1 for t in p.tasks if t.status == "open"),
        "requests_pending": sum(1 for q in p.requests if q.status == "pending"),
        "latest_note": {"text": ln.note, "user": user_brief(ln.user), "at": iso(ln.created_at)} if ln else None,
        "clarification_pending": p.clarification_pending,
        "created_at": iso(p.created_at), "updated_at": iso(p.updated_at),
    }


_RESULT = {"done": "Done", "signoff": "Signed", "approve": "Approved", "sendback": "Sent back", "hold": "On hold",
           "reject": "Rejected"}
# The moments a reviewer cares about. Everything else is routine hand-overs, notes and files.
KEY_ACTIONS = {"approve", "sendback", "hold", "resume", "reject", "cancel", "moved", "fasttrack", "ext_yes", "ext_no"}


def run_chips(p: Project, run, dirx: dict) -> list:
    """Who a waiting step is with: the chosen person, or everyone in the role."""
    chips = _owner_chips(p, eng.waiting_roles(p, run), dirx, eng.signed_roles(p, run))
    if run.assignee_id and run.assignee:
        role = run.assignee.role
        return [{"role": role, "short": wf.ROLES[role]["short"], "label": wf.ROLES[role]["label"],
                 "people": [run.assignee.name], "signed": False, "chosen": True}]
    return chips


def _event(e: Event, docs_by_id: dict) -> dict:
    step = wf.STEP_BY_KEY.get(e.step_key)
    opt = (step or {}).get("options", {}).get(e.option) if e.option else None
    meta = e.meta or {}
    return {
        "id": e.id, "kind": e.kind, "action": e.action, "step_key": e.step_key,
        "step_name": step["name"] if step else "", "option": e.option, "option_label": opt["label"] if opt else "",
        "result": _RESULT.get(e.action, e.action), "role": e.role,
        "role_label": wf.ROLES[e.role]["label"] if e.role in wf.ROLES else "",
        "user": user_brief(e.user), "note": e.note, "to": e.to_text, "at": iso(e.created_at),
        "data": meta.get("data") or [], "checks": meta.get("checks") or [],
        "docs": [docs_by_id[i] for i in meta.get("docs") or [] if i in docs_by_id],
        "target_name": meta.get("target_name"), "chart": meta.get("chart"),
        "old": meta.get("old"), "new": meta.get("new"), "label": meta.get("label") or meta.get("title"),
        "doc": docs_by_id.get(meta.get("doc_id")) if meta.get("doc_id") else None,
        "doc_kind": meta.get("kind"), "doc_label": meta.get("doc_label"), "due": meta.get("due"),
        "run_id": e.run_id, "key": e.action in KEY_ACTIONS, "task": meta.get("task"), "reuse": meta.get("reuse"),
        "target": meta.get("target"),
    }


def _request(r, user) -> dict:
    return {"id": r.id, "kind": r.kind, "run_id": r.run_id, "task_id": r.task_id, "status": r.status,
            "requested_by": user_brief(r.requested_by), "approver": user_brief(r.approver),
            "old_due": iso(r.old_due), "new_due": iso(r.new_due), "reason": r.reason, "at": iso(r.created_at),
            "can_decide": r.status == "pending" and user.id != r.requested_by_id
            and (user.id == r.approver_id or user.role in eng.DIRECTORS)}


def _task(t: Task, p: Project, user: User, now: datetime, db=None, docs_by_id=None) -> dict:
    pend = next((r for r in p.requests if r.task_id == t.id and r.status == "pending"), None)
    return {"id": t.id, "title": t.title, "details": t.details, "status": t.status, "blocking": t.blocking,
            "step_key": t.step_key, "step_name": wf.STEP_BY_KEY[t.step_key]["name"] if t.step_key else "",
            "assignee": user_brief(t.assignee), "creator": user_brief(t.creator), "due_at": iso(t.due_at),
            "due_days": _days_to(t.due_at, now) if t.status == "open" else None,
            "overdue": t.status == "open" and t.due_at < now, "done_note": t.done_note,
            "completed_at": iso(t.completed_at), "created_at": iso(t.created_at),
            "docs": [d for d in (docs_by_id or {}).values() if d["task_id"] == t.id],
            "can_complete": t.status == "open" and t.assignee_id == user.id,
            "can_request": t.status == "open" and t.assignee_id == user.id and pend is None,
            "can_cancel": t.status == "open" and (user.id == t.creator_id or user.role in eng.DIRECTORS or user.role == "admin"),
            "pending_request": _request(pend, user) if pend else None,
            "request_to": _brief_approver(db, user, t.creator_id) if db is not None and t.assignee_id == user.id else None}


def _brief_approver(db, user, assigner_id):
    a = eng._approver_for(db, user, assigner_id)
    return user_brief(a) if a else None


def _handover(run, docs_by_id) -> dict | None:
    """What the person before sent along: their message, details, ticks and documents."""
    h = run.handover or {}
    if not h:
        return None
    return {**h, "docs": [docs_by_id[i] for i in h.get("docs", []) if i in docs_by_id], "at": iso(run.entered_at),
            "has_content": bool(h.get("note") or h.get("data") or h.get("checks") or h.get("docs"))}


def _action_card(db, p, run, user, dirx, docs_by_step, now, docs_by_id=None):
    docs_by_id = docs_by_id or {}
    step = wf.STEP_BY_KEY[run.step_key]
    signed = eng.signed_roles(p, run)
    can = eng.can_act_run(p, run, user)
    my_role = next((r for r in wf.actor_roles(step) if eng._role_matches(p, user, r)), None) if can else None
    attached = docs_by_step.get(run.step_key, [])
    pend = next((q for q in p.requests if q.run_id == run.id and q.status == "pending"), None)
    prefill = {}
    for f in step.get("fields", []):
        if f.get("maps") == "est_value" and p.est_value:
            prefill[f["key"]] = str(int(p.est_value) if float(p.est_value).is_integer() else p.est_value)
        elif f.get("maps") in ("target_date", "manufacturer") and getattr(p, f["maps"]):
            prefill[f["key"]] = getattr(p, f["maps"])
    nexts = {}
    if step["mode"] == "decision":
        for k, o in step["options"].items():
            if o["kind"] in ("approve", "back"):
                nexts[k] = eng.preview_next(db, p, run, k) if o["kind"] == "approve" else None
    else:
        nexts["done"] = eng.preview_next(db, p, run)
    d = _days_to(run.due_at, now)
    return {
        "run_id": run.id, "key": step["key"], "name": step["name"], "mode": step["mode"],
        "rework": run.kind == "rework", "round": run.seq, "can_act": can,
        "from": {**user_brief(run.from_user), "note": run.from_note, "at": iso(run.entered_at)} if run.from_user else None,
        "return_to_name": wf.STEP_BY_KEY[run.return_to]["name"] if run.return_to else None,
        "return_to_user": user_brief(run.return_user) if run.return_user_id else None,
        "due_at": iso(run.due_at), "due_days": d, "overdue": d < 0, "sla": wf.sla_days(step["key"]),
        "button": step.get("button") or "Done", "all": bool(step.get("all")),
        "owners": (run_chips(p, run, dirx) if run.assignee_id else _owner_chips(p, step["roles"], dirx, signed)),
        "assignee": user_brief(run.assignee) if run.assignee_id else None,
        "handover": _handover(run, docs_by_id),
        "assign_options": [user_brief(u) for u in eng.people_for_roles(db, p, step["roles"])]
        if eng.can_pick_person(step) else [],
        "can_assign": p.status == "active" and eng.can_pick_person(step) and (
            user.id == run.from_user_id or can or user.role in eng.DIRECTORS or user.role == "admin"),
        "consult": wf.ROLES[step["consult"]]["short"] if step.get("consult") else None,
        "coordinator": wf.ROLES[step["coordinator"]]["short"] if step.get("coordinator") else None,
        "docs": [{**dd, "items": [x for x in attached if x["doc_type"] == dd["key"]],
                  "role_short": wf.ROLES[dd["role"]]["short"] if dd.get("role") else None,
                  "editable": can and dd.get("role") in (None, my_role)} for dd in step.get("docs", [])],
        "other_docs": [x for x in attached if not any(x["doc_type"] == dd["key"] for dd in step.get("docs", []))],
        "fields": [{**f, "value": prefill.get(f["key"], "")} for f in step.get("fields", [])],
        "checks": [c for c in step.get("checks", []) if my_role is None or c["role"] in (None, my_role)],
        "options": [{"key": k, "label": v["label"], "short": v.get("short"), "kind": v["kind"], "note": bool(v.get("note")),
                     "to": v.get("to"), "to_name": wf.STEP_BY_KEY[v["to"]]["name"] if v.get("to") else None}
                    for k, v in step.get("options", {}).items()],
        "next": nexts,
        "request_to": _brief_approver(db, user, run.from_user_id) if can else None,
        "targets": eng.send_back_targets(db, p, run) if can else [],
        "blockers": [t.title for t in eng._blocking_tasks(p, run)],
        "pending_request": _request(pend, user) if pend else None,
        "can_set_due": user.id == run.from_user_id or user.role in eng.DIRECTORS or user.role == "admin",
        "can_nudge": p.status == "active" and not can,
    }


def _is_full(p: Project, user: User) -> bool:
    """Owner (the project's initiator), Directors, the Office Admin and managers of the people working on it
    see everything on a project."""
    return user.role == "admin" or user.role in eng.DIRECTORS or p.initiator_id == user.id         or eng.is_manager_of_involved(p, user)


def _my_steps(p: Project, user: User) -> tuple:
    """Steps this person works on (or worked on, or handed over) and the documents handed to them."""
    steps, handed = set(), set()
    for r in p.runs:
        mine = r.completed_by_id == user.id or r.from_user_id == user.id or r.assignee_id == user.id
        if r.status == "active" and eng.can_act_run(p, r, user):
            mine = True
        if mine:
            steps.add(r.step_key)
            h = r.handover or {}
            if h.get("step_key") and r.status == "active":
                steps.add(h["step_key"])
            handed.update(h.get("docs", []))
    for e in p.events:
        if e.user_id == user.id and e.step_key:
            steps.add(e.step_key)
    return steps, handed


def doc_visible(p: Project, user: User, d) -> bool:
    if _is_full(p, user) or d.user_id == user.id:
        return True
    steps, handed = _my_steps(p, user)
    if d.id in handed:
        return True
    if d.task_id:
        return any(t.id == d.task_id and (t.assignee_id == user.id or t.creator_id == user.id) for t in p.tasks)
    return not d.step_key or d.step_key in steps


def _brief(p: Project, order: list, rows: list, events: list, now: datetime, dirx: dict, docs: list) -> dict:
    """The short version for someone who just wants to know where things stand."""
    stages = []
    by_key = {r["key"]: r for r in rows}
    for ph in wf.PHASES:
        keys = [k for k in order if wf.STEP_BY_KEY[k]["phase"] == ph["key"] and k != "clarification"]
        if not keys:
            continue
        done = [k for k in keys if by_key[k]["state"] == "done"]
        active = [k for k in keys if by_key[k]["state"] in ("current", "hold", "stopped")]
        runs = [r for r in p.runs if r.step_key in keys]
        ends = [r.completed_at for r in runs if r.completed_at and r.status == "done"]
        state = "done" if len(done) == len(keys) else "now" if active or done else "later"
        if state == "done" and not active:
            state = "done"
        started = min((r.entered_at for r in runs), default=None)
        finished = max(ends) if state == "done" and ends else None
        last = next((e for e in reversed(events) if e["kind"] == "step" and e["step_key"] in keys
                     and e["action"] in ("done", "approve")), None)
        stages.append({
            "key": ph["key"], "name": ph["name"], "color": ph["color"], "state": state,
            "steps_done": len(done), "steps_total": len(keys),
            "started": iso(started), "finished": iso(finished),
            "days": (((finished or now) - started).days if started else None),
            "sendbacks": sum(1 for e in events if e["action"] == "sendback" and e["step_key"] in keys),
            "now": [{"name": wf.STEP_BY_KEY[k]["name"], "people": [n for ch in by_key[k]["owners"] for n in ch["people"]]}
                    for k in active],
            "last": {"name": last["user"]["name"] if last["user"] else "", "step": last["step_name"], "at": last["at"]}
            if last and state == "done" else None,
        })
    attention = []
    for r in eng.active_runs(p):
        step = wf.STEP_BY_KEY[r.step_key]
        who = ", ".join(n for ch in run_chips(p, r, dirx) for n in ch["people"]) or "—"
        d = _days_to(r.due_at, now)
        if r.kind == "rework":
            attention.append({"tone": "bad", "step_key": r.step_key,
                              "text": f"{step['name']} was sent back by {r.from_user.name if r.from_user else 'someone'}"
                                      f"{(': ' + r.from_note) if r.from_note else ''} – now with {who}."})
        if d < 0:
            attention.append({"tone": "bad", "step_key": r.step_key,
                              "text": f"{step['name']} is {-d} day{'s' if d != -1 else ''} late – with {who}."})
    for q in p.requests:
        if q.status == "pending":
            attention.append({"tone": "warn", "text": f"{q.requested_by.name} asks for more time until {q.new_due:%d %b}"
                                                      f" – waiting for {q.approver.name}."})
    for t in p.tasks:
        if t.status == "open" and (t.blocking or t.due_at < now):
            attention.append({"tone": "warn" if not t.due_at < now else "bad",
                              "text": f"Task “{t.title}” ({t.assignee.name})" + (" is late" if t.due_at < now else "")
                                      + (" and blocks a step" if t.blocking else "") + "."})
    if p.status == "on_hold":
        attention.append({"tone": "warn", "text": f"On hold: {p.status_note}"})
    if p.status in ("rejected", "cancelled"):
        attention.append({"tone": "bad", "text": f"{p.status.capitalize()}: {p.status_note}"})
    counts = {"sendbacks": sum(1 for e in events if e["action"] == "sendback"),
              "holds": sum(1 for e in events if e["action"] == "hold"),
              "extensions": sum(1 for e in events if e["action"] == "ext_yes"),
              "days": max(0, ((p.updated_at if p.status in ("completed", "rejected", "cancelled") else now) - p.created_at).days)}
    return {"stages": stages, "attention": attention, "counts": counts, "key_docs": [d for d in docs if d["important"]
            and not d["source_id"]][:12]}


def detail(db: Session, p: Project, user: User) -> dict:
    now = datetime.utcnow()
    dirx = directory(db)
    base = summary(p, user, dirx)
    order = wf.flat_order(p.ptype)
    full = _is_full(p, user)
    steps_mine, handed = (None, set()) if full else _my_steps(p, user)
    my_tasks = {t.id for t in p.tasks if full or t.assignee_id == user.id or t.creator_id == user.id}
    my_reqs = {r.id for r in p.requests if full or r.requested_by_id == user.id or r.approver_id == user.id}

    def doc_ok(d) -> bool:
        if full or d.user_id == user.id or d.id in handed:
            return True
        if d.task_id:
            return d.task_id in my_tasks
        return not d.step_key or d.step_key in steps_mine

    vis = [d for d in p.documents if doc_ok(d)]
    uses: dict = {}
    task_titles = {t.id: t.title for t in p.tasks}
    for d in p.documents:
        if d.source_id:
            step = wf.STEP_BY_KEY.get(d.step_key)
            uses.setdefault(d.source_id, []).append(step["name"] if step else task_titles.get(d.task_id, "Task"))
    docs_all = [_doc(d, uses, task_titles) for d in vis]
    docs_by_id = {d["id"]: d for d in docs_all}
    docs_by_step: dict = {}
    for d in docs_all:
        docs_by_step.setdefault(d["step_key"], []).append(d)

    def ev_ok(e) -> bool:
        if full or e.user_id == user.id or e.kind == "comment":
            return True
        m = e.meta or {}
        if e.kind in ("step", "doc") and e.step_key in steps_mine:
            return True
        if e.action == "sendback" and m.get("target") in steps_mine:
            return True
        if m.get("task_id") in my_tasks or m.get("request_id") in my_reqs:
            return True
        return e.kind == "system" and e.action in ("hold", "resume", "cancel", "fasttrack")

    events = [_event(e, docs_by_id) for e in p.events if ev_ok(e)]
    by_step: dict = {}
    for e in events:
        if e["step_key"]:
            by_step.setdefault(e["step_key"], []).append(e)
    actives = {r.step_key: r for r in eng.active_runs(p)}

    rows = []
    for i, k in enumerate(order):
        s = wf.STEP_BY_KEY[k]
        lr = eng.latest_run(p, k)
        mine_step = full or k in steps_mine
        evs = by_step.get(k, []) if mine_step else []
        results = [e for e in evs if e["kind"] == "step" and e["action"] in ("done", "approve", "sendback", "hold", "reject")]
        last_done = next((e for e in reversed(results) if e["action"] in ("done", "approve")), None)
        if k in actives:
            state = {"active": "current", "on_hold": "hold"}.get(p.status, "stopped")
        elif lr and lr.status == "done":
            state = "done"
        elif lr:
            state = "upcoming"
        elif any(eng.latest_run(p, later) for later in order[i + 1:]) or p.status == "completed":
            state = "skipped"
        else:
            state = "upcoming"
        gi = wf.group_of(k)
        rows.append({
            "key": k, "name": s["name"], "phase": s["phase"], "mode": s["mode"], "only": s.get("only"),
            "all": bool(s.get("all")),
            "owners": (run_chips(p, actives[k], dirx) if k in actives and actives[k].assignee_id else
                       _owner_chips(p, s["roles"], dirx, eng.signed_roles(p, actives[k]) if k in actives else ())),
            "coordinator": wf.ROLES[s["coordinator"]]["short"] if s.get("coordinator") else None,
            "group": gi[0] if gi else None, "track": gi[1] if gi else None, "state": state,
            "runs": sum(1 for r in p.runs if r.step_key == k), "sent_back": sum(1 for e in results if e["action"] == "sendback"),
            "last": last_done, "events": evs, "mine": mine_step,
            "due_at": iso(actives[k].due_at) if k in actives else None,
            "due_days": _days_to(actives[k].due_at, now) if k in actives else None,
            "docs": docs_by_step.get(k, []) if mine_step else [],
        })
    groups = []
    for gid, g in wf.GROUPS.items():
        groups.append({"id": gid, "name": g["name"], "why": g["why"], "mode": p.group_mode.get(gid),
                       "tracks": [{"name": t["name"], "steps": t["steps"]} for t in g["tracks"]]})
    actions = [_action_card(db, p, r, user, dirx, docs_by_step, now, docs_by_id) for r in eng.active_runs(p)]
    actions.sort(key=lambda a: (not a["can_act"], order.index(a["key"])))
    is_dir = user.role in eng.DIRECTORS
    base.update({
        "scope": "full" if full else "focus",
        "description": p.description, "actions": actions, "steps": rows, "groups": groups, "events": events,
        "documents": docs_all, "tasks": [_task(t, p, user, now, db, docs_by_id) for t in p.tasks if t.id in my_tasks],
        "requests": [_request(r, user) for r in p.requests if r.id in my_reqs],
        "brief": _brief(p, order, rows, events, now, dirx, docs_all) if full else None,
        "permissions": {
            "hold": is_dir and p.status == "active", "resume": is_dir and p.status == "on_hold",
            "cancel": is_dir and p.status in ("active", "on_hold"),
            "edit": user.role == "admin" or user.id == p.initiator_id, "move": user.role == "admin",
            "fast_track": is_dir and p.status in ("active", "on_hold"),
            "add_task": p.status in ("active", "on_hold") and (user.role == "admin" or is_dir or user.id == p.initiator_id
                                                                 or bool(eng.acting_runs(p, user))),
            "upload": True,
            "mark_key": full,
        },
        "step_options": [{"key": k, "name": wf.STEP_BY_KEY[k]["name"]} for k in order],
        "doc_types": {s["key"]: s.get("docs", []) for s in wf.STEPS if s.get("docs")},
    })
    return base


def dashboard(db: Session, user: User) -> dict:
    now = datetime.utcnow()
    dirx = directory(db)
    projects = visible_projects(db, user)
    sums = {p.id: summary(p, user, dirx) for p in projects}
    mine = []
    for p in projects:
        s = sums[p.id]
        for a in s["active"]:
            if a["can_act"]:
                mine.append({"type": "step", "project_id": p.id, "title": p.title, "phase": s["phase"], "label": a["step_name"],
                             "mode": a["mode"], "due_days": a["due_days"], "overdue": a["overdue"], "rework": a["rework"],
                             "key": f"r{a['run_id']}"})
        for t in p.tasks:
            if t.status == "open" and t.assignee_id == user.id:
                d = _days_to(t.due_at, now)
                mine.append({"type": "task", "project_id": p.id, "title": p.title, "phase": s["phase"], "label": t.title,
                             "mode": "task", "due_days": d, "overdue": d < 0, "from": t.creator.name, "key": f"t{t.id}"})
        for r in p.requests:
            if r.status == "pending" and r.approver_id == user.id:
                mine.append({"type": "request", "project_id": p.id, "title": p.title, "phase": s["phase"],
                             "label": f"{r.requested_by.name} asks for more time", "mode": "request",
                             "due_days": None, "overdue": False, "from": r.requested_by.name, "key": f"q{r.id}"})
    mine.sort(key=lambda m: (m["due_days"] is None, m["due_days"] if m["due_days"] is not None else 0))
    mine_ids = {m["project_id"] for m in mine}
    others = [s for pid, s in sums.items() if pid not in mine_ids and s["status"] in ("active", "on_hold")]
    oversight = user.role == "admin" or user.role in eng.DIRECTORS
    out = {
        "view": "admin" if user.role == "admin" else "director" if user.role in eng.DIRECTORS else "staff",
        "mine": mine, "following": others,
        "counts": {
            "waiting_me": len(mine),
            "active": sum(s["status"] == "active" for s in sums.values()),
            "on_hold": sum(s["status"] == "on_hold" for s in sums.values()),
            "completed": sum(s["status"] == "completed" for s in sums.values()),
            "overdue": sum(bool(s["overdue"]) for s in sums.values()),
        },
    }
    if oversight:
        pipeline = {ph["key"]: 0 for ph in wf.PHASES}
        for s in sums.values():
            if s["status"] in ("active", "on_hold"):
                pipeline[s["phase"]] += 1
        out["pipeline"] = [{**ph, "count": pipeline[ph["key"]]} for ph in wf.PHASES]
        out["overdue"] = sorted([s for s in sums.values() if s["overdue"]], key=lambda s: s["due_days"])
    return out
