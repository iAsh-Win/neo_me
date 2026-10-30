import os
import sys
import tempfile
from pathlib import Path

_tmp = tempfile.mkdtemp(prefix="neo_test_")
os.environ["NEO_DATA_DIR"] = _tmp
os.environ["NEO_AUTOSEED"] = "0"
os.environ["NEO_BACKGROUND"] = "0"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.db import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import User  # noqa: E402
from app.seed import DOM, PASSWORD, USERS  # noqa: E402
from app.security import hash_password  # noqa: E402


@pytest.fixture()
def api():
    """Empty database with one person per role; returns a helper to act as anyone."""
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

        def post(self, who, url, **kw):
            return client.post(url, headers=self.as_(who), **kw)

        def act(self, who, pid, option=None, note="", text=None, expect=200):
            r = self.post(who, f"/api/projects/{pid}/act", json={"option": option, "note": note, "text": text})
            assert r.status_code == expect, f"{who} {option}: {r.status_code} {r.text}"
            return r.json()

        def upload(self, who, pid, step):
            r = self.post(who, f"/api/projects/{pid}/documents", data={"step_key": step},
                          files={"file": ("doc.pdf", b"%PDF-demo", "application/pdf")})
            assert r.status_code == 200, r.text

        def step(self, who, pid):
            return self.get(who, f"/api/projects/{pid}").json()["current_step"]

        def create(self, who="ananya", ptype="development", title="Test Product"):
            r = self.post(who, "/api/projects", json={"title": title, "ptype": ptype, "market": "AU"})
            assert r.status_code == 200, r.text
            return r.json()["id"]

    Api.tokens = {}
    return Api()
