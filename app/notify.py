"""Bildirishnomalar (notifications) va audit log.

BAND 11/12/18 — BILDIRISHNOMA ARXITEKTURASI
    Har bir bildirishnoma o'zining MUSTAQIL DB record'i (`notifications`):
        id, user_id (recipient), type, source, title, body (message),
        created_at, read_at, related_lesson_id, created_by, data (metadata)

    `source` — bildirishnomaning TABIIATI. Aynan shu maydon "Xabarlar"
    bo'limida faqat haqiqiy admin xabarlarini ko'rsatish uchun ishlatiladi:

        ADMIN_MESSAGE       — admin yuborgan xabar (created_by = admin id)
        LESSON_REMINDER     — avtomatik 2-soat eslatma (created_by = NULL/SYSTEM)
        LESSON_ASSIGNED     — talabaga mashg'ulot biriktirildi
        LESSON_RESCHEDULED  — mashg'ulot vaqti ko'chirildi
        LESSON_CANCELLED    — mashg'ulot bekor qilindi
        LESSON_COMPLETED    — mashg'ulot yakunlandi
        PRACTICE_REQUEST    — mashg'ulotga yozilish so'rovi
        MESSAGE             — tizim ichi chat xabari
        SECURITY            — kirish/xavfsizlik hodisasi
        SYSTEM              — boshqa tizim hodisasi

    AVTОMATIK bildirishnomalar (LESSON_REMINDER, LESSON_ASSIGNED, ...)
    `source = ADMIN_MESSAGE` BO'LMAYDI — ya'ni "Xabarlar" kategoriyasida
    admin xabari sifatida chiqmaydi (BAND 12).

BAND 17 — BILDIRISHNOMA SOZLAMALARI
    `notification_settings` jadvali: har bir foydalanuvchi uchun alohida qator.
    Frontend'dagi toggle faqat dizayn emas — haqiqiy yoqish/yoqish shu
    jadvalga yoziladi va `notify()` shu qiymatlarni tekshiradi.
    Brauzer yopilgandan keyin ham, boshqa qurilmadan kirilganda ham saqlanadi.
"""
import threading

from .db import now, jdump, jload

# BAND 18 — manba (source) ro'yxati. Ro'yxatga qo'shilmagan manba "SYSTEM"
# deb hisoblanadi (yoki `notify()` da aniq beriladi).
SRC_ADMIN_MESSAGE = "ADMIN_MESSAGE"
SRC_LESSON_REMINDER = "LESSON_REMINDER"
SRC_LESSON_ASSIGNED = "LESSON_ASSIGNED"
SRC_LESSON_RESCHEDULED = "LESSON_RESCHEDULED"
SRC_LESSON_CANCELLED = "LESSON_CANCELLED"
SRC_LESSON_COMPLETED = "LESSON_COMPLETED"
SRC_PRACTICE_REQUEST = "PRACTICE_REQUEST"
SRC_MESSAGE = "MESSAGE"
SRC_SECURITY = "SECURITY"
SRC_SYSTEM = "SYSTEM"

SOURCES = (
    SRC_ADMIN_MESSAGE, SRC_LESSON_REMINDER, SRC_LESSON_ASSIGNED,
    SRC_LESSON_RESCHEDULED, SRC_LESSON_CANCELLED, SRC_LESSON_COMPLETED,
    SRC_PRACTICE_REQUEST, SRC_MESSAGE, SRC_SECURITY, SRC_SYSTEM,
)

# `notification_settings` ustunlari -> notif turi (kategoriya) xaritasi.
# `type` (eski kategoriya: lesson/cancel/request/message/security/reminder/admin)
# bo'yicha sozlanadi — chunki u frontend filtri bilan bog'liq.
_COL_ = {
    "lesson_reminders": ("reminder",),
    "lesson_status_updates": ("lesson", "cancel"),
    "admin_messages": ("admin",),
    "messages": ("message",),
    "requests": ("request",),
    "security": ("security",),
}

# Barcha ustunlar (default: yoqilgan)
DEFAULT_NOTIFICATION_SETTINGS = {
    "lesson_reminders": True,
    "admin_messages": True,
    "lesson_status_updates": True,
    "messages": True,
    "requests": True,
    "security": True,
}

