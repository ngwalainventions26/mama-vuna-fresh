"""Indicators page and data exports (anonymised CSV and DHIS2-style aggregate JSON)."""
import csv
import io
from collections import defaultdict
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.orm import Session

from .. import models as m
from ..db import get_db
from ..security import managers, scope_mothers, staff
from ..services import indicators
from ..services.common import audit
from ..web import render

router = APIRouter(include_in_schema=False)


@router.get("/reports")
def reports(request: Request, user: m.User = Depends(staff), db: Session = Depends(get_db)):
    return render(request, "reports.html", user, k=indicators.compute(db, user),
                  districts=indicators.by_district(db, user))


def _csv(name: str, header: list[str], rows) -> StreamingResponse:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(header)
    w.writerows(rows)
    buf.seek(0)
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": f'attachment; filename="{name}-{date.today()}.csv"'})


@router.get("/reports/export/{kind}.csv")
def export(kind: str, user: m.User = Depends(managers), db: Session = Depends(get_db)):
    mothers = scope_mothers(db.query(m.Mother), user).filter(m.Mother.is_demo.is_(False)).all()
    ids = {x.id: x for x in mothers}
    audit(db, user, "export", detail=kind)
    db.commit()
    if kind == "mothers":
        return _csv("mothers", ["code", "region", "district", "setting", "livelihood", "crop", "age_group", "edd_month",
                                "edd_source", "status", "risk_flag", "registered_via", "registered_on"],
                    [[x.code, x.region, x.district, x.setting, x.livelihood, x.crop or "",
                      ("<20" if (x.age or 0) < 20 else "20-34" if (x.age or 0) < 35 else "35+") if x.age else "",
                      x.edd.strftime("%Y-%m"), x.edd_source, x.status, x.risk_flag, x.registered_via,
                      x.created_at.date()] for x in mothers])
    if kind == "requests":
        rows = []
        for r in db.query(m.SupportRequest).order_by(m.SupportRequest.id):
            if r.mother_id in ids:
                first = min((a.sent_at for a in r.alerts), default=None)
                acc = min((a.responded_at for a in r.alerts if a.status == "accepted" and a.responded_at), default=None)
                rows.append([r.id, ids[r.mother_id].code, ids[r.mother_id].district, r.task_type, r.source,
                             r.start_date, r.end_date, r.status, r.est_hours, r.verified_hours or "",
                             len(r.alerts), round((acc - first).total_seconds() / 3600, 1) if first and acc else ""])
        return _csv("support-requests", ["request_id", "mother_code", "district", "task_type", "source", "start",
                                         "end", "status", "planned_hours", "verified_hours", "helpers_asked",
                                         "hours_to_acceptance"], rows)
    if kind == "visits":
        return _csv("visits", ["mother_code", "district", "visit_date", "kind", "gest_week", "did_heavy_work",
                               "handled_pesticide", "help_received", "anc_up_to_date", "danger_signs_seen"],
                    [[ids[v.mother_id].code, ids[v.mother_id].district, v.visit_date, v.kind, v.gest_week or "",
                      v.did_heavy_work, v.handled_pesticide, v.help_received, v.anc_up_to_date, v.danger_signs_seen]
                     for v in db.query(m.Visit).order_by(m.Visit.visit_date) if v.mother_id in ids])
    if kind == "outcomes":
        return _csv("birth-outcomes", ["mother_code", "district", "livelihood", "delivery_month", "place",
                                       "gest_weeks", "birth_weight_g", "preterm", "low_birth_weight", "outcome",
                                       "mother_complication", "source"],
                    [[ids[o.mother_id].code, ids[o.mother_id].district, ids[o.mother_id].livelihood,
                      o.delivery_date.strftime("%Y-%m"), o.place, o.gest_weeks or "", o.birth_weight_g or "",
                      o.preterm, o.low_birth_weight, o.outcome, o.mother_complication, o.source]
                     for o in db.query(m.BirthOutcome) if o.mother_id in ids])
    if kind == "ledger":
        return _csv("time-credit-ledger", ["seq", "date", "helper", "mother", "request", "task", "hours",
                                           "verifier", "prev_hash", "hash"],
                    [[e.seq, e.recorded_on, e.helper_code, e.mother_code, e.request_id, e.task_type, e.hours,
                      e.verifier_code, e.prev_hash, e.hash] for e in db.query(m.LedgerEntry).order_by(m.LedgerEntry.seq)])
    raise HTTPException(404, "Unknown export.")


@router.get("/reports/export/dhis2.json")
def export_dhis2(period: str = "", user: m.User = Depends(managers), db: Session = Depends(get_db)):
    """Monthly aggregates per district in DHIS2 dataValueSets layout.
    Data element and org unit codes are placeholders: map them with the district HMIS team before import."""
    period = period or date.today().strftime("%Y%m")
    if len(period) != 6 or not period.isdigit():
        raise HTTPException(400, "Use period=YYYYMM")
    y, mo = int(period[:4]), int(period[4:])
    agg = defaultdict(lambda: defaultdict(float))
    for x in scope_mothers(db.query(m.Mother), user).filter(m.Mother.is_demo.is_(False)):
        key = f"{x.region}/{x.district}"
        if x.created_at.year == y and x.created_at.month == mo:
            agg[key]["MVF_NEW_REGISTRATIONS"] += 1
        for r in x.requests:
            if r.verified_at and r.verified_at.year == y and r.verified_at.month == mo:
                agg[key]["MVF_VERIFIED_SUPPORT_HOURS"] += r.verified_hours or 0
                agg[key]["MVF_VERIFIED_REQUESTS"] += 1
        for d in x.danger_reports:
            if d.reported_at.year == y and d.reported_at.month == mo:
                agg[key]["MVF_DANGER_REPORTS"] += 1
        if x.outcome and x.outcome.delivery_date.year == y and x.outcome.delivery_date.month == mo:
            agg[key]["MVF_BIRTHS_RECORDED"] += 1
            if x.outcome.preterm:
                agg[key]["MVF_PRETERM_BIRTHS"] += 1
            if x.outcome.low_birth_weight:
                agg[key]["MVF_LBW_BIRTHS"] += 1
    values = [{"dataElement": de, "orgUnit": ou, "period": period, "value": str(round(v, 1))}
              for ou, des in sorted(agg.items()) for de, v in sorted(des.items())]
    audit(db, user, "export", detail=f"dhis2 {period}")
    db.commit()
    return JSONResponse({"dataSet": "MAMA_VUNA_FRESH_MONTHLY", "period": period,
                         "note": "Codes are placeholders. Map dataElement and orgUnit to your DHIS2 instance.",
                         "dataValues": values},
                        headers={"Content-Disposition": f'attachment; filename="mvf-dhis2-{period}.json"'})
