"""M13-A E2E — Bekor qilish / qayta rejalashtirish oqimi (CDP, real brauzer).
Instruktor mashg'ulotni sababi bilan bekor qiladi; talaba tarix jadvalidan
boshlasa ham sabab va holatni ko'radi.
    py -X utf8 tools_e2e_m13.py
"""
import json
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
PORT = 9332
PROFILE = Path(tempfile.mkdtemp(prefix="avtomaktab_e2e_m13a_"))

FAILS = []

SDATE = (datetime.now() + timedelta(days=(7 - datetime.now().weekday()) % 7 or 7)).strftime("%Y-%m-%d")


def api_admin_create_session():
    """Admin orqali keyingi dushanba uchun M13A E2E sessiyasini yaratadi
    (avval avvalgi yugurishlardan qolgan M13A E2E sessiyalarni tozalaydi)."""
    import http.cookiejar
    import sqlite3
    con = sqlite3.connect(str(ROOT / "data" / "avtomaktab.db"))
    rows = con.execute("SELECT id FROM lesson_sessions WHERE notes='M13A E2E'").fetchall()
    for (sid,) in rows:
        con.execute("DELETE FROM session_students WHERE session_id=?", (sid,))
        con.execute("DELETE FROM notifications WHERE data LIKE ?", (f'%"session_id": {sid}%',))
        con.execute("DELETE FROM attendance WHERE session_id=?", (sid,))
        con.execute("DELETE FROM lesson_sessions WHERE id=?", (sid,))
        print(f"  eski M13A E2E sessiya #{sid} tozalandi")
    con.commit()
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
        data=json.dumps({"date": SDATE, "start_time": "11:00", "end_time": "12:00",
                         "instructor_id": 1, "student_ids": [1], "notes": "M13A E2E"}).encode(),
        headers={"Content-Type": "application/json", "X-Requested-With": "Avtomaktab"}, method="POST")
    with op.open(req2, timeout=10) as resp:
        return json.loads(resp.read())["id"]


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
            (ROOT / f"m13shot_{name}.png").write_bytes(base64.b64decode(r["data"]))
        except Exception as e:
            print("  (screenshot xatosi:", e, ")")


def login(cdp, login, password, role):
    cdp.wait("!document.querySelector('#login-screen').classList.contains('hidden')", 15)
    cdp.ev(f"""(()=>{{const u=document.querySelector('#login-username');const p=document.querySelector('#login-password');
        u.value='{login}'; u.dispatchEvent(new Event('input',{{bubbles:true}}));
        p.value='{password}'; p.dispatchEvent(new Event('input',{{bubbles:true}}));
        document.querySelector('#login-form').requestSubmit(); return true}})()""")


def logout(cdp):
    cdp.evp("(async()=>{try{await fetch('/api/auth/logout',{method:'POST',headers:{'X-Requested-With':'Avtomaktab'}})}catch(e){};location.reload();return true})()")
    cdp.wait("!document.querySelector('#login-screen').classList.contains('hidden')", 15)


