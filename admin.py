"""Administration: users, crop calendar, facilities, messages, audit log, scheduler, simulator, training data."""
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse, PlainTextResponse, RedirectResponse
from sqlalchemy.orm import Session

from .. import models as m
from ..db import get_db
from ..security import (admin_only, check_csrf, hash_password, in_area, managers, password_problem, scope_area,
                        staff)
from ..services import demo, reference, scheduler
from ..services.common import audit, normalize_phone
from ..services.sms_inbound import handle_inbound
from ..services.ussd import handle as ussd_handle
from ..web import flash, render

router = APIRouter(include_in_schema=False)
CSRF = [Depends(check_csrf)]


# ------------------------------------------------------------------ users
@router.get("/admin/users")
def users(request: Request, user: m.User = Depends(managers), db: Session = Depends(get_db)):
    q = db.query(m.User)
    if user.role != "admin":
        q = q.filter(m.User.role == "chw", m.User.region == user.region)
        if user.district:
            q = q.filter(m.User.district == user.district)
    rows = q.order_by(m.User.role, m.User.name).all()
    regions = reference.regions(db)
    return render(request, "users.html", user, rows=rows, regions=regions,
                  locs={r: reference.districts(db, r) for r in regions})


@router.post("/admin/users/new", dependencies=CSRF)
def user_create(request: Request, name: str = Form(...), email: str = Form(...), phone: str = Form(""),
                role: str = Form("chw"), region: str = Form(""), district: str = Form(""), ward: str = Form(""),
                password: str = Form(...), user: m.User = Depends(managers), db: Session = Depends(get_db)):
    if user.role != "admin" and (role != "chw" or not in_area(user, region, district)):
        raise HTTPException(403, "District officers can only add CHWs in their own district.")
    if role not in m.ROLES:
        role = "chw"
    if db.query(m.User).filter(m.User.email == email.strip().lower()).first():
        flash(request, "A user with this email already exists.", "err")
    elif problem := password_problem(password):
        flash(request, "Password: " + problem, "err")
    elif role != "admin" and not region:
        flash(request, "Choose a region (and district) for this user.", "err")
    else:
        u = m.User(name=name.strip(), email=email.strip().lower(), phone=normalize_phone(phone) or None, role=role,
                   region=region or None, district=district or None, ward=ward.strip().title() or None,
                   password_hash=hash_password(password))
        db.add(u)
        db.flush()
        audit(db, user, "user_created", "user", u.id, role)
        db.commit()
        flash(request, f"{u.name} can now sign in with {u.email}.")
    return RedirectResponse("/admin/users", 303)


@router.post("/admin/users/{uid}", dependencies=CSRF)
def user_update(request: Request, uid: int, role: str = Form(...), region: str = Form(""), district: str = Form(""),
                ward: str = Form(""), phone: str = Form(""), active: str = Form(""), new_password: str = Form(""),
                user: m.User = Depends(managers), db: Session = Depends(get_db)):
    u = db.get(m.User, uid)
    if not u:
        raise HTTPException(404, "User not found.")
    if user.role != "admin" and (u.role != "chw" or not in_area(user, u.region, u.district)):
        raise HTTPException(403, "You can only manage CHWs in your district.")
    if u.id == user.id and (not active or role != user.role):
        flash(request, "You cannot remove your own access.", "err")
        return RedirectResponse("/admin/users", 303)
    u.role = role if (user.role == "admin" and role in m.ROLES) else u.role
    u.region, u.district = region or u.region, district or None
    u.ward, u.phone, u.active = ward.strip().title() or None, normalize_phone(phone) or None, bool(active)
    if new_password:
        if problem := password_problem(new_password):
            flash(request, "Password: " + problem, "err")
            return RedirectResponse("/admin/users", 303)
        u.password_hash = hash_password(new_password)
    audit(db, user, "user_updated", "user", u.id)
    db.commit()
    flash(request, f"{u.name} saved.")
    return RedirectResponse("/admin/users", 303)


