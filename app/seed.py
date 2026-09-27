"""Seed: demo ma'lumotlar — admin, instruktorlar + avtomobillar, talabalar, sessiyalar.
Birinchi ishga tushirishda (baza bo'sh bo'lsa) avtomatik yaratiladi.
"""
import json
import os
from datetime import datetime, timedelta

from .auth import hash_password
from .db import now, today, next_credentials
from .notify import audit


class _Conn:
    """connection ob'ektini db wrapper'ga moslashtiradi (audit uchun)."""

    def __init__(self, c):
        self._c = c

    def ex(self, sql, params=()):
        cur = self._c.execute(sql, params)
        return cur.lastrowid


def seed(db_pool) -> None:
    if db_pool.q1("SELECT COUNT(*) c FROM users")["c"] > 0:
        return

    def make_user(c, first, last, role, phone="", extra_student=None, extra_instructor=None):
        login, password = next_credentials(c)
        cur = c.execute(
            """INSERT INTO users(first_name,last_name,login,password_hash,role,status,phone,
                                 must_change_password,created_at,updated_at)
               VALUES(?,?,?,?,?,?,?,?,?,?)""",
            (first, last, login, hash_password(password), role, "active", phone, 0, now(), now()),
        )
        uid = cur.lastrowid
        if extra_student is not None:
            c.execute(
                """INSERT INTO students(user_id, group_name, license_category, study_status, enrolled_at, address, notes, status)
                   VALUES(?,?,?,?,?,?,?,?)""",
                (uid, *extra_student),
            )
        if extra_instructor is not None:
            c.execute(
                """INSERT INTO instructors(user_id, license_categories, experience_years, bio, work_days,
                                           work_start, work_end, break_start, break_end, assigned_car_id, status)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                (uid, *extra_instructor),
            )
        return uid

    def make_car(c, brand, model, plate, capacity, status="active", year=2020, color="Oq", seats=4):
        cur = c.execute(
            """INSERT INTO cars(brand_id, model_id, custom_model_name, brand, model, plate_number, year, color,
                                seat_count, practice_capacity, status, technical_inspection_date,
                                insurance_expiry, notes, created_at, updated_at)
               VALUES(NULL,NULL,'',?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (brand, model, plate, year, color, seats, capacity, status,
             (datetime.now() + timedelta(days=120)).strftime("%Y-%m-%d"),
             (datetime.now() + timedelta(days=300)).strftime("%Y-%m-%d"), "", now(), now()),
        )
        return cur.lastrowid

    def _tx(c):
        # Admin paroli muhitdan (ADMIN_INITIAL_PASSWORD). Bo'sh bo'lsa — demo "admin123".
        # Production'da .env orqali kuchli parol qo'yiladi; qattiq yozilgan maxfiy
        # ma'lumot kod ichida saqlanmaydi.
        admin_pw = os.environ.get("ADMIN_INITIAL_PASSWORD") or "admin123"
        c.execute(
            """INSERT INTO users(first_name,last_name,login,password_hash,role,status,phone,must_change_password,created_at,updated_at)
               VALUES(?,?,?,?,?,?,?,0,?,?)""",
            ("Admin", "Avtomaktab", "admin", hash_password(admin_pw), "admin", "active", "+998 90 000 00 00", now(), now()),
        )
        cobalt = make_car(c, "Chevrolet", "Cobalt", "01 A 123 AA", 4, "active", 2022, "Oq", 4)
        nexia = make_car(c, "Chevrolet", "Nexia", "01 B 456 BB", 4, "active", 2021, "Kumush", 4)
        onix = make_car(c, "Chevrolet", "Onix", "01 C 789 CC", 4, "active", 2023, "Qora", 4)
        lacetti = make_car(c, "Chevrolet", "Lacetti", "01 D 321 DB", 3, "repair", 2019, "Ko'k", 4)
        spark = make_car(c, "Daewoo", "Matiz", "01 E 999 EE", 3, "active", 2018, "Qizil", 4)

        akmal = make_user(c, "Akmal", "Karimov", "instructor", "+998 90 111 22 33",
                          extra_instructor=("B", 8, "15 yillik haydovchi, 8 yil instruktor.",
                                            json.dumps(["mon", "tue", "wed", "thu", "fri", "sat"]),
                                            "08:00", "18:00", "13:00", "14:00", cobalt, "active"))
        jasur = make_user(c, "Jasur", "Aliyev", "instructor", "+998 91 222 33 44",
                          extra_instructor=("B, C", 5, "Yosh va g'ayratli instruktor.",
                                            json.dumps(["mon", "tue", "wed", "thu", "fri"]),
                                            "09:00", "17:00", "13:00", "14:00", nexia, "active"))
        vali_ins = make_user(c, "Vali", "Hasanov", "instructor", "+998 93 333 44 55",
                             extra_instructor=("B", 12, "Tajribali instruktor.",
                                               json.dumps(["mon", "tue", "wed", "thu", "fri", "sat", "sun"]),
                                               "08:00", "20:00", "13:00", "14:00", onix, "active"))

        omad = make_user(c, "Omadbek", "Xoshimov", "student", "+998 94 444 55 66",
                         extra_student=("B-24", "B", "active", now()[:10], "Farg'ona shahar, A.Navoiy 12", "", "active"))
        ali = make_user(c, "Ali", "Valiyev", "student", "+998 95 555 66 77",
                        extra_student=("B-24", "B", "active", now()[:10], "Farg'ona shahar, Mustaqillik 45", "", "active"))
        vali_st = make_user(c, "Vali", "Jalilov", "student", "+998 97 666 77 88",
                            extra_student=("B-24", "B", "active", now()[:10], "Farg'ona shahar, Istiqlol 3", "", "active"))
        hasan = make_user(c, "Hasan", "Rahimov", "student", "+998 99 777 88 99",
                          extra_student=("A-23", "A", "paused", "2023-09-01", "Farg'ona tumani", "", "active"))

        td = today()
        dt = datetime.now()
        tomorrow = (dt + timedelta(days=1)).strftime("%Y-%m-%d")

        def stud_id(uid):
            return c.execute("SELECT id FROM students WHERE user_id=?", (uid,)).fetchone()["id"]

        def inst_id(uid):
            return c.execute("SELECT id FROM instructors WHERE user_id=?", (uid,)).fetchone()["id"]

        akmal_i, jasur_i, vali_i = inst_id(akmal), inst_id(jasur), inst_id(vali_ins)
        omad_s, ali_s, vali_s, hasan_s = stud_id(omad), stud_id(ali), stud_id(vali_st), stud_id(hasan)

        def add_session(date, start, end, inst, car, students):
            cinfo = c.execute("SELECT brand||' '||model AS nm, plate_number AS pl, practice_capacity AS cap FROM cars WHERE id=?", (car,)).fetchone()
            cur = c.execute(
                """INSERT INTO lesson_sessions(date,start_time,end_time,instructor_id,car_id,car_name_snapshot,
                                               car_plate_snapshot,capacity_snapshot,status,notes,created_at,updated_at)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                (date, start, end, inst, car, cinfo["nm"], cinfo["pl"], cinfo["cap"], "scheduled", "", now(), now()),
            )
            sid = cur.lastrowid
            for st in students:
                c.execute(
                    """INSERT INTO session_students(session_id, student_id, pickup_address, attendance_status, student_status, joined_at)
                       VALUES(?,?,?,'unmarked','active',?)""",
                    (sid, st, "", now()),
                )
            return sid

        add_session(td, "15:00", "16:00", akmal_i, cobalt, [omad_s, ali_s, vali_s])
        add_session(td, "17:00", "18:00", jasur_i, nexia, [hasan_s])
        add_session(tomorrow, "10:00", "11:00", vali_i, onix, [omad_s, ali_s])
        add_session(tomorrow, "15:00", "16:00", akmal_i, cobalt, [hasan_s, omad_s])

        c.execute(
            """INSERT INTO practice_requests(student_id, preferred_date, preferred_start_time, preferred_end_time, message, status, created_at)
               VALUES(?,?,?,?,?,'pending',?)""",
            (omad_s, (dt + timedelta(days=2)).strftime("%Y-%m-%d"), "09:00", "10:00", "Ertalabki vaqt mos keladi", now()),
        )

        c.executemany(
            "INSERT OR REPLACE INTO system_settings(key,value,updated_at) VALUES(?,?,?)",
            [
                ("allow_student_requests", json.dumps(True), now()),
            ],
        )
        c.executemany(
            "INSERT OR IGNORE INTO branches(name,address,phone,is_active,created_at,updated_at) VALUES(?,?,?,1,?,?)",
            [("Farg'ona filiali", "Farg'ona shahar, Al-Farg'oniy ko'chasi 10", "+998 73 244 55 66", now(), now()),
             ("Marg'ilon filiali", "Marg'ilon shahar, Boburshoh ko'chasi 22", "+998 73 355 66 77", now(), now())],
        )
        audit(_Conn(c), None, "seed", "system", None, {"note": "demo ma'lumotlar yaratildi"})

    db_pool.transaction(_tx)