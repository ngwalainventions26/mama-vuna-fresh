"""Day-to-day pages for CHWs, district officers and administrators."""
from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import or_
from sqlalchemy.orm import Session

from .. import models as m
from ..db import get_db
from ..security import (can_see_area, can_see_mother, check_csrf, in_area, scope_area, scope_mothers, staff)
from ..services import indicators, ledger, reference
from ..services.common import audit, normalize_phone
from ..services.matching import create_request, dispatch, rank
from ..services.mothers import (change_edd, find_or_create_group, register_helper, register_mother, report_birth,
                                welcome_sms)
from ..services.pregnancy import gest_week, protected_period, windows
from ..services.sms import send_sms
from ..services.texts import t
from ..services.ussd import parse_date
from ..web import flash, render

router = APIRouter(include_in_schema=False)
CSRF = [Depends(check_csrf)]


def _date(v: str) -> Optional[date]:
    if not v:
        return None
    try:
        return date.fromisoformat(v)
    except ValueError:
        return parse_date(v)


def _int(v) -> Optional[int]:
    try:
        return int(v) if str(v).strip() else None
    except (TypeError, ValueError):
        return None


def _bool(v) -> Optional[bool]:
    return {"yes": True, "no": False}.get(v)


def _mother(db: Session, user: m.User, mid: int) -> m.Mother:
    mo = db.get(m.Mother, mid)
    if not mo or not can_see_mother(user, mo):
        raise HTTPException(404, "Mother not found.")
    return mo


def _back(path: str):
    return RedirectResponse(path, 303)


# ------------------------------------------------------------------ dashboard
@router.get("/")
def dashboard(request: Request, user: m.User = Depends(staff), db: Session = Depends(get_db)):
    mq = scope_mothers(db.query(m.Mother), user)
    ids = [x.id for x in mq.with_entities(m.Mother.id)]
    today = date.today()
    dangers = (db.query(m.DangerReport).filter(m.DangerReport.mother_id.in_(ids),
                                               m.DangerReport.status.in_(["new", "contacted"]))
               .order_by(m.DangerReport.reported_at.desc()).limit(10).all())
    unfilled = (db.query(m.SupportRequest).filter(m.SupportRequest.mother_id.in_(ids),
                                                  m.SupportRequest.status == "unfilled")
                .order_by(m.SupportRequest.start_date).limit(10).all())
    to_verify = (db.query(m.SupportRequest).filter(m.SupportRequest.mother_id.in_(ids),
                                                   m.SupportRequest.status == "accepted",
                                                   m.SupportRequest.end_date <= today + timedelta(days=7))
                 .order_by(m.SupportRequest.end_date).limit(10).all())
    waiting = (db.query(m.SupportRequest).filter(m.SupportRequest.mother_id.in_(ids),
                                                 m.SupportRequest.status.in_(["open", "alerting"]))
               .count())
    due_soon = (mq.filter(m.Mother.status == "pregnant", m.Mother.edd <= today + timedelta(days=21))
                .order_by(m.Mother.edd).limit(10).all())
    no_chw = mq.filter(m.Mother.chw_id.is_(None), m.Mother.status != "closed").count() \
        if user.role != "chw" else 0
    state = db.get(m.SystemState, "scheduler_last_run")
    return render(request, "dashboard.html", user, k=indicators.compute(db, user), dangers=dangers,
                  unfilled=unfilled, to_verify=to_verify, waiting=waiting, due_soon=due_soon, no_chw=no_chw,
                  scheduler=state.value if state else None)


# ------------------------------------------------------------------ mothers
@router.get("/mothers")
def mothers_list(request: Request, q: str = "", status: str = "active", district: str = "", livelihood: str = "",
                 user: m.User = Depends(staff), db: Session = Depends(get_db)):
    query = scope_mothers(db.query(m.Mother), user)
    if q:
        like = f"%{q.strip()}%"
        query = query.filter(or_(m.Mother.name.ilike(like), m.Mother.phone.ilike(like), m.Mother.code.ilike(like),
                                 m.Mother.village.ilike(like)))
    if status == "active":
        query = query.filter(m.Mother.status.in_(["pregnant", "delivered"]))
    elif status:
        query = query.filter(m.Mother.status == status)
    if district:
        query = query.filter(m.Mother.district == district)
    if livelihood:
        query = query.filter(m.Mother.livelihood == livelihood)
    rows = query.order_by(m.Mother.edd).limit(500).all()
    dists = sorted({d for (d,) in scope_mothers(db.query(m.Mother), user).with_entities(m.Mother.district).distinct()})
    return render(request, "mothers.html", user, rows=rows, q=q, status=status, district=district,
                  livelihood=livelihood, districts=dists)


