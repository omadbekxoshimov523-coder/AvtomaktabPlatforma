"""REST API router — barcha rollar (admin/talaba/instruktor) uchun.
RBAC: har bir endpointda foydalanuvchi roli tekshiriladi.
Barcha biznes qoidalar backendda majburiy bajariladi (app/rules.py).
"""
import base64
import csv
import datetime as _dt
import hashlib
import hmac
import io
import json
import os
import re
import secrets
import struct
import time as _time
import urllib.parse

from .auth import (
    create_session, destroy_session, get_session, get_session_user, hash_password,
    verify_password, new_token, login_allowed, reset_login_attempts,
    ip_blocked, reset_ip_attempts, generate_credentials, generate_password,
    is_valid_login, password_strength_errors, credential_digest,
    encrypt_secret, decrypt_secret, credentials_crypto_available,
)
from .db import init_db, now, today, jload, jdump, next_credentials, Db
from .rules import check_session_rules, session_auto_data, parse_date, validate_time_range
from .notify import (
    notify, notify_session_participants, audit, DEFAULT_NOTIF, DEFAULT_NOTIFICATION_SETTINGS,
    SRC_ADMIN_MESSAGE, SRC_LESSON_REMINDER, SRC_LESSON_ASSIGNED, SRC_LESSON_CANCELLED,
    SRC_LESSON_COMPLETED, SRC_LESSON_RESCHEDULED, SRC_PRACTICE_REQUEST, SRC_MESSAGE,
    SRC_SECURITY, SRC_SYSTEM, SOURCES, clear_lesson_reminders,
    get_settings as notif_get_settings, set_settings as notif_set_settings,
    session_student_user_ids, legacy_flags,
)
from .export import export_table
from . import export as expmod
from .config import public_map_config

DB_PATH = None
DATA_DIR = None
BACKUP_DIR = None

OK = 200
BAD = 400
UNAUTH = 401
FORBIDDEN = 403
NOTFOUND = 404
CONFLICT = 409

MAX_IMG_BYTES = 5 * 1024 * 1024  # ≤5MB (base64 URL qabul qilinadi)
MAX_CAR_PHOTOS = 8               # bitta avtomobil uchun fotosuratlar soni

# Tizimdagi mavjud rollar — login paytida yuborilgan rol shu ro'yxamdandagi
# bo'lishi SHART (MODUL 2). Noma'lum rol ham "wrong_role" bilan rad etiladi.
ROLES = ("admin", "instructor", "student")

# MODUL 4 — kenglik/uzunlik chegaralari (WGS84, Yandex xaritasi uchun).
COORD_RANGE = {"lat": (-90.0, 90.0), "lng": (-180.0, 180.0)}


def parse_coord(value, kind):
    """MODUL 4: kenglik/uzunlikni tekshiradi va `float` ga aylantiradi.

    Qoidalar:
      * `None` / bo'sh satr  -> `None` (koordinata tozalanadi)
      * noto'g'ri son / chegaradan tashqarida -> `ValueError` (400 qaytariladi)
    Noto'g'ri qiymat JIM QOLMAYDI: `coord.bad_lat` / `coord.bad_lng` kodi
    orqali aniq xato qaytariladi.
    """
    if value is None:
        return None
    if isinstance(value, str):
        v = value.strip().replace(",", ".")
        if not v:
            return None
    elif isinstance(value, bool):
        raise ValueError(kind)  # True/False — koordinata emas
    else:
        v = value
    try:
        num = float(v)
    except (TypeError, ValueError):
        raise ValueError(kind)
    if num != num or num in (float("inf"), float("-inf")):  # NaN / Infinity
        raise ValueError(kind)
    lo, hi = COORD_RANGE[kind]
    if not (lo <= num <= hi):
        raise ValueError(kind)
    # 7 ta kasr belgisidan ko'p — ortiqcha aniqlik (baza TEXT da saqlanadi)
    return round(num, 7)


def _week_monday() -> str:
    """Joriy haftaning dushanba sanasi (YYYY-MM-DD). M6: haftalik statistika uchun."""
    from datetime import date, timedelta
    d = date.today()
    return (d - timedelta(days=d.weekday())).isoformat()


def _week_days() -> list:
    """Joriy hafta kunlari: dushanbadan yakshanbagacha ISO sanalar ro'yxati. M8: grafik uchun."""
    from datetime import date, timedelta
    m = date.fromisoformat(_week_monday())
    return [(m + timedelta(days=i)).isoformat() for i in range(7)]


def _dur_hours(start: str, end: str) -> float:
    """'HH:MM' dan 'HH:MM' gacha soat (float). Xato/notartib qiymatda 0."""
    try:
        sh, sm = map(int, str(start).split(":"))
        eh, em = map(int, str(end).split(":"))
        return max((eh * 60 + em) - (sh * 60 + sm), 0) / 60
    except Exception:
        return 0


def _add_minutes(start: str, minutes: int) -> str:
    """'HH:MM' ga daqiqa qo'shish. Xato qiymatda asl start qaytadi."""
    try:
        from datetime import datetime, timedelta
        h, m = map(int, str(start).split(":"))
        base = datetime(2000, 1, 1, h, m) + timedelta(minutes=int(minutes))
        return base.strftime("%H:%M")
    except Exception:
        return str(start)


# M12: platforma darajasidagi sozlamalar default qiymatlari
DEFAULT_PLATFORM_SETTINGS = {
    "allow_student_requests": True,
    "lesson_duration_min": 90,   # mashg'ulot davomiyligi standarti (daqiqa)
    "work_start": "09:00",       # ish vaqti boshlanishi
    "work_end": "18:00",         # ish vaqti tugashi
    "reminder_minutes": 60,      # avtomatik eslatma — necha daqiqa oldin
    # MODUL 5: "Jami darslar" — kurst o'rtasida talaba o'tishi kerak bo'lgan
    # umumiy darslar soni (OMMAVIY rejim). Talabada individual qiymat
    # (students.total_lessons_target) bo'lsa, u shu yerda ustun keladi.
    "total_lessons_target": 30,
}


# ===========================================================================
# XARITA VAQTINCHA O'CHIRILGAN — API kalit va Geosuggest to'liq sozlangandan
# so'ng, qayta yoqish uchun.
#
# NIMA QILINDI:
#   "Olib ketish joyi" -> "Uchrashuv joyi" ga o'zgartirildi va undan
#   XARITA butunlay olib tashlandi. Endi bu — FAQAT oddiy erkin matn maydoni
#   (autocomplete yo'q, koordinata yo'q, xarita yo'q).
#
# NIMA O'ZGARTIRILMADI (MUHIM — kelajak uchun saqlanadi):
#   * `session_students.pickup_lat` / `pickup_lng` USTUNLARI BAZADA O'CHIRILMADI.
#     Ular hozircha NULL (bo'sh) turadi. Xarita qaytganda kerak bo'ladi.
#   * Jadval strukturasi (`app/db.py`) tegilmadi — migration yozilmadi.
#   * Koordinata validatsiyasi (`parse_coord`) o'z holicha turibdi.
#
# QAYTA QO'YISH QANDAY:
#   1) Bu bayroqni `False` qiling.
#   2) `web/js/shared.js` -> `openPickupEdit()` ichidagi `MAP_DISABLED`
#      blokini oching (xarita + autocomplete kodi saqlangan).
#   3) `.env` ga `YANDEX_MAPS_API_KEY` va `YANDEX_GEOCODER_API_KEY` qo'ying.
# ===========================================================================
MAP_DISABLED = True


def _platform_setting(db, key: str, default=None):
    """system_settings'da saqlangan platforma sozlamasini qaytaradi (default bilan)."""
    row = db.q1("SELECT value FROM system_settings WHERE key=?", (key,))
    if row is None:
        return DEFAULT_PLATFORM_SETTINGS.get(key, default)
    val = jload(row["value"], DEFAULT_PLATFORM_SETTINGS.get(key, default))
    return val if val is not None else default


# ---------------------------------------------------------------------------
# BAND 14 — MASHG'ULOTNING ANIQ BIZNES HOLATI
#
# DB'dagi `lesson_sessions.status` (scheduled/ongoing/completed/cancelled)
# saqlanib qoladi. Lekin u Foydalanuvchiga yetarli emas: "scheduled" ham
# kelmagan, ham o'tib ketgan dars uchun bir xil ko'rinardi. Shu sababdan
# biznes holati (`_display_status`) va kelajak/o'tgan ajratmasi (`_is_future`)
# HISOBLANADI va API javobida alohida maydon sifatida qaytariladi.
#
#   PENDING    KUTILMOQDA    — kelmagan, tasdiqlanmagan
#   CONFIRMED  TASDIQLANGAN  — kelmagan, tasdiqlangan
#   ONGOING    JARAYONDA     — ayni damda o'tmoqda
#   COMPLETED  BAJARILGAN    — yakunlangan
#   CANCELLED  BEKOR QILINGAN
#   OVERDUE    O'TIB KETGAN  — vaqt o'tdi, lekin YAKUNLANMADI
#                               (avtomatik "Bajarilgan" BO'LMAYDI!)
#
# So'rovlar uchun alohida holat: `practice_requests.status='rejected'` ->
# RAD ETILGAN.
# ---------------------------------------------------------------------------
def _row_get(row, key, default=None):
    """sqlite3.Row / dict'dan qiymatni xatosiz olish (ustun yo'q bo'lsa default)."""
    try:
        v = row[key]
    except (KeyError, IndexError, TypeError):
        return default
    return default if v is None else v


# --------------------------------------------------------------------------
# MODUL 5 — SO'ROVLAR MUDDATI (eskirgan so'rovlar "Tarix"ga o'tadi)
#
# ANIQ QOIDA (avvalgi "so'rov yaratilgan vaqtdan +1 kun" MEZONI NOTO'G'RI edi):
#
#   Muddat HISOBLANADIGAN narsa — so'rov YARATILGAN VAQT EMAS, balki
#   so'ralgan MASHG'ULOT SANASI (`preferred_date`).
#
#   * Sana KELAJAKDA bo'lsa  -> so'rov QANCHA VAQT o'tishidan qat'i nazar
#                              faol ro'yxatda qoladi (u hali amalga oshirilishi
#                              mumkin), ya'ni "2 hafta keyingi" so'rov kechkirib
#                              yashirilMAYdi.
#   * Sana O'TGAN bo'lsa VA holat hali `pending` (Kutilmoqda) bo'lsa
#                          -> so'rov endi dolzarb emas: sana o'tganidan keyingi
#                             1 KUN o'tgach avtomatik "Eskirgan"ga o'tadi va
#                             asosiy (faol) ro'yxatdan yashiriladi.
#   * Holat `approved/rejected/cancelled` bo'lsa -> "Tarix"ga xos
#                             (bu allaqachon to'g'ri ishlaydi).
#
# Saqlash: `practice_requests.expired_at` (fon vazifa to'ldiradi) — tarixda
# "qachon eskirgani" ko'rinadi. Lekin ro'yxat mantig'i UNIEMAS, so'rov
# yaratilgan/kiritilgan bo'lishidan QAT'I NAZAR `preferred_date` dan hisoblanadi
# (eski yozuvlar ham to'g'ri ishlaydi).
# --------------------------------------------------------------------------
REQUEST_FILTERS = ("active", "expired", "history")


def request_is_expired(row, today_iso: str = None) -> bool:
    """So'rov "eskirgan"mi? (asosiy ro'yxatdan yashirilishi kerakmi)

    Faqat `pending` + `preferred_date` O'TGAN bo'lsa. Kelajakdagi sana
    (bugun yoki keyin) hech qachon eskirgan hisoblanmaydi.
    """
    today_iso = today_iso or today()
    if _row_get(row, "status", "") != "pending":
        return False
    d = str(_row_get(row, "preferred_date", "") or "")[:10]
    if not d:
        return False
    return d < today_iso


def request_bucket(row, today_iso: str = None) -> str:
    """So'rov qaysi bo'limga tegishli: `active` | `expired` | `history`."""
    if _row_get(row, "status", "") == "pending":
        return "expired" if request_is_expired(row, today_iso) else "active"
    return "history"


def decorate_requests(rows, today_iso: str = None):
    """Har bir so'rovga `_bucket` va `is_expired` qo'shib, sanalarni qaytaradi."""
    today_iso = today_iso or today()
    out = []
    for r in rows:
        b = request_bucket(r, today_iso)
        r["_bucket"] = b
        r["is_expired"] = (b == "expired")
        out.append(r)
    return out


def filter_requests(rows, mode: str = "active", today_iso: str = None):
    """`mode` bo'yicha ajratadi. Noma'lum `mode` -> `active`."""
    today_iso = today_iso or today()
    mode = mode if mode in REQUEST_FILTERS else "active"
    out = []
    counts = {"active": 0, "expired": 0, "history": 0}
    for r in rows:
        b = request_bucket(r, today_iso)
        counts[b] += 1
        if b == mode:
            r["_bucket"] = b
            r["is_expired"] = (b == "expired")
            out.append(r)
    return out, counts


def expire_stale_requests(db) -> int:
    """FON VAZIFA: eskirgan `pending` so'rovlarni `expired_at` bilan belgilaydi.

    Ro'yxat mantig'i `preferred_date` dan hisoblanadi (yuqoriga qarang), bu
    funksiya esa faqat "qachon eskirgani" faktini yozib qo'yadi — shu tariqa
    tarixda aniq vaqt ko'rinadi va qayta tiklash oson bo'ladi.

    Qaytaradi: bu safar belgilangan so'rovlar soni.
    """
    today_iso = today()
    rows = db.q(
        "SELECT id, preferred_date FROM practice_requests "
        "WHERE status='pending' AND (expired_at IS NULL OR expired_at='') "
        "AND preferred_date IS NOT NULL AND preferred_date!=''",
    )
    n = 0
    for r in rows:
        d = str(r["preferred_date"] or "")[:10]
        if not d or d >= today_iso:
            continue          # kelajakdagi sana — muddat kelmagan
        db.upd("UPDATE practice_requests SET expired_at=? WHERE id=?", (now(), r["id"]))
        n += 1
    return n


def session_business_status(row, today_iso: str = None, hhmm: str = None):
    """Qatorga `_display_status` va `_is_future` qo'shadi (mutatsiyali)."""
    today_iso = today_iso or today()
    hhmm = hhmm or now()[11:16]
    st = _row_get(row, "status", "")
    date_s = _row_get(row, "date", "")
    end_t = _row_get(row, "end_time", "")
    is_future = bool(date_s) and (date_s > today_iso or (date_s == today_iso and end_t > hhmm))
    row["_is_future"] = is_future
    if st == "completed":
        disp = "completed"
    elif st == "cancelled":
        disp = "cancelled"
    elif st == "ongoing":
        disp = "ongoing"
    elif is_future:
        # KELMAGAN: "Kutilmoqda" faqat shu yerda ishlatiladi.
        disp = "confirmed" if _row_get(row, "confirm_state", "pending") == "confirmed" else "pending"
    else:
        # O'tib ketgan, lekin yakunlanmagan — BAJARILGAN emas.
        disp = "overdue"
    row["_display_status"] = disp
    return disp


def session_start_dt(date_str: str, time_str: str):
    """'YYYY-MM-DD' + 'HH:MM' -> datetime (xato qiymatda None)."""
    try:
        sh, sm = map(int, str(time_str).split(":"))
        y, mo, d = map(int, str(date_str).split("-"))
        return _dt.datetime(y, mo, d, sh, sm)
    except Exception:
        return None


# BAND 9 — 2 soat oldin eslatma. Doimiy qiymat platforma sozlamasidan
# olinmaydi: talab aniq "2 SOAT" deb belgilagan.
REMINDER_LEAD_MINUTES = 120


def ensure_reminders(db) -> int:
    """Mashg'ulot boshlanishidan 2 SOAT oldin talab va instruktorga
    eslatma yuboradi (BAND 9). Qaytaradi: yuborilgan bildirishnomalar soni.

    QOIDALAR (barchasi majburiy):
      * FAQAT BIR MARTA — `ux_notif_reminder_once` UNIQUE indeksi
        (user_id + related_lesson_id) kafolatlaydi. Parallel jarayonlar
        ishlatsa ham, ikkinchi urinish `IntegrityError` beradi va o'tkazib
        yuboriladi.
      * VAQT O'ZGARSA — eslatma QAYTA HISOBLANADI: `admin_session_reschedule`
        eslatmani o'chiradi (`clear_lesson_reminders`), shunda yangi vaqt
        uchun yangi eslatma yuborilishi mumkin bo'ladi. Eski (noto'g'ri)
        eslatma esa qolmaydi.
      * BEKOR QILINGAN mashg'ulotga — hech qachon eslatma yuborilmaydi
        (status='cancelled' filtrlanadi) va eslatmasi o'chiriladi.
      * 2 SOATDAN KAM VAQT ichida yaratilgan mashg'ulotga — eslatma
        YUBORILMAYDI: eslatma vaqti (T-2h) allaqachon o'tgan bo'lgani uchun
        shart bajarilmaydi (`created_at > T-2h`). Shunday qilib "2 soatdan
        kam vaqt ichida yaratilgan mashg'ulotda duplicate yoki noto'g'ri
        bildirishnoma" chiqmaydi.
      * Foydalanuvchi Sozlamalar → "Mashg'ulot eslatmalari" ni O'CHIRGAN
        bo'lsa — unga eslatma yuborilmaydi.
    """
    now_dt = _dt.datetime.now().replace(second=0, microsecond=0)
    lead = _dt.timedelta(minutes=REMINDER_LEAD_MINUTES)
    # Barcha yaqin kelajakdagi mashg'ulotlar: bugundan keyingi 2 kun.
    day_after = (_dt.date.today() + _dt.timedelta(days=2)).strftime("%Y-%m-%d")
    rows = db.q(
        """SELECT ls.id, ls.date, ls.start_time, ls.end_time, ls.instructor_id, ls.created_at,
                  i.user_id AS instructor_uid
           FROM lesson_sessions ls
           JOIN instructors i ON i.id = ls.instructor_id
           WHERE ls.status IN ('scheduled','ongoing') AND ls.date <= ?""",
        (day_after,),
    )
    sent_n = 0
    for r in rows:
        start = session_start_dt(r["date"], r["start_time"])
        if start is None:
            continue
        remind_at = start - lead
        # (a) Hali eslatma vaqti kelmagan
        if now_dt < remind_at:
            continue
        # (b) Mashg'ulot allaqachon boshlangan/b tugagan
        if now_dt >= start:
            continue
        # (c) Eslatma vaqti mashg'ulot YARATILGANDAN keyin o'tgan bo'lsa
        #     (mashg'ulot 2 soatdan kam vaqt ichida yaratilgan) — yubormaymiz.
        created = session_start_dt(str(r["created_at"])[:10], str(r["created_at"])[11:16])
        if created is not None and created > remind_at:
            continue
        # (d) Boshqa kunka ko'chirilgan (eski eslatma qolgan bo'lishi mumkin)
        if now_dt >= remind_at + lead:
            continue

        st = db.q1(
            """SELECT ss.pickup_address FROM session_students ss
               WHERE ss.session_id=? AND ss.student_status='active' LIMIT 1""",
            (r["id"],),
        )
        meta = {
            "session_id": r["id"], "verb": "reminder",
            "date": r["date"], "start_time": r["start_time"], "end_time": r["end_time"],
            "pickup_address": (st["pickup_address"] if st else "") or "",
        }
        recipients = [(r["instructor_uid"], r["instructor_id"])]
        for u in db.q(
            """SELECT u.id AS uid FROM session_students ss
               JOIN students s ON s.id=ss.student_id JOIN users u ON u.id=s.user_id
               WHERE ss.session_id=? AND ss.student_status='active'""", (r["id"],),
        ):
            recipients.append((u["uid"], None))
        for uid, _iid in recipients:
            sent_n += lesson_reminder(
                db, r["id"], uid, r["date"], r["start_time"], r["end_time"], meta)
    return sent_n


def lesson_reminder(db, lesson_id: int, user_id: int, date: str, start_time: str,
                    end_time: str, meta: dict = None) -> int:
    """Bitta qabulchiga 2-soat eslatmasini yuboradi. 1 = yuborildi, 0 = yo'q.

    Matn talabdagidek: sana, vaqt, instruktor, uchrashuv joyi.
    """
    from .notify import SRC_LESSON_REMINDER, notify as _notify
    info = db.q1(
        """SELECT u.first_name||' '||u.last_name AS name
           FROM lesson_sessions ls JOIN instructors i ON i.id=ls.instructor_id
           JOIN users u ON u.id=i.user_id WHERE ls.id=?""", (lesson_id,),
    )
    m = dict(meta or {})
    m.setdefault("session_id", lesson_id)
    m["date"] = date
    m["start_time"] = start_time
    m["end_time"] = end_time
    m["instructor_name"] = (info["name"] if info else "") or m.get("instructor_name", "")
    try:
        nid = _notify(
            db, user_id, "lesson.reminder_2h", f"{date} {start_time}-{end_time}",
            "reminder", m, None, "", source=SRC_LESSON_REMINDER, related_lesson_id=lesson_id,
        )
    except ValueError:
        return 0
    return 1 if nid else 0



# ---------------------------------------------------------------------------
# MODUL 1 — ZAXIRA NUSXA YORDAMCHILARI
#
# `BACKUP_RETENTION_DAYS` kunidan ortiq yotayotgan `.db` nusxalari avtomatik
# o'chiriladi (joy tejash). Barcha nusxalar BIZ yaratgan nom bilan
# (`db_*.db`) — qo'lda qo'yilgan boshqa fayllar tegilmaydi.
# ---------------------------------------------------------------------------
BACKUP_RETENTION_DAYS = 30


def _retention_days() -> int:
    try:
        v = int(os.environ.get("BACKUP_RETENTION_DAYS") or BACKUP_RETENTION_DAYS)
        return v if v > 0 else BACKUP_RETENTION_DAYS
    except (TypeError, ValueError):
        return BACKUP_RETENTION_DAYS


def cleanup_old_backups(directory, retention_days=None) -> list:
    """`retention_days`dan eski nusxalarni o'chiradi, o'chirilgan nomlar ro'yxati."""
    days = retention_days if retention_days is not None else _retention_days()
    if not directory or not os.path.isdir(directory):
        return []
    cutoff = _time.time() - days * 86400
    removed = []
    for f in sorted(os.listdir(directory)):
        if not f.startswith("db_") or not f.endswith(".db"):
            continue
        fp = os.path.join(directory, f)
        try:
            if os.path.isfile(fp) and os.path.getmtime(fp) < cutoff:
                os.remove(fp)
                removed.append(f)
        except OSError:
            continue
    return removed


def make_backup(db_path, directory) -> dict:
    """VACUUM INTO bilan xavfsiz (WAL-safe) nusxa oladi.

    Server ISHLAB turib ham bajariladi — `VACUUM INTO` yaxlit (consistent)
    snapshot beradi. Natija: {file, name, path, size, created_at}
    """
    os.makedirs(directory, exist_ok=True)
    name = "db_" + now().replace("-", "").replace(":", "").replace(" ", "_") + ".db"
    path = os.path.join(directory, name)
    try:
        import sqlite3 as _sq
        con = _sq.connect(db_path)
        try:
            con.execute("VACUUM INTO ?", (path,))
        finally:
            con.close()
    except Exception:
        import shutil
        shutil.copy2(db_path, path)
    return {"file": name, "name": name, "path": path,
            "size": os.path.getsize(path), "created_at": now()}


# ---------------------------------------------------------------------------
# MODUL 1 — audit yordamchilari: foydalanuvchi ismi va roli.
# `audit_log.user_name` vaqt chegarasidagi ismni saqlaydi (jurnal keyinchalik
# o'zgarmasligi kerak), shuning uchun u har bir yozuvda alohida yoziladi.
# ---------------------------------------------------------------------------
_ROLE_UZ = {"admin": "Admin", "instructor": "Instruktor", "student": "Talaba"}


def user_name(u) -> str:
    if not u:
        return ""
    if isinstance(u, str):
        return u
    return ("%s %s" % (u.get("first_name") or "", u.get("last_name") or "")).strip()


def role_name(role) -> str:
    return _ROLE_UZ.get(str(role or ""), str(role or ""))


# ======================================================================
# MODUL 5 — PAROLNING QAYTARIB OCHILADIGAN NUSXASI
#
# `password_hash` (scrypt) — ASOSIY saqlash. O'zgartirilmaydi.
# `password_enc`  (AES-256-GCM) — admin parolni ko'ra olishi uchun.
#
# `encrypt_par()` HECH QACHON xato OTARMAYDI: kalit yoki `cryptography`
# yo'q bo'lsa bo'sh satr qaytaradi va platforma odatdagidek ishlayveradi
# (faqat "parolni ko'rsatish" 503 qaytaradi). Parol o'zi hech qachon
# qaytarib yozilmaydi — xato bo'lsa ham `password_hash` to'g'ri saqlanadi.
# ======================================================================
def encrypt_par(password: str) -> str:
    try:
        return encrypt_secret(password)
    except Exception:
        return ""


def upload_dir(*parts: str) -> str:
    """web/uploads/<...> papkasi (loyiha ildiziga nisbatan)."""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    d = os.path.join(root, "web", "uploads", *parts)
    os.makedirs(d, exist_ok=True)
    return d


def save_data_url_image(data_url: str, folder: str, prefix: str) -> "tuple[str, str] | None":
    """`data:image/...;base64,` URL-ni saqlaydi.
    Qaytaradi: (path, ext). Xato bo'lsa: None (xato kodi img.format/img.size).
    Noto'g'ri kirishda/cheklovda ValueError ko'taradi — chaqiruvchi err() ga aylantiradi."""
    m = re.match(r"^data:image/(png|jpe?g|webp);base64,", data_url)
    if not m:
        raise ValueError("img.format")
    ext = {"png": "png", "jpeg": "jpg", "jpg": "jpg", "webp": "webp"}[m.group(1)]
    try:
        raw = base64.b64decode(data_url.split(",", 1)[1])
    except Exception:
        raise ValueError("img.format")
    if len(raw) < 50:
        raise ValueError("img.format")
    if len(raw) > MAX_IMG_BYTES:
        raise ValueError("img.size")
    d = upload_dir(folder)
    name = "%s%d.%s" % (prefix, _time.time_ns(), ext)
    with open(os.path.join(d, name), "wb") as f:
        f.write(raw)
    return "/uploads/%s/%s" % (folder, name), os.path.join(d, name)


