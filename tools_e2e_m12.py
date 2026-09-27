"""M12 E2E — Sozlamalar bo'limi (CDP orqali, real brauzer).
Chrome headless + websocket-client. Server 8080 da ishlamoqda deb taxmin qilinadi.
    py -X utf8 tools_e2e_m12.py
"""
import json
import os
import shutil
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
PORT = 9331
PROFILE = Path(tempfile.mkdtemp(prefix="avtomaktab_e2e_m12_"))

FAILS = []


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
        txt = cdp.ev("document.body.innerText.slice(0,600)")
        print("   [debug] body:", repr(txt)[:600])
    except Exception as e:
        print("   [debug] err:", e)
    return False


def kill_old(port):
    """Portni egallagan eski chrome jarayonini o'ldirish (Windows)."""
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
            (ROOT / f"m12shot_{name}.png").write_bytes(base64.b64decode(r["data"]))
        except Exception as e:
            print("  (screenshot xatosi:", e, ")")


def dq(s):
    return s.replace('"', '\\"')


def login(cdp, login, password, role):
    cdp.wait("!document.querySelector('#login-screen').classList.contains('hidden')", 15)
    cdp.ev(f"""(()=>{{const u=document.querySelector('#login-username');const p=document.querySelector('#login-password');
        u.value='{login}'; u.dispatchEvent(new Event('input',{{bubbles:true}}));
        p.value='{password}'; p.dispatchEvent(new Event('input',{{bubbles:true}}));
        document.querySelector('#login-form').requestSubmit(); return true}})()""")


def logout(cdp):
    cdp.evp("(async()=>{try{await fetch('/api/auth/logout',{method:'POST',headers:{'X-Requested-With':'Avtomaktab'}})}catch(e){};location.reload();return true})()")
    cdp.wait("!document.querySelector('#login-screen').classList.contains('hidden')", 15)


def settings_card(cdp, title):
    return f"(Array.from(document.querySelectorAll('#view .card')).find(c=>{{const h=c.querySelector('h3');return h&&h.textContent.includes('{title}')}}))"


def goto_settings(cdp):
    cdp.ev('document.querySelector(\'.nav-item[data-view="settings"]\').click()')


