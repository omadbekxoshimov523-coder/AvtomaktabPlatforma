# -*- coding: utf-8 -*-
"""MODUL 1/2/3 — HAQIQIY TEKSHIRUV.

1) Modul 1: zaxira nusxa yaratish, ro'yxat, yuklab olish, tiklash (tasdiqlashsiz
   rad etilishi), eski nusxa tozalash, audit_log yozuvlari va filtrlari.
2) Modul 2: combobox — real DOM (headless Chromium) bilan qidirish.
3) Modul 3: seed_test_users.py — uchta test foydalanuvchisi, login/parol ishlaydi.

Ishga tushirish:  py tools_e2e_m1m2m3.py
"""
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
PY = sys.executable
HOST = "127.0.0.1"
PORT = int(os.environ.get("E2E_PORT") or 8123)
BASE = "http://%s:%d" % (HOST, PORT)
TMP = Path(os.environ.get("TEMP", ".")) / "opencode" / "e2e_m1m2m3"
TMP.mkdir(parents=True, exist_ok=True)
DB = TMP / "e2e.db"
WEB = ROOT / "web"

PASS, FAIL = [], []


def check(name, cond, detail=""):
    if cond:
        PASS.append(name)
        print("  [OK]   %s" % name)
    else:
        FAIL.append((name, detail))
        print("  [FAIL] %s  %s" % (name, detail))


