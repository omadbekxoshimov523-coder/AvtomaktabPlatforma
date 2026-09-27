"""M8 E2E: admin Sozlamalar sahifasida "Platforma nomi" va "Asosiy filial" maydonlari yo'q;
sozlamalar karatasi boshqa maydonlar bilan ishlayveradi.
    py -X utf8 tools_e2e_m8.py
"""
import json
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
PORT = 9337
PROFILE = Path(tempfile.mkdtemp(prefix="avtomaktab_e2e_m8_"))

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


def login(cdp, login, password):
    cdp.wait("!document.querySelector('#login-screen').classList.contains('hidden')", 15)
    cdp.ev(f"""(()=>{{const u=document.querySelector('#login-username');const p=document.querySelector('#login-password');
        u.value='{login}'; u.dispatchEvent(new Event('input',{{bubbles:true}}));
        p.value='{password}'; p.dispatchEvent(new Event('input',{{bubbles:true}}));
        document.querySelector('#login-form').requestSubmit(); return true}})()""")
    cdp.wait('!!document.querySelector("#sidebar-nav .nav-item")', 20)


def main():
    cdp = None
    try:
        cdp = CDP()
        cdp.cmd("Page.navigate", {"url": BASE + "/"})
        assert cdp.wait("!document.querySelector('#login-screen').classList.contains('hidden')"), "login ochilmadi"
        login(cdp, "admin", "admin123")
        # Sozlamalar sahifasini ochamiz
        cdp.ev('document.querySelector(`.nav-item[data-view="settings"]`).click()')
        assert cdp.wait('document.querySelector(".content").innerText.includes("Sozlamalar")', 20), "settings ochilmadi"
        assert cdp.wait('document.querySelector(".content").innerText.includes("Soniyalar ichida") || document.querySelector(".content").innerText.includes("Ish vaqti") || document.querySelectorAll(".content .card").length >= 4', 25), "settings kartalari yuklanmadi"
        txt = cdp.ev("document.querySelector('.content').innerText") or ""
        print("  [debug] settings matni:", txt[:260].replace("\n", " | "))
        check("M8: 'Platforma nomi' maydoni yo'q", "Platforma nomi" not in txt)
        check("M8: 'Asosiy filial' maydoni yo'q", "Asosiy filial" not in txt)
        check("M8: boshqa sozlamalar maydonlari bor",
              "Mashg'ulot davomiyligi" in txt or "lesson" in txt.lower() or
              ("Ish vaqti" in txt.replace("Boshlanishi", "")) or "Ish vaqti" in txt)
        # Saqlash tugmasi mavjud (karta ishlayapti)
        check("M8: saqlash tugmasi bor", "Saqlash" in txt)
        if FAILS:
            print("\n=== NATIJA: " + str(len(FAILS)) + " xato ===")
            for f in FAILS:
                print("  -", f)
            sys.exit(1)
        print("\n=== M8 E2E: 100% OK ===")
    finally:
        if cdp:
            try:
                cdp.proc.terminate()
            except Exception:
                pass


if __name__ == "__main__":
    main()