"""Small shared helpers: phone numbers, codes, labels, audit trail."""
import re
from datetime import date, datetime
from typing import Optional

from sqlalchemy.orm import Session

from .. import models as m

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
MIEZI = ["Jan", "Feb", "Mac", "Apr", "Mei", "Jun", "Jul", "Ago", "Sep", "Okt", "Nov", "Des"]


def normalize_phone(raw: Optional[str]) -> str:
    """Return a Tanzanian number in +255XXXXXXXXX form where possible."""
    if not raw:
        return ""
    p = re.sub(r"[^\d+]", "", raw.strip())
    if p.startswith("+"):
        return p
    if p.startswith("00"):
        return "+" + p[2:]
    if p.startswith("255"):
        return "+" + p
    if p.startswith("0") and len(p) == 10:
        return "+255" + p[1:]
    if len(p) == 9:
        return "+255" + p
    return p


def mask_phone(p: str) -> str:
    return p[:7] + "•••" + p[-2:] if p and len(p) > 9 else p


def short_date(d: date, lang: str = "sw") -> str:
    return f"{d.day} {(MIEZI if lang == 'sw' else MONTHS)[d.month - 1]}"


def fmt_date(d: Optional[date]) -> str:
    return d.strftime("%d/%m/%Y") if d else ""


def first_name(name: str) -> str:
    return (name or "").split(" ")[0]


def sw_part(label: str) -> str:
    """'Kuvuna (harvest)' -> 'Kuvuna'"""
    return label.split(" (")[0]


def en_part(label: str) -> str:
    mt = re.search(r"\(([^)]+)\)", label or "")
    return mt.group(1) if mt else label


def label_for(label: str, lang: str) -> str:
    return sw_part(label) if lang == "sw" else en_part(label)


def task_label(task_type: str, lang: str = "en") -> str:
    sw, en = m.TASK_TYPES.get(task_type, (task_type, task_type))
    return sw if lang == "sw" else en


def next_mother_code(db: Session) -> str:
    last = db.query(m.Mother.id).order_by(m.Mother.id.desc()).first()
    return f"MVF-{(last[0] if last else 0) + 1:06d}"


def helper_code(h_id: int) -> str:
    return f"HLP-{h_id:05d}"


def user_code(u_id: Optional[int]) -> str:
    return f"USR-{u_id:04d}" if u_id else "SYSTEM"


def audit(db: Session, user: Optional[m.User], action: str, entity: str = None,
          entity_id: int = None, detail: str = None) -> None:
    db.add(m.AuditLog(user_id=user.id if user else None, action=action, entity=entity,
                      entity_id=entity_id, detail=detail, at=datetime.now()))
