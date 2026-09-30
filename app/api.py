"""REST API router — barcha rollar (admin/talaba/instruktor) uchun.
RBAC: har bir endpointda foydalanuvchi roli tekshiriladi.
Barcha biznes qoidalar backendda majburiy bajariladi (app/rules.py).
"""
import base64
import csv
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
    create_session, destroy_session, get_session_user, hash_password,
    verify_password, new_token, login_allowed, reset_login_attempts,
)
from .db import init_db, now, today, jload, jdump, next_credentials, Db
from .rules import check_session_rules, session_auto_data, parse_date, validate_time_range
from .notify import notify, notify_session_participants, audit, DEFAULT_NOTIF
from .export import export_table
from . import export as expmod

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


def _platform_setting(db, key: str, default=None):
    """system_settings'da saqlangan platforma sozlamasini qaytaradi (default bilan)."""
    row = db.q1("SELECT value FROM system_settings WHERE key=?", (key,))
    if row is None:
        return DEFAULT_PLATFORM_SETTINGS.get(key, default)
    val = jload(row["value"], DEFAULT_PLATFORM_SETTINGS.get(key, default))
    return val if val is not None else default


def ensure_reminders(db) -> int:
    """Platforma 'reminder_minutes' sozlamasi bo'yicha yaqinlashayotgan
    mashg'ulotlar uchun eslatma bildirishnomalari yuboradi (M12).

    Har bir mashg'ulot uchun kuniga bitta eslatma ('reminder_log' yozuvi).
    Yuborilgan eslatmalar sonini qaytaradi.
    """
    import datetime as _dt
    try:
        minutes = int(_platform_setting(db, "reminder_minutes", 60) or 60)
    except (TypeError, ValueError):
        minutes = 60
    minutes = max(minutes, 1)
    td = _dt.date.today()
    now_dt = _dt.datetime.now().replace(second=0, microsecond=0)
    window_end = now_dt + _dt.timedelta(minutes=minutes)
    rows = db.q(
        "SELECT id, date, start_time, end_time, instructor_id FROM lesson_sessions "
        "WHERE date=? AND status!='cancelled'", (td.strftime("%Y-%m-%d"),))
    log_row = db.q1("SELECT value FROM system_settings WHERE key='reminder_log'")
    log = jload(log_row["value"], {}) if log_row else {}
    log = log if isinstance(log, dict) else {}
    sent_n = 0
    for r in rows:
        try:
            sh, sm = map(int, r["start_time"].split(":"))
            start_dt = _dt.datetime(td.year, td.month, td.day, sh, sm)
        except Exception:
            continue
        if not (now_dt <= start_dt <= window_end):
            continue
        marker = r["date"] + " " + r["start_time"]
        if log.get(str(r["id"])) == marker:
            continue  # allaqachon yuborilgan
        info = f"{r['date']} {r['start_time']}-{r['end_time']}"
        rdata = {"session_id": r["id"], "verb": "reminder",
                 "date": r["date"], "start_time": r["start_time"], "end_time": r["end_time"]}
        inst = db.q1(
            "SELECT u.id AS uid FROM instructors i JOIN users u ON u.id=i.user_id WHERE i.id=?",
            (r["instructor_id"],))
        if inst:
            notify(db, inst["uid"], "lesson.reminder", info, "reminder", rdata)
            sent_n += 1
        students = db.q(
            """SELECT u.id AS uid FROM session_students ss JOIN students s ON s.id=ss.student_id
               JOIN users u ON u.id=s.user_id
               WHERE ss.session_id=? AND ss.student_status='active'""", (r["id"],))
        for s in students:
            notify(db, s["uid"], "lesson.reminder", info, "reminder", rdata)
            sent_n += 1
        log[str(r["id"])] = marker
    db.ex(
        "INSERT INTO system_settings(key,value,updated_at) VALUES('reminder_log',?,?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
        (jdump(log), now()))
    return sent_n


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

    # ------------------------------------------------------------------ auth
    def auth_login(self, body):
        login = str(body.get("login", "")).strip()
        password = str(body.get("password", ""))
        role = str(body.get("role", "")).strip()
        remember = bool(body.get("remember"))
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
        # Tab'ga xos rejim: cookie'ga qurilma kaliti yoziladi (HttpOnly), sessiya
        # esa shu qurilma + shu tab birligidan yaratiladi. Shunda boshqa tab'
        # kirganda bu tab'ning sessiyasi buzilmaydi.
        token = create_session(self.db, u["id"], remember, tab=self.tab, device=self.token or None)
        if self.tab and self.token:
            # Eski rejimda yaratilgan sessiya qoldig'ini tozalaymiz
            # (cookie qiymati endi qurilma kaliti sifatida ishlatiladi).
            destroy_session(self.db, self.token)
        self.db.upd("UPDATE users SET last_login_at=? WHERE id=?", (now(), u["id"]))
        return OK, {"ok": True, "token": token, "user": user_public(u)}

    def auth_logout(self):
        destroy_session(self.db, self.token, self.tab)
        return OK, {"ok": True}

    def auth_change_password(self, body):
        if not self.user:
            return UNAUTH, err("auth.required")
        old = body.get("old_password", "") if not self.user["must_change_password"] else None
        new = body.get("new_password", "")
        if old is not None and not verify_password(old, self.user["password_hash"]):
            return BAD, err("auth.wrong_old_password")
        if len(new) < 5:
            return BAD, err("auth.password_short")
        self.db.upd(
            "UPDATE users SET password_hash=?, must_change_password=0, updated_at=? WHERE id=?",
            (hash_password(new), now(), self.user["id"]),
        )
        return OK, {"ok": True}

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
        if len(newpass) < 5:
            return BAD, err("auth.password_short")
        self.db.upd("UPDATE users SET password_hash=?, updated_at=? WHERE id=?", (hash_password(newpass), now(), row["user_id"]))
        self.db.upd("UPDATE password_reset_tokens SET used_at=? WHERE id=?", (now(), row["id"]))
        return OK, {"ok": True}

    # ------------------------------------------------------------ me (barcha)
    def me(self):
        if not self.user:
            return UNAUTH, err("auth.required")
        u = user_public(self.user)
        extra = {"unread": self.db.q1("SELECT COUNT(*) c FROM notifications WHERE user_id=? AND is_read=0", (self.user["id"],))["c"]}
        if u["role"] == "student":
            st = self.db.q1("SELECT * FROM students WHERE user_id=?", (self.user["id"],))
            if st:
                extra["student"] = st
        elif u["role"] == "instructor":
            inst = self.db.q1("SELECT * FROM instructors WHERE user_id=?", (self.user["id"],))
            if inst:
                extra["instructor"] = inst
                car = self.db.q1("SELECT * FROM cars WHERE id=?", (inst["assigned_car_id"],)) if inst["assigned_car_id"] else None
                if car:
                    extra["car"] = car
        return OK, {"ok": True, "user": u, **extra}

    def me_notifications(self):
        if not self.user:
            return UNAUTH, err("auth.required")
        rows = self.db.q(
            """SELECT n.*, su.first_name AS sender_first_name, su.last_name AS sender_last_name,
                      su.profile_image AS sender_profile_image
               FROM notifications n LEFT JOIN users su ON su.id=n.sender_id
               WHERE n.user_id=? ORDER BY n.id DESC LIMIT 100""", (self.user["id"],)
        )
        return OK, {"ok": True, "notifications": rows}

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

    # ---- M12: shaxsiy sozlamalar (til / tema / bildirishnomalar) ----

    def me_settings_get(self):
        if not self.user:
            return UNAUTH, err("auth.required")
        rows = self.db.q("SELECT key, value FROM user_settings WHERE user_id=?", (self.user["id"],))
        s = {r["key"]: jload(r["value"], {}) for r in rows}
        notif = s.get("notif")
        notif = notif if isinstance(notif, dict) else {}
        return OK, {"ok": True, "settings": {
            "lang": s.get("lang", ""),
            "theme": s.get("theme", ""),
            "notif": {**DEFAULT_NOTIF, **notif},
        }}

    def me_settings_put(self, body):
        if not self.user:
            return UNAUTH, err("auth.required")
        uid = self.user["id"]
        t = now()

        def _upsert(key_f, value, ok):
            if ok:
                self.db.ex(
                    "INSERT INTO user_settings(user_id,key,value,updated_at) VALUES(?,?,?,?) "
                    "ON CONFLICT(user_id,key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
                    (uid, key_f, jdump(value), t))

        if "lang" in body:
            lang = str(body["lang"]).strip()
            _upsert("lang", lang, lang in ("uz", "ru", "en"))
        if "theme" in body:
            theme = str(body["theme"]).strip()
            _upsert("theme", theme, theme in ("light", "dark", "system"))
        if isinstance(body.get("notif"), dict):
            row = self.db.q1("SELECT value FROM user_settings WHERE user_id=? AND key='notif'", (uid,))
            cur = jload(row["value"], {}) if row else {}
            cur = cur if isinstance(cur, dict) else {}
            n = {k: bool(v) for k, v in body["notif"].items() if k in DEFAULT_NOTIF}
            _upsert("notif", {**DEFAULT_NOTIF, **cur, **n}, True)
        return OK, {"ok": True}

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

    def me_update_profile(self, body):
        if not self.user:
            return UNAUTH, err("auth.required")
        fields = {}
        for f in ("phone", "first_name", "last_name", "middle_name"):
            if f in body and body[f] is not None:
                fields[f] = str(body[f]).strip()
        if fields:
            fields["updated_at"] = now()
            self.db.upd("UPDATE users SET " + ", ".join(f"{k}=?" for k in fields) + " WHERE id=?",
                        (*fields.values(), self.user["id"]))
        return OK, {"ok": True}

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
        where = ["deleted_at IS NULL"]
        params = []
        if query.get("role"):
            where.append("role=?")
            params.append(query["role"])
        if query.get("status"):
            where.append("status=?")
            params.append(query["status"])
        if query.get("q"):
            where.append("(first_name LIKE ? OR last_name LIKE ? OR login LIKE ? OR phone LIKE ?)")
            p = "%" + query["q"] + "%"
            params += [p, p, p, p]
        rows = self.db.q(
            "SELECT * FROM users WHERE " + " AND ".join(where) + " ORDER BY id DESC LIMIT 500", params
        )
        out = [user_public(r) for r in rows]

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
                total = p["total"] or 0
                done = p["done"] or 0
                prog[p["sid"]] = {
                    "total": total, "done": done,
                    "pct": round(done * 100 / total) if total else 0,
                }

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
                    u["progress"] = prog.get(s["id"], {"total": 0, "done": 0, "pct": 0})
                    u["instructors"] = inst_of.get(s["id"], [])
            elif u["role"] == "instructor":
                i_ = inst_by_uid.get(u["id"])
                u["instructor"] = i_
                if i_:
                    u["students_count"] = stud_count.get(i_["id"], 0)
                if i_ and i_["assigned_car_id"]:
                    c = self.db.q1("SELECT id, brand, model, plate_number, practice_capacity, status FROM cars WHERE id=?", (i_["assigned_car_id"],))
                    u["car"] = c
        return OK, {"ok": True, "users": out}

    def admin_user_create(self, body):
        self._require("admin")
        role = body.get("role")
        if role not in ("student", "instructor"):
            return BAD, err("user.invalid_role")
        db = self.db
        created = db.transaction(lambda c: self._create_user_tx(c, body, role))
        audit(db, self.user["id"], "user created", "users", created["user"]["id"], {"login": created["user"]["login"], "role": role})
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
                                 login,password_hash,role,status,profile_image,must_change_password,
                                 created_at,updated_at)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (first, last, str(body.get("middle_name", "")).strip(),
             str(body.get("birth_date", "")).strip(), str(body.get("gender", "")).strip(),
             str(body.get("phone", "")).strip(), str(body.get("secondary_phone", "")).strip(),
             login, hash_password(password), role, "active",
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
        else:
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
        if st not in ("block", "unblock", "archive"):
            return BAD, err("user.bad_status")
        new_status = {"block": "blocked", "unblock": "active", "archive": "archived"}[st]
        u = self.db.q1("SELECT * FROM users WHERE id=?", (int(uid),))
        if not u:
            return NOTFOUND, err("user.not_found")
        if u["role"] == "admin":
            return BAD, err("user.cannot_modify_admin")
        self.db.upd("UPDATE users SET status=?, updated_at=? WHERE id=?", (new_status, now(), int(uid)))
        if new_status == "blocked":
            self.db.upd("DELETE FROM sessions_ring WHERE user_id=?", (int(uid),))
        audit(self.db, self.user["id"], f"user {new_status}", "users", int(uid))
        return OK, {"ok": True}

    def admin_user_reset_password(self, uid):
        self._require("admin")
        u = self.db.q1("SELECT * FROM users WHERE id=? AND deleted_at IS NULL", (int(uid),))
        if not u:
            return NOTFOUND, err("user.not_found")
        newpass = new_token(12)
        self.db.upd(
            "UPDATE users SET password_hash=?, must_change_password=1, updated_at=? WHERE id=?",
            (hash_password(newpass), now(), int(uid)),
        )
        audit(self.db, self.user["id"], "password reset", "users", int(uid))
        return OK, {"ok": True, "login": u["login"], "password": newpass}

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
        if "pickup_lat" in body: upd["pickup_lat"] = float(body["pickup_lat"]) if body["pickup_lat"] else None
        if "pickup_lng" in body: upd["pickup_lng"] = float(body["pickup_lng"]) if body["pickup_lng"] else None
        if "notes" in body: upd["notes"] = str(body["notes"]).strip()
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
    def admin_requests(self, query):
        self._require("admin")
        rows = self.db.q(
            """SELECT r.*, u.first_name, u.last_name, u.phone, u.profile_image, s.group_name
               FROM practice_requests r JOIN students s ON s.id=r.student_id
               JOIN users u ON u.id=s.user_id
               ORDER BY (r.status='pending') DESC, r.id DESC LIMIT 300""")
        return OK, {"ok": True, "requests": rows}

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
        self._require("admin")
        role = body.get("role") or None
        title = str(body.get("title", "")).strip()
        text = str(body.get("text", "")).strip()
        if not text:
            return BAD, err("notif.empty")
        if role:
            users = self.db.q("SELECT id FROM users WHERE role=? AND status='active' AND deleted_at IS NULL", (role,))
        else:
            users = self.db.q("SELECT id FROM users WHERE status='active' AND deleted_at IS NULL")
        for u in users:
            notify(self.db, u["id"], title or "message", text, "admin",
                   sender_id=self.user["id"], sender_role="admin")
        audit(self.db, self.user["id"], "notification sent", None, None, {"role": role, "count": len(users)})
        return OK, {"ok": True, "count": len(users)}

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
        import shutil
        if not BACKUP_DIR:
            return BAD, err("backup.disabled")
        name = f"backup_{today().replace('-', '')}_{now().replace(':', '').replace(' ', '_')}.db"
        path = os.path.join(BACKUP_DIR, name)
        shutil.copy2(DB_PATH, path)
        audit(self.db, self.user["id"], "backup created", "backup", None, {"file": name})
        return OK, {"ok": True, "file": name, "size": os.path.getsize(path)}

    def admin_backup_list(self):
        self._require("admin")
        if not BACKUP_DIR or not os.path.isdir(BACKUP_DIR):
            return OK, {"ok": True, "backups": []}
        files = sorted(os.listdir(BACKUP_DIR), reverse=True)[:30]
        out = [{"name": f, "size": os.path.getsize(os.path.join(BACKUP_DIR, f)),
                "time": os.path.getmtime(os.path.join(BACKUP_DIR, f))} for f in files]
        return OK, {"ok": True, "backups": out}

    # ---- audit
    def admin_audit(self, query):
        self._require("admin")
        where = []
        params = []
        if query.get("action"):
            where.append("action LIKE ?")
            params.append("%" + query["action"] + "%")
        rows = self.db.q(
            "SELECT * FROM audit_logs WHERE " + (" AND ".join(where) if where else "1=1") +
            " ORDER BY id DESC LIMIT 400", params)
        return OK, {"ok": True, "logs": rows}

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
        return OK, {"ok": True, "weekly": agg(wk_rows), "overall": agg(rows),
                    "progress": progress, "next": nxt}

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
        self._require("student")
        st = self._stud_record()
        up = query.get("upcoming", "1")
        if up == "1":
            rows = self.db.q(
                """SELECT ls.*, u.first_name||' '||u.last_name AS instructor_name, u.phone AS instructor_phone,
                          ss.pickup_address, ss.pickup_lat, ss.pickup_lng, ss.attendance_status,
                          (SELECT COUNT(*) FROM session_students s2 WHERE s2.session_id=ls.id AND s2.student_status='active') AS student_count
                   FROM session_students ss JOIN lesson_sessions ls ON ls.id=ss.session_id
                   JOIN instructors i ON i.id=ls.instructor_id JOIN users u ON u.id=i.user_id
                   WHERE ss.student_id=? AND ss.student_status='active' AND ls.status IN ('scheduled','ongoing')
                   ORDER BY ls.date, ls.start_time""", (st["id"],))
        else:
            rows = self.db.q(
                """SELECT ls.*, u.first_name||' '||u.last_name AS instructor_name, u.phone AS instructor_phone,
                          ss.pickup_address, ss.attendance_status,
                          (SELECT COUNT(*) FROM session_students s2 WHERE s2.session_id=ls.id AND s2.student_status='active') AS student_count
                   FROM session_students ss JOIN lesson_sessions ls ON ls.id=ss.session_id
                   JOIN instructors i ON i.id=ls.instructor_id JOIN users u ON u.id=i.user_id
                   WHERE ss.student_id=? AND ss.student_status='active' AND ls.status IN ('completed','cancelled')
                     AND ls.id NOT IN (SELECT session_id FROM hidden_history WHERE user_id=?)
                   ORDER BY ls.date DESC, ls.start_time DESC LIMIT 200""", (st["id"], st["id"]))
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
        return OK, {"ok": True, "session": row}

    def student_update_pickup(self, body, sid):
        self._require("student")
        st = self._stud_record()
        upd = self.db.upd(
            """UPDATE session_students SET pickup_address=?, pickup_lat=?, pickup_lng=?
               WHERE id=(SELECT id FROM session_students WHERE session_id=? AND student_id=? AND student_status='active')""",
            (str(body.get("address", "")).strip(), body.get("lat"), body.get("lng"), int(sid), st["id"]))
        if upd == 0:
            return NOTFOUND, err("session.student_not_found")
        return OK, {"ok": True}

    def student_requests(self):
        self._require("student")
        st = self._stud_record()
        rows = self.db.q(
            "SELECT * FROM practice_requests WHERE student_id=? AND id NOT IN "
            "(SELECT request_id FROM hidden_requests WHERE user_id=?) ORDER BY id DESC",
            (st["id"], st["id"]))
        return OK, {"ok": True, "requests": rows}

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
        if seg[0] == "auth":
            if method == "POST" and seg[1] == "login": return self.auth_login(body)
            if method == "POST" and seg[1] == "logout": return self.auth_logout()
            if method == "GET" and seg[1] == "me": return self.me()
            if method == "POST" and seg[1] == "change-password": return self.auth_change_password(body)
            if method == "POST" and seg[1] == "request-password-reset": return self.auth_request_reset(body)
            if method == "POST" and seg[1] == "reset-password": return self.auth_reset_password(body)
        if seg[0] == "me":
            if method == "GET" and len(seg) == 1: return self.me()
            if method == "GET" and seg[1] == "notifications": return self.me_notifications()
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
            if len(seg) == 2:
                uid = seg[1]
                if method == "PUT": return self.admin_users_update(body, uid)
                if method == "DELETE": return self.admin_user_delete(uid)
            if len(seg) == 3 and seg[2] == "status": return self.admin_users_status(body, seg[1])
            if len(seg) == 3 and seg[2] == "reset-password": return self.admin_user_reset_password(seg[1])
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
            if method == "POST": return self.admin_backup_create()
            if method == "GET": return self.admin_backup_list()
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
                if method == "GET": return self.student_requests()
                if method == "POST": return self.student_request_create(body)
            if len(seg) == 2:
                if seg[1] == "delete" and method == "POST": return self.student_request_delete(body)
                if seg[1] == "clear" and method == "POST": return self.student_requests_clear()
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
    out = {k: v for k, v in dict(u).items() if k not in ("password_hash", "totp_secret")}
    return out


import os  # noqa: E402  bu BACKUP_DIR uchun


def configure(db_path: str, data_dir: str, backup_dir: str):
    global DB_PATH, DATA_DIR, BACKUP_DIR
    DB_PATH = db_path
    DATA_DIR = data_dir
    BACKUP_DIR = backup_dir