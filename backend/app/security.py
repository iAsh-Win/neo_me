import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta

import jwt
from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from .db import DATA_DIR, get_db
from .models import User


def _secret() -> str:
    env = os.environ.get("NEO_SECRET")
    if env:
        return env
    f = DATA_DIR / "secret.key"
    if not f.exists():
        f.write_text(secrets.token_hex(32))
    return f.read_text().strip()


def hash_password(pw: str) -> str:
    salt = secrets.token_hex(8)
    h = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt.encode(), 120_000).hex()
    return f"{salt}${h}"


def verify_password(pw: str, stored: str) -> bool:
    try:
        salt, h = stored.split("$")
    except ValueError:
        return False
    test = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt.encode(), 120_000).hex()
    return hmac.compare_digest(test, h)


def make_token(user: User) -> str:
    return jwt.encode({"sub": str(user.id), "exp": datetime.utcnow() + timedelta(hours=12)},
                      _secret(), algorithm="HS256")


def current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = None
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        token = auth[7:]
    token = token or request.query_params.get("token")   # used by download links
    if not token:
        raise HTTPException(401, "Please sign in.")
    try:
        data = jwt.decode(token, _secret(), algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(401, "Your session has ended. Please sign in again.")
    user = db.get(User, int(data["sub"]))
    if not user or not user.active:
        raise HTTPException(401, "This account is not active.")
    return user