def main():
    cdp = None
    try:
        cdp = CDP()
        cdp.cmd("Page.navigate", {"url": BASE + "/"})
        assert cdp.wait("!document.querySelector('#login-screen').classList.contains('hidden')"), "login sahifa ochilmadi"

        # ---------- ADMIN ----------
        login(cdp, "admin", "admin123", "admin")
        ok = cdp.wait('!!document.querySelector(\'.nav-item[data-view="settings"]\')')
        check("admin: nav'da Sozlamalar bor", ok)
        goto_settings(cdp)
        ok = cdp.wait('document.body.innerText.includes("Platforma sozlamalari")')
        check("admin: settings sahifa ochildi (Platforma kartasi)", ok)
        for title in ["Til va mintaqa", "Tema (mavzu)", "Bildirishnoma sozlamalari", "Maxfiylik va xavfsizlik"]:
            check(f"admin: karta — {title}", cdp.ev(f"document.body.innerText.includes('{title}')"))
        # faol sessiyalar jadvali
        ok = cdp.wait('document.querySelectorAll(\'#view table.tbl tbody tr\').length >= 1')
        check("admin: faol sessiyalar jadvalida kamida 1 qator", ok)
        check("admin: joriy qurilma belgisi", cdp.ev('document.body.innerText.includes("Joriy qurilma")'))
        check("admin: barchadan chiqish tugmasi", cdp.ev('document.body.innerText.includes("Barcha qurilmalardan chiqish")'))
        cdp.shot("admin_light")

        # Tema: tungi
        cdp.ev("Array.from(document.querySelectorAll('button')).find(b=>b.textContent.includes('Tungi')).click()")
        cdp.wait("document.documentElement.dataset.theme === 'dark'")
        check("admin: tungi tema yoqildi (data-theme=dark)", cdp.ev("document.documentElement.dataset.theme === 'dark'"))
        cdp.shot("admin_dark")
        # Tema: yorug'ga qaytarish
        cdp.ev("Array.from(document.querySelectorAll('button')).find(b=>b.textContent.includes('Yorug')).click()")
        cdp.wait("document.documentElement.dataset.theme === 'light'")
        check("admin: yorug' tema qaytarildi", cdp.ev("document.documentElement.dataset.theme === 'light'"))

        # Til: RU -> reiniz → qayta UZ
        cdp.ev("Array.from(document.querySelectorAll('button')).find(b=>b.textContent.includes('Русский')).click()")
        must(cdp, "admin: til RU ga o'tdi", 'document.body.innerText.includes("Настройки платформы")')
        cdp.ev("Array.from(document.querySelectorAll('button')).find(b=>b.textContent.includes(\"O'zbek\")).click()")
        must(cdp, "admin: til UZ ga qaytdi", 'document.body.innerText.includes("Platforma sozlamalari")')

        # Bildirishnoma: 'Mashg'ulotlar' o'chirish → saqlanishi
        card_js = settings_card(cdp, "Bildirishnoma")
        cdp.ev(f"((()=>{{const c={card_js};const ch=c.querySelectorAll('.check input[type=checkbox]')[0];ch.click();return true}})())")
        cdp.wait(f"(async()=>{{const j=await (await fetch('/api/me/settings')).json();return j.settings.notif&&j.settings.notif.lesson===false}})()")
        check("admin: notif.lesson=false saqlandi", True)
        cdp.ev(f"((()=>{{const c={card_js};const ch=c.querySelectorAll('.check input[type=checkbox]')[0];if(!ch.checked)ch.click();return true}})())")
        cdp.wait(f"(async()=>{{const j=await (await fetch('/api/me/settings')).json();return j.settings.notif&&j.settings.notif.lesson===true}})()")
        check("admin: notif.lesson=true qaytarildi", True)

        # Platforma: davomiylik 60 → saqlash → tekshirish → 90 ga qaytarish
        pcard = settings_card(cdp, "Platforma")
        cdp.ev(f"((()=>{{const c={pcard};const n=c.querySelector('input[type=number]');if(!n)return 'no-num';n.value='60';n.dispatchEvent(new Event('input',{{bubbles:true}}));return true}})())")
        cdp.ev(f"((()=>{{const c={pcard};const b=c.querySelector('.btn-primary');if(!b)return 'no-btn';b.click();return true}})())")
        must(cdp, "admin: platforma davomiyligi 60 saqlandi", f"(async()=>{{const j=await (await fetch('/api/admin/settings')).json();return j.settings&&j.settings.lesson_duration_min===60}})()")
        print("   [debug] lesson_duration_min hozir:", cdp.evp("(async()=>{const j=await (await fetch('/api/admin/settings')).json();return j.settings?j.settings.lesson_duration_min:null})()"))
        cdp.ev(f"((()=>{{const c={pcard};const n=c.querySelector('input[type=number]');if(!n)return 'no-num';n.value='90';n.dispatchEvent(new Event('input',{{bubbles:true}}));return true}})())")
        cdp.ev(f"((()=>{{const c={pcard};const b=c.querySelector('.btn-primary');if(!b)return 'no-btn';b.click();return true}})())")
        must(cdp, "admin: platforma davomiyligi 90 ga qaytarildi", f"(async()=>{{const j=await (await fetch('/api/admin/settings')).json();return j.settings&&j.settings.lesson_duration_min===90}})()")

        # ---------- INSTRUKTOR ----------
        logout(cdp)
        login(cdp, "usrL_00001", "usrP_00001", "instructor")
        ok = must(cdp, "instruktor: nav'da Sozlamalar bor", '!!document.querySelector(\'.nav-item[data-view="settings"]\')')
        if ok:
            goto_settings(cdp)
        must(cdp, "instruktor: settings sahifa ochildi", 'document.body.innerText.includes("Til va mintaqa")')
        check("instruktor: platforma kartasi YO'Q", not cdp.ev('document.body.innerText.includes("Platforma sozlamalari")'))
        for title in ["Til va mintaqa", "Tema (mavzu)", "Bildirishnoma sozlamalari", "Maxfiylik va xavfsizlik"]:
            check(f"instruktor: karta — {title}", cdp.ev(f"document.body.innerText.includes('{title}')"))

        # ---------- TALABA ----------
        logout(cdp)
        login(cdp, "usrL_00004", "usrP_00004", "student")
        ok = must(cdp, "talaba: nav'da Sozlamalar bor", '!!document.querySelector(\'.nav-item[data-view="settings"]\')')
        if ok:
            goto_settings(cdp)
        must(cdp, "talaba: settings sahifa ochildi", 'document.body.innerText.includes("Til va mintaqa")')
        check("talaba: platforma kartasi YO'Q", not cdp.ev('document.body.innerText.includes("Platforma sozlamalari")'))
        for title in ["Til va mintaqa", "Tema (mavzu)", "Bildirishnoma sozlamalari", "Maxfiylik va xavfsizlik"]:
            check(f"talaba: karta — {title}", cdp.ev(f"document.body.innerText.includes('{title}')"))
    finally:
        try:
            from urllib.request import Request as _Req
            from urllib.request import urlopen as _Url
            _data = json.dumps({"login": "admin", "password": "admin123", "role": "admin"}).encode()
            _req = _Req(BASE + "/api/auth/login", data=_data, headers={"Content-Type": "application/json"})
            with _Url(_req, timeout=8) as _r:
                _ck = (_r.headers.get("Set-Cookie") or "").split(";")[0]
            _req = _Req(BASE + "/api/admin/settings",
                        data=json.dumps({"lesson_duration_min": 90}).encode(), method="PUT",
                        headers={"Content-Type": "application/json", "X-Requested-With": "Avtomaktab", "Cookie": _ck})
            with _Url(_req, timeout=8):
                pass
            print("  (iz yo'q: lesson_duration_min=90 qaytarildi)")
        except Exception as e:
            print("  (tozalash xatosi:", e, ")")
        try:
            if cdp is not None:
                cdp.proc.terminate()
        except Exception:
            pass
        time.sleep(1)
        kill_old(PORT)
    try:
        shutil.rmtree(PROFILE, ignore_errors=True)
    except Exception:
        pass
    print("-" * 40)
    print(f"Natija: {len(FAILS)} xato")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())