def _form_ctx(db: Session, user: m.User):
    regions = reference.regions(db)
    locs = {r: reference.districts(db, r) for r in regions}
    crops = {r: reference.crops_for_region(db, r) for r in regions}
    chws = scope_area(db.query(m.User).filter(m.User.role == "chw", m.User.active.is_(True)), m.User, user).all()
    return dict(regions=regions, locs=locs, crops=crops, chws=chws)


@router.get("/mothers/new")
def mother_new(request: Request, user: m.User = Depends(staff), db: Session = Depends(get_db)):
    return render(request, "mother_form.html", user, mo=None, **_form_ctx(db, user))


@router.post("/mothers/new", dependencies=CSRF)
def mother_create(request: Request, name: str = Form(...), phone: str = Form(...), age: str = Form(""),
                  region: str = Form(...), district: str = Form(...), ward: str = Form(""), village: str = Form(""),
                  setting: str = Form("rural"), livelihood: str = Form("farmer"), crop: str = Form(""),
                  edd: str = Form(...), edd_source: str = Form("chw"), gravida: str = Form(""),
                  language: str = Form("sw"), chw_id: str = Form(""), consent: str = Form(""),
                  user: m.User = Depends(staff), db: Session = Depends(get_db)):
    phone_n = normalize_phone(phone)
    d = _date(edd)
    err = None
    if not consent:
        err = "Confirm that the mother agreed to register."
    elif not phone_n.startswith("+") or len(phone_n) < 12:
        err = "Enter a valid phone number, for example 0754 123 456."
    elif db.query(m.Mother).filter(m.Mother.phone == phone_n).first():
        err = "A mother with this phone number is already registered."
    elif not d or not (date.today() - timedelta(days=14) <= d <= date.today() + timedelta(days=300)):
        err = "The due date must be within the next 10 months."
    elif not in_area(user, region, district):
        err = "You can only register mothers in your own district."
    if err:
        flash(request, err, "err")
        return _back("/mothers/new")
    chw = db.get(m.User, _int(chw_id)) if _int(chw_id) else (user if user.role == "chw" else None)
    mo = register_mother(db, name=name, phone=phone_n, region=region, district=district, ward=ward,
                         village=village, setting=setting, livelihood=livelihood, crop=crop or None,
                         age=_int(age), language=language, edd=d, edd_source=edd_source, via="web", chw=chw,
                         gravida=_int(gravida))
    audit(db, user, "mother_registered", "mother", mo.id)
    db.commit()
    flash(request, f"{mo.name} registered as {mo.code}. A welcome SMS was sent.")
    return _back(f"/mothers/{mo.id}")


@router.get("/mothers/{mid}")
def mother_detail(request: Request, mid: int, user: m.User = Depends(staff), db: Session = Depends(get_db)):
    mo = _mother(db, user, mid)
    by_key = {r.window_key: r for r in mo.requests if r.window_key}
    wins = [(w, by_key.get(w.key)) for w in windows(db, mo)]
    p_start, p_end = protected_period(mo)
    facilities = db.query(m.Facility).filter(m.Facility.district == mo.district, m.Facility.active.is_(True)).all()
    chws = db.query(m.User).filter(m.User.role == "chw", m.User.active.is_(True),
                                   m.User.district == mo.district).all()
    return render(request, "mother_detail.html", user, mo=mo, wins=wins, p_start=p_start, p_end=p_end,
                  week=gest_week(mo.edd), facilities=facilities, chws=chws,
                  requests=sorted(mo.requests, key=lambda r: r.start_date),
                  visits=sorted(mo.visits, key=lambda v: v.visit_date, reverse=True),
                  dangers=sorted(mo.danger_reports, key=lambda d: d.reported_at, reverse=True))


@router.get("/mothers/{mid}/edit")
def mother_edit(request: Request, mid: int, user: m.User = Depends(staff), db: Session = Depends(get_db)):
    mo = _mother(db, user, mid)
    facilities = db.query(m.Facility).filter(m.Facility.district == mo.district, m.Facility.active.is_(True)).all()
    return render(request, "mother_form.html", user, mo=mo, facilities=facilities, **_form_ctx(db, user))


