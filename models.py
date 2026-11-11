"""Data model for Mama Vuna Fresh."""
from datetime import date, datetime
from typing import Optional

from sqlalchemy import (Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text,
                        UniqueConstraint, func)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base

# ---- Reference values -------------------------------------------------------
ROLES = {
    "admin": "Administrator",
    "district_officer": "District health officer",
    "chw": "Community health worker",
}

# Who the mother is. Smallholder farmers are the core group; every pregnant woman can join.
LIVELIHOODS = {
    "farmer": ("Mkulima", "Smallholder farmer"),
    "livestock": ("Mfugaji", "Livestock keeper"),
    "market": ("Biashara / sokoni", "Market or small business"),
    "household": ("Kazi za nyumbani", "Home-based / household"),
    "labourer": ("Kibarua / kiwanda", "Casual or factory worker"),
    "employed": ("Mwajiriwa / ofisi", "Salaried or office work"),
    "other": ("Nyingine", "Other"),
}

SETTINGS_TYPES = {"rural": "Rural", "periurban": "Peri-urban", "urban": "Urban"}

# Kinds of help a helper can give. "pesticide" tasks only go to trained helpers.
TASK_TYPES = {
    "lifting": ("Kubeba mizigo mizito", "Heavy lifting and carrying"),
    "bending": ("Kazi za kuinama", "Bending work (planting, weeding, picking)"),
    "chemical": ("Kunyunyizia dawa", "Pesticide or chemical handling"),
    "water": ("Kuchota maji na kuni", "Fetching water and firewood"),
    "household": ("Kazi nzito za nyumbani", "Heavy household chores"),
    "market": ("Msaada wa biashara", "Help at market stall or shop"),
    "livestock": ("Kuhudumia mifugo", "Caring for livestock"),
    "escort": ("Kusindikiza kliniki", "Escort to clinic or hospital"),
    "childcare": ("Kulea watoto wengine", "Caring for older children"),
}

# Default help needed in late pregnancy for women who do not farm (or in addition to farm windows)
LIVELIHOOD_NEEDS = {
    "farmer": ["water"],
    "livestock": ["livestock", "water"],
    "market": ["market", "water"],
    "household": ["water", "household"],
    "labourer": ["household", "water"],
    "employed": ["household"],
    "other": ["household", "water"],
}

GROUP_TYPES = {
    "amcos": "Farmers' cooperative (AMCOS)",
    "vicoba": "Savings group (VICOBA / VSLA)",
    "women": "Women's group",
    "youth": "Youth group",
    "faith": "Faith group",
    "neighbourhood": "Neighbourhood / mtaa group",
    "other": "Other",
}

DANGER_SIGNS = {
    "bleeding": ("Kutokwa na damu ukeni", "Vaginal bleeding"),
    "convulsions": ("Degedege / kifafa", "Convulsions or fits"),
    "headache": ("Kichwa kuuma sana / kuona ukungu", "Severe headache or blurred vision"),
    "fever": ("Homa kali", "High fever"),
    "abdominal": ("Maumivu makali ya tumbo", "Severe abdominal pain"),
    "movement": ("Mtoto hachezi tumboni", "Baby moving less or not at all"),
    "waters": ("Chupa kupasuka", "Waters broke"),
    "swelling": ("Kuvimba uso au mikono", "Swelling of face or hands"),
    "breathing": ("Kupumua kwa shida", "Difficulty breathing"),
    "other": ("Tatizo jingine", "Other problem"),
}

REQUEST_STATUS = {
    "open": "Not yet alerted",
    "alerting": "Waiting for a helper",
    "accepted": "Helper confirmed",
    "verified": "Done and verified",
    "unfilled": "No helper found",
    "cancelled": "Cancelled",
}


def now() -> datetime:
    return datetime.now()


# ---- Tables -----------------------------------------------------------------
class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    phone: Mapped[Optional[str]] = mapped_column(String(20))
    role: Mapped[str] = mapped_column(String(30), default="chw")
    region: Mapped[Optional[str]] = mapped_column(String(60))
    district: Mapped[Optional[str]] = mapped_column(String(80))
    ward: Mapped[Optional[str]] = mapped_column(String(80))
    password_hash: Mapped[str] = mapped_column(String(255))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime)


