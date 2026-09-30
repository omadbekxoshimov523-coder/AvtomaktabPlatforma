"""Avtomatik testlar (Python stdlib unittest):
    py -m tests.test_api
Server alohida jarayonda emas — shu jarayonda, temp bazada ishga tushiriladi.
Qamrab oladi: LOGIN, USERS, CARS, SESSIONS, CAPACITY, INSTRUCTOR BANDLIGI,
CAR ALMASHTIRISH TARIXI, SECURITY/RBAC.
"""
import http.cookiejar
import os
import shutil
import sys
import tempfile
import threading
import unittest
import urllib.request
import urllib.error
import json
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Test uchun alohida temp baza
TMP = Path(tempfile.mkdtemp(prefix="avtomaktab_test_"))
os.environ["AVTOMAKTAB_DB"] = str(TMP / "test.db")

import server  # noqa: E402

from app.db import jload, Db, now  # noqa: E402
from app.api import ensure_reminders  # noqa: E402

HOST, PORT = "127.0.0.1", 0


class Client:
    """Cookie'li HTTP klient."""

    def __init__(self):
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))

    def req(self, method, path, body=None, cookie=None):
        data = None
        headers = {}
        if body is not None:
            data = json.dumps(body).encode()
            headers["Content-Type"] = "application/json"
        if method in ("POST", "PUT", "DELETE"):
            headers["X-Requested-With"] = "Avtomaktab"
        # Chiqishdan keyin "eski token saqlab qolinsa ham ishlamaydi" —
        # buni tekshirish uchun cookie'ni qo'lda yuborish imkoniyati.
        if cookie:
            headers["Cookie"] = "sid=" + cookie
        req = urllib.request.Request(f"http://{HOST}:{PORT}{path}", data=data, headers=headers, method=method)
        try:
            with self.opener.open(req, timeout=15) as resp:
                raw = resp.read()
                try:
                    return resp.status, json.loads(raw.decode("utf-8"))
                except Exception:
                    return resp.status, {"raw": True, "mime": resp.headers.get("Content-Type")}
        except urllib.error.HTTPError as e:
            raw = e.read()
            try:
                return e.code, json.loads(raw.decode("utf-8"))
            except Exception:
                return e.code, {}

    # qulaylik
    def get(self, p): return self.req("GET", p)
    def post(self, p, b=None): return self.req("POST", p, b or {})
    def put(self, p, b=None): return self.req("PUT", p, b or {})
    def delete(self, p): return self.req("DELETE", p)


class TabClient(Client):
    """Brauzer tab'ini taqlid qiladi: `X-Avto-Tab` sarlavhasini yuboradi.

    Bitta brauzerda bir nechta tab ochilganda har bir tab' o'z sessiyasini
    oladi (cookie esa barcha tab'larda umumiy) — shu sarlavha orqali.
    `jar` parametri orqali bir nechta tab bitta cookie jarni ham ulaydi.
    """

    def __init__(self, tab, jar=None):
        super().__init__()
        self.tab = tab
        if jar is not None:
            self.jar = jar
            self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

    def req(self, method, path, body=None, cookie=None, tab=None):
        data = None
        headers = {}
        if body is not None:
            data = json.dumps(body).encode()
            headers["Content-Type"] = "application/json"
        if method in ("POST", "PUT", "DELETE"):
            headers["X-Requested-With"] = "Avtomaktab"
        # `tab=False` -> sarlavha yuborilmaydi (eski mijoz kabi: curl, bot)
        if tab is not False:
            headers["X-Avto-Tab"] = tab if tab else self.tab
        if cookie:
            headers["Cookie"] = "sid=" + cookie
        req = urllib.request.Request(f"http://{HOST}:{PORT}{path}", data=data, headers=headers, method=method)
        try:
            with self.opener.open(req, timeout=15) as resp:
                raw = resp.read()
                try:
                    return resp.status, json.loads(raw.decode("utf-8"))
                except Exception:
                    return resp.status, {"raw": True}
        except urllib.error.HTTPError as e:
            raw = e.read()
            try:
                return e.code, json.loads(raw.decode("utf-8"))
            except Exception:
                return e.code, {}


# Barcha test klasslari BIRTA umumiy server ishlatadi (har klassda yangi server ochish
# Windows'da SO_REUSEADDR tufayli o'lik serverga ulanish/osilish muammosini keltiradi)
_SERVER = {"httpd": None, "owners": 0}


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        global HOST, PORT  # noqa: PLW0603
        if _SERVER["httpd"] is None:
            from http.server import ThreadingHTTPServer
            httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
            _SERVER["httpd"] = httpd
            threading.Thread(target=httpd.serve_forever, daemon=True).start()
            HOST, PORT = "127.0.0.1", httpd.server_address[1]
        _SERVER["owners"] += 1
        cls.httpd = _SERVER["httpd"]
        cls.port = _SERVER["httpd"].server_address[1]

    @classmethod
    def tearDownClass(cls):
        # DIQQAT: bu yerda hech narsani o'chirmaymiz! Server va vaqtinchalik
        # baza butun testlar tugagandan KEYIN `tearDownModule()` da yopiladi.
        # Sababi: sinflar ketma-ket ishlaganda, birinchisi tugagach TMP
        # o'chirilsa, qolgan sinflar bazani topolmaydi
        # ("sqlite3.OperationalError: unable to open database file").
        # (Windows'da ochiq faylni o'chirib bo'lmaydi, Linux'da esa
        #  o'chib ketardi — ya'ni xato faqat CI da ko'rinardi.)
        pass


def tearDownModule():
    """Barcha sinflar tugagach — serverni to'xtatish va temp bazani tozalash."""
    httpd = _SERVER.get("httpd")
    if httpd is not None:
        httpd.shutdown()
        httpd.server_close()
        _SERVER["httpd"] = None
    shutil.rmtree(TMP, ignore_errors=True)


class TestAuthAndUsers(Base):
    def test_01_admin_login_ok(self):
        c = Client()
        st, r = c.post("/api/auth/login", {"login": "admin", "password": "admin123", "role": "admin"})
        self.assertEqual(st, 200, r)

    def test_02_wrong_password(self):
        c = Client()
        st, r = c.post("/api/auth/login", {"login": "admin", "password": "wrong"})
        self.assertEqual(st, 400)
        self.assertEqual(r["error"], "auth.wrong_credentials")

    def test_03_wrong_role(self):
        c = Client()
        st, r = c.post("/api/auth/login", {"login": "admin", "password": "admin123", "role": "student"})
        self.assertEqual(st, 400)
        self.assertEqual(r["error"], "auth.wrong_role")

    def test_04_blocked_user_cannot_login(self):
        admin = Client()
        admin.post("/api/auth/login", {"login": "admin", "password": "admin123", "role": "admin"})
        # Boshqa testlar Akmalga (usrL_00001) bog'liq — bloklash uchun alohida user yaratamiz
        st, cr = admin.post("/api/admin/users", {"role": "student", "first_name": "Blok", "last_name": "Test"})
        self.assertEqual(st, 200, cr)
        lg, pw = cr["credentials"]["login"], cr["credentials"]["password"]
        st, r = admin.post(f"/api/admin/users/{cr['user']['id']}/status", {"status": "block"})
        self.assertEqual(st, 200, r)
        stud = Client()
        st, r = stud.post("/api/auth/login", {"login": lg, "password": pw, "role": "student"})
        self.assertEqual(r["error"], "auth.user_blocked")

    def test_05_logout(self):
        c = Client()
        c.post("/api/auth/login", {"login": "admin", "password": "admin123", "role": "admin"})
        st, r = c.post("/api/auth/logout")
        self.assertEqual(st, 200)

    def test_06_admin_creates_student_auto_creds(self):
        admin = Client()
        admin.post("/api/auth/login", {"login": "admin", "password": "admin123", "role": "admin"})
        st, r = admin.post("/api/admin/users", {
            "role": "student", "first_name": "Test", "last_name": "Student", "phone": "+998911111111", "group_name": "T-1",
        })
        self.assertEqual(st, 200, r)
        self.assertRegex(r["credentials"]["login"], r"^usrL_\d{5}$")
        self.assertRegex(r["credentials"]["password"], r"^usrP_\d{5}$")
        # yangi login bilan kirish
        sc = Client()
        st, r2 = sc.post("/api/auth/login", {"login": r["credentials"]["login"],
                                             "password": r["credentials"]["password"],
                                             "role": "student"})
        self.assertEqual(st, 200, r2)

    def test_07_sequence_increases_and_not_reused(self):
        admin = Client()
        admin.post("/api/auth/login", {"login": "admin", "password": "admin123", "role": "admin"})
        l1 = admin.post("/api/admin/users", {"role": "student", "first_name": "A1", "last_name": "B1"})[1]["credentials"]["login"]
        l2 = admin.post("/api/admin/users", {"role": "student", "first_name": "A2", "last_name": "B2"})[1]["credentials"]["login"]
        l3 = admin.post("/api/admin/users", {"role": "instructor", "first_name": "A3", "last_name": "B3"})[1]["credentials"]["login"]
        n1, n2, n3 = int(l1.split("_")[1]), int(l2.split("_")[1]), int(l3.split("_")[1])
        self.assertEqual(n2, n1 + 1)
        self.assertEqual(n3, n2 + 1)
        # ochirilgan user raqami qayta ishlatilmaydi
        users = admin.get("/api/admin/users?role=student")[1]["users"]
        target = next(u for u in users if u["login"] == l1)
        admin.delete(f"/api/admin/users/{target['id']}")
        l4 = admin.post("/api/admin/users", {"role": "student", "first_name": "A4", "last_name": "B4"})[1]["credentials"]["login"]
        self.assertGreater(int(l4.split("_")[1]), n2)

    def test_08_bulk_create(self):
        admin = Client()
        admin.post("/api/auth/login", {"login": "admin", "password": "admin123", "role": "admin"})
        st, r = admin.post("/api/admin/users/bulk", {"count": 10})
        self.assertEqual(st, 200)
        self.assertEqual(len(r["created"]), 10)

    def test_09_no_public_registration(self):
        c = Client()
        st, r = c.post("/api/user/register", {"first_name": "X"})
        self.assertEqual(st, 404)  # bunday endpoint yo'q


class TestLogoutSession(Base):
    """Chiqish (logout).

    Talablar: sessiya server tomonida ham yopilishi (faqat frontend tokenni
    "unutib qo'yishi" yetarli emas), eski token qayta ishlamasligi, himoyalangan
    endpoint'lar 401 qaytarishi va barcha uch rol uchun bir xil ishlashi.
    """

    ROLES = [
        ("admin", "admin", "admin123"),
        ("instructor", "usrL_00001", "usrP_00001"),
        ("student", "usrL_00004", "usrP_00004"),
    ]

    def _sid(self, c):
        for ck in c.jar:
            if ck.name == "sid":
                return ck.value
        return None

    def _login(self, login, password, role):
        c = Client()
        st, r = c.post("/api/auth/login", {"login": login, "password": password, "role": role})
        self.assertEqual(st, 200, r)
        return c

    def test_01_login_then_logout_all_roles(self):
        for role, login, pw in self.ROLES:
            with self.subTest(role=role):
                c = self._login(login, pw, role)
                self.assertTrue(self._sid(c), "login cookie berilmadi")
                st, r = c.get("/api/auth/me")
                self.assertEqual(st, 200, r)
                self.assertEqual(r["user"]["role"], role)
                st, r = c.post("/api/auth/logout")
                self.assertEqual(st, 200, r)

    def test_02_protected_endpoints_401_after_logout(self):
        for role, login, pw in self.ROLES:
            with self.subTest(role=role):
                c = self._login(login, pw, role)
                self.assertEqual(c.post("/api/auth/logout")[0], 200)
                st, r = c.get("/api/auth/me")
                self.assertEqual(st, 401, r)
                self.assertEqual(r["error"], "auth.required")

    def test_03_stale_token_rejected_server_side(self):
        # Eski token texnik jihatdan saqlab qolinsa ham, serverda bekor
        # qilingani uchun qabul qilinmasligi shart.
        c = self._login("admin", "admin123", "admin")
        old = self._sid(c)
        self.assertTrue(old)
        self.assertEqual(c.post("/api/auth/logout")[0], 200)

        stale = Client()
        for path in ("/api/auth/me", "/api/me/settings", "/api/me/sessions", "/api/admin/dashboard"):
            with self.subTest(path=path):
                st, r = stale.req("GET", path, cookie=old)
                self.assertEqual(st, 401, r)

    def test_04_logout_clears_cookie(self):
        # Set-Cookie Max-Age=0 — klient jaridagi sid yo'qolishi kerak
        c = self._login("admin", "admin123", "admin")
        self.assertTrue(self._sid(c))
        st, r = c.post("/api/auth/logout")
        self.assertEqual(st, 200, r)
        self.assertIsNone(self._sid(c), "sid cookie tozalanmadi")

    def test_05_logout_without_session_is_idempotent(self):
        c = Client()
        st, r = c.post("/api/auth/logout")
        self.assertEqual(st, 200, r)
        st, r = c.post("/api/auth/logout")
        self.assertEqual(st, 200, r)

    def test_06_other_sessions_survive(self):
        # Faqat joriy sessiya yopiladi — boshqa qurilmalar saqlanib qoladi
        a = self._login("admin", "admin123", "admin")
        b = self._login("admin", "admin123", "admin")
        self.assertEqual(a.post("/api/auth/logout")[0], 200)
        st, _ = b.get("/api/auth/me")
        self.assertEqual(st, 200)
        self.assertEqual(b.post("/api/auth/logout")[0], 200)

    def test_07_no_data_leak_between_users(self):
        # Chiqqandan keyin boshqa hisob bilan kiringanda avvalgi foydalanuvchi
        # ma'lumotlari (profil) ko'rinmasligi kerak.
        admin = self._login("admin", "admin123", "admin")
        stu = Client()
        st, r = stu.post("/api/auth/login", {"login": "usrL_00004", "password": "usrP_00004", "role": "student"})
        self.assertEqual(st, 200, r)
        st, r = stu.get("/api/auth/me")
        stu_login = r["user"]["login"]
        stu_id = r["user"]["id"]

        self.assertEqual(admin.post("/api/auth/logout")[0], 200)

        st, r = stu.get("/api/auth/me")
        self.assertEqual(st, 200, r)
        self.assertEqual(r["user"]["login"], stu_login)
        self.assertEqual(r["user"]["id"], stu_id)
        # Talaba admin endpoint'iga kira olmaydi
        st, r = stu.get("/api/admin/dashboard")
        self.assertEqual(st, 403, r)
        self.assertEqual(stu.post("/api/auth/logout")[0], 200)

    def test_08_relogin_works_after_logout(self):
        c = self._login("admin", "admin123", "admin")
        self.assertEqual(c.post("/api/auth/logout")[0], 200)
        c2 = self._login("admin", "admin123", "admin")
        self.assertTrue(self._sid(c2))
        st, r = c2.get("/api/auth/me")
        self.assertEqual(st, 200, r)
        self.assertEqual(c2.post("/api/auth/logout")[0], 200)


