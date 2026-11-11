from datetime import datetime

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from .. import models as m
from ..db import get_db
from ..security import (check_csrf, current_user, note_failed_attempt, password_problem, too_many_attempts,
                        verify_password, hash_password)
from ..services.common import audit
from ..web import flash, render

router = APIRouter(include_in_schema=False)


def _safe_next(nxt: str) -> str:
    return nxt if nxt.startswith("/") and not nxt.startswith("//") else "/"


@router.get("/login")
def login_page(request: Request, next: str = "/"):
    if request.session.get("uid"):
        return RedirectResponse(_safe_next(next), 303)
    return render(request, "login.html", next=_safe_next(next))


@router.post("/login", dependencies=[Depends(check_csrf)])
def login(request: Request, email: str = Form(...), password: str = Form(...), next: str = Form("/"),
          db: Session = Depends(get_db)):
    ip = request.client.host if request.client else "?"
    if too_many_attempts(ip):
        return render(request, "login.html", next=next, error="Too many attempts. Wait 15 minutes and try again.",
                      status_code=429)
    user = db.query(m.User).filter(m.User.email == email.strip().lower()).first()
    if not user or not user.active or not verify_password(password, user.password_hash):
        note_failed_attempt(ip)
        return render(request, "login.html", next=next, email=email,
                      error="Email or password is not correct.", status_code=401)
    request.session.clear()
    request.session["uid"] = user.id
    user.last_login = datetime.now()
    audit(db, user, "login")
    db.commit()
    return RedirectResponse(_safe_next(next), 303)


@router.post("/logout", dependencies=[Depends(check_csrf)])
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", 303)


@router.get("/account")
def account(request: Request, user: m.User = Depends(current_user)):
    return render(request, "account.html", user)


@router.post("/account/password", dependencies=[Depends(check_csrf)])
def change_password(request: Request, current: str = Form(...), new: str = Form(...), confirm: str = Form(...),
                    user: m.User = Depends(current_user), db: Session = Depends(get_db)):
    if not verify_password(current, user.password_hash):
        flash(request, "Your current password is not correct.", "err")
    elif new != confirm:
        flash(request, "The new passwords do not match.", "err")
    elif problem := password_problem(new):
        flash(request, problem, "err")
    else:
        user.password_hash = hash_password(new)
        audit(db, user, "password_changed", "user", user.id)
        db.commit()
        flash(request, "Password changed.")
    return RedirectResponse("/account", 303)
