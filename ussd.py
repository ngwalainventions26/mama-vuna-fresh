"""USSD menus. Stateless: the gateway sends every answer so far joined by "*" (Africa's Talking style),
and each request replays the menu from the start. Replies start with CON (keep session open) or END.
"""
import re
from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from .. import models as m
from ..config import settings
from . import reference
from .common import first_name, label_for, short_date
from .matching import pending_alert, respond
from .mothers import change_edd, help_now, register_helper, register_mother, report_birth, report_danger, \
    find_or_create_group
from .pregnancy import edd_from_months, gest_week, upcoming_windows
from .texts import t

PAGE = 7
LIVELIHOOD_ORDER = ["farmer", "livestock", "market", "household", "labourer", "employed", "other"]
SETTING_ORDER = ["rural", "periurban", "urban"]
HELP_ORDER = ["lifting", "bending", "water", "household", "market", "livestock", "childcare", "escort"]
DANGER_ORDER = list(m.DANGER_SIGNS.keys())
STATUS_SW = {"open": "tunatafuta", "alerting": "tunatafuta", "accepted": "msaidizi yupo",
             "verified": "imekamilika", "unfilled": "CHW atapanga", "cancelled": "imesitishwa"}
STATUS_EN = {"open": "finding helper", "alerting": "finding helper", "accepted": "helper confirmed",
             "verified": "done", "unfilled": "CHW will arrange", "cancelled": "cancelled"}


class Need(Exception):
    """More input is needed: show this screen (CON)."""


class Done(Exception):
    """End the session with this screen (END)."""


class Flow:
    def __init__(self, parts: list[str], lang: str):
        self.parts, self.i, self.lang = parts, 0, lang

    def take(self, screen: str) -> str:
        if self.i >= len(self.parts):
            raise Need(screen)
        v = self.parts[self.i].strip()
        self.i += 1
        return v

    def end(self, key: str, **kw):
        raise Done(t(self.lang, key, **kw))

    def invalid(self):
        self.end("invalid", code=settings.USSD_SERVICE_CODE)

    def text(self, key: str, min_len: int = 2) -> str:
        v = self.take(t(self.lang, key))
        if len(v) < min_len:
            self.invalid()
        return v

    def number(self, key: str, lo: int, hi: int) -> int:
        v = self.take(t(self.lang, key))
        if not v.isdigit() or not (lo <= int(v) <= hi):
            self.invalid()
        return int(v)

    def choose(self, head: str, options: list[str]) -> int:
        page = 0
        while True:
            chunk = options[page * PAGE:(page + 1) * PAGE]
            more = (page + 1) * PAGE < len(options)
            screen = head + "\n" + "\n".join(f"{n}. {o}" for n, o in enumerate(chunk, 1))
            if more:
                screen += "\n" + t(self.lang, "more")
            v = self.take(screen)
            if v == "98" and more:
                page += 1
                continue
            if v.isdigit() and 1 <= int(v) <= len(chunk):
                return page * PAGE + int(v) - 1
            self.invalid()

    def menu(self, screen: str, n: int) -> int:
        v = self.take(screen)
        if not v.isdigit() or not (1 <= int(v) <= n):
            self.invalid()
        return int(v)

    def date(self, key: str) -> date:
        v = self.take(t(self.lang, key))
        d = parse_date(v)
        if not d:
            self.end("bad_date", code=settings.USSD_SERVICE_CODE)
        return d


def parse_date(v: str):
    v = v.strip()
    mt = re.match(r"^(\d{1,2})[-/. ](\d{1,2})[-/. ](\d{4})$", v) or re.match(r"^(\d{2})(\d{2})(\d{4})$", v)
    if not mt:
        return None
    try:
        return date(int(mt.group(3)), int(mt.group(2)), int(mt.group(1)))
    except ValueError:
        return None


def _flip(lang: str) -> str:
    return "en" if lang == "sw" else "sw"


