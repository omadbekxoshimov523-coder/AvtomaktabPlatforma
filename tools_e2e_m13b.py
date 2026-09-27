"""M13-B E2E — Admin analitika paneli (CDP, real brauzer).
Admin "Analitika" sahifasida oylik grafik, bekor ulushi va eng band
instruktorlar ro'yxatini ko'radi.
    py -X utf8 tools_e2e_m13b.py
"""
import json
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

import websocket  # pip: websocket-client

ROOT = Path(__file__).resolve().parent
BASE = "http://127.0.0.1:8080"
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
PORT = 9333
PROFILE = Path(tempfile.mkdtemp(prefix="avtomaktab_e2e_m13b_"))

FAILS = []


def api_health():
    try:
        with urllib.request.urlopen(BASE + "/api/health", timeout=5) as r:
            return r.status == 200
    except Exception:
        return False


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


def main():
    assert api_health(), "Server 8080 ishlamayapti"
    cdp = None
    try:
        cdp = CDP()
        cdp.cmd("Page.navigate", {"url": BASE + "/"})
        assert cdp.wait("!document.querySelector('#login-screen').classList.contains('hidden')"), "login sahifa ochilmadi"

        # ---------- ADMIN: Analitika ----------
        login(cdp, "admin", "admin123", "admin")
        ok = cdp.wait('!!document.querySelector(\'.nav-item[data-view="analytics"]\')')
        check("admin: nav ochildi (Analitika havolasi bor)", ok)
        cdp.ev('document.querySelector(\'.nav-item[data-view="analytics"]\').click()')

        # Yo'l xaritasi ochildi: 6 ta stat-karta
        ok = must(cdp, "analitika: stat-kartalar yuklandi (6 ta)",
                  'document.querySelectorAll("#view .stat-card").length >= 6')
        check("analitika: 'Jami mashg\'ulotlar' kartasi",
              bool(cdp.ev('document.body.innerText.includes("Jami mashg\'ulotlar")')))
        check("analitika: 'Bekor ulushi' kartasi",
              bool(cdp.ev('document.body.innerText.includes("Bekor ulushi")')))
        check("analitika: 'Soatlar' kartasi",
              bool(cdp.ev('document.body.innerText.includes("Soatlar")')))

        # Kunlik grafik: bar-chart ustunlari
        ok = must(cdp, "analitika: kunlik grafik chizildi",
                  'document.querySelectorAll("#view .bar-chart .chart-col").length >= 28')
        check("analitika: kunlik grafikda qiymat belgilari bor",
              bool(cdp.ev('document.querySelectorAll("#view .bar-chart .chart-val").length >= 28')))

        # Oylik tendentsiya grafigi
        ok = must(cdp, "analitika: oylik tendentsiya (12 ustun)",
                  '(function(){const charts=document.querySelectorAll("#view .bar-chart");' +
                  'return charts.length>=2 && charts[1].querySelectorAll(".chart-col").length===12})()')
        check("analitika: oylik grafikda oy nomlari",
              bool(cdp.ev('document.body.innerText.includes("Oylik tendentsiya")')))

        # Eng band instruktorlar
        ok = must(cdp, "analitika: eng band instruktorlar ro'yxati",
                  'document.body.innerText.includes("Eng band instruktorlar")')
        check("analitika: instruktor ro'yxatida kamida 1 qator",
              bool(cdp.ev('document.querySelectorAll("#view .rank").length >= 1')))
        cdp.shot("m13b_analytics")

        # Oy tanlovchi ishlaydi: boshqa oy tanlasak qayta yuklanadi
        cdp.ev("window.__m13bBefore = document.querySelector('#view .stat-card .stat-value').textContent")
        cdp.ev("""
        (()=>{const sels=Array.from(document.querySelectorAll('#view select'));
          const sel=sels.find(s=>s.options.length>=12 && s.options[0].value.includes('-'));
          if(!sel)return false;
          sel.value=sel.options[sel.options.length-2].value;
          sel.dispatchEvent(new Event('change',{bubbles:true})); return true})()
        """)
        changed = cdp.wait("""
        (()=>{const el=document.querySelector('#view .stat-card .stat-value');
          return el && !!window.__m13bBefore && el.textContent !== window.__m13bBefore})()
        """, 12)
        check("analitika: oy tanlanganda qayta yuklanadi", changed)
        cdp.shot("m13b_analytics_month")

        if FAILS:
            print("\n=== NATIJA: " + str(len(FAILS)) + " xato ===")
            for f in FAILS:
                print("  -", f)
            sys.exit(1)
        print("\n=== M13-B E2E: 100% OK ===")
    finally:
        if cdp:
            try:
                cdp.proc.terminate()
            except Exception:
                pass


if __name__ == "__main__":
    main()