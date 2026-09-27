"""Hisobotlar: kunlik/haftalik/oylik ko'rsatkichlar va eksport qatorlari."""
from datetime import datetime, timedelta

from .db import now, today


def _range(query) -> tuple:
    period = query.get("period", "daily")
    anchor = datetime.now()
    try:
        dt = datetime.strptime(query.get("date") or today(), "%Y-%m-%d")
        anchor = dt
    except Exception:
        pass
    if period == "daily":
        start, end = anchor, anchor + timedelta(days=1)
    elif period == "weekly":
        start = anchor - timedelta(days=anchor.weekday())
        end = start + timedelta(days=7)
    else:  # monthly
        start = anchor.replace(day=1)
        end = (start + timedelta(days=32)).replace(day=1)
    if query.get("from") and query.get("to"):
        try:
            start = datetime.strptime(query["from"], "%Y-%m-%d")
            end = datetime.strptime(query["to"], "%Y-%m-%d") + timedelta(days=1)
        except Exception:
            pass
    return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")


def build_reports(db, query) -> dict:
    s, e = _range(query)
    sessions = db.q(
        """SELECT ls.*, u.first_name||' '||u.last_name AS instructor_name
           FROM lesson_sessions ls JOIN instructors i ON i.id=ls.instructor_id
           JOIN users u ON u.id=i.user_id
           WHERE ls.date>=? AND ls.date<? ORDER BY ls.date""", (s, e))
    total = len(sessions)
    completed = sum(1 for x in sessions if x["status"] == "completed")
    ongoing = sum(1 for x in sessions if x["status"] == "ongoing")
    cancelled = sum(1 for x in sessions if x["status"] == "cancelled")
    scheduled = sum(1 for x in sessions if x["status"] == "scheduled")

    att = db.q(
        """SELECT a.status, COUNT(*) AS c FROM attendance a
           JOIN lesson_sessions ls ON ls.id=a.session_id
           WHERE ls.date>=? AND ls.date<? GROUP BY a.status""", (s, e))
    att_map = {r["status"]: r["c"] for r in att}

    per_instructor = {}
    for x in sessions:
        v = per_instructor.setdefault(x["instructor_name"], {"sessions": 0, "completed": 0, "students": 0})
        v["sessions"] += 1
        v["students"] += x["capacity_snapshot"]
        if x["status"] == "completed":
            v["completed"] += 1

    per_car = {}
    for x in sessions:
        key = f"{x['car_name_snapshot']} ({x['car_plate_snapshot']})"
        v = per_car.setdefault(key, {"sessions": 0})
        v["sessions"] += 1

    student_total = db.q1("SELECT COUNT(*) c FROM students WHERE status='active'")["c"]
    instructor_total = db.q1("SELECT COUNT(*) c FROM instructors WHERE status='active'")["c"]

    return {
        "range": {"from": s, "to": (datetime.strptime(e, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")},
        "metrics": {
            "sessions": total, "scheduled": scheduled, "ongoing": ongoing,
            "completed": completed, "cancelled": cancelled,
            "attendance": att_map,
            "present": att_map.get("present", 0), "late": att_map.get("late", 0),
            "absent": att_map.get("absent", 0),
            "students": student_total, "instructors": instructor_total,
        },
        "per_instructor": sorted(per_instructor.items(), key=lambda kv: -kv[1]["sessions"]),
        "per_car": sorted(per_car.items(), key=lambda kv: -kv[1]["sessions"]),
    }


def export_report_rows(db, query):
    s, e = _range(query)
    report = query.get("report", "sessions")
    if report == "sessions":
        rows = db.q(
            """SELECT ls.date AS Sana, ls.start_time AS Boshlanish, ls.end_time AS Tugash,
                      u.first_name||' '||u.last_name AS Instruktor, ls.car_name_snapshot AS Avtomobil,
                      ls.car_plate_snapshot AS Davlat_raqami,
                      (SELECT COUNT(*) FROM session_students ss WHERE ss.session_id=ls.id AND ss.student_status='active') AS Talabalar,
                      ls.capacity_snapshot AS Sigim, ls.status AS Holat, ls.cancel_reason AS Bekor_sababi
               FROM lesson_sessions ls JOIN instructors i ON i.id=ls.instructor_id
               JOIN users u ON u.id=i.user_id
               WHERE ls.date>=? AND ls.date<? ORDER BY ls.date""", (s, e))
        return rows, "Mashg'ulotlar"
    if report == "attendance":
        rows = db.q(
            """SELECT ls.date AS Sana, ls.start_time AS Vaqt, u.last_name AS Talaba,
                      a.status AS Qatnashish, a.marked_at AS Belgilangan
               FROM attendance a JOIN lesson_sessions ls ON ls.id=a.session_id
               JOIN students st ON st.id=a.student_id JOIN users u ON u.id=st.user_id
               WHERE ls.date>=? AND ls.date<? ORDER BY ls.date""", (s, e))
        return rows, "Davomat"
    if report == "users":
        rows = db.q(
            """SELECT first_name AS Ism, last_name AS Familiya, login AS Login, role AS Rol,
                      status AS Holat, phone AS Telefon, created_at AS Yaratilgan
               FROM users WHERE deleted_at IS NULL ORDER BY id""")
        return rows, "Foydalanuvchilar"
    rows = db.q(
        """SELECT ls.date AS Sana, u.first_name||' '||u.last_name AS Instruktor,
                  ls.car_name_snapshot AS Avtomobil, ls.status AS Holat
           FROM lesson_sessions ls JOIN instructors i ON i.id=ls.instructor_id
           JOIN users u ON u.id=i.user_id
           WHERE ls.date>=? AND ls.date<? ORDER BY ls.date""", (s, e))
    return rows, "Hisobot"