"""M3 E2E — Bildirishnoma bosilganda tegishli detal ochiladi.
- talaba: lesson.assigned -> sessiya detal modal; msg.new -> xabarlar dialogi
- admin: request.new -> so'rov detal modal (approve/reject tugmalari bilan)
    py -X utf8 tools_e2e_m3.py
"""
import json
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

import websocket  # pip: websocket-client

ROOT = Path(__file__).resolve().parent
BASE = "http://127.0.0.1:8080"
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
PORT = 9338
PROFILE = Path(tempfile.mkdtemp(prefix="avtomaktab_e2e_m3_"))

FAILS = []
TOMORROW = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
NMON = (datetime.now() + timedelta(days=(7 - datetime.now().weekday()) % 7 or 7)).strftime("%Y-%m-%d")


class H:
    def __init__(self):
        import http.cookiejar
        self.op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def api(self, m, p, b=None):
        h = {"Content-Type": "application/json"}
        if m != "POST" or not p.endswith("/login"):
            h["X-Requested-With"] = "Avtomaktab"
        req = urllib.request.Request(BASE + "/api/" + p, data=json.dumps(b).encode() if b is not None else None,
                                     headers=h, method=m)
        try:
            with self.op.open(req, timeout=10) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())


def setup():
    """Ertaga 10:00 sessiya + keyingi dushanba so'rov + admin->talaba xabar."""
    con = sqlite3.connect(str(ROOT / "data" / "avtomaktab.db"))
    # eski M3-E2E qoldiqlarini tozalash
    con.execute("DELETE FROM messages WHERE text='M3-E2E-MSG'")
    for (rid,) in con.execute("SELECT id FROM practice_requests WHERE message='M3-E2E-REQ'").fetchall():
        con.execute("DELETE FROM notifications WHERE data LIKE ?", (f'%"request_id": {rid}%',))
        con.execute("DELETE FROM practice_requests WHERE id=?", (rid,))
    for (sid,) in con.execute("SELECT id FROM lesson_sessions WHERE notes='M3-E2E'").fetchall():
        con.execute("DELETE FROM session_students WHERE session_id=?", (sid,))
        con.execute("DELETE FROM notifications WHERE data LIKE ?", (f'%"session_id": {sid}%',))
        con.execute("DELETE FROM lesson_sessions WHERE id=?", (sid,))
        con.execute("DELETE FROM audit_logs WHERE entity_type='lesson_sessions' AND entity_id=?", (sid,))
    con.commit()
    con.close()

    a = H()
    a.api("POST", "auth/login", {"login": "admin", "password": "admin123", "role": "admin"})
    st, r = a.api("POST", "admin/sessions", {"date": TOMORROW, "start_time": "10:00", "end_time": "11:00",
                                             "instructor_id": 1, "student_ids": [1], "notes": "M3-E2E"})
    assert st == 200, r
    st, r = a.api("POST", "me/messages", {"to_user_id": 5, "text": "M3-E2E-MSG"})
    assert st == 200, r
    s = H()
    s.api("POST", "auth/login", {"login": "usrL_00004", "password": "usrP_00004", "role": "student"})
    st, r = s.api("POST", "student/requests", {"preferred_date": NMON, "preferred_start_time": "09:00",
                                               "preferred_end_time": "10:00", "message": "M3-E2E-REQ"})
    assert st == 200, r
    print(f"  tayyor: sessiya + xabar + so'rov #{r['id']}")


def cleanup():
    con = sqlite3.connect(str(ROOT / "data" / "avtomaktab.db"))
    con.execute("DELETE FROM messages WHERE text='M3-E2E-MSG'")
    for (rid,) in con.execute("SELECT id FROM practice_requests WHERE message='M3-E2E-REQ'").fetchall():
        con.execute("DELETE FROM notifications WHERE data LIKE ?", (f'%"request_id": {rid}%',))
        con.execute("DELETE FROM practice_requests WHERE id=?", (rid,))
    for (sid,) in con.execute("SELECT id FROM lesson_sessions WHERE notes='M3-E2E'").fetchall():
        con.execute("DELETE FROM session_students WHERE session_id=?", (sid,))
        con.execute("DELETE FROM notifications WHERE data LIKE ?", (f'%"session_id": {sid}%',))
        con.execute("DELETE FROM lesson_sessions WHERE id=?", (sid,))
        con.execute("DELETE FROM audit_logs WHERE entity_type='lesson_sessions' AND entity_id=?", (sid,))
    con.commit()
    con.close()
    print("  tozalandi")


