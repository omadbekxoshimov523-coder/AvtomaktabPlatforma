# -*- coding: utf-8 -*-
"""Smoke test: yangi api.py o'zgarishlarini jonli serverda tekshirish."""
import json
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = "http://127.0.0.1:8080/api"
results = []


def call(method, path, token=None, body=None):
    req = urllib.request.Request(BASE + path, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Cookie", "sid=" + urllib.parse.quote(token))
    data = json.dumps(body).encode() if body is not None else None
    try:
        with urllib.request.urlopen(req, data=data, timeout=10) as r:
            sc = r.headers.get("Set-Cookie", "")
            return r.status, json.loads(r.read().decode()), sc
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode()), ""


def sid_from_cookie(sc):
    for part in sc.split(";"):
        if part.strip().startswith("sid="):
            return urllib.parse.unquote(part.strip()[4:])
    return ""


def check(name, cond, detail=""):
    results.append((name, bool(cond), detail))


# server kutish
up = False
for _ in range(40):
    try:
        s, _, _ = call("GET", "/health")
        if s == 200:
            up = True
            break
    except Exception:
        pass
    time.sleep(0.5)
check("server /api/health", up, f"status={s if up else 'n/a'}")

if not up:
    print("SERVER UPA CHIQMADI")
    for n, ok, d in results:
        print(("OK  " if ok else "FAIL"), n, d)
    raise SystemExit(1)

# admin login
s, r, sc = call("POST", "/auth/login", body={"login": "admin", "password": "admin123", "role": "admin"})
check("admin login", s == 200 and r.get("ok"), json.dumps(r)[:120])
admin_token = sid_from_cookie(sc)
check("admin sid cookie", bool(admin_token), sc[:80])
s, r, _ = call("GET", "/auth/me", token=admin_token)
check("admin me", s == 200 and r.get("ok"), json.dumps(r)[:120])

# 1) admin/instructors -> login maydoni
s, r, _ = call("GET", "/admin/instructors", token=admin_token)
insts = r.get("instructors", [])
has_login = all("login" in i for i in insts) and len(insts) > 0
has_flat = all("user_id" in i and "id" in i and "work_start" in i for i in insts)
check("admin/instructors: login bor", has_login, f"{len(insts)} ta, misol: {json.dumps(insts[0] if insts else {})[:160]}")
check("admin/instructors: flat (user_id+id+work_start)", has_flat, "")

# 2) admin/sessions/{id} -> student_count
s, r, _ = call("GET", "/admin/sessions", token=admin_token)
sess_list = r.get("sessions", []) or r.get("items", [])
sid = sess_list[0]["id"] if sess_list else None
check("admin/sessions list", sid is not None, f"jami {len(sess_list)}")
if sid:
    s, r, _ = call("GET", f"/admin/sessions/{sid}", token=admin_token)
    det = r.get("session", {})
    check("admin/session detail: student_count", "student_count" in det, json.dumps(det)[:200])
    check("admin/session detail: instructor_name", bool(det.get("instructor_name")), det.get("instructor_name", ""))

# 3) instructor detail
s, r, sc = call("POST", "/auth/login", body={"login": "usrL_00001", "password": "usrP_00001", "role": "instructor"})
check("instructor login", s == 200 and r.get("ok"), json.dumps(r)[:120])
itok = sid_from_cookie(sc)
s, r, _ = call("GET", "/instructor/sessions", token=itok)
ism = r.get("sessions", []) or r.get("items", [])
isid = ism[0]["id"] if ism else None
if isid:
    s, r, _ = call("GET", f"/instructor/sessions/{isid}", token=itok)
    det = r.get("session", {})
    check("instructor/session detail: student_count", "student_count" in det, json.dumps(det)[:200])
    check("instructor/session detail: instructor_name", bool(det.get("instructor_name")), det.get("instructor_name", ""))
    check("instructor/session detail: instructor_phone", bool(det.get("instructor_phone")), det.get("instructor_phone", ""))

# 4) student detail
s, r, sc = call("POST", "/auth/login", body={"login": "usrL_00004", "password": "usrP_00004", "role": "student"})
check("student login", s == 200 and r.get("ok"), json.dumps(r)[:120])
stok = sid_from_cookie(sc)
s, r, _ = call("GET", "/student/sessions?upcoming=1", token=stok)
sl = r.get("sessions", []) or r.get("items", [])
ssid = sl[0]["id"] if sl else None
if ssid:
    s, r, _ = call("GET", f"/student/sessions/{ssid}", token=stok)
    det = r.get("session", {})
    check("student/session detail: student_count", "student_count" in det, json.dumps(det)[:200])
    check("student/session detail: pickup_address maydoni", "pickup_address" in det, "")

print("\n=== NATIJALAR ===")
fails = 0
for n, ok, d in results:
    print(("OK   " if ok else "FAIL "), n, (("-> " + d) if d and not ok else ""))
    if not ok:
        fails += 1
print(f"\nJami: {len(results)}, FAIL: {fails}")
raise SystemExit(1 if fails else 0)