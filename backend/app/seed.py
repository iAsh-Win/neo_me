"""Demo data. Projects are walked through the real workflow engine, so every history entry, document, detail,
approval, send-back and request in the demo is exactly what the live system would produce."""
import random
import uuid
from datetime import datetime, timedelta
from io import BytesIO

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import engine as eng
from . import workflow as wf
from .db import UPLOAD_DIR
from .models import Notification, Project, User
from .security import hash_password

PASSWORD = "neo@123"
DOM = "@neohealth.example"

# name, key (e-mail prefix), role, title, manager key
USERS = [
    ("Sneha Kulkarni", "sneha", "admin", "Office Administrator", None),
    ("Rajiv Khanna", "rajiv", "otc_director", "Director, Neo Health OTC Pty Ltd", None),
    ("Suresh Iyer", "suresh", "india_director", "Director, Neo India Lifeline Pvt Ltd", None),
    ("Ananya Reddy", "ananya", "initiator", "Product Manager, Neo Health (OTC)", "rajiv"),
    ("Rohit Malhotra", "rohit", "initiator", "Business Development, Neo Health (OTC)", "rajiv"),
    ("Meera Joshi", "meera", "cft", "Cross-Functional Team – Formulation", "suresh"),
    ("Karthik Subramanian", "karthik", "cft", "Cross-Functional Team – Operations", "suresh"),
    ("Pooja Bansal", "pooja", "legal", "Legal Counsel", "suresh"),
    ("Amit Deshmukh", "amit", "quality", "Head of Quality Assurance", "suresh"),
    ("Dr. Neha Kapoor", "neha", "pv", "Pharmacovigilance Lead", "suresh"),
    ("Dr. Sanjay Patel", "sanjay", "reg_head", "Head of Regulatory Affairs", "suresh"),
    ("Divya Menon", "divya", "reg_team", "Regulatory Affairs Executive", "sanjay"),
    ("Harsh Vora", "harsh", "reg_team", "Regulatory Affairs Executive", "sanjay"),
    ("Ritika Sen", "ritika", "artwork", "Senior Artwork Designer", "rajiv"),
    ("Manish Pillai", "manish", "artwork", "Artwork Coordinator", "rajiv"),
    ("Arjun Bhatia", "arjun", "commercial", "Commercial Manager, Neo Health (OTC)", "rajiv"),
    ("Sakshi Agarwal", "sakshi", "commercial", "Supply Chain Executive", "rajiv"),
    ("Rakesh Gowda", "rakesh", "cmo", "Plant Head, Sunrise Pharma (manufacturer)", None),
]

