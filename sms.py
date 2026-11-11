"""Outgoing SMS. Every message is stored; delivery goes through the configured provider.

SMS_PROVIDER=console      -> messages are stored as "logged" (for testing and demos)
SMS_PROVIDER=africastalking -> sent through the Africa's Talking bulk SMS API
"""
import logging

import httpx
from sqlalchemy.orm import Session

from .. import models as m
from ..config import settings

log = logging.getLogger("mamavuna.sms")


def _send_africastalking(phone: str, body: str) -> tuple[str, str, str]:
    host = "api.sandbox.africastalking.com" if settings.AT_SANDBOX else "api.africastalking.com"
    data = {"username": settings.AT_USERNAME, "to": phone, "message": body}
    if settings.AT_SENDER_ID and not settings.AT_SANDBOX:
        data["from"] = settings.AT_SENDER_ID
    r = httpx.post(f"https://{host}/version1/messaging", data=data, timeout=15,
                   headers={"apiKey": settings.AT_API_KEY, "Accept": "application/json"})
    r.raise_for_status()
    recips = r.json().get("SMSMessageData", {}).get("Recipients", [])
    if not recips:
        return "failed", "", r.json().get("SMSMessageData", {}).get("Message", "No recipients")
    rec = recips[0]
    ok = rec.get("status") in ("Success", "Sent", "Submitted", "Queued")
    return ("sent" if ok else "failed"), rec.get("messageId", ""), "" if ok else rec.get("status", "")


def send_sms(db: Session, phone: str, body: str, kind: str = "system") -> m.Message:
    msg = m.Message(direction="out", phone=phone, body=body, kind=kind, status="queued")
    db.add(msg)
    db.flush()
    if settings.SMS_PROVIDER == "africastalking" and settings.AT_API_KEY:
        try:
            msg.status, msg.provider_id, msg.error = _send_africastalking(phone, body)
        except Exception as e:  # network or provider error: keep the message for retry
            msg.status, msg.error = "failed", str(e)[:250]
            log.warning("SMS to %s failed: %s", phone, e)
    else:
        msg.status = "logged"
        log.info("SMS (console) to %s: %s", phone, body)
    return msg


def record_inbound(db: Session, phone: str, body: str, provider_id: str = None) -> m.Message:
    msg = m.Message(direction="in", phone=phone, body=body, status="received", provider_id=provider_id)
    db.add(msg)
    db.flush()
    return msg


def retry_failed(db: Session, limit: int = 50) -> int:
    """Retry failed messages from the last 24 hours once per scheduler cycle."""
    from datetime import datetime, timedelta
    n = 0
    since = datetime.now() - timedelta(hours=24)
    for msg in (db.query(m.Message).filter(m.Message.direction == "out", m.Message.status == "failed",
                                           m.Message.created_at >= since).limit(limit)):
        if settings.SMS_PROVIDER != "africastalking" or not settings.AT_API_KEY:
            break
        try:
            msg.status, msg.provider_id, msg.error = _send_africastalking(msg.phone, msg.body)
            n += 1
        except Exception as e:
            msg.error = str(e)[:250]
    return n
