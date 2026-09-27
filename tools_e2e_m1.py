"""M1 E2E — Bildirishnomalarda jo'natuvchi (ism+familiya, rol badge, avatar) ko'rinadi.
Talaba sifatida kirib, bildirishnomalar sahifasida admin jo'natuvchini tekshiramiz.
    py -X utf8 tools_e2e_m1.py
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
PORT = 9336
PROFILE = Path(tempfile.mkdtemp(prefix="avtomaktab_e2e_m1_"))

FAILS = []

TOMORROW = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")


def ensure_session():
    """M1 E2E uchun ertaga 09:00-10:00 sessiya mavjud bo'lsin (admin yaratadi)."""
    import http.cookiejar
    con = sqlite3.connect(str(ROOT / "data" / "avtomaktab.db"))
    row = con.execute("SELECT id FROM lesson_sessions WHERE notes='M1-E2E' AND date=? AND start_time='09:00'", (TOMORROW,)).fetchone()
    if row:
        con.close()
        print(f"  M1-E2E sessiya allaqachon mavjud: #{row[0]}")
        return row[0]
    con.close()
    jar = http.cookiejar.CookieJar()
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    req = urllib.request.Request(
        BASE + "/api/auth/login",
        data=json.dumps({"login": "admin", "password": "admin123", "role": "admin"}).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    op.open(req, timeout=10)
    req2 = urllib.request.Request(
        BASE + "/api/admin/sessions",
        data=json.dumps({"date": TOMORROW, "start_time": "09:00", "end_time": "10:00",
                         "instructor_id": 1, "student_ids": [1], "notes": "M1-E2E"}).encode(),
        headers={"Content-Type": "application/json", "X-Requested-With": "Avtomaktab"}, method="POST")
    with op.open(req2, timeout=10) as resp:
        return json.loads(resp.read())["id"]


def cleanup_session(sid):
    con = sqlite3.connect(str(ROOT / "data" / "avtomaktab.db"))
    con.execute("DELETE FROM session_students WHERE session_id=?", (sid,))
    con.execute("DELETE FROM notifications WHERE data LIKE ?", (f'%"session_id": {sid}%',))
    con.execute("DELETE FROM lesson_sessions WHERE id=?", (sid,))
    con.execute("DELETE FROM audit_logs WHERE entity_type='lesson_sessions' AND entity_id=?", (sid,))
    con.commit()
    con.close()
    print(f"  M1-E2E sessiya #{sid} tozalandi")


def check(name, cond):
    print(("OK    " if cond else "FAIL  ") + name)
    if not cond:
        FAILS.append(name)


def must(cdp, name, expr, timeout=20):
    if cdp.wait(expr, timeout):
        check(name, True)
        return True
    check(name, False)
    try:
        print("   [debug] body:", repr(cdp.ev("document.body.innerText.slice(0,500)"))[:500])
    except Exception as e:
        print("   [debug] err:", e)
    return False


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
            print(f"  eski chrome jarayoni (#{pid}) o'ldirildi")
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
            (ROOT / f"m1shot_{name}.png").write_bytes(base64.b64decode(r["data"]))
        except Exception as e:
            print("  (screenshot xatosi:", e, ")")


def login(cdp, login, password):
    cdp.wait("!document.querySelector('#login-screen').classList.contains('hidden')", 15)
    cdp.ev(f"""(()=>{{const u=document.querySelector('#login-username');const p=document.querySelector('#login-password');
        u.value='{login}'; u.dispatchEvent(new Event('input',{{bubbles:true}}));
        p.value='{password}'; p.dispatchEvent(new Event('input',{{bubbles:true}}));
        document.querySelector('#login-form').requestSubmit(); return true}})()""")


def main():
    sid = ensure_session()
    cdp = None
    try:
        cdp = CDP()
        cdp.cmd("Page.navigate", {"url": BASE + "/"})
        assert cdp.wait("!document.querySelector('#login-screen').classList.contains('hidden')"), "login sahifa ochilmadi"

        login(cdp, "usrL_00004", "usrP_00004")  # talaba
        ok = cdp.wait('!!document.querySelector(\'.nav-item[data-view="notifications"]\')')
        check("talaba: nav ochildi", ok)
        cdp.ev('document.querySelector(\'.nav-item[data-view="notifications"]\').click()')
        ok = must(cdp, "talaba: bildirishnomalar sahifasi ochildi",
                  'document.querySelectorAll(".notif-page-item").length >= 1')
        # eng yangi (yangi kelgan lesson.assigned) elementda jo'natuvchi ko'rinishi
        expr = """
        (()=>{const items=Array.from(document.querySelectorAll('.notif-page-item'));
          const it=items.find(x=>x.innerText.includes('09:00-10:00')||x.innerText.includes('lesson'));
          if(!it)return null;
          const name=it.querySelector('.notif-sender')?it.querySelector('.notif-sender').innerText:'';
          const role=it.querySelector('.notif-role')?it.querySelector('.notif-role').innerText:'';
          const av=it.querySelector('.avatar');
          const img=it.querySelector('.avatar img');
          return JSON.stringify({name,role,hasAvatar:!!av,hasImg:!!img,text:it.innerText.slice(0,160)});
        })()"""
        res = cdp.ev(expr)
        print("  jo'natuvchi:", res)
        d = json.loads(res or "null")
        check("talaba: jo'natuvchi ismi ko'rindi", bool(d) and "Samandar" in d["name"])
        check("talaba: rol badge 'Admin'", bool(d) and d["role"].lower() == "admin")
        check("talaba: avatar element bor", bool(d) and d["hasAvatar"])
        check("talaba: avatar rasm yuklandi", bool(d) and d["hasImg"])
        cdp.shot("student_notif_sender")

        # Dashboard kabinetda ham (notifMini) jo'natuvchi ko'rinadi
        cdp.ev('document.querySelector(\'.nav-item[data-view="dashboard"]\').click()')
        ok = must(cdp, "talaba: dashboardda notif-mini sender bor",
                  'Array.from(document.querySelectorAll(".notif-mini .notif-sender")).length >= 1')
        mini = cdp.ev("(document.querySelector('.notif-mini .notif-sender') || {}).innerText || ''")
        print("  mini sender:", repr(mini))
        check("talaba: dashboard sender 'Samandar'", "Samandar" in mini)
        cdp.shot("student_home_mini")

        if FAILS:
            print("\n=== NATIJA: " + str(len(FAILS)) + " xato ===")
            for f in FAILS:
                print("  -", f)
            cleanup_session(sid)
            sys.exit(1)
        print("\n=== M1 E2E: 100% OK ===")
    finally:
        cleanup_session(sid)
        if cdp:
            try:
                cdp.proc.terminate()
            except Exception:
                pass


if __name__ == "__main__":
    main()