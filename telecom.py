"""Webhooks for the telecom gateway (Africa's Talking, or an MNO using similar fields)."""
import hmac

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from .. import models as m
from ..config import settings
from ..db import get_db
from ..services import ussd
from ..services.common import normalize_phone
from ..services.sms_inbound import handle_inbound

router = APIRouter(tags=["Telecom webhooks"])


def _check_token(request: Request) -> None:
    if settings.WEBHOOK_TOKEN:
        sent = request.query_params.get("token", "")
        if not hmac.compare_digest(sent, settings.WEBHOOK_TOKEN):
            raise HTTPException(403, "Invalid webhook token")


async def _fields(request: Request) -> dict:
    data = dict(request.query_params)
    if request.method == "POST":
        ctype = request.headers.get("content-type", "")
        if "json" in ctype:
            data.update(await request.json())
        else:
            data.update(dict(await request.form()))
    return {k.lower(): str(v) for k, v in data.items()}


@router.api_route("/ussd", methods=["GET", "POST"], response_class=PlainTextResponse,
                  summary="USSD callback (Africa's Talking format; also accepts MSISDN/USSD_STRING)")
async def ussd_callback(request: Request, db: Session = Depends(get_db)):
    _check_token(request)
    f = await _fields(request)
    phone = normalize_phone(f.get("phonenumber") or f.get("msisdn") or f.get("phone"))
    text = f.get("text")
    if text is None:
        text = f.get("ussd_string") or f.get("ussdstring") or f.get("input") or ""
    if not phone:
        return PlainTextResponse("END Missing phone number", status_code=400)
    reply = ussd.handle(db, phone, text)
    db.add(m.UssdLog(session_id=f.get("sessionid"), phone=phone, text=text, response=reply[:500]))
    db.commit()
    return PlainTextResponse(reply)


@router.post("/sms/inbound", response_class=PlainTextResponse, summary="Incoming SMS callback")
async def sms_inbound(request: Request, db: Session = Depends(get_db)):
    _check_token(request)
    f = await _fields(request)
    phone = normalize_phone(f.get("from") or f.get("msisdn") or f.get("phonenumber"))
    if not phone:
        raise HTTPException(400, "Missing sender")
    handle_inbound(db, phone, f.get("text") or f.get("message") or "", f.get("id"))
    return PlainTextResponse("OK")


@router.post("/sms/delivery", response_class=PlainTextResponse, summary="SMS delivery report callback")
async def sms_delivery(request: Request, db: Session = Depends(get_db)):
    _check_token(request)
    f = await _fields(request)
    msg = db.query(m.Message).filter(m.Message.provider_id == f.get("id")).first() if f.get("id") else None
    if msg:
        status = (f.get("status") or "").lower()
        msg.status = "delivered" if status == "success" else "failed" if status in ("failed", "rejected") else msg.status
        if f.get("failurereason"):
            msg.error = f["failurereason"][:250]
        db.commit()
    return PlainTextResponse("OK")