# Eski `user_settings.notif` kalitlari bilan moslik (backward compatibility).
# `admin_messages` alohida turar: "message" kategoriyasi TIZIM ichi chat
# xabariga tegishli, "admin" esa platforma yuborgan e'lon.
_NOTIF_KEYS = {
    "lesson_reminders": "reminder",
    "lesson_status_updates": "lesson",
    "messages": "message",
    "requests": "request",
    "security": "security",
}

# Eski kodiqlar uchun qisqa nom (app/api.py `DEFAULT_NOTIF` sifatida).
# Kalitlar: kategoriya -> yoqilgan/yoniq. `admin` — admin e'lonlari.
DEFAULT_NOTIF = {
    "lesson": True,
    "request": True,
    "message": True,
    "security": True,
    "reminder": True,
    "admin": True,
}


def legacy_flags(db, user_id: int) -> dict:
    """Legacy kategoriya -> bool shakli (frontend `settings.notif.*`)."""
    cur = get_settings(db, user_id)
    out = {legacy: bool(cur.get(col, True)) for col, legacy in _NOTIF_KEYS.items()}
    out["admin"] = bool(cur.get("admin_messages", True))
    return out


def get_settings(db, user_id: int) -> dict:
    """Foydalanuvchining bildirishnoma sozlamalari (DB'dan, default bilan)."""
    row = db.q1("SELECT * FROM notification_settings WHERE user_id=?", (user_id,))
    out = dict(DEFAULT_NOTIFICATION_SETTINGS)
    if row:
        for k in DEFAULT_NOTIFICATION_SETTINGS:
            out[k] = bool(row.get(k, 1))
    else:
        # Eski bazalar: `user_settings.notif` dan ko'chiriladi.
        out = legacy_settings(db, user_id)
    return out


def legacy_settings(db, user_id: int) -> dict:
    """Eski `user_settings.notif` JSON'ini yangi semantika bilan qaytaradi."""
    out = dict(DEFAULT_NOTIFICATION_SETTINGS)
    row = db.q1("SELECT value FROM user_settings WHERE user_id=? AND key='notif'", (user_id,))
    if not row:
        return out
    prefs = jload(row["value"], {})
    if not isinstance(prefs, dict):
        return out
    for col, legacy in _NOTIF_KEYS.items():
        out[col] = bool(prefs.get(legacy, True))
    return out


def set_settings(db, user_id: int, values: dict) -> dict:
    """Sozlamalarni saqlaydi (faqat o'z foydalanuvchisi uchun)."""
    cur = get_settings(db, user_id)
    for k in DEFAULT_NOTIFICATION_SETTINGS:
        if k in values:
            cur[k] = bool(values[k])
    db.upd(
        "INSERT INTO notification_settings(user_id, lesson_reminders, admin_messages, "
        "lesson_status_updates, messages, requests, security, updated_at) "
        "VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET "
        "lesson_reminders=excluded.lesson_reminders, admin_messages=excluded.admin_messages, "
        "lesson_status_updates=excluded.lesson_status_updates, messages=excluded.messages, "
        "requests=excluded.requests, security=excluded.security, updated_at=excluded.updated_at",
        (user_id, int(cur["lesson_reminders"]), int(cur["admin_messages"]),
         int(cur["lesson_status_updates"]), int(cur["messages"]),
         int(cur["requests"]), int(cur["security"]), now()),
    )
    # Eski kalit bilan ham sinxron qilamiz — boshqa kod yo'llari (eski UI) ham
    # `user_settings.notif` ni o'qiy oladi.
    legacy = {v: cur[k] for k, v in _NOTIF_KEYS.items() if k in cur}
    db.ex(
        "INSERT INTO user_settings(user_id,key,value,updated_at) VALUES(?,?,?,?) "
        "ON CONFLICT(user_id,key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
        (user_id, "notif", jdump(legacy), now()),
    )
    return cur


def _blocked(db, user_id: int, ntype: str, source: str) -> bool:
    """Bu bildirishnoma turi foydalanuvchi sozlamasida O'CHIRILGANMI?"""
    settings = get_settings(db, user_id)
    if source == SRC_LESSON_REMINDER:
        return not settings["lesson_reminders"]
    for col, types in _COL_.items():
        if ntype in types:
            return not settings[col]
    return False