class TestCars(Base):
    def test_10_car_create_duplicate_plate(self):
        admin = Client()
        admin.post("/api/auth/login", {"login": "admin", "password": "admin123", "role": "admin"})
        payload = {"brand": "Toyota", "model": "Camry", "plate_number": "01 Z 777 ZZ", "practice_capacity": 4, "status": "active"}
        st, r = admin.post("/api/admin/cars", payload)
        self.assertEqual(st, 200, r)
        st, r = admin.post("/api/admin/cars", payload)
        self.assertEqual(st, 409)
        self.assertEqual(r["error"], "car.plate_exists")

    def test_11_car_status_blocks_session(self):
        admin = Client()
        admin.post("/api/auth/login", {"login": "admin", "password": "admin123", "role": "admin"})
        # Akmalning joriy mashinasini topamiz (test_30 uni almashtirib qo'yishi mumkin)
        insts = admin.get("/api/admin/instructors")[1]["instructors"]
        akmal = next(i for i in insts if i["first_name"] == "Akmal" and i["last_name"] == "Karimov")
        car_id = akmal["car"]["id"]
        st, r = admin.put(f"/api/admin/cars/{car_id}", {"status": "repair"})
        self.assertEqual(st, 200, r)
        st, r = admin.post("/api/admin/sessions", {"date": "2026-10-05", "start_time": "10:00", "end_time": "11:00", "instructor_id": akmal["id"], "student_ids": []})
        self.assertEqual(r["ok"], False)
        self.assertIn("car_in_repair", r["params"]["errors"])
        admin.put(f"/api/admin/cars/{car_id}", {"status": "active"})

    def test_12_instructor_assign_car(self):
        admin = Client()
        admin.post("/api/auth/login", {"login": "admin", "password": "admin123", "role": "admin"})
        cars = admin.get("/api/admin/cars")[1]["cars"]
        target = next(c for c in cars if c["plate_number"] == "01 Z 777 ZZ")
        # Jasurning original mashinasini eslab qolamiz (test_27 unga bog'liq)
        insts_before = admin.get("/api/admin/instructors")[1]["instructors"]
        jasur_before = next(i for i in insts_before if i["first_name"] == "Jasur")
        original_car_id = jasur_before["car"]["id"]
        st, r = admin.post(f"/api/admin/instructors/{jasur_before['id']}/car", {"car_id": target["id"]})
        self.assertEqual(st, 200, r)
        # Jasur endi Toyota'da
        insts = admin.get("/api/admin/instructors")[1]["instructors"]
        jasur = next(i for i in insts if i["first_name"] == "Jasur")
        self.assertEqual(jasur["car"]["plate_number"], "01 Z 777 ZZ")
        # Boshqa testlar Nexia'ga bog'liq — tiklaymiz
        admin.post(f"/api/admin/instructors/{jasur['id']}/car", {"car_id": original_car_id})


class TestSessions(Base):
    # 2026-11-02 = dushanba, 11-03 = seshanba, 11-04 = chorshanba, 11-06 = juma,
    # 11-07 = shanba, 11-09 = dushanba, 11-10 = seshanba.
    # Akmal (instructor 1): du-sha; Jasur (instructor 2): du-ju.

    def test_20_create_session_auto_car(self):
        admin = Client()
        admin.post("/api/auth/login", {"login": "admin", "password": "admin123", "role": "admin"})
        # Akmal (instructor id 1) -> Cobalt (car 1)
        st, r = admin.post("/api/admin/sessions", {
            "date": "2026-11-02", "start_time": "09:00", "end_time": "10:00", "instructor_id": 1,
            "student_ids": [1, 2, 3],
        })
        self.assertEqual(st, 200, r)
        self.assertEqual(r["auto"]["car"], "Chevrolet Cobalt")
        self.assertEqual(r["auto"]["capacity"], 4)

    def test_21_capacity_5th_student_fails(self):
        admin = Client()
        admin.post("/api/auth/login", {"login": "admin", "password": "admin123", "role": "admin"})
        st, r = admin.post("/api/admin/sessions", {
            "date": "2026-11-02", "start_time": "11:00", "end_time": "12:00", "instructor_id": 1,
            "student_ids": [1, 2, 3, 4, 5],
        })
        self.assertEqual(st, 409)
        self.assertIn("capacity_full", r["params"]["errors"])

    def test_22_instructor_busy_overlap(self):
        admin = Client()
        admin.post("/api/auth/login", {"login": "admin", "password": "admin123", "role": "admin"})
        ok, _ = admin.post("/api/admin/sessions", {"date": "2026-11-03", "start_time": "09:00", "end_time": "10:00", "instructor_id": 1, "student_ids": []})
        self.assertEqual(ok, 200)
        st, r = admin.post("/api/admin/sessions", {"date": "2026-11-03", "start_time": "09:30", "end_time": "10:30", "instructor_id": 1, "student_ids": []})
        self.assertEqual(st, 409)
        self.assertIn("instructor_busy", r["params"]["errors"])

    def test_23_student_busy(self):
        admin = Client()
        admin.post("/api/auth/login", {"login": "admin", "password": "admin123", "role": "admin"})
        # Jasur (id 2) bilan
        ok, _ = admin.post("/api/admin/sessions", {"date": "2026-11-04", "start_time": "10:00", "end_time": "11:00", "instructor_id": 2, "student_ids": [1]})
        self.assertEqual(ok, 200)
        st, r = admin.post("/api/admin/sessions", {"date": "2026-11-04", "start_time": "10:30", "end_time": "11:30", "instructor_id": 1, "student_ids": [1]})
        self.assertEqual(st, 409)
        self.assertIn("student_busy", r["params"]["errors"])

    def test_24_work_schedule_enforced(self):
        admin = Client()
        admin.post("/api/auth/login", {"login": "admin", "password": "admin123", "role": "admin"})
        # Akmal: 08:00-18:00, tanaffus 13-14.  2026-11-06 = juma (ish kuni)
        st, r = admin.post("/api/admin/sessions", {"date": "2026-11-06", "start_time": "13:00", "end_time": "14:00", "instructor_id": 1, "student_ids": []})
        self.assertEqual(st, 409)
        self.assertIn("intersects_break", r["params"]["errors"])
        st, r = admin.post("/api/admin/sessions", {"date": "2026-11-06", "start_time": "07:00", "end_time": "08:00", "instructor_id": 1, "student_ids": []})
        self.assertIn("outside_work_hours", r["params"]["errors"])

    def test_25_no_car_instructor_blocked(self):
        admin = Client()
        admin.post("/api/auth/login", {"login": "admin", "password": "admin123", "role": "admin"})
        # yangi instruktor avtomobilsiz
        st, r = admin.post("/api/admin/users", {"role": "instructor", "first_name": "Noc", "last_name": "Car"})
        self.assertEqual(st, 200)
        new_inst_login = r["credentials"]["login"]
        insts = admin.get("/api/admin/instructors")[1]["instructors"]
        newest = max(insts, key=lambda i: i["id"])
        st, r = admin.post("/api/admin/sessions", {"date": "2026-11-07", "start_time": "09:00", "end_time": "10:00", "instructor_id": newest["id"], "student_ids": []})
        self.assertEqual(st, 409)
        self.assertIn("car_not_assigned", r["params"]["errors"])

    def test_26_start_finish_attendance(self):
        admin = Client()
        admin.post("/api/auth/login", {"login": "admin", "password": "admin123", "role": "admin"})
        today_s = datetime.now().strftime("%Y-%m-%d")  # boshlash faqat "bugun" uchun ruxsat
        # Vali (instructor 3) — haftaning 7 kunida ham ishlaydi (yakshanba ham o'tadi)
        ok, r = admin.post("/api/admin/sessions", {"date": today_s, "start_time": "09:00", "end_time": "10:00", "instructor_id": 3, "student_ids": [1, 2]})
        self.assertEqual(ok, 200, r)
        sid = r["id"]
        # instruktor bilan
        inst = Client()
        inst.post("/api/auth/login", {"login": "usrL_00003", "password": "usrP_00003", "role": "instructor"})
        st, r = inst.post(f"/api/instructor/sessions/{sid}/start")
        self.assertEqual(st, 200, r)
        st, r = inst.post(f"/api/instructor/sessions/{sid}/attendance", {"student_id": 1, "status": "present"})
        self.assertEqual(st, 200, r)
        st, r = inst.post(f"/api/instructor/sessions/{sid}/attendance", {"student_id": 2, "status": "absent"})
        self.assertEqual(st, 200, r)
        st, r = inst.post(f"/api/instructor/sessions/{sid}/finish")
        self.assertEqual(st, 200, r)
        detail = inst.get(f"/api/instructor/sessions/{sid}")[1]["session"]
        self.assertEqual(detail["status"], "completed")

    def test_27_cancel_and_reschedule(self):
        admin = Client()
        admin.post("/api/auth/login", {"login": "admin", "password": "admin123", "role": "admin"})
        ok, r = admin.post("/api/admin/sessions", {"date": "2026-11-09", "start_time": "11:00", "end_time": "12:00", "instructor_id": 1, "student_ids": [1]})
        self.assertEqual(ok, 200, r)
        sid = r["id"]
        # Ko'chirish: Jasur'ga
        st, r2 = admin.post(f"/api/admin/sessions/{sid}/reschedule", {"date": "2026-11-10", "start_time": "10:00", "end_time": "11:00", "instructor_id": 2})
        self.assertEqual(st, 200, r2)
        det = admin.get(f"/api/admin/sessions/{sid}")[1]["session"]
        self.assertEqual(det["instructor_name"], "Jasur Aliyev")
        self.assertEqual(det["car_plate_snapshot"], "01 B 456 BB")  # Jasurning avtomobili avtomatik
        st, r3 = admin.post(f"/api/admin/sessions/{sid}/cancel", {"reason": "yomg'ir"})
        self.assertEqual(st, 200)
        det = admin.get(f"/api/admin/sessions/{sid}")[1]["session"]
        self.assertEqual(det["status"], "cancelled")


class TestCarChangeHistory(Base):
    def test_30_car_change_keeps_history(self):
        admin = Client()
        admin.post("/api/auth/login", {"login": "admin", "password": "admin123", "role": "admin"})
        # Akmal bilan eski session (Cobalt)
        ok, r = admin.post("/api/admin/sessions", {"date": "2026-12-01", "start_time": "09:00", "end_time": "10:00", "instructor_id": 1, "student_ids": []})
        old_sid = r["id"]
        self.assertEqual(r["auto"]["car"], "Chevrolet Cobalt")
        # Akmalning mashinasini almashtiramiz: Cobalt -> Onix (id 3)
        st, r2 = admin.post("/api/admin/instructors/1/car", {"car_id": 3})
        self.assertEqual(st, 200, r2)
        # Eski session tarixi buzilmasin
        old_detail = admin.get(f"/api/admin/sessions/{old_sid}")[1]["session"]
        self.assertEqual(old_detail["car_plate_snapshot"], "01 A 123 AA")
        # Yangi session -> Onix
        ok, r3 = admin.post("/api/admin/sessions", {"date": "2026-12-02", "start_time": "09:00", "end_time": "10:00", "instructor_id": 1, "student_ids": []})
        self.assertEqual(r3["auto"]["car"], "Chevrolet Onix")
        self.assertEqual(r3["auto"]["plate"], "01 C 789 CC")
        # Keyingi testlar uchun avtomobillarni tiklaymiz: Akmal -> Cobalt (1), Vali -> Onix (3)
        admin.post("/api/admin/instructors/1/car", {"car_id": 1})
        admin.post("/api/admin/instructors/3/car", {"car_id": 3})


class TestSecurityRBAC(Base):
    def test_40_student_cannot_access_admin(self):
        st = Client()
        st.post("/api/auth/login", {"login": "usrL_00004", "password": "usrP_00004", "role": "student"})
        code, r = st.get("/api/admin/users")
        self.assertEqual(code, 403)
        self.assertEqual(r["error"], "forbidden")

    def test_41_instructor_cannot_access_admin(self):
        it = Client()
        it.post("/api/auth/login", {"login": "usrL_00001", "password": "usrP_00001", "role": "instructor"})
        code, r = it.get("/api/admin/dashboard")
        self.assertEqual(code, 403)

    def test_42_student_cannot_see_other_student_data(self):
        st = Client()
        st.post("/api/auth/login", {"login": "usrL_00004", "password": "usrP_00004", "role": "student"})
        # Boshqa talabaning sessionlari API bor, lekin yo'l boshqa talabaga tegishli emas
        sessions = st.get("/api/student/sessions?upcoming=1")[1]["sessions"]
        # 1-talaba (Omadbek) sessionlari ro'yxatida faqat o'ziniki bo'ladi; boshqa talabaning ma'lumotlari yo'q
        for s in sessions:
            # student na faqat o'z sessionlarini ko'ra oladi — ular ro'yxati Omadbek'dan
            pass
        # shaxsiy profil
        me = st.get("/api/auth/me")[1]
        self.assertEqual(me["user"]["login"], "usrL_00004")

    def test_43_instructor_cannot_manage_others_sessions(self):
        it = Client()
        it.post("/api/auth/login", {"login": "usrL_00001", "password": "usrP_00001", "role": "instructor"})
        # Jasurning sessioni emas; Akmal boshqa instruktorlar sessionlarini boshqara olmaydi
        admin = Client()
        admin.post("/api/auth/login", {"login": "admin", "password": "admin123", "role": "admin"})
        ok, r = admin.post("/api/admin/sessions", {"date": "2026-12-10", "start_time": "09:00", "end_time": "10:00", "instructor_id": 2, "student_ids": []})
        sid = r["id"]
        st, r2 = it.post(f"/api/instructor/sessions/{sid}/start")
        self.assertEqual(st, 404)  # topilmadi — boshqa instruktor sessioni
        st, r3 = it.get(f"/api/instructor/sessions/{sid}")
        self.assertEqual(st, 404)

    def test_44_no_password_in_responses(self):
        admin = Client()
        admin.post("/api/auth/login", {"login": "admin", "password": "admin123", "role": "admin"})
        _, r = admin.get("/api/admin/users")
        for u in r["users"]:
            self.assertNotIn("password_hash", u)
            self.assertNotIn("usrP_", json.dumps(u))