def main():
    sid = api_admin_create_session()
    print(f"  M13A E2E sessiya #{sid} yaratildi ({SDATE} 11:00-12:00)")
    cdp = None
    try:
        cdp = CDP()
        cdp.cmd("Page.navigate", {"url": BASE + "/"})
        assert cdp.wait("!document.querySelector('#login-screen').classList.contains('hidden')"), "login sahifa ochilmadi"

        # ---------- INSTRUKTOR: bekor qilish ----------
        login(cdp, "usrL_00001", "usrP_00001", "instructor")
        ok = cdp.wait('!!document.querySelector(\'.nav-item[data-view="schedule"]\')')
        check("instruktor: nav ochildi", ok)
        cdp.ev('document.querySelector(\'.nav-item[data-view="schedule"]\').click()')
        ok = must(cdp, "instruktor: jadval sahifasi ochildi",
                  'document.querySelectorAll("#view input[type=date]").length >= 1')
        # Sana filtrini M13A sessiyasi sanasiga (keyingi dushanba) o'rnatamiz
        cdp.ev(f"""(()=>{{const d=document.querySelector('#view input[type=date]');
            d.value='{SDATE}'; d.dispatchEvent(new Event('change',{{bubbles:true}})); return true}})()""")
        # M13A E2E sessiyasi (11:00–12:00) kartasini kutamiz
        open_card = """
        (()=>{const cards=Array.from(document.querySelectorAll('.session-card'));
          const c=cards.find(x=>x.innerText.includes('11:00–12:00')&&x.innerText.includes('Kutilmoqda'));
          if(!c)return false; c.click(); return true})()
        """
        check("instruktor: sessiya kartasi topildi va bosildi", must(cdp, "instruktor: sessiya kartasi paydo bo'ldi",
              'Array.from(document.querySelectorAll(".session-card")).some(x=>x.innerText.includes("11:00–12:00")&&x.innerText.includes("Kutilmoqda"))') and bool(cdp.ev(open_card)))
        ok = must(cdp, "instruktor: sessiya modalida Ko'chirish tugmasi",
                  'Array.from(document.querySelectorAll("button")).some(b=>b.textContent.includes("Ko\'chirish")&&!b.textContent.includes("Qayta rejalashtirildi"))')
        ok2 = must(cdp, "instruktor: sessiya modalida Bekor qilish tugmasi",
                   'Array.from(document.querySelectorAll("#modal button, .modal button, body button")).some(b=>b.textContent.includes("✕")&&b.textContent.includes("Bekor qilish"))')
        cdp.shot("inst_actions")
        if not ok2:
            raise RuntimeError("Bekor qilish tugmasi topilmadi — davom etmayman")
        # Bekor qilish oqimi: tugma -> sabab -> tasdiqlash
        cdp.ev("Array.from(document.querySelectorAll('button')).find(b=>b.textContent.includes('✕')&&b.textContent.includes('Bekor qilish')).click()")
        ok = must(cdp, "instruktor: sabab tanlash modali ochildi",
                  'Array.from(document.querySelectorAll("select")).some(s=>s.options.length>=5)')
        cdp.ev("""
        (()=>{const sel=Array.from(document.querySelectorAll('select')).find(s=>s.options.length>=5);
          if(!sel)return false;
          sel.value='school'; sel.dispatchEvent(new Event('change',{bubbles:true})); return true})()
        """)
        cdp.ev("""
        (()=>{const btns=Array.from(document.querySelectorAll('.modal button')).filter(b=>b.textContent.includes('✕')&&b.textContent.includes('Bekor qilish'));
          const btn=btns.pop(); if(!btn)return false; btn.click(); return true})()
        """)
        ok = must(cdp, "instruktor: bekor qilish tasdiqlandi (sabab modali yopildi)",
                  'document.querySelectorAll(".modal").length === 1')
        check("instruktor: sessiya 'Bekor qilingan' holatga o'tdi",
              must(cdp, "instruktor: sessiya 'Bekor qilingan' holatga o'tdi (modal)",
                   'document.body.innerText.includes("Bekor qilingan")'))
        check("instruktor: sabab matni ko'rindi",
              bool(cdp.ev('document.body.innerText.includes("Bekor qilish sababi")')))
        cdp.shot("inst_cancelled")
        # Modalni yopamiz
        cdp.ev("(()=>{const b=Array.from(document.querySelectorAll('button')).find(x=>x.textContent.trim()==='Yopish');if(b)b.click();return true})()")

        # ---------- TALABA: sabab va holatni ko'radi ----------
        logout(cdp)
        login(cdp, "usrL_00004", "usrP_00004", "student")
        check("talaba: nav ochildi", cdp.wait('!!document.querySelector(\'.nav-item[data-view="history"]\')'))
        cdp.ev('document.querySelector(\'.nav-item[data-view="history"]\').click()')
        ok = must(cdp, "talaba: tarix jadvalida cancell sessiya bor",
                  'document.querySelectorAll("#view table.tbl tbody tr").length >= 1')
        click_row = """
        (()=>{const rows=Array.from(document.querySelectorAll('#view table.tbl tbody tr.row-click'));
          const r=rows.find(x=>x.innerText.includes('11:00–12:00')&&x.innerText.includes('Bekor qilingan'));
          if(!r)return false; r.click(); return true})()
        """
        check("talaba: cancell qator bosildi", bool(cdp.ev(click_row)))
        ok = must(cdp, "talaba: modalda 'Bekor qilingan' status + sabab",
                  'Array.from(document.querySelectorAll(".modal")).some(m=>m.innerText.includes("Bekor qilingan")&&m.innerText.includes("Bekor qilish sababi"))')
        check("talaba: sabab qiymati 'school' ko'rindi",
              bool(cdp.ev('Array.from(document.querySelectorAll(".modal")).some(m=>m.innerText.includes("Bekor qilish sababi")&&m.innerText.includes("school"))')))
        cdp.shot("student_sees_cancelled")

        if FAILS:
            print("\n=== NATIJA: " + str(len(FAILS)) + " xato ===")
            for f in FAILS:
                print("  -", f)
            sys.exit(1)
        print("\n=== M13-A E2E: 100% OK ===")
    finally:
        if cdp:
            try:
                cdp.proc.terminate()
            except Exception:
                pass


if __name__ == "__main__":
    main()