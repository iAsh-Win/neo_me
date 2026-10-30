"""Demo data. Projects are walked through the real workflow engine, so every
history, approval and file in the demo is exactly what the live system would produce."""
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

# title, type, market, yearly sales (A$), description, initiator, stop-at step, days waiting there, options script
PROJECTS = [
    ("C-Boost Vitamin C Effervescent 1000mg", "development", "Australia", 520000,
     "Orange-flavoured effervescent tablets, tube of 20. Targets the winter immunity season.",
     "ananya", "shade_card", 2,
     {"india_review": [("reject", "Please add the competitor price comparison and stability plan.")],
      "artwork_approval": [("back", "Please make the dosage panel larger and fix the colour of the logo."), ("approve", "")]}),
    ("Zinc + D3 Immunity Gummies", "in_licence", "Australia", 380000,
     "In-licensed gummy from a Korean partner, 60 count. Needs TGA listing.",
     "rohit", "reg_decision", 4, {}),
    ("Magnesium Night Calm Tablets", "development", "Australia & NZ", 290000,
     "Magnesium glycinate 300mg for sleep and muscle relaxation, 60 tablets.",
     "ananya", "india_review", 1, {}),
    ("Joint Flex Collagen Sachets", "development", "Australia", 340000,
     "Hydrolysed collagen with vitamin C, 30 sachets. Berry flavour.",
     "rohit", "internal_review", 2,
     {"india_review": [("incomplete", "")], "clarification": [("done", "Please confirm the collagen source and the shelf life claim.")]}),
    ("Daily Probiotic 30B Capsules", "in_licence", "Australia", 610000,
     "30 billion CFU, 30 capsules, in-licensed from a European supplier.",
     "ananya", "commercial_approval", 1, {"__partial__": "india_director"}),
    ("Kids Honey Cough Syrup", "development", "Australia", 450000,
     "Honey and ivy leaf cough syrup for children 2+, 100 ml bottle.",
     "rohit", "otc_decision", 1, {}),
    ("Iron + Folate Tablets", "in_licence", "Australia", 260000,
     "Iron 24mg with folic acid for pregnancy support, 90 tablets.",
     "ananya", None, 0, {}),
    ("Omega-3 Fish Oil 1000mg", "development", "Australia", 700000,
     "High-strength fish oil, 200 capsules.",
     "rohit", "otc_decision", 9, {"otc_decision": [("reject", "The market is already crowded and the margin is too low for now.")]}),
    ("Electrolyte Hydration Powder", "development", "Australia", 330000,
     "Sugar-free electrolyte powder, 10 sachets, three flavours.",
     "ananya", "feas_decision", 6, {"feas_decision": [("hold", "Waiting for raw-material prices to settle before we decide.")]}),
    ("Lutein Eye Care Softgels", "development", "Australia", 275000,
     "Lutein 20mg and zeaxanthin, 60 softgels.",
     "rohit", "concept", 3,
     {"artwork_approval": [("back", "Front panel looks crowded. Simplify and show the key benefit only.")]}),
    ("Aloe Vera Throat Lozenges", "in_licence", "Australia", 180000,
     "Soothing lozenges, 24 pack, in-licensed.",
     "rohit", "draft_brief", 9, {}),
    ("Herbal Sleep Drops", "development", "New Zealand", 150000,
     "Valerian and passionflower liquid drops, 50 ml.",
     "ananya", "screening", 0, {}),
    ("Ibuprofen 5% Pain Relief Gel", "development", "Australia", 480000,
     "Topical gel for muscle and joint pain, 100 g tube.",
     "rohit", "fmea", 3, {}),
    ("Antacid Chewable Tablets", "in_licence", "Australia", 310000,
     "Calcium carbonate chewables, mint flavour, 48 tablets.",
     "ananya", "mfr_tech", 1, {}),
    ("Ashwagandha Stress Relief Capsules", "development", "Australia", 420000,
     "Standardised ashwagandha root extract 600mg, 60 capsules. Made at the India plant.",
     "ananya", "agreement_prep", 2, {}),
]

FILE_STEPS = {"draft_brief": ("Master-Excel-Brief", "xlsx"), "feas_submit": ("Final-Feasibility-Report", "pdf"),
              "agreement_prep": ("Supplier-Agreement-Draft", "pdf"), "artwork": ("Artwork-Concept", "pdf"),
              "print_proof": ("Manufacturer-Print-Proof", "pdf")}

COMMENTS = [
    "Supplier has confirmed they can meet the first batch date.",
    "Please check the claim wording with Regulatory before we go further.",
    "Samples arrived today, looking good.",
    "Pricing updated in the Master Excel, please have a look.",
]