@router.post("/mothers/{mid}/edit", dependencies=CSRF)
def mother_update(request: Request, mid: int, name: str = Form(...), phone: str = Form(...), age: str = Form(""),
                  region: str = Form(...), district: str = Form(...), ward: str = Form(""),
                  village: str = Form(""), setting: str = Form("rural"), livelihood: str = Form("farmer"),
                  crop: str = Form(""), gravida: str = Form(""), language: str = Form("sw"),
                  chw_id: str = Form(""), facility_id: str = Form(""),
                  user: m.User = Depends(staff), db: Session = Depends(get_db)):
    mo = _mother(db, user, mid)
    phone_n = normalize_phone(phone)
    other = db.query(m.Mother).filter(m.Mother.phone == phone_n, m.Mother.id != mo.id).first()
    if other:
        flash(request, "Another mother already uses this phone number.", "err")
        return _back(f"/mothers/{mid}/edit")
    changed_farm = (mo.livelihood, mo.crop, mo.region) != (livelihood, crop or None, region)
    mo.name, mo.phone, mo.age = name.strip().title(), phone_n, _int(age)
    mo.region, mo.district = region, district
    mo.ward, mo.village = ward.strip().title() or None, village.strip().title() or None
    mo.setting, mo.livelihood = setting, livelihood
    mo.crop = crop or None if livelihood == "farmer" else None
    mo.gravida, mo.language = _int(gravida), language
    if user.role != "chw":
        mo.chw_id = _int(chw_id)
    mo.facility_id = _int(facility_id)
    if changed_farm:
        change_edd(db, mo, mo.edd, mo.edd_source)  # cancels future windows so new ones are created
    audit(db, user, "mother_updated", "mother", mo.id)
    db.commit()
    flash(request, "Details saved.")
    return _back(f"/mothers/{mid}")


@router.post("/mothers/{mid}/edd", dependencies=CSRF)
def mother_edd(request: Request, mid: int, edd: str = Form(...), source: str = Form("chw"),
               user: m.User = Depends(staff), db: Session = Depends(get_db)):
    mo = _mother(db, user, mid)
    d = _date(edd)
    if not d or not (date.today() - timedelta(days=14) <= d <= date.today() + timedelta(days=300)):
        flash(request, "The due date must be within the next 10 months.", "err")
    else:
        change_edd(db, mo, d, source)
        audit(db, user, "edd_changed", "mother", mo.id, f"{d} ({source})")
        db.commit()
        flash(request, "Due date updated. Future help periods will be recalculated in the next cycle.")
    return _back(f"/mothers/{mid}")


@router.post("/mothers/{mid}/birth", dependencies=CSRF)
def mother_birth(request: Request, mid: int, delivery_date: str = Form(...), place: str = Form("facility"),
                 gest_weeks: str = Form(""), birth_weight_g: str = Form(""), outcome: str = Form("live"),
                 mother_complication: str = Form(""), referred: str = Form(""), source: str = Form("chw"),
                 notes: str = Form(""), user: m.User = Depends(staff), db: Session = Depends(get_db)):
    mo = _mother(db, user, mid)
    d = _date(delivery_date)
    if not d or d > date.today():
        flash(request, "Enter the date of birth (not in the future).", "err")
        return _back(f"/mothers/{mid}")
    gw, bw = _int(gest_weeks), _int(birth_weight_g)
    if gw is not None and not (20 <= gw <= 45):
        flash(request, "Gestational age must be between 20 and 45 weeks.", "err")
        return _back(f"/mothers/{mid}")
    if bw is not None and not (300 <= bw <= 6500):
        flash(request, "Birth weight must be in grams, between 300 and 6500.", "err")
        return _back(f"/mothers/{mid}")
    if mo.status == "pregnant":
        report_birth(db, mo, d, via="web")
    mo.delivery_date = d
    oc = mo.outcome or m.BirthOutcome(mother_id=mo.id, delivery_date=d)
    oc.delivery_date, oc.place, oc.gest_weeks, oc.birth_weight_g, oc.outcome = d, place, gw, bw, outcome
    oc.mother_complication, oc.referred = _bool(mother_complication), _bool(referred)
    oc.source, oc.notes, oc.recorded_by = source, notes or None, user.id
    db.add(oc)
    audit(db, user, "birth_recorded", "mother", mo.id)
    db.commit()
    flash(request, "Birth outcome saved.")
    return _back(f"/mothers/{mid}")


