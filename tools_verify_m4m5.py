"""M4/M5: Tarix va so'rovlarni o'chirish / tozalash (soft-delete) — CDP E2E.
     py -X utf8 tools_verify_m4m5.py
- Tarix: har bir qatorda ✕; "Barchasini tozalash" -> tasdiqlash oynasi
  ("Rostdan ham barcha tarixni o'chirmoqchimisiz? Bu amalni qaytarib bo'lmaydi")
- So'rovlar: xuddi shu, o'z matni bilan
- Soft-delete: asl jadval qatorlari saqlanadi (audit), faqat hidden_* jadvallar o'sadi
Test so'ngida barcha test'dagi hidden qatorlari o'chiriladi — talaba tarixi tiklanadi.
"""
import base64
import sqlite3
import time
from pathlib import Path

from tools_e2e_m13 import CDP, BASE, check, FAILS

ROOT = Path(__file__).resolve().parent
DB = ROOT / "data" / "avtomaktab.db"
SHOTS = ROOT / "shots"
LOGIN = "usrL_00004"
PASS = "usrP_00004"
CONFIRM_HISTORY = "Rostdan ham barcha tarixni o'chirmoqchimisiz? Bu amalni qaytarib bo'lmaydi"
CONFIRM_REQUESTS = "Rostdan ham barcha so'rovlarni o'chirmoqchimisiz? Bu amalni qaytarib bo'lmaydi"


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


def q(sql, args=()):
    con = sqlite3.connect(DB)
    try:
        return con.execute(sql, args).fetchall()
    finally:
        con.close()