# ---------------------------------------------------------------- entry point
def handle(db: Session, phone: str, text: str) -> str:
    parts = [p for p in (text or "").split("*")] if text else []
    mother = db.query(m.Mother).filter(m.Mother.phone == phone, m.Mother.status != "closed").first()
    helper = None if mother else db.query(m.Helper).filter(m.Helper.phone == phone).first()
    lang = (mother or helper).language if (mother or helper) else "sw"
    flow = Flow(parts, lang)
    try:
        if mother:
            mother_menu(db, flow, mother)
        elif helper:
            helper_menu(db, flow, helper)
        else:
            new_caller(db, flow, phone)
        flow.invalid()
    except Need as e:
        return "CON " + str(e)
    except Done as e:
        db.commit()
        return "END " + str(e)
    except Exception:
        db.rollback()
        import logging
        logging.getLogger("mamavuna.ussd").exception("USSD error for %s text=%r", phone, text)
        return "END " + ("Samahani, kuna tatizo. Jaribu tena baadaye." if lang == "sw"
                         else "Sorry, something went wrong. Please try again later.")
    return "END " + t(lang, "bye")


# ---------------------------------------------------------------- new callers
def new_caller(db: Session, f: Flow, phone: str):
    while True:
        c = f.menu(t(f.lang, "welcome_new"), 4)
        if c == 4:
            f.lang = _flip(f.lang)
            continue
        break
    if c == 1:
        if db.query(m.Mother).filter(m.Mother.phone == phone).first():
            f.end("already_mother")
        register_mother_flow(db, f, phone)
    elif c == 2:
        register_helper_flow(db, f, phone)
    elif c == 3:
        f.end("danger_nonreg")


def _location(db: Session, f: Flow):
    regs = reference.regions(db)
    region = regs[f.choose(t(f.lang, "ask_region"), regs)]
    dists = reference.districts(db, region)
    district = dists[f.choose(t(f.lang, "ask_district"), dists)]
    ward = f.text("ask_ward")
    village = f.text("ask_village")
    return region, district, ward, village


def register_mother_flow(db: Session, f: Flow, phone: str):
    name = f.text("ask_name", 3)
    age = f.number("ask_age", 12, 55)
    region, district, ward, village = _location(db, f)
    setting = SETTING_ORDER[f.menu(t(f.lang, "ask_setting"), 3) - 1]
    livelihood = LIVELIHOOD_ORDER[f.menu(t(f.lang, "ask_livelihood"), 7) - 1]
    crop = None
    if livelihood == "farmer":
        crops = reference.crops_for_region(db, region)
        if crops:
            crop = crops[f.choose(t(f.lang, "ask_crop"), [label_for(c, f.lang) for c in crops])]
    how = f.menu(t(f.lang, "ask_preg"), 2)
    if how == 1:
        edd, source = f.date("ask_edd"), "mother"
    else:
        edd, source = edd_from_months(f.number("ask_months", 1, 9)), "months"
    if not (date.today() - timedelta(days=14) <= edd <= date.today() + timedelta(days=300)):
        f.end("bad_edd_range", code=settings.USSD_SERVICE_CODE)
    if f.menu(t(f.lang, "ask_consent"), 2) != 1:
        f.end("no_consent")
    mother = register_mother(db, name=name, phone=phone, region=region, district=district, ward=ward,
                             village=village, setting=setting, livelihood=livelihood, crop=crop, age=age,
                             language=f.lang, edd=edd, edd_source=source, via="ussd")
    f.end("reg_done", first=first_name(mother.name), code=mother.code)


def register_helper_flow(db: Session, f: Flow, phone: str):
    name = f.text("ask_name", 3)
    region, district, ward, village = _location(db, f)
    group_name = f.take(t(f.lang, "ask_group"))
    skills = {1: "lifting,bending,escort", 2: "water,household,childcare,market,livestock,escort",
              3: "lifting,bending,water,household,childcare,market,livestock,escort"}[f.menu(t(f.lang, "ask_skills"), 3)]
    if f.menu(t(f.lang, "helper_consent"), 2) != 1:
        f.end("no_consent")
    group = find_or_create_group(db, group_name, region, district, ward)
    h = register_helper(db, name=name, phone=phone, region=region, district=district, ward=ward, village=village,
                        group=group, skills=skills, language=f.lang, via="ussd")
    f.end("helper_reg_done", first=first_name(h.name))


