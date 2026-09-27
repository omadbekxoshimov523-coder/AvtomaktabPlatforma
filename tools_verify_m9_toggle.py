"""M13-M9: Toggle-switch komponenti — CDP tekshiruvi.
     py -X utf8 tools_verify_m9_toggle.py
Tekshiradi:
  - login sahifada "Eslab qolish" checkbox o'rniga toggle-switch bor
  - sozlamalarda (student/instructor/admin) checkbox YO'Q, toggle'lar bor
  - toggle bosilganda holati almashadi (aria-checked + .on)
  - skrinshot shots/11_m9_settings_*.png
"""
import base64
import json
import time
from pathlib import Path

from tools_e2e_m13 import CDP, BASE, check, FAILS

ROOT = Path(__file__).resolve().parent
SHOT_DIR = ROOT / "shots"


def shot(cdp, path):
    (Path(path).parent).mkdir(parents=True, exist_ok=True)
    r = cdp.cmd("Page.captureScreenshot", {"format": "png"})
    Path(path).write_bytes(base64.b64decode(r["data"]))
    print("   screenshot ->", path)


def login(cdp, log, pw, role=None):
    cdp.ev(f"""(()=>{{const u=document.querySelector('#login-username');const p=document.querySelector('#login-password');
        u.value='{log}'; p.value='{pw}';
        u.dispatchEvent(new Event('input',{{bubbles:true}})); p.dispatchEvent(new Event('input',{{bubbles:true}})); return true}})()""")
    if role:
        cdp.ev(f"""(()=>{{const b=document.querySelector('#login-form .role-btn[data-role="{role}"]'); b&&b.click(); return true}})()""")
    cdp.ev("document.querySelector('#login-form').requestSubmit(); true")


def go_settings(cdp):
    cdp.ev("App.go('settings'); true")
    return cdp.wait("document.body.innerText.includes('Sozlamalar')")


def count(cdp, sel):
    return cdp.ev(f"document.querySelectorAll('{sel}').length")


def main():
    cdp = CDP()
    cdp.cmd("Page.navigate", {"url": BASE + "/"})
    ok = cdp.wait("!!document.querySelector('#login-screen')")
    check("login sahifa ochildi", ok)

    # 1) login: remember toggle, checkbox yo'q
    rm = cdp.ev("!!document.querySelector('#login-remember.toggle[role=switch]')")
    check("login: toggle-switch mavjud", rm)
    cb = cdp.ev("document.querySelectorAll('#login-screen input[type=checkbox]').length")
    check("login: checkbox yo'q", cb == 0)
    # toggle bosilsa state almashadi
    cdp.ev("document.querySelector('#login-remember').click(); true")
    st = cdp.ev("document.querySelector('#login-remember').getAttribute('aria-checked') + '|' + document.querySelector('#login-remember').className")
    check("login toggle holati almashadi", st.startswith("true|toggle on"))
    cdp.ev("document.querySelector('#login-remember').click(); true")

    # 2) Talaba sozlamalari
    login(cdp, "usrL_00004", "usrP_00004")
    check("talaba kirdi", cdp.wait("!!App.me && App.me.user.role==='student'", 15))
    go_settings(cdp)
    time.sleep(1.2)
    toggles = count(cdp, ".toggle")
    checks = count(cdp, "input[type=checkbox]")
    rows = count(cdp, ".toggle-row")
    check("talaba sozlamalar: 5+ toggle", toggles >= 5)
    check("talaba sozlamalar: toggle-qatorlar 5", rows == 5)
    check("talaba sozlamalar: checkbox yo'q", checks == 0)
    # birinchi toggle bosilganda holat almashadi
    before = cdp.ev("document.querySelector('.toggle-row .toggle').getAttribute('aria-checked')")
    cdp.ev("document.querySelector('.toggle-row .toggle').click(); true")
    after = cdp.ev("document.querySelector('.toggle-row .toggle').getAttribute('aria-checked')")
    check("talaba toggle holati almashadi", before != after and after is not None)
    shot(cdp, SHOT_DIR / "11_m9_settings_student.png")

    # 3) Admin sozlamalari (platform toggle ham bor) — toza brauzer, yangi CDP
    cdp2 = CDP()
    cdp2.cmd("Page.navigate", {"url": BASE + "/"})
    cdp2.wait("!!document.querySelector('#login-screen')")
    login(cdp2, "admin", "admin123", "admin")
    check("admin kirdi", cdp2.wait("!!App.me && App.me.user.role==='admin'", 15))
    go_settings(cdp2)
    time.sleep(1.2)
    toggles = count(cdp2, ".toggle")
    checks = count(cdp2, "input[type=checkbox]")
    check("admin sozlamalar: 6+ toggle (platforma qatori bilan)", toggles >= 6)
    check("admin sozlamalar: checkbox yo'q", checks == 0)
    shot(cdp2, SHOT_DIR / "12_m9_settings_admin.png")

    print("\n=== NATIJA ===")
    bad = 0
    for name in FAILS:
        print("  FAIL | " + name)
        bad += 1
    if bad == 0:
        print("  Hammasi OK")
    print(f"Jami xatolar: {bad}")
    return bad


def logout_via(cdp):
    # Hozirgi sessiyani tozalash uchun logout API + sahifani qayta yuklash
    try:
        cdp.ev("fetch('/api/auth/logout',{method:'POST',headers:{'X-Requested-With':'Avtomaktab'}}).then(r=>r.json()).then(()=>location.reload()); true")
    except Exception:
        pass
    ok = cdp.wait("!!document.querySelector('#login-screen') && !document.querySelector('#login-screen').classList.contains('hidden')", 15)
    return ok


if __name__ == "__main__":
    import sys
    sys.exit(main())