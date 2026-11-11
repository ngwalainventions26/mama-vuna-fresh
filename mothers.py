"""Actions on mothers and helpers shared by USSD, SMS and the web dashboard."""
from datetime import date, datetime, timedelta
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models as m
from ..config import settings
from .common import first_name, label_for, next_mother_code, short_date
from .matching import create_request, dispatch
from .pregnancy import NON_FARM_EFFORT, gest_week, protected_period, upcoming_windows
from .reference import nearest_facility
from .sms import send_sms
from .texts import t


def assign_chw(db: Session, mother: m.Mother) -> Optional[m.User]:
    q = db.query(m.User).filter(m.User.role == "chw", m.User.active.is_(True), m.User.district == mother.district)
    cands = q.all()
    if not cands:
        return None
    same_ward = [u for u in cands if mother.ward and (u.ward or "").lower() == mother.ward.lower()]
    pool = same_ward or cands
    loads = dict(db.query(m.Mother.chw_id, func.count(m.Mother.id)).filter(m.Mother.status != "closed")
                 .group_by(m.Mother.chw_id).all())
    return min(pool, key=lambda u: loads.get(u.id, 0))


def welcome_sms(db: Session, mother: m.Mother) -> None:
    ws = upcoming_windows(db, mother, limit=3)
    lines = "\n".join(f"- {short_date(max(w.start, date.today()), mother.language)}-{short_date(w.end, mother.language)}: "
                      f"{label_for(w.activity, mother.language)}" for w in ws) or t(mother.language, "sms_no_windows")
    send_sms(db, mother.phone, t(mother.language, "sms_welcome", first=first_name(mother.name), code=mother.code,
                                 windows=lines, ussd=settings.USSD_SERVICE_CODE), kind="system")


def register_mother(db: Session, *, name: str, phone: str, region: str, district: str, edd: date,
                    ward: str = None, village: str = None, setting: str = "rural", livelihood: str = "farmer",
                    crop: str = None, age: int = None, language: str = "sw", edd_source: str = "mother",
                    via: str = "ussd", chw: m.User = None, consent: bool = True, gravida: int = None,
                    is_demo: bool = False, send_welcome: bool = True) -> m.Mother:
    mother = m.Mother(code=next_mother_code(db), name=name.strip().title(), phone=phone, region=region,
                      district=district, ward=(ward or "").strip().title() or None,
                      village=(village or "").strip().title() or None, setting=setting, livelihood=livelihood,
                      crop=crop if livelihood == "farmer" else None, edd=edd, edd_source=edd_source, age=age,
                      language=language, registered_via=via, gravida=gravida, is_demo=is_demo,
                      consent_at=datetime.now() if consent else None)
    db.add(mother)
    db.flush()
    chw = chw or assign_chw(db, mother)
    mother.chw_id = chw.id if chw else None
    if mother.chw_id is None:
        mother.chw = None
    db.flush()
    db.refresh(mother)
    if send_welcome:
        welcome_sms(db, mother)
    return mother


def find_or_create_group(db: Session, name: str, region: str, district: str, ward: str = None) -> Optional[m.Group]:
    name = (name or "").strip()
    if not name or name == "0":
        return None
    g = (db.query(m.Group).filter(func.lower(m.Group.name) == name.lower(), m.Group.district == district).first())
    if not g:
        g = m.Group(name=name.title(), group_type="other", region=region, district=district, ward=ward)
        db.add(g)
        db.flush()
    return g


def register_helper(db: Session, *, name: str, phone: str, region: str, district: str, ward: str = None,
                    village: str = None, group: m.Group = None, skills: str = "lifting,bending,water,household",
                    pesticide_trained: bool = False, language: str = "sw", via: str = "web", sex: str = None,
                    is_demo: bool = False) -> m.Helper:
    h = m.Helper(name=name.strip().title(), phone=phone, region=region, district=district,
                 ward=(ward or "").strip().title() or None, village=(village or "").strip().title() or None,
                 group_id=group.id if group else None, skills=skills, pesticide_trained=pesticide_trained,
                 language=language, registered_via=via, sex=sex, consent_at=datetime.now(), is_demo=is_demo)
    db.add(h)
    db.flush()
    return h


def report_danger(db: Session, mother: m.Mother, signs: list[str], via: str = "ussd") -> m.DangerReport:
    fac = nearest_facility(db, mother)
    rep = m.DangerReport(mother_id=mother.id, signs=",".join(signs), via=via,
                         facility_id=fac.id if fac else None)
    db.add(rep)
    mother.risk_flag = "high"
    db.flush()
    chw = mother.chw
    if chw and chw.phone:
        names = ", ".join(m.DANGER_SIGNS.get(s, (s, s))[0] for s in signs)
        send_sms(db, chw.phone, t("sw", "sms_chw_danger", mother=mother.name, code=mother.code,
                                  week=gest_week(mother.edd), signs=names, phone=mother.phone,
                                  place=mother.village or mother.ward or mother.district), kind="danger")
    return rep


def _cancel_future(db: Session, mother: m.Mother, after: date) -> int:
    n = 0
    for r in mother.requests:
        if r.status in ("open", "alerting", "unfilled") and r.start_date > after:
            r.status = "cancelled"
            r.window_key = None  # free the key so a corrected window can be created
            for a in r.alerts:
                if a.status == "sent":
                    a.status = "withdrawn"
            n += 1
    return n


def report_birth(db: Session, mother: m.Mother, on: date, via: str = "ussd") -> None:
    mother.status = "delivered"
    mother.delivery_date = on
    _, end = protected_period(mother)
    _cancel_future(db, mother, end)
    chw = mother.chw
    if chw and chw.phone:
        send_sms(db, chw.phone, t("sw", "sms_chw_birth", mother=mother.name, code=mother.code), kind="system")


def change_edd(db: Session, mother: m.Mother, edd: date, source: str = "mother") -> None:
    mother.edd = edd
    mother.edd_source = source
    mother.last_tip_week = 0
    _cancel_future(db, mother, date.today())


def help_now(db: Session, mother: m.Mother, task_type: str, via: str = "ussd"):
    """Ask for help this week. Returns (request, alert or None, duplicate: bool)."""
    today = date.today()
    dup = (db.query(m.SupportRequest).filter(
        m.SupportRequest.mother_id == mother.id, m.SupportRequest.task_type == task_type,
        m.SupportRequest.status.in_(["open", "alerting", "accepted"]),
        m.SupportRequest.start_date <= today + timedelta(days=6), m.SupportRequest.end_date >= today).first())
    if dup:
        return dup, None, True
    hpd, dpw = NON_FARM_EFFORT.get(task_type, (4.0, 4))
    sw, en = m.TASK_TYPES[task_type]
    req = create_request(db, mother, task_type, f"{sw} ({en.lower()})", today, today + timedelta(days=6),
                         round(dpw * hpd), source=via)
    alert = dispatch(db, req)
    return req, alert, False
