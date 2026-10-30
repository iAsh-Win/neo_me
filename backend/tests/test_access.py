"""Who can see what, hierarchy, notifications, reminders, e-mail and account security."""
from datetime import datetime, timedelta

from app import engine as eng
from app import mailer
from app.db import SessionLocal
from app.models import Notification, Project, StepRun

from conftest import tomorrow
from test_flow import run_to


def ids(resp):
    return {p["id"] for p in resp.json()}


# ---- visibility ------------------------------------------------------------------
def test_people_only_see_projects_they_work_on(api):
    a = api.create("ananya", title="Ananya project")
    b = api.create("rohit", title="Rohit project")
    assert ids(api.get("ananya", "/api/projects")) == {a}
    assert ids(api.get("rohit", "/api/projects")) == {b}
    for who in ("rajiv", "suresh", "sneha"):                      # Directors and the Office Admin see everything
        assert ids(api.get(who, "/api/projects")) == {a, b}
    assert ids(api.get("pooja", "/api/projects")) == set()
    assert api.get("pooja", f"/api/projects/{a}").status_code == 404
    assert api.get("rohit", f"/api/projects/{a}").status_code == 404
    assert api.get("pooja", "/api/dashboard").json()["mine"] == []


def test_project_appears_when_it_reaches_a_team_and_stays_after(api):
    pid = api.create()
    run_to(api, pid, "agreement_prep")
    for who in ("pooja", "amit", "neha"):                         # Legal / Quality / PV are now responsible
        assert pid in ids(api.get(who, "/api/projects"))
        assert api.get(who, "/api/dashboard").json()["counts"]["waiting_me"] == 1
    assert pid not in ids(api.get("sanjay", "/api/projects"))     # Regulatory Head: not yet
    run_to(api, pid, "handover")
    assert pid in ids(api.get("sanjay", "/api/projects"))
    assert pid in ids(api.get("pooja", "/api/projects"))          # has worked on it → keeps access
    assert pid not in ids(api.get("ritika", "/api/projects"))     # Artwork Team: not yet


def test_files_follow_the_same_rule(api):
    pid = api.create()
    doc = api.file("ananya", pid, "screening", "")[0]
    assert api.get("ananya", f"/api/documents/{doc}").status_code == 200
    assert api.get("pooja", f"/api/documents/{doc}").status_code == 404
    assert api.post("pooja", f"/api/projects/{pid}/comments", json={"note": "hi"}).status_code == 404
    assert api.post("pooja", f"/api/projects/{pid}/links", json={"title": "x", "url": "https://x.test"}).status_code == 404


def test_notifications_are_private_and_only_for_the_right_people(api):
    pid = api.create()
    run_to(api, pid, "otc_decision")
    assert any("your turn" in n["text"] for n in api.get("rajiv", "/api/notifications").json())
    assert api.get("suresh", "/api/notifications").json() == []
    assert api.get("pooja", "/api/notifications").json() == []


def test_people_directory_is_for_directors_and_admin_only(api):
    assert api.get("ananya", "/api/users").status_code == 403
    assert api.get("pooja", "/api/users").status_code == 403
    for who in ("rajiv", "suresh", "sneha"):
        assert api.get(who, "/api/users").status_code == 200
    names = api.get("pooja", "/api/people").json()                 # task picker: names only, no e-mails, no admin
    assert names and "email" not in names[0] and all(p["role"] != "admin" for p in names)


# ---- hierarchy -------------------------------------------------------------------
def test_reporting_line_rules(api):
    users = {u["email"].split("@")[0]: u for u in api.get("sneha", "/api/users").json()}
    assert users["divya"]["manager_id"] == users["sanjay"]["id"]
    assert users["sanjay"]["manager_id"] == users["suresh"]["id"]
    body = {"name": "Suresh Iyer", "email": "suresh@neohealth.example", "role": "india_director",
            "manager_id": users["divya"]["id"]}
    from fastapi.testclient import TestClient
    from app.main import app
    r = TestClient(app).put(f"/api/users/{users['suresh']['id']}", json=body, headers=api.as_("sneha"))
    assert r.status_code == 400 and "loop" in r.json()["detail"]


def test_only_admin_changes_people(api):
    from fastapi.testclient import TestClient
    from app.main import app
    c = TestClient(app)
    body = {"name": "X Person", "email": "x@neohealth.example", "role": "legal", "password": "secret1"}
    assert c.post("/api/users", json=body, headers=api.as_("rajiv")).status_code == 403
    assert c.post("/api/users", json=body, headers=api.as_("sneha")).status_code == 200
    assert c.post("/api/users", json={**body, "password": "abc"}, headers=api.as_("sneha")).status_code == 400