# title, type, market, yearly sales (A$), description, initiator, steps to leave waiting, days waiting, script, fast track
# script: step -> list of ("approve"|"done"|"complete"|"incomplete"|"back"|"hold"|"reject", note) or ("sendback", target, note)
PROJECTS = [
    ("C-Boost Vitamin C Effervescent 1000mg", "development", "Australia", 520000,
     "Orange-flavoured effervescent tablets, tube of 20. Targets the winter immunity season.",
     "ananya", {"reg_submission", "shade_card"}, 2,
     {"india_review": [("reject", "Please add the competitor price comparison and stability plan.")],
      "artwork_approval": [("back", "Please make the dosage panel larger and fix the colour of the logo."), ("approve", "")],
      "mfr_approval": [("sendback", "print_proof", "The green on the carton is too dark. Please reprint the proof.")]}, True),
    ("Zinc + D3 Immunity Gummies", "in_licence", "Australia", 380000,
     "In-licensed gummy from a Korean partner, 60 count. Needs TGA listing.",
     "rohit", {"reg_decision"}, 4, {}, False),
    ("Magnesium Night Calm Tablets", "development", "Australia & NZ", 290000,
     "Magnesium glycinate 300mg for sleep and muscle relaxation, 60 tablets.",
     "ananya", {"india_review"}, 1, {}, False),
    ("Joint Flex Collagen Sachets", "development", "Australia", 340000,
     "Hydrolysed collagen with vitamin C, 30 sachets. Berry flavour.",
     "rohit", {"internal_review"}, 2,
     {"india_review": [("incomplete", "")], "clarification": [("done", "")]}, False),
    ("Daily Probiotic 30B Capsules", "in_licence", "Australia", 610000,
     "30 billion CFU, 30 capsules, in-licensed from a European supplier.",
     "ananya", {"commercial_approval"}, 1, {"__partial__": "india_director"}, False),
    ("Kids Honey Cough Syrup", "development", "Australia", 450000,
     "Honey and ivy leaf cough syrup for children 2+, 100 ml bottle.",
     "rohit", {"otc_decision"}, 1, {}, False),
    ("Iron + Folate Tablets", "in_licence", "Australia", 260000,
     "Iron 24mg with folic acid for pregnancy support, 90 tablets.",
     "ananya", set(), 0, {}, False),
    ("Omega-3 Fish Oil 1000mg", "development", "Australia", 700000,
     "High-strength fish oil, 200 capsules.",
     "rohit", {"otc_decision"}, 9, {"otc_decision": [("reject", "The market is already crowded and the margin is too low for now.")]}, False),
    ("Electrolyte Hydration Powder", "development", "Australia", 330000,
     "Sugar-free electrolyte powder, 10 sachets, three flavours.",
     "ananya", {"feas_decision"}, 6, {"feas_decision": [("hold", "Waiting for raw-material prices to settle before we decide.")]}, False),
    ("Lutein Eye Care Softgels", "development", "Australia", 275000,
     "Lutein 20mg and zeaxanthin, 60 softgels.",
     "rohit", {"concept"}, 3,
     {"artwork_approval": [("back", "Front panel looks crowded. Simplify and show the key benefit only.")]}, False),
    ("Aloe Vera Throat Lozenges", "in_licence", "Australia", 180000,
     "Soothing lozenges, 24 pack, in-licensed.",
     "rohit", {"draft_brief"}, 9, {}, False),
    ("Herbal Sleep Drops", "development", "New Zealand", 150000,
     "Valerian and passionflower liquid drops, 50 ml.",
     "ananya", {"screening"}, 0, {}, False),
    ("Ibuprofen 5% Pain Relief Gel", "development", "Australia", 480000,
     "Topical gel for muscle and joint pain, 100 g tube.",
     "rohit", {"fmea"}, 3, {}, False),
    ("Antacid Chewable Tablets", "in_licence", "Australia", 310000,
     "Calcium carbonate chewables, mint flavour, 48 tablets.",
     "ananya", {"mfr_tech"}, 1, {}, False),
    ("Ashwagandha Stress Relief Capsules", "development", "Australia", 420000,
     "Standardised ashwagandha root extract 600mg, 60 capsules. Made at the India plant.",
     "ananya", {"agreement_prep"}, 2, {}, False),
    ("Biotin Hair & Nails Gummies", "development", "Australia", 360000,
     "Biotin 5000mcg gummies, 60 count, strawberry.",
     "rohit", {"feas_prep@rework"}, 1,
     {"feas_decision": [("sendback", "feas_prep", "Please add the stability data for the gummy base before I can decide.")]}, False),
]

FILE_TYPES = {"master_excel": "xlsx"}

COMMENTS = [
    "Supplier has confirmed they can meet the first batch date.",
    "Please check the claim wording with Regulatory before we go further.",
    "Samples arrived today, looking good.",
    "Pricing updated in the Master Excel, please have a look.",
]

TEXT = {"manufacturer": "Sunrise Pharma Pvt Ltd (CDMO)", "country": "India", "version": "v2", "pathway": None,
        "question": "Please confirm the key ingredient details and the shelf life claim."}


