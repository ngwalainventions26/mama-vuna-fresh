"""Passwords, sessions, roles, CSRF and data scoping."""
import hashlib
import hmac
import secrets
import time
from typing import Optional

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Query, Session

from . import models as m
from .config import settings
from .db import get_db

ITERATIONS = 260_000


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), ITERATIONS).hex()
    return f"pbkdf2_sha256${ITERATIONS}${salt}${dk}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, iters, salt, dk = stored.split("$")
        test = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), int(iters)).hex()
        return hmac.compare_digest(test, dk)
    except Exception:
        return False


def password_problem(pw: str) -> Optional[str]:
    if len(pw) < 10:
        return "Use at least 10 characters."
    if pw.isdigit() or pw.isalpha():
        return "Mix letters with numbers or symbols."
    return None


# ---- login throttling (per IP, in memory) ------------------------------------
_attempts: dict[str, list[float]] = {}


def too_many_attempts(ip: str) -> bool:
    now = time.time()
    _attempts[ip] = [x for x in _attempts.get(ip, []) if now - x < 900]
    return len(_attempts[ip]) >= 8


def note_failed_attempt(ip: str) -> None:
    _attempts.setdefault(ip, []).append(time.time())


# ---- session user -------------------------------------------------------------
class LoginRequired(Exception):
    pass


def current_user(request: Request, db: Session = Depends(get_db)) -> m.User:
    uid = request.session.get("uid")
    user = db.get(m.User, uid) if uid else None
    if not user or not user.active:
        request.session.clear()
        raise LoginRequired()
    return user


def require(*roles: str):
    def dep(user: m.User = Depends(current_user)) -> m.User:
        if user.role not in roles:
            raise HTTPException(403, "You do not have access to this page.")
        return user
    return dep


admin_only = require("admin")
managers = require("admin", "district_officer")
staff = require("admin", "district_officer", "chw")


# ---- CSRF -----------------------------------------------------------------------
def csrf_token(request: Request) -> str:
    tok = request.session.get("csrf")
    if not tok:
        tok = secrets.token_urlsafe(32)
        request.session["csrf"] = tok
    return tok


async def check_csrf(request: Request) -> None:
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return
    sent = request.headers.get("x-csrf-token")
    if not sent:
        form = await request.form()
        sent = form.get("csrf")
    if not sent or not hmac.compare_digest(str(sent), request.session.get("csrf", "")):
        raise HTTPException(400, "Your form expired. Go back, refresh the page and try again.")


# ---- data scoping -----------------------------------------------------------------
def scope_mothers(q: Query, user: m.User) -> Query:
    if user.role == "admin":
        return q
    if user.role == "district_officer":
        q = q.filter(m.Mother.region == user.region)
        return q.filter(m.Mother.district == user.district) if user.district else q
    return q.filter((m.Mother.chw_id == user.id) |
                    ((m.Mother.chw_id.is_(None)) & (m.Mother.district == user.district)))


def scope_area(q: Query, model, user: m.User) -> Query:
    """For helpers, groups, facilities: by region/district."""
    if user.role == "admin":
        return q
    if user.region:
        q = q.filter(model.region == user.region)
    if user.district:
        q = q.filter(model.district == user.district)
    return q


def can_see_mother(user: m.User, mother: m.Mother) -> bool:
    if user.role == "admin":
        return True
    if user.role == "district_officer":
        return mother.region == user.region and (not user.district or mother.district == user.district)
    return mother.chw_id == user.id or (mother.chw_id is None and mother.district == user.district)


def in_area(user: m.User, region: str, district: str) -> bool:
    if user.role == "admin":
        return True
    return (not user.region or region == user.region) and (not user.district or district == user.district)


def can_see_area(user: m.User, obj) -> bool:
    if user.role == "admin":
        return True
    return (not user.region or obj.region == user.region) and (not user.district or obj.district == user.district)


def api_token_ok(request: Request) -> bool:
    import os
    tok = os.getenv("API_TOKEN", "")
    auth = request.headers.get("authorization", "")
    return bool(tok) and hmac.compare_digest(auth, f"Bearer {tok}")