# ---------------------------------------------------------------- registered mother
def mother_menu(db: Session, f: Flow, mother: m.Mother):
    c = f.menu(t(f.lang, "mother_menu", first=first_name(mother.name)), 6)
    if c == 1:
        week = gest_week(mother.edd) if mother.status == "pregnant" else None
        head = (t(f.lang, "status_head", week=week, edd=mother.edd.strftime("%d/%m/%Y"))
                if week is not None else f"{mother.code}\n")
        reqs = {r.window_key: r for r in mother.requests if r.window_key}
        lines = []
        for w in upcoming_windows(db, mother, limit=3):
            r = reqs.get(w.key)
            st = (STATUS_SW if f.lang == "sw" else STATUS_EN).get(r.status if r else "", "")
            lines.append(f"{short_date(w.start, f.lang)}: {label_for(w.activity, f.lang)}" + (f" - {st}" if st else ""))
        raise Done(head + ("\n".join(lines) if lines else t(f.lang, "status_none")))
    if c == 2:
        opts = [o for o in HELP_ORDER if o != "bending" or mother.livelihood == "farmer"]
        task = opts[f.choose(t(f.lang, "ask_help_type"), [m.TASK_TYPES[o][0 if f.lang == "sw" else 1] for o in opts])]
        req, alert, dup = help_now(db, mother, task)
        if dup:
            f.end("help_dup")
        if alert:
            f.end("help_sent", helper=alert.helper.name)
        f.end("help_none")
    if c == 3:
        signs = DANGER_ORDER
        sign = signs[f.choose(t(f.lang, "danger_ask"), [m.DANGER_SIGNS[s][0 if f.lang == "sw" else 1] for s in signs])]
        rep = report_danger(db, mother, [sign], via="ussd")
        fac = rep.facility
        fac_txt = f"{fac.name}{' ' + fac.phone if fac.phone else ''}. " if fac else ""
        f.end("danger_done", facility=fac_txt)
    if c == 4:
        when = f.menu(t(f.lang, "ask_birth"), 3)
        on = date.today() if when == 1 else date.today() - timedelta(days=1) if when == 2 else f.date("ask_birth_date")
        if on > date.today() or on < date.today() - timedelta(days=60):
            f.end("bad_date", code=settings.USSD_SERVICE_CODE)
        report_birth(db, mother, on, via="ussd")
        f.end("birth_done")
    if c == 5:
        edd = f.date("ask_edd")
        if not (date.today() - timedelta(days=14) <= edd <= date.today() + timedelta(days=300)):
            f.end("bad_edd_range", code=settings.USSD_SERVICE_CODE)
        change_edd(db, mother, edd, source="mother")
        f.end("edd_changed", edd=edd.strftime("%d/%m/%Y"))
    if c == 6:
        mother.language = _flip(mother.language)
        f.lang = mother.language
        f.end("lang_set")


# ---------------------------------------------------------------- registered helper
def helper_menu(db: Session, f: Flow, helper: m.Helper):
    n = db.query(m.Alert).filter(m.Alert.helper_id == helper.id, m.Alert.status == "sent").count()
    avail = t(f.lang, "avail_on" if helper.available else "avail_off")
    c = f.menu(t(f.lang, "helper_menu", first=first_name(helper.name), n=n, avail=avail), 4)
    if c == 1:
        a = pending_alert(db, helper)
        if not a:
            f.end("helper_no_req")
        r = a.request
        screen = t(f.lang, "helper_req_line",
                   when=f"{short_date(r.start_date, f.lang)}-{short_date(r.end_date, f.lang)}",
                   task=label_for(r.activity, f.lang), village=r.mother.village or r.mother.ward or r.mother.district)
        ans = f.menu(screen, 2)
        raise Done(respond(db, helper, ans == 1, a))
    if c == 2:
        f.end("helper_hours", hours=f"{helper.credit_hours:g}")
    if c == 3:
        helper.available = not helper.available
        f.end("avail_now_on" if helper.available else "avail_now_off")
    if c == 4:
        helper.language = _flip(helper.language)
        f.lang = helper.language
        f.end("lang_set")
