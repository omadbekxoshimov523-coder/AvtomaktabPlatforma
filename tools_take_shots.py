"""Yangi dizayn skrinshotlari: login + admin/instruktor/talaba dashboard."""
import base64
import json
import os
import subprocess
import tempfile
import time
import urllib.request

import websocket

PORT = 9336
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
PROFILE = tempfile.mkdtemp(prefix="avtomaktab_design_")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "shots")
os.makedirs(OUT, exist_ok=True)

out = subprocess.run(["netstat", "-ano"], capture_output=True, text=True, timeout=15).stdout
pids = set()
for line in out.splitlines():
    parts = line.split()
    if len(parts) >= 5 and f":{PORT}" in parts[1] and parts[3] == "LISTENING":
        pids.add(parts[4])
for pid in pids:
    subprocess.run(["taskkill", "/F", "/PID", pid], capture_output=True, text=True, timeout=10)
time.sleep(0.5)

proc = subprocess.Popen(
    [CHROME, f"--remote-debugging-port={PORT}", "--headless=new",
     "--no-first-run", "--no-default-browser-check", "--disable-gpu",
     "--disable-extensions", "--remote-allow-origins=*",
     "--window-size=1440,900",
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
    raise RuntimeError("no chrome")

ws = websocket.create_connection(ws_url, timeout=60)
mid = 0


def cmd(method, params=None):
    global mid
    mid += 1
    ws.send(json.dumps({"id": mid, "method": method, "params": params or {}}))
    while True:
        m = json.loads(ws.recv())
        if m.get("id") == mid:
            return m.get("result", {})


def ev(expr):
    r = cmd("Runtime.evaluate", {"expression": expr, "returnByValue": True})
    return r.get("result", {}).get("value")


def evp(expr):
    r = cmd("Runtime.evaluate", {"expression": expr, "returnByValue": True, "awaitPromise": True})
    if r.get("exceptionDetails"):
        raise RuntimeError(r["exceptionDetails"])
    return r.get("result", {}).get("value")


def wait(expr, timeout=25):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            if evp(expr):
                return True
        except Exception:
            pass
        time.sleep(0.25)
    return False


def shot(name):
    r = cmd("Page.captureScreenshot", {"format": "png"})
    data = base64.b64decode(r.get("data", ""))
    path = os.path.join(OUT, name)
    with open(path, "wb") as f:
        f.write(data)
    print("shot:", name, len(data), "bytes")


def do_login(login, password):
    evp(f"""(()=>{{const u=document.querySelector('#login-username');
u.value='{login}'; u.dispatchEvent(new Event('input',{{bubbles:true}}));
const p=document.querySelector('#login-password');
p.value='{password}'; p.dispatchEvent(new Event('input',{{bubbles:true}}));
document.querySelector('#login-form').requestSubmit(); return true}})()""")


def logout():
    evp("(async()=>{try{await fetch('/api/auth/logout',{method:'POST',headers:{'X-Requested-With':'Avtomaktab'}})}catch(e){};location.reload();return true})()")
    wait("!document.querySelector('#login-screen').classList.contains('hidden')", 20)


cmd("Page.enable")
cmd("Runtime.enable")
cmd("Emulation.setDeviceMetricsOverride", {"width": 1440, "height": 900, "deviceScaleFactor": 1, "mobile": False})
cmd("Page.navigate", {"url": "http://127.0.0.1:8080/"})
wait("!document.querySelector('#login-screen').classList.contains('hidden')")
time.sleep(0.6)
shot("01_login.png")

# --- Admin ---
do_login("admin", "admin123")
wait("!!document.querySelector('.nav-item[data-view=analytics]')")
time.sleep(1.4)
shot("02_admin_dashboard.png")
ev("document.querySelector('.nav-item[data-view=analytics]').click()")
wait("!!document.querySelector('.chart-col') || !!document.querySelector('.grid-stats')")
time.sleep(1.4)
shot("03_admin_analytics.png")
logout()

# --- Instruktor ---
do_login("usrL_00001", "usrP_00001")
wait("!!document.querySelector('.nav-item[data-view=schedule]')")
time.sleep(1.4)
shot("04_instructor.png")
ev("document.querySelector('.nav-item[data-view=schedule]').click()")
time.sleep(1.4)
shot("05_instructor_schedule.png")
logout()

# --- Talaba ---
do_login("usrL_00004", "usrP_00004")
wait("!!document.querySelector('.nav-item[data-view=history]')")
time.sleep(1.4)
shot("06_student.png")

# Tungi rejim
ev("document.documentElement.setAttribute('data-theme','dark')")
time.sleep(1.0)
shot("07_student_dark.png")
logout()

try:
    proc.terminate()
except Exception:
    pass
print("DONE")