@router.post("/mothers/{mid}/visit", dependencies=CSRF)
def mother_visit(request: Request, mid: int, visit_date: str = Form(...), kind: str = Form("home"),
                 did_heavy_work: str = Form(""), handled_pesticide: str = Form(""), help_received: str = Form(""),
                 anc_up_to_date: str = Form(""), danger_signs_seen: str = Form(""), notes: str = Form(""),
                 user: m.User = Depends(staff), db: Session = Depends(get_db)):
    mo = _mother(db, user, mid)
    d = _date(visit_date) or date.today()
    if d > date.today():
        flash(request, "The visit date cannot be in the future.", "err")
        return _back(f"/mothers/{mid}")
    v = m.Visit(mother_id=mo.id, chw_id=user.id, visit_date=d, kind=kind,
                gest_week=gest_week(mo.edd, d) if mo.status == "pregnant" or (mo.delivery_date and d < mo.delivery_date) else None,
                did_heavy_work=_bool(did_heavy_work), handled_pesticide=_bool(handled_pesticide),
                help_received=_bool(help_received), anc_up_to_date=_bool(anc_up_to_date),
                danger_signs_seen=_bool(danger_signs_seen), notes=notes or None)
    db.add(v)
    if v.danger_signs_seen:
        mo.risk_flag = "high"
    audit(db, user, "visit_recorded", "mother", mo.id)
    db.commit()
    flash(request, "Visit recorded.")
    return _back(f"/mothers/{mid}")


@router.post("/mothers/{mid}/risk", dependencies=CSRF)
def mother_risk(request: Request, mid: int, risk_flag: str = Form("normal"), risk_note: str = Form(""),
                user: m.User = Depends(staff), db: Session = Depends(get_db)):
    mo = _mother(db, user, mid)
    mo.risk_flag, mo.risk_note = risk_flag, risk_note or None
    audit(db, user, "risk_flag", "mother", mo.id, risk_flag)
    db.commit()
    flash(request, "Risk flag updated.")
    return _back(f"/mothers/{mid}")


@router.post("/mothers/{mid}/request", dependencies=CSRF)
def mother_request(request: Request, mid: int, window_key: str = Form(""), task_type: str = Form(""),
                   start: str = Form(""), days: str = Form("7"), user: m.User = Depends(staff),
                   db: Session = Depends(get_db)):
    mo = _mother(db, user, mid)
    if window_key:
        w = next((w for w in windows(db, mo) if w.key == window_key), None)
        if not w or db.query(m.SupportRequest).filter(m.SupportRequest.window_key == window_key).first():
            flash(request, "This help period already has a request.", "err")
            return _back(f"/mothers/{mid}")
        req = create_request(db, mo, w.task_type, w.activity, max(w.start, date.today()), w.end, w.est_hours,
                             source="chw", window_key=w.key)
    else:
        if task_type not in m.TASK_TYPES:
            flash(request, "Choose the kind of help.", "err")
            return _back(f"/mothers/{mid}")
        s = _date(start) or date.today()
        n = max(1, min(60, _int(days) or 7))
        sw, en = m.TASK_TYPES[task_type]
        req = create_request(db, mo, task_type, f"{sw} ({en.lower()})", s, s + timedelta(days=n - 1),
                             round(n / 7 * 4 * 4), source="chw")
    alert = dispatch(db, req)
    audit(db, user, "request_created", "request", req.id)
    db.commit()
    flash(request, f"Request sent to {alert.helper.name}." if alert else
          "No helper is free right now. The request is on the board for follow-up.",
          "ok" if alert else "warn")
    return _back(f"/mothers/{mid}")


@router.post("/mothers/{mid}/welcome", dependencies=CSRF)
def mother_welcome(request: Request, mid: int, user: m.User = Depends(staff), db: Session = Depends(get_db)):
    mo = _mother(db, user, mid)
    welcome_sms(db, mo)
    db.commit()
    flash(request, "Welcome SMS sent again.")
    return _back(f"/mothers/{mid}")


