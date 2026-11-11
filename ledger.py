"""Time-credit ledger: an append-only, hash-chained record of verified help.

Each entry stores only codes (no names, phone numbers or health data) and the SHA-256 hash of
the previous entry. Changing any past entry breaks every hash after it, so tampering is visible.
The chain can later be anchored to a public blockchain by publishing the latest hash.
"""
import hashlib
from datetime import date, datetime

from sqlalchemy.orm import Session

from .. import models as m
from .common import helper_code, user_code
from .sms import send_sms
from .texts import t

GENESIS = "0" * 64


def _canonical(e: m.LedgerEntry) -> str:
    return "|".join([str(e.seq), e.recorded_on, e.helper_code, e.mother_code, str(e.request_id),
                     e.task_type, f"{e.hours:.2f}", e.verifier_code, e.prev_hash])


def _hash(e: m.LedgerEntry) -> str:
    return hashlib.sha256(_canonical(e).encode()).hexdigest()


def verify_request(db: Session, req: m.SupportRequest, hours: float, user: m.User) -> m.LedgerEntry:
    if req.status != "accepted" or not req.helper_id:
        raise ValueError("Only accepted requests with a helper can be verified.")
    if not (0 < hours <= 1000):
        raise ValueError("Hours must be between 0 and 1000.")
    last = db.query(m.LedgerEntry).order_by(m.LedgerEntry.seq.desc()).first()
    e = m.LedgerEntry(seq=(last.seq + 1) if last else 1, recorded_on=date.today().isoformat(),
                      helper_code=helper_code(req.helper_id), mother_code=req.mother.code, request_id=req.id,
                      task_type=req.task_type, hours=round(hours, 2), verifier_code=user_code(user.id),
                      prev_hash=last.hash if last else GENESIS, hash="")
    e.hash = _hash(e)
    db.add(e)
    req.status = "verified"
    req.verified_hours = e.hours
    req.verified_by = user.id
    req.verified_at = datetime.now()
    helper = req.helper
    helper.credit_hours = round((helper.credit_hours or 0) + e.hours, 2)
    send_sms(db, helper.phone, t(helper.language, "sms_verified", hours=f"{e.hours:g}",
                                 total=f"{helper.credit_hours:g}"), kind="confirm")
    db.flush()
    return e


def verify_chain(db: Session) -> tuple[bool, int, int]:
    """Returns (intact, first_bad_seq, count)."""
    prev, n = GENESIS, 0
    for e in db.query(m.LedgerEntry).order_by(m.LedgerEntry.seq):
        n += 1
        if e.prev_hash != prev or _hash(e) != e.hash:
            return False, e.seq, n
        prev = e.hash
    return True, 0, n