class Location(Base):
    __tablename__ = "locations"
    __table_args__ = (UniqueConstraint("region", "district"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    region: Mapped[str] = mapped_column(String(60), index=True)
    district: Mapped[str] = mapped_column(String(80))
    zone: Mapped[Optional[str]] = mapped_column(String(40))


class CropActivity(Base):
    __tablename__ = "crop_activities"
    id: Mapped[int] = mapped_column(primary_key=True)
    region: Mapped[str] = mapped_column(String(60), index=True)  # "ALL" = national default
    season_system: Mapped[Optional[str]] = mapped_column(String(80))
    crop: Mapped[str] = mapped_column(String(80), index=True)
    activity: Mapped[str] = mapped_column(String(120))
    start_month: Mapped[int] = mapped_column(Integer)
    end_month: Mapped[int] = mapped_column(Integer)
    heavy_work: Mapped[bool] = mapped_column(Boolean, default=True)
    pesticide: Mapped[bool] = mapped_column(Boolean, default=False)
    task_type: Mapped[str] = mapped_column(String(20), default="lifting")
    hours_per_day: Mapped[float] = mapped_column(Float, default=6)
    days_per_week: Mapped[float] = mapped_column(Float, default=4)


class Facility(Base):
    __tablename__ = "facilities"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    level: Mapped[str] = mapped_column(String(40), default="dispensary")
    region: Mapped[str] = mapped_column(String(60), index=True)
    district: Mapped[str] = mapped_column(String(80), index=True)
    ward: Mapped[Optional[str]] = mapped_column(String(80))
    phone: Mapped[Optional[str]] = mapped_column(String(20))
    offers_emonc: Mapped[bool] = mapped_column(Boolean, default=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Group(Base):
    __tablename__ = "groups"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    group_type: Mapped[str] = mapped_column(String(30), default="other")
    region: Mapped[str] = mapped_column(String(60))
    district: Mapped[str] = mapped_column(String(80))
    ward: Mapped[Optional[str]] = mapped_column(String(80))
    village: Mapped[Optional[str]] = mapped_column(String(80))
    leader_name: Mapped[Optional[str]] = mapped_column(String(120))
    leader_phone: Mapped[Optional[str]] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    helpers = relationship("Helper", back_populates="group")


class Mother(Base):
    __tablename__ = "mothers"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    phone: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    language: Mapped[str] = mapped_column(String(2), default="sw")
    age: Mapped[Optional[int]] = mapped_column(Integer)
    region: Mapped[str] = mapped_column(String(60), index=True)
    district: Mapped[str] = mapped_column(String(80), index=True)
    ward: Mapped[Optional[str]] = mapped_column(String(80))
    village: Mapped[Optional[str]] = mapped_column(String(80))
    setting: Mapped[str] = mapped_column(String(12), default="rural")
    livelihood: Mapped[str] = mapped_column(String(20), default="farmer")
    crop: Mapped[Optional[str]] = mapped_column(String(80))
    edd: Mapped[date] = mapped_column(Date)
    edd_source: Mapped[str] = mapped_column(String(20), default="mother")  # mother | months | chw | scan
    gravida: Mapped[Optional[int]] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="pregnant")  # pregnant | delivered | closed
    risk_flag: Mapped[str] = mapped_column(String(12), default="normal")  # normal | watch | high
    risk_note: Mapped[Optional[str]] = mapped_column(Text)
    delivery_date: Mapped[Optional[date]] = mapped_column(Date)
    chw_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))
    facility_id: Mapped[Optional[int]] = mapped_column(ForeignKey("facilities.id"))
    consent_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    opted_out: Mapped[bool] = mapped_column(Boolean, default=False)
    last_tip_week: Mapped[int] = mapped_column(Integer, default=0)
    registered_via: Mapped[str] = mapped_column(String(10), default="ussd")
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)

    chw = relationship("User", foreign_keys=[chw_id])
    facility = relationship("Facility")
    requests = relationship("SupportRequest", back_populates="mother", cascade="all, delete-orphan")
    visits = relationship("Visit", back_populates="mother", cascade="all, delete-orphan")
    danger_reports = relationship("DangerReport", back_populates="mother", cascade="all, delete-orphan")
    outcome = relationship("BirthOutcome", back_populates="mother", uselist=False, cascade="all, delete-orphan")