def check(name, cond):
    print(("OK    " if cond else "FAIL  ") + name)
    if not cond:
        FAILS.append(name)


def kill_old(port):
    try:
        out = subprocess.run(["netstat", "-ano"], capture_output=True, text=True, timeout=15).stdout
        pids = set()
        for line in out.splitlines():
            parts = line.split()
            if len(parts) >= 5 and f":{port}" in parts[1] and parts[3] == "LISTENING":
                pids.add(parts[4])
        for pid in pids:
            subprocess.run(["taskkill", "/F", "/PID", pid], capture_output=True, text=True, timeout=10)
    except Exception:
        pass


class CDP:
    def __init__(self):
        kill_old(PORT)
        time.sleep(0.5)
        self.proc = subprocess.Popen(
            [CHROME, f"--remote-debugging-port={PORT}", "--headless=new",
             "--no-first-run", "--no-default-browser-check", "--disable-gpu",
             "--disable-extensions", "--remote-allow-origins=*",
             f"--user-data-dir={PROFILE}", "about:blank"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        ws_url = None
        for _ in range(60):
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json/list", timeout=2) as r:
                    targets = json.load(r)
                page = next((t for t in targets if t.get("type") == "page"), None)
                if page:
                    ws_url = page["webSocketDebuggerUrl"]
                    break
            except Exception:
                time.sleep(0.25)
        if not ws_url:
            raise RuntimeError("Chrome CDP ishga tushmadi")
        self.ws = websocket.create_connection(ws_url, timeout=40)
        self.mid = 0
        self.cmd("Page.enable")
        self.cmd("Runtime.enable")

    def cmd(self, method, params=None):
        self.mid += 1
        self.ws.send(json.dumps({"id": self.mid, "method": method, "params": params or {}}))
        while True:
            m = json.loads(self.ws.recv())
            if m.get("id") == self.mid:
                if "error" in m:
                    raise RuntimeError(m["error"])
                return m.get("result", {})

    def ev(self, expr):
        r = self.cmd("Runtime.evaluate", {"expression": expr, "returnByValue": True})
        return r.get("result", {}).get("value")

    def evp(self, expr):
        r = self.cmd("Runtime.evaluate", {"expression": expr, "returnByValue": True, "awaitPromise": True})
        if r.get("exceptionDetails"):
            raise RuntimeError(r["exceptionDetails"])
        return r.get("result", {}).get("value")

    def wait(self, expr, timeout=20):
        t0 = time.time()
        while time.time() - t0 < timeout:
            try:
                if self.evp(expr):
                    return True
            except Exception:
                pass
            time.sleep(0.25)
        return False

    def shot(self, name):
        try:
            import base64
            r = self.cmd("Page.captureScreenshot", {"format": "png"})
            (ROOT / f"m3shot_{name}.png").write_bytes(base64.b64decode(r["data"]))
        except Exception as e:
            print("  (screenshot xatosi:", e, ")")


def login(cdp, login, password):
    cdp.wait("!document.querySelector('#login-screen').classList.contains('hidden')", 15)
    cdp.ev(f"""(()=>{{const u=document.querySelector('#login-username');const p=document.querySelector('#login-password');
        u.value='{login}'; u.dispatchEvent(new Event('input',{{bubbles:true}}));
        p.value='{password}'; p.dispatchEvent(new Event('input',{{bubbles:true}}));
        document.querySelector('#login-form').requestSubmit(); return true}})()""")


def open_notifs(cdp):
    cdp.ev('document.querySelector(\'.nav-item[data-view="notifications"]\').click()')
    return cdp.wait('document.querySelectorAll(".notif-page-item").length >= 1')


def click_item_containing(cdp, marker):
    """Berilgan matnni o'z ichiga olgan bildirishnoma elementini bosadi; topildimi qaytaradi."""
    return cdp.ev(f"""(()=>{{const items=Array.from(document.querySelectorAll('.notif-page-item'));
        const it=items.find(x=>x.innerText.includes({json.dumps(marker)}));
        if(!it)return false; it.click(); return true;}})()""")


def wait_modal_text(cdp, marker, timeout=15):
    """Ochiq modal mavjud bo'lib, uning body matni marker'ni o'z ichiga olgunicha kutadi."""
    t0 = time.time()
    while time.time() - t0 < timeout:
        if not cdp.ev('!!document.querySelector(".modal-overlay:not(.hidden) .modal-body")'):
            time.sleep(0.25)
            continue
        txt = cdp.ev("document.querySelector('.modal-overlay:not(.hidden) .modal-body').innerText") or ""
        if marker in txt:
            return txt
        time.sleep(0.25)
    txt = cdp.ev("document.querySelector('.modal-overlay:not(.hidden) .modal-body')?.innerText") or ""
    print(f"  [debug] modal-da marker '{marker}' topilmadi, body='{txt[:160]}'")
    return txt


def main():
    setup()
    cdp = None
    try:
        cdp = CDP()
        cdp.cmd("Page.navigate", {"url": BASE + "/"})
        assert cdp.wait("!document.querySelector('#login-screen').classList.contains('hidden')"), "login ochilmadi"

        # ---------- TALABA ----------
        login(cdp, "usrL_00004", "usrP_00004")
        assert cdp.wait('!!document.querySelector(\'.nav-item[data-view="notifications"]\')'), "nav ochilmadi"
        assert open_notifs(cdp), "bildirishnomalar ochilmadi"

        # lesson.assigned -> sessiya detail
        ok = click_item_containing(cdp, TOMORROW)
        check("talaba: lesson.assigned elementi topildi", bool(ok))
        txt = wait_modal_text(cdp, "Akmal Karimov")
        print("  sessiya modal:", repr(txt[:140]))
        check("talaba: sessiya detal ochildi (instruktor)", "Akmal Karimov" in txt)
        check("talaba: sessiya detalda sana/vaqt", ("10:00" in txt and "11:00" in txt) and ("2026" in txt))
        check("talaba: sessiya detalda avto", "Chevrolet" in txt or "Cobalt" in txt)
        cdp.shot("student_session_from_notif")
        cdp.ev('document.querySelector(".modal-overlay:not(.hidden) .modal-head .btn-ghost").click()')
        cdp.wait('document.querySelectorAll(".modal-overlay:not(.hidden)").length === 0', 5)

        # msg.new -> xabarlar dialogi
        ok = click_item_containing(cdp, "M3-E2E-MSG")
        check("talaba: msg.new elementi topildi", bool(ok))
        mtxt = wait_modal_text(cdp, "M3-E2E-MSG")
        print("  xabar modal:", repr(mtxt[:140]))
        check("talaba: xabar matni ko'rindi", "M3-E2E-MSG" in mtxt)
        check("talaba: javob yozish maydoni bor",
              cdp.ev("!!document.querySelector('.modal-overlay:not(.hidden) textarea')"))
        cdp.shot("student_thread_from_notif")

        if FAILS:
            print("\n=== NATIJA: " + str(len(FAILS)) + " xato (talaba qismi) ===")
            for f in FAILS:
                print("  -", f)
            sys.exit(1)

        # ---------- ADMIN: request.new -> so'rov detal ----------
        cdp.proc.terminate()
        time.sleep(1)
        cdp = CDP()
        cdp.cmd("Page.navigate", {"url": BASE + "/"})
        assert cdp.wait("!document.querySelector('#login-screen').classList.contains('hidden')"), "login ochilmadi"
        login(cdp, "admin", "admin123")
        assert cdp.wait('!!document.querySelector(\'.nav-item[data-view="notifications"]\')'), "nav ochilmadi"
        assert open_notifs(cdp), "admin bildirishnomalari ochilmadi"

        ok = click_item_containing(cdp, "Omadbek")
        check("admin: request.new elementi topildi", bool(ok))
        rtxt = wait_modal_text(cdp, "09:00")
        print("  request modal:", repr(rtxt[:160]))
        check("admin: so'rov detalda talaba ismi", "Omadbek" in rtxt)
        check("admin: so'rov detalda sana/vaqt", "2026" in rtxt and "09:00" in rtxt)
        check("admin: approve tugmasi bor", "Tasdiqlash" in rtxt)
        check("admin: reject tugmasi bor", "Rad etish" in rtxt)
        cdp.shot("admin_request_from_notif")

        if FAILS:
            print("\n=== NATIJA: " + str(len(FAILS)) + " xato ===")
            for f in FAILS:
                print("  -", f)
            sys.exit(1)
        print("\n=== M3 E2E: 100% OK ===")
    finally:
        cleanup()
        if cdp:
            try:
                cdp.proc.terminate()
            except Exception:
                pass


if __name__ == "__main__":
    main()