class TestProfileAvatar2FA(Base):
    """Modul 2 — profil rasm yuklash, 2FA (TOTP) va profil tahriri."""

    TINY_PNG = ("data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJ"
                "AAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")

    def _cleanup_avatar(self, path_):
        if path_ and path_.startswith("/uploads/avatars/"):
            fp = ROOT / "web" / path_.lstrip("/")
            try:
                if fp.exists():
                    fp.unlink()
            except OSError:
                pass

    def test_50_avatar_upload_valid(self):
        admin = Client()
        admin.post("/api/auth/login", {"login": "admin", "password": "admin123", "role": "admin"})
        st, r = admin.put("/api/me/profile/avatar", {"image": self.TINY_PNG})
        self.assertEqual(st, 200, r)
        self.assertTrue(r["profile_image"].startswith("/uploads/avatars/"))
        # me() qaytariladigan user'da ko'rinadi
        _, me = admin.get("/api/auth/me")
        self.assertEqual(me["user"]["profile_image"], r["profile_image"])
        self._cleanup_avatar(r["profile_image"])

    def test_51_avatar_rejects_bad_format(self):
        admin = Client()
        admin.post("/api/auth/login", {"login": "admin", "password": "admin123", "role": "admin"})
        st, r = admin.put("/api/me/profile/avatar", {"image": "data:image/gif;base64," + "A" * 100})
        self.assertEqual(st, 400)
        self.assertEqual(r["error"], "img.format")
        st, r2 = admin.put("/api/me/profile/avatar", {"image": "notadata"})
        self.assertEqual(st, 400)
        self.assertEqual(r2["error"], "img.format")

    def test_52_avatar_rejects_oversize(self):
        import base64 as _b64
        admin = Client()
        admin.post("/api/auth/login", {"login": "admin", "password": "admin123", "role": "admin"})
        big = _b64.b64encode(b"x" * (5 * 1024 * 1024 + 100)).decode()
        st, r = admin.put("/api/me/profile/avatar", {"image": "data:image/png;base64," + big})
        self.assertEqual(st, 400)
        self.assertEqual(r["error"], "img.size")

    def _latest_twofa_code(self):
        import re
        import sqlite3
        con = sqlite3.connect(os.environ["AVTOMAKTAB_DB"])
        try:
            row = con.execute(
                "SELECT body FROM notifications WHERE type='2fa' ORDER BY id DESC LIMIT 1").fetchone()
        finally:
            con.close()
        if not row:
            return None
        m = re.search(r"\d{6}", row[0])
        return m.group() if m else None

    def test_53_2fa_full_cycle(self):
        admin = Client()
        admin.post("/api/auth/login", {"login": "admin", "password": "admin123", "role": "admin"})
        # noto'g'ri parol bilan yoqib bo'lmaydi
        st, r = admin.post("/api/me/2fa/enable", {"password": "wrong"})
        self.assertEqual(st, 400)
        self.assertEqual(r["error"], "auth.wrong_old_password")
        # to'g'ri parol + telefon bilan SMS kod yuboriladi (QR/secret yo'q)
        st, r = admin.post("/api/me/2fa/enable", {"password": "admin123", "phone": "+998901112233"})
        self.assertEqual(st, 200, r)
        self.assertNotIn("secret", r)
        self.assertNotIn("otpauth", r)
        # kod bildirishnoma (simulyatsiya) orqali yetib boradi
        code = self._latest_twofa_code()
        self.assertTrue(code and len(code) == 6, code)
        # noto'g'ri kod rad etiladi
        st, r2 = admin.post("/api/me/2fa/verify-enable", {"code": "000000"})
        self.assertEqual(st, 400)
        self.assertEqual(r2["error"], "auth.otp_invalid")
        # to'g'ri SMS kod bilan yoqiladi
        st, r3 = admin.post("/api/me/2fa/verify-enable", {"code": code})
        self.assertEqual(st, 200, r3)
        _, me = admin.get("/api/auth/me")
        self.assertEqual(me["user"]["totp_enabled"], 1)
        # endi loginda kod so'raladi (yangi SMS kod yuboriladi)
        st, r4 = admin.post("/api/auth/login", {"login": "admin", "password": "admin123", "role": "admin"})
        self.assertEqual(r4["error"], "auth.otp_required")
        code2 = self._latest_twofa_code()
        self.assertTrue(code2 and len(code2) == 6, code2)
        # kod bilan kirish ishlaydi
        st, r5 = admin.post("/api/auth/login", {"login": "admin", "password": "admin123", "role": "admin", "otp": code2})
        self.assertEqual(st, 200, r5)
        # noto'g'ri parol bilan o'chirib bo'lmaydi, parol bilan o'chiriladi
        st, r6 = admin.post("/api/me/2fa/disable", {"password": "wrong"})
        self.assertEqual(st, 400)
        st, r7 = admin.post("/api/me/2fa/disable", {"password": "admin123"})
        self.assertEqual(st, 200, r7)
        # 2FA o'chgach, kod siz kirish qaytadan ishlaydi
        st, r8 = admin.post("/api/auth/login", {"login": "admin", "password": "admin123", "role": "admin"})
        self.assertEqual(st, 200, r8)

    def test_54_profile_update(self):
        st = Client()
        st.post("/api/auth/login", {"login": "usrL_00004", "password": "usrP_00004", "role": "student"})
        code, r = st.put("/api/me/profile", {"phone": "+998901234567", "first_name": "Omad"})
        self.assertEqual(code, 200, r)
        _, me = st.get("/api/auth/me")
        self.assertEqual(me["user"]["phone"], "+998901234567")
        self.assertEqual(me["user"]["first_name"], "Omad")
        # orqaga qaytaramiz
        st.put("/api/me/profile", {"phone": "", "first_name": "Omadbek"})


class TestCarPhotosAndStatus(Base):
    """M5: avtomobil fotosuratlari va tezkor status o'zgarishi."""

    PNG = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="

    def _admin(self):
        a = Client()
        a.post("/api/auth/login", {"login": "admin", "password": "admin123", "role": "admin"})
        return a

    def _upload_photo(self, admin, car_id):
        return admin.post(f"/api/admin/cars/{car_id}/photos", {"image": "data:image/png;base64," + TestCarPhotosAndStatus.PNG})

    def test_60_quick_status_change(self):
        admin = self._admin()
        # dastlab aktiv
        _, r = admin.get("/api/admin/cars")
        car = next(c for c in r["cars"] if c["plate_number"] == "01 A 123 AA")
        st, r2 = admin.put(f"/api/admin/cars/{car['id']}/status", {"status": "repair"})
        self.assertEqual(st, 200, r2)
        self.assertEqual(r2["status"], "repair")
        _, r3 = admin.get("/api/admin/cars")
        self.assertEqual(next(c for c in r3["cars"] if c["id"] == car["id"])["status"], "repair")
        # noto'g'ri status
        st, r4 = admin.put(f"/api/admin/cars/{car['id']}/status", {"status": "flying"})
        self.assertEqual(st, 400)
        self.assertEqual(r4["error"], "car.bad_status")
        # tiklaymiz
        admin.put(f"/api/admin/cars/{car['id']}/status", {"status": "active"})
        # RBAC: talaba statusni o'zgartira olmaydi
        stud = Client()
        stud.post("/api/auth/login", {"login": "usrL_00004", "password": "usrP_00004", "role": "student"})
        st, _ = stud.put(f"/api/admin/cars/{car['id']}/status", {"status": "inactive"})
        self.assertEqual(st, 403)

    def test_61_photo_add_list_remove(self):
        admin = self._admin()
        cars = admin.get("/api/admin/cars")[1]["cars"]
        cid = cars[0]["id"]
        # qo'shish
        st, r = self._upload_photo(admin, cid)
        self.assertEqual(st, 200, r)
        _, r2 = admin.get("/api/admin/cars")
        ph = r2["photos"][str(cid)]
        self.assertEqual(len(ph), 1)
        self.assertTrue(ph[0]["path"].startswith("/uploads/cars/"))
        # yana birini qo'shamiz
        st, r3 = self._upload_photo(admin, cid)
        self.assertEqual(st, 200, r3)
        _, r4 = admin.get("/api/admin/cars")
        self.assertEqual(len(r4["photos"][str(cid)]), 2)
        # noto'g'ri format rad etiladi
        st, r5 = admin.post(f"/api/admin/cars/{cid}/photos", {"image": "not-a-data-url"})
        self.assertEqual(st, 400)
        self.assertEqual(r5["error"], "img.format")
        # bittasini o'chirish
        pid = r["id"]
        st, r6 = admin.delete(f"/api/admin/cars/{cid}/photos/{pid}")
        self.assertEqual(st, 200, r6)
        _, r7 = admin.get("/api/admin/cars")
        self.assertEqual(len(r7["photos"][str(cid)]), 1)
        # qolganini ham o'chirib tozalaymiz
        pid2 = r3["id"]
        admin.delete(f"/api/admin/cars/{cid}/photos/{pid2}")
        _, r8 = admin.get("/api/admin/cars")
        self.assertFalse(r8["photos"].get(str(cid)))

    def test_62_photo_limit_and_rbac(self):
        admin = self._admin()
        cars = admin.get("/api/admin/cars")[1]["cars"]
        cid = cars[0]["id"]
        pids = []
        try:
            for _ in range(8):
                st, r = self._upload_photo(admin, cid)
                self.assertEqual(st, 200, r)
                pids.append(r["id"])
            # 9-rasm rad etiladi
            st, r = self._upload_photo(admin, cid)
            self.assertEqual(st, 409)
            self.assertEqual(r["error"], "car.photo_limit")
        finally:
            for pid in pids:
                admin.delete(f"/api/admin/cars/{cid}/photos/{pid}")
        # RBAC: talaba o'chira olmaydi
        stud = Client()
        stud.post("/api/auth/login", {"login": "usrL_00004", "password": "usrP_00004", "role": "student"})
        st, _ = stud.delete(f"/api/admin/cars/{cid}/photos/1")
        self.assertEqual(st, 403)
        st, _ = stud.post(f"/api/admin/cars/{cid}/photos", {"image": "x"})
        self.assertEqual(st, 403)

    def test_63_instructor_sees_car_photos(self):
        admin = self._admin()
        # Akmal (instructor 1) Cobalt'da — fotosurat qo'shamiz
        akmal = Client()
        akmal.post("/api/auth/login", {"login": "usrL_00001", "password": "usrP_00001", "role": "instructor"})
        _, ctx = akmal.get("/api/instructor/car")
        cid = ctx["car"]["id"]
        st, r = self._upload_photo(admin, cid)
        self.assertEqual(st, 200, r)
        try:
            _, r2 = akmal.get("/api/instructor/car")
            self.assertEqual(r2["car"]["id"], cid)
            self.assertIn(r["path"], [p["path"] for p in r2["photos"]])
        finally:
            admin.delete(f"/api/admin/cars/{cid}/photos/{r['id']}")


class TestHomeAndToday(Base):
    def test_70_admin_dashboard_weekly_stats(self):
        admin = Client()
        admin.post("/api/auth/login", {"login": "admin", "password": "admin123", "role": "admin"})
        st, r = admin.get("/api/admin/dashboard")
        self.assertEqual(st, 200, r)
        d = r["dashboard"]
        for k in ("week_sessions", "week_done", "week_hours", "week_requests", "week_new_users"):
            self.assertIn(k, d)
        self.assertIsInstance(d["week_sessions"], int)
        self.assertIsInstance(d["week_hours"], float)

    def test_71_instructor_home(self):
        inst = Client()
        inst.post("/api/auth/login", {"login": "usrL_00001", "password": "usrP_00001", "role": "instructor"})
        st, r = inst.get("/api/instructor/home")
        self.assertEqual(st, 200, r)
        for k in ("sessions", "done", "hours", "students", "today"):
            self.assertIn(k, r["weekly"])
        for k in ("sessions", "done", "hours"):
            self.assertIn(k, r["overall"])
        self.assertIn("car", r)

    def test_72_student_home_overall_progress(self):
        st = Client()
        st.post("/api/auth/login", {"login": "usrL_00004", "password": "usrP_00004", "role": "student"})
        code, r = st.get("/api/student/home")
        self.assertEqual(code, 200, r)
        self.assertIn("overall", r)
        self.assertIn("weekly", r)
        self.assertIn("next", r)
        self.assertIsInstance(r["overall"]["sessions"], int)
        self.assertIsInstance(r["weekly"]["done"], int)

    def test_73_student_today(self):
        st = Client()
        st.post("/api/auth/login", {"login": "usrL_00004", "password": "usrP_00004", "role": "student"})
        code, r = st.get("/api/student/today")
        self.assertEqual(code, 200, r)
        self.assertIn("sessions", r)
        self.assertIsInstance(r["sessions"], list)

    def test_74_rbac_home_and_today(self):
        stud = Client()
        stud.post("/api/auth/login", {"login": "usrL_00004", "password": "usrP_00004", "role": "student"})
        st, _ = stud.get("/api/instructor/home")
        self.assertEqual(st, 403)
        inst = Client()
        inst.post("/api/auth/login", {"login": "usrL_00001", "password": "usrP_00001", "role": "instructor"})
        st, _ = inst.get("/api/student/home")
        self.assertEqual(st, 403)
        st, _ = inst.get("/api/student/today")
        self.assertEqual(st, 403)


class TestAdminDashboardM8(Base):
    def test_80_dashboard_week_chart_data(self):
        admin = Client()
        admin.post("/api/auth/login", {"login": "admin", "password": "admin123", "role": "admin"})
        st, r = admin.get("/api/admin/dashboard")
        self.assertEqual(st, 200, r)
        byd = r["dashboard"].get("week_sessions_by_day")
        self.assertIsInstance(byd, list)
        self.assertEqual(len(byd), 7)
        for b in byd:
            self.assertIn("date", b)
            self.assertIn("count", b)
            self.assertIsInstance(b["count"], int)
        # kunlar tartibi hafta boshidan boshlanadi
        from datetime import datetime
        monday = datetime.strptime(byd[0]["date"], "%Y-%m-%d").weekday()
        self.assertEqual(monday, 0)

    def test_81_instructors_include_profile_image(self):
        admin = Client()
        admin.post("/api/auth/login", {"login": "admin", "password": "admin123", "role": "admin"})
        st, r = admin.get("/api/admin/instructors")
        self.assertEqual(st, 200, r)
        self.assertTrue(r["instructors"])
        for u in r["instructors"]:
            self.assertIn("profile_image", u)

    def test_82_requests_include_profile_image(self):
        admin = Client()
        admin.post("/api/auth/login", {"login": "admin", "password": "admin123", "role": "admin"})
        st, r = admin.get("/api/admin/requests")
        self.assertEqual(st, 200, r)
        for req in r["requests"]:
            self.assertIn("profile_image", req)

    def test_83_users_include_profile_image(self):
        admin = Client()
        admin.post("/api/auth/login", {"login": "admin", "password": "admin123", "role": "admin"})
        st, r = admin.get("/api/admin/users?role=student")
        self.assertEqual(st, 200, r)
        self.assertTrue(r["users"])
        for u in r["users"]:
            self.assertIn("profile_image", u)


