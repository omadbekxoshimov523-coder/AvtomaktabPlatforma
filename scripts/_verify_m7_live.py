"""M7 jonli probe: branches endpoint'lar olib tashlangan -> 404.
Admin sidebar'ida "Filiallar" yo'q (frontend boshqa E2E da tekshiriladi)."""
import http.cookiejar
import json
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8080"
jar = http.cookiejar.CookieJar()
op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))


def api(m, p, b=None):
    h = {"Content-Type": "application/json"}
    if m == "POST":
        h["X-Requested-With"] = "Avtomaktab"
    req = urllib.request.Request(BASE + "/api/" + p, data=json.dumps(b).encode() if b is not None else None,
                                 headers=h, method=m)
    try:
        with op.open(req, timeout=10) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


ok = True
st, r = api("POST", "auth/login", {"login": "admin", "password": "admin123", "role": "admin"})
print("login:", st)
st, r = api("GET", "admin/branches")
print("GET admin/branches ->", st, r)
ok = ok and st == 404
st, r = api("POST", "admin/branches", {"name": "X"})
print("POST admin/branches ->", st)
ok = ok and st == 404
st, r = api("GET", "admin/settings")
print("GET admin/settings (boshqa endpoint ishlayapti):", st)
ok = ok and st == 200
print("\n=== M7 probe:", "OK" if ok else "FAIL", "===")
raise SystemExit(0 if ok else 1)