class Api:
    # `tab` — so'rov sarlavhasidagi tab kaliti (None = eski rejim: faqat cookie).
    # Foydalanuvchi har bir so'rovda FAQAT shu so'rov keltirgan kalit orqali
    # aniqlanadi; modul darajasida hech qanday foydalanuvchi holati saqlanmaydi.
    def __init__(self, db: Db, token: str, tab: str = None):
        self.db = db
        self.token = token
        self.tab = tab or None
        self.user = get_session_user(db, token, self.tab) if token else None
        # BAND 6: sessiya qatori (CSRF token'i shu yerda). `sid` cookie'si
        # HttpOnly bo'lgani uchun JS uni ko'ra olmaydi — CSRF token'i alohida
        # sarlavha orqali yuboriladi va shu sessiyaga bog'liq.
        self.session = get_session(db, token, self.tab) if (token and self.user) else None

    # ------------------------------------------------------------------ auth
    def auth_login(self, body, client_ip: str = ""):
        login = str(body.get("login", "")).strip()
        password = str(body.get("password", ""))
        role = str(body.get("role", "")).strip()
        remember = bool(body.get("remember"))
        # BAND 6: IP bo'yicha vaqtinchalik blok. 1) bloklangan IP
        # 2) bitta login'ga juda ko'p urinish — ikkalasi ham rad etiladi.
        wait = ip_blocked(client_ip)
        if wait:
            return BAD, err("auth.ip_blocked", {"seconds": wait})
        if not login or not password:
            return BAD, err("auth.missing_fields")
        if not login_allowed("login:" + login):
            return BAD, err("auth.too_many_attempts")
        u = self.db.q1("SELECT * FROM users WHERE login=? AND deleted_at IS NULL", (login,))
        if not u or not verify_password(password, u["password_hash"]):
            return BAD, err("auth.wrong_credentials")
        if u["status"] != "active":
            return BAD, err("auth.user_blocked")
        # MODUL 2: rol MAJBURIY va foydalanuvchining haqiqiy roliga mos kelishi shart.
        # Eski kod `if role and ...` edi — rol yuborilmasa umuman tekshirilmasdi,
        # ya'ni tizim roli "avtomatik" deb qabul qilib kirishga ruxsat berardi.
        # Endi rol yo'q/noto'g'ri/xato bo'lsa — kirish RAD etiladi.
        # Xavfsizlik uchun xabar umumiy ("login yoki parol noto'g'ri"): foydalanuvchi
        # haqiqiy roli oshkor qilinmaydi.
        if role not in ROLES or u["role"] != role:
            return BAD, err("auth.wrong_role")
        if u.get("totp_enabled"):
            otp = str(body.get("otp", "")).strip()
            if not otp:
                # 2FA talab qilinsa — SMS kodni yuboramiz (simulyatsiya)
                self._twofa_send_code(u)
                return BAD, err("auth.otp_required")
            if not self._check_twofa_code(u, otp):
                return BAD, err("auth.otp_invalid")
        reset_login_attempts("login:" + login)
        reset_ip_attempts(client_ip)   # muvaffaqiyatli kirish — IP blokini bo'shatadi
        # Tab'ga xos rejim: cookie'ga qurilma kaliti yoziladi (HttpOnly), sessiya
        # esa shu qurilma + shu tab birligidan yaratiladi. Shunda boshqa tab'
        # kirganda bu tab'ning sessiyasi buzilmaydi.
        token = create_session(self.db, u["id"], remember, tab=self.tab, device=self.token or None)
        if self.tab and self.token:
            # Eski rejimda yaratilgan sessiya qoldig'ini tozalaymiz
            # (cookie qiymati endi qurilma kaliti sifatida ishlatiladi).
            destroy_session(self.db, self.token)
        self.db.upd("UPDATE users SET last_login_at=? WHERE id=?", (now(), u["id"]))
        # MODUL 1: har bir rol (admin / instruktor / talaba) kirishi JURNALGA
        # yoziladi. Parol yozilmaydi - faqat "kim, qachon, qayerdan" fakt.
        audit(self.db, u["id"], action_type="login", target_type="users",
              target_id=u["id"], user_name=user_name(u),
              description="%s tizimga kirdi" % role_name(u["role"]),
              ip_address=client_ip)
        sess = get_session(self.db, token, self.tab)
        return OK, {"ok": True, "token": token, "user": user_public(u),
                    "csrf": (sess or {}).get("csrf_token", "")}


    def auth_logout(self):
        if self.user:
            audit(self.db, self.user["id"], action_type="logout", target_type="users",
                  target_id=self.user["id"], user_name=user_name(self.user),
                  description="Tizimdan chiqdi")
        destroy_session(self.db, self.token, self.tab)
        return OK, {"ok": True}

    def auth_change_password(self, body):
        """Parol va/yoki loginni o'zgartirish — YAGONA xavfsiz oqim (MODUL 4).

        Bitta formada:
          * `old_password`     — joriy parol (tasdiqlash uchun) MAJBURIY,
          * `new_login`        — ixtiyoriy yangi login,
          * `new_password`     — ixtiyoriy yangi parol,
          * `confirm_password` — yangi parolni takrorlash (mosligi tekshiriladi).

        Kamida bittasi (login yoki parol) o'zgarishi shart. Yangi parol kuch
        talablariga javob berishi shart — bu yerda, backendda QAYTA tekshiriladi
        (frontend tekshiruviga ishonilmaydi). Yangi login `usrL_` formatida va
        UNIKAL bo'lishi kerak. Muvaffaqiyatdan so'ng boshqa qurilmalardagi
        sessiyalar bekor qilinadi (joriy sessiya qoladi). Auditga parolning
        O'ZI emas, faqat o'zgargan FAKT yoziladi.
        """
        if not self.user:
            return UNAUTH, err("auth.required")
        old = str(body.get("old_password", ""))
        new = str(body.get("new_password", ""))
        confirm = body.get("confirm_password")
        new_login = body.get("new_login")
        new_login = str(new_login).strip() if new_login is not None else ""

        changing_pw = bool(new)
        changing_login = bool(new_login) and new_login != self.user["login"]
        if not changing_pw and not changing_login:
            return BAD, err("auth.nothing_to_change")

        # MODUL 4: JORIY PAROL HAR DOIM MAJBURIY. Bu — login va parol
        # o'zgartirish uchun YAGONA xavfsiz oqim; uni tasdiqlamay o'tish
        # mumkin emas (hatto `must_change_password=1` holatida ham: foydalanuvchi
        # vaqtinchalik parolni admin'dan olgan, demak uni biladi).
        if not verify_password(old, self.user["password_hash"]):
            return BAD, err("auth.wrong_old_password")

        if changing_pw and confirm is not None and str(confirm) != new:
            return BAD, err("auth.password_mismatch")

        sets = []
        params = []
        changed = []
        if changing_pw:
            strength = password_strength_errors(new)
            if strength:
                return BAD, err("auth.password_weak", {"errors": strength})
            if new == old:
                return BAD, err("auth.password_same")
            pd = credential_digest(new)
            if self.db.q1("SELECT 1 FROM used_credentials WHERE password_digest=?", (pd,)):
                return BAD, err("auth.password_used")
            sets += ["password_hash=?", "password_enc=?", "must_change_password=0"]
            params.append(hash_password(new))
            params.append(encrypt_par(new))
            changed.append("password_changed")
        if changing_login:
            if not is_valid_login(new_login):
                return BAD, err("profile.login_format")
            # `deleted_at` filtrisiz: arxivlangan login ham qayta ishlatilmasin.
            if self.db.q1("SELECT id FROM users WHERE login=? AND id!=?",
                          (new_login, self.user["id"])):
                return BAD, err("profile.login_taken")
            sets.append("login=?")
            params.append(new_login)
            changed.append("login_changed")

        sets.append("updated_at=?")
        params.append(now())
        params.append(self.user["id"])

        def _apply(c):
            if changing_pw:
                # Ishlatilgan parollar ro'yxatiga qo'shamiz (qayta ishlatilmasin).
                c.execute(
                    "INSERT INTO used_credentials(login_digest, password_digest, created_at)"
                    " VALUES(?,?,?)",
                    (credential_digest("manual:" + str(self.user["id"]) + ":" + new),
                     credential_digest(new), now()),
                )
            c.execute("UPDATE users SET " + ", ".join(sets) + " WHERE id=?", params)

        self.db.transaction(_apply)
        # Xavfsizlik: parol yoki login o'zgarganda boshqa qurilmalardagi
        # sessiyalar bekor qilinadi (faqat joriy sessiya qoladi).
        self.db.upd(
            "DELETE FROM sessions_ring WHERE user_id=? AND token_hash!=?",
            (self.user["id"], (self.session or {}).get("token_hash") or ""),
        )
        for act in changed:
            audit(self.db, self.user["id"], action_type=act, target_type="users",
                  target_id=self.user["id"], user_name=user_name(self.user),
                  description=("Parol o'zgartirildi" if act == "password_changed"
                               else "Login o'zgartirildi"))
        return OK, {"ok": True, "password_changed": changing_pw,
                    "login_changed": changing_login,
                    "login": new_login if changing_login else self.user["login"]}

    def auth_request_reset(self, body):
        login = str(body.get("login", "")).strip()
        u = self.db.q1("SELECT * FROM users WHERE login=? AND deleted_at IS NULL", (login,))
        if not u:
            # man-in-the-middle ma'lumot sizdirilmasin
            return OK, {"ok": True, "note": "if exists, token created"}
        token = new_token()
        from datetime import datetime, timedelta
        self.db.ex(
            "INSERT INTO password_reset_tokens(user_id, token_hash, expires_at, created_at) VALUES(?,?,?,?)",
            (u["id"], hash_password(token), (datetime.now() + timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S"), now()),
        )
        notify(self.db, u["id"], "auth.reset_token", token, "security", {"token": token})
        return OK, {"ok": True, "token": token} if u["role"] == "admin" else {"ok": True}

    def auth_reset_password(self, body):
        token = str(body.get("token", ""))
        newpass = str(body.get("new_password", ""))
        row = self.db.q1("SELECT * FROM password_reset_tokens WHERE token_hash=?", (hash_password(token),))
        if not row or row["used_at"] or row["expires_at"] < now():
            return BAD, err("auth.invalid_token")
        strength = password_strength_errors(newpass)
        if strength:
            return BAD, err("auth.password_weak", {"errors": strength})
        pd = credential_digest(newpass)
        if self.db.q1("SELECT 1 FROM used_credentials WHERE password_digest=?", (pd,)):
            return BAD, err("auth.password_used")
        self.db.upd("UPDATE users SET password_hash=?, password_enc=?, must_change_password=0, updated_at=? WHERE id=?", (hash_password(newpass), encrypt_par(newpass), now(), row["user_id"]))
        self.db.upd("UPDATE password_reset_tokens SET used_at=? WHERE id=?", (now(), row["id"]))
        # Parol tiklangan — barcha sessiyalar bekor qilinadi.
        self.db.upd("DELETE FROM sessions_ring WHERE user_id=?", (row["user_id"],))
        return OK, {"ok": True}

    # ------------------------------------------------------------ me (barcha)
    def me(self):
        if not self.user:
            return UNAUTH, err("auth.required")
        u = user_public(self.user)
        # BAND 16: "Ro'yxatga olingan sana" talaba/instruktorga KO'RSATILMAYDI.
        # Ma'lumot DB'da saqlanib qoladi; faqat admin ko'ra oladi.
        u.pop("created_at", None)
        extra = {"unread": self.db.q1("SELECT COUNT(*) c FROM notifications WHERE user_id=? AND is_read=0", (self.user["id"],))["c"]}
        if u["role"] == "student":
            st = self.db.q1("SELECT * FROM students WHERE user_id=?", (self.user["id"],))
            if st:
                extra["student"] = student_private(st)
        elif u["role"] == "instructor":
            inst = self.db.q1("SELECT * FROM instructors WHERE user_id=?", (self.user["id"],))
            if inst:
                inst = dict(inst)
                inst.pop("created_at", None)
                extra["instructor"] = inst
                car = self.db.q1("SELECT * FROM cars WHERE id=?", (inst["assigned_car_id"],)) if inst["assigned_car_id"] else None
                if car:
                    extra["car"] = car
        return OK, {"ok": True, "user": u,
                    # BAND 6: CSRF token frontend'ga shu javob orqali beriladi
                    # (sid cookie'si HttpOnly — JS uni o'zi olmaydi).
                    "csrf": (self.session or {}).get("csrf_token") or "",
                    **extra}

    # ---- bildirishnomalar (BAND 8/11/12) ----
    NOTIF_CATEGORIES = {
        # kategoriya -> SQL sharti. "Xabarlar" = FAQAT haqiqiy admin xabarlari.
        "all": None,
        "lesson": ("(n.source IN (?,?,?,?) OR n.type IN ('lesson','cancel'))",),
        "message": None,   # quyida maxsus shart bilan
        "reminder": None,  # quyida maxsus shart bilan
    }

    def me_notifications(self, query=None):
        """`GET /me/notifications[?category=]`

        Har bir qator — MUSTAQIL DB record. Har biri o'z `id`, `source`,
        `title`, `body`, `related_lesson_id`, `created_by` qiymatiga ega:
        biri boshqasining matnini ko'chira olmaydi (BAND 11).
        """
        if not self.user:
            return UNAUTH, err("auth.required")
        cat = str((query or {}).get("category", "all")).strip() or "all"
        params = [self.user["id"]]
        where = "n.user_id=?"
        if cat == "lesson":
            where += (" AND (n.source IN (?,?,?,?) OR n.type IN ('lesson','cancel'))")
            params += [SRC_LESSON_ASSIGNED, SRC_LESSON_RESCHEDULED,
                       SRC_LESSON_CANCELLED, SRC_LESSON_COMPLETED]
        elif cat == "message":
            # BAND 12: faqat ADMIN yuborgan xabarlar. Avtomatik system
            # bildirishnomalari (LESSON_REMINDER va h.k.) bu yerda CHIQMAYDI.
            where += " AND n.source=?"
            params.append(SRC_ADMIN_MESSAGE)
        elif cat == "reminder":
            where += " AND n.source=?"
            params.append(SRC_LESSON_REMINDER)
        elif cat != "all":
            return BAD, err("bad_request")
        rows = self.db.q(
            """SELECT n.*, su.first_name AS sender_first_name, su.last_name AS sender_last_name,
                      su.profile_image AS sender_profile_image
               FROM notifications n LEFT JOIN users su ON su.id=n.sender_id
               WHERE %s ORDER BY n.id DESC LIMIT 200""" % where, params
        )
        for r in rows:
            # `data` — JSON matn (frontend `JSON.parse` qiladi, moslik saqlanadi),
            # `metadata` — tayyor ob'ekt (BAND 18: metadata maydoni).
            r["metadata"] = jload(r.get("data"), {})
        return OK, {"ok": True, "notifications": rows,
                    "categories": ["all", "lesson", "message", "reminder"]}

    def me_notification_detail(self, nid):
        """`GET /me/notifications/{id}` — aynan O'SHA id bo'yicha bitta record.

        BAND 6 (IDOR): `user_id` sharti bilan filtrlanadi — boshqa
        foydalanuvchining bildirishnoma id'sini URL'ga qo'yib ko'rib
        bo'lmaydi (boshqa id kiritilsa 404 qaytariladi).
        """
        if not self.user:
            return UNAUTH, err("auth.required")
        try:
            nid = int(nid)
        except (TypeError, ValueError):
            return BAD, err("invalid_input")
        row = self.db.q1(
            """SELECT n.*, su.first_name AS sender_first_name, su.last_name AS sender_last_name,
                      su.profile_image AS sender_profile_image
               FROM notifications n LEFT JOIN users su ON su.id=n.sender_id
               WHERE n.id=? AND n.user_id=?""", (nid, self.user["id"]),
        )
        if not row:
            return NOTFOUND, err("not_found")
        row["metadata"] = jload(row.get("data"), {})
        if not row["is_read"]:
            self.db.upd("UPDATE notifications SET is_read=1, read_at=? WHERE id=? AND user_id=?",
                        (now(), nid, self.user["id"]))
            row["is_read"] = 1
        return OK, {"ok": True, "notification": row}


    def me_notifications_read(self, body):
        if not self.user:
            return UNAUTH, err("auth.required")
        nid = body.get("id")
        if nid:
            self.db.upd("UPDATE notifications SET is_read=1, read_at=? WHERE id=? AND user_id=?", (now(), nid, self.user["id"]))
        else:
            self.db.upd("UPDATE notifications SET is_read=1, read_at=? WHERE user_id=? AND is_read=0", (now(), self.user["id"]))
        cnt = self.db.q1("SELECT COUNT(*) c FROM notifications WHERE user_id=? AND is_read=0", (self.user["id"],))["c"]
        return OK, {"ok": True, "unread": cnt}

    def me_notifications_delete(self, body):
        """Bitta bildirishnomani o'chirish (faqat o'zining)."""
        if not self.user:
            return UNAUTH, err("auth.required")
        nid = body.get("id")
        if not nid:
            return BAD, err("invalid_input")
        self.db.upd("DELETE FROM notifications WHERE id=? AND user_id=?", (nid, self.user["id"]))
        cnt = self.db.q1("SELECT COUNT(*) c FROM notifications WHERE user_id=? AND is_read=0", (self.user["id"],))["c"]
        return OK, {"ok": True, "unread": cnt}

    def me_notifications_clear(self):
        """Foydalanuvchining barcha bildirishnomalarini tozalash."""
        if not self.user:
            return UNAUTH, err("auth.required")
        self.db.upd("DELETE FROM notifications WHERE user_id=?", (self.user["id"],))
        return OK, {"ok": True, "unread": 0}

    # ---- BAND 17: shaxsiy sozlamalar (til / tema / bildirishnoma) ----

    def me_settings_get(self):
        if not self.user:
            return UNAUTH, err("auth.required")
        rows = self.db.q("SELECT key, value FROM user_settings WHERE user_id=?", (self.user["id"],))
        s = {r["key"]: jload(r["value"], {}) for r in rows}
        notif = notif_get_settings(self.db, self.user["id"])
        return OK, {"ok": True, "settings": {
            "lang": s.get("lang", ""),
            "theme": s.get("theme", ""),
            # Eski shakl saqlanadi (`notif`: kategoriya -> bool)
            "notif": {**DEFAULT_NOTIF, **legacy_flags(self.db, self.user["id"])},
            # Yangi aniq shakl (BAND 17): har bir sozlama alohida ustun
            "notification_settings": notif,
        }}

    def me_settings_put(self, body):
        if not self.user:
            return UNAUTH, err("auth.required")
        uid = self.user["id"]
        t = now()

        def _upsert(key_f, value):
            self.db.ex(
                "INSERT INTO user_settings(user_id,key,value,updated_at) VALUES(?,?,?,?) "
                "ON CONFLICT(user_id,key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
                (uid, key_f, jdump(value), t))

        if "lang" in body:
            lang = str(body["lang"]).strip()
            if lang in ("uz", "ru", "en"):
                _upsert("lang", lang)
        if "theme" in body:
            theme = str(body["theme"]).strip()
            if theme in ("light", "dark", "system"):
                _upsert("theme", theme)
        # BAND 17: bildirishnoma sozlamalari — DB ga saqlanadi va
        # `notify()` shu qiymatlarni tekshiradi. Toggle faqat dizayn EMAS.
        payload = None
        if isinstance(body.get("notification_settings"), dict):
            payload = body["notification_settings"]
        elif isinstance(body.get("notif"), dict):
            # Eski frontend shakli: kategoriya -> bool
            legacy = body["notif"]
            cur = notif_get_settings(self.db, uid)
            for col, key in (("lesson_reminders", "reminder"), ("lesson_status_updates", "lesson"),
                             ("admin_messages", "admin"), ("messages", "message"),
                             ("requests", "request"), ("security", "security")):
                if key in legacy:
                    cur[col] = bool(legacy[key])
            payload = cur
        if payload is not None:
            notif_set_settings(self.db, uid, payload)
        return OK, {"ok": True, "notification_settings": notif_get_settings(self.db, uid)}


    # ---- M12: maxfiylik va xavfsizlik — faol sessiyalar ----

    def me_sessions(self):
        if not self.user:
            return UNAUTH, err("auth.required")
        cur = None
        if self.token:
            cur = self.db.q1(
                "SELECT id FROM sessions_ring WHERE token_hash=?",
                (hashlib.sha256(self.token.encode("utf-8")).hexdigest(),))
        cur_id = cur["id"] if cur else None
        rows = self.db.q(
            "SELECT id, created_at, expires_at, last_seen FROM sessions_ring "
            "WHERE user_id=? ORDER BY id DESC", (self.user["id"],))
        for r in rows:
            r["current"] = (r["id"] == cur_id)
        return OK, {"ok": True, "sessions": rows}

    def me_session_revoke(self, body):
        if not self.user:
            return UNAUTH, err("auth.required")
        try:
            sid = int(body.get("id") or 0)
        except (TypeError, ValueError):
            return BAD, err("invalid_input")
        row = self.db.q1(
            "SELECT * FROM sessions_ring WHERE id=? AND user_id=?",
            (sid, self.user["id"]))
        if not row:
            return NOTFOUND, err("invalid_input")
        self.db.upd("DELETE FROM sessions_ring WHERE id=? AND user_id=?", (sid, self.user["id"]))
        cur = False
        if self.token:
            th = hashlib.sha256(self.token.encode("utf-8")).hexdigest()
            cur = row["token_hash"] == th
        return OK, {"ok": True, "current_revoked": cur}

    def me_sessions_revoke_all(self):
        if not self.user:
            return UNAUTH, err("auth.required")
        self.db.upd("DELETE FROM sessions_ring WHERE user_id=?", (self.user["id"],))
        return OK, {"ok": True, "current_revoked": True}

    def me_messages(self, query):
        if not self.user:
            return UNAUTH, err("auth.required")
        with_ = query.get("with")
        if with_:
            rows = self.db.q(
                """SELECT * FROM messages WHERE (from_user_id=? AND to_user_id=?) OR (from_user_id=? AND to_user_id=?)
                   ORDER BY id DESC LIMIT 200""",
                (self.user["id"], with_, with_, self.user["id"]),
            )
            self.db.upd("UPDATE messages SET is_read=1 WHERE from_user_id=? AND to_user_id=? AND is_read=0", (with_, self.user["id"],))
        else:
            rows = self.db.q(
                """SELECT m.*, u.first_name, u.last_name FROM messages m
                   JOIN users u ON u.id=m.from_user_id
                   WHERE m.to_user_id=? ORDER BY m.id DESC LIMIT 100""", (self.user["id"],)
            )
        return OK, {"ok": True, "messages": rows}

    def me_send_message(self, body):
        if not self.user:
            return UNAUTH, err("auth.required")
        to_id = body.get("to_user_id")
        text = str(body.get("text", "")).strip()
        if not to_id or not text:
            return BAD, err("msg.empty")
        mid = self.db.ex(
            "INSERT INTO messages(session_id, from_user_id, to_user_id, text, created_at) VALUES(?,?,?,?,?)",
            (body.get("session_id"), self.user["id"], to_id, text, now()),
        )
        notify(self.db, to_id, "msg.new", text[:120], "message", {"message_id": mid, "text": text[:120]},
               sender_id=self.user["id"], sender_role=self.user["role"])
        return OK, {"ok": True, "id": mid}

    # BAND 15: "Profilim" -> "Tahrirlash" — 5 ta maydon:
    #   tug'ilgan sana, telefon, login, guruh, haydovchilik toifasi.
    # Parol BU YERDA KO'RSATILMAYDI va o'zgartirilmaydi — u alohida
    # xavfsiz oqim: `POST /api/auth/change-password`.
    PROFILE_USER_FIELDS = ("birth_date", "phone", "first_name", "last_name", "middle_name")
    PROFILE_STUDENT_FIELDS = ("group_name", "license_category")

    def me_update_profile(self, body):
        """`PUT /api/me/profile` — o'z profilini tahrirlash.

        Validatsiya IKKALA tomonda ham (server va frontend). Login:
          * `usrL_` formatida bo'lishi shart (BAND 5/15),
          * boshqa foydalanuvchining login'i bilan TAKRORLANMASIN.
        Login o'zgartirilsa — eski sessiyalar BEKOR qilinadi (login
        o'g'irlangan bo'lishi mumkin).
        """
        if not self.user:
            return UNAUTH, err("auth.required")
        fields = {}
        for f in self.PROFILE_USER_FIELDS:
            if f in body and body[f] is not None:
                fields[f] = str(body[f]).strip()
        # --- login (alohida: unikal + `usrL_` formati) ---
        login_changed = False
        if "login" in body and body["login"] is not None:
            new_login = str(body["login"]).strip()
            if not is_valid_login(new_login):
                return BAD, err("profile.login_format")
            if new_login != self.user["login"]:
                # `deleted_at` filtrisiz: yumshoq o'chirilgan (archiv) login ham
                # qayta ishlatilmasligi kerak (UNIQUE constraint shuni talab qiladi).
                if self.db.q1("SELECT id FROM users WHERE login=?", (new_login,)):
                    return BAD, err("profile.login_taken")
                fields["login"] = new_login
                login_changed = True
        # --- telefon ---
        if "phone" in fields:
            phone = re.sub(r"[^\d+]", "", fields["phone"])
            if phone and not (7 <= len(phone.lstrip("+")) <= 15):
                return BAD, err("profile.phone_invalid")
            fields["phone"] = phone
        # --- tug'ilgan sana ---
        if "birth_date" in fields and fields["birth_date"]:
            d = parse_date(fields["birth_date"])
            if not d:
                return BAD, err("profile.birth_date_invalid")
            if d.year < 1900 or d > _dt.date.today():
                return BAD, err("profile.birth_date_invalid")
            fields["birth_date"] = d.strftime("%Y-%m-%d")
        if fields:
            fields["updated_at"] = now()
            self.db.upd("UPDATE users SET " + ", ".join(f"{k}=?" for k in fields) + " WHERE id=?",
                        (*fields.values(), self.user["id"]))
        # --- talabaga xos maydonlar (guruh, haydovchilik toifasi) ---
        sfields = {}
        for f in self.PROFILE_STUDENT_FIELDS:
            if f in body and body[f] is not None:
                sfields[f] = str(body[f]).strip()
        if self.user["role"] == "student" and sfields:
            st = self._stud_record()
            if st:
                self.db.upd("UPDATE students SET " + ", ".join(f"{k}=?" for k in sfields) + " WHERE id=?",
                            (*sfields.values(), st["id"]))
        if login_changed:
            # Xavfsizlik: login o'zgargandan keyin boshqa qurilmalardagi
            # sessiyalar yoki o'g'irlangan login bilan kirish to'xtatiladi.
            self.db.upd("DELETE FROM sessions_ring WHERE user_id=?", (self.user["id"],))
        return OK, {"ok": True, "updated": sorted(list(fields) + list(sfields)),
                    "login_changed": login_changed}

    def me_update_avatar(self, body):
        """Profil rasmini yuklash: `data:image/png|jpeg|webp;base64,...` qabul qiladi.
        Hajm ≤5MB, format jpg/png/webp — noto'g'ri kirishda aniq xato."""
        if not self.user:
            return UNAUTH, err("auth.required")
        data_url = str(body.get("image", ""))
        try:
            path, full = save_data_url_image(data_url, "avatars", "u%d_" % self.user["id"])
        except ValueError as ve:
            return BAD, err(str(ve))
        old = self.user.get("profile_image") or ""
        self.db.upd("UPDATE users SET profile_image=?, updated_at=? WHERE id=?",
                    (path, now(), self.user["id"]))
        if old.startswith("/uploads/avatars/"):
            try:
                os.remove(upload_dir("avatars") + os.sep + os.path.basename(old))
            except OSError:
                pass
        audit(self.db, self.user["id"], "profile.avatar_update", "user", self.user["id"], {})
        return OK, {"ok": True, "profile_image": path}

    # ------------------------------------------------------- 2FA (TOTP)
    def me_2fa_enable(self, body):
        """2FA yoqish: parolni tasdiqlash + telefon raqamiga SMS kod (simulyatsiya).
        QR yo'q — kod bildirishnoma sifatida ham yuboriladi."""
        if not self.user:
            return UNAUTH, err("auth.required")
        if not verify_password(str(body.get("password", "")), self.user["password_hash"]):
            return BAD, err("auth.wrong_old_password")
        secret = _new_totp_secret()
        self.db.upd("UPDATE users SET totp_secret=?, updated_at=? WHERE id=?",
                    (secret, now(), self.user["id"]))
        phone = str(body.get("phone", "")).strip() or (self.user.get("phone") or "")
        self._twofa_send_code(self.user, phone, force=True)
        return OK, {"ok": True}

    def me_2fa_verify_enable(self, body):
        """2FA ni yoqishni tasdiqlash: SMS kodni qo'lda kiritib tasdiqlaydi."""
        if not self.user:
            return UNAUTH, err("auth.required")
        if not self._check_twofa_code(self.user, str(body.get("code", ""))):
            return BAD, err("auth.otp_invalid")
        self.db.upd("UPDATE users SET totp_enabled=1, updated_at=? WHERE id=?",
                    (now(), self.user["id"]))
        return OK, {"ok": True}

    def me_2fa_disable(self, body):
        """2FA o'chirish: joriy parolni tasdiqlash bilan."""
        if not self.user:
            return UNAUTH, err("auth.required")
        if not verify_password(str(body.get("password", "")), self.user["password_hash"]):
            return BAD, err("auth.wrong_old_password")
        self.db.upd("UPDATE users SET totp_enabled=0, totp_secret='', updated_at=? WHERE id=?",
                    (now(), self.user["id"]))
        return OK, {"ok": True}

    def _twofa_send_code(self, u, phone="", force=False):
        """6 xonali SMS kod yaratadi va bildirishnoma (simulyatsiya) orqali yuboradi.
        force=False bo'lsa, amaldagi foydalanilmagan kod bo'lsa qayta yubormaydi."""
        from datetime import datetime, timedelta
        if not force:
            pending = self.db.q1(
                "SELECT 1 FROM twofa_codes WHERE user_id=? AND used_at='' AND expires_at>=? ORDER BY id DESC LIMIT 1",
                (u["id"], now()))
            if pending:
                return None
        code = str(secrets.randbelow(1000000)).zfill(6)
        expires = (datetime.now() + timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M:%S")
        # foydalanilmagan eski kodlarni bekor qilamiz
        self.db.upd("UPDATE twofa_codes SET used_at=? WHERE user_id=? AND used_at=''", (now(), u["id"]))
        self.db.ex(
            "INSERT INTO twofa_codes(user_id, code_hash, phone, expires_at, created_at) VALUES(?,?,?,?,?)",
            (u["id"], hash_password(code), phone, expires, now()))
        notify(self.db, u["id"], "2fa.code",
               f"{code} — {phone or u.get('phone') or 'telefon'}. Kod 5 daqiqa amal qiladi.", "2fa",
               {"code": code})
        return code

    def _check_twofa_code(self, u, code):
        """SMS kod amal qilishini tekshiradi; muvaffaqiyatda iste'mol qilinadi (TOTP hali ham o'tadi)."""
        if not code:
            return False
        row = self.db.q1(
            "SELECT * FROM twofa_codes WHERE user_id=? AND used_at='' AND expires_at>=? ORDER BY id DESC LIMIT 1",
            (u["id"], now()))
        if row and verify_password(code, row["code_hash"]):
            self.db.upd("UPDATE twofa_codes SET used_at=? WHERE id=?", (now(), row["id"]))
            return True
        if verify_totp(u.get("totp_secret", ""), code):
            return True
        return False

    # -------------------------------------------------------------- ADMIN
    # ---- dashboard
    def admin_dashboard(self):
        self._require("admin")
        db = self.db
        ws = _week_monday()
        we = today()
        d = {"students": db.q1("SELECT COUNT(*) c FROM students WHERE status='active'")["c"],
             "instructors": db.q1("SELECT COUNT(*) c FROM instructors WHERE status='active'")["c"],
             "cars": db.q1("SELECT COUNT(*) c FROM cars WHERE deleted_at IS NULL")["c"],
             "cars_active": db.q1("SELECT COUNT(*) c FROM cars WHERE deleted_at IS NULL AND status='active'")["c"],
             "cars_repair": db.q1("SELECT COUNT(*) c FROM cars WHERE deleted_at IS NULL AND status='repair'")["c"],
             "today_sessions": db.q1("SELECT COUNT(*) c FROM lesson_sessions WHERE date=? AND status!='cancelled'", (today(),))["c"],
             "pending_requests": db.q1("SELECT COUNT(*) c FROM practice_requests WHERE status='pending'")["c"],
             "active_instructors": db.q1("SELECT COUNT(*) c FROM users WHERE role='instructor' AND status='active' AND deleted_at IS NULL")["c"],
             "total_users": db.q1("SELECT COUNT(*) c FROM users WHERE deleted_at IS NULL")["c"],
             "blocked_users": db.q1("SELECT COUNT(*) c FROM users WHERE status='blocked' AND deleted_at IS NULL")["c"],
             "archived_users": db.q1("SELECT COUNT(*) c FROM users WHERE status='archived' AND deleted_at IS NULL")["c"],
             "today_sessions_list": db.q(
                 """SELECT ls.id, ls.date, ls.start_time, ls.end_time, ls.status, ls.capacity_snapshot,
                          ls.car_name_snapshot, ls.car_plate_snapshot,
                          u.first_name||' '||u.last_name AS instructor_name,
                          (SELECT COUNT(*) FROM session_students ss WHERE ss.session_id=ls.id AND ss.student_status='active') AS student_count
                   FROM lesson_sessions ls JOIN instructors i ON i.id=ls.instructor_id
                   JOIN users u ON u.id=i.user_id
                   WHERE ls.date=? AND ls.status!='cancelled' ORDER BY ls.start_time""", (today(),))}
        # M6: haftalik statistika (Bosh sahifa uchun)
        wk_rows = db.q(
            "SELECT date, start_time, end_time, status FROM lesson_sessions WHERE date>=? AND date<=? AND status!='cancelled'",
            (ws, we))
        d["week_sessions"] = len(wk_rows)
        d["week_done"] = sum(1 for r in wk_rows if r["status"] == "completed")
        d["week_hours"] = round(sum(_dur_hours(r["start_time"], r["end_time"]) for r in wk_rows), 1)
        d["week_requests"] = db.q1("SELECT COUNT(*) c FROM practice_requests WHERE created_at>=? AND created_at<=?",
                                   (ws + " 00:00:00", we + " 23:59:59"))["c"]
        d["week_new_users"] = db.q1("SELECT COUNT(*) c FROM users WHERE created_at>=? AND created_at<=?",
                                    (ws + " 00:00:00", we + " 23:59:59"))["c"]
        # M8: haftalik faollik grafiki — kunlar bo'yicha mashg'ulotlar soni (du..ya)
        by_day = {dd: 0 for dd in _week_days()}
        for r in wk_rows:
            if r["date"] in by_day:
                by_day[r["date"]] += 1
        d["week_sessions_by_day"] = [{"date": dd, "count": by_day[dd]} for dd in by_day]
        return OK, {"ok": True, "dashboard": d}

    # ---- users
    def admin_users(self, query):
        self._require("admin")
        # MODUL 2.2/3.2: "Arxiv" — arxivlangan foydalanuvchilar ro'yxatdan
        # BUTUNLAY yo'qolmasligi kerak (ularni keyin qaytarib bo'ladi).
        # Shu sababli `status=archived` filtrida `deleted_at IS NULL` sharti
        # qo'llanmaydi. Boshqa holatlar (active/blocked) yoki filtrsiz
        # chaqiruvda avvalgi xatti-harakat saqlanadi.
        _status = query.get("status")
        if _status == "archived":
            # "Arxiv" — bitta `status` qiymati ikkita holatni (bloklash +
            # arxivlash) birga saqlay olmagani uchun asosiy belgi `deleted_at`.
            # Aks holda "arxivlangan va bloklangan" foydalanuvchi hech
            # qanday filtrda ham ko'rinmasdi.
            where = ["(status='archived' OR deleted_at IS NOT NULL)"]
            params = []
        elif _status:
            where = ["status=?", "deleted_at IS NULL"]
            params = [_status]
        else:
            where = ["deleted_at IS NULL"]
            params = []
        if query.get("role"):
            where.append("role=?")
            params.append(query["role"])
        if query.get("q"):
            where.append("(first_name LIKE ? OR last_name LIKE ? OR login LIKE ? OR phone LIKE ?)")
            p = "%" + query["q"] + "%"
            params += [p, p, p, p]
        rows = self.db.q(
            "SELECT * FROM users WHERE " + " AND ".join(where) + " ORDER BY id DESC LIMIT 500", params
        )
        out = [user_public(r) for r in rows]

        # MODUL 2: "Jami: N ta talaba" — hisoblagich BIR XIL shartlar bilan
        # (rol + holat + qidiruv) hisoblanadi, shuning uchun filtr qo'yilganda
        # son ham filtrlangan natijaga mos yangilanadi.
        # `LIMIT 500` dan O'TMAYDI: bu umumiy son (jami nechta mos kator bor).
        total_all = self.db.q1(
            "SELECT COUNT(*) c FROM users WHERE deleted_at IS NULL")["c"]
        total = self.db.q1(
            "SELECT COUNT(*) c FROM users WHERE " + " AND ".join(where), params)["c"]
        # `by_role` — barcha toifalarning umumiy sonlari (bo'sh filtr bilan).
        by_role = {r["role"]: r["c"] for r in self.db.q(
            "SELECT role, COUNT(*) c FROM users WHERE deleted_at IS NULL GROUP BY role")}

        # MODUL 6: rolda bo'linish uchun qo'shimcha ma'lumotlar BULK so'rov bilan
        # olinadi (har bir qatorga alohida SQL yubormaslik uchun — N+1 oldi olindi).
        st_by_uid = {s["user_id"]: s for s in self.db.q("SELECT * FROM students")}
        inst_by_uid = {i["user_id"]: i for i in self.db.q("SELECT * FROM instructors")}

        prog = {}
        if any(u["role"] == "student" for u in out):
            for p in self.db.q(
                """SELECT ss.student_id AS sid,
                          COUNT(*) AS total,
                          SUM(CASE WHEN ls.status='completed' THEN 1 ELSE 0 END) AS done
                   FROM session_students ss
                   JOIN lesson_sessions ls ON ls.id=ss.session_id
                   WHERE ss.student_status='active' AND ls.status!='cancelled'
                   GROUP BY ss.student_id"""
            ):
                # MUHIM: o'zgaruvchi nomi `total` EMAS — yuqorida hisoblangan
                # "Jami: N ta talaba" soni shu yerda qayta yozilib ketardi
                # (natijada hisoblagich oxirgi talabaning dars sonini
                # ko'rsatgan: "Jami: 1 ta talaba").
                s_total = p["total"] or 0
                done = p["done"] or 0
                prog[p["sid"]] = {
                    "total": s_total, "done": done,
                    "pct": round(done * 100 / s_total) if s_total else 0,
                }

        # BAND 22: admin ro'yxatida maqsadli (jami) darslar soni va qolgani
        # ham ko'rsatiladi. Maqsad: talabaning o'z `total_lessons_target` qiymati,
        # yo'q bo'lsa platforma umumiy sozlamasi.
        group_target = DEFAULT_PLATFORM_SETTINGS["total_lessons_target"]

        inst_of = {}
        if any(u["role"] == "student" for u in out):
            for p in self.db.q(
                """SELECT DISTINCT ss.student_id AS sid, i.id AS iid,
                          u.first_name||' '||u.last_name AS name
                   FROM session_students ss
                   JOIN lesson_sessions ls ON ls.id=ss.session_id
                   JOIN instructors i ON i.id=ls.instructor_id
                   JOIN users u ON u.id=i.user_id
                   WHERE ss.student_status='active' ORDER BY ss.student_id, name"""
            ):
                inst_of.setdefault(p["sid"], []).append({"id": p["iid"], "name": p["name"]})

        stud_count = {}
        if any(u["role"] == "instructor" for u in out):
            for p in self.db.q(
                """SELECT ls.instructor_id AS iid,
                          COUNT(DISTINCT CASE WHEN ss.student_status='active' THEN ss.student_id END) AS n
                   FROM lesson_sessions ls
                   JOIN session_students ss ON ss.session_id=ls.id
                   GROUP BY ls.instructor_id"""
            ):
                stud_count[p["iid"]] = p["n"] or 0

        for u in out:
            if u["role"] == "student":
                s = st_by_uid.get(u["id"])
                u["student"] = s
                if s:
                    # BAND 16: `enrolled_at` faqat admin ko'radi (admin ro'yxati
                    # shuning uchun to'liq qator qaytariladi).
                    pr0 = dict(prog.get(s["id"], {"total": 0, "done": 0, "pct": 0}))
                    own = s.get("total_lessons_target")
                    target = int(own) if own else group_target
                    pr0["target"] = target
                    pr0["individual_target"] = int(own) if own else None
                    pr0["group_target"] = group_target
                    pr0["mode"] = "individual" if own else "group"
                    pr0["remaining"] = max(0, target - pr0["done"])
                    pr0["pct"] = round(pr0["done"] * 100 / target) if target else 0
                    u["progress"] = pr0
                    u["instructors"] = inst_of.get(s["id"], [])
            elif u["role"] == "instructor":
                i_ = inst_by_uid.get(u["id"])
                u["instructor"] = i_
                if i_:
                    u["students_count"] = stud_count.get(i_["id"], 0)
                if i_ and i_["assigned_car_id"]:
                    c = self.db.q1("SELECT id, brand, model, plate_number, practice_capacity, status FROM cars WHERE id=?", (i_["assigned_car_id"],))
                    u["car"] = c
        # MODUL 2/6: `total` — jami (hisoblagich uchun), `by_role` — toifalar
        # kesimidagi umumiy sonlar, `filtered` — filtr qo'llanganmi.
        filtered = bool(query.get("role") or query.get("status") or query.get("q"))
        return OK, {"ok": True, "users": out, "total": int(total),
                    "shown": len(out), "by_role": by_role,
                    "total_all": int(total_all), "filtered": filtered,
                    "limited": int(total) > len(out)}

    def admin_user_create(self, body):
        self._require("admin")
        role = body.get("role")
        if role not in ("student", "instructor", "admin"):
            return BAD, err("user.invalid_role")
        db = self.db
        created = db.transaction(lambda c: self._create_user_tx(c, body, role))
        # MODUL 3: yangi admin yaratilganda aniq audit yozuvi — kim yaratdi,
        # kimga yaratildi. Parolning O'ZI yozilmaydi (faqat login).
        if role == "admin":
            audit(db, self.user["id"], action_type="admin_created", target_type="users",
                  target_id=created["user"]["id"],
                  description="%s -> yangi admin %s yaratildi" % (user_name(self.user), created["user"]["login"]))
        else:
            audit(db, self.user["id"], "user created", "users", created["user"]["id"],
                  {"login": created["user"]["login"], "role": role})
        return OK, {"ok": True, "credentials": created["credentials"], "user": created["user"]}

    def _create_user_tx(self, c, body, role):
        first = str(body.get("first_name", "")).strip()
        last = str(body.get("last_name", "")).strip()
        if not first or not last:
            raise ApiError(BAD, "user.name_required")
        login, password = next_credentials(c)
        from .db import now as _now
        t = _now()
        cur = c.execute(
            """INSERT INTO users(first_name,last_name,middle_name,birth_date,gender,phone,secondary_phone,
                                 login,password_hash,password_enc,role,status,profile_image,must_change_password,
                                 created_at,updated_at)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (first, last, str(body.get("middle_name", "")).strip(),
             str(body.get("birth_date", "")).strip(), str(body.get("gender", "")).strip(),
             str(body.get("phone", "")).strip(), str(body.get("secondary_phone", "")).strip(),
             login, hash_password(password), encrypt_par(password), role, "active",
             str(body.get("profile_image", "")).strip(), 1, t, t),
        )
        uid = cur.lastrowid
        if role == "student":
            # MODUL 5: individual jami-darslar maqsadi (bo'sh = ommaviy sozlama)
            try:
                _tgt = int(body["total_lessons_target"]) if body.get("total_lessons_target") else None
            except (TypeError, ValueError):
                _tgt = None
            if _tgt is not None and (_tgt < 1 or _tgt > 999):
                raise ApiError(BAD, "user.bad_total_lessons")
            c.execute(
                """INSERT INTO students(user_id, group_name, license_category, study_status, enrolled_at,
                                        address, notes, total_lessons_target, status)
                   VALUES(?,?,?,?,?,?,?,?,?)""",
                (uid, str(body.get("group_name", "")).strip(), str(body.get("license_category", "B")).strip(),
                 "active", str(body.get("enrolled_at") or _now()[:10]).strip(),
                 str(body.get("address", "")).strip(), str(body.get("notes", "")).strip(), _tgt, "active"),
            )
        elif role == "instructor":
            c.execute(
                """INSERT INTO instructors(user_id, license_categories, experience_years, bio, work_days,
                                           work_start, work_end, break_start, break_end, assigned_car_id, status)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                (uid, str(body.get("license_categories", "B")).strip(),
                 int(body.get("experience_years") or 0), str(body.get("bio", "")).strip(),
                 json.dumps(body.get("work_days") or ["mon", "tue", "wed", "thu", "fri", "sat"], ensure_ascii=False),
                 str(body.get("work_start", "08:00")).strip(), str(body.get("work_end", "18:00")).strip(),
                 str(body.get("break_start", "13:00")).strip(), str(body.get("break_end", "14:00")).strip(),
                 int(body["assigned_car_id"]) if body.get("assigned_car_id") else None, "active"),
            )
        # MODUL 3: `role == "admin"` uchun alohida profil jadvali (students /
        # instructors kabi) YO'Q — admin ma'lumotlari to'liq `users` da turadi,
        # shuning uchun qo'shimcha INSERT bajarilmaydi.
        u = dict(c.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone())
        return {"user": u, "credentials": {"login": login, "password": password}}

    def admin_users_bulk(self, body):
        self._require("admin")
        role = body.get("role", "student")
        count = int(body.get("count") or 10)
        if role not in ("student",):
            return BAD, err("user.bulk_role")
        if count < 1 or count > 1000:
            return BAD, err("user.bulk_count")
        created = []
        for i in range(count):
            try:
                rec = self.db.transaction(lambda c, i=i: self._create_user_tx(
                    c, {"first_name": f"Talaba{i+1}", "last_name": "Import"}, role))
                created.append(rec["credentials"])
            except ApiError as e:
                return e.status, err(e.code)
        audit(self.db, self.user["id"], "bulk created", "users", None, {"count": count})
        return OK, {"ok": True, "created": created, "count": len(created)}

    # ====================================================================
    # MODUL 6 — OMMAVIY (BULK) AMALLAR: o'chirish va tahrirlash
    #
    # HIMOYALAR:
    #   * RBAC: faqat `admin`.
    #   * IDOR/INJEKSIYA: `user_id` ro'yxati — har bir ID `int()` orqali
    #     tekshiriladi va `?` placeholder bilan so'raladi (SQLi yo'q).
    #   * `MAX_BULK = 200` — bitta so'rovda juda ko'p yozilishdan saqlaydi
    #     (DoS/tez timeout). `bulk.too_many` bilan aniq rad etiladi.
    #   * O'ZINI O'CHIRISHGA BO'LMAYDI: ro'yxatda o'z `id`si bo'lsa
    #     (`self_protected`) — admin o'zini o'chira olmaydi. Bu muhim:
    #     aks holda tizimda admin qolmay qolishi mumkin.
    #   * O'chirish `deleted_at` bilan YUMISH (soft delete) — foydalanuvchi
    #     ma'lumotlari (mashg'ulotlar, tarix) o'chmaydi va tiklanadi.
    # ====================================================================
    MAX_BULK = 200

    def _bulk_ids(self, body):
        """`ids` ro'yxatini xavfsiz int listiga aylantiradi (SQLi himoyasi)."""
        raw = body.get("ids")
        if not isinstance(raw, (list, tuple)) or not raw:
            return None, BAD, err("bulk.none")
        if len(raw) > self.MAX_BULK:
            return None, BAD, err("bulk.too_many", {"n": self.MAX_BULK})
        ids = []
        for x in raw:
            try:
                n = int(x)
            except (TypeError, ValueError):
                return None, BAD, err("bulk.bad_id")
            if n > 0:
                ids.append(n)
        if not ids:
            return None, BAD, err("bulk.none")
        return ids, OK, None

    def admin_users_bulk_update(self, body):
        """`POST /api/admin/users/bulk-update` — MODUL 6.

        Tanlangan foydalanuvchilarning UMUMIY maydonlarini bir vaqtda
        o'zgartiradi (masalan: barcha tanlangan talabalarning guruhini
        bir xil qilib belgilash, yoki hammasini "Faol" qilish).

        QOIDALAR:
          * BO'SH maydonlar UMUMAN o'zgartirilmaydi ("o'zgartirilmaydi"
            semantikasi) — `None` yoki bo'sh string `skip` qilinadi.
          * Har bir maydon turi tekshiriladi (uzunlik, ruxsatli ro'yxat).
          * `total_lessons_target` faqat talabalar uchun.
        """
        self._require("admin")
        ids, st, e = self._bulk_ids(body)
        if st != OK:
            return st, e
        fields = {}
        # --- umumiy maydonlar (users jadvali) ---
        if body.get("status") in ("active", "blocked"):
            fields["status"] = body["status"]
        if body.get("phone"):
            fields["phone"] = str(body["phone"]).strip()[:40]
        if body.get("notes"):
            fields["notes"] = str(body["notes"]).strip()[:500]
        # --- talaba maydonlari (students jadvali) ---
        s_fields = {}
        if body.get("group_name"):
            s_fields["group_name"] = str(body["group_name"]).strip()[:60]
        if body.get("license_category"):
            s_fields["license_category"] = str(body["license_category"]).strip()[:8]
        if body.get("study_status") in ("active", "paused", "graduated", "dropped"):
            s_fields["study_status"] = body["study_status"]
        if body.get("total_lessons_target") not in (None, "", 0, "0"):
            try:
                tv = int(body["total_lessons_target"])
            except (TypeError, ValueError):
                return BAD, err("user.bad_total_lessons")
            if tv < 1 or tv > 999:
                return BAD, err("user.bad_total_lessons")
            s_fields["total_lessons_target"] = tv
        if not fields and not s_fields:
            return BAD, err("bulk.nothing_to_change")

        updated = 0
        # `status` o'zgarishi users jadvalida
        if fields:
            sets = ", ".join(f"{k}=?" for k in fields)
            vals = list(fields.values())
            vals += [now(), *ids]
            ph = ",".join("?" * len(ids))
            updated += self.db.upd(
                "UPDATE users SET " + sets + ", updated_at=? WHERE id IN (" + ph + ")",
                tuple(vals))
        # `group_name`/`category`/`study_status` o'zgarishi students jadvalida.
        # `users.id` -> `students.user_id` bog'lanishini ishlatamiz (user_id).
        if s_fields:
            sets = ", ".join(f"{k}=?" for k in s_fields)
            vals = list(s_fields.values())
            vals += [*ids]
            ph = ",".join("?" * len(ids))
            updated += self.db.upd(
                "UPDATE students SET " + sets + " WHERE user_id IN (" + ph + ")",
                tuple(vals))
        audit(self.db, self.user["id"], "bulk updated", "users", None,
              {"count": updated, "ids": ids[:50]})
        return OK, {"ok": True, "updated": updated}

    def admin_users_bulk_delete(self, body):
        """`POST /api/admin/users/bulk-delete` — MODUL 6.

        Tanlangan foydalanuvchilarni O'CHIRADI (soft delete `deleted_at`).
        HIMOYA: o'zini o'chirishga BO'LMAYDI (`self_protected`).
        """
        self._require("admin")
        ids, st, e = self._bulk_ids(body)
        if st != OK:
            return st, e
        # O'ZINI HIMOYA QILISH: admin o'zini o'chira olmaydi.
        if self.user["id"] in ids:
            return BAD, err("bulk.self_protected")
        ph = ",".join("?" * len(ids))
        n = self.db.upd(
            "UPDATE users SET deleted_at=?, status='archived', updated_at=? "
            "WHERE deleted_at IS NULL AND id IN (" + ph + ") AND id!=?",
            (now(), now(), *ids, self.user["id"]))
        audit(self.db, self.user["id"], "bulk deleted", "users", None,
              {"count": n, "ids": ids[:50]})
        return OK, {"ok": True, "deleted": n}

    def admin_users_update(self, body, uid):
        self._require("admin")
        u = self.db.q1("SELECT * FROM users WHERE id=? AND deleted_at IS NULL", (uid,))
        if not u:
            return NOTFOUND, err("user.not_found")
        fields = {}
        for f in ("first_name", "last_name", "middle_name", "birth_date", "gender", "phone", "secondary_phone", "profile_image"):
            if f in body and body[f] is not None:
                fields[f] = str(body[f]).strip()
        if fields:
            fields["updated_at"] = now()
            self.db.upd("UPDATE users SET " + ", ".join(f"{k}=?" for k in fields) + " WHERE id=?",
                        (*fields.values(), uid))
        # student profili
        if u["role"] == "student" and body.get("student"):
            s = body["student"]
            # MODUL 5: individual "jami darslar" maqsadi. None/0/bo'sh = ommaviy
            # (platforma) sozlamasiga qaytish.
            target = s.get("total_lessons_target", "__keep__")
            if target != "__keep__":
                try:
                    tv = int(target) if target not in (None, "", 0, "0") else None
                except (TypeError, ValueError):
                    return BAD, err("user.bad_total_lessons")
                if tv is not None and (tv < 1 or tv > 999):
                    return BAD, err("user.bad_total_lessons")
                self.db.upd("UPDATE students SET total_lessons_target=? WHERE user_id=?", (tv, uid))
            self.db.upd(
                """UPDATE students SET group_name=?, license_category=?, study_status=?, enrolled_at=?, address=?, notes=? WHERE user_id=?""",
                (str(s.get("group_name", "")).strip(), str(s.get("license_category", "B")).strip(),
                 str(s.get("study_status", "active")).strip(), str(s.get("enrolled_at") or now()[:10]).strip(),
                 str(s.get("address", "")).strip(), str(s.get("notes", "")).strip(), uid),
            )
        if u["role"] == "instructor" and body.get("instructor"):
            i_ = body["instructor"]
            self.db.upd(
                """UPDATE instructors SET license_categories=?, experience_years=?, bio=?, work_days=?, work_start=?, work_end=?, break_start=?, break_end=? WHERE user_id=?""",
                (str(i_.get("license_categories", "B")).strip(), int(i_.get("experience_years") or 0),
                 str(i_.get("bio", "")).strip(),
                 json.dumps(i_.get("work_days") or ["mon", "tue", "wed", "thu", "fri", "sat"], ensure_ascii=False),
                 str(i_.get("work_start", "08:00")).strip(), str(i_.get("work_end", "18:00")).strip(),
                 str(i_.get("break_start", "13:00")).strip(), str(i_.get("break_end", "14:00")).strip(), uid),
            )
        audit(self.db, self.user["id"], "user updated", "users", int(uid))
        return OK, {"ok": True}

    def admin_users_status(self, body, uid):
        self._require("admin")
        st = body.get("status")
        if st not in ("block", "unblock", "archive", "unarchive"):
            return BAD, err("user.bad_status")
        map_st = {"block": "blocked", "unblock": "active",
                  "archive": "archived", "unarchive": "active"}
        new_status = map_st.get(st)
        if not new_status:
            return BAD, err("user.bad_status")
        u = self.db.q1("SELECT * FROM users WHERE id=?", (int(uid),))
        if not u:
            return NOTFOUND, err("user.not_found")
        # MODUL 3: adminga nisbatan bloklash/arxivlash mumkin, lekin
        # 1) o'zini o'zi bloklay/arxivlay OLMAYDI (tizimga kirishdan qoliladi),
        # 2) oxirgi faol adminni bloklash/arxivlashga ruxsat YO'Q — aks holda
        #    hech kim panelga kira olmay qoladi.
        if u["role"] == "admin" and new_status in ("blocked", "archived"):
            if int(uid) == int(self.user["id"]):
                return BAD, err("user.cannot_block_self")
            left = self.db.q1(
                "SELECT COUNT(*) AS c FROM users WHERE role='admin' AND status='active'"
                " AND deleted_at IS NULL AND id<>?",
                (int(uid),),
            )
            if int(left["c"] or 0) == 0:
                return BAD, err("user.last_admin_protected")
        sets = ["status=?", "updated_at=?"]
        params = [new_status, now()]
        # `deleted_at` faqat ARXIV bilan bog'liq: bloklash uni tegmamasligi
        # kerak (aks holda arxivlangan foydalanuvchini bloklash uni "arxivdan
        # chiqarib" yuborardi).
        if st == "archive":
            sets.append("deleted_at=?")
            params.append(now())
        elif st == "unarchive":
            sets.append("deleted_at=NULL")
        params.append(int(uid))
        self.db.upd("UPDATE users SET " + ", ".join(sets) + " WHERE id=?", params)
        if new_status == "blocked" or new_status == "archived":
            self.db.upd("DELETE FROM sessions_ring WHERE user_id=?", (int(uid),))
        act = {"blocked": "user_blocked", "active": "user_activated",
               "archived": "user_archived"}[new_status]
        audit(self.db, self.user["id"], action_type=act, target_type="users",
              target_id=int(uid),
              description="%s: %s (%s) -> %s" % (act, user_name(self.user), u["login"], new_status))
        return OK, {"ok": True, "status": new_status}

    def admin_user_reset_password(self, uid, body=None):
        """`POST /api/admin/users/{id}/reset-password` — parolni tiklash.

        Ikki rejim:
          * `body.new_password` berilmasa — `usrP_` + 14 ta xavfsiz random
            belgi generatsiya qilinadi (katta/kichik harf, raqam, maxsus belgi).
          * `body.new_password` berilsa — ADMIN qo'lda belgilagan parol; u ham
            bir xil kuch talablariga (10+ belgi, bosh/kichik harf, raqam)
            javob berishi SHART (MODUL 4 — backendda qayta tekshiriladi).

        MODUL 5: parol endi `password_enc` (AES-256-GCM) sifatida ham
        saqlanadi — admin uni 🔑 orqali keyin HAM ko'ra (va o'zgartira) oladi.
        "Bir marta ko'rsatish" cheklovi OLIB TASHLANDI.
        """
        self._require("admin")
        body = body or {}
        u = self.db.q1("SELECT * FROM users WHERE id=? AND deleted_at IS NULL", (int(uid),))
        if not u:
            return NOTFOUND, err("user.not_found")
        custom = str(body.get("new_password", "") or "")
        if custom:
            strength = password_strength_errors(custom)
            if strength:
                return BAD, err("auth.password_weak", {"errors": strength})
            pd = credential_digest(custom)
            if self.db.q1("SELECT 1 FROM used_credentials WHERE password_digest=?", (pd,)):
                return BAD, err("auth.password_used")
            newpass = custom
            self.db.transaction(lambda c: c.execute(
                "INSERT INTO used_credentials(login_digest, password_digest, created_at)"
                " VALUES(?,?,?)",
                (credential_digest("reset:" + str(uid) + ":" + custom), pd, now())))
        else:
            newpass = self.db.transaction(lambda c: generate_credentials(c)[1])
        self.db.upd(
            "UPDATE users SET password_hash=?, password_enc=?, must_change_password=1, updated_at=? WHERE id=?",
            (hash_password(newpass), encrypt_par(newpass), now(), int(uid)),
        )
        # Xavfsizlik: parol almashtirilgandan keyin barcha sessiyalar bekor qilinadi.
        self.db.upd("DELETE FROM sessions_ring WHERE user_id=?", (int(uid),))
        audit(self.db, self.user["id"], action_type="user_password_reset", target_type="users",
              target_id=int(uid),
              description="%s: %s uchun yangi parol o'rnatildi" % (user_name(self.user), u["login"]))
        # MODUL 5: parol endi DOIMIY saqlanadi — admin 🔑 orqali ko'ra,
        # shu bilan birga login+parolni o'zgartira ham oladi.
        return OK, {"ok": True, "login": u["login"], "password": newpass,
                    "password_format": "usrP_<14 random>" if not custom else "custom",
                    "stored_encrypted": bool(encrypt_par(newpass))}

    # ====================================================================
    # MODUL 5 — ADMIN: LOGIN VA PAROLNI KO'RISH / BIRGA O'ZGARTIRISH
    #
    # Talab: "admin har bir foydalanuvchining login va parolini ko'ra olsin
    # va xohlagancha o'zgartira olsin". Buning uchun parol `password_enc`
    # (AES-256-GCM, `app/auth.py`) sifatida QAYTARIB OCHILADIGAN saqlanadi.
    #
    # HIMOYALAR:
    #   * RBAC — faqat `admin` (talaba/instruktor 403 oladi).
    #   * OQILISH (GET) ham auditga yoziladi: kim, qachon, qaysi foydalanuvchi
    #     parolini ko'rdi. Bu maxfiy ma'lumot — iz qolishi SHART.
    #   * `password_enc` hech qanday ro'yxat/profil javobida chiqmaydi
    #     (`user_public` uni filtrlab qo'yadi).
    #   * Kalit/kutubxona yo'q bo'lsa `can_view: false` + `reason` qaytariladi —
    #     platforma qolgan qismi ishlayveradi, frontend aniq xabar ko'rsatadi.
    #   * O'zgartirish: `login` va `password` bir so'rovda yuboriladi.
    #     Bo'sh qiymat = "o'zgartirma" (maʼlumot O'Z-O'ZINI qayta yozilmaydi —
    #     aynan "agar admin o'zi almashtirsa, o'zgarishsiz saqlansin" talabi).
    # ====================================================================

    def admin_user_credentials_get(self, uid):
        """`GET /api/admin/users/{id}/credentials` — login + parolni ko'rish."""
        self._require("admin")
        try:
            uid = int(uid)
        except (TypeError, ValueError):
            return BAD, err("user.not_found")
        # Arxivlangan foydalanuvchilarning credential'i ham ko'rinadi —
        # admin arxivni ko'rib chiqayotgani mantiqan to'g'ri. Faqat o'zini
        # bloklashga yo'l qo'yilmaydi (o'shandan keyin `active` emas).
        u = self.db.q1("SELECT id,first_name,last_name,login,role,status,password_enc"
                       " FROM users WHERE id=?", (uid,))
        if not u:
            return NOTFOUND, err("user.not_found")
        pw = decrypt_secret(u["password_enc"])
        audit(self.db, self.user["id"], action_type="user_credentials_viewed",
              target_type="users", target_id=uid,
              description="%s: %s (%s) login/parolini ko'rib chiqdi" % (
                  user_name(self.user), u["login"], user_name(u)))
        # `reason` — frontend aniq, tushunarli xabar ko'rsatsin:
        #   none     — parol ko'rinadi (shifrlangan nusxa bor)
        #   crypto   — kalit yoki `cryptography` yo'q: funksiya o'chirilgan
        #   legacy   — foydalanuvchi eski modelda yaratilgan, `password_enc` yo'q
        if pw is not None:
            reason = "none"
        elif not credentials_crypto_available():
            reason = "crypto"
        else:
            reason = "legacy"
        return OK, {
            "ok": True,
            "id": u["id"],
            "name": user_name(u),
            "role": u["role"],
            "status": u["status"],
            "login": u["login"],
            "password": pw,
            # False = parolni KO'RISH mumkin emas. Sabab `reason` da.
            "can_view": pw is not None,
            "reason": reason,
        }

    def admin_user_credentials_set(self, uid, body):
        """`PUT /api/admin/users/{id}/credentials` — login va/yoki parolni
        BIR VAQTDA o'zgartirish.

        Tanlanmagan maydon (yoki bo'sh satr) — O'ZGARTIRILMAYDI.
        """
        self._require("admin")
        try:
            uid = int(uid)
        except (TypeError, ValueError):
            return BAD, err("user.not_found")
        u = self.db.q1("SELECT * FROM users WHERE id=?", (uid,))
        if not u:
            return NOTFOUND, err("user.not_found")

        body = body or {}
        new_login = str(body.get("login", "") or "").strip()
        # Parol uchun `strip()` QILINMAYDI (parolda bo'shliq bo'lishi mumkin),
        # lekin FAQAT bo'shliqdan iborat qiymat "kiritilmagan" hisoblanadi —
        # aks holda `"   "` kuchsiz parol sifatida rad etilardi, holbuki
        # foydalanuvchi shunchaki maydonga tegmagan.
        new_pass = str(body.get("password", "") or "")
        if not new_pass.strip():
            new_pass = ""
        # "generate" — parol maydoniga shu so'z yozilsa, avtomatik generatsiya.
        if new_pass.lower() in ("generate", "auto", "auto-generate"):
            new_pass = ""
            wants_gen = True
        else:
            wants_gen = bool(body.get("generate_password"))

        if not new_login and not new_pass and not wants_gen:
            # Hech narsa o'zgartirilmadi — BU NORMAL. "Agar admin o'zi
            # almashtirsa, o'zgarishsiz yangi bazaga saqlansin" talabi:
            # bo'sh so'rov hech qanday yozuv QILMAYDI (faqat o'zgarish
            # bo'lmagani bildiriladi) — eski qiymat buzilmaydi.
            return OK, {"ok": True, "changed": False, "login": u["login"],
                        "password_changed": False,
                        "note": "nothing_changed"}

        sets, params, changed = [], [], []

        if new_login and new_login != u["login"]:
            if not is_valid_login(new_login):
                return BAD, err("profile.login_format")
            # Arxivlangan login ham qayta ishlatilmasin (`deleted_at` filtrisiz).
            if self.db.q1("SELECT id FROM users WHERE login=? AND id!=?", (new_login, uid)):
                return BAD, err("profile.login_taken")
            sets.append("login=?")
            params.append(new_login)
            changed.append("login")

        if new_pass or wants_gen:
            # Parol BIR O'ZGARMI yoki yo'qmi — avval aniqlanadi. Bu belgi
            # orqali "faqat login o'zgardi" holati ham, "forma o'zgartirilmay
            # yuborilgan" holat ham to'g'ri ishlaydi.
            pw_unchanged = False
            if not new_pass:
                new_pass = self.db.transaction(lambda c: generate_credentials(c)[1])
            else:
                strength = password_strength_errors(new_pass)
                if strength:
                    return BAD, err("auth.password_weak", {"errors": strength})
                # MODUL 5: eski foydalanuvchining parolini BIRIKTIRISH.
                # `password_enc` yo'q bo'lgan (eski model) foydalanuvchida
                # admin parolni KO'RA OLMAYDI. Bu yerda admin o'z bilgan
                # parolni tasdiqlaydi -> u tekshiriladi va SHIFRLANGAN nusxasi
                # biriktiriladi. `password_hash` O'ZGARMAYDI, sessiyalar
                # bekor qilinMAYdi (parol o'zgarmagan).
                if verify_password(new_pass, u["password_hash"]):
                    if not (u["password_enc"] or "").strip():
                        self.db.upd("UPDATE users SET password_enc=?, updated_at=? WHERE id=?",
                                    (encrypt_par(new_pass), now(), uid))
                        audit(self.db, self.user["id"], action_type="user_credentials_attached",
                              target_type="users", target_id=uid,
                              description="%s: %s uchun parol shifrlangan nusxaga biriktirildi"
                                          % (user_name(self.user), u["login"]))
                        return OK, {"ok": True, "changed": False, "attached": True,
                                    "login": u["login"], "password_changed": False,
                                    "note": "attached"}
                    # Parol allaqachon SHUNDAY va shifrlangan nusxa ham bor.
                    # Bu XATO EMAS: forma o'zgartirilmay qayta yuborilgan
                    # bo'lishi mumkin ("agar admin o'zi almashtirsa,
                    # o'zgarishsiz saqlansin" talabi). Parolga tegilMAYdi.
                    pw_unchanged = True

            if not pw_unchanged:
                # `used_credentials`: ilgari ishlatilgan parol qaytarilmaydi.
                # Faqat ADMIN qo'lda belgilagan parol uchun tekshiriladi
                # (avtomatik generatsiya allaqachon unique).
                if not wants_gen:
                    pd = credential_digest(new_pass)
                    if self.db.q1("SELECT 1 FROM used_credentials WHERE password_digest=?", (pd,)):
                        return BAD, err("auth.password_used")
                    self.db.transaction(lambda c: c.execute(
                        "INSERT INTO used_credentials(login_digest, password_digest, created_at)"
                        " VALUES(?,?,?)",
                        (credential_digest("admin_set:%d:%s" % (uid, new_pass)), pd, now())))
                sets += ["password_hash=?", "password_enc=?", "must_change_password=0"]
                params.append(hash_password(new_pass))
                params.append(encrypt_par(new_pass))
                changed.append("password")

        if not changed:
            # Hech narsa O'ZGARMADI (forma o'zgartirilmay yuborilgan yoki
            # parol shundayligi aniqlandi). Yozuv QILINMAYDI: hash,
            # `must_change_password`, sessiyalar va `updated_at` o'zgarmaydi.
            return OK, {"ok": True, "changed": False, "password_changed": False,
                        "login": u["login"], "what": [], "note": "nothing_changed"}

        sets.append("updated_at=?")
        params.append(now())
        params.append(uid)
        self.db.upd("UPDATE users SET " + ", ".join(sets) + " WHERE id=?", params)

        # Parol o'zgarsa — barcha sessiyalar bekor qilinadi.
        if "password" in changed:
            self.db.upd("DELETE FROM sessions_ring WHERE user_id=?", (uid,))

        audit(self.db, self.user["id"], action_type="user_credentials_changed",
              target_type="users", target_id=uid,
              description="%s: %s uchun o'zgartirildi [%s]" % (
                  user_name(self.user), u["login"], "+".join(changed)))
        return OK, {"ok": True, "changed": True, "what": changed,
                    "login": new_login if "login" in changed else u["login"],
                    "password_changed": "password" in changed,
                    # Yangi parol admin o'ziga qaytariladi — shunda u uni
                    # foydalanuvchiga berishi mumkin.
                    "password": new_pass if "password" in changed else None}

    # ---- BAND 3: jami mashg'ulotlar sonini o'zgartirish ----
    def _student_progress(self, student_id: int) -> dict:
        """Talabaning progress hisobi: {done, total, target, remaining, pct}."""
        row = self.db.q1(
            """SELECT COUNT(*) AS total,
                      SUM(CASE WHEN ls.status='completed' THEN 1 ELSE 0 END) AS done
               FROM session_students ss JOIN lesson_sessions ls ON ls.id=ss.session_id
               WHERE ss.student_id=? AND ss.student_status='active' AND ls.status!='cancelled'""",
            (student_id,),
        )
        done = int(row["done"] or 0)
        st = self.db.q1("SELECT total_lessons_target FROM students WHERE id=?", (student_id,))
        own = (st["total_lessons_target"] if st else None)
        group = DEFAULT_PLATFORM_SETTINGS["total_lessons_target"]
        target = int(own) if own else group
        return {
            "done": done,
            "sessions": int(row["total"] or 0),
            "target": target,
            "individual_target": int(own) if own else None,
            "group_target": group,
            "mode": "individual" if own else "group",
            "remaining": max(0, target - done),
            "pct": round(done * 100 / target) if target else 0,
        }

    @staticmethod
    def _coerce_total(value):
        """`total_lessons` qiymatini butun songa aylantiradi.

        QAT'IY: `12.5`, `"12.5"`, `"12abc"`, `True`, bo'sh bo'lmagan `[]` va
        h.k. — RAD etiladi (`None` qaytariladi). Aks holda `int()` butunlikka
        kesib tashlab ("12.5" -> 12) xato ma'lumot saqlanardi.
        `None`/" " -> `None` (= platforma umumiy qiymatiga qaytarish).
        """
        if value is None:
            return None
        if isinstance(value, bool):
            return -1                      # True/False — mantiqiy emas
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value) if value.is_integer() else -1
        if isinstance(value, str):
            s = value.strip()
            if not s:
                return None
            try:
                return int(s)
            except ValueError:
                return -1
        return -1                          # list/dict/None-turlari

    def _set_total_lessons(self, student_id: int, value) -> dict:
        """Bitta talabaning jami darslar sonini o'zgartiradi (yoki umumiyga
        qaytaradi). `value` bo'sh/None -> individual maqsad olib tashlanadi.

        VALIDATSIYA (BAND 3): yangi jami < BAJARILGAN bo'lsa — RAD etiladi
        ("Yangi darslar soni bajarilgan darslardan kam bo'lishi mumkin emas").
        Bajarilgan mashg'ulotlar, tarix va booking O'CHIRILMAYDI.
        """
        st = self.db.q1("SELECT user_id FROM students WHERE id=?", (student_id,))
        if not st:
            return {"error": "user.not_found"}
        pr = self._student_progress(student_id)
        if value is None or (isinstance(value, str) and not value.strip()):
            self.db.upd("UPDATE students SET total_lessons_target=NULL WHERE id=?", (student_id,))
            return {"ok": True, "mode": "group", "progress": self._student_progress(student_id)}
        n = self._coerce_total(value)
        if n is None or n < 1 or n > 999:
            return {"error": "user.bad_total_lessons"}
        if n < pr["done"]:
            # BAND 3: yangi jami bajarilgan dan kam bo'lsa — qabul qilinmaydi.
            return {"error": "user.total_lessons_below_done", "done": pr["done"], "min": pr["done"]}
        self.db.upd("UPDATE students SET total_lessons_target=? WHERE id=?", (n, student_id))
        return {"ok": True, "mode": "individual", "progress": self._student_progress(student_id)}

    def admin_user_total_lessons(self, body):
        """`POST /api/admin/users/total-lessons` — JUMLI mashg'ulotlar soni.

        `scope`: "user" (bitta talaba) | "all" (barcha talabalar)
        `user_id`: scope="user" uchun (users.id)
        `total_lessons`: 1..999, yoki bo'sh/null -> platforma umumiy qiymatiga
                          qaytarish (individual maqsad tozalanadi).
        """
        self._require("admin")
        scope = str(body.get("scope", "user")).strip()
        if scope == "all":
            rows = self.db.q("SELECT id FROM students")
            value = body.get("total_lessons")
            # Ommaviy rejimda ham validatsiya: eng ko'p bajarilgan talabaga
            # qarshi tekshiriladi — aks holda progress manfiy bo'lib ketadi.
            if value is not None and str(value).strip() != "":
                n = self._coerce_total(value)
                if n is None or n < 1 or n > 999:
                    return BAD, err("user.bad_total_lessons")
                max_done = max([self._student_progress(r["id"])["done"] for r in rows] or [0])
                if n < max_done:
                    return BAD, err("user.total_lessons_below_done", {"done": max_done, "min": max_done})
                value = n
            updated, skipped, errors = 0, 0, []
            for r in rows:
                if value is None:
                    self.db.upd("UPDATE students SET total_lessons_target=NULL WHERE id=?", (r["id"],))
                    skipped += 1
                    continue
                res = self._set_total_lessons(r["id"], value)
                if res.get("error"):
                    errors.append({"student_id": r["id"], "error": res["error"]})
                else:
                    updated += 1
            audit(self.db, self.user["id"], "total_lessons bulk", "students", None,
                  {"scope": "all", "total": value, "updated": updated, "skipped": skipped})
            return OK, {"ok": True, "scope": "all", "updated": updated,
                        "cleared": skipped, "errors": errors}
        uid = body.get("user_id")
        if not uid:
            return BAD, err("bad_request")
        u = self.db.q1("SELECT id, role FROM users WHERE id=? AND deleted_at IS NULL", (int(uid),))
        if not u:
            return NOTFOUND, err("user.not_found")
        if u["role"] != "student":
            return BAD, err("user.not_a_student")
        st = self.db.q1("SELECT id FROM students WHERE user_id=?", (u["id"],))
        if not st:
            return NOTFOUND, err("user.not_found")
        res = self._set_total_lessons(st["id"], body.get("total_lessons"))
        if res.get("error"):
            # faqat MAVJUD parametrlarni yubaramiz (frontend `None` ko'rmasin)
            _p = {k: v for k, v in (("done", res.get("done")),
                                    ("min", res.get("min"))) if v is not None}
            return BAD, err(res["error"], _p)
        audit(self.db, self.user["id"], "total_lessons set", "students", st["id"],
              {"total_lessons": body.get("total_lessons"), "mode": res["mode"]})
        return OK, {"ok": True, "scope": "user", "user_id": u["id"],
                    "mode": res["mode"], "progress": res["progress"]}

    # ---- BAND 22: admin uchun foydalanuvchi profili ----
    def admin_user_profile(self, uid):
        """`GET /api/admin/users/{id}` — bitta foydalanuvchi to'liq profili.

        Talaba, login, telefon, guruh, haydovchilik toifasi, jami darslar,
        bajarilgan, qolgan, progress. BAND 16: `enrolled_at` shu yerda
        KO'RSATILADI (faqat admin uchun).
        """
        self._require("admin")
        uid = int(uid)
        # MODUL 2.3/3.3: arxivlangan foydalanuvchi profili ham ko'rinishi
        # kerak (ma'lumotlari saqlangan) — faqat jadvaldan "o'chirilgan"
        # deb qarilganlar (`deleted_at` to'ldirilgan va arxivlanmagan) chiqariladi.
        u = self.db.q1("SELECT * FROM users WHERE id=?", (uid,))
        if not u:
            return NOTFOUND, err("user.not_found")
        out = user_public(u)
        # Parol HECH QACHON shu yerda qaytarilmaydi (BAND 6). MODUL 5: admin
        # faqat `GET .../credentials` orqali ko'radi — bu alohida so'rov va
        # auditga yoziladi. `can_view_password` faqat "ko'rsatish mumkinmi"
        # degan OCHIQ boolean (parolning O'zi EMAS).
        out.pop("must_change_password", None)
        out["has_password"] = bool(u["password_hash"])
        out["can_view_password"] = bool(decrypt_secret(u["password_enc"]))
        progress = None
        if u["role"] == "student":
            st = self.db.q1("SELECT * FROM students WHERE user_id=?", (uid,))
            out["student"] = st          # `enrolled_at` shu yerda (faqat admin)
            if st:
                progress = self._student_progress(st["id"])
                out["instructors"] = [
                    {"id": p["id"], "name": p["name"]}
                    for p in self.db.q(
                        """SELECT DISTINCT i.id AS id, us.first_name||' '||us.last_name AS name
                           FROM session_students ss JOIN lesson_sessions ls ON ls.id=ss.session_id
                           JOIN instructors i ON i.id=ls.instructor_id JOIN users us ON us.id=i.user_id
                           WHERE ss.student_id=? AND ss.student_status='active'""", (st["id"],))
                ]
        elif u["role"] == "instructor":
            inst = self.db.q1("SELECT * FROM instructors WHERE user_id=?", (uid,))
            out["instructor"] = inst
            if inst and inst["assigned_car_id"]:
                out["car"] = self.db.q1(
                    "SELECT id, brand, model, plate_number, status FROM cars WHERE id=?",
                    (inst["assigned_car_id"],))
            out["students_count"] = self.db.q1(
                """SELECT COUNT(DISTINCT ss.student_id) c FROM lesson_sessions ls
                   JOIN session_students ss ON ss.session_id=ls.id
                   WHERE ls.instructor_id=? AND ss.student_status='active'""",
                (inst["id"],))["c"] if inst else 0
        out["progress"] = progress
        return OK, {"ok": True, "user": out}

    def admin_user_delete(self, uid):
        """Soft delete — tarix buzilmaydi."""
        self._require("admin")
        u = self.db.q1("SELECT * FROM users WHERE id=? AND deleted_at IS NULL", (int(uid),))
        if not u:
            return NOTFOUND, err("user.not_found")
        if u["role"] in ("admin",):
            return BAD, err("user.cannot_modify_admin")
        self.db.upd("UPDATE users SET deleted_at=?, status='archived', updated_at=? WHERE id=?", (now(), now(), int(uid)))
        self.db.upd("DELETE FROM sessions_ring WHERE user_id=?", (int(uid),))
        audit(self.db, self.user["id"], "user deleted (soft)", "users", int(uid))
        return OK, {"ok": True}

    # ---- cars
    def admin_cars(self, query):
        self._require("admin")
        where = ["deleted_at IS NULL"]
        params = []
        if query.get("status"):
            where.append("status=?")
            params.append(query["status"])
        if query.get("q"):
            where.append("(plate_number LIKE ? OR brand LIKE ? OR model LIKE ?)")
            p = "%" + query["q"] + "%"
            params += [p, p, p]
        rows = self.db.q("SELECT * FROM cars WHERE " + " AND ".join(where) + " ORDER BY id DESC", params)
        assign = {}
        for r in rows:
            i_ = self.db.q1("SELECT i.id, u.first_name, u.last_name FROM instructors i JOIN users u ON u.id=i.user_id WHERE i.assigned_car_id=?", (r["id"],))
            assign[r["id"]] = f"{i_['first_name']} {i_['last_name']}" if i_ else None
        photos = self._car_photos_map([r["id"] for r in rows])
        return OK, {"ok": True, "cars": rows, "assigned_to": assign, "photos": photos}

    def _car_photos_map(self, car_ids):
        """[{'id','path'}, ...] ro'yxatlarini car_id bo'yicha qaytaradi."""
        if not car_ids:
            return {}
        marks = ",".join("?" * len(car_ids))
        pr = self.db.q(f"SELECT id, car_id, path FROM car_photos WHERE car_id IN ({marks}) ORDER BY position ASC, id ASC", car_ids)
        out = {}
        for p in pr:
            out.setdefault(p["car_id"], []).append({"id": p["id"], "path": p["path"]})
        return out

    def admin_car_photos_add(self, body, cid):
        self._require("admin")
        car = self.db.q1("SELECT id FROM cars WHERE id=? AND deleted_at IS NULL", (int(cid),))
        if not car:
            return NOTFOUND, err("car.not_found")
        cnt = self.db.q1("SELECT COUNT(*) c FROM car_photos WHERE car_id=?", (int(cid),))["c"]
        if cnt >= MAX_CAR_PHOTOS:
            return CONFLICT, err("car.photo_limit")
        data_url = str(body.get("image", ""))
        try:
            path, _full = save_data_url_image(data_url, "cars", "c%d_" % int(cid))
        except ValueError as ve:
            return BAD, err(str(ve))
        pid = self.db.ex(
            "INSERT INTO car_photos(car_id, path, position, created_at) VALUES(?,?,?,?)",
            (int(cid), path, cnt, now()),
        )
        audit(self.db, self.user["id"], "car.photo_add", "cars", int(cid), {"photo_id": pid})
        return OK, {"ok": True, "id": pid, "path": path}

    def admin_car_photos_remove(self, cid, pid):
        self._require("admin")
        photo = self.db.q1("SELECT * FROM car_photos WHERE id=? AND car_id=?", (int(pid), int(cid)))
        if not photo:
            return NOTFOUND, err("car.photo_not_found")
        self.db.upd("DELETE FROM car_photos WHERE id=?", (int(pid),))
        if photo["path"].startswith("/uploads/cars/"):
            try:
                os.remove(os.path.join(upload_dir("cars"), os.path.basename(photo["path"])))
            except OSError:
                pass
        audit(self.db, self.user["id"], "car.photo_remove", "cars", int(cid), {"photo_id": int(pid)})
        return OK, {"ok": True}

    def admin_cars_status(self, body, cid):
        """Tezkor status almashtirish: active/repair/checkup/inactive."""
        self._require("admin")
        car = self.db.q1("SELECT * FROM cars WHERE id=? AND deleted_at IS NULL", (int(cid),))
        if not car:
            return NOTFOUND, err("car.not_found")
        st = str(body.get("status", "")).strip()
        if st not in ("active", "repair", "checkup", "inactive"):
            return BAD, err("car.bad_status")
        if car["status"] == st:
            return OK, {"ok": True, "status": st}
        self.db.upd("UPDATE cars SET status=?, updated_at=? WHERE id=?", (st, now(), int(cid)))
        audit(self.db, self.user["id"], "car.status_changed", "cars", int(cid),
              {"old": car["status"], "new": st})
        return OK, {"ok": True, "status": st}

    def admin_cars_create(self, body):
        self._require("admin")
        plate = str(body.get("plate_number", "")).strip().upper()
        if not re.match(r"^[0-9A-ZА-ЯЁUZ \-]{4,12}$", plate):
            return BAD, err("car.bad_plate")
        if self.db.q1("SELECT id FROM cars WHERE plate_number=? AND deleted_at IS NULL", (plate,)):
            return CONFLICT, err("car.plate_exists")
        capacity = int(body.get("practice_capacity") or 4)
        if capacity < 1 or capacity > 20:
            return BAD, err("car.bad_capacity")
        cid = self.db.ex(
            """INSERT INTO cars(brand_id, model_id, custom_model_name, brand, model, plate_number, year, color,
                                seat_count, practice_capacity, status, technical_inspection_date,
                                insurance_expiry, notes, created_at, updated_at)
               VALUES(NULL,NULL,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (str(body.get("custom_model_name", "")).strip(), str(body.get("brand", "")).strip(),
             str(body.get("model", "")).strip(), plate, int(body.get("year") or 0),
             str(body.get("color", "")).strip(), int(body.get("seat_count") or 4), capacity,
             str(body.get("status", "active")), str(body.get("technical_inspection_date", "")).strip(),
             str(body.get("insurance_expiry", "")).strip(), str(body.get("notes", "")).strip(), now(), now()),
        )
        audit(self.db, self.user["id"], "car created", "cars", cid, {"plate": plate, "capacity": capacity})
        return OK, {"ok": True, "id": cid}

    def admin_cars_update(self, body, cid):
        self._require("admin")
        car = self.db.q1("SELECT * FROM cars WHERE id=? AND deleted_at IS NULL", (int(cid),))
        if not car:
            return NOTFOUND, err("car.not_found")
        upd = {}
        if "plate_number" in body:
            plate = str(body["plate_number"]).strip().upper()
            if self.db.q1("SELECT id FROM cars WHERE plate_number=? AND id!=? AND deleted_at IS NULL", (plate, int(cid))):
                return CONFLICT, err("car.plate_exists")
            upd["plate_number"] = plate
        if "brand" in body: upd["brand"] = str(body["brand"]).strip()
        if "model" in body: upd["model"] = str(body["model"]).strip()
        if "custom_model_name" in body: upd["custom_model_name"] = str(body["custom_model_name"]).strip()
        if "year" in body: upd["year"] = int(body["year"] or 0)
        if "color" in body: upd["color"] = str(body["color"]).strip()
        if "seat_count" in body: upd["seat_count"] = int(body["seat_count"] or 4)
        if "practice_capacity" in body:
            cap = int(body["practice_capacity"])
            if cap < 1 or cap > 20:
                return BAD, err("car.bad_capacity")
            upd["practice_capacity"] = cap
        if "technical_inspection_date" in body: upd["technical_inspection_date"] = str(body["technical_inspection_date"]).strip()
        if "insurance_expiry" in body: upd["insurance_expiry"] = str(body["insurance_expiry"]).strip()
        if "status" in body:
            if body["status"] not in ("active", "repair", "checkup", "inactive"):
                return BAD, err("car.bad_status")
            upd["status"] = body["status"]
        if "notes" in body: upd["notes"] = str(body["notes"]).strip()
        if upd:
            upd["updated_at"] = now()
            self.db.upd("UPDATE cars SET " + ", ".join(f"{k}=?" for k in upd) + " WHERE id=?",
                        (*upd.values(), int(cid)))
        audit(self.db, self.user["id"], "car updated", "cars", int(cid), upd)
        return OK, {"ok": True}

    def admin_cars_delete(self, cid):
        self._require("admin")
        car = self.db.q1("SELECT * FROM cars WHERE id=? AND deleted_at IS NULL", (int(cid),))
        if not car:
            return NOTFOUND, err("car.not_found")
        inst = self.db.q1("SELECT id FROM instructors WHERE assigned_car_id=?", (int(cid),))
        if inst:
            return CONFLICT, err("car.assigned")
        self.db.upd("UPDATE cars SET deleted_at=?, status='inactive', updated_at=? WHERE id=?", (now(), now(), int(cid)))
        audit(self.db, self.user["id"], "car deleted (soft)", "cars", int(cid))
        return OK, {"ok": True}

    def admin_instructor_assign_car(self, body, iid):
        self._require("admin")
        inst = self.db.q1("SELECT * FROM instructors WHERE id=?", (int(iid),))
        u = self.db.q1("SELECT * FROM users WHERE id=? AND deleted_at IS NULL", (inst["user_id"],)) if inst else None
        if not inst or not u:
            return NOTFOUND, err("user.not_found")
        old_car = inst["assigned_car_id"]
        car_id = body.get("car_id")
        if car_id:
            car = self.db.q1("SELECT * FROM cars WHERE id=? AND deleted_at IS NULL", (int(car_id),))
            if not car:
                return NOTFOUND, err("car.not_found")
            # boshqa instruktorga biriktirilgan bo'lsa — oldingisidan yechiladi
            self.db.upd("UPDATE instructors SET assigned_car_id=NULL WHERE assigned_car_id=? AND id!=?", (int(car_id), int(iid)))
            self.db.upd("UPDATE instructors SET assigned_car_id=? WHERE id=?", (int(car_id), int(iid)))
        else:
            self.db.upd("UPDATE instructors SET assigned_car_id=NULL WHERE id=?", (int(iid),))
        new_car = car if car_id else None
        car_info = {
            "old": self.db.q1("SELECT id, brand, model, plate_number FROM cars WHERE id=?", (old_car,)) if old_car else None,
            "new": {"id": new_car["id"], "brand": new_car["brand"], "model": new_car["model"], "plate_number": new_car["plate_number"]} if new_car else None,
        }
        audit(self.db, self.user["id"], "car assigned", "instructors", int(iid), car_info)
        # Eslatma: eski sessiyalar eski avtomobil bilan tarixda qoladi (capacity_snapshot, car_name_snapshot saqlanadi)
        return OK, {"ok": True, "car": car_info["new"]}

    # ---- sessions
    def admin_sessions(self, query):
        self._require("admin")
        where = []
        params = []
        if query.get("date"):
            where.append("ls.date=?")
            params.append(query["date"])
        if query.get("instructor_id"):
            where.append("ls.instructor_id=?")
            params.append(int(query["instructor_id"]))
        if query.get("status"):
            where.append("ls.status=?")
            params.append(query["status"])
        if query.get("from") and query.get("to"):
            where.append("ls.date BETWEEN ? AND ?")
            params += [query["from"], query["to"]]
        if query.get("q"):
            where.append("(ls.car_name_snapshot LIKE ? OR ls.car_plate_snapshot LIKE ? OR u.first_name LIKE ? OR u.last_name LIKE ?)")
            p = "%" + query["q"] + "%"
            params += [p, p, p, p]
        rows = self.db.q(
            """SELECT ls.*, u.first_name||' '||u.last_name AS instructor_name, u.phone AS instructor_phone,
                      (SELECT COUNT(*) FROM session_students ss WHERE ss.session_id=ls.id AND ss.student_status='active') AS student_count
               FROM lesson_sessions ls JOIN instructors i ON i.id=ls.instructor_id
               JOIN users u ON u.id=i.user_id
               WHERE """ + (" AND ".join(where) if where else "1=1") +
            " ORDER BY ls.date DESC, ls.start_time DESC LIMIT 500", params)
        return OK, {"ok": True, "sessions": rows}

    def admin_session_detail(self, sid):
        self._require("admin")
        row = self.db.q1(
            """SELECT ls.*, u.first_name||' '||u.last_name AS instructor_name, u.phone AS instructor_phone,
                      (SELECT COUNT(*) FROM session_students WHERE session_id=ls.id AND student_status='active') AS student_count
               FROM lesson_sessions ls JOIN instructors i ON i.id=ls.instructor_id
               JOIN users u ON u.id=i.user_id WHERE ls.id=?""", (int(sid),))
        if not row:
            return NOTFOUND, err("session.not_found")
        row["students"] = self.db.q(
            """SELECT ss.*, u.id AS user_id, u.first_name, u.last_name, u.middle_name, u.phone,
                      s.group_name, s.license_category
               FROM session_students ss JOIN students s ON s.id=ss.student_id
               JOIN users u ON u.id=s.user_id
               WHERE ss.session_id=? ORDER BY ss.joined_at""", (int(sid),))
        return OK, {"ok": True, "session": row}

    def admin_session_create(self, body):
        self._require("admin")
        date = str(body.get("date", "")).strip()
        start = str(body.get("start_time", "")).strip()
        end = str(body.get("end_time", "")).strip()
        instructor_id = int(body.get("instructor_id") or 0)
        student_ids = body.get("student_ids") or []
        note = str(body.get("notes", "")).strip()

        # M12: end_time berilmagan bo'lsa — platforma standarti (lesson_duration_min)
        if not end and start:
            dur = int(_platform_setting(self.db, "lesson_duration_min", 90) or 90)
            end = _add_minutes(start, dur)

        errors = check_session_rules(self.db, date, start, end, instructor_id, student_ids)
        if errors:
            return CONFLICT, err("session.rules_violated", {"errors": errors})
        auto = session_auto_data(self.db, instructor_id)
        if not auto:
            return CONFLICT, err("car_not_assigned")
        sid = self.db.ex(
            """INSERT INTO lesson_sessions(date,start_time,end_time,instructor_id,car_id,car_name_snapshot,
                                           car_plate_snapshot,capacity_snapshot,status,notes,created_at,updated_at)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
            (date, start, end, instructor_id, auto["car_id"], auto["car_name_snapshot"],
             auto["car_plate_snapshot"], auto["capacity_snapshot"], "scheduled", note, now(), now()),
        )
        for sid_student in student_ids:
            self.db.ex(
                """INSERT INTO session_students(session_id, student_id, pickup_address, pickup_lat, pickup_lng,
                                                attendance_status, student_status, joined_at, notes)
                   VALUES(?,?,?,?,?,?,?,?,?)""",
                (sid, int(sid_student), "", None, None, "unmarked", "active", now(), ""),
            )
        row = self.db.q1("SELECT * FROM lesson_sessions WHERE id=?", (sid,))
        notify_session_participants(self.db, row, "created", sender_id=self.user["id"], sender_role=self.user["role"])
        audit(self.db, self.user["id"], "session created", "lesson_sessions", sid,
              {"date": date, "start": start, "end": end, "instructor_id": instructor_id, "car_id": auto["car_id"]})
        return OK, {"ok": True, "id": sid,
                    "auto": {"car": auto["car_name_snapshot"], "plate": auto["car_plate_snapshot"],
                             "capacity": auto["capacity_snapshot"]}}

    def admin_session_add_student(self, body, sid):
        self._require("admin")
        row = self.db.q1("SELECT * FROM lesson_sessions WHERE id=? AND status IN ('scheduled','ongoing')", (int(sid),))
        if not row:
            return NOTFOUND, err("session.not_found")
        student_id = int(body.get("student_id") or 0)
        if self.db.q1("SELECT id FROM session_students WHERE session_id=? AND student_id=?", (int(sid), student_id)):
            return CONFLICT, err("session.duplicate_student")
        cur_count = self.db.q1(
            "SELECT COUNT(*) c FROM session_students WHERE session_id=? AND student_status='active'", (int(sid),))["c"]
        if cur_count >= row["capacity_snapshot"]:
            return CONFLICT, err("capacity_full")
        busy = self.db.q1(
            """SELECT ls.id FROM session_students ss JOIN lesson_sessions ls ON ls.id=ss.session_id
               WHERE ss.student_id=? AND ss.student_status='active' AND ls.status IN ('scheduled','ongoing')
                 AND ls.date=? AND (? < ls.end_time) AND (? > ls.start_time)""",
            (student_id, row["date"], row["start_time"], row["end_time"]))
        if busy:
            return CONFLICT, err("student_busy")
        self.db.ex(
            """INSERT INTO session_students(session_id, student_id, pickup_address, pickup_lat, pickup_lng,
                                            attendance_status, student_status, joined_at, notes)
               VALUES(?,?,?,?,?,?,?,?,?)""",
            (int(sid), student_id, str(body.get("pickup_address", "")).strip(),
             body.get("pickup_lat"), body.get("pickup_lng"), "unmarked", "active", now(),
             str(body.get("notes", "")).strip()),
        )
        audit(self.db, self.user["id"], "student added", "session_students", int(sid), {"student_id": student_id})
        return OK, {"ok": True}

    def admin_session_remove_student(self, sid, ssid):
        self._require("admin")
        ss = self.db.q1("SELECT * FROM session_students WHERE id=?", (int(ssid),))
        if not ss or ss["session_id"] != int(sid):
            return NOTFOUND, err("session.student_not_found")
        self.db.upd(
            "UPDATE session_students SET student_status='removed', removed_at=? WHERE id=?", (now(), int(ssid)))
        audit(self.db, self.user["id"], "student removed", "session_students", int(sid), {"student_id": ss["student_id"]})
        return OK, {"ok": True}

    def admin_session_update_student(self, body, sid, ssid):
        self._require("admin")
        ss = self.db.q1("SELECT * FROM session_students WHERE id=? AND session_id=?", (int(ssid), int(sid)))
        if not ss:
            return NOTFOUND, err("session.student_not_found")
        upd = {}
        if "pickup_address" in body: upd["pickup_address"] = str(body["pickup_address"]).strip()
        if "notes" in body: upd["notes"] = str(body["notes"]).strip()
        # Koordinatalar: xarita vaqtincha o'chirilgan, lekin ustunlar saqlangan.
        # Kelganda xarita qaytadi — shuning uchun validatsiya SAQLANADI va
        # `parse_coord` orqali bajariladi (avvalgi `float(...)` "abc" kabi
        # noto'g'ri qiymatda ValueError -> 500 xatosini berardi).
        has_lat = "pickup_lat" in body
        has_lng = "pickup_lng" in body
        if has_lat or has_lng:
            try:
                lat = parse_coord(body.get("pickup_lat"), "lat")
                lng = parse_coord(body.get("pickup_lng"), "lng")
            except ValueError as e:
                kind = e.args[0] if e.args else "lat"
                return BAD, err("coord.bad_" + kind)
            if (lat is None) != (lng is None):
                return BAD, err("coord.pair_incomplete")
            upd["pickup_lat"] = lat
            upd["pickup_lng"] = lng
        if upd:
            self.db.upd("UPDATE session_students SET " + ", ".join(f"{k}=?" for k in upd) + " WHERE id=?", (*upd.values(), int(ssid)))
        return OK, {"ok": True}

    def admin_session_move_student(self, body, sid):
        self._require("admin")
        ssid = int(body.get("session_student_id") or 0)
        to_sid = int(body.get("to_session_id") or 0)
        ss = self.db.q1("SELECT * FROM session_students WHERE id=? AND session_id=?", (ssid, int(sid)))
        if not ss:
            return NOTFOUND, err("session.student_not_found")
        target = self.db.q1("SELECT * FROM lesson_sessions WHERE id=?", (to_sid,))
        if not target:
            return BAD, err("session.not_found")
        cur_count = self.db.q1(
            "SELECT COUNT(*) c FROM session_students WHERE session_id=? AND student_status='active'", (to_sid,))["c"]
        if cur_count >= target["capacity_snapshot"]:
            return CONFLICT, err("capacity_full")
        if self.db.q1("SELECT id FROM session_students WHERE session_id=? AND student_id=?", (to_sid, ss["student_id"])):
            return CONFLICT, err("session.duplicate_student")
        busy = self.db.q1(
            """SELECT ls.id FROM session_students ss2 JOIN lesson_sessions ls ON ls.id=ss2.session_id
               WHERE ss2.student_id=? AND ss2.student_status='active' AND ls.status IN ('scheduled','ongoing')
                 AND ls.date=? AND (? < ls.end_time) AND (? > ls.start_time) AND ls.id!=?""",
            (ss["student_id"], target["date"], target["start_time"], target["end_time"], to_sid))
        if busy:
            return CONFLICT, err("student_busy")
        self.db.upd("UPDATE session_students SET student_status='removed', removed_at=? WHERE id=?", (now(), ssid))
        self.db.ex(
            """INSERT INTO session_students(session_id, student_id, pickup_address, pickup_lat, pickup_lng,
                                            attendance_status, student_status, joined_at, notes)
               VALUES(?,?,?,?,?,?,?,?,?)""",
            (to_sid, ss["student_id"], ss["pickup_address"], ss["pickup_lat"], ss["pickup_lng"],
             "unmarked", "active", now(), ss["notes"] or ""),
        )
        audit(self.db, self.user["id"], "student moved", "session_students", int(sid),
              {"student_id": ss["student_id"], "to_session": to_sid})
        return OK, {"ok": True}

    def admin_session_reschedule(self, body, sid):
        self._require("admin")
        row = self.db.q1("SELECT * FROM lesson_sessions WHERE id=?", (int(sid),))
        if not row:
            return NOTFOUND, err("session.not_found")
        date = str(body.get("date", row["date"])).strip()
        start = str(body.get("start_time", row["start_time"])).strip()
        end = str(body.get("end_time", row["end_time"])).strip()
        instructor_id = int(body.get("instructor_id") or row["instructor_id"])
        errors = check_session_rules(self.db, date, start, end, instructor_id,
                                     [r["student_id"] for r in self.db.q(
                                         "SELECT student_id FROM session_students WHERE session_id=? AND student_status='active'",
                                         (int(sid),))],
                                     exclude_session_id=int(sid))
        if errors:
            return CONFLICT, err("session.rules_violated", {"errors": errors})
        auto = session_auto_data(self.db, instructor_id) or {}
        # original_* faqat birinchi ko'chirishda saqlanadi (SET tartibi: RHS eski qiymatni o'qiydi)
        self.db.upd(
            """UPDATE lesson_sessions SET
                 original_date=CASE WHEN original_date='' THEN date ELSE original_date END,
                 original_start_time=CASE WHEN original_start_time='' THEN start_time ELSE original_start_time END,
                 original_end_time=CASE WHEN original_end_time='' THEN end_time ELSE original_end_time END,
                 original_instructor_id=CASE WHEN original_instructor_id IS NULL THEN instructor_id ELSE original_instructor_id END,
                 date=?, start_time=?, end_time=?, instructor_id=?,
                 car_id=COALESCE(?,car_id), car_name_snapshot=COALESCE(?,car_name_snapshot),
                 car_plate_snapshot=COALESCE(?,car_plate_snapshot),
                 capacity_snapshot=COALESCE(?,capacity_snapshot),
                 status='scheduled', updated_at=?
                 WHERE id=?""",
            (date, start, end, instructor_id, auto.get("car_id"), auto.get("car_name_snapshot"),
             auto.get("car_plate_snapshot"), auto.get("capacity_snapshot"), now(), int(sid)),
        )
        newrow = self.db.q1("SELECT * FROM lesson_sessions WHERE id=?", (int(sid),))
        # BAND 9: vaqt o'zgarganda ESLATMA QAYTA HISOBLANADI — eski (noto'g'ri)
        # eslatma o'chiriladi, shunda yangi vaqt uchun yangi eslatma yuborilishi
        # mumkin bo'ladi. Aks holda eski eslatma qolib, yangisi yuborilmasligi
        # (yoki ikkalasi birga chiqishi) mumkin edi.
        clear_lesson_reminders(self.db, int(sid))
        notify_session_participants(self.db, newrow, "rescheduled", sender_id=self.user["id"], sender_role=self.user["role"])
        audit(self.db, self.user["id"], "session rescheduled", "lesson_sessions", int(sid),
              {"date": date, "start": start, "end": end, "instructor_id": instructor_id})
        return OK, {"ok": True, "session": newrow}

    def admin_session_cancel(self, body, sid):
        self._require("admin")
        row = self.db.q1("SELECT * FROM lesson_sessions WHERE id=?", (int(sid),))
        if not row:
            return NOTFOUND, err("session.not_found")
        reason = str(body.get("reason", "")).strip()
        self.db.upd(
            "UPDATE lesson_sessions SET status='cancelled', cancel_reason=?, updated_at=? WHERE id=?",
            (reason, now(), int(sid)))
        # BAND 9: bekor qilingan mashg'ulotga eslatma yuborilmaydi — avval
        # yuborilgan eslatma ham o'chiriladi (noto'g'ri xabar qolmasin).
        clear_lesson_reminders(self.db, int(sid))
        notify_session_participants(self.db, row, "cancelled", sender_id=self.user["id"], sender_role=self.user["role"])
        audit(self.db, self.user["id"], "session cancelled", "lesson_sessions", int(sid), {"reason": reason})
        return OK, {"ok": True}

    def admin_session_notes(self, body, sid):
        self._require("admin")
        self.db.upd("UPDATE lesson_sessions SET notes=?, updated_at=? WHERE id=?",
                    (str(body.get("notes", "")).strip(), now(), int(sid)))
        return OK, {"ok": True}

    def admin_calendar(self, query):
        self._require("admin")
        view = query.get("view", "week")
        date = query.get("date") or today()
        from datetime import datetime, timedelta
        try:
            anchor = datetime.strptime(date, "%Y-%m-%d")
        except Exception:
            anchor = datetime.now()
        if view == "day":
            start = anchor
            end = anchor + timedelta(days=1)
        elif view == "week":
            start = anchor - timedelta(days=anchor.weekday())
            end = start + timedelta(days=7)
        else:  # month
            start = anchor.replace(day=1)
            end = (start + timedelta(days=32)).replace(day=1)
        rows = self.db.q(
            """SELECT ls.id, ls.date, ls.start_time, ls.end_time, ls.status, ls.capacity_snapshot,
                      ls.car_name_snapshot, ls.car_plate_snapshot,
                      u.first_name||' '||u.last_name AS instructor_name,
                      (SELECT COUNT(*) FROM session_students ss WHERE ss.session_id=ls.id AND ss.student_status='active') AS student_count
               FROM lesson_sessions ls JOIN instructors i ON i.id=ls.instructor_id
               JOIN users u ON u.id=i.user_id
               WHERE ls.date>=? AND ls.date<? AND ls.status!='cancelled'
               ORDER BY ls.date, ls.start_time""",
            (start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")))
        return OK, {"ok": True, "view": view, "start": start.strftime("%Y-%m-%d"), "end": end.strftime("%Y-%m-%d"), "events": rows}

    # ---- requests
    REQUEST_SQL = (
        """SELECT r.*, u.first_name, u.last_name, u.phone, u.profile_image, s.group_name
           FROM practice_requests r JOIN students s ON s.id=r.student_id
           JOIN users u ON u.id=s.user_id """
    )

    def admin_requests(self, query):
        """`GET /api/admin/requests[?filter=active|expired|history]`

        MODUL 5: javob uchta bo'limga bo'linadi —
          * `active`  — hali dolzarb (kelajakdagi/bugungi sana, `pending`),
          * `expired` — mashg'ulot sanasi o'tib, 1 kun o'tgan `pending` so'rovlar,
          * `history` — tasdiqlangan / rad etilgan / bekor qilingan so'rovlar.

        Muhim: filtr `LIMIT` dan KEYIN qo'llanadi, ya'ni hech bir so'rov
        "yo'qolmaydi" — faqat boshqa bo'limga o'tadi (eski so'rovni id bo'yicha
        ochish uchun `GET /api/admin/requests/{id}` ishlating).
        """
        self._require("admin")
        rows = self.db.q(self.REQUEST_SQL +
                         "ORDER BY (r.status='pending') DESC, r.id DESC")
        selected, counts = filter_requests(rows, (query or {}).get("filter", "active"))
        return OK, {"ok": True, "requests": selected, "counts": counts,
                    "filter": (query or {}).get("filter", "active")}

    def admin_request_detail(self, rid):
        """`GET /api/admin/requests/{id}` — bitta so'rovni TO'LIQ ochadi.

        Ro'yxatdan topish ishlatilmaydi, shuning uchun eski so'rov ham
        (300+ yozuv ichida qolib ketgani yoki "Tarix"/"Eskirgan"ga o'tgani)
        har doim to'g'ri tafsilotlar bilan ochiladi (MODUL 5A).
        """
        self._require("admin")
        try:
            rid_int = int(rid)
        except (TypeError, ValueError):
            return NOTFOUND, err("request.not_found")
        row = self.db.q1(self.REQUEST_SQL + "WHERE r.id=?", (rid_int,))
        if not row:
            return NOTFOUND, err("request.not_found")
        req = decorate_requests([row])[0]
        return OK, {"ok": True, "request": req}

    def admin_request_approve(self, body, rid):
        self._require("admin")
        req = self.db.q1("SELECT * FROM practice_requests WHERE id=?", (int(rid),))
        if not req:
            return NOTFOUND, err("request.not_found")
        if req["status"] != "pending":
            return CONFLICT, err("request.not_pending")
        date = str(body.get("date") or req["preferred_date"] or "").strip()
        start = str(body.get("start_time") or req["preferred_start_time"] or "").strip()
        end = str(body.get("end_time") or req["preferred_end_time"] or "").strip()
        instructor_id = int(body.get("instructor_id") or 0)
        if not instructor_id:
            return BAD, err("request.no_instructor")
        errors = check_session_rules(self.db, date, start, end, instructor_id, [req["student_id"]])
        if errors:
            return CONFLICT, err("session.rules_violated", {"errors": errors})
        auto = session_auto_data(self.db, instructor_id)
        if not auto:
            # check_session_rules mashinani tekshirdi, lekin orasida holat
            # o'zgargan bo'lishi mumkin. Nothiy TypeError (500) bermaslik uchun
            # aniq xato qaytaramiz — so'rov "pending"da qoladi, xabar o'qiladi.
            row_car = self.db.q1("SELECT assigned_car_id FROM instructors WHERE id=?", (instructor_id,))
            code = "car_not_assigned" if not (row_car and row_car["assigned_car_id"]) else "car_not_found"
            return CONFLICT, err("session.rules_violated", {"errors": [code]})

        # Session, uning talabasi va so'rov holati bitta tranzaksiyada:
        # oraliqda xato chiqsa hech narsa yozilmaydi (yaroq session qolmasdi).
        def _approve(c):
            cur = c.execute(
                """INSERT INTO lesson_sessions(date,start_time,end_time,instructor_id,car_id,car_name_snapshot,
                                               car_plate_snapshot,capacity_snapshot,status,notes,created_at,updated_at)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                (date, start, end, instructor_id, auto["car_id"], auto["car_name_snapshot"],
                 auto["car_plate_snapshot"], auto["capacity_snapshot"], "scheduled",
                 "So'rov asosida yaratildi (so'rov #%d)" % int(rid), now(), now()),
            )
            sid = cur.lastrowid
            c.execute(
                """INSERT INTO session_students(session_id, student_id, pickup_address, pickup_lat, pickup_lng,
                                                attendance_status, student_status, joined_at)
                   VALUES(?,?,NULL,NULL,NULL,'unmarked','active',?)""",
                (sid, req["student_id"], now()))
            c.execute(
                "UPDATE practice_requests SET status='approved', session_id=?, processed_at=?, admin_note=? WHERE id=?",
                (sid, now(), str(body.get("note", "")).strip(), int(rid)))
            return sid

        sid = self.db.transaction(_approve)
        row = self.db.q1("SELECT * FROM lesson_sessions WHERE id=?", (sid,))
        notify_session_participants(self.db, row, "created", sender_id=self.user["id"], sender_role=self.user["role"])
        audit(self.db, self.user["id"], "request approved", "practice_requests", int(rid), {"session_id": sid})
        return OK, {"ok": True, "session_id": sid}

    def admin_request_reject(self, body, rid):
        self._require("admin")
        note = str(body.get("note", "")).strip()
        r = self.db.upd("UPDATE practice_requests SET status='rejected', processed_at=?, admin_note=? WHERE id=?",
                        (now(), note, int(rid)))
        if r == 0:
            return NOTFOUND, err("request.not_found")
        audit(self.db, self.user["id"], "request rejected", "practice_requests", int(rid), {"note": note})
        return OK, {"ok": True}

    def admin_request_cancel(self, rid):
        self._require("admin")
        self.db.upd("UPDATE practice_requests SET status='cancelled', processed_at=? WHERE id=?", (now(), int(rid)))
        return OK, {"ok": True}

    # ---- notifications (admin)
    def admin_notifications(self):
        self._require("admin")
        rows = self.db.q(
            """SELECT n.*, u.first_name, u.last_name, su.first_name AS sender_first_name,
                      su.last_name AS sender_last_name, su.profile_image AS sender_profile_image
               FROM notifications n
               JOIN users u ON u.id=n.user_id
               LEFT JOIN users su ON su.id=n.sender_id
               ORDER BY n.id DESC LIMIT 200""")
        return OK, {"ok": True, "notifications": rows}

    def admin_send_notification(self, body):
        """`POST /api/admin/notifications` — admin xabari yuborish.

        BAND 12: har bir qabulchi uchun ALOHIDA DB record yaratiladi va
        `source = ADMIN_MESSAGE`, `created_by = <admin id>` belgilanadi.
        Shu sababli "Xabarlar" kategoriyasida faqat SHU xabarlar chiqadi —
        avtomatik tizim bildirishnomalari (2-soat eslatma, mashg'ulot
        biriktirilishi va h.k.) admin xabari sifatida chiqmaydi va boshqa
        bildirishnomalarda takrorlanmaydi (BAND 11).
        """
        self._require("admin")
        role = body.get("role") or None
        title = str(body.get("title", "")).strip()
        text = str(body.get("text", "")).strip()
        if not text:
            return BAD, err("notif.empty")
        if len(text) > 4000:
            return BAD, err("notif.too_long")
        if role:
            if role not in ROLES:
                return BAD, err("bad_request")
            users = self.db.q("SELECT id FROM users WHERE role=? AND status='active' AND deleted_at IS NULL", (role,))
        else:
            users = self.db.q("SELECT id FROM users WHERE status='active' AND deleted_at IS NULL")
        created, skipped = [], []
        for u in users:
            nid = notify(self.db, u["id"], title or "message", text, "admin",
                         sender_id=self.user["id"], sender_role="admin",
                         source=SRC_ADMIN_MESSAGE, created_by=self.user["id"])
            (created if nid else skipped).append(nid or u["id"])
        audit(self.db, self.user["id"], "notification sent", None, None,
              {"role": role, "count": len(created), "skipped": len(skipped)})
        return OK, {"ok": True, "count": len(created), "skipped": len(skipped),
                    "ids": created, "source": SRC_ADMIN_MESSAGE}

    # ---- reports & export
    def admin_analytics(self, query):
        """M13-B — Admin analitika paneli: oylik faollik grafigi, bekor qilingan
        mashg'ulotlar foizi, eng band instruktorlar. GET ?month=YYYY-MM."""
        self._require("admin")
        db = self.db
        from datetime import date as _date, timedelta as _td
        try:
            ym = (query.get("month") or _date.today().strftime("%Y-%m")).strip()
            y, m = int(ym[:4]), int(ym[5:7])
            assert len(ym) == 7 and 1 <= m <= 12
            d0 = _date(y, m, 1)
        except Exception:
            return BAD, err("bad_request")
        prefix = ym + "-%"
        nxt = _date(d0.year + 1, 1, 1) if d0.month == 12 else _date(d0.year, d0.month + 1, 1)
        n_days = (nxt - d0).days
        # Joriy oy + tendentsiya uchun ~12 oy orqaga (keng so'rov)
        rows = db.q(
            """SELECT substr(date,1,7) AS ym, date AS d, status, start_time, end_time
               FROM lesson_sessions WHERE date>=?""", ((d0 - _td(days=400)).isoformat(),))
        oy = [r for r in rows if r["ym"] == ym]
        total = len(oy)
        completed = sum(1 for r in oy if r["status"] == "completed")
        cancelled = sum(1 for r in oy if r["status"] == "cancelled")
        hours = round(sum(_dur_hours(r["start_time"], r["end_time"])
                          for r in oy if r["status"] == "completed"), 1)
        unique_students = db.q1(
            """SELECT COUNT(DISTINCT ss.student_id) c FROM session_students ss
               JOIN lesson_sessions ls ON ls.id=ss.session_id
               WHERE ls.date LIKE ? AND ss.student_status='active'""", (prefix,))["c"]
        days = [{"day": i, "sessions": 0, "cancelled": 0} for i in range(1, n_days + 1)]
        for r in oy:
            try:
                day = int(r["d"][8:10])
            except Exception:
                continue
            if 1 <= day <= n_days:
                days[day - 1]["sessions"] += 1
                if r["status"] == "cancelled":
                    days[day - 1]["cancelled"] += 1
        # So'nggi 12 oy tendentsiyasi (joriy oyni ham qo'shib)
        months = []
        for k in range(11, -1, -1):
            mm, yy = m - k, y
            while mm <= 0:
                mm += 12
                yy -= 1
            key = f"{yy:04d}-{mm:02d}"
            sub = [r for r in rows if r["ym"] == key]
            months.append({"month": key, "sessions": len(sub),
                           "cancelled": sum(1 for r in sub if r["status"] == "cancelled")})
        top = db.q(
            """SELECT i.id,
                      u.first_name||' '||u.last_name AS name,
                      COUNT(ls.id) AS sessions,
                      COALESCE(SUM(CASE WHEN ls.status='completed' THEN 1 ELSE 0 END),0) AS completed,
                      COALESCE(SUM(CASE WHEN ls.status='cancelled' THEN 1 ELSE 0 END),0) AS cancelled
               FROM lesson_sessions ls
               JOIN instructors i ON i.id=ls.instructor_id
               JOIN users u ON u.id=i.user_id
               WHERE ls.date LIKE ?
               GROUP BY i.id ORDER BY sessions DESC, name LIMIT 6""", (prefix,))
        return OK, {"ok": True, "analytics": {
            "month": ym, "total": total, "completed": completed, "cancelled": cancelled,
            "cancel_rate": round(cancelled / total * 100, 1) if total else 0.0,
            "hours": hours, "unique_students": unique_students,
            "days": days, "months": months, "top_instructors": top,
        }}

    def admin_reports(self, query):
        self._require("admin")
        from .reports import build_reports
        return OK, {"ok": True, "reports": build_reports(self.db, query)}

    def admin_export(self, query):
        self._require("admin")
        from .reports import export_report_rows
        fmt = query.get("format", "csv")
        rows, sheet = export_report_rows(self.db, query)
        res = export_table(rows, fmt, sheet)
        return OK, {"ok": True, "download": {
            "filename": res["filename"], "mime": res["mime"],
            "b64": __import__("base64").b64encode(res["data"]).decode("ascii")}}

    # ---- import
    # ====================================================================
    # VAZIFA 1 — HISOBOT YARATISH: POST /api/reports/generate
    #
    # Parametrlar:
    #   roles                — ["student","instructor","admin"] (ixtiyoriy;
    #                          bo'sh = uchala rol)
    #   format               — "csv" | "xlsx" | "pdf"
    #   include_credentials  — true/false
    #   report               — "users" (foydalanuvchi ro'yxati) yoki
    #                          "sessions"/"attendance" (avvalgi mashg'ulot
    #                          hisobotlari)
    #
    # XAVFSIZLIK:
    #   * RBAC: faqat `admin` (`_require("admin")`).
    #   * `include_credentials=True` — FAQAT login/parol hisoboti qaytariladi.
    #     Bu maxfiy hujjat: har bir fayl yuklanish AUDIT jurnaliga yoziladi
    #     (kim, qachon, nechta yozuv, QANDAY format).
    #   * Har bir yuklanish `audit()` bilan qayd etiladi.
    #   * Kutubxona/shrift yo'q bo'lsa — 503 + aniq kod (bo'sh/buzilgan
    #     fayl QAYTARILMAYDI).
    # ====================================================================
    REPORT_ROLES = ("student", "instructor", "admin")

    def reports_generate(self, body):
        self._require("admin")
        from .export import ExportUnavailable, export_table
        from .reports import user_report

        # --- format ---
        fmt = str(body.get("format") or "csv").lower().strip()
        if fmt not in ("csv", "xlsx", "pdf"):
            return BAD, err("export.bad_format")
        # --- ro'yxalar ---
        report = str(body.get("report") or "users").lower().strip()
        include_cred = bool(body.get("include_credentials"))
        raw_roles = body.get("roles")
        if isinstance(raw_roles, str):
            raw_roles = [x for x in raw_roles.replace(",", " ").split() if x]
        if raw_roles is None:
            raw_roles = []
        if not isinstance(raw_roles, (list, tuple)):
            return BAD, err("export.bad_roles")
        roles = []
        for r in raw_roles:
            r = str(r).strip().lower()
            if r not in self.REPORT_ROLES:
                return BAD, err("export.bad_role", {"role": str(r)[:24]})
            if r not in roles:
                roles.append(r)
        if not roles:
            return BAD, err("rep.no_types")
        # --- til ---
        lang = str(body.get("lang") or "uz").lower().strip()
        if lang not in ("uz", "ru", "en"):
            lang = "uz"

        # --- qatorlar ---
        if report == "users":
            rows, sheet = user_report(self.db, roles, include_cred)
        else:
            from .reports import export_report_rows
            q = {"report": report, "period": body.get("period") or "monthly"}
            if body.get("from"):
                q["from"] = str(body["from"])
            if body.get("to"):
                q["to"] = str(body["to"])
            rows, sheet = export_report_rows(self.db, q)
        if not rows:
            return BAD, err("rep.no_rows")

        # --- fayl ---
        fname = ("login_parollar" if include_cred else "hisobot") + "." + fmt
        try:
            res = export_table(rows, fmt, sheet, lang=lang, filename=fname)
        except ExportUnavailable as e:
            return 503, err(e.code, {"fmt": fmt})
        except Exception:
            import traceback
            traceback.print_exc()
            return 500, err("export.failed")

        # --- AUDIT (maxfiy hisobotlar alohida belgilanadi) ---
        audit(self.db, self.user["id"],
              "report generated" + (" (CREDENTIALS)" if include_cred else ""),
              "reports", None,
              {"format": fmt, "report": report, "roles": roles,
               "rows": len(rows), "include_credentials": include_cred,
               "lang": lang})

        return OK, {"ok": True, "rows": len(rows), "format": fmt,
                    "include_credentials": include_cred,
                    "download": {"filename": res["filename"],
                                 "mime": res["mime"],
                                 "b64": __import__("base64").b64encode(res["data"]).decode("ascii")}}

    def admin_import_students(self, body):
        self._require("admin")
        csv_text = body.get("csv", "")
        if isinstance(csv_text, list):
            rows_in = csv_text
        else:
            rows_in = self._parse_csv(csv_text)
        results = {"total": 0, "created": 0, "duplicates": 0, "errors": [], "credentials": []}
        for r in rows_in:
            results["total"] += 1
            first = str(r.get("first_name", "") or r.get("Ism", "")).strip()
            last = str(r.get("last_name", "") or r.get("Familiya", "")).strip()
            if not first or not last:
                results["errors"].append({"row": r, "error": "ism/familiya majburiy"})
                continue
            phone = str(r.get("phone", "") or r.get("Telefon", "")).strip()
            dup = None
            if phone:
                dup = self.db.q1("SELECT id FROM users WHERE phone=? AND deleted_at IS NULL", (phone,))
            if dup:
                results["duplicates"] += 1
                results["errors"].append({"row": r, "error": f"Telefon allaqachon mavjud (user #{dup['id']})"})
                continue
            try:
                rec = self.db.transaction(lambda c, r=r, first=first, last=last, phone=phone: self._create_user_tx(
                    c, {
                        "first_name": first, "last_name": last,
                        "middle_name": str(r.get("middle_name", "") or "").strip(),
                        "birth_date": str(r.get("birth_date", "") or "").strip(),
                        "phone": phone,
                        "group_name": str(r.get("group_name", "") or "").strip(),
                        "license_category": str(r.get("license_category", "B") or "B").strip(),
                        "address": str(r.get("address", "") or "").strip(),
                        "notes": str(r.get("notes", "") or "").strip(),
                    }, "student"))
                results["created"] += 1
                results["credentials"].append(rec["credentials"])
            except ApiError as e:
                results["errors"].append({"row": r, "error": e.code})
        audit(self.db, self.user["id"], "students imported", "users", None, {"created": results["created"], "duplicates": results["duplicates"]})
        return OK, {"ok": True, "results": results}

    def _parse_csv(self, text):
        rows = []
        try:
            reader = csv.DictReader(io.StringIO(text), delimiter=";")
            rows = list(reader)
            if not rows:
                reader = csv.DictReader(io.StringIO(text), delimiter=",")
                rows = list(reader)
        except Exception:
            return []
        return rows

    # ---- backup
    def admin_backup_create(self):
        self._require("admin")
        if not BACKUP_DIR:
            return BAD, err("backup.disabled")
        # VACUUM INTO — server ISHLAB turib ham xavfsiz, yaxlit (WAL-safe) nusxa.
        info = make_backup(DB_PATH, BACKUP_DIR)
        name = info["file"]
        path = info["path"]
        # MODUL 1 (5): eski nusxalarni avtomatik tozalash (30 kundan ortiq)
        removed = cleanup_old_backups(BACKUP_DIR, BACKUP_RETENTION_DAYS)
        audit(self.db, self.user["id"], action_type="backup_created", target_type="backup",
              target_id=None, description=name, user_name=user_name(self.user))
        if removed:
            audit(self.db, self.user["id"], action_type="backup_cleanup", target_type="backup",
                  description="%d ta eski nusxa o'chirildi" % len(removed))
        return OK, {"ok": True, "file": name, "size": os.path.getsize(path),
                    "removed": removed, "retention_days": BACKUP_RETENTION_DAYS}

    def admin_backup_list(self):
        self._require("admin")
        if not BACKUP_DIR or not os.path.isdir(BACKUP_DIR):
            return OK, {"ok": True, "backups": []}
        files = sorted(os.listdir(BACKUP_DIR), reverse=True)[:100]
        out = [{"name": f, "size": os.path.getsize(os.path.join(BACKUP_DIR, f)),
                "time": os.path.getmtime(os.path.join(BACKUP_DIR, f))} for f in files if os.path.isfile(os.path.join(BACKUP_DIR, f))]
        return OK, {"ok": True, "backups": out}

    def admin_backup_download(self, filename: str):
        self._require("admin")
        import os as _os
        if not filename or ".." in filename:
            return BAD, err("backup.bad")
        path = _os.path.join(BACKUP_DIR, filename) if BACKUP_DIR else filename
        if not _os.path.exists(path) or not _os.path.isfile(path):
            return NOTFOUND, err("not_found")
        import base64
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        return OK, {"download": {"b64": b64, "filename": filename, "mime": "application/octet-stream"}}

    def admin_backup_delete(self, filename: str):
        """Zaxira nusxani serverdan BUTUNLAY o'chirish (MODUL 3).

        Xavfsizlik: papkadan chiqib ketish (`..`, absolyut yo'l) bloklanadi;
        faqat BACKUP_DIR ichidagi oddiy fayl o'chiriladi. Amal Audit
        jurnaliga yoziladi (kim, qachon, qaysi faylni o'chirgani).
        """
        self._require("admin")
        name = str(filename or "")
        if not name or ".." in name or "/" in name or "\\" in name:
            return BAD, err("backup.bad")
        path = os.path.join(BACKUP_DIR, name) if BACKUP_DIR else name
        if not os.path.isfile(path):
            return NOTFOUND, err("backup.not_found")
        try:
            size = os.path.getsize(path)
            os.remove(path)
        except OSError:
            return BAD, err("backup.delete_failed")
        audit(self.db, self.user["id"], action_type="backup_deleted", target_type="backup",
              target_id=None, description=name, user_name=user_name(self.user))
        return OK, {"ok": True, "deleted": name, "size": size}

    def admin_backup_restore(self, body):
        self._require("admin")
        filename = str(body.get("filename", ""))
        if not filename or ".." in filename:
            return BAD, err("backup.bad")
        path = os.path.join(BACKUP_DIR, filename) if BACKUP_DIR else filename
        if not os.path.exists(path):
            return NOTFOUND, err("not_found")
        # XAVFSIZLIK: tiklashdan OLDIN joriy bazaning "zaxira nusxasi"ni
        # olamiz — noto'g'ri nusxa tanlansa ham ma'lumot yo'qolmaydi.
        try:
            self.admin_backup_create()
        except Exception:
            pass
        import shutil, sqlite3 as _sq
        # WAL yordamchi fayllarini o'chiramiz (eski holat qolmasin)
        for suf in ("-wal", "-shm"):
            p = DB_PATH + suf
            if os.path.exists(p):
                try:
                    os.remove(p)
                except Exception:
                    pass
        shutil.copy2(path, DB_PATH)
        # Nusxa haqiqiy SQLite bazasi ekanini tekshiramiz
        try:
            vc = _sq.connect(DB_PATH)
            ok = vc.execute("PRAGMA integrity_check").fetchone()[0]
            vc.close()
        except Exception:
            return BAD, err("backup.restore_bad")
        if ok != "ok":
            return BAD, err("backup.restore_bad")
        try:
            uname = (self.user.get("first_name") or "") + " " + (self.user.get("last_name") or "")
        except Exception:
            uname = ""
        audit(self.db, self.user["id"], action_type="backup_restored", target_type="backup", description=filename, user_name=uname)
        return OK, {"ok": True}

    # ---- audit
    def admin_audit(self, query):
        self._require("admin")
        where = []
        params = []
        if query.get("action"):
            where.append("action_type LIKE ?")
            params.append("%" + query["action"] + "%")
        if query.get("q"):
            where.append("(action_type LIKE ? OR description LIKE ? OR user_name LIKE ?)")
            qv = "%" + query["q"] + "%"
            params.extend([qv, qv, qv])
        if query.get("user"):
            try:
                uid = int(query["user"])
                where.append("user_id = ?")
                params.append(uid)
            except Exception:
                pass
        if query.get("from"):
            where.append("timestamp >= ?")
            params.append(query["from"] + " 00:00:00")
        if query.get("to"):
            where.append("timestamp <= ?")
            params.append(query["to"] + " 23:59:59")
        rows = self.db.q(
            "SELECT id,user_id,user_name,action_type,target_type,target_id,description,ip_address,timestamp FROM audit_log WHERE " + (" AND ".join(where) if where else "1=1") +
            " ORDER BY id DESC LIMIT 500", params)
        users = self.db.q(
            "SELECT DISTINCT user_id AS id, user_name AS name FROM audit_log WHERE user_id IS NOT NULL ORDER BY name LIMIT 200")
        acts = self.db.q("SELECT DISTINCT action_type FROM audit_log ORDER BY action_type LIMIT 200")
        return OK, {"ok": True, "logs": rows,
                    "user_options": users,
                    "action_options": [a["action_type"] for a in acts if a.get("action_type")]}

    # ---- settings, translations
    def admin_settings_get(self):
        self._require("admin")
        rows = self.db.q("SELECT * FROM system_settings")
        s = {r["key"]: jload(r["value"]) for r in rows}
        # M12: platforma sozlamalari defaultlar bilan (csrf_session kabi ichki
        # kalitlar sirga chiqmaydi — faqat platforma kalitlari qaytariladi)
        out = {k: s.get(k, v) for k, v in DEFAULT_PLATFORM_SETTINGS.items()}
        return OK, {"ok": True, "settings": out}

    def admin_settings_put(self, body):
        self._require("admin")
        for k, v in body.items():
            # MODUL 5: "jami darslar" maqsadi 1..999 oralig'ida bo'lishi SHART.
            # 0, bo'sh yoki noto'g'ri qiymat standartga qaytariladi — shunda
            # talaba sahifasidagi foiz hisobi hech qachon nolga bo'linib xato
            # bermaydi ( ZeroDivisionError ).
            if k == "total_lessons_target":
                try:
                    v = int(v)
                except (TypeError, ValueError):
                    v = 0
                if v < 1:
                    v = DEFAULT_PLATFORM_SETTINGS["total_lessons_target"]
                elif v > 999:
                    v = 999
            self.db.ex(
                "INSERT INTO system_settings(key,value,updated_at) VALUES(?,?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
                (k, jdump(v), now()))
        return OK, {"ok": True}

    # ------------------------------------------------------------- INSTRUKTOR
    def _inst_record(self):
        return self.db.q1("SELECT * FROM instructors WHERE user_id=?", (self.user["id"],))

    def instructor_context(self):
        if not self.user or self.user["role"] != "instructor":
            return FORBIDDEN, err("forbidden")
        inst = self._inst_record()
        if not inst:
            return FORBIDDEN, err("forbidden")
        car = self.db.q1("SELECT * FROM cars WHERE id=? AND deleted_at IS NULL", (inst["assigned_car_id"],)) if inst["assigned_car_id"] else None
        return OK, {"ok": True, "instructor": inst, "car": car, "user": user_public(self.user)}

    def instructor_today(self):
        self._require("instructor")
        inst = self._inst_record()
        rows = self.db.q(
            """SELECT ls.*, (SELECT COUNT(*) FROM session_students ss WHERE ss.session_id=ls.id AND ss.student_status='active') AS student_count
               FROM lesson_sessions ls WHERE ls.instructor_id=? AND ls.date=? AND ls.status!='cancelled'
               ORDER BY ls.start_time""", (inst["id"], today()))
        return OK, {"ok": True, "sessions": rows}

    def instructor_home(self):
        """M6: Instruktor Bosh sahifasi — haftalik statistika, avtomobil, umumiy progress."""
        self._require("instructor")
        inst = self._inst_record()
        ws = _week_monday()
        we = today()
        wk = self.db.q(
            """SELECT ls.start_time, ls.end_time, ls.status
               FROM lesson_sessions ls WHERE ls.instructor_id=? AND ls.date>=? AND ls.date<=? AND ls.status!='cancelled'""",
            (inst["id"], ws, we))
        done = sum(1 for r in wk if r["status"] == "completed")
        hours = sum(_dur_hours(r["start_time"], r["end_time"]) for r in wk)
        students = self.db.q1(
            """SELECT COUNT(DISTINCT ss.student_id) AS c
               FROM session_students ss JOIN lesson_sessions ls ON ls.id=ss.session_id
               WHERE ls.instructor_id=? AND ls.date>=? AND ls.date<=? AND ls.status!='cancelled' AND ss.student_status='active'""",
            (inst["id"], ws, we))["c"]
        # Umumiy (barcha davr): bajarilgan darslar va soatlar
        all_rows = self.db.q(
            """SELECT start_time, end_time, status FROM lesson_sessions
               WHERE instructor_id=? AND status!='cancelled'""", (inst["id"],))
        car = self.db.q1("SELECT * FROM cars WHERE id=? AND deleted_at IS NULL", (inst["assigned_car_id"],)) \
            if inst["assigned_car_id"] else None
        return OK, {"ok": True, "weekly": {
            "sessions": len(wk), "done": done, "hours": round(hours, 1), "students": students,
            "today": self.db.q1(
                "SELECT COUNT(*) c FROM lesson_sessions WHERE instructor_id=? AND date=? AND status!='cancelled'",
                (inst["id"], today()))["c"],
        }, "overall": {
            "sessions": len(all_rows), "done": sum(1 for r in all_rows if r["status"] == "completed"),
            "hours": round(sum(_dur_hours(r["start_time"], r["end_time"]) for r in all_rows), 1),
        }, "car": car}

    def instructor_schedule(self, query):
        self._require("instructor")
        inst = self._inst_record()
        date = query.get("date") or today()
        rows = self.db.q(
            """SELECT ls.*, (SELECT COUNT(*) FROM session_students ss WHERE ss.session_id=ls.id AND ss.student_status='active') AS student_count
               FROM lesson_sessions ls WHERE ls.instructor_id=? AND ls.date=? ORDER BY ls.start_time""", (inst["id"], date))
        return OK, {"ok": True, "date": date, "sessions": rows}

    def instructor_students(self):
        self._require("instructor")
        inst = self._inst_record()
        rows = self.db.q(
            """SELECT DISTINCT s.id AS student_id, u.id AS user_id, u.first_name, u.last_name, u.middle_name,
                      u.phone, s.group_name, s.license_category
               FROM session_students ss JOIN lesson_sessions ls ON ls.id=ss.session_id
               JOIN students s ON s.id=ss.student_id JOIN users u ON u.id=s.user_id
               WHERE ls.instructor_id=? AND ss.student_status='active'
               ORDER BY u.last_name""", (inst["id"],))
        return OK, {"ok": True, "students": rows}

    def instructor_car(self):
        self._require("instructor")
        inst = self._inst_record()
        car = self.db.q1("SELECT * FROM cars WHERE id=? AND deleted_at IS NULL", (inst["assigned_car_id"],)) if inst["assigned_car_id"] else None
        photos = self._car_photos_map([car["id"]]) if car else {}
        hist = self.db.q(
            """SELECT COUNT(*) AS sessions, date FROM lesson_sessions WHERE instructor_id=? AND car_id=?
               GROUP BY date ORDER BY date DESC LIMIT 20""", (inst["id"], car["id"])) if car else []
        return OK, {"ok": True, "car": car, "photos": photos.get(car["id"], []) if car else [], "history": hist}

    def instructor_car_update(self, body):
        """M6 — instruktor FAQAT o'ziga biriktirilgan mashinani tahrirlay oladi
        (assigned_car_id tekshiruvi); admin huquqlari o'zgarishsiz."""
        self._require("instructor")
        inst = self._inst_record()
        cid = inst["assigned_car_id"]
        if not cid:
            return NOTFOUND, err("instructor.no_car")
        car = self.db.q1("SELECT * FROM cars WHERE id=? AND deleted_at IS NULL", (cid,))
        if not car:
            return NOTFOUND, err("car.not_found")
        upd = {}
        if "plate_number" in body:
            plate = str(body["plate_number"]).strip().upper()
            if not re.match(r"^[0-9A-ZА-ЯЁUZ \-]{4,12}$", plate):
                return BAD, err("car.bad_plate")
            if self.db.q1("SELECT id FROM cars WHERE plate_number=? AND id!=? AND deleted_at IS NULL", (plate, cid)):
                return CONFLICT, err("car.plate_exists")
            upd["plate_number"] = plate
        if "brand" in body: upd["brand"] = str(body["brand"]).strip()
        if "model" in body: upd["model"] = str(body["model"]).strip()
        if "custom_model_name" in body: upd["custom_model_name"] = str(body["custom_model_name"]).strip()
        if "year" in body: upd["year"] = int(body["year"] or 0)
        if "color" in body: upd["color"] = str(body["color"]).strip()
        if "seat_count" in body: upd["seat_count"] = int(body["seat_count"] or 4)
        if "practice_capacity" in body:
            cap = int(body["practice_capacity"])
            if cap < 1 or cap > 20:
                return BAD, err("car.bad_capacity")
            upd["practice_capacity"] = cap
        if "technical_inspection_date" in body: upd["technical_inspection_date"] = str(body["technical_inspection_date"]).strip()
        if "insurance_expiry" in body: upd["insurance_expiry"] = str(body["insurance_expiry"]).strip()
        if "notes" in body: upd["notes"] = str(body["notes"]).strip()
        if upd:
            upd["updated_at"] = now()
            self.db.upd("UPDATE cars SET " + ", ".join(f"{k}=?" for k in upd) + " WHERE id=?",
                        (*upd.values(), cid))
        audit(self.db, self.user["id"], "car updated (instructor)", "cars", cid, upd)
        return OK, {"ok": True}

    def instructor_session_detail(self, sid):
        self._require("instructor")
        inst = self._inst_record()
        row = self.db.q1(
            """SELECT ls.*, u.first_name||' '||u.last_name AS instructor_name, u.phone AS instructor_phone,
                      (SELECT COUNT(*) FROM session_students WHERE session_id=ls.id AND student_status='active') AS student_count
               FROM lesson_sessions ls JOIN instructors i ON i.id=ls.instructor_id
               JOIN users u ON u.id=i.user_id WHERE ls.id=? AND ls.instructor_id=?""",
            (int(sid), inst["id"]))
        if not row:
            return NOTFOUND, err("session.not_found")
        row["students"] = self.db.q(
            """SELECT ss.*, u.id AS user_id, u.first_name, u.last_name, u.middle_name, u.phone, s.group_name
               FROM session_students ss JOIN students s ON s.id=ss.student_id
               JOIN users u ON u.id=s.user_id
               WHERE ss.session_id=? AND ss.student_status='active' ORDER BY ss.joined_at""", (int(sid),))
        return OK, {"ok": True, "session": row}

    def instructor_start(self, sid):
        self._require("instructor")
        inst = self._inst_record()
        row = self.db.q1("SELECT * FROM lesson_sessions WHERE id=? AND instructor_id=?", (int(sid), inst["id"]))
        if not row:
            return NOTFOUND, err("session.not_found")
        if row["status"] != "scheduled":
            return CONFLICT, err("session.wrong_status")
        if row["date"] != today():
            return CONFLICT, err("session.not_today")
        self.db.upd("UPDATE lesson_sessions SET status='ongoing', started_at=?, updated_at=? WHERE id=?",
                    (now(), now(), int(sid)))
        audit(self.db, self.user["id"], "session started", "lesson_sessions", int(sid))
        return OK, {"ok": True}

    def instructor_finish(self, sid):
        self._require("instructor")
        inst = self._inst_record()
        row = self.db.q1("SELECT * FROM lesson_sessions WHERE id=? AND instructor_id=?", (int(sid), inst["id"]))
        if not row:
            return NOTFOUND, err("session.not_found")
        if row["status"] != "ongoing":
            return CONFLICT, err("session.wrong_status")
        self.db.upd("UPDATE lesson_sessions SET status='completed', completed_at=?, updated_at=? WHERE id=?",
                    (now(), now(), int(sid)))
        # BAND 9/14: yakunlandi — 2-soat eslatmasi kerak emas (o'chiriladi),
        # va har bir talabaga alohida BAJARILGAN bildirishnoma yoziladi
        # (`source=LESSON_COMPLETED`, admin xabari sifatida chiqmaydi).
        clear_lesson_reminders(self.db, int(sid))
        newrow = self.db.q1("SELECT * FROM lesson_sessions WHERE id=?", (int(sid),))
        notify_session_participants(self.db, newrow, "finished",
                                    sender_id=self.user["id"], sender_role=self.user["role"])
        audit(self.db, self.user["id"], "session finished", "lesson_sessions", int(sid))
        return OK, {"ok": True}

    def instructor_attendance(self, body, sid):
        self._require("instructor")
        inst = self._inst_record()
        row = self.db.q1("SELECT * FROM lesson_sessions WHERE id=? AND instructor_id=?", (int(sid), inst["id"]))
        if not row:
            return NOTFOUND, err("session.not_found")
        if row["status"] not in ("ongoing", "scheduled"):
            return CONFLICT, err("session.wrong_status")
        student_id = int(body.get("student_id") or 0)
        status = body.get("status")
        if status not in ("present", "late", "absent"):
            return BAD, err("attendance.bad_status")
        ok = self.db.upd(
            "UPDATE session_students SET attendance_status=? WHERE session_id=? AND student_id=? AND student_status='active'",
            (status, int(sid), student_id))
        if ok == 0:
            return NOTFOUND, err("session.student_not_found")
        self.db.ex(
            "INSERT INTO attendance(session_id, student_id, status, marked_by, marked_at) VALUES(?,?,?,?,?)",
            (int(sid), student_id, status, inst["user_id"], now()))
        return OK, {"ok": True}

    def instructor_session_cancel(self, body, sid):
        """Instruktor o'z mashg'ulotini sababi bilan bekor qiladi (scheduled)."""
        self._require("instructor")
        inst = self._inst_record()
        row = self.db.q1("SELECT * FROM lesson_sessions WHERE id=? AND instructor_id=?", (int(sid), inst["id"]))
        if not row:
            return NOTFOUND, err("session.not_found")
        if row["status"] != "scheduled":
            return CONFLICT, err("session.wrong_status")
        reason = str(body.get("reason", "")).strip()
        self.db.upd("UPDATE lesson_sessions SET status='cancelled', cancel_reason=?, updated_at=? WHERE id=?",
                    (reason, now(), int(sid)))
        notify_session_participants(self.db, row, "cancelled", by="instructor",
                                   sender_id=self.user["id"], sender_role=self.user["role"])
        audit(self.db, self.user["id"], "session cancelled", "lesson_sessions", int(sid),
              {"reason": reason, "by": "instructor"})
        return OK, {"ok": True}

    def instructor_session_reschedule(self, body, sid):
        """Instruktor o'z mashg'ulotini boshqa vaqtga ko'chiradi (sana/vaqt, o'zi bilan)."""
        self._require("instructor")
        inst = self._inst_record()
        row = self.db.q1("SELECT * FROM lesson_sessions WHERE id=? AND instructor_id=?", (int(sid), inst["id"]))
        if not row:
            return NOTFOUND, err("session.not_found")
        if row["status"] != "scheduled":
            return CONFLICT, err("session.wrong_status")
        date = str(body.get("date", row["date"])).strip()
        start = str(body.get("start_time", row["start_time"])).strip()
        end = str(body.get("end_time", row["end_time"])).strip()
        errors = check_session_rules(self.db, date, start, end, inst["id"],
                                     [r["student_id"] for r in self.db.q(
                                         "SELECT student_id FROM session_students WHERE session_id=? AND student_status='active'",
                                         (int(sid),))],
                                     exclude_session_id=int(sid))
        if errors:
            return CONFLICT, err("session.rules_violated", {"errors": errors})
        self.db.upd(
            """UPDATE lesson_sessions SET
                 original_date=CASE WHEN original_date='' THEN date ELSE original_date END,
                 original_start_time=CASE WHEN original_start_time='' THEN start_time ELSE original_start_time END,
                 original_end_time=CASE WHEN original_end_time='' THEN end_time ELSE original_end_time END,
                 date=?, start_time=?, end_time=?,
                 status='scheduled', updated_at=? WHERE id=?""",
            (date, start, end, now(), int(sid)))
        newrow = self.db.q1("SELECT * FROM lesson_sessions WHERE id=?", (int(sid),))
        notify_session_participants(self.db, newrow, "rescheduled", by="instructor",
                                   sender_id=self.user["id"], sender_role=self.user["role"])
        audit(self.db, self.user["id"], "session rescheduled", "lesson_sessions", int(sid),
              {"date": date, "start": start, "end": end, "by": "instructor"})
        return OK, {"ok": True, "session": newrow}

    # -------------------------------------------------------------- TALABA
    def _stud_record(self):
        return self.db.q1("SELECT * FROM students WHERE user_id=?", (self.user["id"],))

    def student_context(self):
        if not self.user or self.user["role"] != "student":
            return FORBIDDEN, err("forbidden")
        st = self._stud_record()
        if not st:
            return FORBIDDEN, err("forbidden")
        return OK, {"ok": True, "student": st, "user": user_public(self.user)}

    def student_next(self):
        self._require("student")
        st = self._stud_record()
        row = self.db.q1(
            """SELECT ls.*, u.first_name||' '||u.last_name AS instructor_name, u.phone AS instructor_phone,
                      ss.pickup_address, ss.pickup_lat, ss.pickup_lng,
                      (SELECT COUNT(*) FROM session_students ss WHERE ss.session_id=ls.id AND ss.student_status='active') AS student_count
               FROM session_students ss JOIN lesson_sessions ls ON ls.id=ss.session_id
               JOIN instructors i ON i.id=ls.instructor_id JOIN users u ON u.id=i.user_id
               WHERE ss.student_id=? AND ss.student_status='active' AND ls.status IN ('scheduled','ongoing')
                 AND (ls.date > ? OR (ls.date=? AND ls.end_time > ?))
               ORDER BY ls.date, ls.start_time LIMIT 1""",
            (st["id"], today(), today(), now()[11:16]))
        return OK, {"ok": True, "next": row}

    def student_home(self):
        """M6: Talaba Bosh sahifasi — haftalik va umumiy progress + keyingi dars."""
        self._require("student")
        st = self._stud_record()
        ws = _week_monday()
        we = today()
        rows = self.db.q(
            """SELECT ls.date, ls.start_time, ls.end_time, ls.status, ls.id,
                      u.first_name||' '||u.last_name AS instructor_name,
                      ls.car_plate_snapshot, ss.pickup_address
               FROM session_students ss JOIN lesson_sessions ls ON ls.id=ss.session_id
               JOIN instructors i ON i.id=ls.instructor_id JOIN users u ON u.id=i.user_id
               WHERE ss.student_id=? AND ss.student_status='active' AND ls.status!='cancelled'
               ORDER BY ls.date, ls.start_time""", (st["id"],))
        wk_rows = [r for r in rows if ws <= r["date"] <= we]
        def agg(items):
            return {
                "sessions": len(items),
                "done": sum(1 for r in items if r["status"] == "completed"),
                "hours": round(sum(_dur_hours(r["start_time"], r["end_time"]) for r in items), 1),
            }
        nxt = self.db.q1(
            """SELECT ls.id, ls.date, ls.start_time, ls.end_time, ls.status,
                      u.first_name||' '||u.last_name AS instructor_name, ls.car_plate_snapshot,
                      ss.pickup_address,
                      (SELECT COUNT(*) FROM session_students ss WHERE ss.session_id=ls.id AND ss.student_status='active') AS student_count
               FROM session_students ss JOIN lesson_sessions ls ON ls.id=ss.session_id
               JOIN instructors i ON i.id=ls.instructor_id JOIN users u ON u.id=i.user_id
               WHERE ss.student_id=? AND ss.student_status='active' AND ls.status IN ('scheduled','ongoing')
                 AND (ls.date > ? OR (ls.date=? AND ls.end_time > ?))
               ORDER BY ls.date, ls.start_time LIMIT 1""",
            (st["id"], today(), today(), now()[11:16]))
        # MODUL 5 — "Jami darslar": individual yoki ommaviy rejim.
        # Individual: students.total_lessons_target (NULL bo'lmasa) ustun keladi,
        # ommaviy: system_settings.total_lessons_target.
        try:
            global_target = int(_platform_setting(self.db, "total_lessons_target", 30) or 30)
        except (TypeError, ValueError):
            global_target = 30
        try:
            individual = int(st["total_lessons_target"]) if st.get("total_lessons_target") else None
        except (TypeError, ValueError):
            individual = None
        target = individual if individual and individual > 0 else global_target
        done_all = sum(1 for r in rows if r["status"] == "completed")
        progress = {
            "target": target,
            "done": done_all,
            "remaining": max(0, target - done_all),
            "mode": "individual" if individual else "group",
            "group_target": global_target,
            "individual_target": individual,
            # Bajarilgan foiz. Maqsad 0 bo'lsa (admin o'chirib qo'ygan bo'lsa)
            # foiz 0 qoladi — xatolik chiqmasligi uchun.
            "pct": round(done_all * 100 / target) if target > 0 else 0,
        }
        # BAND 13/14: kelmagan va o'tib ketgan mashg'ulotlar soni. "Kutilmoqda"
        # faqat kelmaganlar uchun; o'tib ketgan lekin yakunlanmagan darslar
        # alohida hisoblanadi va progress'ga kirMAYDI.
        upcoming, overdue = 0, 0
        for r in rows:
            disp = session_business_status(r, today(), now()[11:16])
            if disp in ("pending", "confirmed"):
                upcoming += 1
            elif disp == "overdue":
                overdue += 1
        return OK, {"ok": True, "weekly": agg(wk_rows), "overall": agg(rows),
                    "progress": progress, "next": nxt,
                    "counts": {"total": len(rows), "done": done_all,
                               "remaining": progress["remaining"], "upcoming": upcoming,
                               "overdue": overdue}}

    def student_today(self):
        """M6: Talaba 'Bugun' bo'limi — bugungi mashg'ulotlar ro'yxati."""
        self._require("student")
        st = self._stud_record()
        rows = self.db.q(
            """SELECT ls.id, ls.date, ls.start_time, ls.end_time, ls.status, ls.car_name_snapshot,
                      ls.car_plate_snapshot, ls.capacity_snapshot,
                      u.first_name||' '||u.last_name AS instructor_name, ss.pickup_address,
                      (SELECT COUNT(*) FROM session_students s2 WHERE s2.session_id=ls.id AND s2.student_status='active') AS student_count
               FROM session_students ss JOIN lesson_sessions ls ON ls.id=ss.session_id
               JOIN instructors i ON i.id=ls.instructor_id JOIN users u ON u.id=i.user_id
               WHERE ss.student_id=? AND ss.student_status='active' AND ls.date=? AND ls.status!='cancelled'
               ORDER BY ls.start_time""", (st["id"], today()))
        return OK, {"ok": True, "sessions": rows}

    def student_sessions(self, query):
        """`GET /api/student/sessions?upcoming=1|0|all`

        BAND 13/14 — kelajakdagi va o'tilgan mashg'ulotlar ANIQ ajratiladi:
          * KELAJAK (`upcoming=1`): faqat kelmagan/rejalashtirilgan mashg'ulotlar.
            Bitta kun o'tib ketgan dars bu ro'yxatda QOLMAYDI (lekin DB'da
            saqlanadi va "Mashg'ulotlar tarixi"ga kiradi).
          * O'TGAN (`upcoming=0`): `completed` + `cancelled` + o'tib ketgan
            lekin yakunlanmagan (`overdue`) mashg'ulotlar.
          * `all`: ikkalasi birga.

        BAND 14 — "Kutilmoqda" faqat KELMAGAN mashg'ulotlar uchun. Vaqt o'tib
        ketgan, lekin haqiqatan bajarilmagan dars AVTOMATIK "Bajarilgan"
        BO'LMAYDI — u `OVERDUE` ("o'tib ketgan, tasdiqlash kutilmoqda")
        holatida tarixga tushadi. Bajarilgan darslar soniga faqat
        `status='completed'` hisoblanadi.
        """
        self._require("student")
        st = self._stud_record()
        sel = """SELECT ls.*, ls.confirm_state AS confirm_state,
                        u.first_name||' '||u.last_name AS instructor_name, u.phone AS instructor_phone,
                        ss.pickup_address, ss.pickup_lat, ss.pickup_lng, ss.attendance_status,
                        (SELECT COUNT(*) FROM session_students s2 WHERE s2.session_id=ls.id AND s2.student_status='active') AS student_count
                 FROM session_students ss JOIN lesson_sessions ls ON ls.id=ss.session_id
                 JOIN instructors i ON i.id=ls.instructor_id JOIN users u ON u.id=i.user_id
                 WHERE ss.student_id=? AND ss.student_status='active' """
        up = str(query.get("upcoming", "1")).strip()
        # Kelajak = kelmagan, bekor qilinmagan. VAQT O'TGAN darslar hamkiradi
        # (bitta kun o'tishi yetarli).
        future_cond = ("AND ls.status IN ('scheduled','ongoing') "
                       "AND (ls.date > ? OR (ls.date = ? AND ls.end_time > ?))")
        past_cond = ("AND (ls.status IN ('completed','cancelled') "
                     "OR (ls.status IN ('scheduled','ongoing') "
                     "AND NOT (ls.date > ? OR (ls.date = ? AND ls.end_time > ?)))) "
                     "AND ls.id NOT IN (SELECT session_id FROM hidden_history WHERE user_id=?)")
        params_all = [st["id"], today(), today(), now()[11:16]]
        if up == "1":
            rows = self.db.q(sel + future_cond + " ORDER BY ls.date, ls.start_time", params_all)
        elif up == "0":
            rows = self.db.q(sel + past_cond + " ORDER BY ls.date DESC, ls.start_time DESC LIMIT 200",
                             [st["id"], today(), today(), now()[11:16], st["id"]])
        else:
            rows = self.db.q(sel + " ORDER BY ls.date, ls.start_time LIMIT 400", [st["id"]])
        for r in rows:
            session_business_status(r, today(), now()[11:16])
        if up == "all":
            upcoming = [r for r in rows if r["_is_future"]]
            past = [r for r in rows if not r["_is_future"]]
            return OK, {"ok": True, "sessions": upcoming, "upcoming": upcoming,
                        "past": past, "counts": {
                            "upcoming": len(upcoming), "past": len(past),
                            "overdue": sum(1 for r in past if r["_display_status"] == "overdue"),
                            "completed": sum(1 for r in past if r["_display_status"] == "completed"),
                        }}
        return OK, {"ok": True, "sessions": rows}

    def student_session_detail(self, sid):
        self._require("student")
        st = self._stud_record()
        row = self.db.q1(
            """SELECT ls.*, u.first_name||' '||u.last_name AS instructor_name, u.phone AS instructor_phone,
                      ss.pickup_address, ss.pickup_lat, ss.pickup_lng, ss.attendance_status,
                      (SELECT COUNT(*) FROM session_students s2 WHERE s2.session_id=ls.id AND s2.student_status='active') AS student_count
               FROM session_students ss JOIN lesson_sessions ls ON ls.id=ss.session_id
               JOIN instructors i ON i.id=ls.instructor_id JOIN users u ON u.id=i.user_id
               WHERE ss.student_id=? AND ss.student_status='active' AND ls.id=?""",
            (st["id"], int(sid)))
        if not row:
            return NOTFOUND, err("session.not_found")
        # BAND 14: aniq biznes holati (KUTILMOQDA / TASDIQLANGAN / ... / O'TIB KETGAN)
        session_business_status(row, today(), now()[11:16])
        return OK, {"ok": True, "session": row}

    def student_update_pickup(self, body, sid):
        """`POST /api/student/sessions/{id}/pickup` — UCHRASHUV JOYINI o'zgartirish.

        VAQTINCHA REJIM (MAP_DISABLED=True, `app/api.py` yuqorida):
          UI'da faqat BIR TA oddiy matn maydoni bor — "Uchrashuv joyi".
          Xarita, autocomplete va koordinata kiritish yo'q.
          So'rov yuborilganda `lat`/`lng` kelmasa -> bazada NULL qoladi
          (ustunlar O'CHIRILMAGAN, kelajakda xarita uchun joy bor).
          Kelganda `lat`/`lng` yuborilsa ham ular saqlanadi — eski mijozlar
          (yoki kelajakdagi xarita rejimi) buzilmaydi.

        QAYTA XARITA YOQILGANDA (MAP_DISABLED=False): quyidagi mantiq to'liq
        ishlaydi — koordinata FAQAT shu endpoint orqali keladi.

        IDOR HIMOYASI: `WHERE session_id=? AND student_id=?` — `/student/123`
        o'rniga `/student/124` yozilsa, boshqa talabaning mashg'uloti
        OG'IRILMAYDI (0 qator yangilanadi -> 404).
        """
        self._require("student")
        st = self._stud_record()
        # MODUL 4: kenglik/uzunlik validatsiyasi. Noto'g'ri qiymat ("abc",
        # 200, "NaN") JIM QOLMAYDI — 400 + aniq kod qaytariladi.
        # MUHIM: so'rovda `lat`/`lng` KALITI yo'q bo'lsa — mavjud koordinata
        # o'zgartirilmaydi (faqat manzil o'zgaradi). Bo'sh string yuborilsa
        # esa koordinata ataylab tozalanadi.
        has_lat = "lat" in body or "pickup_lat" in body
        has_lng = "lng" in body or "pickup_lng" in body
        lat = lng = None
        if has_lat or has_lng:
            raw_lat = body["lat"] if "lat" in body else body.get("pickup_lat")
            raw_lng = body["lng"] if "lng" in body else body.get("pickup_lng")
            try:
                lat = parse_coord(raw_lat, "lat")
                lng = parse_coord(raw_lng, "lng")
            except ValueError as e:
                kind = e.args[0] if e.args else "lat"
                return BAD, err("coord.bad_" + kind)
            # Bir tomoni bo'sh, ikkinchisi to'ldirilgan bo'lsa — chalkash holat
            if (lat is None) != (lng is None):
                return BAD, err("coord.pair_incomplete")
        # Hali saqlanmagan koordinatani saqlashga urinish -> 404
        if not self.db.q1(
                """SELECT id FROM session_students
                   WHERE session_id=? AND student_id=? AND student_status='active'""",
                (int(sid), st["id"])):
            return NOTFOUND, err("session.student_not_found")
        sets = ["pickup_address=?"]
        address = str(body.get("address", "")).strip()
        if len(address) > 300:
            return BAD, err("map.address_too_long")
        # VAQTINCHA REJIM (xarita o'chirilgan): faqat MATN talab qilinadi.
        # Koordinata kelmasa `pickup_lat/lng` NULL bo'lib qoladi (ustunlar
        # bazada saqlanib qolgan). Kelajakda xarita qaytganda ham xuddi shu
        # qoida ishlaydi — `address` bo'sh va koordinata ham bo'sh bo'lsa,
        # ma'nosiz so'rov rad etiladi (jim qolmasligi uchun).
        if not address and not has_lat and not has_lng:
            return BAD, err("map.address_required")
        params = [address]
        if has_lat or has_lng:
            sets += ["pickup_lat=?", "pickup_lng=?"]
            params += [lat, lng]
        params += [int(sid), st["id"]]
        upd = self.db.upd(
            """UPDATE session_students SET %s
               WHERE id=(SELECT id FROM session_students
                         WHERE session_id=? AND student_id=? AND student_status='active')"""
            % ", ".join(sets), params)
        if upd == 0:
            return NOTFOUND, err("session.student_not_found")
        return OK, {"ok": True}

    def student_requests(self, query=None):
        """`GET /api/student/requests[?filter=active|expired|history]`

        MODUL 5: bo'limlar `admin_requests` bilan bir xil mantiqda bo'linadi
        (mashg'ulot sanasi + 1 kun, faqat `pending` holda). Foydalanuvchi
        tomonidan qo'lda yashirilgan so'rovlar (`hidden_requests`) umuman
        ko'rsatilmaydi.
        """
        self._require("student")
        st = self._stud_record()
        rows = self.db.q(
            "SELECT * FROM practice_requests WHERE student_id=? AND id NOT IN "
            "(SELECT request_id FROM hidden_requests WHERE user_id=?) ORDER BY id DESC",
            (st["id"], st["id"]))
        selected, counts = filter_requests(rows, (query or {}).get("filter", "active"))
        return OK, {"ok": True, "requests": selected, "counts": counts,
                    "filter": (query or {}).get("filter", "active")}

    def student_request_detail(self, rid):
        """`GET /api/student/requests/{id}` — bitta so'rovni ochish (MODUL 5A)."""
        self._require("student")
        st = self._stud_record()
        try:
            rid_int = int(rid)
        except (TypeError, ValueError):
            return NOTFOUND, err("request.not_found")
        row = self.db.q1(
            "SELECT * FROM practice_requests WHERE id=? AND student_id=?"
            " AND id NOT IN (SELECT request_id FROM hidden_requests WHERE user_id=?)",
            (rid_int, st["id"], st["id"]))
        if not row:
            return NOTFOUND, err("request.not_found")
        return OK, {"ok": True, "request": decorate_requests([row])[0]}

    def student_request_delete(self, body):
        self._require("student")
        st = self._stud_record()
        rid = int(body.get("request_id", 0) or 0)
        if rid <= 0:
            return BAD, err("invalid_input")
        rel = self.db.q1("SELECT 1 FROM practice_requests WHERE id=? AND student_id=?", (rid, st["id"]))
        if not rel:
            return NOTFOUND, err("not_found")
        self.db.ex("INSERT OR IGNORE INTO hidden_requests(user_id, request_id, hidden_at) VALUES(?,?,?)",
                   (st["id"], rid, now()))
        return OK, {"ok": True}

    def student_requests_clear(self):
        self._require("student")
        st = self._stud_record()
        self.db.ex(
            "INSERT OR IGNORE INTO hidden_requests(user_id, request_id, hidden_at) "
            "SELECT ?, id, ? FROM practice_requests WHERE student_id=?",
            (st["id"], now(), st["id"]))
        return OK, {"ok": True}

    def student_history_delete(self, body):
        self._require("student")
        st = self._stud_record()
        sid = int(body.get("session_id", 0) or 0)
        if sid <= 0:
            return BAD, err("invalid_input")
        rel = self.db.q1(
            "SELECT 1 FROM session_students WHERE session_id=? AND student_id=? AND student_status='active'",
            (sid, st["id"]))
        if not rel:
            return NOTFOUND, err("not_found")
        self.db.ex("INSERT OR IGNORE INTO hidden_history(user_id, session_id, hidden_at) VALUES(?,?,?)",
                   (st["id"], sid, now()))
        return OK, {"ok": True}

    def student_history_clear(self):
        self._require("student")
        st = self._stud_record()
        self.db.ex(
            "INSERT OR IGNORE INTO hidden_history(user_id, session_id, hidden_at) "
            "SELECT ?, ss.session_id, ? FROM session_students ss "
            "JOIN lesson_sessions ls ON ls.id=ss.session_id "
            "WHERE ss.student_id=? AND ss.student_status='active' AND ls.status IN ('completed','cancelled')",
            (st["id"], now(), st["id"]))
        return OK, {"ok": True}

    def student_request_create(self, body):
        self._require("student")
        st = self._stud_record()
        date = str(body.get("preferred_date", "")).strip()
        start = str(body.get("preferred_start_time", "")).strip()
        end = str(body.get("preferred_end_time", "")).strip()
        msg = str(body.get("message", "")).strip()
        if start and end or (not start and not end):
            pass
        if date and not parse_date(date):
            return BAD, err("invalid_date")
        if start and end:
            if validate_time_range(start, end):
                return BAD, err("invalid_time")
        rid = self.db.ex(
            """INSERT INTO practice_requests(student_id, preferred_date, preferred_start_time, preferred_end_time, message, status, created_at)
               VALUES(?,?,?,?,?,'pending',?)""",
            (st["id"], date, start, end, msg, now()))
        admins = self.db.q("SELECT id FROM users WHERE role='admin' AND deleted_at IS NULL")
        for a in admins:
            notify(self.db, a["id"], "request.new", f"{self.user['first_name']} {self.user['last_name']} mashg'ulot so'radi", "request",
               {"request_id": rid, "student_name": f"{self.user['first_name']} {self.user['last_name']}".strip()},
               sender_id=self.user["id"], sender_role=self.user["role"])
        return OK, {"ok": True, "id": rid}

    # ------------------------------------------------------------ ichki router
    def public_config(self):
        """MODUL 4 — `GET /api/config`: OMMAVIY sozlamalar (KIRISH KERAK EMAS).

        Bu frontend ilk ochilishida (login sahifasida ham) chaqiriladi, shuning
        uchun sessiya talab qilinmaydi. Qaytariladigan yagona narsa — xarita
        sozlamalari: Yandex Maps JS API kaliti (bu kalit ommaviy — brauzerda
        ko'rinishi shart) va xarita markazi (Toshkent).

        Parol, token yoki boshqa sirli ma'lumot shu endpoint orqali
        QAYTMAYDI — qaytariladigan kalit faqat `YANDEX_MAPS_API_KEY`.
        """
        return OK, {"ok": True, "config": {"maps": public_map_config()}}

    def route(self, method: str, path: str, query: dict, body: dict):
        seg = [urllib.parse.unquote(s) for s in path.strip("/").split("/")]
        try:
            return self._dispatch(method, seg, query, body)
        except ApiError as e:
            return e.status, err(e.code, e.params)
        except ValueError:
            return BAD, err("invalid_input")
        except Exception as ex:  # pragma: no cover
            import traceback
            traceback.print_exc()
            return 500, {"ok": False, "error": "server_error", "message": str(ex)}

    def _dispatch(self, method, seg, query, body):
        # MODUL 4: ommaviy sozlamalar — sessiyasiz, rolda qat'i nazar.
        if seg[0] == "config":
            if method == "GET" and len(seg) == 1: return self.public_config()
            return NOTFOUND, err("not_found")
        if seg[0] == "auth":
            if method == "POST" and seg[1] == "login": return self.auth_login(body)
            if method == "POST" and seg[1] == "logout": return self.auth_logout()
            if method == "GET" and seg[1] == "me": return self.me()
            if method == "POST" and seg[1] == "change-password": return self.auth_change_password(body)
            if method == "POST" and seg[1] == "request-password-reset": return self.auth_request_reset(body)
            if method == "POST" and seg[1] == "reset-password": return self.auth_reset_password(body)
        if seg[0] == "me":
            if method == "GET" and len(seg) == 1: return self.me()
            if method == "GET" and len(seg) == 2 and seg[1] == "notifications": return self.me_notifications(query)
            if method == "GET" and len(seg) == 3 and seg[1] == "notifications":
                return self.me_notification_detail(seg[2])
            if method == "POST" and len(seg) == 3 and seg[1] == "notifications" and seg[2] == "read": return self.me_notifications_read(body)
            if method == "POST" and len(seg) == 3 and seg[1] == "notifications" and seg[2] == "delete": return self.me_notifications_delete(body)
            if method == "POST" and len(seg) == 3 and seg[1] == "notifications" and seg[2] == "clear": return self.me_notifications_clear()
            if method == "GET" and seg[1] == "settings": return self.me_settings_get()
            if method == "PUT" and len(seg) == 2 and seg[1] == "settings": return self.me_settings_put(body)
            if method == "GET" and seg[1] == "sessions": return self.me_sessions()
            if method == "POST" and len(seg) == 3 and seg[1] == "sessions" and seg[2] == "revoke": return self.me_session_revoke(body)
            if method == "POST" and len(seg) == 3 and seg[1] == "sessions" and seg[2] == "revoke-all": return self.me_sessions_revoke_all()
            if method == "GET" and seg[1] == "messages": return self.me_messages(query)
            if method == "POST" and seg[1] == "messages": return self.me_send_message(body)
            if method == "PUT" and seg[1] == "profile" and len(seg) == 2: return self.me_update_profile(body)
            if method == "PUT" and len(seg) == 3 and seg[1] == "profile" and seg[2] == "avatar": return self.me_update_avatar(body)
            if method == "POST" and len(seg) == 3 and seg[1] == "2fa":
                if seg[2] == "enable": return self.me_2fa_enable(body)
                if seg[2] == "verify-enable": return self.me_2fa_verify_enable(body)
                if seg[2] == "disable": return self.me_2fa_disable(body)
        if seg[0] == "admin":
            return self._admin(method, seg[1:], query, body)
        # VAZIFA 1 — hisobot yaratish (fayl yuklab olish).
        # Alohida prefiks: "reports" admin ichida emas, ochiqroq manzil.
        if seg[0] == "reports" and method == "POST" and len(seg) == 2 and seg[1] == "generate":
            return self.reports_generate(body)
        if seg[0] == "instructor":
            return self._instructor(method, seg[1:], query, body)
        if seg[0] == "student":
            return self._student(method, seg[1:], query, body)
        return NOTFOUND, err("not_found")

    def _admin(self, method, seg, query, body):
        self._require("admin")
        if not seg:
            if method == "GET": return self.admin_dashboard()
        if seg[0] == "dashboard": return self.admin_dashboard()
        if seg[0] == "users":
            if len(seg) == 1:
                if method == "GET": return self.admin_users(query)
                if method == "POST": return self.admin_user_create(body)
            if seg[1] == "bulk" and method == "POST": return self.admin_users_bulk(body)
            # MODUL 6: ommaviy tahrirlash va ommaviy o'chirish
            if len(seg) == 2 and seg[1] == "bulk-update" and method == "POST":
                return self.admin_users_bulk_update(body)
            if len(seg) == 2 and seg[1] == "bulk-delete" and method == "POST":
                return self.admin_users_bulk_delete(body)
            # BAND 3: jami mashg'ulotlar soni (bitta talaba | barcha talabalar)
            if len(seg) == 2 and seg[1] == "total-lessons" and method == "POST":
                return self.admin_user_total_lessons(body)
            if len(seg) == 2:
                uid = seg[1]
                if method == "PUT": return self.admin_users_update(body, uid)
                if method == "GET": return self.admin_user_profile(uid)
                if method == "DELETE": return self.admin_user_delete(uid)
            if len(seg) == 3 and seg[2] == "status": return self.admin_users_status(body, seg[1])
            if len(seg) == 3 and seg[2] == "reset-password": return self.admin_user_reset_password(seg[1], body)
            # MODUL 5: login + parolni KO'RISH va BIRGA o'zgartirish
            if len(seg) == 3 and seg[2] == "credentials":
                if method == "GET": return self.admin_user_credentials_get(seg[1])
                if method == "PUT": return self.admin_user_credentials_set(seg[1], body)
        if seg[0] == "students" and len(seg) >= 2 and seg[1] == "import" and method == "POST":
            return self.admin_import_students(body)
        if seg[0] == "cars":
            if len(seg) == 1:
                if method == "GET": return self.admin_cars(query)
                if method == "POST": return self.admin_cars_create(body)
            if len(seg) == 2:
                if method == "PUT": return self.admin_cars_update(body, seg[1])
                if method == "DELETE": return self.admin_cars_delete(seg[1])
            if len(seg) == 3 and seg[2] == "status" and method == "PUT":
                return self.admin_cars_status(body, seg[1])
            if len(seg) == 3 and seg[2] == "photos" and method == "POST":
                return self.admin_car_photos_add(body, seg[1])
            if len(seg) == 4 and seg[2] == "photos" and method == "DELETE":
                return self.admin_car_photos_remove(seg[1], seg[3])
        if seg[0] == "instructors":
            if len(seg) == 1 and method == "GET":
                return self.admin_instructors_list()
            if len(seg) == 3 and seg[2] == "car":
                return self.admin_instructor_assign_car(body, seg[1])
        if seg[0] == "sessions":
            if len(seg) == 1:
                if method == "GET": return self.admin_sessions(query)
                if method == "POST": return self.admin_session_create(body)
            if len(seg) == 2:
                if method == "GET": return self.admin_session_detail(seg[1])
                if method == "POST" and seg[1] == "calendar":  # not used
                    pass
            if len(seg) == 3:
                if seg[2] == "reschedule": return self.admin_session_reschedule(body, seg[1])
                if seg[2] == "cancel": return self.admin_session_cancel(body, seg[1])
                if seg[2] == "students":
                    if method == "POST": return self.admin_session_add_student(body, seg[1])
                    if method == "GET": return self.admin_session_detail(seg[1])
                if seg[2] == "move-student": return self.admin_session_move_student(body, seg[1])
                if seg[2] == "notes": return self.admin_session_notes(body, seg[1])
            if len(seg) == 4 and seg[2] == "students" and method in ("PUT", "DELETE"):
                if method == "PUT": return self.admin_session_update_student(body, seg[1], seg[3])
                return self.admin_session_remove_student(seg[1], seg[3])
        if seg[0] == "calendar": return self.admin_calendar(query)
        if seg[0] == "requests":
            if len(seg) == 1 and method == "GET": return self.admin_requests(query)
            if len(seg) == 2 and method == "GET":
                return self.admin_request_detail(seg[1])
            if len(seg) == 3:
                if seg[2] == "approve": return self.admin_request_approve(body, seg[1])
                if seg[2] == "reject": return self.admin_request_reject(body, seg[1])
                if seg[2] == "cancel": return self.admin_request_cancel(seg[1])
        if seg[0] == "notifications":
            if len(seg) == 1:
                if method == "GET": return self.admin_notifications()
                if method == "POST": return self.admin_send_notification(body)
        if seg[0] == "reports": return self.admin_reports(query)
        if seg[0] == "analytics": return self.admin_analytics(query)
        if seg[0] == "export": return self.admin_export(query)
        if seg[0] == "backup":
            if method == "POST":
                # restore or create?
                if body and body.get("action") == "restore":
                    return self.admin_backup_restore(body)
                return self.admin_backup_create()
            if method == "GET":
                if query.get("download"):
                    return self.admin_backup_download(str(query.get("download")))
                return self.admin_backup_list()
            if method == "DELETE":
                return self.admin_backup_delete(str(query.get("name") or ""))
        if seg[0] == "audit": return self.admin_audit(query)
        if seg[0] == "settings":
            if method == "GET": return self.admin_settings_get()
            if method == "PUT": return self.admin_settings_put(body)
        if seg[0] == "translations":
            if method == "GET":
                return OK, {"ok": True, "translations": self.db.q("SELECT * FROM translations")}
            if method == "PUT":
                for item in body.get("items", []):
                    self.db.ex(
                        "INSERT INTO translations(key,uz,ru,en) VALUES(?,?,?,?) ON CONFLICT(key) DO UPDATE SET uz=excluded.uz, ru=excluded.ru, en=excluded.en",
                        (item.get("key", ""), item.get("uz", ""), item.get("ru", ""), item.get("en", "")))
                return OK, {"ok": True}
        return NOTFOUND, err("not_found")

    def admin_instructors_list(self):
        """Instruktorlar ro'yxati + ularning avtomobillari (session formasi uchun)."""
        rows = self.db.q(
            """SELECT u.id AS user_id, u.login, u.first_name, u.last_name, u.phone, u.profile_image,
                      u.status AS user_status, i.*
               FROM instructors i JOIN users u ON u.id=i.user_id
               WHERE u.deleted_at IS NULL ORDER BY u.last_name""")
        out = []
        for r in rows:
            rec = dict(r)
            for k in ("work_days",):
                rec[k] = jload(rec.get(k), []) if rec.get(k) else []
            if rec.get("assigned_car_id"):
                car = self.db.q1(
                    "SELECT id, brand, model, plate_number, practice_capacity, status FROM cars WHERE id=? AND deleted_at IS NULL",
                    (rec["assigned_car_id"],))
                rec["car"] = car
            else:
                rec["car"] = None
            out.append(rec)
        return OK, {"ok": True, "instructors": out}

    def _instructor(self, method, seg, query, body):
        self._require("instructor")
        if not seg:
            if method == "GET": return self.instructor_context()
        if seg[0] == "context": return self.instructor_context()
        if seg[0] == "home": return self.instructor_home()
        if seg[0] == "today": return self.instructor_today()
        if seg[0] == "schedule": return self.instructor_schedule(query)
        if seg[0] == "students": return self.instructor_students()
        if seg[0] == "car":
            if method == "GET": return self.instructor_car()
            if method == "PUT": return self.instructor_car_update(body)
        if seg[0] == "sessions":
            if len(seg) == 2:
                if method == "GET": return self.instructor_session_detail(seg[1])
            if len(seg) == 3:
                if seg[2] == "start": return self.instructor_start(seg[1])
                if seg[2] == "finish": return self.instructor_finish(seg[1])
                if seg[2] == "attendance": return self.instructor_attendance(body, seg[1])
                if seg[2] == "cancel": return self.instructor_session_cancel(body, seg[1])
                if seg[2] == "reschedule": return self.instructor_session_reschedule(body, seg[1])
                if seg[2] == "remind": return self._instructor_remind(seg[1])
        return NOTFOUND, err("not_found")

    def _instructor_remind(self, sid):
        """In-app xabar + tel:// orqali qo'ng'iroq — frontendda amalga oshiriladi.
        Shu yerda faqat tasdiqlash uchun."""
        return OK, {"ok": True}

    def _student(self, method, seg, query, body):
        if not seg:
            if method == "GET": return self.student_context()
        if seg[0] == "context": return self.student_context()
        if seg[0] == "home": return self.student_home()
        if seg[0] == "today": return self.student_today()
        if seg[0] == "next": return self.student_next()
        if seg[0] == "sessions":
            if len(seg) == 1 and method == "GET": return self.student_sessions(query)
            if len(seg) == 2 and method == "GET": return self.student_session_detail(seg[1])
            if len(seg) == 3 and seg[2] == "pickup": return self.student_update_pickup(body, seg[1])
        if seg[0] == "requests":
            if len(seg) == 1:
                if method == "GET": return self.student_requests(query)
                if method == "POST": return self.student_request_create(body)
            if len(seg) == 2:
                if seg[1] == "delete" and method == "POST": return self.student_request_delete(body)
                if seg[1] == "clear" and method == "POST": return self.student_requests_clear()
                if method == "GET": return self.student_request_detail(seg[1])
        if seg[0] == "history":
            if len(seg) == 2:
                if seg[1] == "delete" and method == "POST": return self.student_history_delete(body)
                if seg[1] == "clear" and method == "POST": return self.student_history_clear()
        return NOTFOUND, err("not_found")

    def _require(self, role: str):
        if not self.user:
            raise ApiError(UNAUTH, "auth.required")
        if self.user["role"] != role:
            raise ApiError(FORBIDDEN, "forbidden")


class ApiError(Exception):
    def __init__(self, status: int, code: str, params: dict = None):
        super().__init__(code)
        self.status = status
        self.code = code
        self.params = params or {}


def err(code: str, params: dict = None):
    return {"ok": False, "error": code, "params": params or {}}


# ------------------------------------------------------------------- TOTP (2FA)
def _b32(key: str) -> bytes:
    """Base32 kalitni dekodlash (to'ldirish (padding) bardoshli)."""
    key = key.upper().strip().replace(" ", "")
    pad = (8 - len(key) % 8) % 8
    return base64.b32decode(key + "=" * pad)


def totp_code(secret: str, t: int = None, step: int = 30, digits: int = 6) -> str:
    """RFC 6238: HMAC-SHA1 asosidagi vaqt-cheklangan kod."""
    if t is None:
        t = int(_time.time())
    key = _b32(secret)
    msg = struct.pack(">Q", t // step)
    digest = hmac.new(key, msg, hashlib.sha1).digest()
    o = digest[19] & 0x0F
    return str((struct.unpack(">I", digest[o:o + 4])[0] & 0x7FFFFFFF) % (10 ** digits)).zfill(digits)


def verify_totp(secret: str, code: str, window: int = 1) -> bool:
    """Kodni ±window*30 soniya oynasida tekshiradi."""
    if not secret or not code:
        return False
    now_i = int(_time.time())
    for i in range(-window, window + 1):
        if totp_code(secret, t=now_i + i * 30) == str(code).strip():
            return True
    return False


def _new_totp_secret() -> str:
    return base64.b32encode(os.urandom(20)).decode().rstrip("=")


def user_public(u) -> dict:
    # `password_enc` — shifrlangan parol. Hech qanday ro'yxat/profil
    # javobida chiqmaydi: faqat `admin_user_credentials_get` orqali,
    # va o'shanda `admin` roli bilan, onaylangan holda.
    out = {k: v for k, v in dict(u).items()
           if k not in ("password_hash", "password_enc", "totp_secret")}
    return out


# BAND 16: talaba/instruktor uchun maxfiy maydonlar. "Ro'yxatga olingan sana"
# (`enrolled_at`) DB'da saqlanib qoladi, lekin talabaga/instruktorga
# YUBORILMAYDI — faqat admin endpoint'lari orqali olinadi.
STUDENT_PRIVATE_FIELDS = ("enrolled_at",)


def student_private(st) -> dict:
    out = dict(st)
    for f in STUDENT_PRIVATE_FIELDS:
        out.pop(f, None)
    return out


def notif_legacy(db, user_id: int) -> dict:
    """`notification_settings` -> eski kategoriya shakli (`user_settings.notif`).

    Eski frontend (notifSettingsCard) `settings.notif.lesson` kabi kalitlarni
    o'qiydi — shuning uchun eski shakl saqlanadi, yangi jadval esa MANBA.
    """
    return legacy_flags(db, user_id)


import os  # noqa: E402  bu BACKUP_DIR uchun


def configure(db_path: str, data_dir: str, backup_dir: str):
    global DB_PATH, DATA_DIR, BACKUP_DIR
    DB_PATH = db_path
    DATA_DIR = data_dir
    BACKUP_DIR = backup_dir