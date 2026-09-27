"""M6: 2FA SMS (QR'siz) — backend to'liq sikl tekshiruvi (HTTP + sqlite).
     py -X utf8 tools_verify_m6_backend.py
Yo'nalish: enable (parol+telefon) -> bildirishnomadagi SMS kod -> verify-enable
          -> login OTPSIZ -> auth.otp_required + yangi kod -> login kod BILAN
          -> disable (parol) -> login yana OTPSIZ ishlaydi.
Test oxirida foydalanuvchi 2FA o'chirilgan holatga qaytariladi, test
bildirishnomalari va kodlar jadvalidan tozalanadi.
"""
import http.cookiejar
import json
import re
import sqlite3
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DB = ROOT / "data" / "avtomaktab.db"
BASE = "http://127.0.0.1:8080"
LOGIN = "usrL_00004"
PASS = "usrP_00004"
PHONE = "+998901112233"

FAILS = []


def check(name, cond):
    print(("OK    " if cond else "FAIL  ") + name)
    if not cond:
        FAILS.append(name)


def api_req(method, path, body=None, op=None):
    op = op or urllib.request.build_opener()
    headers = {"Content-Type": "application/json"}
    if method != "POST" or not str(path).endswith("/login"):
        headers["X-Requested-With"] = "Avtomaktab"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + "/api/" + path, data=data, headers=headers, method=method)
    try:
        with op.open(req, timeout=10) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read())
        except Exception:
            return {"http_error": e.code}


def new_session():
    jar = http.cookiejar.CookieJar()
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))


def login(op, otp=None):
    body = {"login": LOGIN, "password": PASS}
    if otp:
        body["otp"] = otp
    return api_req("POST", "auth/login", body, op)


def latest_code(uid):
    con = sqlite3.connect(DB)
    row = con.execute(
        "SELECT body FROM notifications WHERE user_id=? AND type='2fa' ORDER BY id DESC LIMIT 1",
        (uid,)).fetchone()
    con.close()
    if not row:
        return None
    m = re.search(r"\d{6}", row[0])
    return m.group() if m else None


def main():
    con = sqlite3.connect(DB)
    uid = con.execute("SELECT id FROM users WHERE login=?", (LOGIN,)).fetchone()[0]
    con.close()
    print("user id:", uid)

    # 1. Enable: parol + telefon -> OK, lekin QR/secret YO'Q
    op = new_session()
    r = login(op)
    check("dastlab login ishlaydi", r.get("ok") is True)
    r = api_req("POST", "me/2fa/enable", {"password": PASS, "phone": PHONE}, op)
    check("enable -> ok", r.get("ok") is True)
    check("enable javobida secret yo'q", "secret" not in r)
    check("enable javobida otpauth/QR yo'q", "otpauth" not in r)

    # 2. Kod bildirishnoma sifatida yetib bordi (simulyatsiya)
    code1 = latest_code(uid)
    check("SMS kod bildirishnomasi bor", code1 is not None and len(code1) == 6)
    con = sqlite3.connect(DB)
    prow = con.execute(
        "SELECT phone, used_at FROM twofa_codes WHERE user_id=? AND used_at='' ORDER BY id DESC LIMIT 1",
        (uid,)).fetchone()
    con.close()
    check("twofa_codes jadvalida telefon saqlangan", bool(prow) and prow[0] == PHONE)

    # 3. Verify-enable: kiritilgan kod bilan
    r = api_req("POST", "me/2fa/verify-enable", {"code": code1}, op)
    check("verify-enable -> ok", r.get("ok") is True)
    me = api_req("GET", "auth/me", op=op)
    check("me.totp_enabled == 1", me.get("user", {}).get("totp_enabled") == 1)

    # 4. Noto'g'ri kod rad etiladi
    r = api_req("POST", "me/2fa/verify-enable", {"code": "000000"}, op)
    check("noto'g'ri kod rad etiladi", r.get("error") == "auth.otp_invalid")

    # 5. Login OTPSIZ -> auth.otp_required + yangi kod yuboriladi
    op3 = new_session()
    r = login(op3)
    check("OTPSIZ login -> otp_required", r.get("error") == "auth.otp_required")
    code2 = latest_code(uid)
    check("login'da yangi SMS kod yuborildi", code2 is not None and len(code2) == 6)

    # 6. Login kod BILAN -> ishlaydi
    op4 = new_session()
    r = login(op4, otp=code2)
    check("OTP bilan login -> ok", r.get("ok") is True)
    me = api_req("GET", "auth/me", op=op4)
    check("login'da me.totp_enabled == 1", me.get("user", {}).get("totp_enabled") == 1)

    # 7. Disable: parol bilan
    r = api_req("POST", "me/2fa/disable", {"password": PASS}, op4)
    check("disable -> ok", r.get("ok") is True)
    me = api_req("GET", "auth/me", op=op4)
    check("me.totp_enabled == 0", me.get("user", {}).get("totp_enabled") == 0)

    # 8. Login yana OTPSIZ ishlaydi
    op5 = new_session()
    r = login(op5)
    check("2FA o'chirilgach OTPSIZ login -> ok", r.get("ok") is True)

    # 9. Tozalash: test bildirishnomalari + kodlar
    con = sqlite3.connect(DB)
    con.execute("DELETE FROM notifications WHERE user_id=? AND type='2fa'", (uid,))
    con.execute("DELETE FROM twofa_codes WHERE user_id=?", (uid,))
    tot = con.execute("SELECT COUNT(1) FROM users WHERE id=? AND totp_enabled=1", (uid,)).fetchone()[0]
    con.commit()
    con.close()
    check("test izlari tozalandi (2FA OFF)", tot == 0)

    print("\n=== NATIJA ===")
    if FAILS:
        print("Xatolar:", len(FAILS))
        for f in FAILS:
            print("  -", f)
    else:
        print("  Hammasi OK")
    raise SystemExit(1 if FAILS else 0)


if __name__ == "__main__":
    main()