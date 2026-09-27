"""M9 E2E: admin settings'dagi standart davomiylik yangi mashg'ulot formasini auto-to'ldiradi
va tahrirlab bo'ladi; backend end_time berilmaganda start+duration qo'llaydi.
    py -X utf8 tools_e2e_m9.py
"""
import json
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

import websocket

ROOT = Path(__file__).resolve().parent
BASE = "http://127.0.0.1:8080"
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
PORT = 9336
PROFILE = Path(tempfile.mkdtemp(prefix="avtomaktab_e2e_m9_"))

FAILS = []


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

    def wait(self, expr, timeout=20):
        t0 = time.time()
        while time.time() - t0 < timeout:
            try:
                if self.ev(expr):
                    return True
            except Exception:
                pass
            time.sleep(0.25)
        return False


import http.cookiejar
_JAR = http.cookiejar.CookieJar()
_OP = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(_JAR))


def http_api(m, p, b=None):
    h = {"Content-Type": "application/json"}
    if m in ("POST", "PUT", "DELETE"):
        h["X-Requested-With"] = "Avtomaktab"
    req = urllib.request.Request(BASE + "/api/" + p,
                                 data=json.dumps(b).encode() if b is not None else None, headers=h, method=m)
    try:
        with _OP.open(req, timeout=10) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def login(cdp, login, password):
    cdp.wait("!document.querySelector('#login-screen').classList.contains('hidden')", 15)
    cdp.ev(f"""(()=>{{const u=document.querySelector('#login-username');const p=document.querySelector('#login-password');
        u.value='{login}'; u.dispatchEvent(new Event('input',{{bubbles:true}}));
        p.value='{password}'; p.dispatchEvent(new Event('input',{{bubbles:true}}));
        document.querySelector('#login-form').requestSubmit(); return true}})()""")
    cdp.wait('!!document.querySelector("#sidebar-nav .nav-item")', 20)


def main():
    created_sid = None
    cdp = None
    try:
        # 1) backend end-to-end: davomiylik 45 -> end_time avtomatik
        st, _ = http_api("POST", "auth/login", {"login": "admin", "password": "admin123", "role": "admin"})
        assert st == 200, "admin login"
        st, r = http_api("PUT", "admin/settings", {"lesson_duration_min": 45})
        assert st == 200, "settings saqlash"
        from datetime import datetime, timedelta
        d = datetime.now()
        mon = d + timedelta(days=(7 - d.weekday()) % 7 or 7)
        monday = (mon + timedelta(days=7)).strftime("%Y-%m-%d")
        st, r = http_api("POST", "admin/sessions", {
            "date": monday, "start_time": "09:00", "instructor_id": 3,
            "student_ids": [], "notes": "M9-E2E",
        })
        assert st == 200, r
        created_sid = r["id"]
        st, det = http_api("GET", f"admin/sessions/{created_sid}")
        end_time = det["session"]["end_time"]
        check("M9: backend end_time avtomatik (09:00+45=09:45)", end_time == "09:45")
        print("  end_time:", end_time)

        # 2) frontend: yangi mashg'ulot formasi end'ni 45 daqiqaga to'ldiradi
        cdp = CDP()
        cdp.cmd("Page.navigate", {"url": BASE + "/"})
        assert cdp.wait("!document.querySelector('#login-screen').classList.contains('hidden')"), "login ochilmadi"
        login(cdp, "admin", "admin123")
        cdp.ev('document.querySelector(`.nav-item[data-view="lessons"]`).click()')
        assert cdp.wait('Array.from(document.querySelectorAll(".content button")).some(b=>b.innerText.includes("Yangi mashg"))', 20), "lessons ochilmadi"
        cdp.ev('Array.from(document.querySelectorAll(".content button")).find(b=>b.innerText.includes("Yangi mashg")).click()')
        assert cdp.wait('!!document.querySelector(".modal-overlay:not(.hidden) input[type=time]")'), "modal ochilmadi"
        times = cdp.ev("Array.from(document.querySelector('.modal-overlay:not(.hidden)').querySelectorAll('input[type=time]')).map(i=>i.value)")
        print("  [debug] boshlang'ich vaqtlar:", times)
        check("M9: end avtomatik to'ldirildi (15:00 -> 15:45)", len(times) == 2 and times[1] == "15:45")
        # start o'zgarganida end qayta hisoblanadi
        cdp.ev("""(()=>{const ts=document.querySelector('.modal-overlay:not(.hidden)').querySelectorAll('input[type=time]');
            ts[0].value='10:00'; ts[0].dispatchEvent(new Event('change',{bubbles:true})); return true;})()""")
        time.sleep(0.5)
        after = cdp.ev("Array.from(document.querySelector('.modal-overlay:not(.hidden)').querySelectorAll('input[type=time]')).map(i=>i.value)")
        print("  [debug] start o'zgarganda:", after)
        check("M9: start o'zgarganda end yangilanadi (10:00 -> 10:45)", len(after) == 2 and after[1] == "10:45")
        # end tahrirlab bo'ladi
        cdp.ev("""(()=>{const ts=document.querySelector('.modal-overlay:not(.hidden)').querySelectorAll('input[type=time]');
            ts[1].value='12:00'; ts[1].dispatchEvent(new Event('input',{bubbles:true})); return true;})()""")
        editable = cdp.ev("Array.from(document.querySelector('.modal-overlay:not(.hidden)').querySelectorAll('input[type=time]')).map(i=>i.value)")
        check("M9: end qo'lda tahrirlanadi", editable[1] == "12:00")
        cdp.ev('document.querySelector(".modal-overlay:not(.hidden) .modal-head .btn-ghost")?.click()')

        if FAILS:
            print("\n=== NATIJA: " + str(len(FAILS)) + " xato ===")
            for f in FAILS:
                print("  -", f)
            sys.exit(1)
        print("\n=== M9 E2E: 100% OK ===")
    finally:
        # tozalash: sessiya o'chirish + davomiylikni 90 ga qaytarish
        try:
            con = sqlite3.connect(str(ROOT / "data" / "avtomaktab.db"))
            if created_sid:
                con.execute("DELETE FROM notifications WHERE data LIKE ?", (f'%"session_id": {created_sid}%',))
                con.execute("DELETE FROM lesson_sessions WHERE id=?", (created_sid,))
                print("  sessiya o'chirildi:", created_sid)
            con.execute("INSERT OR REPLACE INTO system_settings(key,value,updated_at) VALUES('lesson_duration_min',?,datetime('now'))",
                        (json.dumps(90),))
            con.commit()
            con.close()
            print("  lesson_duration_min -> 90 qaytarildi")
        except Exception as e:
            print("  (tozalash xatosi:", e, ")")
        if cdp:
            try:
                cdp.proc.terminate()
            except Exception:
                pass


if __name__ == "__main__":
    main()