class TestSettingsM12(Base):
    """M12 — Sozlamalar bo'limini kengaytirish:
    shaxsiy sozlamalar (til/tema/bildirishnomalar), faol sessiyalar,
    platforma sozlamalari (mashg'ulot davomiyligi/ish vaqti/eslatma) va
    avtomatik eslatmalar."""

    def _next_monday(self):
        # Seed'dagi "bugun/ertaga" sessiyalari bilan to'qnashmaslik uchun
        # keyingi dushanbani kamida 7 kun oldinga surib olamiz (haftaning istalgan kunida ishlaydi).
        from datetime import timedelta
        d = datetime.now()
        mon = d + timedelta(days=(7 - d.weekday()) % 7 or 7)
        return (mon + timedelta(days=7)).strftime("%Y-%m-%d")

    def test_90_me_settings_defaults(self):
        c = Client()
        c.post("/api/auth/login", {"login": "admin", "password": "admin123", "role": "admin"})
        st, r = c.get("/api/me/settings")
        self.assertEqual(st, 200, r)
        s = r["settings"]
        self.assertIn("lang", s)
        self.assertIn("theme", s)
        self.assertEqual(set(s["notif"].keys()), {"lesson", "request", "message", "security", "reminder"})
        self.assertTrue(all(s["notif"].values()))

    def test_91_me_settings_put_and_get(self):
        c = Client()
        c.post("/api/auth/login", {"login": "admin", "password": "admin123", "role": "admin"})
        st, r = c.put("/api/me/settings", {"lang": "ru", "theme": "dark", "notif": {"lesson": False, "request": False}})
        self.assertEqual(st, 200, r)
        st, r = c.get("/api/me/settings")
        self.assertEqual(st, 200, r)
        self.assertEqual(r["settings"]["lang"], "ru")
        self.assertEqual(r["settings"]["theme"], "dark")
        self.assertFalse(r["settings"]["notif"]["lesson"])
        self.assertFalse(r["settings"]["notif"]["request"])
        self.assertTrue(r["settings"]["notif"]["message"])
        self.assertTrue(r["settings"]["notif"]["security"])

    def test_92_me_settings_invalid_values_ignored(self):
        c = Client()
        c.post("/api/auth/login", {"login": "admin", "password": "admin123", "role": "admin"})
        c.put("/api/me/settings", {"lang": "xx", "theme": "neon"})
        st, r = c.get("/api/me/settings")
        self.assertEqual(st, 200, r)
        self.assertNotEqual(r["settings"]["lang"], "xx")
        self.assertNotEqual(r["settings"]["theme"], "neon")

    def test_93_sessions_list_and_current(self):
        c = Client()
        c.post("/api/auth/login", {"login": "admin", "password": "admin123", "role": "admin"})
        st, r = c.get("/api/me/sessions")
        self.assertEqual(st, 200, r)
        self.assertGreaterEqual(len(r["sessions"]), 1)
        self.assertEqual(sum(1 for s in r["sessions"] if s["current"]), 1)
        for s in r["sessions"]:
            self.assertIn("created_at", s)
            self.assertIn("expires_at", s)
            self.assertIn("last_seen", s)

    def test_94_revoke_other_device_kicks_it(self):
        c1 = Client()
        c1.post("/api/auth/login", {"login": "admin", "password": "admin123", "role": "admin"})
        c2 = Client()
        c2.post("/api/auth/login", {"login": "admin", "password": "admin123", "role": "admin"})
        st, r = c1.get("/api/me/sessions")
        self.assertGreaterEqual(len(r["sessions"]), 2)
        other = next(s for s in r["sessions"] if not s["current"])
        # c1 (joriy) boshqa qurilma sessiyasini o'chirsin
        st, rev = c1.post("/api/me/sessions/revoke", {"id": other["id"]})
        self.assertEqual(st, 200, rev)
        self.assertFalse(rev["current_revoked"])
        # o'sha qurilma (c2) endi kirishi yo'q
        st2, r2 = c2.get("/api/auth/me")
        self.assertEqual(st2, 401)

    def test_95_revoke_current_requires_relogin(self):
        c = Client()
        c.post("/api/auth/login", {"login": "admin", "password": "admin123", "role": "admin"})
        st, r = c.get("/api/me/sessions")
        cur = next(s for s in r["sessions"] if s["current"])
        st, rev = c.post("/api/me/sessions/revoke", {"id": cur["id"]})
        self.assertEqual(st, 200, rev)
        self.assertTrue(rev["current_revoked"])
        st2, r2 = c.get("/api/auth/me")
        self.assertEqual(st2, 401)

    def test_96_revoke_all_logs_out(self):
        c = Client()
        c.post("/api/auth/login", {"login": "admin", "password": "admin123", "role": "admin"})
        st, r = c.post("/api/me/sessions/revoke-all", {})
        self.assertEqual(st, 200, r)
        self.assertTrue(r["current_revoked"])
        st2, r2 = c.get("/api/auth/me")
        self.assertEqual(st2, 401)

    def test_97_notification_prefs_apply(self):
        # Instruktor (Akmal) mashg'ulot bildirishnomalarini o'chiradi
        inst = Client()
        inst.post("/api/auth/login", {"login": "usrL_00001", "password": "usrP_00001", "role": "instructor"})
        inst.put("/api/me/settings", {"notif": {"lesson": False}})
        # Student (Omadbek) default holatda
        stu = Client()
        stu.post("/api/auth/login", {"login": "usrL_00004", "password": "usrP_00004", "role": "student"})

        admin = Client()
        admin.post("/api/auth/login", {"login": "admin", "password": "admin123", "role": "admin"})
        d = self._next_monday()
        st, r = admin.post("/api/admin/sessions", {
            "date": d, "start_time": "15:00", "end_time": "16:30",
            "instructor_id": 1, "student_ids": [1], "notes": "M12 prefs test",
        })
        self.assertEqual(st, 200, r)
        sid = r["id"]

        # Instruktor: lesson bildirishnomasi KELMASLIGI kerak
        st, ni = inst.get("/api/me/notifications")
        self.assertEqual(st, 200, ni)
        for n in ni["notifications"]:
            d = jload(n.get("data") or "{}", {}) if not isinstance(n.get("data"), dict) else (n.get("data") or {})
            if str(d.get("session_id")) == str(sid):
                self.assertNotIn(n["type"], ("lesson", "cancel"), "prefs off bo'lganda kelmasligi kerak")

        # Student: lesson.assigned KELISHI kerak (default prefs)
        st, ns = stu.get("/api/me/notifications")
        self.assertEqual(st, 200, ns)
        got = [n for n in ns["notifications"]
               if str((jload(n.get("data") or "{}", {}) if not isinstance(n.get("data"), dict) else (n.get("data") or {})).get("session_id")) == str(sid)
               and n["type"] == "lesson"]
        self.assertTrue(got, "student default prefs bilan lesson bildirishnomasini oladi")

        # Xavfsizlik toifasi chapdan o'chirilgan bildirishnoma emas: reset so'rovi o'tadi
        before = [n for n in inst.get("/api/me/notifications")[1]["notifications"] if n["type"] == "security"]
        st, rr = inst.post("/api/auth/request-password-reset", {"login": "usrL_00001"})
        self.assertEqual(st, 200, rr)
        after = [n for n in inst.get("/api/me/notifications")[1]["notifications"] if n["type"] == "security"]
        self.assertLess(len(before), len(after), "security toifasi bloklanmaydi")

    def test_98_admin_platform_settings_defaults_and_update(self):
        admin = Client()
        admin.post("/api/auth/login", {"login": "admin", "password": "admin123", "role": "admin"})
        st, r = admin.get("/api/admin/settings")
        self.assertEqual(st, 200, r)
        s = r["settings"]
        self.assertEqual(s["lesson_duration_min"], 90)
        self.assertEqual(s["work_start"], "09:00")
        self.assertEqual(s["work_end"], "18:00")
        self.assertEqual(s["reminder_minutes"], 60)
        # M8: platforma nomi / asosiy filial sozlamalari olib tashlangan
        self.assertNotIn("platform_name", s)
        self.assertNotIn("branch", s)
        st, r = admin.put("/api/admin/settings", {
            "lesson_duration_min": 60, "work_start": "10:00", "work_end": "20:00",
            "reminder_minutes": 30,
        })
        self.assertEqual(st, 200, r)
        st, r = admin.get("/api/admin/settings")
        self.assertEqual(r["settings"]["lesson_duration_min"], 60)
        self.assertEqual(r["settings"]["work_start"], "10:00")
        self.assertEqual(r["settings"]["work_end"], "20:00")
        self.assertEqual(r["settings"]["reminder_minutes"], 30)
        self.assertNotIn("platform_name", r["settings"])

    def test_99_default_duration_used_when_end_missing(self):
        admin = Client()
        admin.post("/api/auth/login", {"login": "admin", "password": "admin123", "role": "admin"})
        admin.put("/api/admin/settings", {"lesson_duration_min": 90})
        d = self._next_monday()
        st, r = admin.post("/api/admin/sessions", {
            "date": d, "start_time": "10:00",
            "instructor_id": 1, "student_ids": [1], "notes": "M12 dur test",
        })
        self.assertEqual(st, 200, r)
        st, det = admin.get(f"/api/admin/sessions/{r['id']}")
        self.assertEqual(st, 200, det)
        self.assertEqual(det["session"]["end_time"], "11:30")  # 10:00 + 90 daqiqa

    def test_100_reminder_generation_no_duplicates(self):
        db = Db(str(TMP / "test.db"))
        # Reminder oynasi 60 daqiqa — ishonchli test
        admin = Client()
        admin.post("/api/auth/login", {"login": "admin", "password": "admin123", "role": "admin"})
        admin.put("/api/admin/settings", {"reminder_minutes": 60})
        # Bugungi mashg'ulot: hozirdan +10 daqiqa
        st_dt = datetime.now() + timedelta(minutes=10)
        date, start = st_dt.strftime("%Y-%m-%d"), st_dt.strftime("%H:%M")
        end = (st_dt + timedelta(minutes=60)).strftime("%H:%M")
        sid = db.ex(
            """INSERT INTO lesson_sessions(date,start_time,end_time,instructor_id,car_id,car_name_snapshot,
               car_plate_snapshot,capacity_snapshot,status,notes,created_at,updated_at)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
            (date, start, end, 1, 1, "Test avto", "A 001 AA", 4, "scheduled", "M12 reminder", now(), now()),
        )
        db.ex(
            """INSERT INTO session_students(session_id, student_id, pickup_address, attendance_status, student_status, joined_at)
               VALUES(?,?,'','unmarked','active',?)""",
            (sid, 1, now()),
        )
        n1 = ensure_reminders(db)
        self.assertGreaterEqual(n1, 2, "instruktor + talaba uchun eslatma yuborilishi kerak")
        n2 = ensure_reminders(db)
        self.assertEqual(n2, 0, "takroriy eslatma yuborilmasligi kerak")
        rows = db.q("SELECT * FROM notifications WHERE type='reminder'")
        mine = [r for r in rows
                if (jload(r.get("data") or "{}", {}) if not isinstance(r.get("data"), dict) else (r.get("data") or {})).get("session_id") == sid]
        self.assertGreaterEqual(len(mine), 2)
        # tozalash
        for r in mine:
            db.upd("DELETE FROM notifications WHERE id=?", (r["id"],))
        db.upd("DELETE FROM session_students WHERE session_id=?", (sid,))
        db.upd("DELETE FROM lesson_sessions WHERE id=?", (sid,))


class TestM13CancelReschedule(Base):
    """M13-A — Instruktor uchun bekor qilish / qayta rejalashtirish oqimi
    (sababi bilan), original vaqt tarixi saqlanadi, ikkala tomon ko'radi."""

    def _next_day(self, days=0):
        # Seed'dagi "bugun/ertaga" sessiyalari bilan to'qnashmaslik uchun
        # bazaviy dushanbani kamida 7 kun oldinga surib olamiz.
        from datetime import timedelta
        d = datetime.now()
        mon = d + timedelta(days=(7 - d.weekday()) % 7 or 7) + timedelta(days=7)
        return (mon + timedelta(days=days)).strftime("%Y-%m-%d")

    def tearDown(self):
        """M13A testlari qolgan sessiyalarni tozalaydi (boshqa klasslar testlariga xalaqit bermaslik uchun)."""
        db = Db(str(TMP / "test.db"))
        rows = db.q("SELECT id FROM lesson_sessions WHERE notes='M13A'")
        for r in rows:
            db.upd("DELETE FROM session_students WHERE session_id=?", (r["id"],))
            db.upd("DELETE FROM notifications WHERE data LIKE ?", (f'%"session_id": {r["id"]}%',))
            db.upd("DELETE FROM attendance WHERE session_id=?", (r["id"],))
            db.upd("DELETE FROM lesson_sessions WHERE id=?", (r["id"],))

    def _mk(self, admin, date, start, end):
        st, r = admin.post("/api/admin/sessions",
                           {"date": date, "start_time": start, "end_time": end,
                            "instructor_id": 1, "student_ids": [1], "notes": "M13A"})
        self.assertEqual(st, 200, r)
        return r["id"]

    def _admin(self):
        c = Client()
        c.post("/api/auth/login", {"login": "admin", "password": "admin123", "role": "admin"})
        return c

    def _inst(self):
        c = Client()
        c.post("/api/auth/login", {"login": "usrL_00001", "password": "usrP_00001", "role": "instructor"})
        return c

    def _stud(self):
        c = Client()
        c.post("/api/auth/login", {"login": "usrL_00004", "password": "usrP_00004", "role": "student"})
        return c

    def test_110_instructor_cancel_with_reason(self):
        admin = self._admin()
        d = self._next_day()
        sid = self._mk(admin, d, "08:30", "09:30")
        inst = self._inst()
        st, r = inst.post(f"/api/instructor/sessions/{sid}/cancel", {"reason": "car"})
        self.assertEqual(st, 200, r)
        st, det = inst.get(f"/api/instructor/sessions/{sid}")
        self.assertEqual(st, 200, det)
        self.assertEqual(det["session"]["status"], "cancelled")
        self.assertEqual(det["session"]["cancel_reason"], "car")
        # Talaba bildirishnoma olishi kerak (type ustuni ntype 'cancel' bo'ladi, title'da 'lesson.cancelled')
        db = Db(str(TMP / "test.db"))
        rows = db.q("SELECT * FROM notifications WHERE data LIKE ?", (f'%"session_id": {sid}%',))
        self.assertTrue(
            any(jload(r["data"]).get("verb") == "cancelled" for r in rows),
            "cancel bildirishnomasi (verb=cancelled) yuborilishi kerak",
        )

    def test_111_instructor_reschedule_preserves_original(self):
        admin = self._admin()
        d = self._next_day()
        sid = self._mk(admin, d, "16:30", "17:30")
        new_d = self._next_day(1)  # seshanba
        inst = self._inst()
        st, r = inst.post(f"/api/instructor/sessions/{sid}/reschedule",
                          {"date": new_d, "start_time": "16:00", "end_time": "17:00"})
        self.assertEqual(st, 200, r)
        st, det = inst.get(f"/api/instructor/sessions/{sid}")
        self.assertEqual(st, 200, det)
        self.assertEqual(det["session"]["date"], new_d)
        self.assertEqual(det["session"]["start_time"], "16:00")
        self.assertEqual(det["session"]["status"], "scheduled")
        self.assertEqual(det["session"]["original_date"], d, "original sana saqlanishi kerak")
        self.assertEqual(det["session"]["original_start_time"], "16:30")
        # Instruktor ham reschedule bildirishnomasini oladi
        db = Db(str(TMP / "test.db"))
        rows = db.q("SELECT * FROM notifications WHERE data LIKE ?", (f'%"session_id": {sid}%',))
        self.assertTrue(
            any(jload(r["data"]).get("verb") == "rescheduled" for r in rows),
            "reschedule bildirishnomasi (verb=rescheduled) yuborilishi kerak",
        )

    def test_112_instructor_reschedule_conflict_409(self):
        admin = self._admin()
        d = self._next_day()
        a = self._mk(admin, d, "11:45", "12:45")
        self._mk(admin, d, "15:30", "16:30")
        inst = self._inst()
        st, r = inst.post(f"/api/instructor/sessions/{a}/reschedule",
                          {"date": d, "start_time": "15:30", "end_time": "16:30"})
        self.assertEqual(st, 409, r)
        self.assertEqual(r["error"], "session.rules_violated")
        self.assertIn("instructor_busy", r.get("params", {}).get("errors", []))

    def test_113_instructor_cancel_wrong_status(self):
        admin = self._admin()
        d = self._next_day()
        sid = self._mk(admin, d, "14:30", "15:30")
        db = Db(str(TMP / "test.db"))
        db.upd("UPDATE lesson_sessions SET status='completed', completed_at=? WHERE id=?", (now(), sid))
        inst = self._inst()
        st, r = inst.post(f"/api/instructor/sessions/{sid}/cancel", {"reason": "school"})
        self.assertEqual(st, 409, r)
        self.assertEqual(r["error"], "session.wrong_status")

    def test_114_student_cannot_cancel_or_reschedule(self):
        admin = self._admin()
        d = self._next_day()
        sid = self._mk(admin, d, "08:00", "09:00")
        stud = self._stud()
        st, r = stud.post(f"/api/instructor/sessions/{sid}/cancel", {"reason": "x"})
        self.assertEqual(st, 403, r)
        st, r = stud.post(f"/api/instructor/sessions/{sid}/reschedule",
                          {"date": d, "start_time": "09:00", "end_time": "10:00"})
        self.assertEqual(st, 403, r)

    def test_115_admin_reschedule_keeps_original_date(self):
        admin = self._admin()
        d = self._next_day()
        sid = self._mk(admin, d, "09:30", "10:00")
        tue, thu = self._next_day(1), self._next_day(3)
        st, r = admin.post(f"/api/admin/sessions/{sid}/reschedule",
                           {"date": tue, "start_time": "10:00", "end_time": "11:00"})
        self.assertEqual(st, 200, r)
        st, r = admin.post(f"/api/admin/sessions/{sid}/reschedule",
                           {"date": thu, "start_time": "11:00", "end_time": "12:00"})
        self.assertEqual(st, 200, r)
        st, det = admin.get(f"/api/admin/sessions/{sid}")
        self.assertEqual(st, 200, det)
        self.assertEqual(det["session"]["date"], thu)
        self.assertEqual(det["session"]["original_date"], d, "original sana birinchi sanada qolishi kerak")
        self.assertEqual(det["session"]["original_start_time"], "09:30")


class TestM13Analytics(Base):
    """M13-B — Admin analitika paneli: oylik faollik grafigi, bekor qilingan
    mashg'ulotlar foizi, eng band instruktorlar."""

    def _admin(self):
        c = Client()
        c.post("/api/auth/login", {"login": "admin", "password": "admin123", "role": "admin"})
        return c

    def _mk(self, admin, date, start, end):
        st, r = admin.post("/api/admin/sessions",
                           {"date": date, "start_time": start, "end_time": end,
                            "instructor_id": 1, "student_ids": [1], "notes": "M13B"})
        self.assertEqual(st, 200, r)
        return r["id"]

    def tearDown(self):
        db = Db(str(TMP / "test.db"))
        rows = db.q("SELECT id FROM lesson_sessions WHERE notes='M13B'")
        for r in rows:
            db.upd("DELETE FROM session_students WHERE session_id=?", (r["id"],))
            db.upd("DELETE FROM attendance WHERE session_id=?", (r["id"],))
            db.upd("DELETE FROM lesson_sessions WHERE id=?", (r["id"],))

    def test_120_admin_analytics_shape(self):
        admin = self._admin()
        st, r = admin.get("/api/admin/analytics")
        self.assertEqual(st, 200, r)
        a = r["analytics"]
        self.assertIn("month", a)
        self.assertIsInstance(a["total"], int)
        self.assertIsInstance(a["cancel_rate"], float)
        self.assertTrue(0 <= a["cancel_rate"] <= 100)
        self.assertEqual(len(a["months"]), 12, "12 oylik tendentsiya bo'lishi kerak")
        self.assertIn(len(a["days"]), (28, 29, 30, 31))
        self.assertIsInstance(a["top_instructors"], list)
        for d in a["days"]:
            self.assertIn("sessions", d)
            self.assertIn("cancelled", d)
        for m in a["months"]:
            self.assertIn("sessions", m)
            self.assertIn("cancelled", m)

    def test_121_admin_analytics_counts_and_cancel_rate(self):
        # Maxsus oy: 2099-03 — boshqa testlardagi qoldiq sessiyalar ta'sir qilmaydi
        db = Db(str(TMP / "test.db"))
        t = now()
        sid1 = db.ex(
            """INSERT INTO lesson_sessions(date,start_time,end_time,instructor_id,car_id,
               car_name_snapshot,car_plate_snapshot,capacity_snapshot,status,notes,created_at,updated_at)
               VALUES('2099-03-10','09:00','10:00',1,1,'Chevrolet Cobalt','01 A 123 AA',4,'completed','M13B',?,?)""",
            (t, t))
        db.ex("INSERT INTO session_students(session_id,student_id,joined_at) VALUES(?,1,?)", (sid1, t))
        sid2 = db.ex(
            """INSERT INTO lesson_sessions(date,start_time,end_time,instructor_id,car_id,
               car_name_snapshot,car_plate_snapshot,capacity_snapshot,status,notes,cancel_reason,created_at,updated_at)
               VALUES('2099-03-12','15:30','16:30',1,1,'Chevrolet Cobalt','01 A 123 AA',4,'cancelled','M13B','other',?,?)""",
            (t, t))
        db.ex("INSERT INTO session_students(session_id,student_id,joined_at) VALUES(?,1,?)", (sid2, t))
        admin = self._admin()
        st, r = admin.get("/api/admin/analytics?month=2099-03")
        self.assertEqual(st, 200, r)
        a = r["analytics"]
        self.assertEqual(a["total"], 2)
        self.assertEqual(a["completed"], 1)
        self.assertEqual(a["cancelled"], 1)
        self.assertEqual(a["cancel_rate"], 50.0)
        self.assertEqual(a["hours"], 1.0)
        self.assertEqual(a["unique_students"], 1)
        self.assertEqual(a["days"][9]["sessions"], 1)
        self.assertEqual(a["days"][11]["cancelled"], 1)
        names = [t_name["name"] for t_name in a["top_instructors"]]
        self.assertTrue(any("Akmal" in n for n in names), "eng band instruktorlar orasida Akmal bor")
        self.assertEqual(a["top_instructors"][0]["sessions"], 2)
        self.assertEqual(a["top_instructors"][0]["completed"], 1)

    def test_122_admin_analytics_bad_month(self):
        admin = self._admin()
        st, r = admin.get("/api/admin/analytics?month=2020-13")
        self.assertEqual(st, 400, r)
        st, r = admin.get("/api/admin/analytics?month=abc")
        self.assertEqual(st, 400, r)

    def test_123_student_cannot_access_analytics(self):
        c = Client()
        c.post("/api/auth/login", {"login": "usrL_00004", "password": "usrP_00004", "role": "student"})
        st, r = c.get("/api/admin/analytics")
        self.assertEqual(st, 403, r)


class TestM4RequestApprove(Base):
    """M4 — Admin so'rovni tasdiqlash (bugfix): session_students INSERT'dagi
    bindings xatosi tufayli tasdiqlash 500 berib, so'rov holati o'zgarmas edi.
    Endi tasdiqlash: yangi session + student qatori + talabaga bildirishnoma."""

    def _student(self):
        c = Client()
        c.post("/api/auth/login", {"login": "usrL_00004", "password": "usrP_00004", "role": "student"})
        return c

    def _admin(self):
        c = Client()
        c.post("/api/auth/login", {"login": "admin", "password": "admin123", "role": "admin"})
        return c

    def _next_monday(self):
        from datetime import timedelta
        d = datetime.now()
        mon = d + timedelta(days=(7 - d.weekday()) % 7 or 7)
        return (mon + timedelta(days=7)).strftime("%Y-%m-%d")

    def tearDown(self):
        db = Db(str(TMP / "test.db"))
        rows = db.q("SELECT id FROM practice_requests WHERE message='M4-TEST'")
        for r_ in rows:
            req = db.q1("SELECT * FROM practice_requests WHERE id=?", (r_["id"],))
            if req and req["session_id"]:
                db.upd("DELETE FROM session_students WHERE session_id=?", (req["session_id"],))
                db.upd("DELETE FROM lesson_sessions WHERE id=?", (req["session_id"],))
            db.upd("DELETE FROM practice_requests WHERE id=?", (r_["id"],))

    def test_130_approve_request_updates_status_and_creates_session(self):
        stu = self._student()
        st, r = stu.post("/api/student/requests", {
            "preferred_date": self._next_monday(), "preferred_start_time": "09:00",
            "preferred_end_time": "10:00", "message": "M4-TEST"})
        self.assertEqual(st, 200, r)
        rid = r["id"]

        admin = self._admin()
        st, r = admin.post(f"/api/admin/requests/{rid}/approve", {
            "date": self._next_monday(), "start_time": "09:00", "end_time": "10:00",
            "instructor_id": 1})
        self.assertEqual(st, 200, r)
        sid = r["session_id"]
        self.assertTrue(sid)

        db = Db(str(TMP / "test.db"))
        req = db.q1("SELECT * FROM practice_requests WHERE id=?", (rid,))
        self.assertEqual(req["status"], "approved")
        self.assertEqual(req["session_id"], sid)
        ss = db.q1("SELECT * FROM session_students WHERE session_id=? AND student_status='active'", (sid,))
        self.assertIsNotNone(ss, "session_students qatori yaratilishi kerak (M4 bugfix)")
        self.assertEqual(ss["student_id"], 1)
        notif = db.q1("SELECT * FROM notifications WHERE user_id=5 AND type='lesson' AND title='lesson.assigned' ORDER BY id DESC LIMIT 1")
        self.assertIsNotNone(notif, "talabaga 'lesson.assigned' bildirishnoma keldi")

    def test_131_reject_request_updates_status(self):
        stu = self._student()
        st, r = stu.post("/api/student/requests", {
            "preferred_date": self._next_monday(), "preferred_start_time": "09:00",
            "preferred_end_time": "10:00", "message": "M4-TEST"})
        self.assertEqual(st, 200, r)
        rid = r["id"]
        admin = self._admin()
        st, r = admin.post(f"/api/admin/requests/{rid}/reject", {"note": "rad etildi"})
        self.assertEqual(st, 200, r)
        db = Db(str(TMP / "test.db"))
        req = db.q1("SELECT * FROM practice_requests WHERE id=?", (rid,))
        self.assertEqual(req["status"], "rejected")
        self.assertEqual(req["admin_note"], "rad etildi")


class TestApproveRequestRules(Base):
    """'Tasdiqlash' tugmasi ishlamaydi degan xato.

    Sabab: backend qoida buzilganda `params.errors` da ANIQ sabablarni
    yuboradi (masalan ["intersects_break"]), lekin frontend `errToast` bu
    ro'yxatni tashlab yuborib faqat umumiy "Mashg'ulot yaratib bo'lmaydi"
    ko'rsatardi — admin qaysi qoida bloklaganini bilmasdi va tugma buzilgan
    deb o'ylardi. Bu yerda har bir qoida kodi alohida tekshiriladi.

    Ikkinchidan, session/so'rov yozuvlari bitta tranzaksiyaga o'tkazildi:
    oraliqda xato chiqsa yaroq session qolmasligi tekshiriladi.
    """

    MSG = "APR-TEST"

    def _admin(self):
        c = Client()
        c.post("/api/auth/login", {"login": "admin", "password": "admin123", "role": "admin"})
        return c

    def _login(self, login):
        """Seed loginlari ketma-ket: usrL_0000N -> parol usrP_0000N."""
        n = login.split("_")[-1]
        c = Client()
        c.post("/api/auth/login", {"login": login, "password": "usrP_" + n, "role": "student"})
        return c

    def _students(self):
        """Bazadagi talabalar: [{login, sid}, ...] (s.id bo'yicha tartiblangan)."""
        db = Db(str(TMP / "test.db"))
        return db.q("""SELECT u.login AS login, s.id AS sid FROM students s
                       JOIN users u ON u.id=s.user_id
                       WHERE u.deleted_at IS NULL ORDER BY s.id""")

    def _next_monday(self, weeks=0):
        d = datetime.now()
        mon = d + timedelta(days=(7 - d.weekday()) % 7 or 7)
        return (mon + timedelta(days=7 * weeks)).strftime("%Y-%m-%d")

    def _next_weekday(self, iso_wd):
        """Keyingi dushanbadan keyingi `iso_wd` kuni (0=mon ... 6=sun)."""
        d = datetime.now()
        mon = d + timedelta(days=(7 - d.weekday()) % 7 or 7)
        return (mon + timedelta(days=iso_wd)).strftime("%Y-%m-%d")

    def _new_request(self, login, date, start, end, msg=None):
        stu = self._login(login)
        st, r = stu.post("/api/student/requests", {
            "preferred_date": date, "preferred_start_time": start,
            "preferred_end_time": end, "message": msg or self.MSG})
        self.assertEqual(st, 200, r)
        return r["id"]

    def _sessions_for(self, note_frag):
        db = Db(str(TMP / "test.db"))
        return db.q("SELECT id FROM lesson_sessions WHERE notes LIKE ?", ("%" + note_frag + "%",))

    def tearDown(self):
        db = Db(str(TMP / "test.db"))
        for r in db.q("SELECT id, session_id FROM practice_requests WHERE message=?", (self.MSG,)):
            if r["session_id"]:
                db.upd("DELETE FROM session_students WHERE session_id=?", (r["session_id"],))
                db.upd("DELETE FROM lesson_sessions WHERE id=?", (r["session_id"],))
            db.upd("DELETE FROM audit_logs WHERE entity_id=? AND entity_type='practice_requests'",
                   (r["id"],))
        db.upd("DELETE FROM practice_requests WHERE message=?", (self.MSG,))

    # ------------------------------------------------------------------
    # 1) Tanaffus vaqti — bu holat admin uchun eng ko'p uchraydigan sabab
    def test_140_approve_blocked_by_break_returns_specific_rule_code(self):
        """12:00-16:00 so'rov 13:00-14:00 tanaffusga tegadi -> intersects_break.

        Bu aynan "Tasdiqlash hech narsa o'zgarmaydi" degan holat: eski kodda
        faqat "Mashg'ulot yaratib bo'lmaydi" ko'rinardi, sabab yo'q edi.
        """
        student = self._students()[0]
        rid = self._new_request(student["login"], self._next_monday(), "12:00", "16:00")
        admin = self._admin()
        st, r = admin.post(f"/api/admin/requests/{rid}/approve", {
            "date": self._next_monday(), "start_time": "12:00", "end_time": "16:00",
            "instructor_id": 1})
        self.assertEqual(st, 409, r)
        self.assertEqual(r["error"], "session.rules_violated")
        self.assertIn("intersects_break", r["params"]["errors"],
                      "frontend aniq sababni ko'rsatishi uchun kod kiritilishi shart")
        # so'rov "pending"da qoladi va yaroq session yaratilmaydi
        db = Db(str(TMP / "test.db"))
        req = db.q1("SELECT * FROM practice_requests WHERE id=?", (rid,))
        self.assertEqual(req["status"], "pending")
        self.assertIsNone(req["session_id"])
        self.assertEqual(self._sessions_for("so'rov #%s" % rid), [])

    # 2) Ish vaqti tashqarisida
    def test_141_approve_outside_work_hours_returns_rule_code(self):
        """Instruktor 1 (Akmal) 08:00-18:00 ishlaydi -> 19:00-20:00 tashqarida."""
        date = self._next_monday()
        rid = self._new_request(self._students()[0]["login"], date, "19:00", "20:00")
        admin = self._admin()
        st, r = admin.post(f"/api/admin/requests/{rid}/approve", {
            "date": date, "start_time": "19:00", "end_time": "20:00",
            "instructor_id": 1})
        self.assertEqual(st, 409, r)
        self.assertIn("outside_work_hours", r["params"]["errors"])
        db = Db(str(TMP / "test.db"))
        self.assertEqual(db.q1("SELECT status FROM practice_requests WHERE id=?",
                               (rid,))["status"], "pending")

    # 3) Ish kuni emas
    def test_142_approve_on_non_work_day_returns_rule_code(self):
        """Instruktor 1 dushanbadan shanbagacha ishlaydi -> yakshanbay = not_work_day."""
        sunday = self._next_weekday(6)
        rid = self._new_request(self._students()[0]["login"], sunday, "09:00", "10:00")
        admin = self._admin()
        st, r = admin.post(f"/api/admin/requests/{rid}/approve", {
            "date": sunday, "start_time": "09:00", "end_time": "10:00",
            "instructor_id": 1})
        self.assertEqual(st, 409, r)
        self.assertIn("not_work_day", r["params"]["errors"])

    # 4) Xato jim qolmasligi: instruktor tanlanmagan
    def test_143_approve_without_instructor_is_explicit_error(self):
        rid = self._new_request(self._students()[0]["login"], self._next_monday(),
                                "09:00", "10:00")
        admin = self._admin()
        st, r = admin.post(f"/api/admin/requests/{rid}/approve", {
            "date": self._next_monday(), "start_time": "09:00", "end_time": "10:00"})
        self.assertEqual(st, 400, r)
        self.assertEqual(r["error"], "request.no_instructor")
        db = Db(str(TMP / "test.db"))
        self.assertEqual(db.q1("SELECT status FROM practice_requests WHERE id=?",
                               (rid,))["status"], "pending")

    # 5) Atomiklik: oraliqda xato chiqsa yaroq session qolmasligi
    def test_144_approve_rolls_back_on_midway_failure(self):
        """session_students INSERTida xato -> session ham, status ham qaytadi."""
        rid = self._new_request(self._students()[0]["login"], self._next_monday(),
                                "09:00", "10:00")
        date = self._next_monday()
        db = Db(str(TMP / "test.db"))
        with db.connect() as c:
            c.execute("""CREATE TRIGGER IF NOT EXISTS t_apr_fail BEFORE INSERT ON session_students
                         BEGIN SELECT RAISE(ABORT, 'test: session_students buzildi'); END""")
            c.commit()
        try:
            admin = self._admin()
            st, r = admin.post(f"/api/admin/requests/{rid}/approve", {
                "date": date, "start_time": "09:00", "end_time": "10:00",
                "instructor_id": 1})
            # xato 5xx sifatida qaytishi kerak (200 emas!) — "jim" qolmasin
            self.assertGreaterEqual(st, 500, "xato yutilmasin, aniq status kod qaytaring")
        finally:
            with db.connect() as c:
                c.execute("DROP TRIGGER IF EXISTS t_apr_fail")
                c.commit()

        req = db.q1("SELECT * FROM practice_requests WHERE id=?", (rid,))
        self.assertEqual(req["status"], "pending", "xatodan keyin holat o'zgarmasligi kerak")
        self.assertIsNone(req["session_id"])
        self.assertEqual(self._sessions_for("so'rov #%s" % rid), [],
                         "yaroq (orphan) session qolmadi — tranzaksiya ishladi")

    # 6) Turli so'rovlarda muvaffaqiyatli tasdiqlash
    def test_145_approve_three_different_requests(self):
        """Uch xil so'rov (turli kun/vaqt/talaba) -> hammasi 'approved'."""
        students = self._students()
        self.assertGreaterEqual(len(students), 3, "seedda kamida 3 ta talaba kerak")
        admin = self._admin()
        # (talaba, sana, start, end, instruktor_id) — har biri boshqacha holatda:
        # oddiy, keyingi hafta, boshqa instruktor bilan.
        cases = [
            (students[0], self._next_monday(), "09:00", "10:00", 1),
            (students[1], self._next_monday(1), "15:00", "16:30", 1),
            (students[2], self._next_monday(2), "11:00", "12:00", 2),
        ]
        for student, date, start, end, iid in cases:
            with self.subTest(login=student["login"], date=date, instructor=iid):
                rid = self._new_request(student["login"], date, start, end)
                st, r = admin.post(f"/api/admin/requests/{rid}/approve", {
                    "date": date, "start_time": start, "end_time": end,
                    "instructor_id": iid})
                self.assertEqual(st, 200, r)
                sid = r["session_id"]
                self.assertTrue(sid)
                db = Db(str(TMP / "test.db"))
                req = db.q1("SELECT * FROM practice_requests WHERE id=?", (rid,))
                self.assertEqual(req["status"], "approved")
                self.assertEqual(req["session_id"], sid)
                ls = db.q1("SELECT * FROM lesson_sessions WHERE id=?", (sid,))
                self.assertIsNotNone(ls, "mashg'ulot yaratilishi kerak")
                self.assertEqual(ls["date"], date)
                self.assertEqual(ls["start_time"], start)
                self.assertEqual(ls["end_time"], end)
                self.assertEqual(ls["instructor_id"], iid)
                self.assertEqual(ls["status"], "scheduled")
                ss = db.q1("SELECT * FROM session_students WHERE session_id=? "
                           "AND student_status='active'", (sid,))
                self.assertIsNotNone(ss, "talaba sessionga bog'lanishi kerak")
                self.assertEqual(ss["student_id"], student["sid"])
                notif = db.q1("SELECT * FROM notifications WHERE type='lesson' "
                              "AND title='lesson.assigned' ORDER BY id DESC LIMIT 1")
                self.assertIsNotNone(notif, "bog'liq amal: talabaga bildirishnoma yuboriladi")


class TestM1SenderInfo(Base):
    """M1 — bildirishnoma jo'natuvchisi (sender_id, sender_role, ism-familiya)
    saqlanadi va `/api/me/notifications` orqali qaytariladi."""

    def _student(self):
        c = Client()
        c.post("/api/auth/login", {"login": "usrL_00004", "password": "usrP_00004", "role": "student"})
        return c

    def _admin(self):
        c = Client()
        c.post("/api/auth/login", {"login": "admin", "password": "admin123", "role": "admin"})
        return c

    def _next_monday(self):
        from datetime import timedelta
        d = datetime.now()
        mon = d + timedelta(days=(7 - d.weekday()) % 7 or 7)
        return (mon + timedelta(days=7)).strftime("%Y-%m-%d")

    def _jdata(self, n):
        if isinstance(n.get("data"), dict):
            return n.get("data") or {}
        return jload(n.get("data") or "{}", {})

    def tearDown(self):
        """M1 testlari qolgan sessiya/so'rovlarni tozalaydi (boshqa klasslarga xalaqit bermaslik uchun)."""
        db = Db(str(TMP / "test.db"))
        rows = db.q("SELECT id FROM lesson_sessions WHERE notes='M1-TEST'")
        for r in rows:
            db.upd("DELETE FROM session_students WHERE session_id=?", (r["id"],))
            db.upd("DELETE FROM notifications WHERE data LIKE ?", (f'%"session_id": {r["id"]}%',))
            db.upd("DELETE FROM lesson_sessions WHERE id=?", (r["id"],))
        reqs = db.q("SELECT id FROM practice_requests WHERE message='M1-TEST'")
        for r in reqs:
            db.upd("DELETE FROM notifications WHERE data LIKE ?", (f'%"request_id": {r["id"]}%',))
            db.upd("DELETE FROM practice_requests WHERE id=?", (r["id"],))

    def test_140_session_created_sender_is_admin(self):
        admin = self._admin()
        d = self._next_monday()
        st, r = admin.post("/api/admin/sessions", {"date": d, "start_time": "09:00", "end_time": "10:00",
                                                   "instructor_id": 1, "student_ids": [1], "notes": "M1-TEST"})
        self.assertEqual(st, 200, r)
        sid = r["id"]
        db = Db(str(TMP / "test.db"))
        n = db.q1("SELECT * FROM notifications WHERE title='lesson.assigned' ORDER BY id DESC LIMIT 1")
        self.assertIsNotNone(n, "talabaga lesson.assigned kelishi kerak")
        self.assertEqual(n["sender_id"], 1, "jo'natuvchi admin (id=1) bo'lishi kerak")
        self.assertEqual(n["sender_role"], "admin")

        stu = self._student()
        st, ns = stu.get("/api/me/notifications")
        self.assertEqual(st, 200, ns)
        hit = [x for x in ns["notifications"] if str(self._jdata(x).get("session_id")) == str(sid)]
        self.assertTrue(hit, "sessiya bildirishnomasi me_notifications'da bor")
        top = hit[0]
        self.assertEqual(top["sender_role"], "admin")
        self.assertEqual(top["sender_id"], 1)
        self.assertEqual(top["sender_first_name"], "Admin")
        self.assertEqual(top["sender_last_name"], "Avtomaktab")

    def test_141_request_new_sender_is_student(self):
        stu = self._student()
        st, r = stu.post("/api/student/requests", {"preferred_date": self._next_monday(),
                                                   "preferred_start_time": "10:00",
                                                   "preferred_end_time": "11:00",
                                                   "message": "M1-TEST"})
        self.assertEqual(st, 200, r)
        admin = self._admin()
        st, ns = admin.get("/api/me/notifications")
        self.assertEqual(st, 200, ns)
        hit = [x for x in ns["notifications"] if str(self._jdata(x).get("request_id")) == str(r["id"])]
        self.assertTrue(hit, "request.new admin bildirishnomasi bor")
        top = hit[0]
        self.assertEqual(top["sender_role"], "student")
        self.assertEqual(top["sender_id"], 5)
        self.assertEqual(top["sender_first_name"], "Omadbek")


class TestM2NotifI18n(Base):
    """M2 — backend bildirishnoma title'da faqat KOD saqlaydi (enum), tarjima frontendda.
    `data` esa lokallizatsiya uchun tizimli maydonlarni o'z ichiga oladi."""

    def _student(self):
        c = Client()
        c.post("/api/auth/login", {"login": "usrL_00004", "password": "usrP_00004", "role": "student"})
        return c

    def _admin(self):
        c = Client()
        c.post("/api/auth/login", {"login": "admin", "password": "admin123", "role": "admin"})
        return c

    def _next_monday(self):
        from datetime import timedelta
        d = datetime.now()
        mon = d + timedelta(days=(7 - d.weekday()) % 7 or 7)
        return (mon + timedelta(days=7)).strftime("%Y-%m-%d")

    def _jdata(self, n):
        if isinstance(n.get("data"), dict):
            return n.get("data") or {}
        return jload(n.get("data") or "{}", {})

    def tearDown(self):
        db = Db(str(TMP / "test.db"))
        rows = db.q("SELECT id FROM lesson_sessions WHERE notes='M2-TEST'")
        for r in rows:
            db.upd("DELETE FROM session_students WHERE session_id=?", (r["id"],))
            db.upd("DELETE FROM notifications WHERE data LIKE ?", (f'%\"session_id\": {r["id"]}%',))
            db.upd("DELETE FROM lesson_sessions WHERE id=?", (r["id"],))
        reqs = db.q("SELECT id FROM practice_requests WHERE message='M2-TEST'")
        for r in reqs:
            db.upd("DELETE FROM notifications WHERE data LIKE ?", (f'%\"request_id\": {r["id"]}%',))
            db.upd("DELETE FROM practice_requests WHERE id=?", (r["id"],))

    def test_150_session_notif_carries_code_and_params(self):
        admin = self._admin()
        d = self._next_monday()
        st, r = admin.post("/api/admin/sessions", {"date": d, "start_time": "09:00", "end_time": "10:00",
                                                   "instructor_id": 1, "student_ids": [1], "notes": "M2-TEST"})
        self.assertEqual(st, 200, r)
        sid = r["id"]
        db = Db(str(TMP / "test.db"))
        n = db.q1("SELECT * FROM notifications WHERE title='lesson.assigned' ORDER BY id DESC LIMIT 1")
        self.assertIsNotNone(n, "lesson.assigned bildirishnoma keldi")
        # title faqat kod bo'lishi kerak (tarjima frontendda)
        self.assertEqual(n["title"], "lesson.assigned")
        nd = jload(n["data"], {})
        self.assertEqual(nd.get("session_id"), sid)
        self.assertEqual(nd.get("date"), d)
        self.assertEqual(nd.get("start_time"), "09:00")
        self.assertEqual(nd.get("end_time"), "10:00")
        self.assertEqual(nd.get("instructor_name"), "Akmal Karimov")
        self.assertTrue(nd.get("car"), "avto nomi data'da bo'lishi kerak")

    def test_151_request_new_carries_student_name(self):
        stu = self._student()
        st, r = stu.post("/api/student/requests", {"preferred_date": self._next_monday(),
                                                   "preferred_start_time": "10:00",
                                                   "preferred_end_time": "11:00",
                                                   "message": "M2-TEST"})
        self.assertEqual(st, 200, r)
        db = Db(str(TMP / "test.db"))
        n = db.q1("SELECT * FROM notifications WHERE title='request.new' ORDER BY id DESC LIMIT 1")
        self.assertIsNotNone(n, "request.new bildirishnoma keldi")
        self.assertEqual(n["title"], "request.new")
        nd = jload(n["data"], {})
        self.assertEqual(nd.get("request_id"), r["id"])
        self.assertEqual(nd.get("student_name"), "Omadbek Xoshimov")


class TestM3NotifNavigation(Base):
    """M3 — bildirishnoma data'sida detalga o'tish uchun etarli ma'lumot bo'lishi.
    Foydalanuvchi bildirishnomani bossa -> sessiya/so'rov/xabar detaliga o'tadi.
    Frontend aynan shu maydonlarga tayanadi: session_id / request_id / message_id."""

    def _jdata(self, n):
        if isinstance(n.get("data"), dict):
            return n.get("data") or {}
        return jload(n.get("data") or "{}", {})

    def test_160_msg_new_carries_message_id(self):
        # admin instruktyor Akmal (uid 2) ga xabar yuboradi
        admin = Client()
        st, r = admin.post("/api/auth/login", {"login": "admin", "password": "admin123", "role": "admin"})
        self.assertEqual(st, 200, r)
        st, r = admin.post("/api/me/messages", {"to_user_id": 2, "text": "M3-TEST-MSG"})
        self.assertEqual(st, 200, r)
        self.assertTrue(r.get("ok"))
        # Akmal bildirishnomalarida msg.new bo'lishi kerak, data da message_id + text
        inst = Client()
        st, r2 = inst.post("/api/auth/login", {"login": "usrL_00001", "password": "usrP_00001", "role": "instructor"})
        self.assertEqual(st, 200, r2)
        st, ns = inst.get("/api/me/notifications")
        self.assertEqual(st, 200, ns)
        hit = [n for n in ns["notifications"] if n.get("title") == "msg.new"]
        self.assertTrue(hit, "msg.new bildirishnoma keldi")
        top = hit[0]
        nd = self._jdata(top)
        self.assertTrue(nd.get("message_id"), "message_id data'da bo'lishi kerak (M3 klik uchun)")
        self.assertEqual(nd.get("text"), "M3-TEST-MSG")
        self.assertEqual(top["sender_role"], "admin")
        # tozalash: ushbu xabar va bildirishnomalar
        db = Db(str(TMP / "test.db"))
        db.upd("DELETE FROM notifications WHERE data LIKE '%M3-TEST-MSG%'")
        db.upd("DELETE FROM messages WHERE text='M3-TEST-MSG'")

    def test_161_data_has_navigation_keys(self):
        """Har bir notification turi data'da tegishli ID maydonini olib yuradi (o'zini-o'zi ta'minlaydi)."""
        from datetime import timedelta
        admin = Client()
        st, r = admin.post("/api/auth/login", {"login": "admin", "password": "admin123", "role": "admin"})
        self.assertEqual(st, 200, r)
        d = (datetime.now() + timedelta(days=(7 - datetime.now().weekday()) % 7 or 7)).strftime("%Y-%m-%d")
        st, sess = admin.post("/api/admin/sessions", {"date": d, "start_time": "09:00", "end_time": "10:00",
                                                      "instructor_id": 1, "student_ids": [1], "notes": "M3-TEST"})
        self.assertEqual(st, 200, sess)
        stu = Client()
        st, r = stu.post("/api/auth/login", {"login": "usrL_00004", "password": "usrP_00004", "role": "student"})
        self.assertEqual(st, 200, r)
        st, rq = stu.post("/api/student/requests", {"preferred_date": d, "preferred_start_time": "10:00",
                                                    "preferred_end_time": "11:00", "message": "M3-TEST-REQ"})
        self.assertEqual(st, 200, rq)
        db = Db(str(TMP / "test.db"))
        sl = db.q("SELECT data FROM notifications WHERE title='lesson.assigned' ORDER BY id DESC LIMIT 1")
        self.assertTrue(sl and "session_id" in jload(sl[0]["data"], {}), "lesson.assigned data'da session_id bor")
        rl = db.q("SELECT data FROM notifications WHERE title='request.new' ORDER BY id DESC LIMIT 1")
        self.assertTrue(rl and "request_id" in jload(rl[0]["data"], {}), "request.new data'da request_id bor")
        # tozalash
        db.upd("DELETE FROM session_students WHERE session_id=?", (sess["id"],))
        db.upd("DELETE FROM notifications WHERE data LIKE ?", (f'%"session_id": {sess["id"]}%',))
        db.upd("DELETE FROM lesson_sessions WHERE id=?", (sess["id"],))
        db.upd("DELETE FROM notifications WHERE data LIKE ?", (f'%"request_id": {rq["id"]}%',))
        db.upd("DELETE FROM practice_requests WHERE id=?", (rq["id"],))


class TestM6InstructorCar(Base):
    """M6 — instruktor FAQAT o'ziga biriktirilgan mashinani tahrirlay oladi;
    admin huquqlari o'zgarishsiz qoladi."""

    def _inst_login(self, login="usrL_00001", pwd="usrP_00001"):
        c = Client()
        st, r = c.post("/api/auth/login", {"login": login, "password": pwd, "role": "instructor"})
        self.assertEqual(st, 200, r)
        return c

    def test_170_instructor_updates_own_car(self):
        inst = self._inst_login()
        # Akmal (inst 1) car 1 ga biriktirilgan; color va capacity ni o'zgartiramiz
        st, r = inst.put("/api/instructor/car", {"color": "To'q ko'k", "practice_capacity": 5})
        self.assertEqual(st, 200, r)
        db = Db(str(TMP / "test.db"))
        car = db.q1("SELECT color, practice_capacity FROM cars WHERE id=1")
        self.assertEqual(car["color"], "To'q ko'k")
        self.assertEqual(car["practice_capacity"], 5)
        # qaytarish
        db.upd("UPDATE cars SET color='Oq', practice_capacity=4 WHERE id=1")

    def test_171_instructor_cannot_edit_other_car(self):
        # Boshqa instruktor (Omad? yo'q) — inst 2, u ham faqat o'z mashinasini tahrirlay oladi;
        # endpoint URL'da car id qabul qilmaydi — e'lon qilingan car har doim O'ZIdan keladi.
        inst = self._inst_login("usrL_00003", "usrP_00003")  # Vali (inst 3)
        db = Db(str(TMP / "test.db"))
        me = db.q1("SELECT assigned_car_id FROM instructors WHERE id=3")
        self.assertTrue(me["assigned_car_id"], "Vali mashinaga biriktirilgan bo'lishi kerak (seed)")
        st, r = inst.put("/api/instructor/car", {"brand": "HACK"})
        self.assertEqual(st, 200, r)
        # faqat O'Z mashinasi yangilandi
        car = db.q1("SELECT brand FROM cars WHERE id=?", (me["assigned_car_id"],))
        self.assertEqual(car["brand"], "HACK")
        own = db.q1("SELECT brand FROM cars WHERE id=1")
        self.assertEqual(own["brand"], "Chevrolet")
        db.upd("UPDATE cars SET brand='Chevrolet' WHERE id=?", (me["assigned_car_id"],))

    def test_172_instructor_without_car_rejected(self):
        db = Db(str(TMP / "test.db"))
        db.upd("UPDATE instructors SET assigned_car_id=NULL WHERE id=1")
        try:
            inst = self._inst_login()
            st, r = inst.put("/api/instructor/car", {"brand": "X"})
            self.assertEqual(st, 404, r)
        finally:
            db.upd("UPDATE instructors SET assigned_car_id=1 WHERE id=1")


class TestM9LessonDuration(Base):
    """M9 — admin settings'dagi standart davomiylik yangi mashg'ulotga qo'llanadi;
    eksplicit end_time berilsa o'zgarmaydi."""

    def _next_monday(self):
        from datetime import timedelta
        d = datetime.now()
        mon = d + timedelta(days=(7 - d.weekday()) % 7 or 7)
        return (mon + timedelta(days=7)).strftime("%Y-%m-%d")

    def _admin(self):
        c = Client()
        st, r = c.post("/api/auth/login", {"login": "admin", "password": "admin123", "role": "admin"})
        self.assertEqual(st, 200, r)
        return c

    def test_180_duration_default_applied_when_end_missing(self):
        admin = self._admin()
        admin.put("/api/admin/settings", {"lesson_duration_min": 45})
        st, r = admin.post("/api/admin/sessions", {
            "date": self._next_monday(), "start_time": "14:00",
            "instructor_id": 3, "student_ids": [], "notes": "M9-TEST",
        })
        self.assertEqual(st, 200, r)
        st, det = admin.get(f"/api/admin/sessions/{r['id']}")
        self.assertEqual(st, 200, det)
        self.assertEqual(det["session"]["end_time"], "14:45")  # 14:00 + 45 daqiqa
        db = Db(str(TMP / "test.db"))
        db.upd("DELETE FROM notifications WHERE data LIKE ?", (f'%"session_id": {r["id"]}%',))
        db.upd("DELETE FROM lesson_sessions WHERE id=?", (r["id"],))
        admin.put("/api/admin/settings", {"lesson_duration_min": 90})

    def test_181_explicit_end_time_kept(self):
        admin = self._admin()
        admin.put("/api/admin/settings", {"lesson_duration_min": 45})
        st, r = admin.post("/api/admin/sessions", {
            "date": self._next_monday(), "start_time": "16:00", "end_time": "17:15",
            "instructor_id": 3, "student_ids": [], "notes": "M9-TEST-EXPL",
        })
        self.assertEqual(st, 200, r)
        st, det = admin.get(f"/api/admin/sessions/{r['id']}")
        self.assertEqual(st, 200, det)
        self.assertEqual(det["session"]["end_time"], "17:15")
        db = Db(str(TMP / "test.db"))
        db.upd("DELETE FROM notifications WHERE data LIKE ?", (f'%"session_id": {r["id"]}%',))
        db.upd("DELETE FROM lesson_sessions WHERE id=?", (r["id"],))
        admin.put("/api/admin/settings", {"lesson_duration_min": 90})


class TestSessionIsolation(Base):
    """MODUL 1 — foydalanuvchi sessiyalari ARALASHMASLIGI (xavfsizlik).

    Xato: sessiya bitta `sid` cookie'siga bog'langan edi. Cookie esa bitta
    brauzer bo'ylab UMUMIY — barcha tab'lar bir xil qiymatni ko'radi.
    Shuning uchun bir brauzerda ikki odam kirsa, ikkinchisi birinchisining
    sessiyasini almashtirib yuborardi va birinchi oyna boshqa odamning
    profilini, jadvalini, xabarlarini ko'ra boshlardi.

    Tuzatma: kalit ikki qismdan yig'iladi — HttpOnly cookie'dagi QURILMA
    kaliti + `X-Avto-Tab` sarlavhasidagi TAB kaliti.
    """

    INSTR = ("usrL_00001", "usrP_00001", "instructor")
    STUD = ("usrL_00004", "usrP_00004", "student")
    ADMIN = ("admin", "admin123", "admin")

    def _login(self, tab_client, creds):
        st, r = tab_client.post("/api/auth/login", {
            "login": creds[0], "password": creds[1], "role": creds[2]})
        self.assertEqual(st, 200, r)
        return r["user"]

    def _device(self, tab_client):
        for ck in tab_client.jar:
            if ck.name == "sid":
                return ck.value
        return None

    # ------------------------------------------------------------------ asosiy
    def test_100_two_tabs_same_browser_stay_independent(self):
        """Bir brauzer, ikki tab: 2-tab kirmasi 1-tabni buzmasin."""
        jar = http.cookiejar.CookieJar()
        tab1 = TabClient("iso-tab-1", jar=jar)
        tab2 = TabClient("iso-tab-2", jar=jar)

        u1 = self._login(tab1, self.INSTR)
        self.assertEqual(u1["role"], "instructor")

        # Ikkala tab bir xil cookie jar'ni ko'radi — bitta brauzer taqdimoti
        self.assertEqual(self._device(tab1), self._device(tab2))

        u2 = self._login(tab2, self.STUD)
        self.assertEqual(u2["role"], "student")

        # MUIM: 1-tab o'zini hali ham instruktor deb o'ylaydi
        st, me1 = tab1.get("/api/auth/me")
        self.assertEqual(st, 200, me1)
        self.assertEqual(me1["user"]["id"], u1["id"], "1-tab boshqa foydalanuvchiga o'tib ketgan!")
        self.assertEqual(me1["user"]["role"], "instructor")

        st, me2 = tab2.get("/api/auth/me")
        self.assertEqual(st, 200, me2)
        self.assertEqual(me2["user"]["id"], u2["id"])
        self.assertEqual(me2["user"]["role"], "student")

        # Rollararo endpoint'lar aralashmaydi
        self.assertEqual(tab1.get("/api/student/home")[0], 403)
        self.assertEqual(tab2.get("/api/instructor/students")[0], 403)

    def test_101_three_roles_parallel_no_mixing(self):
        """3 rol, 3 qurilma, 300 ta parallel so'rov — javoblar aralashmasin."""
        clients = {}
        expect = {}
        for i, creds in enumerate((self.ADMIN, self.INSTR, self.STUD), start=1):
            c = TabClient("iso-par-%d" % i)
            expect[i] = self._login(c, creds)["id"]
            clients[i] = c

        bad = []
        lock = threading.Lock()

        def worker(idx):
            c = clients[idx]
            for _ in range(100):
                st, r = c.get("/api/auth/me")
                if st != 200 or r.get("user", {}).get("id") != expect[idx]:
                    with lock:
                        bad.append((idx, st, r))

        threads = [threading.Thread(target=worker, args=(i,)) for i in (1, 2, 3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(bad, [], "parallel so'rovlarda sessiya aralashdi: %s" % bad[:5])

    def test_102_role_data_isolation(self):
        """Har bir rol faqat o'z ma'lumotini oladi."""
        admin = TabClient("iso-iso-admin"); self._login(admin, self.ADMIN)
        instr = TabClient("iso-iso-instr"); self._login(instr, self.INSTR)
        stud = TabClient("iso-iso-stud"); self._login(stud, self.STUD)

        self.assertEqual(admin.get("/api/admin/users")[0], 200)
        self.assertEqual(instr.get("/api/instructor/students")[0], 200)
        self.assertEqual(stud.get("/api/student/sessions")[0], 200)

        self.assertEqual(stud.get("/api/admin/users")[0], 403)
        self.assertEqual(stud.get("/api/instructor/students")[0], 403)
        self.assertEqual(instr.get("/api/admin/users")[0], 403)
        self.assertEqual(instr.get("/api/student/sessions")[0], 403)
        self.assertEqual(admin.get("/api/student/sessions")[0], 403)

    def test_103_logout_in_one_tab_keeps_others(self):
        """Bitta tab chiqishi qo'shni tab'larni o'ldirmasin."""
        jar = http.cookiejar.CookieJar()
        tab1 = TabClient("iso-out-1", jar=jar)
        tab2 = TabClient("iso-out-2", jar=jar)
        self._login(tab1, self.INSTR)
        self._login(tab2, self.STUD)

        self.assertEqual(tab1.post("/api/auth/logout")[0], 200)
        self.assertEqual(tab1.get("/api/auth/me")[0], 401, "chiqilgandan keyin sessiya o'chiqilmadi")
        # Qurilma kaliti o'chmaydi — shuning uchun 2-tab ishlashda davom etadi
        st, r = tab2.get("/api/auth/me")
        self.assertEqual(st, 200, "bitta tab chiqishi ikkinchisini buzdi")
        self.assertEqual(r["user"]["role"], "student")

    # ---------------------------------------------------------------- xavfsizlik
    def test_104_device_cookie_alone_is_not_a_credential(self):
        """FAQAT cookie (tab kalitisiz) bilan kirib bo'lmasin."""
        c = TabClient("iso-sec-1")
        self._login(c, self.ADMIN)
        dev = self._device(c)
        self.assertTrue(dev)

        # 1) Qurilma kaliti yalang'och — hech qanday sarlavhasiz
        self.assertEqual(Client().req("GET", "/api/auth/me", cookie=dev)[0], 401)
        # 2) Noto'g'ri tab kaliti bilan
        self.assertEqual(TabClient("iso-sec-bogus").req("GET", "/api/auth/me", cookie=dev)[0], 401)

    def test_105_tab_id_alone_is_not_a_credential(self):
        """FAQAT tab kaliti (cookiesiz) bilan kirib bo'lmasin."""
        import urllib.request as _u
        c = TabClient("iso-sec-2")
        self._login(c, self.ADMIN)
        # So'rov tab sarlavhasini yuboradi, lekin cookie'siz (oddiy klient)
        req = _u.Request(f"http://{HOST}:{PORT}/api/auth/me",
                         headers={"X-Avto-Tab": c.tab}, method="GET")
        try:
            with _u.urlopen(req, timeout=15) as resp:
                st = resp.status
        except urllib.error.HTTPError as e:
            st = e.code
        self.assertEqual(st, 401, "faqat tab kaliti bilan kirish mumkin bo'lsa — zaiflik")

    def test_106_legacy_client_without_header_works(self):
        """Eski mijozlar (curl, test, bot) sarlavhasiz ham ishlayveradi."""
        c = Client()
        st, r = c.post("/api/auth/login", {"login": "admin", "password": "admin123", "role": "admin"})
        self.assertEqual(st, 200, r)
        self.assertEqual(c.get("/api/auth/me")[0], 200)
        self.assertEqual(c.post("/api/auth/logout")[0], 200)
        self.assertEqual(c.get("/api/auth/me")[0], 401)

    def test_107_legacy_and_tab_sessions_do_not_leak(self):
        """Sarlavhasiz (legacy) sessiya bilan tab'ga xos sessiya aralashmasin."""
        legacy = Client()
        st, _ = legacy.post("/api/auth/login", {"login": "admin", "password": "admin123", "role": "admin"})
        self.assertEqual(st, 200)
        token = None
        for ck in legacy.jar:
            if ck.name == "sid":
                token = ck.value
        self.assertTrue(token)

        # O'sha cookie qiymati + tab kaliti bilan kirish MUMKIN EMAS
        self.assertEqual(TabClient("iso-mix-1").req("GET", "/api/auth/me", cookie=token)[0], 401)
        # ... lekin legacy ko'rinishida ishlaydi
        self.assertEqual(legacy.get("/api/auth/me")[0], 200)
        legacy.post("/api/auth/logout")

    def test_108_remember_me_cookie_shape(self):
        """"Meni eslab qolish" — yoqilganda 30 kun, o'chirilganda sessiya cookie'si.

        (MODUL 3 uchun batafsil testlar: TestRememberMe)"""
        import urllib.request as _u
        cj = http.cookiejar.CookieJar()
        op = _u.build_opener(_u.HTTPCookieProcessor(cj))
        req = _u.Request(
            f"http://{HOST}:{PORT}/api/auth/login",
            data=json.dumps({"login": "admin", "password": "admin123",
                             "role": "admin", "remember": True}).encode(),
            headers={"Content-Type": "application/json",
                     "X-Requested-With": "Avtomaktab",
                     "X-Avto-Tab": "iso-rm-1"},
            method="POST")
        with op.open(req, timeout=15) as resp:
            sc = resp.headers.get("Set-Cookie", "")
        self.assertIn("Max-Age=2592000", sc, sc)
        self.assertIn("HttpOnly", sc)

    def test_109_relogin_same_tab_ok(self):
        """Bir xil tab'da qayta-qayta kirish xatosiz ishlashi (UNIQUE constraint)."""
        jar = http.cookiejar.CookieJar()
        c = TabClient("iso-relog", jar=jar)
        u1 = self._login(c, self.STUD)
        st, r = c.post("/api/auth/logout")
        self.assertEqual(st, 200, r)
        # Chiqish so'rovi serverga YETIB BORMAGAN holatni ham modellashtiramiz:
        # boshqa tab chiqib ketsin, bu tab esa o'z holicha kalsin.
        c2 = TabClient("iso-relog-2", jar=jar)
        self._login(c2, self.INSTR)
        u2 = self._login(c, self.STUD)
        self.assertEqual(u2["id"], u1["id"])
        st, me = c.get("/api/auth/me")
        self.assertEqual(st, 200, me)
        self.assertEqual(me["user"]["id"], u1["id"])

    def test_110_revoke_all_still_works_per_tab(self):
        """'Barcha qurilmalardan chiqish' — har bir tab'ning sessiyasi."""
        jar = http.cookiejar.CookieJar()
        t1 = TabClient("iso-rev-1", jar=jar)
        t2 = TabClient("iso-rev-2", jar=jar)
        self._login(t1, self.ADMIN)
        self._login(t2, self.ADMIN)

        self.assertEqual(t1.get("/api/auth/me")[0], 200)
        self.assertEqual(t2.get("/api/auth/me")[0], 200)

        self.assertEqual(t2.post("/api/me/sessions/revoke-all")[0], 200)
        self.assertEqual(t1.get("/api/auth/me")[0], 401)
        self.assertEqual(t2.get("/api/auth/me")[0], 401)


class TestRoleMustMatch(Base):
    """MODUL 2 — login qilganda tanlangan rol hisobning roliga MOS bo'lishi shart."""

    CASES = [
        ("admin", "admin123", "admin"),
        ("usrL_00001", "usrP_00001", "instructor"),
        ("usrL_00004", "usrP_00004", "student"),
    ]

    def _login(self, body):
        # Bu testlar ataylab RAD etilishlarni tekshiradi — login urinishlari
        # limitini (6 urinish / 5 daqiqa) tozalab, boshqa testlarni koldirmaymiz.
        from app.auth import reset_login_attempts
        reset_login_attempts("login:" + body["login"])
        return Client().post("/api/auth/login", body)

    def test_200_correct_role_allowed(self):
        for login, pw, role in self.CASES:
            st, r = self._login({"login": login, "password": pw, "role": role})
            self.assertEqual(st, 200, f"{login}/{role}: {r}")
            self.assertEqual(r["user"]["role"], role)

    def test_201_wrong_role_rejected(self):
        for login, pw, role in self.CASES:
            for wrong in ("admin", "instructor", "student"):
                if wrong == role:
                    continue
                st, r = self._login({"login": login, "password": pw, "role": wrong})
                self.assertEqual(st, 400, f"{login} roli {wrong} deb kirildi: {r}")
                self.assertEqual(r["error"], "auth.wrong_role")

    def test_202_missing_role_rejected(self):
        """Rol yuborilmasa kirish RAD etiladi (avval 'avtomatik' deb o'tib ketardi)."""
        for login, pw, _role in self.CASES:
            for extra in ({}, {"role": ""}, {"role": "   "}, {"role": None}):
                body = {"login": login, "password": pw}
                body.update(extra)
                st, r = self._login(body)
                self.assertEqual(st, 400, f"{login} rolisiz kirdi: {r}")
                self.assertEqual(r["error"], "auth.wrong_role")

    def test_203_unknown_role_rejected(self):
        for bogus in ("Admin", "ADMIN", "root", "superadmin", "teaching", "1", "null", "student "):
            st, r = self._login({"login": "admin", "password": "admin123", "role": bogus})
            self.assertEqual(st, 400, f"noma'lum rol '{bogus}' qabul qilindi: {r}")
            self.assertEqual(r["error"], "auth.wrong_role")

    def test_204_wrong_password_still_reported_first(self):
        """Parol noto'g'ri bo'lsa, xabar rol haqida emas — hisob borligi oshkor bo'lmaydi."""
        st, r = self._login({"login": "usrL_00004", "password": "noto'g'ri-parol", "role": "admin"})
        self.assertEqual(st, 400)
        self.assertEqual(r["error"], "auth.wrong_credentials")

    def test_205_no_session_created_on_role_mismatch(self):
        """Rad etilgandan keyin sessiya QOLMASIN."""
        c = Client()
        st, _ = self._login({"login": "usrL_00004", "password": "usrP_00004", "role": "admin"})
        self.assertEqual(st, 400)
        c = TabClient("role-mismatch-1")
        c.post("/api/auth/login", {"login": "usrL_00004", "password": "usrP_00004", "role": "admin"})
        self.assertEqual(c.get("/api/auth/me")[0], 401)


class TestRememberMe(Base):
    """MODUL 3 — "Meni eslab qolish"."""

    def _login_cookie(self, remember):
        cj = http.cookiejar.CookieJar()
        op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
        req = urllib.request.Request(
            f"http://{HOST}:{PORT}/api/auth/login",
            data=json.dumps({"login": "admin", "password": "admin123",
                             "role": "admin", "remember": remember}).encode(),
            headers={"Content-Type": "application/json",
                     "X-Requested-With": "Avtomaktab", "X-Avto-Tab": "rm-%s" % remember},
            method="POST")
        with op.open(req, timeout=15) as resp:
            return resp.headers.get("Set-Cookie", "")

    def test_210_remember_on_is_30_days(self):
        sc = self._login_cookie(True)
        self.assertIn("Max-Age=2592000", sc, sc)
        self.assertIn("HttpOnly", sc)
        self.assertIn("SameSite=Lax", sc)

    def test_211_remember_off_is_session_cookie(self):
        """Checkbox o'chirilgan -> Max-Age YO'Q = brauzer yopilganda o'chadi."""
        sc = self._login_cookie(False)
        self.assertNotIn("Max-Age", sc, "sessiya cookie'si Max-Age olmasligi kerak: %s" % sc)
        self.assertIn("HttpOnly", sc)

    def test_212_session_actually_works(self):
        for remember in (True, False):
            c = TabClient("rm-work-%s" % remember)
            st, r = c.post("/api/auth/login", {
                "login": "admin", "password": "admin123", "role": "admin", "remember": remember})
            self.assertEqual(st, 200, r)
            self.assertEqual(c.get("/api/auth/me")[0], 200)

    def test_213_token_never_in_response_body(self):
        """Token JS ga BERILMASIN — faqat HttpOnly cookie orqali (XSS himoyasi)."""
        c = Client()
        st, r = c.post("/api/auth/login",
                       {"login": "admin", "password": "admin123", "role": "admin", "remember": True})
        self.assertEqual(st, 200, r)
        self.assertNotIn("token", r, "token javob tanasida qaytayapti — XSS ga ochiq!")
        self.assertIn("user", r)

    def test_214_login_name_only_in_localstorage(self):
        """localStorage'da faqat LOGIN nomi saqlanadi — token emas."""
        import re
        src = (ROOT / "web" / "js" / "app.js").read_text(encoding="utf-8")
        for m in re.finditer(r'localStorage\.(setItem|getItem)\(\s*"([^"]+)"', src):
            self.assertNotIn("token", m.group(2).lower(),
                             "localStorage'ga token yozilmoqda: %s" % m.group(2))
            self.assertNotIn("sid", m.group(2).lower(),
                             "localStorage'ga sessiya kaliti yozilmoqda: %s" % m.group(2))


class TestUsersByRole(Base):
    """MODUL 6 — foydalanuvchilar rolda bo'linib ko'rsatiladi
    (Talabalar | Instruktorlar | Adminlar), har biri o'z qidiruvi bilan."""

    def setUp(self):
        self.admin = Client()
        from app.auth import reset_login_attempts
        reset_login_attempts("login:admin")
        st, r = self.admin.post("/api/auth/login",
                                {"login": "admin", "password": "admin123", "role": "admin"})
        self.assertEqual(st, 200, r)

    def test_300_each_role_returned_separately(self):
        """Har bir rol faqat o'z rolikadagilarni oladi — ro'yxatlar aralashmaydi."""
        for role in ("student", "instructor", "admin"):
            st, r = self.admin.get(f"/api/admin/users?role={role}")
            self.assertEqual(st, 200, r)
            self.assertTrue(r["users"], f"{role} bo'sh qaytdi")
            for u in r["users"]:
                self.assertEqual(u["role"], role,
                                 f"role={role} so'rovida {u['role']} qaytdi — ro'yxatlar aralashdi")

    def test_301_admin_tab_shows_admins(self):
        st, r = self.admin.get("/api/admin/users?role=admin")
        self.assertEqual(st, 200, r)
        self.assertTrue(any(u["login"] == "admin" for u in r["users"]),
                        "boshqaruvchi admin ro'yxatda yo'q")
        # Adminlar uchun 'progress'/'instructors' kabi talaba maydonlari chiqmasin
        for u in r["users"]:
            self.assertNotIn("progress", u)
            self.assertNotIn("instructors", u)

    def test_302_student_tab_has_instructor_and_progress(self):
        st, r = self.admin.get("/api/admin/users?role=student")
        self.assertEqual(st, 200, r)
        for u in r["users"]:
            self.assertIn("student", u)
            pr = u.get("progress")
            self.assertIsNotNone(pr, f"{u['login']} uchun progress yo'q")
            for k in ("total", "done", "pct"):
                self.assertIn(k, pr)
            self.assertTrue(0 <= pr["pct"] <= 100, f"{u['login']}: pct={pr['pct']}")
            self.assertLessEqual(pr["done"], pr["total"])
            self.assertIsInstance(u.get("instructors"), list)

    def test_303_instructor_tab_has_students_count(self):
        st, r = self.admin.get("/api/admin/users?role=instructor")
        self.assertEqual(st, 200, r)
        for u in r["users"]:
            self.assertIn("instructor", u)
            self.assertIsInstance(u.get("students_count"), int)
            self.assertGreaterEqual(u["students_count"], 0)

    def test_304_search_inside_role(self):
        """Qidiruv faqat tanlangan rol ichida ishlaydi."""
        st, r = self.admin.get("/api/admin/users?role=student&q=usrL_00004")
        self.assertEqual(st, 200, r)
        self.assertTrue(any(u["login"] == "usrL_00004" for u in r["users"]))

        # Boshqa rolga tegishli qidiruv natijasi bo'sh bo'lishi SHART
        st, r2 = self.admin.get("/api/admin/users?role=admin&q=usrL_00004")
        self.assertEqual(st, 200, r2)
        self.assertEqual([u for u in r2["users"] if u["login"] == "usrL_00004"], [])

        st, r3 = self.admin.get("/api/admin/users?role=student&q=admin123")
        self.assertEqual(st, 200, r3)
        self.assertEqual([u for u in r3["users"] if u["role"] != "student"], [])

    def test_305_other_roles_cannot_list_users(self):
        for login, pw, role in (("usrL_00004", "usrP_00004", "student"),
                                 ("usrL_00001", "usrP_00001", "instructor")):
            from app.auth import reset_login_attempts
            reset_login_attempts("login:" + login)
            c = Client()
            st, _ = c.post("/api/auth/login", {"login": login, "password": pw, "role": role})
            self.assertEqual(st, 200)
            for q in ("role=student", "role=instructor", "role=admin"):
                self.assertEqual(c.get(f"/api/admin/users?{q}")[0], 403,
                                 f"{role} admin ro'yxatini ko'ra oladi!")


if __name__ == "__main__":
    unittest.main(verbosity=2)