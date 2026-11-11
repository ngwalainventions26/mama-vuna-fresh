"""Reference data: Tanzanian locations and the crop labour calendar (CSV import/export)."""
import csv
import io
from typing import Iterable

from sqlalchemy.orm import Session

from .. import models as m
from ..config import BASE_DIR
from .common import MONTHS

DATA = BASE_DIR / "data"

# Default effort assumptions for planning estimates (not measured hours)
DEFAULT_EFFORT = {"lifting": (6, 4), "bending": (6, 4), "chemical": (3, 2)}
CAL_COLUMNS = ["region", "season_system", "crop", "activity", "start_month", "end_month",
               "heavy_work", "pesticide", "task_type", "hours_per_day", "days_per_week"]


def _yes(v) -> bool:
    return str(v or "").strip().lower() in ("y", "yes", "1", "true", "ndiyo", "x")


def _month(v) -> int:
    v = str(v or "").strip()
    if v.isdigit():
        return int(v)
    for i, name in enumerate(MONTHS):
        if v.lower().startswith(name.lower()):
            return i + 1
    return 0


def parse_calendar_csv(text: str) -> list[dict]:
    """Validate a crop calendar CSV. Raises ValueError with a readable message."""
    reader = csv.DictReader(io.StringIO(text.lstrip("﻿")))
    cols = [c.strip().lower().replace(" ", "_") for c in (reader.fieldnames or [])]
    for need in ("crop", "activity", "start_month", "end_month"):
        if need not in cols:
            raise ValueError(f'Missing column "{need}". Required: crop, activity, start_month, end_month.')
    rows, errors = [], []
    for n, raw in enumerate(reader, start=2):
        r = {k.strip().lower().replace(" ", "_"): (v or "").strip() for k, v in raw.items() if k}
        s, e = _month(r.get("start_month")), _month(r.get("end_month"))
        if not r.get("crop") or not r.get("activity") or not (1 <= s <= 12) or not (1 <= e <= 12):
            errors.append(f"row {n}")
            continue
        pest = _yes(r.get("pesticide"))
        tt = r.get("task_type") or ("chemical" if pest else "lifting")
        if tt not in m.TASK_TYPES:
            tt = "chemical" if pest else "lifting"
        hpd, dpw = DEFAULT_EFFORT.get(tt, (6, 4))
        rows.append(dict(
            region=r.get("region") or "ALL", season_system=r.get("season_system") or None,
            crop=r["crop"], activity=r["activity"], start_month=s, end_month=e,
            heavy_work=_yes(r.get("heavy_work")) if r.get("heavy_work") else not pest,
            pesticide=pest, task_type=tt,
            hours_per_day=float(r.get("hours_per_day") or hpd),
            days_per_week=float(r.get("days_per_week") or dpw),
        ))
    if not rows:
        raise ValueError("No valid rows found. Check the month columns (1-12 or Jan-Dec).")
    if errors and len(errors) > len(rows):
        raise ValueError(f"Too many invalid rows ({len(errors)}), e.g. {', '.join(errors[:5])}.")
    return rows


def replace_calendar(db: Session, rows: Iterable[dict]) -> int:
    db.query(m.CropActivity).delete()
    n = 0
    for r in rows:
        db.add(m.CropActivity(**r))
        n += 1
    db.commit()
    return n


def calendar_csv(db: Session) -> str:
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(CAL_COLUMNS)
    for c in db.query(m.CropActivity).order_by(m.CropActivity.region, m.CropActivity.crop, m.CropActivity.start_month):
        w.writerow([c.region, c.season_system or "", c.crop, c.activity, c.start_month, c.end_month,
                    "yes" if c.heavy_work else "no", "yes" if c.pesticide else "no", c.task_type,
                    c.hours_per_day, c.days_per_week])
    return out.getvalue()


def load_reference_data(db: Session) -> None:
    """Load locations and the built-in crop calendar the first time the platform starts."""
    if db.query(m.Location).count() == 0:
        with open(DATA / "locations.csv", newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                db.add(m.Location(region=r["region"], district=r["district"], zone=r.get("zone")))
        db.commit()
    if db.query(m.CropActivity).count() == 0:
        replace_calendar(db, parse_calendar_csv((DATA / "crop_calendar.csv").read_text(encoding="utf-8")))


def regions(db: Session) -> list[str]:
    return [r[0] for r in db.query(m.Location.region).distinct().order_by(m.Location.region)]


def districts(db: Session, region: str) -> list[str]:
    return [r[0] for r in db.query(m.Location.district).filter(m.Location.region == region)
            .order_by(m.Location.district)]


def crops_for_region(db: Session, region: str) -> list[str]:
    own = [r[0] for r in db.query(m.CropActivity.crop).filter(m.CropActivity.region == region)
           .distinct().order_by(m.CropActivity.crop)]
    if own:
        return own
    return [r[0] for r in db.query(m.CropActivity.crop).filter(m.CropActivity.region == "ALL")
            .distinct().order_by(m.CropActivity.crop)]


def calendar_rows_for(db: Session, region: str, crop: str) -> list[m.CropActivity]:
    rows = db.query(m.CropActivity).filter(m.CropActivity.region == region, m.CropActivity.crop == crop).all()
    if not rows:
        rows = db.query(m.CropActivity).filter(m.CropActivity.region == "ALL", m.CropActivity.crop == crop).all()
    return rows


def nearest_facility(db: Session, mother: m.Mother):
    if mother.facility_id:
        return mother.facility
    q = db.query(m.Facility).filter(m.Facility.active.is_(True), m.Facility.district == mother.district)
    if mother.ward:
        f = q.filter(m.Facility.ward == mother.ward).first()
        if f:
            return f
    return q.order_by(m.Facility.offers_emonc.desc()).first()
