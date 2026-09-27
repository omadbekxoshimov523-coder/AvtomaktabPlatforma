"""M7+M8+M1+M3 — CDP E2E tekshiruvi.
     py -X utf8 tools_verify_m7m8m1m3.py
- M7: til tugmalari faqat nomlar (UZ/RU/EN kodlari yo'q)
- M8: tema — faqat Kunduzgi/Tungi (Tizim yo'q), applyTheme default light
- M1: bosh sahifalarda "Tezkor havolalar" yo'q
- M3: sidebar'da "Bugun" yo'q, today sahifa funksiyasi yo'q
Har rol uchun alohida CDP instansiya (sessiya tozaligi uchun).
"""
import base64
import time
from pathlib import Path

from tools_e2e_m13 import CDP, BASE, check, FAILS

ROOT = Path(__file__).resolve().parent
SHOTS = ROOT / "shots"


def shot(cdp, path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    r = cdp.cmd("Page.captureScreenshot", {"format": "png"})
    Path(path).write_bytes(base64.b64decode(r["data"]))
    print("   screenshot ->", path)


def ev(cdp, e):
    return cdp.ev(e)


def login(cdp, log, pw):
    cdp.ev(f"""(()=>{{const u=document.querySelector('#login-username');const p=document.querySelector('#login-password');
        u.value='{log}'; p.value='{pw}';
        u.dispatchEvent(new Event('input',{{bubbles:true}})); p.dispatchEvent(new Event('input',{{bubbles:true}})); return true}})()""")
    cdp.ev("document.querySelector('#login-form').requestSubmit(); true")


def check_login_lang_buttons(cdp):
    langs = ev(cdp, "Array.from(document.querySelectorAll('#login-lang button')).map(b=>b.textContent.trim()).join('|')")
    return langs, langs == "O'zbek|Русский|English"


def has_today_nav(cdp):
    return ev(cdp, "!!document.querySelector('#sidebar-nav .nav-item[data-view=today]')")


def has_quick_links(cdp):
    return ev(cdp, "!!document.querySelector('.quick-links')")


def has_tezkor_text(cdp):
    return ev(cdp, "document.body.innerText.includes('Tezkor havolalar')")


def theme_labels(cdp):
    return ev(cdp,
        "(()=>{const c=[...document.querySelectorAll('.card')]"
        ".find(x=>x.querySelector('.card-title')&&x.querySelector('.card-title').textContent.includes('Tema'));"
        "return c?Array.from(c.querySelectorAll('.lang-btn')).map(b=>b.textContent.trim()).join('|'):'no-card'})()")


def theme_apply(cdp, text):
    ev(cdp,
        "(()=>{const c=[...document.querySelectorAll('.card')]"
        "  .find(x=>x.querySelector('.card-title')&&x.querySelector('.card-title').textContent.includes('Tema'));"
        "if(!c)return false;"
        "for(const b of c.querySelectorAll('.lang-btn')){"
        + ("if(b.textContent.includes('" + text + "')){b.click(); return true}")
        + "}return false})()")
    time.sleep(0.4)
    return ev(cdp, "document.documentElement.dataset.theme")


def role_checks(cdp, role, creds, tag):
    _ = role
    cdp.cmd("Page.navigate", {"url": BASE + "/"})
    cdp.wait("!!document.querySelector('#login-screen')")
    login(cdp, creds[0], creds[1])
    check(tag + ": kirish", cdp.wait("!!App.me", 15))
    time.sleep(0.8)

    # M3: Bugun nav + sahifa yo'q
    today_nav = has_today_nav(cdp)
    check(tag + ": sidebar'da 'Bugun' yo'q", not today_nav)
    fn = ev(cdp, "typeof window." + tag + "Views.today")
    check(tag + ": today sahifa funksiyasi yo'q", fn == "undefined")

    # M1: bosh sahifada tezkor havolalar yo'q
    check(tag + ": .quick-links elementi yo'q", not has_quick_links(cdp))
    check(tag + ": 'Tezkor havolalar' matni yo'q", not has_tezkor_text(cdp))

    # M8: tema kartasi
    cdp.ev("App.go('settings'); true")
    cdp.wait("!!document.querySelector('.card')", 10)
    time.sleep(1.0)
    labels = theme_labels(cdp)
    check(tag + ": tema — faqat Kunduzgi/Tungi", labels == "☀️ Kunduzgi|🌙 Tungi")
    dark = theme_apply(cdp, "Tungi")
    check(tag + ": Tungi -> data-theme=dark", dark == "dark")
    shot(cdp, SHOTS / ("20_m8_dark_" + tag.lower() + ".png"))
    light = theme_apply(cdp, "Kunduzgi")
    check(tag + ": Kunduzgi -> data-theme=light", light == "light")


def main():
    # M7: login ekranidagi til tugmalari (login oldidan)
    cdp0 = CDP()
    cdp0.cmd("Page.navigate", {"url": BASE + "/"})
    cdp0.wait("!!document.querySelector('#login-screen')")
    langs, ok = check_login_lang_buttons(cdp0)
    check("M7: login tugmalari nomlar (kod yo'q): " + langs, ok)
    shot(cdp0, SHOTS / "21_m7_login_lang_names.png")
    del cdp0

    role_checks(CDP(), "admin", ("admin", "admin123"), "Admin")
    role_checks(CDP(), "instructor", ("usrL_00001", "usrP_00001"), "Instructor")
    role_checks(CDP(), "student", ("usrL_00004", "usrP_00004"), "Student")

    # M7: topbardagi til tugmalari ham nomlar (talaba sessiyasidan so'ng qayta)
    cdp = CDP()
    cdp.cmd("Page.navigate", {"url": BASE + "/"})
    cdp.wait("!!document.querySelector('#login-screen')")
    login(cdp, "usrL_00004", "usrP_00004")
    cdp.wait("!!App.me", 15)
    time.sleep(0.8)
    top = ev(cdp, "Array.from(document.querySelectorAll('#app-lang-switch button')).map(b=>b.textContent.trim()).join('|')")
    check("M7: topbar tugmalari nomlar: " + top, top == "O'zbek|Русский|English")
    shot(cdp, SHOTS / "22_m7_topbar_lang_names.png")

    print("\n=== NATIJA ===")
    if FAILS:
        print("Xatolar:", len(FAILS))
        for f in FAILS:
            print("  -", f)
    else:
        print("  Hammasi OK")
    raise SystemExit(1 if FAILS else 0)


if __name__ == "__main__":
    main()