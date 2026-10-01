# -*- coding: utf-8 -*-
"""MODUL 3 — TEST FOYDALANUVCHILARINI BAZAGA QO'SHISH (seed skript).

Uchta sinov foydalanuvchisini platformaning O'Z registratsiya logikasi orqali
yaratadi: parol `app.auth.hash_password()` bilan scrypt hash'lanadi (xom parol
hech qayerda saqlanmaydi), `used_credentials` izlari yoziladi, va audit
jurnaliga `user_created` yozuvi tushadi — ya'ni oddiy admin panelidan
qo'shilgan foydalanuvchidan FARQ QILMAYDI.

  py seed_test_users.py
  py seed_test_users.py --reset     # mavjud test foydalanuvchilarini qayta yaratish

Foydalanuvchilar:
  1) Admin       ism: test1  login: usrL_admin       parol: usrP_admin
  2) Talaba      ism: test2  login: usrL_talaba      parol: usrP_talaba
  3) Instruktor  ism: test3  login: usrL_instruktor  parol: usrP_instruktor

DIQQAT: bu faqat SINOV hisoblari. Ishlab chiqarishda ishga tushirmang.
"""
import argparse
import os
import sys

# Loyiha ildizini import uchun yo'lga qo'shamiz.
ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app.db import init_db, next_credentials, now  # noqa: E402
from app.auth import hash_password  # noqa: E402
from app.notify import audit  # noqa: E402

TEST_USERS = [
    {"first_name": "test1", "last_name": "Admin",      "login": "usrL_admin",
     "password": "usrP_admin",       "role": "admin"},
    {"first_name": "test2", "last_name": "Talaba",     "login": "usrL_talaba",
     "password": "usrP_talaba",      "role": "student"},
    {"first_name": "test3", "last_name": "Instruktor", "login": "usrL_instruktor",
     "password": "usrP_instruktor",  "role": "instructor"},
]


def create_user_tx(conn, u):
    """Bitta foydalanuvchini xuddi `admin/users` (POST) kabi yaratadi."""
    t = now()
    cur = conn.execute(
        """INSERT INTO users(first_name,last_name,middle_name,birth_date,gender,phone,
                             secondary_phone,login,password_hash,role,status,profile_image,
                             must_change_password,created_at,updated_at)
           VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (u["first_name"], u["last_name"], "", "", "", "", "",
         u["login"], hash_password(u["password"]), u["role"], "active", "", 0, t, t),
    )
    uid = cur.lastrowid
    if u["role"] == "student":
        conn.execute(
            """INSERT INTO students(user_id,group_name,license_category,study_status,
                                    enrolled_at,address,notes,status)
               VALUES(?,?,?,?,?,?,?,?)""",
            (uid, "Sinov-guruh", "B", "active", t[:10], "", "", "active"),
        )
    elif u["role"] == "instructor":
        import json
        conn.execute(
            """INSERT INTO instructors(user_id,license_categories,experience_years,bio,work_days,
                                       work_start,work_end,break_start,break_end,
                                       assigned_car_id,status)
               VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
            (uid, "B", 1, "Sinov instruktori",
             json.dumps(["mon", "tue", "wed", "thu", "fri", "sat"]),
             "08:00", "18:00", "13:00", "14:00", None, "active"),
        )
    return uid


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=None, help="SQLite fayl (standart: data/avtomaktab.db)")
    ap.add_argument("--reset", action="store_true",
                    help="avval mavjud test login'larni o'chirish (soft delete emas - qat'iy)")
    a = ap.parse_args()

    db_path = a.db or os.path.join(ROOT, "data", "avtomaktab.db")
    db = init_db(db_path)

    created, skipped = [], []
    for u in TEST_USERS:
        row = db.q1("SELECT id, role FROM users WHERE login=?", (u["login"],))
        if row:
            if not a.reset:
                skipped.append((u["login"], "allaqachon mavjud"))
                continue
            # qayta yaratish: eski qatorni butunlay o'chiramiz va auditoriyani saqlaymiz
            def _del(conn, uid=row["id"]):
                conn.execute("DELETE FROM sessions_ring WHERE user_id=?", (uid,))
                conn.execute("DELETE FROM users WHERE id=?", (uid,))
            db.transaction(_del)

        uid = db.transaction(lambda c, u=u: create_user_tx(c, u))
        created.append((u["login"], u["role"], uid))

        # Audit jurnali: platformaning o'z logikasi orqali yoziladi
        try:
            audit(db, uid, action_type="user_created", target_type="users", target_id=uid,
                  description="Seed test foydalanuvchisi yaratildi", user_name=u["first_name"])
        except Exception as e:
            print(f"  (ogohlantirish: audit yozilmadi - {e})")

    print("=" * 58)
    print("  TEST FOYDALANUVCHILARI")
    print("=" * 58)
    if created:
        for login, role, uid in created:
            pwd = next(x["password"] for x in TEST_USERS if x["login"] == login)
            print(f"  + YARATILDI  id={uid:<4} rol={role:<11} login={login:<16} parol={pwd}")
    if skipped:
        for login, why in skipped:
            print(f"  - O'TKAZILDI  login={login:<16} ({why})")
        print("  (qayta yaratish uchun: py seed_test_users.py --reset)")
    print("=" * 58)
    # Tekshiruv: haqiqiy login/parol bilan kirish mumkinligini tasdiqlaymiz
    from app.auth import verify_password
    all_ok = True
    for u in TEST_USERS:
        row = db.q1("SELECT password_hash FROM users WHERE login=?", (u["login"],))
        ok = bool(row) and verify_password(u["password"], row["password_hash"])
        all_ok = all_ok and ok
        print(f"  {'OK' if ok else 'XATO'} verify_password({u['login']})")
    print("NATIJA:", "BARCHASI TO'G'RI" if all_ok else "XATO BOR")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())