"""Login sahifasidagi rol tugmalari tiklandimi — CDP tekshiruvi.
     py -X utf8 tools_verify_login_roles.py
Tekshiradi: 3 tugma ko'rinadi, tanlash/bekor qilish, tillar, noto'g'ri rol xatosi,
avtomatik aniqlash (rolsiz kirish) va tanlangan rol bilan kirish.
"""
import base64
import json
import time
from pathlib import Path

from tools_e2e_m13 import CDP, BASE, PORT, check, FAILS

ROOT = Path(__file__).resolve().parent
SHOT = ROOT / "shots" / "08_login_roles.png"


def must(cdp, name, expr, timeout=20):
    if cdp.wait(expr, timeout):
        check(name, True)
        return True
    check(name, False)
    try:
        print("   [debug] body:", repr(cdp.ev("document.body.innerText.slice(0,400)"))[:400])
    except Exception as e:
        print("   [debug] err:", e)
    return False


def shot(cdp, path):
    try:
        (Path(path).parent).mkdir(parents=True, exist_ok=True)
        r = cdp.cmd("Page.captureScreenshot", {"format": "png"})
        Path(path).write_bytes(base64.b64decode(r["data"]))
        print("   screenshot ->", path)
    except Exception as e:
        print("  (screenshot xatosi:", e, ")")


def fill_login(cdp, login, password):
    cdp.ev(f"""(()=>{{const u=document.querySelector('#login-username');const p=document.querySelector('#login-password');
        u.value='{login}'; u.dispatchEvent(new Event('input',{{bubbles:true}}));
        p.value='{password}'; p.dispatchEvent(new Event('input',{{bubbles:true}})); return true}})()""")


def submit(cdp):
    cdp.ev("document.querySelector('#login-form').requestSubmit(); true")


def pick_role(cdp, role):
    """Rol tugmasini bosadi (yana bossa — bekor)."""
    expr = ("(()=>{const b=document.querySelector('#login-form .role-btn[data-role=\"" + role + "\"]');"
            "if(!b)return false; b.click(); return true})()")
    return cdp.ev(expr)


def reload_login(cdp):
    cdp.cmd("Page.navigate", {"url": BASE + "/"})
    return must(cdp, "login sahifa ochildi",
                "!!document.querySelector('#login-screen') && !document.querySelector('#login-screen').classList.contains('hidden')")


def main():
    cdp = CDP()
    try:
        # ---------------- A) Tugmalar ko'rinadi ----------------
        assert reload_login(cdp)
        n = cdp.ev("document.querySelectorAll('#login-form .role-btn').length")
        check("A: 3 ta rol tugmasi bor (talaba/instruktor/admin)", n == 3)
        labels = cdp.ev("JSON.stringify(Array.from(document.querySelectorAll('#login-form .role-btn span')).map(s=>s.textContent.trim()))")
        check("A: tugma yorliqlari UZ (Talaba/Instruktor/Admin)", labels == '["Talaba","Instruktor","Admin"]')
        active = cdp.ev("document.querySelectorAll('#login-form .role-btn.active').length")
        check("A: hech biri oldindan tanlanmagan (chalkashlik yo'q)", active == 0)
        pressed = cdp.ev("document.querySelectorAll('#login-form .role-btn[aria-pressed=\"true\"]').length")
        check("A: aria-pressed hammasi false (a11y)", pressed == 0)
        shot(cdp, SHOT)

        # ---------------- B) Tanlash / bekor qilish ----------------
        pick_role(cdp, "instructor")
        check("B: instruktor bosildi -> active", cdp.ev("document.querySelector('#login-form .role-btn[data-role=\"instructor\"]').classList.contains('active')"))
        check("B: faqat 1 tasi active", cdp.ev("document.querySelectorAll('#login-form .role-btn.active').length") == 1)
        pick_role(cdp, "instructor")
        check("B: yana bossa -> bekor (avtomatik rejim)", cdp.ev("document.querySelectorAll('#login-form .role-btn.active').length") == 0)
        pick_role(cdp, "admin")
        check("B: admin tanlandi", cdp.ev("document.querySelector('#login-form .role-btn[data-role=\"admin\"]').getAttribute('aria-pressed')") == "true")

        # ---------------- C) Tillar ----------------
        cdp.ev("document.querySelector('#login-lang button[data-lang=\"ru\"]').click()")
        labels = cdp.ev("JSON.stringify(Array.from(document.querySelectorAll('#login-form .role-btn span')).map(s=>s.textContent.trim()))")
        check("C: RU tilga almashtirildi (Ученик/Инструктор/Админ)", labels == '["Ученик","Инструктор","Админ"]')
        aria = cdp.ev("document.querySelector('.role-switch').getAttribute('aria-label')")
        check("C: aria-label RU (Выберите роль)", aria == "Выберите роль (необязательно)")
        cdp.ev("document.querySelector('#login-lang button[data-lang=\"uz\"]').click(); true")
        time.sleep(0.3)
        pick_role(cdp, "admin")

        # ---------------- D) Noto'g'ri rol xatosi ----------------
        pick_role(cdp, "student")  # talaba tanlab, admin bilan kirish
        fill_login(cdp, "admin", "admin123")
        submit(cdp)
        check("D: noto'g'ri rol -> wrong_role xatosi",
              must(cdp, "D: wrong_role alert ko'rindi",
                   "document.querySelector('#login-alert').classList.contains('show') && document.body.innerText.includes('hisob mos kelmaydi')"))

        # ---------------- E) To'g'ri rol tanlab kirish ----------------
        pick_role(cdp, "admin")
        submit(cdp)
        check("E: admin roli tanlanganda dashboard ochildi",
              cdp.wait("!!document.querySelector('.nav-item[data-view=\"dashboard\"]')", 20))
        shot(cdp, ROOT / "shots" / "09_login_roles_admin.png")

        # ---------------- F) Rolsiz (avtomatik) kirish ----------------
        cdp.evp("(async()=>{try{await fetch('/api/auth/logout',{method:'POST',headers:{'X-Requested-With':'Avtomaktab'}})}catch(e){};location.reload();return true})()")
        cdp.wait("!document.querySelector('#login-screen').classList.contains('hidden')", 15)
        fill_login(cdp, "usrL_00001", "usrP_00001")   # instruktor, rol tanlanmaydi
        submit(cdp)
        check("F: rolsiz kirish -> instruktor avtomatik aniqlandi",
              cdp.wait("!!document.querySelector('.nav-item[data-view=\"schedule\"]')", 20))
        shot(cdp, ROOT / "shots" / "10_login_roles_auto.png")

    finally:
        cdp.ws.close()
        try:
            cdp.proc.terminate()
        except Exception:
            pass

    print("\n=== NATIJA ===")
    if FAILS:
        print(f"MUAMMOLAR ({len(FAILS)}): " + "; ".join(FAILS))
        raise SystemExit(1)
    print("BARCHA TEKSHIRUVLAR OK")


if __name__ == "__main__":
    main()