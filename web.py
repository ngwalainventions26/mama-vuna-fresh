"""Template set-up shared by the web routers."""
from datetime import date

from fastapi import Request
from fastapi.templating import Jinja2Templates

from . import models as m
from .config import BASE_DIR, settings
from .security import csrf_token
from .services.common import fmt_date, label_for, mask_phone, task_label
from .services.pregnancy import gest_week

templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
templates.env.globals.update(
    settings=settings, m=m, fmt_date=fmt_date, mask_phone=mask_phone, task_label=task_label,
    label_for=label_for, gest_week=gest_week, today=date.today,
)


def render(request: Request, name: str, user=None, status_code: int = 200, **ctx):
    flash = request.session.pop("flash", None)
    return templates.TemplateResponse(request, name, {"user": user, "csrf": csrf_token(request), "flash": flash,
                                                      **ctx}, status_code=status_code)


def flash(request: Request, text: str, kind: str = "ok") -> None:
    request.session["flash"] = {"text": text, "kind": kind}
