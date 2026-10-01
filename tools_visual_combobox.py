# -*- coding: utf-8 -*-
"""MODUL 2 — HAQIQIY BRAUZER TEKSHIRUVI (headless Chromium).

Kalendar -> kunni bosish -> "Mashg'ulot yaratish" -> "Talaba qo'shish"
maydoni endi QIDIRILADIGAN combobox bo'lishi kerak:

  1) maydonga bosilganda BARCHA talabalar ro'yxati ko'rinadi
  2) "Jas" deb yozilganda faqat mos talabalar qoladi
  3) familiya bo'yicha ham qidiriladi
  4) hech narsa topilmasa "Hech qanday talaba topilmadi" chiqadi
  5) tanlangach maydon to'ldiriladi va ro'yxat yopiladi
  6) "Qo'shish" tugmasi tanlangan talabani ro'yxatga qo'shadi

Ishga tushirish: py tools_visual_combobox.py
"""
import json
import os
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
PY = sys.executable
HOST = "127.0.0.1"
PORT = int(os.environ.get("VIS_PORT") or 8127)
BASE = "http://%s:%d" % (HOST, PORT)
TMP = Path(os.environ.get("TEMP", ".")) / "opencode" / "combo_e2e"
TMP.mkdir(parents=True, exist_ok=True)
DB = TMP / "combo.db"

PASS, FAIL = [], []


def check(name, cond, detail=""):
    if cond:
        PASS.append(name)
        print("  [OK]   %s" % name)
    else:
        FAIL.append((name, detail))
        print("  [FAIL] %s  %s" % (name, detail))


