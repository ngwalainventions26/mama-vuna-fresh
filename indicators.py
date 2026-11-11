"""Programme indicators, computed only from records in the platform.

Every percentage comes with its denominator (n). Outcome indicators (preterm, low birth weight)
describe enrolled women only: the platform has no comparison group, so they are not effect estimates.
"""
from collections import Counter
from datetime import datetime, timedelta
from statistics import median
from typing import Optional

from sqlalchemy.orm import Session

from .. import models as m
from ..security import scope_area, scope_mothers


def pct(num: int, den: int) -> Optional[float]:
    return round(100 * num / den, 1) if den else None


def compute(db: Session, user: m.User) -> dict:
    mothers = scope_mothers(db.query(m.Mother), user).filter(m.Mother.is_demo.is_(False)).all()
    demo_count = scope_mothers(db.query(m.Mother), user).filter(m.Mother.is_demo.is_(True)).count()
    ids = {x.id for x in mothers}
    helpers = scope_area(db.query(m.Helper), m.Helper, user).filter(m.Helper.is_demo.is_(False)).all()
    groups = scope_area(db.query(m.Group), m.Group, user).count()

    reqs = [r for r in db.query(m.SupportRequest).all() if r.mother_id in ids]
    status = Counter(r.status for r in reqs)
    decided = [r for r in reqs if r.status in ("accepted", "verified", "unfilled")]
    alerted = [r for r in reqs if r.alerts]
    fast = 0
    for r in alerted:
        first_sent = min(a.sent_at for a in r.alerts)
        acc = [a.responded_at for a in r.alerts if a.status == "accepted" and a.responded_at]
        if acc and min(acc) - first_sent <= timedelta(hours=48):
            fast += 1

    req_ids = {r.id for r in reqs}
    ledger = [e for e in db.query(m.LedgerEntry).all() if e.request_id in req_ids]
    verified_hours = round(sum(e.hours for e in ledger), 1)
    planned_hours = round(sum(r.est_hours for r in reqs if r.status in ("accepted", "verified")), 0)

    visits = [v for v in db.query(m.Visit).all() if v.mother_id in ids and (v.gest_week or 0) >= 28]
    pest = [v for v in visits if v.handled_pesticide is not None]
    heavy = [v for v in visits if v.did_heavy_work is not None]
    helped = [v for v in visits if v.help_received is not None]

    dangers = [d for d in db.query(m.DangerReport).all() if d.mother_id in ids]
    contact_hours = [(d.first_contact_at - d.reported_at).total_seconds() / 3600
                     for d in dangers if d.first_contact_at]
    outcomes = [o for o in db.query(m.BirthOutcome).all() if o.mother_id in ids]
    gest = [o for o in outcomes if o.gest_weeks is not None]
    weight = [o for o in outcomes if o.birth_weight_g is not None]

    return {
        "mothers": len(mothers),
        "mothers_active": sum(1 for x in mothers if x.status in ("pregnant", "delivered")),
        "mothers_third_tri": sum(1 for x in mothers if x.status == "pregnant"
                                 and (x.edd - datetime.now().date()).days <= 84),
        "by_livelihood": Counter(x.livelihood for x in mothers),
        "by_setting": Counter(x.setting for x in mothers),
        "demo_records": demo_count,
        "helpers": len(helpers),
        "helpers_pesticide": sum(1 for h in helpers if h.pesticide_trained),
        "groups": groups,
        "chws": db.query(m.User).filter(m.User.role == "chw", m.User.active.is_(True)).count(),
        "requests": len(reqs),
        "req_status": status,
        "fill_rate": pct(sum(1 for r in decided if r.status != "unfilled"), len(decided)),
        "fill_n": len(decided),
        "rapid_rate": pct(fast, len(alerted)),
        "rapid_n": len(alerted),
        "verified_hours": verified_hours,
        "planned_hours": planned_hours,
        "ledger_entries": len(ledger),
        "pesticide_avoid": pct(sum(1 for v in pest if not v.handled_pesticide), len(pest)),
        "pesticide_n": len(pest),
        "heavy_avoid": pct(sum(1 for v in heavy if not v.did_heavy_work), len(heavy)),
        "heavy_n": len(heavy),
        "help_received": pct(sum(1 for v in helped if v.help_received), len(helped)),
        "help_n": len(helped),
        "dangers": len(dangers),
        "dangers_open": sum(1 for d in dangers if d.status in ("new", "contacted")),
        "danger_referred": pct(sum(1 for d in dangers if d.status in ("referred", "resolved") and d.facility_id),
                               len(dangers)),
        "danger_contact_median_h": round(median(contact_hours), 1) if contact_hours else None,
        "births": len(outcomes),
        "facility_births": pct(sum(1 for o in outcomes if o.place == "facility"), len(outcomes)),
        "preterm": pct(sum(1 for o in gest if o.preterm), len(gest)),
        "preterm_n": len(gest),
        "lbw": pct(sum(1 for o in weight if o.low_birth_weight), len(weight)),
        "lbw_n": len(weight),
        "stillbirths": sum(1 for o in outcomes if o.outcome == "stillbirth"),
    }


def by_district(db: Session, user: m.User) -> list[dict]:
    rows: dict[tuple, dict] = {}
    for x in scope_mothers(db.query(m.Mother), user).filter(m.Mother.is_demo.is_(False)):
        r = rows.setdefault((x.region, x.district), {"region": x.region, "district": x.district,
                                                     "mothers": 0, "active": 0, "requests": 0,
                                                     "verified": 0, "unfilled": 0, "hours": 0.0})
        r["mothers"] += 1
        r["active"] += x.status in ("pregnant", "delivered")
        for q in x.requests:
            r["requests"] += 1
            r["verified"] += q.status == "verified"
            r["unfilled"] += q.status == "unfilled"
            r["hours"] += q.verified_hours or 0
    helpers = Counter((h.region, h.district) for h in scope_area(db.query(m.Helper), m.Helper, user)
                      .filter(m.Helper.is_demo.is_(False)))
    for k, n in helpers.items():
        rows.setdefault(k, {"region": k[0], "district": k[1], "mothers": 0, "active": 0, "requests": 0,
                            "verified": 0, "unfilled": 0, "hours": 0.0})["helpers"] = n
    return sorted(rows.values(), key=lambda r: (r["region"], r["district"]))
