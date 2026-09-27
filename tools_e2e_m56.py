"""M5+M6 E2E:
M5 — Admin avtomobillar: kartalar teng balandlikda, action tugmalar pastda, uniform status select.
M6 — Instruktor O'Z mashinasini tahrirlay oladi (yangi qiymat saqlanadi va ko'rinadi).
    py -X utf8 tools_e2e_m56.py
"""
import json
import sqlite3
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
PORT = 9339
PROFILE = Path(tempfile.mkdtemp(prefix="avtomaktab_e2e_m56_"))

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
            (ROOT / f"m56shot_{name}.png").write_bytes(base64.b64decode(r["data"]))
        except Exception as e:
            print("  (screenshot xatosi:", e, ")")


def login(cdp, login, password):
    cdp.wait("!document.querySelector('#login-screen').classList.contains('hidden')", 15)
    cdp.ev(f"""(()=>{{const u=document.querySelector('#login-username');const p=document.querySelector('#login-password');
        u.value='{login}'; u.dispatchEvent(new Event('input',{{bubbles:true}}));
        p.value='{password}'; p.dispatchEvent(new Event('input',{{bubbles:true}}));
        document.querySelector('#login-form').requestSubmit(); return true}})()""")
    cdp.wait('!!document.querySelector("#sidebar-nav .nav-item")', 20)


def goto(cdp, view, marker_selector=None):
    ok = cdp.ev(f"""(()=>{{const b=document.querySelector(`.nav-item[data-view="{view}"]`);
        if(!b)return false; b.click(); return true;}})()""")
    if not ok:
        return False
    if marker_selector:
        return cdp.wait(f'!!document.querySelector({json.dumps(marker_selector)})', 15)
    return cdp.wait(f'!!document.querySelector(".nav-item[data-view="{view}"].active")', 15)


def main():
    orig_color = None
    con = sqlite3.connect(str(ROOT / "data" / "avtomaktab.db"))
    orig_color = con.execute("SELECT color FROM cars WHERE id=1").fetchone()[0]
    con.close()
    cdp = None
    try:
        cdp = CDP()
        cdp.cmd("Page.navigate", {"url": BASE + "/"})
        assert cdp.wait("!document.querySelector('#login-screen').classList.contains('hidden')"), "login ochilmadi"

        # ================= ADMIN: M5 =================
        login(cdp, "admin", "admin123")
        print("  [debug] nav:", (cdp.ev("document.querySelector('#sidebar-nav').innerText") or "")[:200])
        print("  [debug] cars nav mavjudmi:", cdp.ev('!!document.querySelector(\'.nav-item[data-view="cars"]\')'))
        cdp.shot("admin_login_debug")
        assert goto(cdp, "cars", ".cars-grid .card"), "cars sahifasi ochilmadi"
        assert cdp.wait('document.querySelectorAll(".cars-grid .card").length >= 1'), "kartalar chiqmadi"
        heights = cdp.ev("Array.from(document.querySelectorAll('.cars-grid .card')).map(c=>c.getBoundingClientRect().height)")
        check("M5: kamida 2 ta karta bor", len(heights) >= 2)
        check("M5: barcha kartalar teng balandlikda", len(set(round(h, 1) for h in heights)) == 1)
        # action qatori pastga mahkamlangan: card pastki padding qatlamida, kartalar orasida bir xil
        pinned = cdp.ev("""(()=>{const cs=Array.from(document.querySelectorAll('.cars-grid .card'));
            const d=cs.map(c=>{const a=c.querySelector('.car-actions'); if(!a)return null;
                const r=c.getBoundingClientRect(), ar=a.getBoundingClientRect();
                return Math.round(r.bottom-ar.bottom); }).filter(x=>x!==null);
            return d.length>0 && d.every(x=>x<=40) && new Set(d).size===1;})()""")
        check("M5: actions pastga mahkamlangan", bool(pinned))
        # uniform status select: kengliklar deyarli bir xil
        widths = cdp.ev("Array.from(document.querySelectorAll('.cars-grid .car-status-select')).map(s=>Math.round(s.getBoundingClientRect().width))")
        check("M5: status select uniform", len(set(widths)) <= 1)
        cdp.shot("admin_cars_equal_heights")

        # ================= INSTRUCTOR: M6 =================
        cdp.proc.terminate()
        time.sleep(1)
        cdp = CDP()
        cdp.cmd("Page.navigate", {"url": BASE + "/"})
        assert cdp.wait("!document.querySelector('#login-screen').classList.contains('hidden')"), "login ochilmadi"
        login(cdp, "usrL_00001", "usrP_00001")
        assert goto(cdp, "car", ".car-model"), "instructor car sahifasi ochilmadi"
        assert cdp.wait('Array.from(document.querySelectorAll("button")).some(b=>b.innerText.includes("Tahrirlash"))'), \
            "Tahrirlash tugmasi topilmadi"
        # boshqa instruktorning mashina emas — o'z mashinasi ko'rinmoqda
        page = cdp.ev("document.querySelector('.content').innerText")
        check("M6: instruktor o'z mashinasini ko'radi", "Chevrolet" in page and "Cobalt" in page)
        cdp.ev('Array.from(document.querySelectorAll("button")).find(b=>b.innerText.includes("Tahrirlash")).click()')
        assert cdp.wait('!!document.querySelector(".modal-overlay:not(.hidden)")'), "modal ochilmadi"
        # rang maydonini o'zgartiramiz (o'z qiymati orig_color bo'lgan input)
        changed = cdp.ev(f"""(()=>{{const m=document.querySelector('.modal-overlay:not(.hidden)');
            const inputs=m.querySelectorAll('input');
            let color=Array.from(inputs).find(i=>i.value==={json.dumps(orig_color)});
            if(!color)return false;
            color.value='M6-E2E-RANG';
            color.dispatchEvent(new Event('input',{{bubbles:true}}));
            return true;}})()""")
        check("M6: rang maydoni tahrirlandi", bool(changed))
        cdp.ev('Array.from(document.querySelectorAll(".modal-overlay:not(.hidden) button")).find(b=>b.innerText.includes("Saqlash")).click()')
        time.sleep(2)
        print("  [debug] modal soni:", cdp.ev('document.querySelectorAll(".modal-overlay:not(.hidden)").length'))
        print("  [debug] modal body:", (cdp.ev('document.querySelector(".modal-overlay:not(.hidden) .modal-body")?.innerText') or "")[:160])
        assert cdp.wait('document.querySelectorAll(".modal-overlay:not(.hidden)").length === 0', 10), "modal yopilmadi"
        assert cdp.wait('document.querySelector(".content").innerText.includes("M6-E2E-RANG")', 10), \
            "saqlangan rang ko'rinmadi"
        check("M6: tahrir saqlandi va ko'rinmoqda", True)
        cdp.shot("instructor_car_edited")

        if FAILS:
            print("\n=== NATIJA: " + str(len(FAILS)) + " xato ===")
            for f in FAILS:
                print("  -", f)
            sys.exit(1)
        print("\n=== M5+M6 E2E: 100% OK ===")
    finally:
        # tiklanish: car 1 rangni asliga qaytaramiz
        try:
            con = sqlite3.connect(str(ROOT / "data" / "avtomaktab.db"))
            if orig_color is not None:
                con.execute("UPDATE cars SET color=? WHERE id=1", (orig_color,))
                con.commit()
            con.close()
            print("  car#1 rangi qaytarildi:", orig_color)
        except Exception as e:
            print("  (raqam qaytarish xatosi:", e, ")")
        if cdp:
            try:
                cdp.proc.terminate()
            except Exception:
                pass


if __name__ == "__main__":
    main()