# ---- reminders and escalation -----------------------------------------------------
def test_overdue_step_reminds_owner_then_escalates_to_manager(api):
    pid = api.create()
    run_to(api, pid, "handover")
    with SessionLocal() as db:
        p = db.get(Project, pid)
        run = eng.active_runs(p)[0]
        base = run.entered_at
        assert eng.run_reminders(db, base + timedelta(days=1)) == {"reminded": 0, "escalated": 0}
        assert eng.run_reminders(db, base + timedelta(days=4)) == {"reminded": 1, "escalated": 0}
        assert eng.run_reminders(db, base + timedelta(days=4, hours=2)) == {"reminded": 0, "escalated": 0}  # no spam
        assert eng.run_reminders(db, base + timedelta(days=7)) == {"reminded": 0, "escalated": 1}
        kinds = [(n.user_id, n.kind) for n in db.query(Notification).filter(Notification.project_id == pid)]
    me = {u["email"].split("@")[0]: u["id"] for u in api.get("sneha", "/api/users").json()}
    assert (me["sanjay"], "remind") in kinds and (me["suresh"], "escalate") in kinds
    assert any(n["kind"] == "escalate" for n in api.get("suresh", "/api/notifications").json())


def test_reminder_is_reset_when_the_step_moves(api):
    pid = api.create()
    with SessionLocal() as db:
        run = eng.active_runs(db.get(Project, pid))[0]
        eng.run_reminders(db, run.entered_at + timedelta(days=10))
        assert db.get(StepRun, run.id).reminder_level == 2
    api.do("ananya", pid)
    with SessionLocal() as db:
        assert all(r.reminder_level == 0 for r in eng.active_runs(db.get(Project, pid)))


def test_nudge_asks_the_owner_and_is_limited(api):
    pid = api.create()
    run_to(api, pid, "otc_decision")
    run = api.detail("ananya", pid)["actions"][0]["run_id"]
    assert api.post("rajiv", f"/api/projects/{pid}/runs/{run}/nudge").status_code == 400   # his own turn
    assert api.post("ananya", f"/api/projects/{pid}/runs/{run}/nudge").status_code == 200
    n = [x for x in api.get("rajiv", "/api/notifications").json() if x["kind"] == "remind"]
    assert n and "Ananya Reddy (Initiator) reminds you" in n[0]["text"]                   # says who sent it
    assert api.post("ananya", f"/api/projects/{pid}/runs/{run}/nudge").status_code == 400


def test_dashboard_lists_steps_tasks_and_requests_for_the_person(api):
    pid = api.create()
    with SessionLocal() as db:
        p = db.get(Project, pid)
        for r in p.runs:
            r.entered_at -= timedelta(days=10)
            r.due_at -= timedelta(days=10)
        db.commit()
    d = api.get("rajiv", "/api/dashboard").json()
    assert d["view"] == "director" and d["counts"]["overdue"] == 1 and d["overdue"][0]["id"] == pid
    assert "overdue" not in api.get("ananya", "/api/dashboard").json()
    mine = api.get("ananya", "/api/dashboard").json()["mine"]
    assert mine[0]["type"] == "step" and mine[0]["overdue"] is True
    pooja = [p for p in api.get("ananya", "/api/people").json() if p["name"] == "Pooja Bansal"][0]["id"]
    api.post("ananya", f"/api/projects/{pid}/tasks", json={"title": "Check the claim", "assignee_id": pooja, "due": tomorrow(3)})
    assert [m["type"] for m in api.get("pooja", "/api/dashboard").json()["mine"]] == ["task"]


# ---- decision options follow the chart ----------------------------------------------
def test_decision_boxes_offer_what_the_chart_shows(api):
    pid = api.create()
    for step, keys in (("otc_decision", {"approve", "reject"}),
                       ("india_review", {"complete", "incomplete", "reject"}),
                       ("feas_decision", {"approve", "hold", "reject"}),
                       ("commercial_approval", {"approve", "back"}),
                       ("agreement_decision", {"approve", "hold", "reject"}),
                       ("reg_decision", {"approve", "back"}),
                       ("artwork_approval", {"approve", "back"})):
        run_to(api, pid, step)
        a = api.card("sneha", pid, step)
        assert {o["key"] for o in a["options"]} == keys, step


