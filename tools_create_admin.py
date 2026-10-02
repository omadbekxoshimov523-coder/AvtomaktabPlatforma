"""Bir martalik admin yaratish (CLI).

Ishlatish:
    python tools_create_admin.py

Maqsad: aniq belgilangan login/parol bilan admin hisobi yaratish.
Parol `hash_password()` bilan SHA/scrypt hash'ga aylantiriladi — DB'da
OCHIQ MATN SAQLANMAYDI. Audit jurnaliga `admin_created` yoziladi.

ESLATMA: `LOGIN_RE` (usrL_ + 14-32 belgi) — foydalanuvchi O'ZI tanlagan
loginlar uchun. Admin tomonidan qo'lda belgilangan login bu qoidaga
bog'lanmay (bazadagi `admin` logini ham shunday).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.auth import hash_password, password_strength_errors  # noqa: E402
from app.db import Db, now  # noqa: E402
from app.notify import audit  # noqa: E402

LOGIN = "usrL_admin001"
PASSWORD = "usrP_admin001"
FIRST = "Admin"
LAST = "Admin"
PHONE = ""
EMAIL = ""


def main() -> int:
    root = os.path.dirname(os.path.abspath(__file__))
    db = Db(os.path.join(root, "data", "avtomaktab.db"))

    # 1) Parol siyosati — xavfsizlik uchun majburiy tekshiruv.
    weak = password_strength_errors(PASSWORD)
    if weak:
        print("XATO: parol siyosatiga mos kelmaydi:", weak)
        return 1

    # 2) Login band emasligi (arxivlangan loginlar ham hisobga olinadi).
    if db.q1("SELECT id FROM users WHERE login=?", (LOGIN,)):
        print("XATO: bu login band:", LOGIN)
        return 1

    t = now()
    cur = db.ex(
        """INSERT INTO users(first_name, last_name, middle_name, birth_date, gender,
                             phone, secondary_phone, login, password_hash, role, status,
                             profile_image, must_change_password, created_at, updated_at)
           VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (FIRST, LAST, "", "", "", PHONE, "", LOGIN, hash_password(PASSWORD),
         "admin", "active", "", 0, t, t),
    )
    uid = int(cur)

    audit(db, action_type="admin_created", target_type="users", target_id=uid,
          user_name="Tizim (CLI)",
          description="CLI orqali yangi admin yaratildi: %s (%s)" % (LOGIN, uid))

    print("Admin yaratildi:")
    print("  id       =", uid)
    print("  ism      =", FIRST, LAST)
    print("  login    =", LOGIN)
    print("  parol    =", PASSWORD)
    print("  holat    = active")
    print("  parol DB = hash (ochiq matn emas)")
    print("  audit    = admin_created")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())