# ------------------------------------------------------------------ crop calendar
@router.get("/admin/calendar")
def calendar(request: Request, region: str = "", user: m.User = Depends(staff), db: Session = Depends(get_db)):
    regs = [r for (r,) in db.query(m.CropActivity.region).distinct().order_by(m.CropActivity.region)]
    q = db.query(m.CropActivity)
    if region:
        q = q.filter(m.CropActivity.region == region)
    rows = q.order_by(m.CropActivity.region, m.CropActivity.crop, m.CropActivity.start_month).all()
    return render(request, "calendar.html", user, rows=rows, regions=regs, region=region,
                  total=db.query(m.CropActivity).count(),
                  crops=db.query(m.CropActivity.crop).distinct().count())


@router.get("/admin/calendar.csv")
def calendar_download(user: m.User = Depends(staff), db: Session = Depends(get_db)):
    return PlainTextResponse(reference.calendar_csv(db), media_type="text/csv",
                             headers={"Content-Disposition": 'attachment; filename="crop_labour_calendar.csv"'})


@router.post("/admin/calendar/upload", dependencies=CSRF)
async def calendar_upload(request: Request, file: UploadFile = File(...), user: m.User = Depends(admin_only),
                          db: Session = Depends(get_db)):
    try:
        rows = reference.parse_calendar_csv((await file.read()).decode("utf-8", errors="replace"))
        n = reference.replace_calendar(db, rows)
        audit(db, user, "calendar_replaced", detail=f"{n} rows from {file.filename}")
        db.commit()
        flash(request, f"Loaded {n} rows from {file.filename}. New requests will use them.")
    except ValueError as e:
        flash(request, f"{e}", "err")
    return RedirectResponse("/admin/calendar", 303)


@router.post("/admin/calendar/reset", dependencies=CSRF)
def calendar_reset(request: Request, user: m.User = Depends(admin_only), db: Session = Depends(get_db)):
    rows = reference.parse_calendar_csv((reference.DATA / "crop_calendar.csv").read_text(encoding="utf-8"))
    n = reference.replace_calendar(db, rows)
    audit(db, user, "calendar_reset", detail=str(n))
    db.commit()
    flash(request, f"Built-in calendar restored ({n} rows).")
    return RedirectResponse("/admin/calendar", 303)


# ------------------------------------------------------------------ facilities
@router.get("/admin/facilities")
def facilities(request: Request, user: m.User = Depends(staff), db: Session = Depends(get_db)):
    rows = scope_area(db.query(m.Facility), m.Facility, user).order_by(m.Facility.region, m.Facility.district,
                                                                       m.Facility.name).all()
    regions = reference.regions(db)
    return render(request, "facilities.html", user, rows=rows, regions=regions,
                  locs={r: reference.districts(db, r) for r in regions})


@router.post("/admin/facilities/new", dependencies=CSRF)
def facility_create(request: Request, name: str = Form(...), level: str = Form("dispensary"), region: str = Form(...),
                    district: str = Form(...), ward: str = Form(""), phone: str = Form(""),
                    offers_emonc: str = Form(""), user: m.User = Depends(managers), db: Session = Depends(get_db)):
    if not in_area(user, region, district):
        raise HTTPException(403, "You can only add facilities in your own district.")
    f = m.Facility(name=name.strip(), level=level, region=region, district=district, ward=ward.strip().title() or None,
                   phone=normalize_phone(phone) or None, offers_emonc=bool(offers_emonc))
    db.add(f)
    db.flush()
    audit(db, user, "facility_added", "facility", f.id)
    db.commit()
    flash(request, f"{f.name} added.")
    return RedirectResponse("/admin/facilities", 303)


@router.post("/admin/facilities/{fid}/toggle", dependencies=CSRF)
def facility_toggle(request: Request, fid: int, user: m.User = Depends(managers), db: Session = Depends(get_db)):
    f = db.get(m.Facility, fid)
    if not f or not in_area(user, f.region, f.district):
        raise HTTPException(404, "Facility not found.")
    f.active = not f.active
    db.commit()
    return RedirectResponse("/admin/facilities", 303)


