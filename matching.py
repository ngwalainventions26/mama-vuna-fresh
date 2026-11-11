"""Helper matching, alerts and escalation.

Rules (transparent so CHWs can explain every choice):
- only helpers in the mother's district who are available, consented and have the right skill;
- pesticide and chemical tasks only go to helpers marked as trained;
- score = closeness (same village 50, same ward 30, same district 10)
          + reliability (past acceptances, up to 20)
          - 10 for each other job the helper already holds in the same dates;
- one helper is asked at a time; no reply within ALERT_TIMEOUT_HOURS moves to the next helper;
- if nobody is left, the request is marked unfilled and the CHW is told by SMS.
"""
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from .. import models as m
from ..config import settings
from .common import first_name, label_for, short_date, task_label
from .sms import send_sms
from .texts import t


def _norm(s: Optional[str]) -> str:
    return (s or "").strip().lower()


def reliability(db: Session, helper: m.Helper) -> float:
    rows = db.query(m.Alert.status).filter(m.Alert.helper_id == helper.id,
                                           m.Alert.status.in_(["accepted", "declined", "timeout"])).all()
    acc = sum(1 for (s,) in rows if s == "accepted")
    return (acc + 1) / (len(rows) + 2)


def rank(db: Session, req: m.SupportRequest, include_busy: bool = False) -> list[tuple[m.Helper, float, str]]:
    """Eligible helpers, best first. Helpers already waiting to answer another alert are left out
    unless include_busy is set, so each helper has only one question open at a time."""
    mother = req.mother
    tried = {a.helper_id for a in req.alerts}
    busy = {h for (h,) in db.query(m.Alert.helper_id).filter(m.Alert.status == "sent")}
    q = db.query(m.Helper).filter(m.Helper.region == mother.region, m.Helper.district == mother.district,
                                  m.Helper.available.is_(True), m.Helper.opted_out.is_(False),
                                  m.Helper.phone != mother.phone)
    out = []
    for h in q:
        if h.id in tried or (h.id in busy and not include_busy):
            continue
        if req.task_type == "chemical" and not h.pesticide_trained:
            continue
        if req.task_type != "escort" and req.task_type not in h.skill_list():
            continue
        score, why = 0.0, []
        if mother.village and _norm(h.village) == _norm(mother.village):
            score += 50; why.append("same village")
        elif mother.ward and _norm(h.ward) == _norm(mother.ward):
            score += 30; why.append("same ward")
        else:
            score += 10; why.append("same district")
        rel = reliability(db, h)
        score += rel * 20; why.append(f"{round(rel * 100)}% reliable")
        load = db.query(m.SupportRequest).filter(
            m.SupportRequest.helper_id == h.id, m.SupportRequest.status == "accepted",
            m.SupportRequest.start_date <= req.end_date, m.SupportRequest.end_date >= req.start_date).count()
        if load:
            score -= 10 * load; why.append(f"{load} other job(s)")
        if req.task_type == "chemical":
            why.append("pesticide trained")
        out.append((h, round(score, 1), ", ".join(why)))
    return sorted(out, key=lambda x: -x[1])


def _place(mother: m.Mother) -> str:
    return mother.village or mother.ward or mother.district


def dispatch(db: Session, req: m.SupportRequest) -> Optional[m.Alert]:
    """Ask the best remaining helper. Returns the alert, or None when nobody is left."""
    if req.status in ("accepted", "verified", "cancelled"):
        return None
    ranked = rank(db, req)
    if not ranked:
        if rank(db, req, include_busy=True):
            req.status = "open"  # eligible helpers exist but are answering other alerts: try next cycle
            return None
        req.status = "unfilled"
        notify_chw_unfilled(db, req)
        return None
    h, score, why = ranked[0]
    alert = m.Alert(request_id=req.id, helper_id=h.id, score=score, reason=why, status="sent", sent_at=datetime.now())
    db.add(alert)
    req.status = "alerting"
    mother = req.mother
    send_sms(db, h.phone, t(h.language, "sms_alert", first=first_name(mother.name), place=_place(mother),
                            task=label_for(req.activity, h.language).lower(),
                            start=short_date(req.start_date, h.language), end=short_date(req.end_date, h.language)),
             kind="alert")
    db.flush()
    return alert


def notify_chw_unfilled(db: Session, req: m.SupportRequest) -> None:
    mother = req.mother
    chw = mother.chw
    if chw and chw.phone:
        send_sms(db, chw.phone, t("sw", "sms_chw_unfilled", mother=mother.name, code=mother.code,
                                  task=task_label(req.task_type, "sw").lower(),
                                  start=short_date(req.start_date), phone=mother.phone), kind="system")


def pending_alert(db: Session, helper: m.Helper) -> Optional[m.Alert]:
    return (db.query(m.Alert).filter(m.Alert.helper_id == helper.id, m.Alert.status == "sent")
            .order_by(m.Alert.sent_at).first())


def respond(db: Session, helper: m.Helper, accept: bool, alert: Optional[m.Alert] = None) -> str:
    """Apply a helper's reply. Returns the text to show or send back to the helper."""
    lang = helper.language
    alert = alert or pending_alert(db, helper)
    if not alert:
        return t(lang, "sms_no_pending")
    req = alert.request
    alert.responded_at = datetime.now()
    mother = req.mother
    if accept:
        alert.status = "accepted"
        req.status = "accepted"
        req.helper_id = helper.id
        send_sms(db, mother.phone, t(mother.language, "sms_mother_matched", helper=helper.name,
                                     group=helper.group.name if helper.group else helper.village or "",
                                     task=label_for(req.activity, mother.language).lower(),
                                     start=short_date(req.start_date, mother.language), phone=helper.phone),
                 kind="confirm")
        db.flush()
        return t(lang, "sms_helper_thanks", first=first_name(helper.name), mother=first_name(mother.name),
                 phone=mother.phone)
    alert.status = "declined"
    db.flush()
    dispatch(db, req)
    return t(lang, "sms_helper_declined")


def escalate_timeouts(db: Session) -> int:
    cutoff = datetime.now() - timedelta(hours=settings.ALERT_TIMEOUT_HOURS)
    n = 0
    for a in db.query(m.Alert).filter(m.Alert.status == "sent", m.Alert.sent_at < cutoff).all():
        a.status = "timeout"
        a.responded_at = datetime.now()
        db.flush()
        dispatch(db, a.request)
        n += 1
    return n


def create_request(db: Session, mother: m.Mother, task_type: str, activity: str, start, end,
                   est_hours: float, source: str, window_key: Optional[str] = None) -> m.SupportRequest:
    req = m.SupportRequest(mother_id=mother.id, window_key=window_key, task_type=task_type, activity=activity,
                           start_date=start, end_date=end, est_hours=est_hours, status="open", source=source)
    db.add(req)
    db.flush()
    db.refresh(req)
    return req
