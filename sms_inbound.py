"""Incoming SMS commands.

Helpers:  1 / NDIYO / YES  -> accept the waiting request
          2 / HAPANA / NO  -> decline it
Mothers:  HATARI / DANGER  -> danger alert to the CHW
          MSAADA / HELP    -> ask for help with household work this week
Anyone:   STOP / ACHA      -> stop SMS;   ANZA / START -> start again
"""
from typing import Optional

from sqlalchemy.orm import Session

from .. import models as m
from ..config import settings
from .matching import respond
from .mothers import help_now, report_danger
from .sms import record_inbound, send_sms
from .texts import t

YES = {"1", "NDIYO", "YES", "NAKUBALI", "SAWA", "OK"}
NO = {"2", "HAPANA", "NO", "SIWEZI"}
STOP = {"STOP", "ACHA", "SITISHA"}
START = {"ANZA", "START"}
DANGER = {"HATARI", "DANGER", "DHARURA"}
HELP = {"MSAADA", "HELP"}


def handle_inbound(db: Session, phone: str, text: str, provider_id: str = None) -> Optional[str]:
    record_inbound(db, phone, text, provider_id)
    word = (text or "").strip().upper().split(" ")[0] if text else ""
    mother = db.query(m.Mother).filter(m.Mother.phone == phone, m.Mother.status != "closed").first()
    helper = db.query(m.Helper).filter(m.Helper.phone == phone).first()
    person = mother or helper
    lang = person.language if person else "sw"

    if word in STOP and person:
        person.opted_out = True
        if helper:
            helper.available = False
        reply = t(lang, "sms_stopped")
    elif word in START and person:
        person.opted_out = False
        if helper:
            helper.available = True
        reply = t(lang, "sms_restarted")
    elif helper and (word in YES or word in NO):
        reply = respond(db, helper, word in YES)
    elif mother and word in DANGER:
        rep = report_danger(db, mother, ["other"], via="sms")
        fac = rep.facility
        reply = t(lang, "danger_done", facility=f"{fac.name}{' ' + fac.phone if fac.phone else ''}. " if fac else "")
    elif mother and word in HELP:
        req, alert, dup = help_now(db, mother, "household", via="sms")
        reply = t(lang, "help_dup") if dup else t(lang, "help_sent", helper=alert.helper.name) if alert \
            else t(lang, "help_none")
    elif person:
        reply = t(lang, "sms_reply_help", ussd=settings.USSD_SERVICE_CODE)
    else:
        reply = t(lang, "sms_unknown", ussd=settings.USSD_SERVICE_CODE)

    send_sms(db, phone, reply, kind="system")
    db.commit()
    return reply
