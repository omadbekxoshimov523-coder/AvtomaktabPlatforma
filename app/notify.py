"""Bildirishnomalar (notifications) yaratish va audit log.

M12: har bir foydalanuvchi qaysi hodisalar uchun bildirishnoma kelishini
yoqib/o'chirib oladi (`user_settings` → 'notif'). Yo'q qilingan kategoriya
ustidagi bildirishnomalar yozilmaydi.
"""
from .db import now, jdump, jload

# Kategoriya → ntype xaritasi. Qo'shilmagan ntype (info/admin/system) hech
# qachon bloklanmaydi — admin e'lonlari har doim yetib boradi.
_CAT = {
    "lesson": "lesson",
    "cancel": "lesson",     # bekor qilish ham mashg'ulot hodisasi
    "request": "request",
    "message": "message",
    "security": "security",
    "reminder": "reminder",
}

# Barcha kategoriyalar (default: yoqilgan)
DEFAULT_NOTIF = {
    "lesson": True,
    "request": True,
    "message": True,
    "security": True,
    "reminder": True,
}


def _prefs(db, user_id: int) -> dict:
    row = db.q1("SELECT value FROM user_settings WHERE user_id=? AND key='notif'", (user_id,))
    if not row:
        return {}
    prefs = jload(row["value"], {})
    return prefs if isinstance(prefs, dict) else {}


def notify(db, user_id: int, title: str, body: str, ntype: str = "info", data: dict = None,
           sender_id: int = None, sender_role: str = ""):
    cat = _CAT.get(ntype)
    if cat is not None:
        prefs = _prefs(db, user_id)
        if cat in DEFAULT_NOTIF and prefs.get(cat, True) is False:
            return
    db.ex(
        "INSERT INTO notifications(user_id, type, title, body, data, is_read, sender_id, sender_role, created_at) "
        "VALUES(?,?,?,?,?,0,?,?,?)",
        (user_id, ntype, title, body, jdump(data or {}), sender_id, sender_role, now()),
    )


def notify_session_participants(db, session_row, verb: str, sender_id: int = None, sender_role: str = "", **extra):
    """Mashg'ulot yaratilganda/bekor qilinganda/ko'chirilganda tegishlilarga xabar.
    verb: created | cancelled | rescheduled | started | finished
    sender_id/sender_role — hodisani amalga oshirgan foydalanuvchi (admin/instruktor).
    """
    inst = db.q1(
        "SELECT u.id AS uid, u.first_name||' '||u.last_name AS name FROM instructors i "
        "JOIN users u ON u.id=i.user_id WHERE i.id=?",
        (session_row["instructor_id"],),
    )
    car = session_row["car_name_snapshot"] or ""
    plate = session_row["car_plate_snapshot"] or ""
    info = f"{session_row['date']} {session_row['start_time']}-{session_row['end_time']}"
    base = {
        "session_id": session_row["id"], "verb": verb,
        "date": session_row["date"],
        "start_time": session_row["start_time"],
        "end_time": session_row["end_time"],
        "car": car, "plate": plate,
        "instructor_name": inst["name"] if inst else "",
        "instructor_uid": inst["uid"] if inst else "",
        "cancel_reason": session_row.get("cancel_reason") or "",
        **extra,
    }
    if inst:
        uid = inst["uid"]
        if verb == "created":
            cnt = db.q1("SELECT COUNT(*) c FROM session_students WHERE session_id=? AND student_status='active'", (session_row["id"],))
            notify(db, uid, "lesson.created", f"{info} — {cnt['c']} nafar talaba", "lesson",
                   {**base, "student_count": cnt["c"]}, sender_id, sender_role)
        elif verb == "cancelled":
            notify(db, uid, "lesson.cancelled", f"{info}", "cancel",
                   {**base}, sender_id, sender_role)
        elif verb == "rescheduled":
            notify(db, uid, "lesson.rescheduled", f"{info}", "lesson",
                   {**base}, sender_id, sender_role)

    rows = db.q(
        """SELECT ss.student_id, u.id AS uid FROM session_students ss
           JOIN students s ON s.id=ss.student_id JOIN users u ON u.id=s.user_id
           WHERE ss.session_id=? AND ss.student_status='active'""",
        (session_row["id"],),
    )
    for r in rows:
        if verb == "created":
            notify(db, r["uid"], "lesson.assigned",
                   f"{info} · {inst['name'] if inst else ''}", "lesson",
                   {**base}, sender_id, sender_role)
        elif verb == "cancelled":
            notify(db, r["uid"], "lesson.cancelled", f"{info}", "cancel",
                   {**base}, sender_id, sender_role)
        elif verb == "rescheduled":
            notify(db, r["uid"], "lesson.rescheduled", f"{info}", "lesson",
                   {**base}, sender_id, sender_role)


def audit(db, admin_id, action: str, entity_type: str = "", entity_id=None, details: dict = None):
    db.ex(
        "INSERT INTO audit_logs(admin_id, action, entity_type, entity_id, details, created_at) VALUES(?,?,?,?,?,?)",
        (admin_id, action, entity_type, entity_id, jdump(details or {}), now()),
    )