def notify(db, user_id: int, title: str, body: str, ntype: str = "info", data: dict = None,
           sender_id: int = None, sender_role: str = "", source: str = None,
           related_lesson_id: int = None, created_by: int = None,
           force: bool = False) -> int:
    """Bitta bildirishnoma yozadi. Qaytaradi: yozilgan qator id'si (yoki 0).

    `source`     — bildirishnoma tabiati (yuqoridagi SRC_*). Berilmasa
                   `sender_id` bor bo'lsa ADMIN_MESSAGE, aks holda SYSTEM.
    `created_by` — yaratuvchi: admin id (ADMIN_MESSAGE) yoki avtomatik
                   bildirishnomalarda matnli `"SYSTEM"` (BAND 18: avtomatik
                   eslatmada `created_by = SYSTEM` — admin esa hech qachon).
    `force`      — True bo'lsa, foydalanuvchi sozlamasi tekshirilmaydi
                   (masalan kritik xavfsizlik hodisasi uchun).

    BAND 9: `source = LESSON_REMINDER` uchun `related_lesson_id` MAJBURIY.
    UNIQUE indeks `ux_notif_reminder_once` tufayli qayta yozishga urinish
    `IntegrityError` beradi — bu "eslatma faqat bir marta" qoidasining
    o'zi database darajasida kafolatlaydi (ikkita server jarayoni parallel
    ishlanganda ham).
    """
    if source is None:
        source = SRC_ADMIN_MESSAGE if sender_id else SRC_SYSTEM
    if not force and _blocked(db, user_id, ntype, source):
        return 0
    if source == SRC_LESSON_REMINDER and not related_lesson_id:
        raise ValueError("LESSON_REMINDER uchun related_lesson_id majburiy")
    # BAND 18: tizim tomonidan yaratilgan bildirishnomaning `created_by`si
    # `"SYSTEM"` — frontend "kim yuborgan" savoliga aniq javob oladi.
    if created_by is None:
        created_by = "SYSTEM"
    try:
        return db.ex(
            "INSERT INTO notifications(user_id, type, source, title, body, data, is_read, "
            "read_at, sender_id, sender_role, related_lesson_id, created_by, created_at) "
            "VALUES(?,?,?,?,?,?,0,'',?,?,?,?,?)",
            (user_id, ntype, source, title, body, jdump(data or {}),
             sender_id, sender_role, related_lesson_id, created_by, now()),
        )
    except Exception as e:
        if "UNIQUE" in str(e) and source == SRC_LESSON_REMINDER:
            return 0  # allaqachon yuborilgan — jim qolmaydi, xato ham qilmaydi
        raise


def clear_lesson_reminders(db, lesson_id: int, user_id: int = None) -> int:
    """BAND 9: mashg'ulot bekor qilindi / ko'chirildi → ESKATMA
    o'chiriladi. Sababi: eslatma yangi jadvalga mos ravishda QAYTA
    hisoblanishi kerak, eski (noto'g'ri) eslatma esa yuborilmasligi kerak.
    `user_id` berilsa — faqat o'sha qabulchining eslatmasi o'chiriladi."""
    if user_id:
        return db.upd(
            "DELETE FROM notifications WHERE source=? AND related_lesson_id=? AND user_id=?",
            (SRC_LESSON_REMINDER, lesson_id, user_id),
        )
    return db.upd(
        "DELETE FROM notifications WHERE source=? AND related_lesson_id=?",
        (SRC_LESSON_REMINDER, lesson_id),
    )


# ---------------------------------------------------------------------------
# Qisqa yordamchilar
# ---------------------------------------------------------------------------
def student_user_ids(db, student_id: int) -> list:
    r = db.q1("SELECT user_id FROM students WHERE id=?", (student_id,))
    return [r["user_id"]] if r else []


def session_student_user_ids(db, session_id: int) -> list:
    return [r["user_id"] for r in db.q(
        """SELECT u.id AS user_id FROM session_students ss
           JOIN students s ON s.id=ss.student_id JOIN users u ON u.id=s.user_id
           WHERE ss.session_id=? AND ss.student_status='active'""", (session_id,),
    )]


