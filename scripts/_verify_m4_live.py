"""M4 jonli tekshiruv: approve ham, reject ham ishlaydi, status darhol yangilanadi.
Talaba so'rov yaratadi -> admin ma'qullaydi -> sessiya + bildirishnoma tekshiriladi.
So'ng ikkinchi so'rov rad etiladi. Oxirida barcha test ma'lumotlari tozalanadi."""
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


def dbq(sql, params=()):
    con = sqlite3.connect(DB)
    try:
        con.row_factory = sqlite3.Row
        cur = con.execute(sql, params)
        rows = cur.fetchall()
        con.commit()
        return [dict(r) for r in rows]
    finally:
        con.close()


def main():
    # Talabalar va instruktor ID aniqlash
    stu = dbq("SELECT s.id sid, s.user_id uid FROM students s JOIN users u ON u.id=s.user_id WHERE u.login='usrL_00004'")[0]
    inst = dbq("SELECT i.id iid, i.user_id uid FROM instructors i JOIN users u ON u.id=i.user_id WHERE u.login='usrL_00001'")[0]
    print("student:", stu, " instructor:", inst)

    d = next_monday()
    print("test sana:", d)

    # 1) Talaba so'rov yaratadi (approve uchun)
    sop = nh()
    st, r = api("POST", "auth/login", {"login": "usrL_00004", "password": "usrP_00004", "role": "student"}, sop)
    print("student login:", st, r.get("ok"))
    st, r = api("POST", "student/requests", {
        "preferred_date": d, "preferred_start_time": "09:00", "preferred_end_time": "10:00",
        "message": "M4 live approve test"}, sop)
    print("student request create:", st, r)
    req_approve = r["id"]

    # 2) Talaba yana so'rov (reject uchun)
    st, r = api("POST", "student/requests", {
        "preferred_date": d, "preferred_start_time": "11:00", "preferred_end_time": "12:00",
        "message": "M4 live reject test"}, sop)
    print("student request create2:", st, r)
    req_reject = r["id"]

    # 3) Admin ma'qullaydi
    aop = nh()
    st, r = api("POST", "auth/login", {"login": "admin", "password": "admin123", "role": "admin"}, aop)
    print("admin login:", st, r.get("ok"))
    st, r = api("POST", f"admin/requests/{req_approve}/approve",
                {"date": d, "start_time": "09:00", "end_time": "10:00", "instructor_id": inst["iid"]}, aop)
    print("approve:", st, r)
    assert st == 200 and r.get("ok"), "approve bajarilmadi!"
    sid = r["session_id"]

    # 4) DB tekshiruvlar
    req = dbq("SELECT status, session_id, processed_at FROM practice_requests WHERE id=?", (req_approve,))[0]
    print("request status:", req)
    assert req["status"] == "approved" and req["session_id"] == sid
    sess = dbq("SELECT * FROM lesson_sessions WHERE id=?", (sid,))[0]
    print("session:", {k: sess[k] for k in ("date", "start_time", "end_time", "instructor_id", "status")})
    assert sess["status"] == "scheduled" and sess["date"] == d
    ss = dbq("SELECT student_id, attendance_status, student_status FROM session_students WHERE session_id=?", (sid,))
    print("session_students:", ss)
    assert len(ss) == 1 and ss[0]["student_id"] == stu["sid"]
    nts = dbq("SELECT user_id, type, title FROM notifications WHERE data LIKE ? OR (data LIKE ? AND data LIKE ?)",
              (f'%"session_id": {sid}%', "%request%", "%"))
    nts = dbq("SELECT n.user_id, n.type, n.title FROM notifications n WHERE n.data LIKE ?",
              (f'%"session_id": {sid}%',))
    print("notifications:", nts)
    title_set = {n["title"] for n in nts}
    assert "lesson.assigned" in title_set, "talabaga lesson.assigned kelishi kerak"
    assert "lesson.created" in title_set, "instruktorga lesson.created kelishi kerak"

    # 5) Reject
    st, r = api("POST", f"admin/requests/{req_reject}/reject", {"note": "M4 live reject"}, aop)
    print("reject:", st, r)
    assert st == 200 and r.get("ok")
    req2 = dbq("SELECT status, admin_note FROM practice_requests WHERE id=?", (req_reject,))[0]
    print("request2 status:", req2)
    assert req2["status"] == "rejected" and req2["admin_note"] == "M4 live reject"

    print("\nM4 LIVE OK: approve ham, reject ham ishlaydi, statuslar yangilanadi")

    # 6) Tozalash
    con = sqlite3.connect(DB)
    try:
        cur = con.cursor()
        cur.execute("DELETE FROM session_students WHERE session_id=?", (sid,))
        cur.execute("DELETE FROM notifications WHERE data LIKE ?", (f'%"session_id": {sid}%',))
        cur.execute("DELETE FROM lesson_sessions WHERE id=?", (sid,))
        cur.execute("DELETE FROM practice_requests WHERE id IN (?,?)", (req_approve, req_reject))
        cur.execute("DELETE FROM audit_logs WHERE entity='practice_requests' AND entity_id IN (?,?)", (req_approve, req_reject))
        con.commit()
        print("tozalandi")
    finally:
        con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())