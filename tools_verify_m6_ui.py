"""M6: 2FA SMS (QR'siz) — UI E2E (CDP, real brauzer).
     py -X utf8 tools_verify_m6_ui.py
- Profil > 2FA "Yoqish": parol + telefon so'raladi, QR/secret YO'Q
- Kod bosqichi: "SMS kod yuborildi" — faqat kod maydoni, QR YO'Q
- Kod bildirishnoma (simulyatsiya) dan o'qiladi va kiritiladi
- 2FA yoqilgach badge; "O'chirish" parol bilan (kod so'ralmaydi)
Test so'ngida foydalanuvchi 2FA OFF holatga qaytadi, test izlari tozalanadi.
"""
import base64
import re
import sqlite3
import time
from pathlib import Path

from tools_e2e_m13 import CDP, BASE, check, FAILS

ROOT = Path(__file__).resolve().parent
DB = ROOT / "data" / "avtomaktab.db"
SHOTS = ROOT / "shots"
LOGIN = "usrL_00004"
PASS = "usrP_00004"
PHONE = "+998901112233"


def shot(cdp, path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    r = cdp.cmd("Page.captureScreenshot", {"format": "png"})
    Path(path).write_bytes(base64.b64decode(r["data"]))
    print("   screenshot ->", path)


def login(cdp, log, pw):
    cdp.ev(f"""(()=>{{const u=document.querySelector('#login-username');const p=document.querySelector('#login-password');
        u.value='{log}'; p.value='{pw}';
        u.dispatchEvent(new Event('input',{{bubbles:true}})); p.dispatchEvent(new Event('input',{{bubbles:true}})); return true}})()""")
    cdp.ev("document.querySelector('#login-form').requestSubmit(); true")


def ev(cdp, e):
    return cdp.ev(e)


def uid_of():
    con = sqlite3.connect(DB)
    uid = con.execute("SELECT id FROM users WHERE login=?", (LOGIN,)).fetchone()[0]
    con.close()
    return uid


def latest_code(uid):
    con = sqlite3.connect(DB)
    row = con.execute(
        "SELECT body FROM notifications WHERE user_id=? AND type='2fa' ORDER BY id DESC LIMIT 1",
        (uid,)).fetchone()
    con.close()
    if not row:
        return None
    m = re.search(r"\d{6}", row[0])
    return m.group() if m else None


def twofa_row(cdp):
    """2FA qatori (.kv) ichidagi .v matni."""
    return ev(cdp,
        "(()=>{const kv=[...document.querySelectorAll('.kv')]"
        ".find(x=>x.querySelector('.k')&&x.querySelector('.k').textContent.includes('Ikki bosqichli'));"
        "return kv?kv.querySelector('.v').innerText:''})()")


def click_twofa_btn(cdp, text_keyword):
    """2FA qatoridagi tugmani bosadi (matn chastotasi orqali)."""
    kw = text_keyword.replace("'", "\\'")
    return ev(cdp,
        "(()=>{const kv=[...document.querySelectorAll('.kv')]"
        ".find(x=>x.querySelector('.k')&&x.querySelector('.k').textContent.includes('Ikki bosqichli'));"
        "if(!kv)return false;"
        "for(const b of kv.querySelectorAll('button')){"
        + ("if(b.textContent.includes('" + kw + "')){b.click(); return true}")
        + "}"
        "return false})()")


def main():
    uid = uid_of()
    # Boshlanish holati toza: 2FA OFF, eski test izlari yo'q
    con = sqlite3.connect(DB)
    con.execute("DELETE FROM notifications WHERE user_id=? AND type='2fa'", (uid,))
    con.execute("DELETE FROM twofa_codes WHERE user_id=?", (uid,))
    con.execute("UPDATE users SET totp_enabled=0, totp_secret='' WHERE id=?", (uid,))
    con.commit()
    con.close()

    cdp = CDP()
    cdp.cmd("Page.navigate", {"url": BASE + "/"})
    cdp.wait("!!document.querySelector('#login-screen')")
    login(cdp, LOGIN, PASS)
    check("talaba kirdi", cdp.wait("!!App.me && App.me.user.role==='student'", 15))
    time.sleep(0.8)

    cdp.ev("App.go('profile'); true")
    check("profil ochildi", cdp.wait("!!document.querySelector('.profile-name')", 10))
    vtxt = twofa_row(cdp)
    check("2FA holati: o'chirilgan", "o'chirilgan" in vtxt and "Yoqish" in vtxt)

    # ---- Yoqish: parol + telefon modal, QR yo'q
    click_twofa_btn(cdp, "Yoqish")
    m = ev(cdp,
        "(()=>{const ov=document.querySelector('.modal-overlay'); if(!ov)return 'no-modal';"
        "const imgs=ov.querySelectorAll('img').length;"
        "const pw=!!ov.querySelector('input[type=password]');"
        "const tel=!!ov.querySelector('input[type=tel]');"
        "const inputs=ov.querySelectorAll('input').length;"
        "return JSON.stringify({imgs,pw,tel,inputs})})()")
    check("yoqish modal: parol+telefon maydonlari", m == '{"imgs":0,"pw":true,"tel":true,"inputs":2}')
    shot(cdp, SHOTS / "16_m6_2fa_enable_modal.png")

    ev(cdp,
        "(()=>{const ov=document.querySelector('.modal-overlay');"
        f"ov.querySelector('input[type=password]').value='{PASS}';"
        f"ov.querySelector('input[type=tel]').value='{PHONE}'; return true}})()")
    ev(cdp,
        "(()=>{const ov=document.querySelector('.modal-overlay');"
        "const b=[...ov.querySelectorAll('button')].find(x=>x.textContent==='Saqlash');"
        "if(!b)return false; b.click(); return true})()")

    # ---- Kod bosqichi: faqat kod maydoni, QR/secret yo'q
    ok = cdp.wait("!!document.querySelector('.modal-overlay input[inputmode=numeric]')", 10)
    check("kod bosqichi ochildi (SMS)", ok)
    m2 = ev(cdp,
        "(()=>{const ov=document.querySelector('.modal-overlay');"
        "const imgs=ov.querySelectorAll('img').length;"
        "const ro=ov.querySelectorAll('input[readonly]').length;"
        "const hint=ov.innerText.includes('SMS kod yuborildi');"
        "return JSON.stringify({imgs,readonly:ro,hint})})()")
    check("kod modalida QR va secret yo'q", m2 == '{"imgs":0,"readonly":0,"hint":true}')
    shot(cdp, SHOTS / "17_m6_2fa_code_modal.png")

    code = latest_code(uid)
    check("bildirishnomadan SMS kod o'qildi", code is not None and len(code) == 6)
    ev(cdp,
        "(()=>{document.querySelector('.modal-overlay input[inputmode=numeric]').value='"
        + (code or "000000")
        + "'; return true})()")
    ev(cdp,
        "(()=>{const ov=document.querySelector('.modal-overlay');"
        "const b=[...ov.querySelectorAll('button')].find(x=>x.textContent.includes('tasdiqlang'));"
        "if(!b)return false; b.click(); return true})()")

    ok = cdp.wait("!document.querySelector('.modal-overlay') && document.body.innerText.includes('yoqilgan')", 10)
    check("2FA yoqildi (badge)", ok)
    vtxt = twofa_row(cdp)
    check("2FA holati: yoqilgan", "yoqilgan" in vtxt)
    shot(cdp, SHOTS / "18_m6_2fa_enabled.png")

    # ---- O'chirish: parol bilan (kod so'ralmaydi)
    click_twofa_btn(cdp, "O'chirish")
    time.sleep(0.3)
    d = ev(cdp,
        "(()=>{const ov=document.querySelector('.modal-overlay'); if(!ov)return 'no-modal';"
        "const inputs=ov.querySelectorAll('input').length;"
        "const pw=!!ov.querySelector('input[type=password]');"
        "const num=!!ov.querySelector('input[inputmode=numeric]');"
        "return JSON.stringify({inputs,pw,numeric:num})})()")
    check("o'chirish modal: faqat parol (kod yo'q)", d == '{"inputs":1,"pw":true,"numeric":false}')
    ev(cdp,
        "(()=>{const ov=document.querySelector('.modal-overlay');"
        f"ov.querySelector('input[type=password]').value='{PASS}';"
        "const b=[...ov.querySelectorAll('button')].find(x=>x.classList.contains('btn-danger'));"
        "if(!b)return false; b.click(); return true})()")
    ok = cdp.wait("!document.querySelector('.modal-overlay') && document.body.innerText.includes(\"o'chirilgan\")", 10)
    check("2FA o'chirildi (badge)", ok)
    vtxt = twofa_row(cdp)
    check("2FA holati: o'chirilgan (qayta)", "o'chirilgan" in vtxt)
    shot(cdp, SHOTS / "19_m6_2fa_disabled.png")

    # ---- Tozalash
    con = sqlite3.connect(DB)
    con.execute("DELETE FROM notifications WHERE user_id=? AND type='2fa'", (uid,))
    con.execute("DELETE FROM twofa_codes WHERE user_id=?", (uid,))
    tot = con.execute("SELECT COUNT(1) FROM users WHERE id=? AND totp_enabled=1", (uid,)).fetchone()[0]
    con.commit()
    con.close()
    check("test izlari tozalandi (2FA OFF)", tot == 0)

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