def main():
    if DB.exists():
        DB.unlink()
    for sfx in ("-wal", "-shm"):
        p = Path(str(DB) + sfx)
        if p.exists():
            p.unlink()

    # 1) sinov bazasi + talaba/instruktor ma'lumotlari
    from app.db import init_db, next_credentials, now
    from app.auth import hash_password
    db = init_db(str(DB))

    def mk_user(first, last, role, group=""):
        import json as _j
        t = now()

        def _tx(c):
            login, password = next_credentials(c)
            cur = c.execute("""INSERT INTO users(first_name,last_name,middle_name,birth_date,gender,phone,
                       secondary_phone,login,password_hash,role,status,profile_image,
                       must_change_password,created_at,updated_at)
                     VALUES(?,?,'','','','','',?,?,?,'active','',0,?,?)""",
                            (first, last, login, hash_password(password), role, t, t))
            uid = cur.lastrowid
            if role == "student":
                c.execute("""INSERT INTO students(user_id,group_name,license_category,study_status,
                            enrolled_at,address,notes,status) VALUES(?,?,'B','active',?,'','','active')""",
                          (uid, group, t[:10]))
            else:
                c.execute("""INSERT INTO instructors(user_id,license_categories,experience_years,bio,
                            work_days,work_start,work_end,break_start,break_end,assigned_car_id,status)
                            VALUES(?,'B',1,'',?, '08:00','18:00','13:00','14:00',NULL,'active')""",
                          (uid, _j.dumps(["mon", "tue", "wed", "thu", "fri", "sat"])))
            return uid, login, password

        return db.transaction(_tx)

    admin = mk_user("Test", "Admin", "admin")
    inst = mk_user("Inst", "Karimov", "instructor")
    names = [("Jasur", "Aliyev"), ("Jasmin", "Karimova"), ("Bobur", "Rahimov"),
             ("Alisher", "Jumayev"), ("Dilnoza", "Qodirova"), ("Sardor", "Toshev")]
    for i, (f, l) in enumerate(names):
        mk_user(f, l, "student", "G-%d" % (i % 2 + 1))

    def _car_tx(c):
        ts = now()
        cur = c.execute("""INSERT INTO cars(brand,model,plate_number,year,color,practice_capacity,
                           status,created_at,updated_at)
                           VALUES('Toyota','Cora','01A123BC',2020,'white',5,'active',?,?)""", (ts, ts))
        c.execute("UPDATE instructors SET assigned_car_id=? WHERE user_id=?", (cur.lastrowid, inst[0]))

    db.transaction(_car_tx)

    print("Sinov ma'lumotlari: %d talaba, 1 instruktor, 1 avtomobil" % len(names))

    env = dict(os.environ)
    env["AVTOMAKTAB_DB"] = str(DB)
    env["AVTOMAKTAB_BACKUP_DIR"] = str(TMP / "backups")
    env["PORT"] = str(PORT)
    env["HOST"] = HOST
    env["API_RATE_MAX"] = "0"
    env["MAX_IP_TRIES"] = "0"
    env["MAX_LOGIN_TRIES"] = "50"
    proc = subprocess.Popen([PY, "server.py"], cwd=str(ROOT), env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        import urllib.request
        for _ in range(60):
            try:
                urllib.request.urlopen(BASE + "/api/health", timeout=3).read()
                break
            except Exception:
                time.sleep(0.5)
        else:
            print("SERVER FAIL")
            return

        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            b = pw.chromium.launch()
            ctx = b.new_context(viewport={"width": 1500, "height": 1000})
            pg = ctx.new_page()
            errors = []
            pg.on("pageerror", lambda e: errors.append(str(e)))
            pg.on("console", lambda m: errors.append("console:" + m.text) if m.type == "error" else None)

            pg.goto(BASE + "/", wait_until="networkidle")
            pg.fill("#login-username", admin[1])
            pg.fill("#login-password", admin[2])
            pg.click('.role-btn[data-role="admin"]')
            pg.click("#login-submit")
            pg.wait_for_selector("#app-shell:not(.hidden)", timeout=15000)
            pg.wait_for_timeout(800)

            # "Mashg'ulotlar" bo'limiga o'tamiz (mashg'ulot yaratish modali shu yerdan)
            pg.click('.nav-item[data-view="lessons"]')
            pg.wait_for_timeout(1400)
            addBtn = pg.query_selector('button.btn-primary:has-text("Yangi mashg")')
            check("'Mashg'ulot qo'shish' tugmasi topildi", addBtn is not None)
            if addBtn is None:
                b.close()
                return
            addBtn.click()
            pg.wait_for_timeout(1200)
            check("mashg'ulot modali ochildi", pg.query_selector(".modal") is not None)

            if pg.query_selector(".modal"):
                # instruktorni tanlash (avtomobil sig'imi uchun)
                pg.select_option(".modal select >> nth=0", label="Inst Karimov")
                pg.wait_for_timeout(700)

                combo = pg.query_selector(".modal .combobox")
                check("combobox mavjud", combo is not None)
                if combo is None:
                    b.close()
                    return

                inp = pg.query_selector(".modal .combobox > input")
                # 1) bosilganda BARCHA talabalar
                inp.click()
                pg.wait_for_timeout(300)
                items = pg.query_selector_all(".modal .combobox-item")
                check("bosilganda ro'yxat ochildi", len(items) > 0, "items=%d" % len(items))
                check("barcha %d talaba ko'rindi" % len(names), len(items) == len(names),
                      "items=%d" % len(items))

                # 2) ism bo'yicha qidirish "Jas"
                inp.fill("Jas")
                pg.wait_for_timeout(350)
                items = pg.query_selector_all(".modal .combobox-item")
                txts = [i.inner_text() for i in items]
                check("'Jas' -> 2 ta natija (Jasur/Jasmin)", len(items) == 2, str(txts))
                check("Jasur topildi", any("Jasur" in x for x in txts), str(txts))

                # 3) familiya bo'yicha qidirash
                inp.fill("Toshev")
                pg.wait_for_timeout(350)
                items = pg.query_selector_all(".modal .combobox-item")
                check("familiya bo'yicha qidirish", len(items) == 1 and "Sardor" in items[0].inner_text(),
                      str([i.inner_text() for i in items]))

                # 4) hech narsa topilmadi
                inp.fill("zzzzqqq")
                pg.wait_for_timeout(350)
                empty = pg.query_selector(".modal .combobox-empty")
                check("bo'sh natija matni ko'rindi", empty is not None,
                      (empty.inner_text() if empty else "yo'q"))
                check("bo'sh matn to'g'ri", empty is not None and "topilmadi" in empty.inner_text(),
                      (empty.inner_text() if empty else ""))

                # 5) tanlash
                inp.fill("Jasur")
                pg.wait_for_timeout(300)
                pg.query_selector_all(".modal .combobox-item")[0].click()
                pg.wait_for_timeout(350)
                check("tanlangach maydon to'ldirildi", "Jasur" in inp.input_value(), inp.input_value())
                closed = pg.query_selector(".modal .combobox-list.hidden") is not None
                check("tanlangach ro'yxat yopildi", closed)

                # 6) "Qo'shish" tugmasi
                addbtn = pg.query_selector('.modal button:has-text("qo\'shish"), .modal button:has-text("Qo\'shish")')
                if addbtn:
                    addbtn.click()
                    pg.wait_for_timeout(500)
                    body = pg.inner_text(".modal-body")
                    check("tanlangan talaba ro'yxatga qo'shildi", "Jasur" in body)
                else:
                    check("Qo'shish tugmasi topildi", False)

                # 7) izoh: modal ichida combobox-item qolmadi (tanlangan filtrlangan)
                remaining = pg.query_selector_all(".modal .combobox-item")
                names_left = []
                for r in remaining:
                    inp2 = pg.query_selector(".modal .combobox > input")
                    inp2.click()
                    pg.wait_for_timeout(250)
                    remaining = pg.query_selector_all(".modal .combobox-item")
                    names_left = [r.inner_text() for r in remaining]
                    break
                check("tanlangan talaba ro'yxatdan chiqdi",
                      not any("Jasur" in x for x in names_left), str(names_left))

                check("JS xatosi yo'q", not errors, str(errors[:3]))
                shots = Path(os.environ.get("TEMP", ".")) / "opencode" / "shots"
                shots.mkdir(parents=True, exist_ok=True)
                pg.screenshot(path=str(shots / "combo-01-modal.png"))
            b.close()

        print("\n=== NATIJA ===")
        print("  O'tdi: %d | Xato: %d" % (len(PASS), len(FAIL)))
        for n, d in FAIL:
            print("   FAIL: %s  %s" % (n, d))
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except Exception:
            proc.kill()


if __name__ == "__main__":
    main()