def notify_session_participants(db, session_row, verb: str, sender_id: int = None,
                                sender_role: str = "", **extra):
    """Mashg'ulot yaratilganda/bekor qilinganda/ko'chirilganda tegishlilarga
    xabar. verb: created | cancelled | rescheduled | started | finished

    BAND 12: har bir verb o'z `source` ga ega — avtomatik xabarlar
    ADMIN_MESSAGE sifatida chiqmaydi.
    """
    inst = db.q1(
        "SELECT u.id AS uid, u.first_name||' '||u.last_name AS name FROM instructors i "
        "JOIN users u ON u.id=i.user_id WHERE i.id=?",
        (session_row["instructor_id"],),
    )
    car = session_row["car_name_snapshot"] or ""
    plate = session_row["car_plate_snapshot"] or ""
    info = f"{session_row['date']} {session_row['start_time']}-{session_row['end_time']}"
    sid = session_row["id"]
    base = {
        "session_id": sid, "verb": verb,
        "date": session_row["date"],
        "start_time": session_row["start_time"],
        "end_time": session_row["end_time"],
        "car": car, "plate": plate,
        "instructor_name": inst["name"] if inst else "",
        "instructor_uid": inst["uid"] if inst else "",
        "cancel_reason": session_row.get("cancel_reason") or "",
        **extra,
    }
    verb_src = {
        "created": SRC_LESSON_ASSIGNED,
        "cancelled": SRC_LESSON_CANCELLED,
        "rescheduled": SRC_LESSON_RESCHEDULED,
        "started": SRC_LESSON_ASSIGNED,
        "finished": SRC_LESSON_COMPLETED,
    }.get(verb, SRC_SYSTEM)
    verb_type = {
        "created": "lesson",
        "cancelled": "cancel",
        "rescheduled": "lesson",
        "started": "lesson",
        "finished": "lesson",
    }.get(verb, "info")
    verb_title = {
        "created": "lesson.assigned",
        "cancelled": "lesson.cancelled",
        "rescheduled": "lesson.rescheduled",
        "started": "lesson.started",
        "finished": "lesson.finished",
    }.get(verb, "info")

    if inst and verb in ("created", "cancelled", "rescheduled"):
        cnt = db.q1(
            "SELECT COUNT(*) c FROM session_students WHERE session_id=? AND student_status='active'",
            (sid,),
        )
        if verb == "created":
            notify(db, inst["uid"], "lesson.created", f"{info} — {cnt['c']} nafar talaba",
                   verb_type, {**base, "student_count": cnt["c"]}, sender_id, sender_role,
                   source=verb_src, related_lesson_id=sid)
        else:
            notify(db, inst["uid"], verb_title, f"{info}", verb_type, {**base},
                   sender_id, sender_role, source=verb_src, related_lesson_id=sid)

    for uid in session_student_user_ids(db, sid):
        if verb == "created":
            body = f"{info} · {inst['name'] if inst else ''}"
        else:
            body = info
        notify(db, uid, verb_title, body, verb_type, {**base}, sender_id, sender_role,
               source=verb_src, related_lesson_id=sid)


# ---------------------------------------------------------------------------
# MODUL 1 — AUDIT JURNALI (faoliyat jurnali)
#
# Bitta `audit()` chaqiruvi IKKALA jadvalga yozadi:
#   * `audit_log`  — yangi, to'liq jurnal (Kim / Nima qildi / Kimga / IP / Vaqt)
#   * `audit_logs` — eski jadval (backward compatibility; uning o'qiluvchi
#                    endpointlari va testlari saqlanib qoladi)
#
# `user_name` va `ip_address` avtomatik to'ldiriladi:
#   * ism — `users` jadvalidan (foydalanuvchi o'zgargan bo'lsa ham, o'sha
#     paytdagi ism saqlanib qoladi - jurnal "keyinchalik o'zgarmas" tamoyiliga)
#   * IP  — so'rov kontekstida (`set_audit_ip`) orqali. Kontekst yo'q bo'lsa
#     (fon vazifalar, seed skriptlar) bo'sh qoladi.
#
# Parol HECH QACHON yozilmaydi - faqat "parol o'zgartirildi" degan fakt.
# ---------------------------------------------------------------------------