class Helper(Base):
    __tablename__ = "helpers"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    phone: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    language: Mapped[str] = mapped_column(String(2), default="sw")
    sex: Mapped[Optional[str]] = mapped_column(String(1))
    region: Mapped[str] = mapped_column(String(60), index=True)
    district: Mapped[str] = mapped_column(String(80), index=True)
    ward: Mapped[Optional[str]] = mapped_column(String(80))
    village: Mapped[Optional[str]] = mapped_column(String(80))
    group_id: Mapped[Optional[int]] = mapped_column(ForeignKey("groups.id"))
    skills: Mapped[str] = mapped_column(String(200), default="lifting,bending,water,household")
    pesticide_trained: Mapped[bool] = mapped_column(Boolean, default=False)
    available: Mapped[bool] = mapped_column(Boolean, default=True)
    opted_out: Mapped[bool] = mapped_column(Boolean, default=False)
    credit_hours: Mapped[float] = mapped_column(Float, default=0)
    consent_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    registered_via: Mapped[str] = mapped_column(String(10), default="web")
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)

    group = relationship("Group", back_populates="helpers")

    def skill_list(self) -> list[str]:
        s = [x.strip() for x in (self.skills or "").split(",") if x.strip()]
        if self.pesticide_trained and "chemical" not in s:
            s.append("chemical")
        return s


class SupportRequest(Base):
    __tablename__ = "support_requests"
    id: Mapped[int] = mapped_column(primary_key=True)
    mother_id: Mapped[int] = mapped_column(ForeignKey("mothers.id", ondelete="CASCADE"), index=True)
    window_key: Mapped[Optional[str]] = mapped_column(String(200), unique=True)
    task_type: Mapped[str] = mapped_column(String(20))
    activity: Mapped[str] = mapped_column(String(160))
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    est_hours: Mapped[float] = mapped_column(Float, default=0)
    status: Mapped[str] = mapped_column(String(12), default="open", index=True)
    source: Mapped[str] = mapped_column(String(10), default="auto")  # auto | ussd | sms | chw
    helper_id: Mapped[Optional[int]] = mapped_column(ForeignKey("helpers.id"))
    verified_hours: Mapped[Optional[float]] = mapped_column(Float)
    verified_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))
    verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    note: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)

    mother = relationship("Mother", back_populates="requests")
    helper = relationship("Helper", foreign_keys=[helper_id])
    alerts = relationship("Alert", back_populates="request", cascade="all, delete-orphan",
                          order_by="Alert.sent_at")


class Alert(Base):
    """One attempt to ask one helper to take on one support request."""
    __tablename__ = "alerts"
    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("support_requests.id", ondelete="CASCADE"), index=True)
    helper_id: Mapped[int] = mapped_column(ForeignKey("helpers.id"), index=True)
    score: Mapped[float] = mapped_column(Float, default=0)
    reason: Mapped[Optional[str]] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(12), default="sent")  # sent | accepted | declined | timeout | withdrawn
    sent_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    responded_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    channel: Mapped[str] = mapped_column(String(8), default="sms")

    request = relationship("SupportRequest", back_populates="alerts")
    helper = relationship("Helper")


class LedgerEntry(Base):
    """Hash-chained record of verified help. Stores only codes, never names or health data."""
    __tablename__ = "ledger"
    id: Mapped[int] = mapped_column(primary_key=True)
    seq: Mapped[int] = mapped_column(Integer, unique=True)
    recorded_on: Mapped[str] = mapped_column(String(10))
    helper_code: Mapped[str] = mapped_column(String(20))
    mother_code: Mapped[str] = mapped_column(String(20))
    request_id: Mapped[int] = mapped_column(Integer)
    task_type: Mapped[str] = mapped_column(String(20))
    hours: Mapped[float] = mapped_column(Float)
    verifier_code: Mapped[str] = mapped_column(String(20))
    prev_hash: Mapped[str] = mapped_column(String(64))
    hash: Mapped[str] = mapped_column(String(64))