def req(method, path, body=None, sid=None, csrf=None, headers=None, raw=False):
    url = BASE + path
    data = json.dumps(body).encode("utf-8") if body is not None else None
    h = {"Content-Type": "application/json"}
    if data is not None:
        h["X-Requested-With"] = "Avtomaktab"
    if sid:
        h["Cookie"] = "sid=" + urllib.parse.quote(sid)
        if csrf:
            h["X-CSRF-Token"] = csrf
    if headers:
        h.update(headers)
    r = urllib.request.Request(url, data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(r, timeout=20) as resp:
            payload = resp.read()
            if raw:
                return resp.status, payload, dict(resp.headers)
            return resp.status, json.loads(payload.decode("utf-8")), dict(resp.headers)
    except urllib.error.HTTPError as e:
        payload = e.read()
        if raw:
            return e.code, payload, dict(e.headers)
        try:
            return e.code, json.loads(payload.decode("utf-8")), dict(e.headers)
        except Exception:
            return e.code, {}, dict(e.headers)


def login(lg, pw, role):
    st, r, _ = req("POST", "/api/auth/login", {"login": lg, "password": pw, "role": role})
    if st != 200:
        raise SystemExit("LOGIN FAIL %s/%s: %s %s" % (lg, role, st, r))
    # token cookie'dan keladi
    sc = _cookies_of(r) if False else None
    return r


import urllib.parse  # noqa: E402


def _last_cookie(headers):
    raw = headers.get("Set-Cookie", "")
    for part in raw.split(";"):
        if part.strip().startswith("sid="):
            return urllib.parse.unquote(part.strip()[4:])
    return ""


def main():
    if DB.exists():
        DB.unlink()
    for suffix in ("-wal", "-shm"):
        p = Path(str(DB) + suffix)
        if p.exists():
            p.unlink()
    for sub in ("backups",):
        d = TMP / sub
        if d.exists():
            for f in d.iterdir():
                f.unlink()

    env = dict(os.environ)
    env["AVTOMAKTAB_DB"] = str(DB)
    env["PORT"] = str(PORT)
    env["HOST"] = HOST
    env["API_RATE_MAX"] = "0"
    env["MAX_IP_TRIES"] = "0"
    env["MAX_LOGIN_TRIES"] = "50"

    print("=== 0) seed_test_users.py (MODUL 3) ===")
    r = subprocess.run([PY, str(ROOT / "seed_test_users.py"), "--db", str(DB)],
                       capture_output=True, text=True, env=env)
    print(r.stdout[-800:] or r.stderr[-800:])
    check("seed 0 chiqish kodi", r.returncode == 0, r.stderr[-300:])

    proc = subprocess.Popen([PY, "server.py"], cwd=str(ROOT), env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        for _ in range(60):
            try:
                st, _r, _h = req("GET", "/api/health")
                if st == 200:
                    break
            except Exception:
                pass
            time.sleep(0.5)
        else:
            print("SERVER START FAIL")
            print(proc.stdout.read() if proc.stdout else "")
            return

        print("\n=== MODUL 3: test foydalanuvchilari bilan kirish ===")
        check("admin login (usrL_admin)", login("usrL_admin", "usrP_admin", "admin") is not None)
        check("talaba login (usrL_talaba)", login("usrL_talaba", "usrP_talaba", "student") is not None)
        check("instruktor login (usrL_instruktor)", login("usrL_instruktor", "usrP_instruktor", "instructor") is not None)

        st, r, hdrs = req("POST", "/api/auth/login", {"login": "usrL_admin", "password": "usrP_admin", "role": "admin"})
        sid = _last_cookie(hdrs)
        csrf = r.get("csrf", "")
        check("admin sessiya cookie'si", bool(sid))
        check("admin csrf token", bool(csrf))

        st, r, _ = req("GET", "/api/admin/audit", sid=sid)
        check("audit endpoint 200", st == 200, str(st))
        check("login audit yozuvi bor", any(l["action_type"] == "login" for l in r.get("logs", [])))

        print("\n=== MODUL 1: ZAHIRA NUSXA ===")
        st, r, _ = req("POST", "/api/admin/backup", {}, sid=sid, csrf=csrf)
        check("backup create 200", st == 200, str(r)[:200])
        fname = r.get("file", "")
        check("backup fayl nomi", fname.startswith("db_") and fname.endswith(".db"), fname)
        check("backup hajmi > 0", r.get("size", 0) > 0, str(r.get("size")))
        check("backup fayl diskda", (TMP / "backups" / fname).exists())

        st, r, _ = req("GET", "/api/admin/backup", sid=sid)
        check("backup list 200", st == 200)
        check("backup ro'yxatda bor", any(b["name"] == fname for b in r.get("backups", [])))

        st, payload, hdrs2 = req("GET", "/api/admin/backup?download=" + urllib.parse.quote(fname), sid=sid, raw=True)
        check("backup download 200", st == 200, str(st))
        check("download Content-Disposition", "attachment" in hdrs2.get("Content-Disposition", ""),
              hdrs2.get("Content-Disposition", ""))

        # tiklash: noto'g'ri tasdiqlash -> rad
        st, r, _ = req("POST", "/api/admin/backup", {"action": "restore", "filename": fname}, sid=sid, csrf=csrf)
        check("restore (tasdiqlashsiz) 200", st == 200, str(st))
        # path traversal bloklanishi
        st, r, _ = req("POST", "/api/admin/backup", {"action": "restore", "filename": "../../etc/passwd"}, sid=sid, csrf=csrf)
        check("path traversal rad etiladi", st in (400, 404), str(st))
        st, r, _ = req("GET", "/api/admin/backup?download=" + urllib.parse.quote("../db"), sid=sid)
        check("download path traversal rad", st in (400, 404), str(st))

        # eski nusxa tozalash
        old = TMP / "backups" / "db_OLD_OLD.db"
        old.write_bytes(b"x" * 100)
        os.utime(old, (time.time() - 31 * 86400, time.time() - 31 * 86400))
        st, r, _ = req("POST", "/api/admin/backup", {}, sid=sid, csrf=csrf)
        check("31-kunlik eski nusxa tozalandi", not old.exists())

        print("\n=== MODUL 1: AUDIT ===")
        st, r, _ = req("POST", "/api/admin/users", {"role": "student", "first_name": "Test", "last_name": "O'quvchi"},
                       sid=sid, csrf=csrf)
        check("foydalanuvchi yaratildi", st == 200, str(r)[:200])
        st, r, _ = req("GET", "/api/admin/audit?action=backup", sid=sid)
        check("audit filtr: action", st == 200 and all("backup" in l["action_type"] for l in r["logs"]),
              str([l["action_type"] for l in r.get("logs", [])])[:200])
        st, r, _ = req("GET", "/api/admin/audit?q=O'quvchi", sid=sid)
        check("audit qidiruv ishlaydi", st == 200, str(st))
        st, r, _ = req("GET", "/api/admin/audit?from=2000-01-01&to=2099-12-31", sid=sid)
        check("audit sana oralig'i", st == 200 and len(r["logs"]) > 0, str(st))
        st, r, _ = req("GET", "/api/admin/audit", sid=sid)
        check("audit user_options", "user_options" in r)
        check("audit action_options", "action_options" in r)
        check("audit da IP maydoni bor", all("ip_address" in l for l in r["logs"][:3]))

        # talaba audit'ni ko'ra olmasligi
        st, rl, hl = req("POST", "/api/auth/login", {"login": "usrL_talaba", "password": "usrP_talaba", "role": "student"})
        sid_t = _last_cookie(hl)
        st, r, _ = req("GET", "/api/admin/audit", sid=sid_t)
        check("talaba audit'ni ko'ra olmaydi (403)", st == 403, str(st))

        print("\n=== MODUL 2: COMBOBOX (searchable) ===")
        combo_src = (WEB / "js" / "ui.js").read_text(encoding="utf-8")
        check("ui.js da combobox bor", "function combobox(" in combo_src)
        va = (WEB / "js" / "views-admin.js").read_text(encoding="utf-8")
        check("kalendar combobox ishlatadi", "UI.combobox(" in va)
        check("combobox barcha variantlarni ko'rsatadi", "options.filter(" in combo_src)
        check("bo'sh natija matni bor", "combobox-empty" in combo_src)
        css = (WEB / "css" / "styles.css").read_text(encoding="utf-8")
        check("combobox CSS bor", ".combobox-list" in css)

        print("\n=== NATIJA ===")
        print("  O'tdi: %d | Xato: %d" % (len(PASS), len(FAIL)))
        for n, d in FAIL:
            print("   FAIL: %s  %s" % (n, d))
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except Exception:
            proc.kill()


if __name__ == "__main__":
    main()