# ------------------------------------------------------------------ messages, audit, system
@router.get("/admin/messages")
def messages(request: Request, phone: str = "", user: m.User = Depends(managers), db: Session = Depends(get_db)):
    q = db.query(m.Message)
    if phone:
        q = q.filter(m.Message.phone.like(f"%{phone.strip()[-9:]}%"))
    rows = q.order_by(m.Message.id.desc()).limit(300).all()
    failed = db.query(m.Message).filter(m.Message.status == "failed").count()
    return render(request, "messages.html", user, rows=rows, phone=phone, failed=failed)


@router.get("/admin/audit")
def audit_log(request: Request, user: m.User = Depends(admin_only), db: Session = Depends(get_db)):
    rows = db.query(m.AuditLog).order_by(m.AuditLog.id.desc()).limit(400).all()
    return render(request, "audit.html", user, rows=rows)


@router.get("/admin/system")
def system(request: Request, user: m.User = Depends(admin_only), db: Session = Depends(get_db)):
    from ..config import settings
    state = db.get(m.SystemState, "scheduler_last_run")
    return render(request, "system.html", user, state=state.value if state else None, s=settings,
                  demo_mothers=db.query(m.Mother).filter(m.Mother.is_demo.is_(True)).count(),
                  ussd_sessions=db.query(m.UssdLog).count())


@router.post("/admin/system/run", dependencies=CSRF)
def system_run(request: Request, user: m.User = Depends(admin_only), db: Session = Depends(get_db)):
    res = scheduler.run_cycle(db)
    audit(db, user, "scheduler_run", detail=str(res))
    db.commit()
    flash(request, "Cycle finished: " + ", ".join(f"{k} {v}" for k, v in res.items()))
    return RedirectResponse(request.headers.get("referer") or "/admin/system", 303)


@router.post("/admin/system/demo", dependencies=CSRF)
def system_demo(request: Request, action: str = Form(...), user: m.User = Depends(admin_only),
                db: Session = Depends(get_db)):
    if action == "load":
        n = demo.load(db)
        flash(request, f"Loaded training data ({n} mothers) in Mvomero, Morogoro. It is excluded from reports."
              if n else "Training data is already loaded.")
    else:
        n = demo.remove(db)
        flash(request, f"Removed training data ({n} mothers).")
    audit(db, user, f"demo_{action}", detail=str(n))
    db.commit()
    return RedirectResponse("/admin/system", 303)


# ------------------------------------------------------------------ phone simulator
@router.get("/admin/simulator")
def simulator(request: Request, user: m.User = Depends(admin_only), db: Session = Depends(get_db)):
    from ..config import settings
    return render(request, "simulator.html", user, code=settings.USSD_SERVICE_CODE)


@router.post("/admin/simulator/ussd", dependencies=CSRF)
async def simulator_ussd(request: Request, user: m.User = Depends(admin_only), db: Session = Depends(get_db)):
    body = await request.json()
    phone = normalize_phone(body.get("phone", ""))
    if not phone:
        return JSONResponse({"reply": "END Enter a phone number first."})
    reply = ussd_handle(db, phone, body.get("text", ""))
    db.add(m.UssdLog(session_id="simulator", phone=phone, text=body.get("text", ""), response=reply[:500]))
    db.commit()
    return JSONResponse({"reply": reply})


@router.post("/admin/simulator/sms", dependencies=CSRF)
async def simulator_sms(request: Request, user: m.User = Depends(admin_only), db: Session = Depends(get_db)):
    body = await request.json()
    phone = normalize_phone(body.get("phone", ""))
    if phone and body.get("text"):
        handle_inbound(db, phone, body["text"])
    return JSONResponse({"ok": True})


@router.get("/admin/simulator/inbox")
def simulator_inbox(phone: str, user: m.User = Depends(admin_only), db: Session = Depends(get_db)):
    phone = normalize_phone(phone)
    rows = db.query(m.Message).filter(m.Message.phone == phone).order_by(m.Message.id).limit(100).all()
    return JSONResponse([{"dir": r.direction, "body": r.body, "at": r.created_at.strftime("%d/%m %H:%M"),
                          "kind": r.kind or ""} for r in rows])