class DangerReport(Base):
    __tablename__ = "danger_reports"
    id: Mapped[int] = mapped_column(primary_key=True)
    mother_id: Mapped[int] = mapped_column(ForeignKey("mothers.id", ondelete="CASCADE"), index=True)
    signs: Mapped[str] = mapped_column(String(200))
    via: Mapped[str] = mapped_column(String(10), default="ussd")
    status: Mapped[str] = mapped_column(String(12), default="new")  # new | contacted | referred | resolved
    facility_id: Mapped[Optional[int]] = mapped_column(ForeignKey("facilities.id"))
    handled_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))
    notes: Mapped[Optional[str]] = mapped_column(Text)
    reported_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    first_contact_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    mother = relationship("Mother", back_populates="danger_reports")
    facility = relationship("Facility")


class Visit(Base):
    """CHW follow-up. Its answers are the source for measured outcome indicators."""
    __tablename__ = "visits"
    id: Mapped[int] = mapped_column(primary_key=True)
    mother_id: Mapped[int] = mapped_column(ForeignKey("mothers.id", ondelete="CASCADE"), index=True)
    chw_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))
    visit_date: Mapped[date] = mapped_column(Date)
    kind: Mapped[str] = mapped_column(String(10), default="home")  # home | phone
    gest_week: Mapped[Optional[int]] = mapped_column(Integer)
    did_heavy_work: Mapped[Optional[bool]] = mapped_column(Boolean)
    handled_pesticide: Mapped[Optional[bool]] = mapped_column(Boolean)
    help_received: Mapped[Optional[bool]] = mapped_column(Boolean)
    anc_up_to_date: Mapped[Optional[bool]] = mapped_column(Boolean)
    danger_signs_seen: Mapped[Optional[bool]] = mapped_column(Boolean)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)

    mother = relationship("Mother", back_populates="visits")
    chw = relationship("User")


class BirthOutcome(Base):
    __tablename__ = "birth_outcomes"
    id: Mapped[int] = mapped_column(primary_key=True)
    mother_id: Mapped[int] = mapped_column(ForeignKey("mothers.id", ondelete="CASCADE"), unique=True)
    delivery_date: Mapped[date] = mapped_column(Date)
    place: Mapped[str] = mapped_column(String(12), default="facility")  # facility | home | transit
    gest_weeks: Mapped[Optional[int]] = mapped_column(Integer)
    birth_weight_g: Mapped[Optional[int]] = mapped_column(Integer)
    outcome: Mapped[str] = mapped_column(String(12), default="live")  # live | stillbirth
    mother_complication: Mapped[Optional[bool]] = mapped_column(Boolean)
    referred: Mapped[Optional[bool]] = mapped_column(Boolean)
    source: Mapped[str] = mapped_column(String(12), default="chw")  # chw | facility | mother
    notes: Mapped[Optional[str]] = mapped_column(Text)
    recorded_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)

    mother = relationship("Mother", back_populates="outcome")

    @property
    def preterm(self) -> Optional[bool]:
        return None if self.gest_weeks is None else self.gest_weeks < 37

    @property
    def low_birth_weight(self) -> Optional[bool]:
        return None if self.birth_weight_g is None else self.birth_weight_g < 2500


class Message(Base):
    __tablename__ = "messages"
    id: Mapped[int] = mapped_column(primary_key=True)
    direction: Mapped[str] = mapped_column(String(3))  # in | out
    phone: Mapped[str] = mapped_column(String(20), index=True)
    body: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(12), default="queued")  # queued | sent | failed | logged | received | delivered
    provider_id: Mapped[Optional[str]] = mapped_column(String(80), index=True)
    error: Mapped[Optional[str]] = mapped_column(String(255))
    kind: Mapped[Optional[str]] = mapped_column(String(20))  # alert | confirm | tip | danger | system
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class UssdLog(Base):
    __tablename__ = "ussd_log"
    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[Optional[str]] = mapped_column(String(80), index=True)
    phone: Mapped[str] = mapped_column(String(20))
    text: Mapped[str] = mapped_column(Text, default="")
    response: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class AuditLog(Base):
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(60))
    entity: Mapped[Optional[str]] = mapped_column(String(40))
    entity_id: Mapped[Optional[int]] = mapped_column(Integer)
    detail: Mapped[Optional[str]] = mapped_column(Text)
    at: Mapped[datetime] = mapped_column(DateTime, default=now)

    user = relationship("User")


class SystemState(Base):
    __tablename__ = "system_state"
    key: Mapped[str] = mapped_column(String(60), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=func.now())