@router.post("/mothers/{mid}/close", dependencies=CSRF)
def mother_close(request: Request, mid: int, reason: str = Form(""), user: m.User = Depends(staff),
                 db: Session = Depends(get_db)):
    mo = _mother(db, user, mid)
    mo.status = "closed"
    for r in mo.requests:
        if r.status in ("open", "alerting", "unfilled"):
            r.status = "cancelled"
    audit(db, user, "mother_closed", "mother", mo.id, reason)
    db.commit()
    flash(request, "Record closed.")
    return _back(f"/mothers/{mid}")


# ------------------------------------------------------------------ support requests
def _req(db: Session, user: m.User, rid: int) -> m.SupportRequest:
    r = db.get(m.SupportRequest, rid)
    if not r or not can_see_mother(user, r.mother):
        raise HTTPException(404, "Request not found.")
    return r


@router.get("/requests")
def requests_board(request: Request, status: str = "", user: m.User = Depends(staff), db: Session = Depends(get_db)):
    ids = [x for (x,) in scope_mothers(db.query(m.Mother), user).with_entities(m.Mother.id)]
    q = db.query(m.SupportRequest).filter(m.SupportRequest.mother_id.in_(ids))
    counts = {s: q.filter(m.SupportRequest.status == s).count() for s in m.REQUEST_STATUS}
    if status:
        q = q.filter(m.SupportRequest.status == status)
    else:
        q = q.filter(m.SupportRequest.status.in_(["open", "alerting", "accepted", "unfilled"]))
    rows = q.order_by(m.SupportRequest.start_date).limit(300).all()
    return render(request, "requests.html", user, rows=rows, status=status, counts=counts)


@router.get("/requests/{rid}")
def request_detail(request: Request, rid: int, user: m.User = Depends(staff), db: Session = Depends(get_db)):
    r = _req(db, user, rid)
    candidates = rank(db, r, include_busy=True) if r.status in ("open", "alerting", "unfilled") else []
    return render(request, "request_detail.html", user, r=r, candidates=candidates[:15])


@router.post("/requests/{rid}/dispatch", dependencies=CSRF)
def request_dispatch(request: Request, rid: int, user: m.User = Depends(staff), db: Session = Depends(get_db)):
    r = _req(db, user, rid)
    for a in r.alerts:
        if a.status == "sent":
            a.status, a.responded_at = "withdrawn", datetime.now()
    if r.status == "unfilled":
        r.status = "open"
    db.flush()
    alert = dispatch(db, r)
    db.commit()
    flash(request, f"Asked {alert.helper.name}." if alert else "No other eligible helper is free.",
          "ok" if alert else "warn")
    return _back(f"/requests/{rid}")


@router.post("/requests/{rid}/assign", dependencies=CSRF)
def request_assign(request: Request, rid: int, helper_id: int = Form(...), user: m.User = Depends(staff),
                   db: Session = Depends(get_db)):
    """CHW arranged a helper directly (e.g. by phone)."""
    r = _req(db, user, rid)
    h = db.get(m.Helper, helper_id)
    if not h or not can_see_area(user, h):
        raise HTTPException(404, "Helper not found.")
    for a in r.alerts:
        if a.status == "sent":
            a.status, a.responded_at = "withdrawn", datetime.now()
    db.add(m.Alert(request_id=r.id, helper_id=h.id, status="accepted", reason="arranged by CHW",
                   channel="chw", sent_at=datetime.now(), responded_at=datetime.now()))
    r.status, r.helper_id = "accepted", h.id
    mo = r.mother
    send_sms(db, mo.phone, t(mo.language, "sms_mother_matched", helper=h.name,
                             group=h.group.name if h.group else h.village or "",
                             task=r.activity.split(" (")[0].lower() if mo.language == "sw" else r.activity,
                             start=r.start_date.strftime("%d/%m"), phone=h.phone), kind="confirm")
    audit(db, user, "request_assigned", "request", r.id, f"helper {h.id}")
    db.commit()
    flash(request, f"{h.name} assigned. The mother was told by SMS.")
    return _back(f"/requests/{rid}")


