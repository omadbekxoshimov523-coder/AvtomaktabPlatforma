"""Hisobotlar: kunlik/haftalik/oylik ko'rsatkichlar va eksport qatorlari."""
from datetime import datetime, timedelta

from .db import now, today

# ---------------------------------------------------------------------------
# VAZIFA 1 — FOYDALANUVCHI RO'YXATI HISOBOTI (ikki rejim)
#
# `include_credentials=True`  -> FAQAT: Ism, Familiya, Guruh, Login, Parol.
#                                 Boshqa HECH QANDAY ma'lumot (statistika,
#                                 jadval, telefon, holat) QO'SHILMAYDI.
#                                 Bu maxfiy hujjat — alohida, qisqa tarqatish
#                                 uchun mo'ljallangan.
# `include_credentials=False` -> TO'LIQ ma'lumot (ism, rol, guruh, telefon,
#                                 holat, progress, mashg'ulotlar soni, ...),
#                                 LEKIN login/parol ustunlari UMUMAN YO'Q.
#
# Ikkala rejim HECH QACHON aralashmaydi — qat'iy ravishda alohida funksiyalar.
# ---------------------------------------------------------------------------
CRED_COLUMNS = ["Ism", "Familiya", "Guruh", "Kirish", "Parol"]
FULL_COLUMNS = ["Ism", "Familiya", "Rol", "Guruh", "Toifa", "Telefon", "Holat",
                "Tug'ilgan_sana", "Qabul_sanasi", "Otilgan_darslar",
                "Jami_belgilangan", "Qolgan", "Progress", "Oxirgi_kirish", "Izoh"]

DEFAULT_GROUP_TARGET = 30


def _user_rows(db, roles, include_credentials: bool):
    """Tanlangan rollar uchun foydalanuvchi qatorlari.

    `roles` — ["student", ...] ro'yxati. Bo'sh bo'lsa — uchala rol.
    Ikkala rejim uchun umumiy ma'lumot o'qiladi, lekin ustunlar QAT'IY
    ajratiladi: `include_credentials` True bo'lsa — FAQAT CRED_COLUMNS.
    """
    roles = [r for r in (roles or []) if r in ("student", "instructor", "admin")]
    if not roles:
        roles = ["student", "instructor", "admin"]
    ph = ",".join("?" * len(roles))
    where = ("u.deleted_at IS NULL AND u.role IN (%s)" % ph)
    params = list(roles)

    users = db.q(
        """SELECT u.id, u.first_name, u.last_name, u.role, u.phone, u.status,
                  u.birth_date, u.last_login_at, u.login, u.password_hash,
                  u.must_change_password, u.created_at,
                  st.id AS sid, st.group_name, st.license_category, st.enrolled_at,
                  st.notes AS s_notes, st.total_lessons_target, st.study_status
           FROM users u
           LEFT JOIN students st ON st.user_id=u.id
           WHERE %s
           ORDER BY u.role, u.last_name, u.first_name""" % where, params)

    # Bajarilgan mashg'ulotlar soni — BARCHA uchun bir so'rovda (N+1 yo'q)
    done_map = {}
    for p in db.q(
        """SELECT ss.student_id AS sid, COUNT(*) AS n
           FROM session_students ss
           JOIN lesson_sessions ls ON ls.id=ss.session_id
           WHERE ss.student_status='active' AND ls.status='completed'
           GROUP BY ss.student_id"""
    ):
        done_map[p["sid"]] = p["n"] or 0

    rows = []
    for u in users:
        if include_credentials:
            # ---- REJIM A: FAQAT ism/familiya/guruh/kirish/parol ----
            # XOM PAROL tiklanmaydi: platforma parollarni scrypt bilan
            # hash qiladi (`password_hash`), xom qiymat hech qayerda
            # saqlanmaydi. Shu sababli "Parol" ustunida faqat
            # `YANGI_KERAK` belgisi chiqadi — admin "Parolni tiklash"
            # orqali YENGI parol yaratishi mumkin (eski parol o'chadi).
            # Boshqacha qilsak, HECH QANDAY yolg'on ma'lumot ko'rsatilardi.
            rows.append({
                "Ism": u["first_name"] or "",
                "Familiya": u["last_name"] or "",
                "Guruh": u["group_name"] or "",
                "Kirish": u["login"] or "",
                "Parol": "YANGI_KERAK",
            })
            continue

        # ---- REJIM B: TO'LIQ ma'lumot, login/parol YO'Q ----
        done = done_map.get(u["sid"] or 0, 0)
        target = int(u["total_lessons_target"] or 0) or DEFAULT_GROUP_TARGET
        remaining = max(0, target - done)
        rows.append({
            "Ism": u["first_name"] or "",
            "Familiya": u["last_name"] or "",
            "Rol": u["role"] or "",
            "Guruh": u["group_name"] or "",
            "Toifa": u["license_category"] or "",
            "Telefon": u["phone"] or "",
            "Holat": u["status"] or "",
            "Tug'ilgan_sana": u["birth_date"] or "",
            "Qabul_sanasi": u["enrolled_at"] or "",
            "Otilgan_darslar": done,
            "Jami_belgilangan": target,
            "Qolgan": remaining,
            "Progress": (round(done * 100 / target) if target else 0),
            "Oxirgi_kirish": u["last_login_at"] or "",
            "Izoh": (u["s_notes"] or "")[:300],
        })
    return rows


def user_report(db, roles, include_credentials: bool) -> tuple:
    """(qatorlar, sarlavha) — foydalanuvchi ro'yxati hisoboti."""
    rows = _user_rows(db, roles, include_credentials)
    if include_credentials:
        return rows, "Login va parollar"
    parts = {"student": "Talabalar", "instructor": "Instruktorlar", "admin": "Adminlar"}
    names = [parts.get(r, r) for r in (roles or [])]
    return rows, ("Foydalanuvchilar - " + ", ".join(names) if names else "Foydalanuvchilar")


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