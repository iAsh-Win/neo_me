import os
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

_tmp = tempfile.mkdtemp(prefix="neo_test_")
os.environ["NEO_DATA_DIR"] = _tmp
os.environ["NEO_AUTOSEED"] = "0"
os.environ["NEO_BACKGROUND"] = "0"
os.environ["NEO_PBKDF2_ITER"] = "2000"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.db import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import User  # noqa: E402
from app.seed import DOM, PASSWORD, USERS  # noqa: E402
from app.security import hash_password  # noqa: E402

# Who acts for each role in the tests
WHO = {"initiator": "ananya", "otc_director": "rajiv", "india_director": "suresh", "cft": "meera",
       "legal": "pooja", "quality": "amit", "pv": "neha", "reg_head": "sanjay", "reg_team": "divya",
       "artwork": "ritika", "commercial": "arjun", "cmo": "rakesh"}


def tomorrow(days=1):
    return (datetime.utcnow() + timedelta(days=days)).date().isoformat()


@pytest.fixture()
def api():
    """Empty database with the demo people; returns a helper to act as anyone."""
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        for name, key, role, title, _ in USERS:
            db.add(User(name=name, email=key + DOM, role=role, title=title, password_hash=hash_password(PASSWORD)))
        db.commit()
        by = {u.email: u for u in db.query(User)}
        for _, key, _, _, boss in USERS:
            if boss:
                by[key + DOM].manager_id = by[boss + DOM].id
        db.commit()
    import app.main as _main
    _main._fails.clear()
    client = TestClient(app)

    class Api:
        tokens: dict = {}

        def as_(self, who: str):
            if who not in self.tokens:
                r = client.post("/api/auth/login", json={"email": who + DOM, "password": PASSWORD})
                assert r.status_code == 200, r.text
                self.tokens[who] = r.json()["token"]
            return {"Authorization": "Bearer " + self.tokens[who]}

        def get(self, who, url):
            return client.get(url, headers=self.as_(who))

        def client_delete(self, who, url):
            return client.delete(url, headers=self.as_(who))

        def post(self, who, url, **kw):
            return client.post(url, headers=self.as_(who), **kw)

        def detail(self, who, pid):
            r = self.get(who, f"/api/projects/{pid}")
            assert r.status_code == 200, r.text
            return r.json()

        def create(self, who="ananya", ptype="development", title="Test Product"):
            r = self.post(who, "/api/projects", json={"title": title, "ptype": ptype, "market": "AU"})
            assert r.status_code == 200, r.text
            return r.json()["id"]

        # ---- documents
        def file(self, who, pid, step, doc_type, name="doc.pdf", n=1):
            files = [("files", (name if n == 1 else f"{i}-{name}", b"%PDF-demo", "application/pdf")) for i in range(n)]
            r = self.post(who, f"/api/projects/{pid}/documents", data={"step_key": step, "doc_type": doc_type}, files=files)
            assert r.status_code == 200, r.text
            return r.json()["ids"]

        def link(self, who, pid, step, doc_type, url="https://share.example.test/doc"):
            r = self.post(who, f"/api/projects/{pid}/links", json={"title": "Shared doc", "url": url, "step_key": step,
                                                                  "doc_type": doc_type})
            assert r.status_code == 200, r.text
            return r.json()["ids"]

        # ---- acting on steps
        def card(self, who, pid, step=None):
            d = self.detail(who, pid)
            for a in d["actions"]:
                if (step is None or a["key"] == step) and (a["can_act"] or step):
                    return a
            raise AssertionError(f"{who} has no step {step} on project {pid}: {[x['key'] for x in d['actions']]}")

        def fill(self, who, pid, a):
            """Add the documents / details / ticks a step asks for, like a person would."""
            for i, dd in enumerate(a["docs"]):
                if dd["required"] and not dd["items"] and dd.get("editable", True):
                    if i % 2:
                        self.link(who, pid, a["key"], dd["key"])
                    else:
                        self.file(who, pid, a["key"], dd["key"])
            data = {}
            for f in a["fields"]:
                t = f["type"]
                data[f["key"]] = (f["value"] or {"number": "5", "date": tomorrow(30), "textarea": "Please clarify the shelf life.",
                                                 "select": (f.get("options") or ["x"])[0]}.get(t, "Sunrise Pharma"))
            return data, [c["key"] for c in a["checks"]]

        def do(self, who, pid, step=None, option=None, note="", expect=200, fill=True, data=None, checks=None, nexts=None):
            a = self.card(who, pid, step)
            d2, c2 = self.fill(who, pid, a) if fill and (option is None or option in ("approve", "complete", "incomplete")
                                                         or a["mode"] == "action") else ({}, [])
            r = self.post(who, f"/api/projects/{pid}/runs/{a['run_id']}/act",
                          json={"option": option, "note": note, "data": data if data is not None else d2,
                                "checks": checks if checks is not None else c2, "nexts": nexts or {}})
            assert r.status_code == expect, f"{who} {a['key']} {option}: {r.status_code} {r.text}"
            return r.json()

        def sendback(self, who, pid, step, target, note="Please redo this.", expect=200, doc_ids=None, **extra):
            a = self.card(who, pid, step)
            r = self.post(who, f"/api/projects/{pid}/runs/{a['run_id']}/sendback",
                          json={"target": target, "note": note, "doc_ids": doc_ids or [], **extra})
            assert r.status_code == expect, f"{who} sendback {step}->{target}: {r.status_code} {r.text}"
            return r.json()

        def active(self, pid):
            return [a["key"] for a in self.detail("sneha", pid)["actions"]]

    Api.tokens = {}
    return Api()
