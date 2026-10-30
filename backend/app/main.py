import asyncio
import os
import re
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import engine as eng
from . import excel, mailer, views
from . import workflow as wf
from .db import BASE_DIR, UPLOAD_DIR, Base, SessionLocal, backup_legacy_database, get_db
from .db import engine as db_engine
from .models import Document, Notification, Project, User
from .security import current_user, hash_password, make_token, verify_password

MAX_UPLOAD = 20 * 1024 * 1024
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
BLOCKED_EXT = {".exe", ".bat", ".cmd", ".com", ".scr", ".js", ".vbs", ".msi", ".ps1", ".sh"}


def _background():
    """Hourly: remind / escalate overdue steps. Every 20 s: send queued e-mails (when SMTP is configured)."""
    async def loop():
        last_remind = 0.0
        while True:
            await asyncio.sleep(20)
            try:
                with SessionLocal() as db:
                    if mailer.configured():
                        await asyncio.to_thread(mailer.send_pending, db)
                    if time.time() - last_remind > 3600:
                        eng.run_reminders(db)
                        last_remind = time.time()
            except Exception:  # never let a background job stop the app
                pass
    return asyncio.create_task(loop())


@asynccontextmanager
async def lifespan(app):
    backup_legacy_database()
    Base.metadata.create_all(db_engine)
    with SessionLocal() as db:
        if not db.scalar(select(User).limit(1)) and os.environ.get("NEO_AUTOSEED", "1") == "1":
            from .seed import seed
            seed(db)
        eng.run_reminders(db)
    task = _background() if os.environ.get("NEO_BACKGROUND", "1") == "1" else None
    yield
    if task:
        task.cancel()


app = FastAPI(title="Neo Project Flow", lifespan=lifespan)


@app.exception_handler(eng.WorkflowError)
async def _wf_error(_, exc: eng.WorkflowError):
    return JSONResponse({"detail": exc.message}, status_code=exc.status)


@app.exception_handler(RequestValidationError)
async def _validation(_, exc: RequestValidationError):
    return JSONResponse({"detail": "Please check the form – some details are missing or not valid."},
                        status_code=422)


def _project(db: Session, pid: int, user: User) -> Project:
    """A project the person is allowed to see; anything else looks like it does not exist."""
    p = db.get(Project, pid)
    if not p or not eng.can_see(p, user):
        raise HTTPException(404, "Project not found.")
    return p


def _oversight(user: User):
    if user.role != "admin" and user.role not in eng.DIRECTORS:
        raise HTTPException(403, "This page is for the Directors and the Office Admin.")


# ---- auth -----------------------------------------------------------------
class Login(BaseModel):
    email: str
    password: str


class PasswordChange(BaseModel):
    old_password: str
    new_password: str


_fails: dict = {}


@app.post("/api/auth/login")
def login(body: Login, db: Session = Depends(get_db)):
    email = body.email.strip().lower()
    recent = [t for t in _fails.get(email, []) if time.time() - t < 600]
    if len(recent) >= 8:
        raise HTTPException(429, "Too many wrong attempts. Please wait 10 minutes and try again.")
    u = db.scalar(select(User).where(User.email == email))
    if not u or not u.active or not verify_password(body.password, u.password_hash):
        _fails[email] = recent + [time.time()]
        raise HTTPException(401, "Email or password is not correct.")
    _fails.pop(email, None)
    u.last_login = datetime.utcnow()
    db.commit()
    return {"token": make_token(u), "user": views.user_full(u)}


@app.get("/api/auth/demo-users")
def demo_users(db: Session = Depends(get_db)):
    """Shown on the sign-in page so the demo can be tried quickly. Turn off with NEO_DEMO_LOGIN=0."""
    if os.environ.get("NEO_DEMO_LOGIN", "1") != "1":
        return []
    users = db.scalars(select(User).where(User.active == True).order_by(User.id)).all()  # noqa: E712
    return [{"name": u.name, "email": u.email, "role_label": wf.ROLES[u.role]["short"],
             "org": wf.ROLES[u.role]["org"]} for u in users]


@app.get("/api/auth/me")
def me(user: User = Depends(current_user)):
    return views.user_full(user)


