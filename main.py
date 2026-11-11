"""Mama Vuna Fresh: application entry point.

Run locally:  uvicorn app.main:app --reload
"""
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.sessions import SessionMiddleware

from . import models as m
from .config import BASE_DIR, settings
from .db import Base, SessionLocal, engine
from .routers import admin, api, auth, pages, reports, telecom
from .security import LoginRequired, hash_password
from .services import reference, scheduler

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("mamavuna")


def init_database() -> None:
    Base.metadata.create_all(engine)
    db = SessionLocal()
    try:
        reference.load_reference_data(db)
        if db.query(m.User).count() == 0:
            if settings.ADMIN_PASSWORD:
                db.add(m.User(name=settings.ADMIN_NAME, email=settings.ADMIN_EMAIL.lower(), role="admin",
                              password_hash=hash_password(settings.ADMIN_PASSWORD)))
                db.commit()
                log.info("Created first administrator %s", settings.ADMIN_EMAIL)
            else:
                log.warning("No users exist. Set ADMIN_PASSWORD (and ADMIN_EMAIL) or run scripts/create_admin.py")
    finally:
        db.close()


@asynccontextmanager
async def lifespan(_: FastAPI):
    if settings.ENV == "production" and settings.SECRET_KEY == "dev-only-change-me":
        raise RuntimeError("Set SECRET_KEY in the environment before running in production.")
    init_database()
    task = asyncio.create_task(scheduler.loop()) if settings.SCHEDULER_ENABLED else None
    yield
    if task:
        task.cancel()


app = FastAPI(title="Mama Vuna Fresh API", version="1.0.0", lifespan=lifespan,
              description="Community labour support and maternal protection for pregnant women in Tanzania. "
                          "By Ngwala Inventions.",
              docs_url="/api/docs", redoc_url=None, openapi_url="/api/openapi.json")
app.add_middleware(SessionMiddleware, secret_key=settings.SECRET_KEY, session_cookie="mvf_session",
                   max_age=60 * 60 * 12, same_site="lax", https_only=settings.SESSION_HTTPS_ONLY)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

for r in (telecom.router, auth.router, pages.router, admin.router, reports.router, api.router):
    app.include_router(r)


@app.exception_handler(LoginRequired)
async def _login_required(request: Request, _):
    nxt = request.url.path if request.method == "GET" else "/"
    return RedirectResponse(f"/login?next={nxt}", status_code=303)


@app.exception_handler(StarletteHTTPException)
async def _http_error(request: Request, exc: StarletteHTTPException):
    if request.url.path.startswith(("/api", "/ussd", "/sms")):
        from fastapi.responses import JSONResponse
        return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)
    from .web import render
    return render(request, "error.html", status_code=exc.status_code, code=exc.status_code, detail=exc.detail)


@app.get("/health", include_in_schema=False)
def health():
    return {"status": "ok"}


@app.get("/robots.txt", include_in_schema=False, response_class=HTMLResponse)
def robots():
    return HTMLResponse("User-agent: *\nDisallow: /\n", media_type="text/plain")