# ---- e-mail copy -------------------------------------------------------------------
def test_email_is_queued_and_sent_when_smtp_is_configured(api, monkeypatch):
    sent = []

    class FakeSMTP:
        def __init__(self, host, port, timeout=0): sent.append(("connect", host, port))
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def starttls(self): sent.append(("tls",))
        def login(self, u, p): sent.append(("login", u))
        def send_message(self, msg): sent.append(("mail", msg["To"], msg["Subject"]))

    monkeypatch.setenv("NEO_SMTP_HOST", "smtp.example.test")
    monkeypatch.setenv("NEO_SMTP_USER", "robot")
    monkeypatch.setattr(mailer.smtplib, "SMTP", FakeSMTP)
    pid = api.create()
    run_to(api, pid, "otc_decision")
    with SessionLocal() as db:
        pending = db.query(Notification).filter(Notification.email_status == "pending").count()
        assert pending >= 1
        res = mailer.send_pending(db)
        assert res["sent"] == pending and res["failed"] == 0
    assert any(m[0] == "mail" and m[1] == "rajiv@neohealth.example" and "your turn" in m[2] for m in sent)


def test_email_failure_is_recorded_not_raised(api, monkeypatch):
    def boom(*a, **k): raise OSError("no route")
    monkeypatch.setenv("NEO_SMTP_HOST", "smtp.example.test")
    monkeypatch.setattr(mailer.smtplib, "SMTP", boom)
    pid = api.create()
    run_to(api, pid, "otc_decision")
    with SessionLocal() as db:
        res = mailer.send_pending(db)
        assert res["failed"] >= 1 and db.query(Notification).filter(Notification.email_status == "failed").count() >= 1


# ---- account security --------------------------------------------------------------
def test_password_change_and_login_throttle(api):
    r = api.post("ananya", "/api/auth/password", json={"old_password": "wrong", "new_password": "newpass1"})
    assert r.status_code == 400
    assert api.post("ananya", "/api/auth/password", json={"old_password": "neo@123", "new_password": "abc"}).status_code == 400
    assert api.post("ananya", "/api/auth/password", json={"old_password": "neo@123", "new_password": "newpass1"}).status_code == 200
    from fastapi.testclient import TestClient
    from app.main import app
    c = TestClient(app)
    assert c.post("/api/auth/login", json={"email": "ananya@neohealth.example", "password": "neo@123"}).status_code == 401
    assert c.post("/api/auth/login", json={"email": "ananya@neohealth.example", "password": "newpass1"}).status_code == 200
    for _ in range(8):
        c.post("/api/auth/login", json={"email": "pooja@neohealth.example", "password": "bad"})
    assert c.post("/api/auth/login", json={"email": "pooja@neohealth.example", "password": "neo@123"}).status_code == 429


def test_deactivated_person_cannot_sign_in_or_use_old_token(api):
    from fastapi.testclient import TestClient
    from app.main import app
    c = TestClient(app)
    token = api.as_("pooja")
    users = {u["email"].split("@")[0]: u for u in api.get("sneha", "/api/users").json()}
    u = users["pooja"]
    body = {"name": u["name"], "email": u["email"], "role": u["role"], "active": False, "manager_id": u["manager_id"]}
    assert c.put(f"/api/users/{u['id']}", json=body, headers=api.as_("sneha")).status_code == 200
    assert c.get("/api/auth/me", headers=token).status_code == 401
    assert c.post("/api/auth/login", json={"email": u["email"], "password": "neo@123"}).status_code == 401


def test_blocked_and_empty_files_are_refused(api):
    pid = api.create()
    for name, body in (("run.exe", b"MZ"), ("empty.pdf", b"")):
        r = api.post("ananya", f"/api/projects/{pid}/documents", data={"step_key": "", "doc_type": ""},
                     files=[("files", (name, body, "application/octet-stream"))])
        assert r.status_code == 400


def test_old_format_database_is_backed_up_and_replaced(tmp_path):
    """A database from an earlier build is kept as a backup and the app starts fresh."""
    import os
    import sqlite3
    import subprocess
    import sys
    from pathlib import Path
    con = sqlite3.connect(tmp_path / "neo.db")
    con.execute("create table users (id integer primary key, name text, email text, password_hash text, role text, title text, active boolean)")
    con.execute("insert into users values (1,'Old Person','old@x.test','x','admin','',1)")
    con.commit()
    con.close()
    code = """
from fastapi.testclient import TestClient
from app.main import app
with TestClient(app) as c:
    r = c.post('/api/auth/login', json={'email': 'ananya@neohealth.example', 'password': 'neo@123'})
    print('LOGIN', r.status_code)
"""
    env = {**os.environ, "NEO_DATA_DIR": str(tmp_path), "NEO_AUTOSEED": "1", "NEO_BACKGROUND": "0"}
    out = subprocess.run([sys.executable, "-c", code], cwd=Path(__file__).resolve().parent.parent, env=env,
                         capture_output=True, text=True, timeout=300)
    assert "LOGIN 200" in out.stdout, out.stderr[-800:]
    assert list(tmp_path.glob("neo.old-*.db")), "old database was not kept as a backup"