@app.post("/api/auth/password")
def change_password(body: PasswordChange, db: Session = Depends(get_db), user: User = Depends(current_user)):
    if not verify_password(body.old_password, user.password_hash):
        raise HTTPException(400, "Your current password is not correct.")
    if len(body.new_password) < 6:
        raise HTTPException(400, "The new password must have at least 6 characters.")
    user.password_hash = hash_password(body.new_password)
    db.commit()
    return {"ok": True}


@app.get("/api/workflow")
def workflow(_: User = Depends(current_user)):
    return wf.public_definition()


# ---- people and hierarchy (Directors view, Office Admin edits) ---------------
class UserIn(BaseModel):
    name: str
    email: str
    role: str
    title: str = ""
    password: str | None = None
    active: bool = True
    manager_id: int | None = None


def _admin(user: User):
    if user.role != "admin":
        raise HTTPException(403, "Only the Office Admin can manage the team.")


def _check_manager(db: Session, uid: int | None, manager_id: int | None):
    if not manager_id:
        return
    boss = db.get(User, manager_id)
    if not boss or not boss.active:
        raise HTTPException(400, "Please choose a valid manager.")
    seen, cur = {uid}, boss
    while cur:                                  # no loops in the reporting line
        if cur.id in seen:
            raise HTTPException(400, "That would make a loop in the reporting line.")
        seen.add(cur.id)
        cur = db.get(User, cur.manager_id) if cur.manager_id else None


@app.get("/api/users")
def users(db: Session = Depends(get_db), user: User = Depends(current_user)):
    _oversight(user)
    return [views.user_full(u) for u in db.scalars(select(User).order_by(User.name))]


