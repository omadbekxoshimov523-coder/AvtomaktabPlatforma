"""M2/M13: Bildirishnomalar sidebar bo'limi — CDP E2E tekshiruvi.
     py -X utf8 tools_verify_m2_notifs.py
- Header'da bell yo'q; sidebar'da "Bildirishnomalar" (dashboard'dan keyin)
- Badge unread soni; filtr chiplari; o'chirish; o'qilgan; tozalash
- Barcha 3 rolda nav element mavjud
Sinov davomida talabaning eski bildirishnomalari saqlanadi va oxirida
qayta tiklanadi (faqat test yozuvlari o'chiriladi).
"""
import base64
import json
import sqlite3
import time
from datetime import datetime
from pathlib import Path

from tools_e2e_m13 import CDP, BASE, check, FAILS

ROOT = Path(__file__).resolve().parent
DB = ROOT / "data" / "avtomaktab.db"
SHOTS = ROOT / "shots"


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


def ev(cdp, e):
    return cdp.ev(e)


def student_uid():
    con = sqlite3.connect(DB)
    uid = con.execute("SELECT id FROM users WHERE login='usrL_00004'").fetchone()[0]
    con.close()
    return uid


def snapshot(uid):
    con = sqlite3.connect(DB)
    rows = con.execute("SELECT id, type, title, body, data, is_read, read_at, created_at FROM notifications WHERE user_id=?", (uid,)).fetchall()
    con.close()
    return rows


def insert_test_notifs(uid):
    con = sqlite3.connect(DB)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    rows = [
        ("lesson.created", "E2E-M2 mashg'ulot yaratildi", "test"),
        ("request.new", "E2E-M2 so'rov", "test"),
        ("msg.new", "E2E-M2 xabar", "test"),
        ("security.login", "E2E-M2 xavfsizlik", "test"),
        ("reminder.before", "E2E-M2 eslatma", "test"),
    ]
    ids = []
    for t, title, body in rows:
        cur = con.execute(
            "INSERT INTO notifications(user_id, type, title, body, data, is_read, created_at) VALUES(?,?,?,?,'{}',0,?)",
            (uid, t, title, body, now))
        ids.append(cur.lastrowid)
    con.commit()
    con.close()
    return ids


def restore(rows):
    con = sqlite3.connect(DB)
    for r in rows:
        nid, ntype, title, body, data, is_read, read_at, created_at = r
        con.execute(
            "INSERT INTO notifications(user_id, type, title, body, data, is_read, read_at, created_at) VALUES(?,?,?,?,?,?,?,?)",
            (student_uid(), ntype, title, body, data or "{}", is_read, read_at or "", created_at))
    con.commit()
    con.close()


