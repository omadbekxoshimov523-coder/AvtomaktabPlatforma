"""M4: admin approve oqimini jonli sinash (req 4 va req 1)."""
import http.cookiejar
import json
import urllib.error
import urllib.request

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


jar = http.cookiejar.CookieJar()
op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
print("login:", api("POST", "auth/login", {"login": "admin", "password": "admin123", "role": "admin"}, op).get("ok"))

for rid in (4, 1):
    print(f"\n== approve req {rid} (instructor 1) ==")
    body = {"date": "2026-09-27", "start_time": "07:00", "end_time": "08:00", "instructor_id": 1}
    if rid == 1:
        body = {"date": "2026-09-26", "start_time": "09:00", "end_time": "10:00", "instructor_id": 1}
    r = api("POST", f"admin/requests/{rid}/approve", body, op)
    print(r)

print("\n== reject req 4 ==")
print(api("POST", "admin/requests/4/reject", {"note": "test"}, op))

print("\n== statuslar ==")
print(api("GET", "admin/requests", op)["requests"][:4])