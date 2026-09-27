"""M4 tashxisi: admin approve oqimini jonli takrorlash."""
import http.cookiejar
import json
import sqlite3
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "avtomaktab.db"
BASE = "http://127.0.0.1:8080"


def api(method, path, body=None, op=None):
    op = op or urllib.request.build_opener()
    headers = {"Content-Type": "application/json"}
    if method != "POST" or not path.endswith("/login"):
        headers["X-Requested-With"] = "Avtomaktab"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + "/api/" + path, data=data, headers=headers, method=method)
    try:
        with op.open(req, timeout=10) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        try:
            return {"http": e.code, **json.loads(e.read())}
        except Exception:
            return {"http_error": e.code}


def main():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    print("== users ==")
    for r in con.execute("SELECT id, login, first_name, last_name, role FROM users ORDER BY id").fetchall():
        print(" ", dict(r))
    print("== instructors schema ==")
    print(" ", con.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='instructors'").fetchone()[0])
    print("== instructors ==")
    for r in con.execute("SELECT * FROM instructors").fetchall():
        print(" ", dict(r))
    print("== practice_requests schema ==")
    print(" ", con.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='practice_requests'").fetchone()[0])
    print("== practice_requests ==")
    for r in con.execute("SELECT * FROM practice_requests").fetchall():
        print(" ", dict(r))
    con.close()

    jar = http.cookiejar.CookieJar()
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    print("\n== admin login ==")
    r = api("POST", "auth/login", {"login": "admin", "password": "admin123"}, op)
    print(r)

    reqs = api("GET", "admin/requests", op).get("requests", [])
    pend = [x for x in reqs if x["status"] == "pending"]
    print(f"\npending requests: {len(pend)}")
    for x in pend[:5]:
        print("  ", x["id"], x["first_name"], x["last_name"], x["preferred_date"], x["preferred_start_time"], x["preferred_end_time"], "student_id=", x["student_id"])

    insts = api("GET", "admin/instructors", op).get("instructors", [])
    print(f"\ninstructors: {len(insts)}")
    for i in insts:
        print("  ", i["id"], i["first_name"], i["last_name"], "car=", i.get("car"))

    if pend and insts:
        x = pend[0]
        iid = insts[0]["id"]
        print(f"\n== approve req {x['id']} with instructor {iid} ==")
        body = {
            "date": x["preferred_date"] or "2026-09-30",
            "start_time": x["preferred_start_time"] or "15:00",
            "end_time": x["preferred_end_time"] or "16:00",
            "instructor_id": iid,
        }
        print(api("POST", f"admin/requests/{x['id']}/approve", body, op))


if __name__ == "__main__":
    main()