@app.post("/api/users")
def add_user(body: UserIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    _admin(user)
    if body.role not in wf.ROLES:
        raise HTTPException(400, "Please choose a role.")
    email = body.email.strip().lower()
    if not body.name.strip() or "@" not in email:
        raise HTTPException(400, "Please enter a name and a valid email.")
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(400, "That email is already used.")
    if not body.password or len(body.password) < 6:
        raise HTTPException(400, "Please set a password (at least 6 characters).")
    _check_manager(db, None, body.manager_id)
    u = User(name=body.name.strip(), email=email, role=body.role, title=body.title,
             password_hash=hash_password(body.password), active=body.active, manager_id=body.manager_id)
    db.add(u)
    db.commit()
    return views.user_full(u)


@app.put("/api/users/{uid}")
def edit_user(uid: int, body: UserIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    _admin(user)
    u = db.get(User, uid)
    if not u:
        raise HTTPException(404, "Person not found.")
    if body.role not in wf.ROLES:
        raise HTTPException(400, "Please choose a role.")
    if u.id == user.id and (not body.active or body.role != "admin"):
        raise HTTPException(400, "You cannot deactivate yourself or remove your own admin access.")
    email = body.email.strip().lower()
    if db.scalar(select(User).where(User.email == email, User.id != uid)):
        raise HTTPException(400, "That email is already used.")
    _check_manager(db, uid, body.manager_id)
    u.name, u.email, u.role, u.title, u.active = body.name.strip(), email, body.role, body.title, body.active
    u.manager_id = body.manager_id
    if body.password:
        if len(body.password) < 6:
            raise HTTPException(400, "The password must have at least 6 characters.")
        u.password_hash = hash_password(body.password)
    db.commit()
    return views.user_full(u)


# ---- projects -----------------------------------------------------------------
class ProjectIn(BaseModel):
    title: str
    ptype: str
    market: str = ""
    description: str = ""
    est_value: float | None = None
    target_date: str = ""
    initiator_id: int | None = None


class ProjectEdit(BaseModel):
    title: str | None = None
    market: str | None = None
    description: str | None = None
    est_value: float | None = None
    target_date: str | None = None
    manufacturer: str | None = None
    initiator_id: int | None = None


class Act(BaseModel):
    option: str | None = None
    note: str = ""
    text: str | None = None


class Note(BaseModel):
    note: str = ""
    step_key: str = ""


@app.get("/api/projects")
def list_projects(db: Session = Depends(get_db), user: User = Depends(current_user)):
    dirx = views.directory(db)
    return [views.summary(p, user, dirx) for p in views.visible_projects(db, user)]


@app.post("/api/projects")
def create_project(body: ProjectIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    p = eng.create_project(db, user, body.model_dump())
    return views.detail(db, p, user)


@app.get("/api/projects/export.xlsx")
def export_master(db: Session = Depends(get_db), user: User = Depends(current_user)):
    dirx = views.directory(db)
    ps = sorted(views.visible_projects(db, user), key=lambda p: p.id)
    data = excel.master_workbook([views.summary(p, user, dirx) for p in ps])
    return Response(data, media_type=XLSX,
                    headers={"Content-Disposition": 'attachment; filename="Neo-Master-Projects.xlsx"'})


@app.get("/api/projects/import-template.xlsx")
def import_template(_: User = Depends(current_user)):
    return Response(excel.import_template(), media_type=XLSX,
                    headers={"Content-Disposition": 'attachment; filename="Neo-Opportunities-Template.xlsx"'})


@app.post("/api/projects/import")
async def import_projects(file: UploadFile = File(...), initiator_id: int | None = Form(None),
                          db: Session = Depends(get_db), user: User = Depends(current_user)):
    if user.role not in ("initiator", "admin"):
        raise HTTPException(403, "Only a Project Initiator can add projects.")
    try:
        rows = excel.parse_import(await file.read())
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception:
        raise HTTPException(400, "This does not look like the Neo template. Please download the template and try again.")
    if not rows:
        raise HTTPException(400, "No rows found in the file.")
    created = [eng.create_project(db, user, {**r, "initiator_id": initiator_id}) for r in rows]
    return {"created": len(created)}


@app.get("/api/projects/{pid}")
def get_project(pid: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    return views.detail(db, _project(db, pid, user), user)


@app.patch("/api/projects/{pid}")
def edit_project(pid: int, body: ProjectEdit, db: Session = Depends(get_db), user: User = Depends(current_user)):
    p = _project(db, pid, user)
    if not (user.role == "admin" or user.id == p.initiator_id):
        raise HTTPException(403, "Only the Project Initiator or Office Admin can edit the details.")
    for k, v in body.model_dump(exclude_unset=True).items():
        if k == "initiator_id":
            if user.role != "admin":
                raise HTTPException(403, "Only the Office Admin can change the Project Initiator.")
            new = db.get(User, v or 0)
            if not new or new.role != "initiator":
                raise HTTPException(400, "Please choose a Project Initiator.")
            p.initiator_id = v
        elif k == "title" and not (v or "").strip():
            raise HTTPException(400, "The project needs a name.")
        else:
            setattr(p, k, v)
    p.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(p)
    return views.detail(db, p, user)


@app.post("/api/projects/{pid}/act")
def act(pid: int, body: Act, db: Session = Depends(get_db), user: User = Depends(current_user)):
    p = _project(db, pid, user)
    result = eng.act(db, p, user, option=body.option, note=body.note, text=body.text)
    return {**result, "project": views.detail(db, p, user)}


@app.post("/api/projects/{pid}/comments")
def comment(pid: int, body: Note, db: Session = Depends(get_db), user: User = Depends(current_user)):
    p = _project(db, pid, user)
    eng.add_comment(db, p, user, body.note)
    return views.detail(db, p, user)


@app.post("/api/projects/{pid}/nudge")
def nudge(pid: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    p = _project(db, pid, user)
    msg = eng.nudge(db, p, user)
    return {"message": msg, "project": views.detail(db, p, user)}


@app.post("/api/projects/{pid}/hold")
def hold(pid: int, body: Note, db: Session = Depends(get_db), user: User = Depends(current_user)):
    p = _project(db, pid, user)
    eng.hold_project(db, p, user, body.note)
    return views.detail(db, p, user)


@app.post("/api/projects/{pid}/resume")
def resume(pid: int, body: Note, db: Session = Depends(get_db), user: User = Depends(current_user)):
    p = _project(db, pid, user)
    eng.resume_project(db, p, user, body.note)
    return views.detail(db, p, user)


@app.post("/api/projects/{pid}/cancel")
def cancel(pid: int, body: Note, db: Session = Depends(get_db), user: User = Depends(current_user)):
    p = _project(db, pid, user)
    eng.cancel_project(db, p, user, body.note)
    return views.detail(db, p, user)


@app.post("/api/projects/{pid}/move")
def move(pid: int, body: Note, db: Session = Depends(get_db), user: User = Depends(current_user)):
    p = _project(db, pid, user)
    eng.move_project(db, p, user, body.step_key, body.note)
    return views.detail(db, p, user)


@app.get("/api/projects/{pid}/brief.xlsx")
def brief(pid: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    p = _project(db, pid, user)
    name = re.sub(r"[^A-Za-z0-9]+", "-", p.code or p.title).strip("-")
    return Response(excel.brief_workbook(views.detail(db, p, user)), media_type=XLSX,
                    headers={"Content-Disposition": f'attachment; filename="Brief-{name}.xlsx"'})


# ---- files --------------------------------------------------------------------
@app.post("/api/projects/{pid}/documents")
async def upload(pid: int, file: UploadFile = File(...), step_key: str = Form(""),
                 db: Session = Depends(get_db), user: User = Depends(current_user)):
    p = _project(db, pid, user)
    name = Path(file.filename or "file").name
    if Path(name).suffix.lower() in BLOCKED_EXT:
        raise HTTPException(400, "This type of file is not allowed.")
    data = await file.read()
    if not data:
        raise HTTPException(400, "That file is empty.")
    if len(data) > MAX_UPLOAD:
        raise HTTPException(400, "File is too large (limit 20 MB).")
    if step_key and step_key not in wf.STEP_BY_KEY:
        raise HTTPException(400, "Unknown step.")
    stored = uuid.uuid4().hex + Path(name).suffix[:10]
    (UPLOAD_DIR / stored).write_bytes(data)
    eng.add_document(db, p, user, name, stored, len(data), step_key)
    return views.detail(db, p, user)


@app.get("/api/documents/{did}")
def download(did: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    d = db.get(Document, did)
    path = UPLOAD_DIR / d.stored_name if d else None
    if not d or not path.exists() or not eng.can_see(d.project, user):
        raise HTTPException(404, "File not found.")
    return FileResponse(path, filename=d.filename)


@app.delete("/api/documents/{did}")
def delete_doc(did: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    d = db.get(Document, did)
    if not d or not eng.can_see(d.project, user):
        raise HTTPException(404, "File not found.")
    if not (user.role == "admin" or d.user_id == user.id):
        raise HTTPException(403, "Only the person who added the file (or the Office Admin) can remove it.")
    p = d.project
    (UPLOAD_DIR / d.stored_name).unlink(missing_ok=True)
    db.delete(d)
    db.commit()
    return views.detail(db, p, user)


# ---- home + notifications ------------------------------------------------------
@app.get("/api/dashboard")
def dashboard(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return views.dashboard(db, user)


@app.get("/api/notifications")
def notifications(db: Session = Depends(get_db), user: User = Depends(current_user)):
    rows = db.scalars(select(Notification).where(Notification.user_id == user.id)
                      .order_by(Notification.id.desc()).limit(40)).all()
    return [{"id": n.id, "project_id": n.project_id, "text": n.text, "kind": n.kind, "read": n.read,
             "email": n.email_status, "at": views.iso(n.created_at)} for n in rows]


@app.post("/api/notifications/read")
def read_notifications(db: Session = Depends(get_db), user: User = Depends(current_user)):
    for n in db.scalars(select(Notification).where(Notification.user_id == user.id, Notification.read == False)):  # noqa: E712
        n.read = True
    db.commit()
    return {"ok": True}


@app.post("/api/admin/run-reminders")
def run_reminders(db: Session = Depends(get_db), user: User = Depends(current_user)):
    _admin(user)
    return {**eng.run_reminders(db), **(mailer.send_pending(db) if mailer.configured() else {})}


# ---- serve the built web app -----------------------------------------------------
DIST = BASE_DIR.parent / "frontend" / "dist"
if DIST.exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{path:path}")
    def spa(path: str):
        if path.startswith("api/"):
            raise HTTPException(404, "Not found.")
        f = (DIST / path).resolve()
        return FileResponse(f if path and f.is_file() and DIST in f.parents else DIST / "index.html")