def main():
    # Asosiy holat: hidden jadvallar bo'sh deb kutamiz (bu test ularni to'ldiradi)
    before_h = q("SELECT COUNT(*) FROM hidden_history")[0][0]
    before_r = q("SELECT COUNT(*) FROM hidden_requests")[0][0]
    check("boshlang'ich hidden_history bo'sh", before_h == 0)
    check("boshlang'ich hidden_requests bo'sh", before_r == 0)

    hist_total = q(
        "SELECT COUNT(*) FROM session_students ss JOIN lesson_sessions ls ON ls.id=ss.session_id "
        "WHERE ss.student_id=1 AND ss.student_status='active' AND ls.status IN ('completed','cancelled')")[0][0]
    req_total = q("SELECT COUNT(*) FROM practice_requests WHERE student_id=1")[0][0]
    print(f"  talaba tarixi: {hist_total}, so'rovlari: {req_total}")

    cdp = CDP()
    cdp.cmd("Page.navigate", {"url": BASE + "/"})
    cdp.wait("!!document.querySelector('#login-screen')")
    login(cdp, LOGIN, PASS)
    check("talaba kirdi", cdp.wait("!!App.me", 15))
    time.sleep(0.8)

    # ---------- TARIX ----------
    cdp.ev("App.go('history'); true")
    cdp.wait("!!document.querySelector('.tbl') || !!document.querySelector('.empty-state')", 10)
    time.sleep(1.2)
    rows = ev(cdp, "document.querySelectorAll('.tbl tbody tr').length")
    check(f"tarix jadvalida {hist_total} qator", rows == hist_total)
    shot(cdp, SHOTS / "23_m4_history_list.png")

    # Per-item ✕ o'chirish
    clicked = ev(cdp,
        "(()=>{const tr=document.querySelector('.tbl tbody tr'); if(!tr)return false;"
        "const b=tr.querySelector('.btn-ghost'); if(!b)return false; b.click(); return true})()")
    check("tarixda ✕ tugmasi mavjud va bosildi", bool(clicked))
    ok = cdp.wait(
        "document.querySelectorAll('.tbl tbody tr').length === " + str(hist_total - 1) +
        " || !!document.querySelector('.empty-state')", 10)
    check("✕ bosilgach bitta qator yo'qoldi", ok)

    # Clear-all + tasdiqlash matni
    ev(cdp,
        "(()=>{const b=[...document.querySelectorAll('#view button')]"
        ".find(x=>x.textContent.includes('Barchasini tozalash')); if(!b)return false; b.click(); return true})()")
    time.sleep(0.4)
    has_modal = ev(cdp, "!!document.querySelector('.modal-overlay')")
    check("clear-all -> tasdiqlash oynasi", bool(has_modal))
    txt = ev(cdp, "(()=>{const o=document.querySelector('.modal-overlay');return o?o.innerText:''})()")
    check("history tasdiqlash matni to'g'ri", CONFIRM_HISTORY in txt)
    shot(cdp, SHOTS / "24_m4_confirm_clear.png")
    ev(cdp,
        "(()=>{const o=document.querySelector('.modal-overlay');"
        "const b=[...o.querySelectorAll('button')].find(x=>x.classList.contains('btn-primary'));"
        "if(!b)return false; b.click(); return true})()")
    ok = cdp.wait("!!document.querySelector('.empty-state')", 10)
    check("barcha tarix tozalandi (empty-state)", ok)
    shot(cdp, SHOTS / "25_m4_history_cleared.png")

    # Soft-delete: asl qatorlar saqlanib qoldi, faqat hidden_history o'sdi
    hid = q("SELECT COUNT(*) FROM hidden_history")[0][0]
    alive = q(
        "SELECT COUNT(*) FROM session_students ss JOIN lesson_sessions ls ON ls.id=ss.session_id "
        "WHERE ss.student_id=1 AND ss.student_status='active' AND ls.status IN ('completed','cancelled')")[0][0]
    check("tarixdagi asl qatorlar saqlanib qoldi (soft-delete)", alive == hist_total and hid > 0)

    # ---------- SO'ROVLAR ----------
    cdp.ev("App.go('requests'); true")
    cdp.wait("!!document.querySelector('#view .grid-2') || !!document.querySelector('.empty-state')", 10)
    time.sleep(1.2)
    cards = ev(cdp, "document.querySelectorAll('#view .grid-2 .card').length")
    check(f"so'rovlar ro'yxatida {req_total} ta karta", cards == req_total)
    shot(cdp, SHOTS / "26_m5_requests_list.png")

    # Per-item ✕ o'chirish
    c2 = ev(cdp,
        "(()=>{const c=document.querySelector('#view .grid-2 .card'); if(!c)return false;"
        "const b=c.querySelector('.btn-ghost'); if(!b)return false; b.click(); return true})()")
    check("so'rovda ✕ tugmasi mavjud va bosildi", bool(c2))
    ok = cdp.wait(
        "document.querySelectorAll('#view .grid-2 .card').length === " + str(req_total - 1) +
        " || !!document.querySelector('.empty-state')", 10)
    check("✕ bosilgach bitta so'rov yo'qoldi", ok)

    # Clear-all
    ev(cdp,
        "(()=>{const b=[...document.querySelectorAll('#view button')]"
        ".find(x=>x.textContent.includes('Barchasini tozalash')); if(!b)return false; b.click(); return true})()")
    time.sleep(0.4)
    txt = ev(cdp, "(()=>{const o=document.querySelector('.modal-overlay');return o?o.innerText:''})()")
    check("requests tasdiqlash matni to'g'ri", CONFIRM_REQUESTS in txt)
    shot(cdp, SHOTS / "27_m5_confirm_clear.png")
    ev(cdp,
        "(()=>{const o=document.querySelector('.modal-overlay');"
        "const b=[...o.querySelectorAll('button')].find(x=>x.classList.contains('btn-primary'));"
        "if(!b)return false; b.click(); return true})()")
    ok = cdp.wait("!!document.querySelector('.empty-state')", 10)
    check("barcha so'rovlar tozalandi (empty-state)", ok)
    shot(cdp, SHOTS / "28_m5_requests_cleared.png")

    ali = q("SELECT COUNT(*) FROM practice_requests WHERE student_id=1")[0][0]
    hidr = q("SELECT COUNT(*) FROM hidden_requests")[0][0]
    check("so'rovlarning asl qatorlari saqlanib qoldi (soft-delete)", ali == req_total and hidr > 0)

    # ---------- Tiklash (faqat test davomida yashiringan qatorlarni olib tashlash) ----------
    stu_id = q("SELECT id FROM students WHERE user_id=5")[0][0]
    con = sqlite3.connect(DB)
    con.execute("DELETE FROM hidden_history WHERE user_id=?", (stu_id,))
    con.execute("DELETE FROM hidden_requests WHERE user_id=?", (stu_id,))
    con.commit()
    con.close()
    back_h = q("SELECT COUNT(*) FROM hidden_history")[0][0]
    back_r = q("SELECT COUNT(*) FROM hidden_requests")[0][0]
    hist_now = q(
        "SELECT COUNT(*) FROM session_students ss JOIN lesson_sessions ls ON ls.id=ss.session_id "
        "WHERE ss.student_id=1 AND ss.student_status='active' AND ls.status IN ('completed','cancelled')")[0][0]
    req_now = q("SELECT COUNT(*) FROM practice_requests WHERE student_id=1")[0][0]
    check("tarix qayta ko'rinyapti (tiklandi)", hist_now == hist_total and back_h == 0)
    check("so'rovlar qayta ko'rinyapti (tiklandi)", req_now == req_total and back_r == 0)

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