_AUDIT_CTX = threading.local()

# MODUL 1: eski inglizcha `action` satrlarini barqaror `action_type` slug'iga
# tarjima qilish. Frontend filtri va badge'lari shu kalitlarni ishlatadi; eski
# `audit_logs` jadvalidagi matn esa O'ZGARMAYDI (backward compatibility).
# Noma'lum amal matni yo'qotilmaydi - o'zi saqlanadi.
ACTION_ALIASES = {
    "login": "login", "logout": "logout",
    "user created": "user_created", "bulk created": "user_created",
    "users imported": "user_created", "students imported": "user_created",
    "user updated": "user_updated", "bulk updated": "user_updated",
    "user blocked": "user_updated", "user unblocked": "user_updated",
    "user archived": "user_updated", "user activated": "user_updated",
    "user deleted (soft)": "user_deleted", "bulk deleted": "user_deleted",
    "password reset": "password_reset", "password changed": "password_changed",
    "session created": "session_created", "session rescheduled": "session_rescheduled",
    "session cancelled": "session_cancelled", "session started": "session_started",
    "session finished": "session_finished",
    "request approved": "request_approved", "request rejected": "request_rejected",
    "backup created": "backup_created", "backup restored": "backup_restored",
}


def action_slug(action: str) -> str:
    """`action` matni -> `action_type` slug'i (noma'lom bo'lsa o'zi)."""
    a = str(action or "").strip()
    return ACTION_ALIASES.get(a.lower(), a)


def set_audit_ip(ip: str) -> None:
    """Joriy so'rov mijoz IP'sini audit yozuvlariga ulash uchun."""
    _AUDIT_CTX.ip = str(ip or "")[:45]


def get_audit_ip() -> str:
    return str(getattr(_AUDIT_CTX, "ip", "") or "")


def _resolve_user_name(db, user_id) -> str:
    """Foydalanuvchi ismi (yoki 'Tizim' / bo'sh)."""
    if not user_id:
        return ""
    try:
        row = db.q1("SELECT first_name, last_name FROM users WHERE id=?", (int(user_id),))
        if row:
            name = ("%s %s" % (row.get("first_name") or "", row.get("last_name") or "")).strip()
            return name or ("#%s" % user_id)
    except Exception:
        pass
    return "#%s" % user_id


def audit(db, admin_id=None, action: str = "", entity_type: str = "", entity_id=None,
          details: dict = None, user_id=None, user_name: str = "", action_type: str = "",
          target_type: str = "", target_id=None, description: str = "",
          ip_address: str = "", timestamp=None):
    """Journga yozuv qo'shish (ikkala jadvalga ham).

    ESKI chaqiruv usuli saqlanadi:
        audit(db, uid, "user created", "users", 12, {...})
    YANGI (to'liq) usuli:
        audit(db, user_id=1, action_type="user_updated", target_type="users",
              target_id=12, description="Ism tahrirlandi", ip_address="1.2.3.4")
    """
    t = timestamp or now()
    uid = user_id if user_id is not None else admin_id
    aname = user_name or _resolve_user_name(db, uid)
    atype = action_type or action_slug(action)
    ttype = target_type or entity_type or ""
    tid = target_id if target_id is not None else entity_id
    desc = description
    if not desc and details:
        desc = ", ".join("%s=%s" % (k, v) for k, v in details.items())
    ip = ip_address or get_audit_ip()
    # `audit_log` dagi `target_id` TEXT - NULL-safe bo'lishi uchun str().
    try:
        db.ex(
            "INSERT INTO audit_log(user_id, user_name, action_type, target_type, target_id,"
            " description, ip_address, timestamp) VALUES(?,?,?,?,?,?,?,?)",
            (uid, aname, atype, ttype, (None if tid is None else str(tid)), desc, ip, t),
        )
    except Exception:
        pass  # jurnal yozilmasa ham asiy amali to'xtamasin
    try:
        db.ex(
            "INSERT INTO audit_logs(admin_id, action, entity_type, entity_id, details, created_at)"
            " VALUES(?,?,?,?,?,?)",
            (uid, atype or action, ttype or entity_type, tid,
             desc or jdump(details or {}), t),
        )
    except Exception:
        pass
