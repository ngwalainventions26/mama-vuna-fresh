"""Read-only JSON API for partners and dashboards. Use a signed-in session or the API_TOKEN bearer token."""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from .. import models as m
from ..db import get_db
from ..security import api_token_ok
from ..services import indicators, ledger

router = APIRouter(prefix="/api/v1", tags=["Partner API"])


def api_user(request: Request, db: Session = Depends(get_db)) -> m.User:
    uid = request.session.get("uid")
    user = db.get(m.User, uid) if uid else None
    if user and user.active:
        return user
    if api_token_ok(request):
        return m.User(id=0, name="API", email="api", role="admin", password_hash="")
    raise HTTPException(401, "Sign in or send 'Authorization: Bearer <API_TOKEN>'.")


@router.get("/indicators", summary="Programme indicators (counts and rates with denominators)")
def get_indicators(user: m.User = Depends(api_user), db: Session = Depends(get_db)):
    k = indicators.compute(db, user)
    return {key: (dict(v) if hasattr(v, "items") else v) for key, v in k.items()}


@router.get("/districts", summary="Indicators by district")
def get_districts(user: m.User = Depends(api_user), db: Session = Depends(get_db)):
    return indicators.by_district(db, user)


@router.get("/ledger/verify", summary="Check the time-credit ledger hash chain")
def verify_ledger(user: m.User = Depends(api_user), db: Session = Depends(get_db)):
    ok, bad, n = ledger.verify_chain(db)
    last = db.query(m.LedgerEntry).order_by(m.LedgerEntry.seq.desc()).first()
    return {"intact": ok, "first_bad_seq": bad or None, "entries": n, "head_hash": last.hash if last else None}


@router.get("/calendar", summary="Crop labour calendar")
def calendar(region: str = "", user: m.User = Depends(api_user), db: Session = Depends(get_db)):
    q = db.query(m.CropActivity)
    if region:
        q = q.filter(m.CropActivity.region == region)
    return [{"region": c.region, "crop": c.crop, "activity": c.activity, "start_month": c.start_month,
             "end_month": c.end_month, "pesticide": c.pesticide, "task_type": c.task_type} for c in q]