def make_file(title: str, label: str, ext: str) -> tuple:
    stem = "".join(c if c.isalnum() else "-" for c in label).strip("-")
    name = f"{stem}.{ext}"
    if ext == "xlsx":
        from openpyxl import Workbook
        wb = Workbook()
        ws = wb.active
        ws.title = "Brief"
        for row in [("Project", title), ("Section", "Details"), ("Product concept", "As agreed in screening"),
                    ("Target market", "OTC pharmacy and grocery"), ("Pack", "See concept")]:
            ws.append(row)
        bio = BytesIO()
        wb.save(bio)
        return name, bio.getvalue()
    import fitz
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((60, 90), label, fontsize=20)
    page.insert_text((60, 130), f"Project: {title}", fontsize=12)
    page.insert_text((60, 160), "Sample document created for the Neo Project Flow demo data.", fontsize=10)
    return name, doc.tobytes()


class _Sim:
    def __init__(self, db: Session, rng: random.Random):
        self.db, self.rng = db, rng
        self.t = datetime(2026, 1, 1, 9, 0)

    def tick(self, lo=18, hi=70):
        self.t += timedelta(hours=self.rng.randint(lo, hi))
        return self.t

    def person(self, p: Project, role: str) -> User:
        if role == "initiator":
            return p.initiator
        people = self.db.scalars(select(User).where(User.role == role, User.active == True)  # noqa: E712
                                 .order_by(User.id)).all()
        return self.rng.choice(people)

    def add_docs(self, p: Project, user: User, step: dict, at):
        for d in step.get("docs", []):
            if d.get("role") not in (None, user.role):
                continue
            if d["required"] and not any(x.step_key == step["key"] and x.doc_type == d["key"] for x in p.documents):
                if (p.id + len(p.documents)) % 3 == 0:
                    slug = d["key"].replace("_", "-")
                    eng.add_link(self.db, p, user, d["label"], f"https://share.neohealth.example/{p.id}/{slug}",
                                 step["key"], d["key"], at=at)
                else:
                    name, data = make_file(p.title, d["label"], FILE_TYPES.get(d["key"], "pdf"))
                    stored = uuid.uuid4().hex + "." + name.rsplit(".", 1)[1]
                    (UPLOAD_DIR / stored).write_bytes(data)
                    eng.add_file(self.db, p, user, name, stored, len(data), step["key"], d["key"], at=at)

    def values(self, p: Project, step: dict, role: str) -> tuple:
        data = {}
        for f in step.get("fields", []):
            k, t = f["key"], f["type"]
            if k in TEXT and TEXT[k]:
                data[k] = TEXT[k]
            elif t == "number":
                data[k] = {"est_value": str(int(p.est_value or 100000)), "unit_cost": "1.85", "moq": "50000", "margin": "32",
                           "lead_days": "45", "batch_size": "60000", "qty": "58000"}.get(k, "1000")
            elif t == "date":
                data[k] = (self.t + timedelta(days=60)).date().isoformat() if k in ("target_date", "target_submission") \
                    else self.t.date().isoformat()
            elif t == "select":
                data[k] = f["options"][0] if k != "risk_level" else "Medium"
            elif k == "reference":
                data[k] = f"TGA-{p.id:04d}-26"
            elif k == "batch_no":
                data[k] = f"B{26000 + p.id}"
            elif k == "invoice":
                data[k] = f"INV-26-{p.id:03d}"
            else:
                data[k] = "OK"
        return data, [c["key"] for c in wf.required_checks(step, role)]

    def step_once(self, p: Project, run, script: dict):
        step = wf.STEP_BY_KEY[run.step_key]
        role = eng.waiting_roles(p, run)[0]
        user = self.person(p, role)
        at = self.tick()
        queue = script.get(run.step_key)
        item = queue.pop(0) if queue else None
        if item and item[0] == "sendback":
            eng.send_back(self.db, p, user, run.id, item[1], item[2], at=at)
            return
        option, note = (item if item else (None, ""))
        if step["mode"] == "decision":
            option = option or ("complete" if step["key"] == "india_review" else "approve")
        elif option == "done":
            option = None
        if step["mode"] == "decision" and step["options"][option]["kind"] in ("back", "hold", "reject"):
            note = note or "Needs more work before we can proceed."
            eng.act(self.db, p, user, run.id, option=option, note=note, at=at)
            return
        self.add_docs(p, user, step, at)
        data, checks = self.values(p, step, role)
        eng.act(self.db, p, user, run.id, option=option, note=note if option != "complete" else "", data=data,
                checks=checks, at=at)

    def advance(self, p: Project, hold: set, script: dict):
        """Keep finishing steps until every step still waiting is one we want to leave waiting."""
        for _ in range(500):
            if p.status != "active":
                return
            pending = [r for r in eng.active_runs(p)
                       if not (r.step_key in hold or (r.kind == "rework" and r.step_key + "@rework" in hold))]
            if not eng.active_runs(p) or not pending:
                return
            for run in pending:
                if run.status == "active":
                    self.step_once(p, run, script)
                    break
        raise RuntimeError(f"seed did not settle on {hold}")