def make_file(title: str, stem: str, ext: str) -> tuple:
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
    page.insert_text((60, 90), stem.replace("-", " "), fontsize=20)
    page.insert_text((60, 130), f"Project: {title}", fontsize=12)
    page.insert_text((60, 160), "Demo document created for the Neo Project Flow sample data.", fontsize=10)
    return name, doc.tobytes()


class _Sim:
    def __init__(self, db: Session, rng: random.Random):
        self.db, self.rng = db, rng
        self.t = datetime(2026, 1, 1, 9, 0)

    def tick(self, lo=18, hi=70):
        self.t += timedelta(hours=self.rng.randint(lo, hi))
        return self.t

    def actor(self, p: Project, role: str) -> User:
        if role == "initiator":
            return p.initiator
        people = self.db.scalars(select(User).where(User.role == role, User.active == True)  # noqa: E712
                                 .order_by(User.id)).all()
        return self.rng.choice(people)

    def attach(self, p: Project, user: User, step_key: str, at):
        stem, ext = FILE_STEPS[step_key]
        name, data = make_file(p.title, stem, ext)
        stored = uuid.uuid4().hex + "." + ext
        (UPLOAD_DIR / stored).write_bytes(data)
        eng.add_document(self.db, p, user, name, stored, len(data), step_key, at)

    def advance(self, p: Project, target: str | None, script: dict):
        """Move the project forward step by step until it reaches `target` (None = completion)."""
        for _ in range(400):
            if p.status != "active" or (target and p.current_step == target):
                return
            step = wf.STEP_BY_KEY[p.current_step]
            role = eng.waiting_roles(p)[0]
            user = self.actor(p, role)
            at = self.tick()
            if p.current_step in FILE_STEPS and not any(d.step_key == p.current_step for d in p.documents):
                self.attach(p, user, p.current_step, at)
            queue = script.get(p.current_step)
            option, note = None, ""
            if queue:
                option, note = queue.pop(0)
                if option == "done":
                    option = None
            elif step["mode"] == "decision":
                option = "complete" if step["key"] == "india_review" else "approve"
            text = "Sunrise Pharma Pvt Ltd (CDMO)" if step.get("needs_text") else None
            if step.get("needs_note") and not note:
                note = "Please confirm the key ingredient details."
            if option in (step.get("options") or {}) and step["options"][option].get("note") and not note:
                note = "Needs more work before we can proceed."
            eng.act(self.db, p, user, option=option, note=note, text=text, at=at)
            if p.status == "completed":
                return
        raise RuntimeError(f"seed did not reach {target}")


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

    for title, ptype, market, value, desc, ini, target, days, script in PROJECTS:
        sim.t = datetime(2026, 1, 1, 9, 0)
        initiator = users[ini + DOM]
        p = eng.create_project(db, initiator, {"title": title, "ptype": ptype, "market": market,
                                               "est_value": value, "description": desc,
                                               "target_date": f"2027-{rng.randint(1, 9):02d}-15"}, at=sim.t)
        partial = script.pop("__partial__", None)
        script = {k: list(v) for k, v in script.items()}
        if target is None:                                   # finished project
            sim.advance(p, None, script)
        elif target == "otc_decision" and script.get("otc_decision"):
            sim.advance(p, "otc_decision", script)
            eng.act(db, p, sim.actor(p, "otc_director"), option="reject", note=script["otc_decision"][0][1],
                    at=sim.tick())
        elif target == "feas_decision" and script.get("feas_decision"):
            sim.advance(p, "feas_decision", script)
            eng.act(db, p, sim.actor(p, "india_director"), option="hold", note=script["feas_decision"][0][1],
                    at=sim.tick())
        else:
            sim.advance(p, target, script)
        if partial:
            eng.act(db, p, sim.actor(p, partial), option="approve", at=sim.tick())
        if rng.random() < 0.8:
            eng.add_comment(db, p, sim.actor(p, "initiator"), rng.choice(COMMENTS), at=sim.tick())
        # shift the whole history so the project has been waiting `days` days now
        last = max(e.created_at for e in p.events)
        delta = (now - timedelta(days=days, hours=rng.randint(0, 5))) - max(p.step_entered_at, last)
        for e in p.events:
            e.created_at += delta
        for d in p.documents:
            d.created_at += delta
        p.step_entered_at += delta
        p.created_at += delta
        p.updated_at = max(e.created_at for e in p.events)
        db.commit()

    # notifications: history is read; only what is waiting right now stays unread
    waiting = {p.id: f"{p.title} – your turn: {wf.STEP_BY_KEY[p.current_step]['name']}"
               for p in db.scalars(select(Project)) if p.status == "active"}
    for n in db.scalars(select(Notification)):
        n.read = waiting.get(n.project_id) != n.text
        n.created_at = now - timedelta(hours=rng.randint(2, 70))
    db.commit()
    eng.run_reminders(db, now)
