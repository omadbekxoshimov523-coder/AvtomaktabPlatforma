"""Biznes qoidalar: session yaratish/ko'chirish oldidan barcha tekshiruvlar.
Mijoz talabidagi 10 ta majburiy backend tekshiruv + qo'shimchalar shu yerda.
"""
from datetime import datetime

from .db import jload, now
import json

WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
# ISO weekday -> index
_ISO = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}


def _hm(t: str):
    h, m = t.split(":")
    return int(h) * 60 + int(m)


def _overlap(s1, e1, s2, e2) -> bool:
    """[s1,e1) va [s2,e2) kesishadimi?"""
    return s1 < e2 and s2 < e1


def parse_date(value: str):
    for fmt in ("%Y-%m-%d", "%d.%m.%Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def validate_time_range(start: str, end: str) -> str | None:
    try:
        s, e = _hm(start), _hm(end)
    except Exception:
        return "invalid_time"
    if s >= e:
        return "time_order"
    if e - s > 8 * 60:
        return "session_too_long"
    return None


def check_session_rules(db, date: str, start: str, end: str, instructor_id: int,
                        student_ids: list, exclude_session_id: int | None = None,
                        new_instructor_id: int | None = None):
    """Barcha business qoidalarni tekshiradi. Xatolar ro'yxatini qaytaradi.
    Agar qoida buzilsa, xato kod qaytariladi.
    """
    errors = []

    if not parse_date(date):
        return ["invalid_date"]

    t_err = validate_time_range(start, end)
    if t_err:
        return [t_err]

    inst = db.q1(
        """SELECT i.*, u.first_name, u.last_name, u.status AS user_status
           FROM instructors i JOIN users u ON u.id=i.user_id
           WHERE i.id=? AND u.deleted_at IS NULL""",
        (instructor_id,),
    )
    if not inst:
        return ["instructor_not_found"]
    if inst["user_status"] == "blocked":
        return ["instructor_blocked"]
    if inst["status"] != "active":
        return ["instructor_inactive"]

    # 1. Ish jadvali
    d = parse_date(date)
    wd = d.strftime("%a").lower()
    work_days = jload(inst["work_days"], ["mon", "tue", "wed", "thu", "fri", "sat"])
    if wd not in work_days:
        errors.append("not_work_day")
    ws, we = _hm(inst["work_start"]), _hm(inst["work_end"])
    s, e = _hm(start), _hm(end)
    if s < ws or e > we:
        errors.append("outside_work_hours")
    b = inst.get("break_start") and inst.get("break_end")
    if b and not errors:
        bs, be = _hm(inst["break_start"]), _hm(inst["break_end"])
        if _overlap(s, e, bs, be):
            errors.append("intersects_break")

    # 5-7. Instruktorning avtomobili
    car = None
    if not inst["assigned_car_id"]:
        errors.append("car_not_assigned")
    else:
        car = db.q1("SELECT * FROM cars WHERE id=? AND deleted_at IS NULL", (inst["assigned_car_id"],))
        if not car:
            errors.append("car_not_found")
        elif car["status"] != "active":
            if car["status"] == "repair":
                errors.append("car_in_repair")
            elif car["status"] == "checkup":
                errors.append("car_in_checkup")
            else:
                errors.append("car_inactive")

    # 4. Instruktor bir vaqtda bandmi?  (reschedule'da o'z sessionini istisno qilamiz)
    inst_exclude = ""
    ex_params = []
    if exclude_session_id:
        inst_exclude = "AND id != ?"
        ex_params.append(exclude_session_id)
    conflict = db.q1(
        f"""SELECT id FROM lesson_sessions
            WHERE instructor_id=? AND status IN ('scheduled','ongoing')
              AND date=? {inst_exclude}
              AND (? < end_time) AND (? > start_time)""",
        (instructor_id, date, *ex_params, start, end),
    )
    if conflict:
        errors.append("instructor_busy")

    # 8. Avtomobil bir vaqtda bandmi (arxitektura xavfsizligi)
    if car and not errors:
        car_conflict = db.q1(
            f"""SELECT id FROM lesson_sessions
                WHERE car_id=? AND status IN ('scheduled','ongoing')
                  AND date=? {inst_exclude}
                  AND (? < end_time) AND (? > start_time)""",
            (car["id"], date, *ex_params, start, end),
        )
        if car_conflict:
            errors.append("car_busy")

    # 9-10. Talabalar tekshiruvi
    student_ids = [int(x) for x in student_ids if str(x).isdigit()]
    if len(set(student_ids)) != len(student_ids):
        errors.append("duplicate_student_in_session")
    if car and not errors:
        capacity = car["practice_capacity"]
        if len(student_ids) > capacity:
            errors.append("capacity_full")

    for sid in student_ids:
        st = db.q1(
            """SELECT s.id FROM students s JOIN users u ON u.id=s.user_id
               WHERE s.id=? AND u.deleted_at IS NULL""",
            (sid,),
        )
        if not st:
            errors.append("student_not_found")
            continue
        # 71. Talaba bir vaqtda boshqa sessionda bo'lmasin
        stud_conf = db.q1(
            f"""SELECT ss.session_id, ls.date, ls.start_time, ls.end_time
                FROM session_students ss
                JOIN lesson_sessions ls ON ls.id=ss.session_id
                WHERE ss.student_id=? AND ss.student_status='active'
                  AND ls.status IN ('scheduled','ongoing') AND ls.date=?
                  AND (? < ls.end_time) AND (? > ls.start_time)
                  AND (? IS NULL OR ls.id != ?)""",
            (sid, date, start, end, exclude_session_id, exclude_session_id),
        )
        if stud_conf:
            errors.append("student_busy")

    return list(dict.fromkeys(errors))


def session_auto_data(db, instructor_id: int):
    """Instruktorning avtomobilini avtomatik aniqlaydi: car_id, nomi, raqami, sig'imi."""
    inst = db.q1("SELECT assigned_car_id FROM instructors WHERE id=?", (instructor_id,))
    if not inst or not inst["assigned_car_id"]:
        return None
    car = db.q1("SELECT * FROM cars WHERE id=? AND deleted_at IS NULL", (inst["assigned_car_id"],))
    if not car:
        return None
    name = car["brand"] + " " + (car["model"] or car["custom_model_name"] or "")
    return {
        "car_id": car["id"],
        "car_name_snapshot": name.strip(),
        "car_plate_snapshot": car["plate_number"],
        "capacity_snapshot": car["practice_capacity"],
    }


def reschedule_is_valid(db, session_id: int, date: str, start: str, end: str, instructor_id: int):
    errors = check_session_rules(
        db, date, start, end, instructor_id,
        [r["student_id"] for r in db.q("SELECT student_id FROM session_students WHERE session_id=? AND student_status='active'", (session_id,))],
        exclude_session_id=session_id,
    )
    return errors