def main():
    uid = student_uid()
    saved = snapshot(uid)
    ids = insert_test_notifs(uid)
    expect_unread = sum(1 for r in saved if not r[5]) + 5

    cdp = CDP()
    cdp.cmd("Page.navigate", {"url": BASE + "/"})
    cdp.wait("!!document.querySelector('#login-screen')")
    check("header'da bell tugmasi yo'q", ev(cdp, "!document.querySelector('#bell-btn')"))

    login(cdp, "usrL_00004", "usrP_00004")
    check("talaba kirdi", cdp.wait("!!App.me && App.me.user.role==='student'", 15))
    time.sleep(1.0)

    nav = ev(cdp, "Array.from(document.querySelectorAll('#sidebar-nav .nav-item')).map(b=>b.dataset.view).join(',')")
    check("sidebar nav: dashboard, notifications, ...", nav.startswith("dashboard,notifications"))
    badge = ev(cdp, "(()=>{const b=document.querySelector('#sidebar-nav .nav-item[data-view=notifications] .nav-badge');return b?b.textContent:''})()")
    check(f"badge {expect_unread} ta o'qilmagan", badge == str(expect_unread))

    cdp.ev("App.go('notifications'); true")
    ok = cdp.wait("document.querySelectorAll('.notif-page-item').length>=5", 10)
    check("sahifada >=5 ta bildirishnoma", ok)
    unread = ev(cdp, "document.querySelectorAll('.notif-page-item.unread').length")
    check(f"{expect_unread} ta o'qilmagan uslubda", unread == expect_unread)
    dot = ev(cdp, "!!document.querySelector('.notif-page-item.unread .notif-unread-dot')")
    check("o'qilmagan nuqtasi bor", dot)
    chips_on = ev(cdp, "document.querySelectorAll('.notif-filters .chip.on').length")
    chips_total = ev(cdp, "document.querySelectorAll('.notif-filters .chip').length")
    check(f"chiplar: 'Barchasi' active, {chips_total} ta", chips_on == 1 and chips_total == 6)
    shot(cdp, SHOTS / "13_m2_notifications_student.png")

    # Filtr: Mashg'ulotlar — hamma ko'rsatilganlari kamayishi va faqat lesson bo'lishi
    total_all = ev(cdp, "document.querySelectorAll('.notif-page-item').length")
    cdp.ev("Array.from(document.querySelectorAll('.notif-filters .chip')).find(c=>c.textContent===\"Mashg'ulotlar\").click(); true")
    time.sleep(0.5)
    total_lesson = ev(cdp, "document.querySelectorAll('.notif-page-item').length")
    first_lesson = ev(cdp, "document.querySelector('.notif-page-item .notif-title').textContent")
    check("filtr 'Mashg'ulotlar' ishlaydi", 0 < total_lesson < total_all)
    check("filtr — mavjud mashg'ulot yozuvi", "E2E-M2 mashg'ulot" in first_lesson or "mashg'ulot" in first_lesson.lower())
    shot(cdp, SHOTS / "14_m2_filter_lesson.png")
    cdp.ev("Array.from(document.querySelectorAll('.notif-filters .chip')).find(c=>c.textContent.includes(\"Barchasi\")).click(); true")
    time.sleep(0.5)

    # Bitta test yozuvini o'chirish
    ok = cdp.ev("(()=>{const it=[...document.querySelectorAll('.notif-page-item')].find(i=>i.querySelector('.notif-title').textContent.includes('E2E-M2 mashg\\'ulot')); if(!it)return false; it.querySelector('.notif-del').click(); return true})()")
    check("o'chirish tugmasi topildi", ok)
    ok = cdp.wait("document.querySelectorAll('.notif-page-item .notif-title').length ? Array.from(document.querySelectorAll('.notif-page-item')).filter(i=>i.querySelector('.notif-title').textContent.includes('E2E-M2')).length === 4 : false", 10)
    check("o'chirish → E2E-M2 4 ta qoldi", ok)
    badge = ev(cdp, "(()=>{const b=document.querySelector('#sidebar-nav .nav-item[data-view=notifications] .nav-badge');return b?b.textContent:''})()")
    check("badge yangilandi (-1)", badge == str(expect_unread - 1))

    # Barchasini o'qilgan deb belgilash
    cdp.ev("Array.from(document.querySelectorAll('#view button')).find(b=>b.textContent.includes(\"o'qilgan\")).click(); true")
    ok = cdp.wait("document.querySelectorAll('.notif-page-item.unread').length===0", 10)
    check("barchasi o'qilgan", ok)
    badge = ev(cdp, "(()=>{const b=document.querySelector('#sidebar-nav .nav-item[data-view=notifications] .nav-badge');return b?'X':'OK'})()")
    check("badge yashirildi", badge == "OK")

    # Barchasini tozalash — tasdiqlash oynasi
    cdp.ev("Array.from(document.querySelectorAll('#view button')).find(b=>b.textContent.includes('tozalash')).click(); true")
    ok = cdp.wait("!!document.querySelector('.modal-overlay')", 6)
    check("tasdiqlash oynasi", ok)
    shot(cdp, SHOTS / "15_m2_confirm_clear.png")
    cdp.ev("Array.from(document.querySelectorAll('.modal-overlay button')).pop().click(); true")
    ok = cdp.wait("document.querySelectorAll('.notif-page-item').length===0 && !!document.querySelector('.notif-page .empty-state, .empty-state')", 10)
    check("barchasi tozalandi (bo'sh holat)", ok)

    # Test yozuvlari o'chirilgan, eski bildirishnomalarni qayta tiklash
    con = sqlite3.connect(DB)
    con.execute("DELETE FROM notifications WHERE id IN (%s)" % ",".join("?" * len(ids)), ids)
    con.commit()
    con.close()
    restore(saved)

    # Instruktor nav tekshiruvi
    cdp2 = CDP()
    cdp2.cmd("Page.navigate", {"url": BASE + "/"})
    cdp2.wait("!!document.querySelector('#login-screen')")
    login(cdp2, "usrL_00001", "usrP_00001")
    check("instruktor kirdi", cdp2.wait("!!App.me && App.me.user.role==='instructor'", 15))
    nav2 = ev(cdp2, "Array.from(document.querySelectorAll('#sidebar-nav .nav-item')).map(b=>b.dataset.view).join(',')")
    check("instruktor nav'ida notifications bor", "dashboard,notifications" in nav2)

    # Admin nav tekshiruvi
    cdp3 = CDP()
    cdp3.cmd("Page.navigate", {"url": BASE + "/"})
    cdp3.wait("!!document.querySelector('#login-screen')")
    login(cdp3, "admin", "admin123", "admin")
    check("admin kirdi", cdp3.wait("!!App.me && App.me.user.role==='admin'", 15))
    nav3 = ev(cdp3, "Array.from(document.querySelectorAll('#sidebar-nav .nav-item')).map(b=>b.dataset.view).join(',')")
    check("admin nav'ida notifications bor", "dashboard,notifications" in nav3)

    print("\n=== NATIJA ===")
    bad = 0
    for name in FAILS:
        print("  FAIL | " + name)
        bad += 1
    if bad == 0:
        print("  Hammasi OK")
    print(f"Jami xatolar: {bad}")
    return bad


if __name__ == "__main__":
    import sys
    sys.exit(main())