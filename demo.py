"""Training data for demos and staff training. Every record is flagged is_demo and is
left out of all indicators and reports. Load it only on a training server."""
from datetime import date, timedelta

from sqlalchemy.orm import Session

from .. import models as m
from .mothers import find_or_create_group, register_helper, register_mother

REGION, DISTRICT = "Morogoro", "Mvomero"


def load(db: Session) -> int:
    if db.query(m.Mother).filter(m.Mother.is_demo.is_(True)).count():
        return 0
    today = date.today()
    groups = {
        "upendo": find_or_create_group(db, "Upendo Women's Group (demo)", REGION, DISTRICT, "Mtibwa"),
        "tumaini": find_or_create_group(db, "VICOBA Tumaini (demo)", REGION, DISTRICT, "Mtibwa"),
        "vijana": find_or_create_group(db, "Mtibwa Youth Group (demo)", REGION, DISTRICT, "Mtibwa"),
    }
    groups["upendo"].group_type, groups["tumaini"].group_type, groups["vijana"].group_type = "women", "vicoba", "youth"
    helpers = [
        ("Neema Saidi", "+255700100001", "Kidudwe", "upendo", "lifting,bending,water,household,childcare", False, "F"),
        ("Baraka Kombo", "+255700100002", "Kidudwe", "vijana", "lifting,bending,water", True, "M"),
        ("Halima Rajabu", "+255700100003", "Lusanga", "tumaini", "water,household,market,childcare,escort", False, "F"),
        ("Juma Mfaume", "+255700100004", "Lusanga", "vijana", "lifting,bending,livestock", True, "M"),
        ("Zawadi Ally", "+255700100005", "Kidudwe", "tumaini", "water,household,escort", False, "F"),
    ]
    for name, phone, village, g, skills, pest, sex in helpers:
        if not db.query(m.Helper).filter(m.Helper.phone == phone).first():
            register_helper(db, name=name, phone=phone, region=REGION, district=DISTRICT, ward="Mtibwa",
                            village=village, group=groups[g], skills=skills, pesticide_trained=pest, sex=sex,
                            is_demo=True)
    mothers = [
        ("Rehema Mussa", "+255700200001", 26, "Kidudwe", "rural", "farmer", "Mahindi (maize)", today + timedelta(days=60)),
        ("Asha Omari", "+255700200002", 31, "Lusanga", "rural", "farmer", "Mpunga (rice paddy)", today + timedelta(days=95)),
        ("Mwajuma Hassan", "+255700200003", 22, "Mtibwa Mjini", "periurban", "market", None, today + timedelta(days=40)),
        ("Grace Lyimo", "+255700200004", 29, "Kidudwe", "rural", "livestock", None, today + timedelta(days=120)),
    ]
    n = 0
    for name, phone, age, village, setting, liv, crop, edd in mothers:
        if db.query(m.Mother).filter(m.Mother.phone == phone).first():
            continue
        register_mother(db, name=name, phone=phone, region=REGION, district=DISTRICT, ward="Mtibwa", village=village,
                        setting=setting, livelihood=liv, crop=crop, age=age, edd=edd, via="web", is_demo=True,
                        send_welcome=False)
        n += 1
    if not db.query(m.Facility).filter(m.Facility.district == DISTRICT).first():
        db.add(m.Facility(name="Mtibwa Dispensary (demo)", level="dispensary", region=REGION, district=DISTRICT,
                          ward="Mtibwa", phone="+255700300001"))
    db.commit()
    return n


def remove(db: Session) -> int:
    n = 0
    phones = {p for (p,) in db.query(m.Mother.phone).filter(m.Mother.is_demo.is_(True))} | \
             {p for (p,) in db.query(m.Helper.phone).filter(m.Helper.is_demo.is_(True))}
    for mo in db.query(m.Mother).filter(m.Mother.is_demo.is_(True)).all():
        db.delete(mo)
        n += 1
    db.flush()
    for h in db.query(m.Helper).filter(m.Helper.is_demo.is_(True)).all():
        db.query(m.Alert).filter(m.Alert.helper_id == h.id).delete()
        db.query(m.SupportRequest).filter(m.SupportRequest.helper_id == h.id).update({"helper_id": None})
        db.delete(h)
    for g in db.query(m.Group).filter(m.Group.name.like("%(demo)")).all():
        db.delete(g)
    db.query(m.Facility).filter(m.Facility.name.like("%(demo)")).delete(synchronize_session=False)
    if phones:
        db.query(m.Message).filter(m.Message.phone.in_(phones)).delete(synchronize_session=False)
    db.commit()
    return n