@router.post("/requests/{rid}/verify", dependencies=CSRF)
def request_verify(request: Request, rid: int, hours: float = Form(...), note: str = Form(""),
                   user: m.User = Depends(staff), db: Session = Depends(get_db)):
    r = _req(db, user, rid)
    try:
        e = ledger.verify_request(db, r, hours, user)
        if note:
            r.note = note
        audit(db, user, "request_verified", "request", r.id, f"{hours} h, ledger #{e.seq}")
        db.commit()
        flash(request, f"{hours:g} hours verified and added to the ledger (#{e.seq}).")
    except ValueError as ex:
        flash(request, str(ex), "err")
    return _back(request.headers.get("referer") or f"/requests/{rid}")


@router.post("/requests/{rid}/cancel", dependencies=CSRF)
def request_cancel(request: Request, rid: int, user: m.User = Depends(staff), db: Session = Depends(get_db)):
    r = _req(db, user, rid)
    r.status = "cancelled"
    for a in r.alerts:
        if a.status == "sent":
            a.status, a.responded_at = "withdrawn", datetime.now()
    audit(db, user, "request_cancelled", "request", r.id)
    db.commit()
    flash(request, "Request cancelled.")
    return _back(f"/requests/{rid}")


# ------------------------------------------------------------------ helpers & groups
@router.get("/helpers")
def helpers_list(request: Request, q: str = "", district: str = "", user: m.User = Depends(staff),
                 db: Session = Depends(get_db)):
    query = scope_area(db.query(m.Helper), m.Helper, user)
    if q:
        like = f"%{q}%"
        query = query.filter(or_(m.Helper.name.ilike(like), m.Helper.phone.ilike(like), m.Helper.village.ilike(like)))
    if district:
        query = query.filter(m.Helper.district == district)
    rows = query.order_by(m.Helper.district, m.Helper.name).limit(500).all()
    groups = scope_area(db.query(m.Group), m.Group, user).order_by(m.Group.name).all()
    return render(request, "helpers.html", user, rows=rows, q=q, district=district, groups=groups,
                  **_form_ctx(db, user))


@router.post("/helpers/new", dependencies=CSRF)
def helper_create(request: Request, name: str = Form(...), phone: str = Form(...), region: str = Form(...),
                  district: str = Form(...), ward: str = Form(""), village: str = Form(""), sex: str = Form(""),
                  group_id: str = Form(""), skills: list[str] = Form([]), pesticide_trained: str = Form(""),
                  language: str = Form("sw"), user: m.User = Depends(staff), db: Session = Depends(get_db)):
    phone_n = normalize_phone(phone)
    if db.query(m.Helper).filter(m.Helper.phone == phone_n).first():
        flash(request, "A helper with this phone number already exists.", "err")
        return _back("/helpers")
    if not in_area(user, region, district):
        flash(request, "You can only add helpers in your own district.", "err")
        return _back("/helpers")
    g = db.get(m.Group, _int(group_id)) if _int(group_id) else None
    h = register_helper(db, name=name, phone=phone_n, region=region, district=district, ward=ward, village=village,
                        group=g, skills=",".join(s for s in skills if s in m.TASK_TYPES) or "lifting,water",
                        pesticide_trained=bool(pesticide_trained), language=language, via="web", sex=sex or None)
    audit(db, user, "helper_registered", "helper", h.id)
    db.commit()
    flash(request, f"{h.name} added as a helper.")
    return _back(f"/helpers/{h.id}")


@router.get("/helpers/{hid}")
def helper_detail(request: Request, hid: int, user: m.User = Depends(staff), db: Session = Depends(get_db)):
    h = db.get(m.Helper, hid)
    if not h or not can_see_area(user, h):
        raise HTTPException(404, "Helper not found.")
    alerts = db.query(m.Alert).filter(m.Alert.helper_id == h.id).order_by(m.Alert.sent_at.desc()).limit(50).all()
    groups = scope_area(db.query(m.Group), m.Group, user).order_by(m.Group.name).all()
    return render(request, "helper_detail.html", user, h=h, alerts=alerts, groups=groups)


