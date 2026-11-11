"""Pregnancy timing and risk windows.

A woman is protected from week 28 of pregnancy (third trimester) until 6 weeks after birth.
Risk windows are the parts of that period when she would normally do hazardous work:
- farm tasks from the crop labour calendar for her region and crop (farmers), and
- everyday heavy tasks linked to her livelihood (all women), in 4-week blocks so helpers can rotate.
"""
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from .. import models as m
from ..config import settings
from .reference import calendar_rows_for

# Planning assumptions for non-farm help: (hours per day, days per week)
NON_FARM_EFFORT = {
    "water": (1.0, 7), "household": (2.0, 5), "market": (4.0, 5),
    "livestock": (2.0, 7), "childcare": (3.0, 5), "escort": (3.0, 1),
}
BLOCK_DAYS = 28


@dataclass
class Window:
    key: str
    task_type: str
    activity: str
    start: date
    end: date
    pesticide: bool
    est_hours: float
    source: str  # crop | livelihood

    @property
    def days(self) -> int:
        return (self.end - self.start).days + 1


def gest_week(edd: date, on: Optional[date] = None) -> int:
    on = on or date.today()
    return int(40 - (edd - on).days / 7)


def trimester(week: int) -> int:
    return 1 if week < 14 else 2 if week < 28 else 3


def edd_from_months(months: int, on: Optional[date] = None) -> date:
    on = on or date.today()
    weeks_now = max(1, min(42, round(months * 4.33)))
    return on + timedelta(weeks=40 - weeks_now)


def protected_period(mother: m.Mother) -> tuple[date, date]:
    start = mother.edd - timedelta(weeks=40 - settings.RISK_START_WEEK)
    birth = mother.delivery_date or mother.edd
    return start, birth + timedelta(days=settings.POSTPARTUM_DAYS)


def _month_span(year: int, s: int, e: int) -> tuple[date, date]:
    start = date(year, s, 1)
    end_year = year if e >= s else year + 1
    end = (date(end_year + (e == 12), 1 if e == 12 else e + 1, 1)) - timedelta(days=1)
    return start, end


def windows(db: Session, mother: m.Mother) -> list[Window]:
    p_start, p_end = protected_period(mother)
    out: list[Window] = []

    if mother.livelihood == "farmer" and mother.crop:
        for c in calendar_rows_for(db, mother.region, mother.crop):
            if not (c.heavy_work or c.pesticide):
                continue
            for y in range(p_start.year - 1, p_end.year + 1):
                a, b = _month_span(y, c.start_month, c.end_month)
                s, e = max(a, p_start), min(b, p_end)
                if s <= e:
                    days = (e - s).days + 1
                    est = round(days / 7 * c.days_per_week * c.hours_per_day)
                    out.append(Window(
                        key=f"{mother.id}|crop|{c.id}|{s.isoformat()}", task_type=c.task_type,
                        activity=c.activity, start=s, end=e, pesticide=c.pesticide,
                        est_hours=est, source="crop"))

    for task in m.LIVELIHOOD_NEEDS.get(mother.livelihood, ["household"]):
        hpd, dpw = NON_FARM_EFFORT.get(task, (2.0, 5))
        sw, en = m.TASK_TYPES[task]
        s = p_start
        while s <= p_end:
            e = min(s + timedelta(days=BLOCK_DAYS - 1), p_end)
            days = (e - s).days + 1
            out.append(Window(
                key=f"{mother.id}|need|{task}|{s.isoformat()}", task_type=task,
                activity=f"{sw} ({en.lower()})", start=s, end=e, pesticide=False,
                est_hours=round(days / 7 * dpw * hpd), source="livelihood"))
            s = e + timedelta(days=1)

    return sorted(out, key=lambda w: (w.start, w.source != "crop"))


def upcoming_windows(db: Session, mother: m.Mother, on: Optional[date] = None, limit: int = 4) -> list[Window]:
    on = on or date.today()
    return [w for w in windows(db, mother) if w.end >= on][:limit]