def _shift(p: Project, delta: timedelta):
    for e in p.events:
        e.created_at += delta
    for d in p.documents:
        d.created_at += delta
    for r in p.runs:
        r.entered_at += delta
        r.due_at += delta
        if r.completed_at:
            r.completed_at += delta
    for t in p.tasks:
        t.created_at += delta
        t.due_at += delta
    p.created_at += delta


def seed(db: Session):
    rng = random.Random(11)
    pw = hash_password(PASSWORD)  # one hash is enough for the demo accounts
    for name, key, role, title, _ in USERS:
        db.add(User(name=name, email=key + DOM, role=role, title=title, password_hash=pw))
    db.commit()
    users = {u.email: u for u in db.scalars(select(User))}
    for _, key, _, _, boss in USERS:
        if boss:
            users[key + DOM].manager_id = users[boss + DOM].id
    db.commit()
    sim = _Sim(db, rng)
    now = datetime.utcnow()
    rajiv, suresh = users["rajiv" + DOM], users["suresh" + DOM]
    made = {}

    for title, ptype, market, value, desc, ini, hold, days, script, fast in PROJECTS:
        sim.t = datetime(2026, 1, 1, 9, 0)
        p = eng.create_project(db, users[ini + DOM], {"title": title, "ptype": ptype, "market": market, "est_value": value,
                                                      "description": desc,
                                                      "target_date": f"2027-{rng.randint(1, 9):02d}-15"}, at=sim.t)
        made[title] = p
        partial = script.pop("__partial__", None)
        script = {k: list(v) for k, v in script.items()}
        if fast:
            eng.set_fast_track(db, p, rajiv, True, at=sim.t)
        sim.advance(p, hold, script)
        for key in hold:                       # decisions the demo wants taken at the step where it stops
            if script.get(key) and p.status == "active":
                for run in eng.active_runs(p):
                    if run.step_key == key:
                        sim.step_once(p, run, script)
        if partial:
            run = eng.active_runs(p)[0]
            eng.act(db, p, sim.person(p, partial), run.id, option="approve", at=sim.tick())
        if p.status in ("active", "on_hold") and rng.random() < 0.7:
            eng.add_comment(db, p, sim.person(p, "initiator"), rng.choice(COMMENTS), at=sim.tick())
        last = max([e.created_at for e in p.events] + [r.entered_at for r in p.runs])
        _shift(p, (now - timedelta(days=days, hours=rng.randint(0, 5))) - last)
        p.updated_at = now - timedelta(days=days)
        db.commit()

    # tasks and time requests (created after the history is in place, so their dates are recent)
    zinc, aloe, ibu, mag = (made["Zinc + D3 Immunity Gummies"], made["Aloe Vera Throat Lozenges"],
                            made["Ibuprofen 5% Pain Relief Gel"], made["Magnesium Night Calm Tablets"])
    sanjay, divya, arjun = users["sanjay" + DOM], users["divya" + DOM], users["arjun" + DOM]
    eng.create_task(db, zinc, sanjay, "Collect the GMP clearance letter from the manufacturer", divya.id,
                    (now + timedelta(days=2)).date().isoformat(), "Needed before we can complete the dossier.",
                    "dossier_assign", True, at=now - timedelta(days=1))
    eng.create_task(db, aloe, users["rohit" + DOM], "Get the competitor price list", arjun.id,
                    (now - timedelta(days=1)).date().isoformat(), "Three main competitors, pharmacy prices.", "", False,
                    at=now - timedelta(days=5))
    eng.create_task(db, mag, suresh, "Confirm batch size with the plant", users["rakesh" + DOM].id,
                    (now + timedelta(days=4)).date().isoformat(), "", "", False, at=now - timedelta(hours=20))
    run = next(r for r in eng.active_runs(ibu) if r.step_key == "fmea")
    eng.request_time(db, ibu, users["meera" + DOM], run_id=run.id,
                     new_due=(run.due_at + timedelta(days=4)).date().isoformat(),
                     reason="The stability data from the plant will reach us only next Tuesday.",
                     at=now - timedelta(hours=18))

    # a document on a task, key documents, and a step handed to one chosen person (shows the new features in the demo)
    gmp = next(t for t in zinc.tasks if t.title.startswith("Collect the GMP"))
    eng.add_document(db, zinc, sanjay, title="GMP checklist (SharePoint)", url="https://share.neohealth.example/zinc/gmp-checklist",
                     task_id=gmp.id, at=now - timedelta(hours=20))
    name, data = make_file(zinc.title, "Supplier GMP certificate", "pdf")
    stored = uuid.uuid4().hex + ".pdf"
    (UPLOAD_DIR / stored).write_bytes(data)
    eng.add_document(db, zinc, divya, title="Supplier GMP certificate", url="https://share.neohealth.example/zinc/gmp-cert",
                     filename=name, stored=stored, size=len(data), task_id=gmp.id, at=now - timedelta(hours=5))
    for p in made.values():
        for d in p.documents:
            if d.doc_type in ("business_case", "quotation", "dossier", "final_artwork") and not d.source_id:
                d.important = True
    shown = 0
    for p in made.values():
        if shown >= 2 or p.status != "active":
            continue
        for r in eng.active_runs(p):
            step = wf.STEP_BY_KEY[r.step_key]
            people = eng.people_for_roles(db, p, step["roles"])
            if eng.can_pick_person(step) and len(people) > 1 and not any(
                    q.run_id == r.id for q in p.requests):
                eng.reassign_run(db, p, rajiv, r.id, people[-1].id, at=now - timedelta(hours=3))
                shown += 1
                break
    db.commit()

    # notifications: history is read; what is waiting right now stays unread
    for n in db.scalars(select(Notification)):
        n.read = True
        n.created_at = now - timedelta(hours=rng.randint(2, 70))
    for p in db.scalars(select(Project)):
        if p.status != "active":
            continue
        for r in eng.active_runs(p):
            if r.kind == "rework" or r.from_user_id:
                msg = f"{p.title} · your turn: {wf.STEP_BY_KEY[r.step_key]['name']}"
                for n in db.scalars(select(Notification).where(Notification.project_id == p.id,
                                                               Notification.kind.in_(("turn", "back")))):
                    if n.text.startswith(msg) or (r.kind == "rework" and wf.STEP_BY_KEY[r.step_key]["name"] in n.text):
                        n.read = False
    for n in db.scalars(select(Notification).where(Notification.kind.in_(("request",)))):
        n.read = False
    db.commit()
    eng.run_reminders(db, now)
