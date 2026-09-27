"""M1 jonli tekshiruv: bildirishnomalarda jo'natuvchi ko'rinadi.
Admin sessiya yaratadi -> talaba me_notifications'da sender_admin ko'rsatadi.
So'ng tozalanadi."""
import http.cookiejar
import json
import sqlite3
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "avtomaktab.db"
BASE = "http://127.0.0.1:8080"


def api(method, path, body=None, op=None):
    op = op or urllib.request.build_opener()
    headers = {"Content-Type": "application/json"}
    if method in ("POST", "PUT", "DELETE") and not path.endswith("/login"):
        headers["X-Requested-With"] = "Avtomaktab"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + "/api/" + path, data=data, headers=headers, method=method)
    try:
        with op.open(req, timeout=10) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read())
        except Exception:
            return e.code, {}


def nh():
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))


def next_monday():
    d = datetime.now()
    mon = d + timedelta(days=(7 - d.weekday()) % 7 or 7)
    return (mon + timedelta(days=7)).strftime("%Y-%m-%d")


def main():
    # migrate qo'llanganini tekshiramiz
    con = sqlite3.connect(DB)
    try:
        cols = [r[1] for r in con.execute("PRAGMA table_info(notifications)").fetchall()]
        assert "sender_id" in cols and "sender_role" in cols, "sender ustunlari yo'q!"
        print("sender ustunlari mavjud:", cols)
    finally:
        con.close()

    aop = nh()
    st, r = api("POST", "auth/login", {"login": "admin", "password": "admin123", "role": "admin"}, aop)
    print("admin login:", st, r.get("ok"))
    d = next_monday()
    st, r = api("POST", "admin/sessions", {"date": d, "start_time": "12:00", "end_time": "13:00",
                                           "instructor_id": 1, "student_ids": [1], "notes": "M1-LIVE"}, aop)
    print("session create:", st, r.get("ok"), "id =", r.get("id"))
    assert st == 200 and r.get("id"), "sessiya yaratilmadi: %r" % r
    sid = r["id"]

    sop = nh()
    st, r = api("POST", "auth/login", {"login": "usrL_00004", "password": "usrP_00004", "role": "student"}, sop)
    st, ns = api("GET", "me/notifications", op=sop)
    hits = [n for n in ns.get("notifications", [])
            if str((json.loads(n.get("data") or "{}") or {}).get("session_id")) == str(sid)]
    print("student notif hits:", len(hits))
    for n in hits[:2]:
        print("  sender_id=%s sender_role=%s sender_name=%s %s profile=%r" % (
            n.get("sender_id"), n.get("sender_role"),
            n.get("sender_first_name"), n.get("sender_last_name"), n.get("sender_profile_image")))
    ok = any(n.get("sender_role") == "admin" and n.get("sender_id") == 1
             and (n.get("sender_first_name") or "") for n in hits)
    assert ok, "jo'natuvchi admin bo'lishi shart!"
    print("M1 LIVE OK: bildirishnomada admin jo'natuvchi ko'rinadi")

    # tozalash (M1-LIVE belgili barcha sessiyalar)
    con = sqlite3.connect(DB)
    try:
        cur = con.cursor()
        for (sid,) in cur.execute("SELECT id FROM lesson_sessions WHERE notes='M1-LIVE'").fetchall():
            cur.execute("DELETE FROM session_students WHERE session_id=?", (sid,))
            cur.execute("DELETE FROM notifications WHERE data LIKE ?", (f'%"session_id": {sid}%',))
            cur.execute("DELETE FROM lesson_sessions WHERE id=?", (sid,))
            cur.execute("DELETE FROM audit_logs WHERE entity_type='lesson_sessions' AND entity_id=?", (sid,))
        con.commit()
        print("tozalandi")
    finally:
        con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())