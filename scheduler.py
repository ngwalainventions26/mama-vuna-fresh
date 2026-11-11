"""Background jobs. Safe to run repeatedly: every step checks what was already done."""
import asyncio
import logging
from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from .. import models as m
from ..config import settings
from ..db import SessionLocal
from .matching import create_request, dispatch, escalate_timeouts
from .pregnancy import gest_week, protected_period, windows
from .sms import retry_failed, send_sms
from .texts import tip_for_week

log = logging.getLogger("mamavuna.scheduler")


def _active_mothers(db: Session):
    return (db.query(m.Mother).filter(m.Mother.status.in_(["pregnant", "delivered"]), m.Mother.opted_out.is_(False),
                                      m.Mother.consent_at.isnot(None)).all())


def create_due_requests(db: Session, on: date = None) -> int:
    on = on or date.today()
    horizon = on + timedelta(days=settings.LEAD_DAYS)
    existing = {k for (k,) in db.query(m.SupportRequest.window_key).filter(m.SupportRequest.window_key.isnot(None))}
    created = 0
    for mother in _active_mothers(db):
        for w in windows(db, mother):
            if w.key in existing or w.end < on or w.start > horizon:
                continue
            create_request(db, mother, w.task_type, w.activity, max(w.start, on), w.end, w.est_hours,
                           source="auto", window_key=w.key)
            existing.add(w.key)
            created += 1
    return created


def dispatch_open(db: Session) -> int:
    n = 0
    for req in db.query(m.SupportRequest).filter(m.SupportRequest.status == "open").all():
        dispatch(db, req)
        n += 1
    return n


def send_tips(db: Session, on: date = None) -> int:
    if not settings.WEEKLY_TIPS_ENABLED:
        return 0
    on = on or date.today()
    n = 0
    for mother in db.query(m.Mother).filter(m.Mother.status == "pregnant", m.Mother.opted_out.is_(False),
                                            m.Mother.consent_at.isnot(None)):
        tip = tip_for_week(gest_week(mother.edd, on), mother.language)
        if tip and tip[0] != mother.last_tip_week:
            send_sms(db, mother.phone, "MAMA VUNA FRESH: " + tip[1], kind="tip")
            mother.last_tip_week = tip[0]
            n += 1
    return n


def close_finished(db: Session, on: date = None) -> int:
    on = on or date.today()
    n = 0
    for mother in _active_mothers(db):
        _, end = protected_period(mother)
        if end < on - timedelta(days=1):
            mother.status = "closed"
            for r in mother.requests:
                if r.status in ("open", "alerting"):
                    r.status = "cancelled"
            n += 1
    return n


def run_cycle(db: Session, on: date = None) -> dict:
    result = {
        "created": create_due_requests(db, on),
        "dispatched": dispatch_open(db),
        "escalated": escalate_timeouts(db),
        "tips": send_tips(db, on),
        "closed": close_finished(db, on),
        "sms_retried": retry_failed(db),
    }
    state = db.get(m.SystemState, "scheduler_last_run") or m.SystemState(key="scheduler_last_run")
    state.value = f"{datetime.now().isoformat(timespec='seconds')} {result}"
    db.merge(state)
    db.commit()
    return result


def _run_once():
    db = SessionLocal()
    try:
        res = run_cycle(db)
        log.info("Scheduler cycle: %s", res)
    except Exception:
        db.rollback()
        log.exception("Scheduler cycle failed")
    finally:
        db.close()


async def loop():
    await asyncio.sleep(5)
    while True:
        await asyncio.to_thread(_run_once)
        await asyncio.sleep(settings.SCHEDULER_INTERVAL_MIN * 60)