@router.post("/helpers/{hid}/edit", dependencies=CSRF)
def helper_update(request: Request, hid: int, name: str = Form(...), ward: str = Form(""), village: str = Form(""),
                  group_id: str = Form(""), skills: list[str] = Form([]), pesticide_trained: str = Form(""),
                  available: str = Form(""), language: str = Form("sw"), user: m.User = Depends(staff),
                  db: Session = Depends(get_db)):
    h = db.get(m.Helper, hid)
    if not h or not can_see_area(user, h):
        raise HTTPException(404, "Helper not found.")
    h.name, h.ward, h.village = name.strip().title(), ward.strip().title() or None, village.strip().title() or None
    h.group_id = _int(group_id)
    h.skills = ",".join(s for s in skills if s in m.TASK_TYPES)
    h.pesticide_trained, h.available, h.language = bool(pesticide_trained), bool(available), language
    audit(db, user, "helper_updated", "helper", h.id)
    db.commit()
    flash(request, "Helper saved.")
    return _back(f"/helpers/{hid}")


@router.get("/groups")
def groups_list(request: Request, user: m.User = Depends(staff), db: Session = Depends(get_db)):
    rows = scope_area(db.query(m.Group), m.Group, user).order_by(m.Group.region, m.Group.district, m.Group.name).all()
    return render(request, "groups.html", user, rows=rows, **_form_ctx(db, user))


@router.post("/groups/new", dependencies=CSRF)
def group_create(request: Request, name: str = Form(...), group_type: str = Form("other"), region: str = Form(...),
                 district: str = Form(...), ward: str = Form(""), village: str = Form(""),
                 leader_name: str = Form(""), leader_phone: str = Form(""), user: m.User = Depends(staff),
                 db: Session = Depends(get_db)):
    if not in_area(user, region, district):
        flash(request, "You can only add groups in your own district.", "err")
        return _back("/groups")
    g = find_or_create_group(db, name, region, district, ward or None)
    g.group_type, g.village = group_type, village or None
    g.leader_name, g.leader_phone = leader_name or None, normalize_phone(leader_phone) or None
    audit(db, user, "group_saved", "group", g.id)
    db.commit()
    flash(request, f"Group {g.name} saved.")
    return _back("/groups")


# ------------------------------------------------------------------ danger reports
@router.get("/danger")
def danger_list(request: Request, status: str = "open", user: m.User = Depends(staff), db: Session = Depends(get_db)):
    ids = [x for (x,) in scope_mothers(db.query(m.Mother), user).with_entities(m.Mother.id)]
    q = db.query(m.DangerReport).filter(m.DangerReport.mother_id.in_(ids))
    if status == "open":
        q = q.filter(m.DangerReport.status.in_(["new", "contacted"]))
    rows = q.order_by(m.DangerReport.reported_at.desc()).limit(300).all()
    return render(request, "danger.html", user, rows=rows, status=status)


@router.post("/danger/{did}", dependencies=CSRF)
def danger_update(request: Request, did: int, status: str = Form(...), facility_id: str = Form(""),
                  notes: str = Form(""), user: m.User = Depends(staff), db: Session = Depends(get_db)):
    d = db.get(m.DangerReport, did)
    if not d or not can_see_mother(user, d.mother):
        raise HTTPException(404, "Report not found.")
    if d.status == "new" and status != "new" and not d.first_contact_at:
        d.first_contact_at = datetime.now()
    d.status, d.handled_by = status, user.id
    d.facility_id = _int(facility_id) or d.facility_id
    if notes:
        d.notes = ((d.notes + "\n") if d.notes else "") + f"{datetime.now():%d/%m %H:%M} {user.name}: {notes}"
    if status == "resolved":
        d.closed_at = datetime.now()
    audit(db, user, "danger_updated", "danger", d.id, status)
    db.commit()
    flash(request, "Danger report updated.")
    return _back(request.headers.get("referer") or "/danger")


# ------------------------------------------------------------------ ledger
@router.get("/ledger")
def ledger_page(request: Request, user: m.User = Depends(staff), db: Session = Depends(get_db)):
    rows = db.query(m.LedgerEntry).order_by(m.LedgerEntry.seq.desc()).limit(300).all()
    total = db.query(m.LedgerEntry).count()
    hours = sum(e.hours for e in db.query(m.LedgerEntry.hours))
    return render(request, "ledger.html", user, rows=rows, total=total, hours=hours, check=None)


@router.post("/ledger/verify", dependencies=CSRF)
def ledger_verify(request: Request, user: m.User = Depends(staff), db: Session = Depends(get_db)):
    ok, bad, n = ledger.verify_chain(db)
    flash(request, f"All {n} records are intact." if ok else f"Record #{bad} has been altered. "
          "Records after it cannot be trusted.", "ok" if ok else "err")
    return _back("/ledger")
