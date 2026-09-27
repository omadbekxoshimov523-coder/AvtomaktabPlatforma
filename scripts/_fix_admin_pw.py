"""Admin parolini qayta tiklash + audit_log tekshirish (M4 tashxisi uchun)."""
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.auth import hash_password  # noqa: E402

DB = Path(__file__).resolve().parent.parent / "data" / "avtomaktab.db"
con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row

print("== audit_log (oxirgi 12) ==")
try:
    for r in con.execute("SELECT id, user_id, action, target_type, target_id, created_at FROM audit_log ORDER BY id DESC LIMIT 12").fetchall():
        print(" ", dict(r))
except Exception as e:
    print("  audit_log xatosi:", e)

print("\n== admin parolini tiklash ==")
cur = con.execute("SELECT id FROM users WHERE login='admin'")
row = cur.fetchone()
if row:
    con.execute("UPDATE users SET password_hash=? WHERE id=?", (hash_password("admin123"), row["id"]))
    con.commit()
    print("  admin paroli -> admin123 (user id", row["id"], ")")
else:
    print("  admin topilmadi!")
con.close()

import urllib.request, urllib.error, json, http.cookiejar
jar = http.cookiejar.CookieJar()
op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

def api(method, path, body=None):
    headers = {"Content-Type": "application/json"}
    if method != "POST" or not path.endswith("/login"):
        headers["X-Requested-With"] = "Avtomaktab"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request("http://127.0.0.1:8080/api/" + path, data=data, headers=headers, method=method)
    try:
        with op.open(req, timeout=10) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        try:
            return {"http": e.code, **json.loads(e.read())}
        except Exception:
            return {"http_error": e.code}

print("\n== admin login tekshiruvi ==")
print(api("POST", "auth/login", {"login": "admin", "password": "admin123", "role": "admin"}))
reqs = api("GET", "admin/requests")["requests"]
pend = [x for x in reqs if x["status"] == "pending"]
print("pending requests:", [(x["id"], x["first_name"], x["last_name"], x["preferred_date"], x["preferred_start_time"], x["preferred_end_time"]) for x in pend])
insts = api("GET", "admin/instructors")["instructors"]
print("instructors:", [(i["id"], i["first_name"], i["last_name"], i["car"]["brand"] if i.get("car") else None) for i in insts])