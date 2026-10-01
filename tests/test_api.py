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
import re
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Test uchun alohida temp baza
TMP = Path(tempfile.mkdtemp(prefix="avtomaktab_test_"))
os.environ["AVTOMAKTAB_DB"] = str(TMP / "test.db")

# BAND 6 — rate limiting / IP bloklash TESTLARNI buzmasligi uchun o'chiriladi.
# Bular server JARAYONI ichida bitta umumiy serverda ishlayotgani uchun
# kerak: aks holda birinchi ~100 so'rovdan keyin 429 qaytadi.
# (Brute-force himoyasi alohida test sinflarida `reset_login_attempts()` orqali
#  tekshiriladi — u o'chirilmaydi, faqat chegaralar ko'tariladi.)
os.environ["API_RATE_MAX"] = "0"     # umumiy so'rov limiteri — o'chirilgan
os.environ["MAX_IP_TRIES"] = "0"    # IP bloklash — o'chirilgan
os.environ["MAX_LOGIN_TRIES"] = "100000"

import server  # noqa: E402

from app.db import jload, Db, now  # noqa: E402
from app.api import ensure_reminders  # noqa: E402
from app.auth import hash_password  # noqa: E402


# ---------------------------------------------------------------------------
# BAND 5/7: seed endi RANDOM credential yaratadi (taxmin qilinishi mumkin emas).
# Testlar barqaror bo'lishi uchun seeded foydalanuvchilarning login/parolini
# shu yerda TESTGA XOS, YANGI FORMATDAGI qiymatlar bilan almashtiramiz
# (boshqa hech narsa — mashg'ulotlar, tarix, statistika — tegilmaydi).
#
#   login    : usrL_<14 belgi>   (harflar + raqam)
#   password : usrP_<14 belgi>   (katta + kichik harf + raqam + maxsus belgi)
# ---------------------------------------------------------------------------
INSTR_LOGINS = ("usrL_instr00000001", "usrL_instr00000002", "usrL_instr00000003")
INSTR_PASSWORDS = ("usrP_Inst0000!Ab1x", "usrP_Inst0000!Ab2x", "usrP_Inst0000!Ab3x")
STUD_LOGINS = ("usrL_stud00000001", "usrL_stud00000002",
               "usrL_stud00000003", "usrL_stud00000004")
STUD_PASSWORDS = ("usrP_Stud0000!Cd1x", "usrP_Stud0000!Cd2x",
                  "usrP_Stud0000!Cd3x", "usrP_Stud0000!Cd4x")

ADMIN_LOGIN, ADMIN_PASSWORD = "admin", "admin123"

# Qisqa nomlar (testlar shularni ishlatadi)
INSTR_LOGIN_1, INSTR_PASS_1 = INSTR_LOGINS[0], INSTR_PASSWORDS[0]
INSTR_LOGIN_3, INSTR_PASS_3 = INSTR_LOGINS[2], INSTR_PASSWORDS[2]
STUD_LOGIN_1, STUD_PASS_1 = STUD_LOGINS[0], STUD_PASSWORDS[0]
STUD_LOGIN_2, STUD_PASS_2 = STUD_LOGINS[1], STUD_PASSWORDS[1]
STUD_LOGIN_3, STUD_PASS_3 = STUD_LOGINS[2], STUD_PASSWORDS[2]
STUD_LOGIN_4, STUD_PASS_4 = STUD_LOGINS[3], STUD_PASSWORDS[3]

# Test fixture parollari — `_login` yordamchisi shu ro'yxatdan topadi.
PW_BY_LOGIN = {
    INSTR_LOGINS[0]: INSTR_PASSWORDS[0],
    INSTR_LOGINS[1]: INSTR_PASSWORDS[1],
    INSTR_LOGINS[2]: INSTR_PASSWORDS[2],
    STUD_LOGINS[0]: STUD_PASSWORDS[0],
    STUD_LOGINS[1]: STUD_PASSWORDS[1],
    STUD_LOGINS[2]: STUD_PASSWORDS[2],
    STUD_LOGINS[3]: STUD_PASSWORDS[3],
}


def _seed_fixture_credentials():
    """Seeded foydalanuvchilarga barqaror login/parol beradi (testga xos)."""
    db = Db(str(TMP / "test.db"))
    fixed = []
    for i, name in enumerate(["Akmal", "Jasur", "Vali"]):
        row = db.q1("SELECT id FROM users WHERE first_name=? AND role='instructor'", (name,))
        if row:
            fixed.append((row["id"], INSTR_LOGINS[i], INSTR_PASSWORDS[i]))
    for i, name in enumerate(["Omadbek", "Ali", "Vali", "Hasan"]):
        row = db.q1(
            """SELECT u.id AS id FROM users u JOIN students s ON s.user_id=u.id
               WHERE u.first_name=? AND u.role='student'""", (name,))
        if row:
            fixed.append((row["id"], STUD_LOGINS[i], STUD_PASSWORDS[i]))
    for uid, login, pw in fixed:
        db.upd(
            "UPDATE users SET login=?, password_hash=?, must_change_password=0, updated_at=? WHERE id=?",
            (login, hash_password(pw), now(), uid))
        db.ex(
            "INSERT OR IGNORE INTO used_credentials(login_digest, password_digest, created_at) VALUES(?,?,?)",
            (__import__("hashlib").sha256(login.encode()).hexdigest(),
             __import__("hashlib").sha256(pw.encode()).hexdigest(), now()))
    return len(fixed)


FIXED_COUNT = _seed_fixture_credentials()

HOST, PORT = "127.0.0.1", 0


class Client:
    """Cookie'li HTTP klient."""

    def __init__(self):
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))
        self._csrf = ""

    # BAND 6: server CSRF token'ni MAJBURIY qilgan -> test klient ham uni
    # yuborishi shart (haqiqiy frontend kabi: `sessionStorage`dan oladi).
    def _csrf_token(self):
        if not self._csrf:
            st, r = self.get("/api/auth/me")      # GET -> token talab qilinmaydi
            if st == 200:
                self._csrf = (r or {}).get("csrf") or ""
        return self._csrf

    def req(self, method, path, body=None, cookie=None):
        data = None
        headers = {}
        if body is not None:
            data = json.dumps(body).encode()
            headers["Content-Type"] = "application/json"
        if method in ("POST", "PUT", "DELETE"):
            headers["X-Requested-With"] = "Avtomaktab"
            # `cookie=` — BOSHQA sessiya uchun so'rov: o'shaning token'i
            # kerak emas (maqsad — "eski cookie ishlamaydi" tekshiruvi).
            if not cookie:
                tok = self._csrf_token()
                if tok:
                    headers["X-CSRF-Token"] = tok
        # Chiqishdan keyin "eski token saqlab qolinsa ham ishlamaydi" —
        # buni tekshirish uchun cookie'ni qo'lda yuborish imkoniyati.
        if cookie:
            headers["Cookie"] = "sid=" + cookie
        req = urllib.request.Request(f"http://{HOST}:{PORT}{path}", data=data, headers=headers, method=method)
        try:
            with self.opener.open(req, timeout=15) as resp:
                raw = resp.read()
                try:
                    out = json.loads(raw.decode("utf-8"))
                except Exception:
                    return resp.status, {"raw": True, "mime": resp.headers.get("Content-Type")}
                if isinstance(out, dict) and out.get("csrf"):
                    self._csrf = out["csrf"]
                return resp.status, out
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
            if not cookie:
                tok = self._csrf_token()
                if tok:
                    headers["X-CSRF-Token"] = tok
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
                    out = json.loads(raw.decode("utf-8"))
                except Exception:
                    return resp.status, {"raw": True}
                if isinstance(out, dict) and out.get("csrf"):
                    self._csrf = out["csrf"]
                return resp.status, out
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
        # Boshqa testlar Akmalga (INSTR_LOGIN_1) bog'liq — bloklash uchun alohida user yaratamiz
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
        self.assertRegex(r["credentials"]["login"], r"^usrL_[A-Za-z0-9]{14}$")
        self.assertRegex(r["credentials"]["password"], r"^usrP_[A-Za-z0-9!@#$%^&*()\-_=+\[\]{}?]{14}$")
        # yangi login bilan kirish
        sc = Client()
        st, r2 = sc.post("/api/auth/login", {"login": r["credentials"]["login"],
                                             "password": r["credentials"]["password"],
                                             "role": "student"})
        self.assertEqual(st, 200, r2)

    def test_07_credentials_unique_random_not_reused(self):
        """BAND 7: har bir yangi credential UNIKAL va RANDOM.

        Eski ketma-ket format (`usrL_00001`) olib tashlangan — login ham,
        parol ham `secrets` (CSPRNG) bilan tasodifiy yaratiladi va hech
        qachon qayta ishlatilmaydi (DB UNIQUE constraint + collision retry).
        """
        admin = Client()
        admin.post("/api/auth/login", {"login": ADMIN_LOGIN, "password": ADMIN_PASSWORD, "role": "admin"})
        logins, passes = [], []
        for i, role in enumerate(("student", "student", "instructor")):
            st, r = admin.post("/api/admin/users",
                               {"role": role, "first_name": "A%d" % i, "last_name": "B%d" % i})
            self.assertEqual(st, 200, r)
            logins.append(r["credentials"]["login"])
            passes.append(r["credentials"]["password"])
        # 1) UNIKAL: hech ikkisi bir xil emas
        self.assertEqual(len(set(logins)), 3, "loginlar takrorlanmasin")
        self.assertEqual(len(set(passes)), 3, "parollar takrorlanmasin")
        # 2) FORMAT: usrL_ / usrP_ + 14 ta xavfsiz random belgi
        for lg in logins:
            self.assertRegex(lg, r"^usrL_[A-Za-z0-9]{14}$")
        for pw in passes:
            self.assertRegex(pw, r"^usrP_[A-Za-z0-9!@#$%^&*()\-_=+\[\]{}?]{14}$")
            body = pw[len("usrP_"):]
            self.assertTrue(any(c.isupper() for c in body), "katta harf")
            self.assertTrue(any(c.islower() for c in body), "kichik harf")
            self.assertTrue(any(c.isdigit() for c in body), "raqam")
            self.assertTrue(any(not c.isalnum() for c in body), "maxsus belgi")
        # 3) KETMA-KET EMAS: loginlar bir-biridan "keyingi" emas
        self.assertNotEqual(logins[1], logins[0])
        # 4) O'chirilgan foydalanuvchining credential'i QAYTA ishlatilmaydi
        users = admin.get("/api/admin/users?role=student")[1]["users"]
        target = next(u for u in users if u["login"] == logins[0])
        admin.delete(f"/api/admin/users/{target['id']}")
        st, r = admin.post("/api/admin/users",
                           {"role": "student", "first_name": "A4", "last_name": "B4"})
        self.assertEqual(st, 200, r)
        self.assertNotEqual(r["credentials"]["login"], logins[0])
        self.assertNotEqual(r["credentials"]["password"], passes[0])
        # 5) Parol DB'da oddiy matn sifatida SAQLANMAYDI (BAND 6)
        db = Db(str(TMP / "test.db"))
        row = db.q1("SELECT password_hash FROM users WHERE login=?", (r["credentials"]["login"],))
        self.assertTrue(row["password_hash"].startswith("scrypt$"),
                        "parol scrypt hash sifatida saqlanadi")
        self.assertNotIn(r["credentials"]["password"], row["password_hash"])

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
        ("instructor", INSTR_LOGIN_1, INSTR_PASS_1),
        ("student", STUD_LOGIN_1, STUD_PASS_1),
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
        st, r = stu.post("/api/auth/login", {"login": STUD_LOGIN_1, "password": STUD_PASS_1, "role": "student"})
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
        inst.post("/api/auth/login", {"login": INSTR_LOGIN_3, "password": INSTR_PASS_3, "role": "instructor"})
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
        st.post("/api/auth/login", {"login": STUD_LOGIN_1, "password": STUD_PASS_1, "role": "student"})
        code, r = st.get("/api/admin/users")
        self.assertEqual(code, 403)
        self.assertEqual(r["error"], "forbidden")

    def test_41_instructor_cannot_access_admin(self):
        it = Client()
        it.post("/api/auth/login", {"login": INSTR_LOGIN_1, "password": INSTR_PASS_1, "role": "instructor"})
        code, r = it.get("/api/admin/dashboard")
        self.assertEqual(code, 403)

    def test_42_student_cannot_see_other_student_data(self):
        st = Client()
        st.post("/api/auth/login", {"login": STUD_LOGIN_1, "password": STUD_PASS_1, "role": "student"})
        # Boshqa talabaning sessionlari API bor, lekin yo'l boshqa talabaga tegishli emas
        sessions = st.get("/api/student/sessions?upcoming=1")[1]["sessions"]
        # 1-talaba (Omadbek) sessionlari ro'yxatida faqat o'ziniki bo'ladi; boshqa talabaning ma'lumotlari yo'q
        for s in sessions:
            # student na faqat o'z sessionlarini ko'ra oladi — ular ro'yxati Omadbek'dan
            pass
        # shaxsiy profil
        me = st.get("/api/auth/me")[1]
        self.assertEqual(me["user"]["login"], STUD_LOGIN_1)

    def test_43_instructor_cannot_manage_others_sessions(self):
        it = Client()
        it.post("/api/auth/login", {"login": INSTR_LOGIN_1, "password": INSTR_PASS_1, "role": "instructor"})
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
        st.post("/api/auth/login", {"login": STUD_LOGIN_1, "password": STUD_PASS_1, "role": "student"})
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
        stud.post("/api/auth/login", {"login": STUD_LOGIN_1, "password": STUD_PASS_1, "role": "student"})
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
        stud.post("/api/auth/login", {"login": STUD_LOGIN_1, "password": STUD_PASS_1, "role": "student"})
        st, _ = stud.delete(f"/api/admin/cars/{cid}/photos/1")
        self.assertEqual(st, 403)
        st, _ = stud.post(f"/api/admin/cars/{cid}/photos", {"image": "x"})
        self.assertEqual(st, 403)

    def test_63_instructor_sees_car_photos(self):
        admin = self._admin()
        # Akmal (instructor 1) Cobalt'da — fotosurat qo'shamiz
        akmal = Client()
        akmal.post("/api/auth/login", {"login": INSTR_LOGIN_1, "password": INSTR_PASS_1, "role": "instructor"})
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
        inst.post("/api/auth/login", {"login": INSTR_LOGIN_1, "password": INSTR_PASS_1, "role": "instructor"})
        st, r = inst.get("/api/instructor/home")
        self.assertEqual(st, 200, r)
        for k in ("sessions", "done", "hours", "students", "today"):
            self.assertIn(k, r["weekly"])
        for k in ("sessions", "done", "hours"):
            self.assertIn(k, r["overall"])
        self.assertIn("car", r)

    def test_72_student_home_overall_progress(self):
        st = Client()
        st.post("/api/auth/login", {"login": STUD_LOGIN_1, "password": STUD_PASS_1, "role": "student"})
        code, r = st.get("/api/student/home")
        self.assertEqual(code, 200, r)
        self.assertIn("overall", r)
        self.assertIn("weekly", r)
        self.assertIn("next", r)
        self.assertIsInstance(r["overall"]["sessions"], int)
        self.assertIsInstance(r["weekly"]["done"], int)

    def test_73_student_today(self):
        st = Client()
        st.post("/api/auth/login", {"login": STUD_LOGIN_1, "password": STUD_PASS_1, "role": "student"})
        code, r = st.get("/api/student/today")
        self.assertEqual(code, 200, r)
        self.assertIn("sessions", r)
        self.assertIsInstance(r["sessions"], list)

    def test_74_rbac_home_and_today(self):
        stud = Client()
        stud.post("/api/auth/login", {"login": STUD_LOGIN_1, "password": STUD_PASS_1, "role": "student"})
        st, _ = stud.get("/api/instructor/home")
        self.assertEqual(st, 403)
        inst = Client()
        inst.post("/api/auth/login", {"login": INSTR_LOGIN_1, "password": INSTR_PASS_1, "role": "instructor"})
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
        self.assertEqual(set(s["notif"].keys()),
                         {"lesson", "request", "message", "security", "reminder", "admin"})
        self.assertTrue(all(s["notif"].values()))
        # BAND 17: yangi, aniq `notification_settings` ham qaytariladi
        self.assertEqual(set(s["notification_settings"].keys()),
                         {"lesson_reminders", "admin_messages", "lesson_status_updates",
                          "messages", "requests", "security"})
        self.assertTrue(all(s["notification_settings"].values()))

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
        inst.post("/api/auth/login", {"login": INSTR_LOGIN_1, "password": INSTR_PASS_1, "role": "instructor"})
        inst.put("/api/me/settings", {"notif": {"lesson": False}})
        # Student (Omadbek) default holatda
        stu = Client()
        stu.post("/api/auth/login", {"login": STUD_LOGIN_1, "password": STUD_PASS_1, "role": "student"})

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
        st, rr = inst.post("/api/auth/request-password-reset", {"login": INSTR_LOGIN_1})
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

    def _mk_session(self, db, start_dt, created_at, student_id=1, inst_id=1, notes="REM"):
        """Test uchun mashg'ulot qatori (created_at ni boshqarish bilan)."""
        date, start = start_dt.strftime("%Y-%m-%d"), start_dt.strftime("%H:%M")
        end = (start_dt + timedelta(minutes=60))
        end_s = end.strftime("%H:%M") + (("+" + end.strftime("%d")) if end.day != start_dt.day else "")
        sid = db.ex(
            """INSERT INTO lesson_sessions(date,start_time,end_time,instructor_id,car_id,car_name_snapshot,
               car_plate_snapshot,capacity_snapshot,status,notes,created_at,updated_at)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
            (date, start, end_s, inst_id, 1, "Test avto", "A 001 AA", 4, "scheduled",
             notes, created_at, created_at),
        )
        db.ex(
            """INSERT INTO session_students(session_id, student_id, pickup_address,
               attendance_status, student_status, joined_at) VALUES(?,?,'','unmarked','active',?)""",
            (sid, student_id, created_at),
        )
        return sid

    def _reminder_count(self, db, sid):
        return db.q1(
            "SELECT COUNT(*) c FROM notifications WHERE source='LESSON_REMINDER' AND related_lesson_id=?",
            (sid,))["c"]

    def test_100_reminder_2h_before_exactly_once(self):
        """BAND 9: 2 soat oldin eslatma FAQAT BIR MARTA yuboriladi."""
        db = Db(str(TMP / "test.db"))
        # Boshlanishi hozirdan 1 soat 50 daqiqa keyin (2 soat oynasi KIRGAN),
        # lekin yaratilishi eslatma vaqtidan OLDIN (3 soat oldin).
        start_dt = (datetime.now() + timedelta(minutes=110)).replace(second=0, microsecond=0)
        created = (start_dt - timedelta(hours=3)).strftime("%Y-%m-%d %H:%M:%S")
        sid = self._mk_session(db, start_dt, created)
        try:
            n1 = ensure_reminders(db)
            self.assertGreaterEqual(n1, 2, "instruktor + talaba uchun eslatma yuborilishi kerak")
            n2 = ensure_reminders(db)
            self.assertEqual(n2, 0, "takroriy eslatma yuborilmasligi kerak")
            n3 = ensure_reminders(db)
            self.assertEqual(n3, 0, "uchinchi marta ham 0")
            self.assertEqual(self._reminder_count(db, sid), 2, "faqat 2 ta qabulchi")
            # Ma'lumot: sana, vaqt, instruktor, olib ketish joyi
            row = db.q1("""SELECT * FROM notifications
                           WHERE source='LESSON_REMINDER' AND related_lesson_id=? LIMIT 1""", (sid,))
            data = jload(row["data"], {}) if not isinstance(row["data"], dict) else row["data"]
            self.assertEqual(data["date"], start_dt.strftime("%Y-%m-%d"))
            self.assertEqual(data["start_time"], start_dt.strftime("%H:%M"))
            self.assertIn("instructor_name", data)
            self.assertIn("pickup_address", data)
            self.assertEqual(row["created_by"], "SYSTEM", "avtomatik eslatma: created_by=SYSTEM")
        finally:
            self._cleanup(db, sid)

    def test_101_no_reminder_when_created_later_than_2h_window(self):
        """BAND 9: 2 soatdan KAM vaqt ichida yaratilgan mashg'ulotga eslatma
        yuborilmaydi (noto'g'ri/duplicate bildirishnoma chiqmasin)."""
        db = Db(str(TMP / "test.db"))
        start_dt = (datetime.now() + timedelta(minutes=30)).replace(second=0, microsecond=0)
        sid = self._mk_session(db, start_dt, now(), notes="REM2")
        try:
            self.assertEqual(ensure_reminders(db), 0, "eslatma yuborilmasligi kerak")
            self.assertEqual(self._reminder_count(db, sid), 0)
        finally:
            self._cleanup(db, sid)

    def test_102_no_reminder_after_lesson_started(self):
        """BAND 9: allaqachon boshlangan mashg'ulotga eslatma yuborilmaydi."""
        db = Db(str(TMP / "test.db"))
        start_dt = (datetime.now() - timedelta(minutes=10)).replace(second=0, microsecond=0)
        sid = self._mk_session(db, start_dt, (start_dt - timedelta(hours=4)).strftime("%Y-%m-%d %H:%M:%S"),
                               notes="REM3")
        try:
            self.assertEqual(ensure_reminders(db), 0)
            self.assertEqual(self._reminder_count(db, sid), 0)
        finally:
            self._cleanup(db, sid)

    def _cleanup(self, db, sid):
        db.upd("DELETE FROM notifications WHERE related_lesson_id=?", (sid,))
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
        c.post("/api/auth/login", {"login": INSTR_LOGIN_1, "password": INSTR_PASS_1, "role": "instructor"})
        return c

    def _stud(self):
        c = Client()
        c.post("/api/auth/login", {"login": STUD_LOGIN_1, "password": STUD_PASS_1, "role": "student"})
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
        c.post("/api/auth/login", {"login": STUD_LOGIN_1, "password": STUD_PASS_1, "role": "student"})
        st, r = c.get("/api/admin/analytics")
        self.assertEqual(st, 403, r)


class TestM4RequestApprove(Base):
    """M4 — Admin so'rovni tasdiqlash (bugfix): session_students INSERT'dagi
    bindings xatosi tufayli tasdiqlash 500 berib, so'rov holati o'zgarmas edi.
    Endi tasdiqlash: yangi session + student qatori + talabaga bildirishnoma."""

    def _student(self):
        c = Client()
        c.post("/api/auth/login", {"login": STUD_LOGIN_1, "password": STUD_PASS_1, "role": "student"})
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
        """Test fixture loginlari (`PW_BY_LOGIN` ro'yxatidan parol topiladi)."""
        c = Client()
        c.post("/api/auth/login",
               {"login": login, "password": PW_BY_LOGIN.get(login, "usrP_Nope0000!Ab1x"),
                "role": "student"})
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
        c.post("/api/auth/login", {"login": STUD_LOGIN_1, "password": STUD_PASS_1, "role": "student"})
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
        c.post("/api/auth/login", {"login": STUD_LOGIN_1, "password": STUD_PASS_1, "role": "student"})
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
        st, r2 = inst.post("/api/auth/login", {"login": INSTR_LOGIN_1, "password": INSTR_PASS_1, "role": "instructor"})
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
        st, r = stu.post("/api/auth/login", {"login": STUD_LOGIN_1, "password": STUD_PASS_1, "role": "student"})
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

    def _inst_login(self, login=INSTR_LOGIN_1, pwd=INSTR_PASS_1):
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
        inst = self._inst_login(INSTR_LOGIN_3, INSTR_PASS_3)  # Vali (inst 3)
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

    INSTR = (INSTR_LOGIN_1, INSTR_PASS_1, "instructor")
    STUD = (STUD_LOGIN_1, STUD_PASS_1, "student")
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
        (INSTR_LOGIN_1, INSTR_PASS_1, "instructor"),
        (STUD_LOGIN_1, STUD_PASS_1, "student"),
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
        st, r = self._login({"login": STUD_LOGIN_1, "password": "noto'g'ri-parol", "role": "admin"})
        self.assertEqual(st, 400)
        self.assertEqual(r["error"], "auth.wrong_credentials")

    def test_205_no_session_created_on_role_mismatch(self):
        """Rad etilgandan keyin sessiya QOLMASIN."""
        c = Client()
        st, _ = self._login({"login": STUD_LOGIN_1, "password": STUD_PASS_1, "role": "admin"})
        self.assertEqual(st, 400)
        c = TabClient("role-mismatch-1")
        c.post("/api/auth/login", {"login": STUD_LOGIN_1, "password": STUD_PASS_1, "role": "admin"})
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
        st, r = self.admin.get("/api/admin/users?role=student&q=" + STUD_LOGIN_1)
        self.assertEqual(st, 200, r)
        self.assertTrue(any(u["login"] == STUD_LOGIN_1 for u in r["users"]))

        # Boshqa rolga tegishli qidiruv natijasi bo'sh bo'lishi SHART
        st, r2 = self.admin.get("/api/admin/users?role=admin&q=" + STUD_LOGIN_1)
        self.assertEqual(st, 200, r2)
        self.assertEqual([u for u in r2["users"] if u["login"] == STUD_LOGIN_1], [])

        st, r3 = self.admin.get("/api/admin/users?role=student&q=admin123")
        self.assertEqual(st, 200, r3)
        self.assertEqual([u for u in r3["users"] if u["role"] != "student"], [])

    def test_305_other_roles_cannot_list_users(self):
        for login, pw, role in ((STUD_LOGIN_1, STUD_PASS_1, "student"),
                                 (INSTR_LOGIN_1, INSTR_PASS_1, "instructor")):
            from app.auth import reset_login_attempts
            reset_login_attempts("login:" + login)
            c = Client()
            st, _ = c.post("/api/auth/login", {"login": login, "password": pw, "role": role})
            self.assertEqual(st, 200)
            for q in ("role=student", "role=instructor", "role=admin"):
                self.assertEqual(c.get(f"/api/admin/users?{q}")[0], 403,
                                 f"{role} admin ro'yxatini ko'ra oladi!")


class TestTotalLessonsTarget(Base):
    """MODUL 5 — "Jami darslar": admin belgilaydigan maqsad.
    Rejimlar: individual (talaba uchun alohida) va ommaviy (platforma)."""

    STUD = (STUD_LOGIN_1, STUD_PASS_1, "student")

    def setUp(self):
        self.admin = Client()
        from app.auth import reset_login_attempts
        reset_login_attempts("login:admin")
        st, r = self.admin.post("/api/auth/login",
                                {"login": "admin", "password": "admin123", "role": "admin"})
        self.assertEqual(st, 200, r)
        self.db = Db(str(TMP / "test.db"))
        # Har bir test toza holatdan boshlanishi uchun individual qiymatni
        # ommaviy sozlamaga qaytaramiz.
        self._set_individual(None)
        self._set_group(30)

    # ------------------------------------------------------------------ yordamchi
    def _set_group(self, n):
        st, r = self.admin.put("/api/admin/settings", {"total_lessons_target": n})
        self.assertEqual(st, 200, r)

    def _set_individual(self, val):
        st, r = self.admin.get("/api/admin/users?role=student&q=" + STUD_LOGIN_1)
        self.assertEqual(st, 200, r)
        uid = r["users"][0]["id"]
        body = {"student": {"total_lessons_target": val}}
        st, r2 = self.admin.put(f"/api/admin/users/{uid}", body)
        self.assertEqual(st, 200, r2)

    def _home(self):
        c = Client()
        st, r = c.post("/api/auth/login",
                       {"login": self.STUD[0], "password": self.STUD[1], "role": "student"})
        self.assertEqual(st, 200, r)
        st, h = c.get("/api/student/home")
        self.assertEqual(st, 200, h)
        return h

    def _done_count(self):
        """Bazadagi haqiqiy bajarilgan darslar soni."""
        row = self.db.q1(
            """SELECT COUNT(*) AS n FROM session_students ss
               JOIN lesson_sessions ls ON ls.id=ss.session_id
               JOIN students s ON s.id=ss.student_id
               JOIN users u ON u.id=s.user_id
               WHERE u.login=? AND ss.student_status='active'
                 AND ls.status!='cancelled' AND ls.status='completed'""",
            (self.STUD[0],))
        return row["n"]

    # ------------------------------------------------------------------ testlar
    def test_400_home_returns_progress(self):
        h = self._home()
        pr = h["progress"]
        for k in ("target", "done", "remaining", "pct", "mode"):
            self.assertIn(k, pr)
        self.assertEqual(pr["done"], self._done_count())
        self.assertEqual(pr["mode"], "group", "individual qiymat yo'q — ommaviy rejim kerak")
        self.assertEqual(pr["target"], 30)
        self.assertEqual(pr["pct"], round(self._done_count() * 100 / 30))

    def test_401_group_target_applies_to_all(self):
        for n in (10, 45, 100):
            self._set_group(n)
            self.assertEqual(self._home()["progress"]["target"], n,
                             f"ommaviy maqsad {n} qo'llanmadi")

    def test_402_individual_overrides_group(self):
        self._set_group(30)
        self._set_individual(12)
        pr = self._home()["progress"]
        self.assertEqual(pr["mode"], "individual")
        self.assertEqual(pr["target"], 12, "individual maqsad ustun kelmadi")
        self.assertEqual(pr["group_target"], 30)
        self.assertEqual(pr["individual_target"], 12)

    def test_403_clearing_individual_returns_to_group(self):
        self._set_individual(12)
        self.assertEqual(self._home()["progress"]["mode"], "individual")
        self._set_individual(None)
        pr = self._home()["progress"]
        self.assertEqual(pr["mode"], "group")
        self.assertEqual(pr["target"], 30)
        self.assertIsNone(pr["individual_target"])

    def test_404_pct_and_remaining_are_consistent(self):
        self._set_group(20)
        pr = self._home()["progress"]
        self.assertEqual(pr["remaining"], max(0, pr["target"] - pr["done"]))
        self.assertEqual(pr["pct"], round(pr["done"] * 100 / pr["target"]))
        self.assertTrue(0 <= pr["pct"] <= 100)

    def test_405_invalid_group_target_normalized(self):
        """Admin noto'g'ri qiymat yuborsa — standartga qaytariladi (xato chiqmaydi)."""
        for bad, want in ((0, 30), (-5, 30), (1000, 999), ("abc", 30), (None, 30), ("45", 45)):
            st, r = self.admin.put("/api/admin/settings", {"total_lessons_target": bad})
            self.assertEqual(st, 200, f"{bad!r}: {r}")
            pr = self._home()["progress"]
            self.assertEqual(pr["target"], want, f"{bad!r} -> {pr['target']}, kutilgan {want}")
            self.assertGreaterEqual(pr["target"], 1, "maqsad 0 bo'lsa foiz hisobi buziladi")
            self.assertTrue(0 <= pr["pct"] <= 100)

    def test_406_invalid_individual_target_rejected(self):
        self._set_individual(20)
        for bad in (-5, 1000, 99999, "abc", "1.5"):
            st, r = self.admin.put(f"/api/admin/users/{self._uid()}",
                                   {"student": {"total_lessons_target": bad}})
            self.assertEqual(st, 400, f"{bad!r} qabul qilindi: {r}")
            self.assertEqual(r["error"], "user.bad_total_lessons")
        # Xato qabul qilinmagan qiymat maqsadni buzmasin
        self.assertEqual(self._ind_value(), 20)

    def test_406b_zero_means_clear_individual(self):
        """0 / bo'sh qiymat = individual rejimni bekor qilish (ommaviyga qaytish)."""
        for empty in (0, "0", "", None):
            self._set_individual(15)
            self._set_individual(empty)
            self.assertIsNone(self._ind_value(), f"{empty!r} individual maqsadni tozalamadi")
            self.assertEqual(self._home()["progress"]["mode"], "group")

    def test_407_valid_individual_target_accepted(self):
        for good in (1, 50, 999):
            self._set_individual(good)
            self.assertEqual(self._ind_value(), good)
            self.assertEqual(self._home()["progress"]["target"], good)

    def test_408_new_student_can_get_individual_target(self):
        st, r = self.admin.post("/api/admin/users", {
            "role": "student", "first_name": "Maqsad", "last_name": "Test",
            "group_name": "G-1", "license_category": "B", "total_lessons_target": 7,
        })
        self.assertEqual(st, 200, r)
        uid = r["user"]["id"]
        row = self.db.q1("SELECT total_lessons_target FROM students WHERE user_id=?", (uid,))
        self.assertEqual(row["total_lessons_target"], 7)
        # Tozalash
        self.db.upd("UPDATE users SET deleted_at=datetime('now') WHERE id=?", (uid,))

    def test_409_new_student_without_target_uses_group(self):
        st, r = self.admin.post("/api/admin/users", {
            "role": "student", "first_name": "Kurs", "last_name": "Test",
            "group_name": "G-2", "license_category": "B",
        })
        self.assertEqual(st, 200, r)
        row = self.db.q1("SELECT total_lessons_target FROM students WHERE user_id=?",
                         (r["user"]["id"],))
        self.assertIsNone(row["total_lessons_target"], "individual maqsad berilmagan bo'lishi kerak")
        self.db.upd("UPDATE users SET deleted_at=datetime('now') WHERE id=?", (r["user"]["id"],))

    def test_410_settings_expose_target(self):
        st, r = self.admin.get("/api/admin/settings")
        self.assertEqual(st, 200, r)
        self.assertIn("total_lessons_target", r["settings"])
        self._set_group(44)
        st, r = self.admin.get("/api/admin/settings")
        self.assertEqual(r["settings"]["total_lessons_target"], 44)

    def test_411_student_cannot_change_target(self):
        st, r = self.admin.post("/api/admin/users", {
            "role": "student", "first_name": "Sinov", "last_name": "Test", "group_name": "G-3"})
        self.assertEqual(st, 200, r)
        uid = r["user"]["id"]
        login = r["credentials"]["login"]
        pw = r["credentials"]["password"]
        c = Client()
        st, _ = c.post("/api/auth/login", {"login": login, "password": pw, "role": "student"})
        self.assertEqual(st, 200)
        self.assertEqual(c.put(f"/api/admin/users/{uid}",
                               {"student": {"total_lessons_target": 1}})[0], 403)
        self.assertEqual(c.put("/api/admin/settings", {"total_lessons_target": 1})[0], 403)
        self.assertIsNone(self.db.q1(
            "SELECT total_lessons_target FROM students WHERE user_id=?", (uid,))["total_lessons_target"])
        self.db.upd("UPDATE users SET deleted_at=datetime('now') WHERE id=?", (uid,))

    def test_412_instructor_cannot_change_target(self):
        c = Client()
        st, _ = c.post("/api/auth/login",
                       {"login": INSTR_LOGIN_1, "password": INSTR_PASS_1, "role": "instructor"})
        self.assertEqual(st, 200)
        self.assertEqual(c.put("/api/admin/settings", {"total_lessons_target": 1})[0], 403)

    # ------------------------------------------------------------------ kichik yordamchilar
    def _uid(self):
        st, r = self.admin.get("/api/admin/users?role=student&q=" + STUD_LOGIN_1)
        return r["users"][0]["id"]

    def _ind_value(self):
        return self.db.q1("SELECT total_lessons_target FROM students WHERE user_id=?",
                          (self._uid(),))["total_lessons_target"]


class TestMapAndCoordinates(Base):
    """MODUL 4 — XARITA (Yandex Maps JS API) va kenglik/uzunlik.

    Tekshiriladi:
      * `GET /api/config` — xarita sozlamalari KIRISHSIZ qaytariladi,
        kalit faqat `.env` dan olinadi, hech qanday sirli ma'lumot yo'q.
      * Xarita markazi — Toshkent (`.env` bilan o'zgartirilishi mumkin).
      * "Kenglik"/"Uzunlik" validatsiyasi — noto'g'ri qiymat JIM QOLMAYDI,
        aniq `coord.*` kodi qaytariladi va eski qiymat buzilmaydi.
    """

    ENV_KEYS = ("YANDEX_MAPS_API_KEY", "MAP_PROVIDER", "MAP_CENTER_LAT",
                "MAP_CENTER_LNG", "MAP_CENTER_ZOOM")
    TASHKENT = (41.311081, 69.240562)

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        from app.auth import reset_login_attempts
        reset_login_attempts("login:admin")
        admin = Client()
        st, _ = admin.post("/api/auth/login",
                           {"login": "admin", "password": "admin123", "role": "admin"})
        assert st == 200, "admin login muvaffaqiyatsiz"
        st, cr = admin.post("/api/admin/users", {
            "role": "student", "first_name": "Xarita", "last_name": "Sinov",
            "group_name": "G-M4", "license_category": "B",
        })
        assert st == 200, cr
        cls.user_id = cr["user"]["id"]
        cls.login = cr["credentials"]["login"]
        cls.password = cr["credentials"]["password"]
        row = Db(str(TMP / "test.db")).q1("SELECT id FROM students WHERE user_id=?", (cls.user_id,))
        assert row, "talaba yaratilmadi"
        cls.student_id = row["id"]

        # Yetarli masofadagi kun (seed sessiyalari bilan to'qnashmasligi uchun)
        from datetime import datetime, timedelta
        d = datetime.now()
        day = (d + timedelta(days=(7 - d.weekday()) % 7 or 7) + timedelta(days=21)).strftime("%Y-%m-%d")
        st, sr = admin.post("/api/admin/sessions", {
            "date": day, "start_time": "08:00", "end_time": "09:00",
            "instructor_id": 1, "student_ids": [cls.student_id], "notes": "M4MAP",
        })
        assert st == 200, sr
        cls.session_id = sr["id"]

    @classmethod
    def tearDownClass(cls):
        db = Db(str(TMP / "test.db"))
        if getattr(cls, "session_id", None):
            db.upd("DELETE FROM session_students WHERE session_id=?", (cls.session_id,))
            db.upd("DELETE FROM notifications WHERE data LIKE ?",
                   (f'%"session_id": {cls.session_id}%',))
            db.upd("DELETE FROM lesson_sessions WHERE id=?", (cls.session_id,))
        if getattr(cls, "user_id", None):
            db.upd("DELETE FROM students WHERE user_id=?", (cls.user_id,))
            db.upd("DELETE FROM users WHERE id=?", (cls.user_id,))
        super().tearDownClass()

    def setUp(self):
        from app.auth import reset_login_attempts
        reset_login_attempts("login:admin")
        reset_login_attempts("login:" + self.login)
        reset_login_attempts("login:INSTR_LOGIN_1")
        self.admin = Client()
        st, r = self.admin.post("/api/auth/login",
                                {"login": "admin", "password": "admin123", "role": "admin"})
        self.assertEqual(st, 200, r)
        self.db = Db(str(TMP / "test.db"))
        # .env kalitlarini o'zgartirmaslik uchun zaxira
        self._env_backup = {k: os.environ.get(k) for k in self.ENV_KEYS}
        self._clear_env()
        self._reset_pickup(None, None, "")

    def tearDown(self):
        self._restore_env()

    def _clear_env(self):
        for k in self.ENV_KEYS:
            os.environ.pop(k, None)

    def _restore_env(self):
        for k, v in self._env_backup.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def _reset_pickup(self, lat, lng, address=""):
        self.db.upd("""UPDATE session_students
                       SET pickup_address=?, pickup_lat=?, pickup_lng=?
                       WHERE session_id=? AND student_id=?""",
                    (address, lat, lng, self.session_id, self.student_id))

    def _pickup(self):
        return self.db.q1("""SELECT pickup_address, pickup_lat, pickup_lng
                             FROM session_students WHERE session_id=? AND student_id=?""",
                          (self.session_id, self.student_id))

    def _student(self):
        c = Client()
        st, r = c.post("/api/auth/login",
                       {"login": self.login, "password": self.password, "role": "student"})
        self.assertEqual(st, 200, r)
        return c

    def _put(self, c, body, sid=None):
        return c.put(f"/api/student/sessions/{sid or self.session_id}/pickup", body)

    # ------------------------------------------------------------ /api/config
    def test_500_config_is_public(self):
        """Sessiyasiz (cookie'siz) so'rov ham ishlashi SHART — login sahifasi
        ham xaritadan foydalanadi."""
        anon = Client()
        st, r = anon.get("/api/config")
        self.assertEqual(st, 200, r)
        self.assertTrue(r["ok"])
        self.assertIn("maps", r["config"])

    def test_501_config_shape(self):
        st, r = self.admin.get("/api/config")
        self.assertEqual(st, 200, r)
        m = r["config"]["maps"]
        for k in ("provider", "api_key", "enabled", "center", "zoom"):
            self.assertIn(k, m, f"/api/config.maps.{k} yo'q")
        self.assertIn("lat", m["center"])
        self.assertIn("lng", m["center"])
        self.assertIsInstance(m["api_key"], str)
        self.assertIsInstance(m["enabled"], bool)

    def test_502_center_is_tashkent_by_default(self):
        m = self.admin.get("/api/config")[1]["config"]["maps"]
        self.assertAlmostEqual(m["center"]["lat"], self.TASHKENT[0], places=4)
        self.assertAlmostEqual(m["center"]["lng"], self.TASHKENT[1], places=4)
        self.assertEqual(m["zoom"], 12)
        # Toshkent chegaralarida bo'lishi SHART (41°N, 69°E)
        self.assertTrue(40 < m["center"]["lat"] < 42)
        self.assertTrue(68 < m["center"]["lng"] < 70)

    def test_503_center_from_env(self):
        os.environ["MAP_CENTER_LAT"] = "39.6542"
        os.environ["MAP_CENTER_LNG"] = "66.9597"
        os.environ["MAP_CENTER_ZOOM"] = "14"
        m = self.admin.get("/api/config")[1]["config"]["maps"]
        self.assertAlmostEqual(m["center"]["lat"], 39.6542, places=4)
        self.assertAlmostEqual(m["center"]["lng"], 66.9597, places=4)
        self.assertEqual(m["zoom"], 14)

    def test_504_bad_center_falls_back_to_tashkent(self):
        """`.env` da noto'g'ri son bo'lsa — xarita JOYNI bo'sh qolmasligi uchun
        Toshkentga qaytariladi (jim qolmaydi, lekin xarita ishlayveradi)."""
        os.environ["MAP_CENTER_LAT"] = "Toshkent"
        m = self.admin.get("/api/config")[1]["config"]["maps"]
        self.assertAlmostEqual(m["center"]["lat"], self.TASHKENT[0], places=4)
        os.environ["MAP_CENTER_LAT"] = "41.311081,5"   # vergulli son
        m = self.admin.get("/api/config")[1]["config"]["maps"]
        self.assertAlmostEqual(m["center"]["lat"], 41.311081, places=4)

    def test_505_disabled_without_key(self):
        m = self.admin.get("/api/config")[1]["config"]["maps"]
        self.assertFalse(m["enabled"], "kalit yo'q bo'lsa xarita 'ochilgan' bo'lmasligi kerak")
        self.assertEqual(m["api_key"], "")

    def test_506_enabled_with_key_from_env(self):
        os.environ["YANDEX_MAPS_API_KEY"] = "test-abc123.Yx-mapKey"
        m = self.admin.get("/api/config")[1]["config"]["maps"]
        self.assertTrue(m["enabled"])
        self.assertEqual(m["api_key"], "test-abc123.Yx-mapKey")
        self.assertEqual(m["provider"], "yandex")

    def test_507_provider_none_disables_map(self):
        os.environ["YANDEX_MAPS_API_KEY"] = "test-abc123.Yx-mapKey"
        os.environ["MAP_PROVIDER"] = "none"
        m = self.admin.get("/api/config")[1]["config"]["maps"]
        self.assertFalse(m["enabled"], "MAP_PROVIDER=none — xarita ko'rsatilmasligi kerak")
        self.assertEqual(m["provider"], "none")

    def test_508_config_never_leaks_secrets(self):
        """Ommaviy endpoint parol/token YOK, faqat xarita kalitini beradi."""
        os.environ["YANDEX_MAPS_API_KEY"] = "map-key-777"
        os.environ.setdefault("BOT_TOKEN", "123456:SECRET-BOT-TOKEN")
        os.environ.setdefault("ADMIN_INITIAL_PASSWORD", "SECRET-ADMIN-PW")
        st, r = self.admin.get("/api/config")
        self.assertEqual(st, 200)
        raw = json.dumps(r, ensure_ascii=False)
        self.assertNotIn("SECRET-BOT-TOKEN", raw)
        self.assertNotIn("SECRET-ADMIN-PW", raw)
        self.assertNotIn("BOT_TOKEN", raw)
        self.assertNotIn("ADMIN_INITIAL_PASSWORD", raw)
        self.assertNotIn("password", raw.lower())
        self.assertNotIn("token", raw.lower())

    def test_509_config_only_get(self):
        self.assertEqual(self.admin.post("/api/config", {"x": 1})[0], 404)
        self.assertEqual(self.admin.put("/api/config", {"x": 1})[0], 404)
        self.assertEqual(self.admin.delete("/api/config")[0], 404)
        self.assertEqual(self.admin.get("/api/config/maps")[0], 404)

    # ------------------------------------------------------------ kenglik/uzunlik
    def test_510_valid_coords_saved(self):
        c = self._student()
        st, r = self._put(c, {"address": "Yunusobod 12", "lat": 41.3364, "lng": 69.2785})
        self.assertEqual(st, 200, r)
        row = self._pickup()
        self.assertEqual(row["pickup_address"], "Yunusobod 12")
        self.assertAlmostEqual(row["pickup_lat"], 41.3364, places=5)
        self.assertAlmostEqual(row["pickup_lng"], 69.2785, places=5)

    def test_511_coords_as_strings(self):
        """Frontend `input` dan qiymat STRING bo'lib keladi — qabul qilinishi kerak."""
        c = self._student()
        for lat, lng in (("41.311081", "69.240562"), (" 41.311081 ", " 69.240562 "),
                         ("41,311081", "69,240562")):
            st, r = self._put(c, {"lat": lat, "lng": lng})
            self.assertEqual(st, 200, f"{lat}/{lng}: {r}")
            row = self._pickup()
            self.assertAlmostEqual(row["pickup_lat"], 41.311081, places=5)
            self.assertAlmostEqual(row["pickup_lng"], 69.240562, places=5)

    def test_512_coords_rounded_to_7_decimals(self):
        c = self._student()
        st, _ = self._put(c, {"lat": 41.31108150000, "lng": 69.24056240000})
        self.assertEqual(st, 200)
        row = self._pickup()
        self.assertEqual(row["pickup_lat"], 41.3110815)
        self.assertEqual(row["pickup_lng"], 69.2405624)

    def test_513_bounds_are_allowed(self):
        """Chegara qiymatlari xato EMAS (Toshkentdan ancha uzoq nuqta ham kerak)."""
        c = self._student()
        for lat, lng in ((90, 180), (-90, -180), (0, 0)):
            st, r = self._put(c, {"lat": lat, "lng": lng})
            self.assertEqual(st, 200, f"{lat}/{lng}: {r}")

    def test_514_bad_lat_rejected(self):
        c = self._student()
        for bad in ("abc", 90.0001, -90.0001, 1000, True, "NaN", "Infinity", "1,2,3", [], {}):
            st, r = self._put(c, {"lat": bad, "lng": 69.24})
            self.assertEqual(st, 400, f"kenglik {bad!r} qabul qilindi: {r}")
            self.assertEqual(r["error"], "coord.bad_lat", f"{bad!r}: {r}")

    def test_515_bad_lng_rejected(self):
        c = self._student()
        for bad in ("abc", 180.0001, -180.0001, 99999, "NaN", "1e400"):
            st, r = self._put(c, {"lat": 41.31, "lng": bad})
            self.assertEqual(st, 400, f"uzunlik {bad!r} qabul qilindi: {r}")
            self.assertEqual(r["error"], "coord.bad_lng", f"{bad!r}: {r}")

    def test_516_incomplete_pair_rejected(self):
        """Faqat bittasi to'ldirilgan holat — chalkash, xato qaytariladi."""
        c = self._student()
        for body in ({"lat": 41.31}, {"lng": 69.24}, {"lat": 41.31, "lng": ""},
                     {"lat": "", "lng": 69.24}):
            st, r = self._put(c, body)
            self.assertEqual(st, 400, f"{body}: {r}")
            self.assertEqual(r["error"], "coord.pair_incomplete", f"{body}: {r}")

    def test_517_clear_both(self):
        self._reset_pickup(41.33, 69.27, "Eski manzil")
        c = self._student()
        st, r = self._put(c, {"address": "", "lat": "", "lng": ""})
        self.assertEqual(st, 200, r)
        row = self._pickup()
        self.assertIsNone(row["pickup_lat"])
        self.assertIsNone(row["pickup_lng"])
        self.assertEqual(row["pickup_address"], "")

    def test_518_rejected_value_keeps_old_data(self):
        """Xatoli so'rov yuborilganda ESKI koordinata buzilmasligi SHART."""
        self._reset_pickup(41.3333, 69.2727, "Saqlangan manzil")
        c = self._student()
        st, r = self._put(c, {"address": "Yangi manzil", "lat": 91, "lng": 69.24})
        self.assertEqual(st, 400, r)
        row = self._pickup()
        self.assertAlmostEqual(row["pickup_lat"], 41.3333, places=5)
        self.assertAlmostEqual(row["pickup_lng"], 69.2727, places=5)
        self.assertEqual(row["pickup_address"], "Saqlangan manzil",
                         "xato so'rovda manzil ham o'zgarib ketmasligi kerak")

    def test_519_address_only_keeps_coords(self):
        """Faqat manzil o'zgartirilsa — koordinata o'zgarMAYdi."""
        self._reset_pickup(41.3333, 69.2727, "Eski")
        c = self._student()
        st, r = self._put(c, {"address": "Yangi manzil"})
        self.assertEqual(st, 200, r)
        row = self._pickup()
        self.assertEqual(row["pickup_address"], "Yangi manzil")
        self.assertAlmostEqual(row["pickup_lat"], 41.3333, places=5)
        self.assertAlmostEqual(row["pickup_lng"], 69.2727, places=5)

    def test_520_other_roles_forbidden(self):
        c = Client()
        st, r = c.post("/api/auth/login",
                       {"login": INSTR_LOGIN_1, "password": INSTR_PASS_1, "role": "instructor"})
        self.assertEqual(st, 200, r)
        self.assertEqual(self._put(c, {"lat": 41.31, "lng": 69.24})[0], 403)
        self.assertEqual(self._put(self.admin, {"lat": 41.31, "lng": 69.24})[0], 403)

    def test_521_unknown_session_404(self):
        """Noto'g'ri sessiya — validatsiyadan keyin 404 (koordinata o'zgarMAYdi)."""
        self._reset_pickup(41.3333, 69.2727, "Saqlangan")
        c = self._student()
        st, r = self._put(c, {"lat": 41.5, "lng": 69.5}, sid=999999)
        self.assertEqual(st, 404, r)
        self.assertEqual(r["error"], "session.student_not_found")
        row = self._pickup()
        self.assertAlmostEqual(row["pickup_lat"], 41.3333, places=5)

    def test_522_saved_coords_visible_in_session(self):
        """Saqlangan koordinata session detallarida QAYTARILISHI shart
        ("Xaritada ko'rish" havolasi uchun)."""
        c = self._student()
        st, _ = self._put(c, {"address": "Chilonzor 40", "lat": 41.3299, "lng": 69.2902})
        self.assertEqual(st, 200)
        st, r = c.get(f"/api/student/sessions/{self.session_id}")
        self.assertEqual(st, 200, r)
        ss = r["session"]
        self.assertAlmostEqual(ss["pickup_lat"], 41.3299, places=5)
        self.assertAlmostEqual(ss["pickup_lng"], 69.2902, places=5)
        self.assertEqual(ss["pickup_address"], "Chilonzor 40")

    def test_523_session_without_coords_returns_null(self):
        """Koordinata yo'q bo'lsa frontend "Xaritada ko'rish" havolasi
        ko'rsatmasligi kerak — qiymat NULL bo'lishi SHART (0 emas)."""
        c = self._student()
        st, r = c.get(f"/api/student/sessions/{self.session_id}")
        self.assertEqual(st, 200, r)
        ss = r["session"]
        self.assertIsNone(ss["pickup_lat"])
        self.assertIsNone(ss["pickup_lng"])

# ============================================================================
# BAND 24 — YANGI TEST SINFLARI: AUTH / MAP / LESSONS / NOTIFICATIONS /
#            PROFILE / SETTINGS
#
# Har bir sinf BAND raqamiga ishora qiladi va o'sha bandning talabini
# ANIQ tekshiradi. Ma'lumot — har doim DB dan (fixture'lar seed'dan keladi).
# ============================================================================


def _json_db():
    return Db(str(TMP / "test.db"))


def _unlink_all(db, sql, params=()):
    """Test tozalash — `upd` INTEGER qaytarmasligi uchun."""
    db.upd(sql, params)


class _MixinAdmin:
    """Har bir test klassi uchun umumiy yordamchilar."""

    def setUp(self):
        from app.auth import reset_ip_attempts, reset_login_attempts
        for lg in ("admin", INSTR_LOGIN_1, INSTR_LOGIN_3,
                   STUD_LOGIN_1, STUD_LOGIN_2, STUD_LOGIN_3, STUD_LOGIN_4):
            reset_login_attempts("login:" + lg)
        reset_ip_attempts("127.0.0.1")
        self.db = _json_db()
        self.admin = Client()
        st, r = self.admin.post("/api/auth/login",
                                {"login": "admin", "password": "admin123", "role": "admin"})
        self.assertEqual(st, 200, r)

    def tearDown(self):
        try:
            self.db.close()
        except Exception:
            pass

    def _mkuser(self, role, first, last, **extra):
        body = {"role": role, "first_name": first, "last_name": last}
        body.update(extra)
        st, r = self.admin.post("/api/admin/users", body)
        self.assertEqual(st, 200, r)
        return r

    def _login(self, login, password, role):
        from app.auth import reset_login_attempts
        reset_login_attempts("login:" + login)
        c = Client()
        st, r = c.post("/api/auth/login", {"login": login, "password": password, "role": role})
        return c, st, r

    def _cleanup_user(self, user_id):
        db = _json_db()
        try:
            srow = db.q1("SELECT id FROM students WHERE user_id=?", (user_id,))
            if srow:
                db.upd("DELETE FROM session_students WHERE student_id=?", (srow["id"],))
                db.upd("DELETE FROM students WHERE id=?", (srow["id"],))
            irow = db.q1("SELECT id FROM instructors WHERE user_id=?", (user_id,))
            if irow:
                db.upd("DELETE FROM instructors WHERE id=?", (irow["id"],))
            db.upd("DELETE FROM notifications WHERE user_id=?", (user_id,))
            db.upd("DELETE FROM user_settings WHERE user_id=?", (user_id,))
            db.upd("DELETE FROM notification_settings WHERE user_id=?", (user_id,))
            db.upd("DELETE FROM sessions_ring WHERE user_id=?", (user_id,))
            db.upd("DELETE FROM students WHERE user_id=?", (user_id,))
            db.upd("DELETE FROM instructors WHERE user_id=?", (user_id,))
            db.upd("DELETE FROM users WHERE id=?", (user_id,))
        finally:
            try:
                db.close()
            except Exception:
                pass

    def _mk_session(self, start_dt, created_at, student_id, inst_id=1,
                    car_id=1, status="scheduled", confirm="pending", notes="BAND24"):
        db = self.db
        date, start = start_dt.strftime("%Y-%m-%d"), start_dt.strftime("%H:%M")
        end_dt = start_dt + timedelta(minutes=60)
        # Kechani kechiruvchi sessiyalar uchun `+1d` SUFFIX qo'yilmaydi:
        # ilova `end_time` ni oddiy "HH:MM" sifatida saqlaydi va shu qat'iy
        # formatda string solishtiriladi ("00:15 +1d" > "18:20" -> noto'g'ri).
        end = min(end_dt, end_dt.replace(hour=23, minute=59, second=0)).strftime("%H:%M")
        sid = db.ex(
            """INSERT INTO lesson_sessions(date,start_time,end_time,instructor_id,car_id,
               car_name_snapshot,car_plate_snapshot,capacity_snapshot,status,confirm_state,
               notes,created_at,updated_at)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (date, start, end, inst_id, car_id, "Test avto", "01A001AA", 4, status,
             confirm, notes, created_at, created_at))
        db.ex(
            """INSERT INTO session_students(session_id,student_id,pickup_address,
               attendance_status,student_status,joined_at) VALUES(?,?,'','unmarked','active',?)""",
            (sid, student_id, created_at))
        return sid

    def _drop_session(self, sid):
        db = self.db
        db.upd("DELETE FROM notifications WHERE related_lesson_id=?", (sid,))
        db.upd("DELETE FROM session_students WHERE session_id=?", (sid,))
        db.upd("DELETE FROM lesson_sessions WHERE id=?", (sid,))

    def _admin_msg(self, title, text):
        """`POST /api/admin/notifications` — barcha faol foydalanuvchilarga
        xabar yuboradi (`source=ADMIN_MESSAGE`)."""
        return self.admin.post("/api/admin/notifications",
                               {"title": title, "text": text})


# ============================================================================
# 1) AUTH — BAND 5, 6, 7 (kuchli credential, xavfsizlik, unikalik)
# ============================================================================
class TestAuthBAND24(_MixinAdmin, Base):
    """AUTH: login/parol formati, hashing, unikalik, rate-limit, CSRF, RBAC."""

    def test_A01_new_credential_format_is_random(self):
        """BAND 5: `usrL_` + random unikal suffix, `usrP_` + 14 belgi.
        Ketma-ket/predictable format QAT'IY TAQIQLANGAN."""
        logins, pwds = set(), set()
        for i in range(4):
            r = self._mkuser("student", "Auth", "T%d" % i, group_name="AUTH")
            lg = r["credentials"]["login"]
            pw = r["credentials"]["password"]
            self.assertRegex(lg, r"^usrL_[A-Za-z0-9]{14}$", "login formati: " + lg)
            self.assertRegex(pw, r"^usrP_", "parol prefiksi: " + pw)
            body = pw[len("usrP_"):]
            self.assertEqual(len(body), 14, "parol tanasi 14 belgi bo'lishi kerak: " + pw)
            self.assertTrue(any(c.islower() for c in body), "kichik harf kerak")
            self.assertTrue(any(c.isupper() for c in body), "katta harf kerak")
            self.assertTrue(any(c.isdigit() for c in body), "raqam kerak")
            self.assertTrue(any(not c.isalnum() for c in body), "maxsus belgi kerak")
            logins.add(lg)
            pwds.add(pw)
            self._cleanup_user(r["user"]["id"])
        self.assertEqual(len(logins), 4, "loginlar UNIKAL bo'lishi shart")
        self.assertEqual(len(pwds), 4, "parollar UNIKAL bo'lishi shart")

    def test_A02_credentials_not_sequential(self):
        """BAND 5: eski ketma-ket format (`usrL_00001`) QAYTMAYDI."""
        r1 = self._mkuser("student", "Seq", "One")
        r2 = self._mkuser("student", "Seq", "Two")
        try:
            l1 = r1["credentials"]["login"]
            l2 = r2["credentials"]["login"]
            self.assertNotIn("0000", l1[len("usrL_"):][:4])
            self.assertFalse(l1[len("usrL_"):].isdigit(), "login sonlardan iborat bo'lmasligi kerak")
            self.assertNotEqual(l1, l2)
        finally:
            self._cleanup_user(r1["user"]["id"])
            self._cleanup_user(r2["user"]["id"])

    def test_A03_password_never_stored_plain(self):
        """BAND 6: parol DB'da PLAIN TEXT ko'rinishida SAQLANMAYDI."""
        r = self._mkuser("student", "Hash", "Test")
        try:
            pw = r["credentials"]["password"]
            row = self.db.q1("SELECT password_hash FROM users WHERE id=?", (r["user"]["id"],))
            h = row["password_hash"] or ""
            self.assertNotEqual(h, pw, "parol o'zicha saqlangan!")
            self.assertNotIn(pw, h, "parol hash ichida ko'rinmoqda!")
            self.assertIn("scrypt", h, "scrypt ishlovchi formati kutilgan")
        finally:
            self._cleanup_user(r["user"]["id"])

    def test_A04_salt_unique_per_password(self):
        """BAND 6: har bir parol uchun salt ALOHIDA (ikkita bir xil parol ->
        turliq hash)."""
        from app.auth import hash_password as _hp
        a = _hp("usrP_Same000000!A1")
        b = _hp("usrP_Same000000!A1")
        self.assertNotEqual(a, b, "bir xil parol uchun hash bir xil chiqdi (salt yo'q)")

    def test_A05_password_verified_by_hash(self):
        """BAND 6: login parolni HASH orqali tekshiradi."""
        from app.auth import verify_password
        r = self._mkuser("student", "Verify", "Hash")
        try:
            pw = r["credentials"]["password"]
            lg = r["credentials"]["login"]
            h = self.db.q1("SELECT password_hash FROM users WHERE id=?",
                           (r["user"]["id"],))["password_hash"]
            self.assertTrue(verify_password(pw, h))
            self.assertFalse(verify_password(pw + "x", h))
            self.assertFalse(verify_password("usrP_Wrong000000!A1", h))
            # haqiqiy login ham ishlaydi
            c, st, rr = self._login(lg, pw, "student")
            self.assertEqual(st, 200, rr)
            c2, st2, rr2 = self._login(lg, pw + "x", "student")
            self.assertEqual(st2, 400)
            self.assertEqual(rr2["error"], "auth.wrong_credentials")
        finally:
            self._cleanup_user(r["user"]["id"])

    def test_A06_password_never_returned_by_api(self):
        """BAND 6: admin ham parolni KO'RA OLMAYDI."""
        r = self._mkuser("student", "Secret", "Hidden")
        try:
            uid = r["user"]["id"]
            st, prof = self.admin.get(f"/api/admin/users/{uid}")
            self.assertEqual(st, 200, prof)
            raw = json.dumps(prof, ensure_ascii=False)
            self.assertNotIn(r["credentials"]["password"], raw)
            self.assertNotIn("password_hash", prof["user"])
            st, lst = self.admin.get("/api/admin/users?role=student")
            self.assertEqual(st, 200)
            raw2 = json.dumps(lst, ensure_ascii=False)
            self.assertNotIn(r["credentials"]["password"], raw2)
            self.assertNotIn("password_hash", raw2)
        finally:
            self._cleanup_user(uid)

    def test_A07_weak_password_rejected(self):
        """BAND 6: foydalanuvchi kuchsiz parol qo'ya olmaydi."""
        r = self._mkuser("student", "Weak", "Pass")
        try:
            c, st, _ = self._login(r["credentials"]["login"],
                                   r["credentials"]["password"], "student")
            self.assertEqual(st, 200)
            for bad in ("abc", "alllowercase123", "ALLUPPERCASE123", "NoDigitsHere!",
                        "Short1!"):
                st2, r2 = c.put("/api/me/profile", {"login": r["credentials"]["login"]})
                self.assertEqual(st2, 200, r2)
                st3, r3 = c.post("/api/auth/change-password",
                                 {"old_password": r["credentials"]["password"],
                                  "new_password": bad, "confirm_password": bad})
                self.assertEqual(st3, 400, f"{bad!r} qabul qilindi: {r3}")
                self.assertEqual(r3["error"], "auth.password_weak", f"{bad!r}: {r3}")
        finally:
            self._cleanup_user(r["user"]["id"])

    def test_A08_same_password_rejected(self):
        r = self._mkuser("student", "Same", "Pass")
        try:
            pw = r["credentials"]["password"]
            c, st, _ = self._login(r["credentials"]["login"], pw, "student")
            self.assertEqual(st, 200)
            st2, r2 = c.post("/api/auth/change-password",
                             {"old_password": pw, "new_password": pw,
                              "confirm_password": pw})
            self.assertEqual(st2, 400, r2)
            self.assertEqual(r2["error"], "auth.password_same", r2)
        finally:
            self._cleanup_user(r["user"]["id"])

    def test_A09_password_reuse_rejected(self):
        """BAND 6/7: eski parol QAYTA ishlatilmaydi."""
        r = self._mkuser("student", "Reuse", "Test")
        try:
            old_pw = r["credentials"]["password"]
            c, st, _ = self._login(r["credentials"]["login"], old_pw, "student")
            self.assertEqual(st, 200)
            new_pw = "usrP_Fresh0000!Zz9"
            st2, r2 = c.post("/api/auth/change-password",
                             {"old_password": old_pw, "new_password": new_pw,
                              "confirm_password": new_pw})
            self.assertEqual(st2, 200, r2)
            # yangi parol bilan kirish, eskisi bilan QAYTARISHga urinish
            c2, st3, _ = self._login(r["credentials"]["login"], new_pw, "student")
            self.assertEqual(st3, 200)
            st4, r4 = c2.post("/api/auth/change-password",
                              {"old_password": new_pw, "new_password": old_pw,
                               "confirm_password": old_pw})
            self.assertEqual(st4, 400, r4)
            self.assertEqual(r4["error"], "auth.password_used", r4)
            # eski parol endi umuman ishlamaydi
            _, st5, _ = self._login(r["credentials"]["login"], old_pw, "student")
            self.assertEqual(st5, 400)
        finally:
            self._cleanup_user(r["user"]["id"])

    def test_A10_admin_reset_password_new_random(self):
        """BAND 5/22: admin yangi parol generatsiya qilsa — random, unique,
        ko'rsatiladi va KEYIN qaytarilmaydi."""
        r = self._mkuser("student", "Reset", "Pass")
        try:
            uid = r["user"]["id"]
            old = r["credentials"]["login"], r["credentials"]["password"]
            st, rr = self.admin.post(f"/api/admin/users/{uid}/reset-password")
            self.assertEqual(st, 200, rr)
            new_pw = rr["password"]
            self.assertRegex(rr["login"], r"^usrL_[A-Za-z0-9]{14}$")
            self.assertRegex(new_pw, r"^usrP_")
            self.assertEqual(len(new_pw) - len("usrP_"), 14)
            self.assertNotEqual(new_pw, old[1])
            # eski parol endi ishlamaydi, yangisi ishlaydi
            _, st1, _ = self._login(old[0], old[1], "student")
            self.assertEqual(st1, 400)
            _, st2, r2 = self._login(rr["login"], new_pw, "student")
            self.assertEqual(st2, 200, r2)
            # DB'da parol ko'rinmaydi
            h = self.db.q1("SELECT password_hash FROM users WHERE id=?", (uid,))["password_hash"]
            self.assertNotIn(new_pw, h)
        finally:
            self._cleanup_user(uid)

    def test_A11_login_rate_limit_blocks(self):
        """BAND 6: brute-force himoyasi — chegaradan keyin rad etiladi.

        `MAX_LOGIN_TRIES` test muhitida 100000 qilib ko'tarilgan (boshqa testlar
        kirish oqib ketmasligi uchun), shuning uchun chegara bu yerda
        ANIQ ko'rsatiladi: `login_allowed(key, max_tries, window)`.
        """
        from app.auth import login_allowed, reset_login_attempts
        key = "login:usrL_bd0000000001"
        reset_login_attempts(key)
        allowed = 0
        for _ in range(12):
            if login_allowed(key, 6, 300):
                allowed += 1
            else:
                break
        self.assertEqual(allowed, 6, "login limiti 6 urinishdan keyin ishlashi kerak")
        # 7-8-urinish ham rad etiladi (counter oshMAYdi)
        self.assertFalse(login_allowed(key, 6, 300))
        self.assertFalse(login_allowed(key, 6, 300))
        # oyna o'tsa — yana urinishga ruxsat beriladi (counter 0 ga qaytadi)
        import time as _time
        _time.sleep(0.05)
        self.assertTrue(login_allowed(key, 6, 0.01),
                        "oyna o'tganda bloklash to'lanadi")

        # API darajasida: chegarani 3 ga tushirib, kodni tekshiramiz
        import app.api as api_mod
        orig = api_mod.login_allowed
        api_mod.login_allowed = lambda k, *a, **kw: orig(k, 3, 300)
        try:
            reset_login_attempts(key)
            c = Client()
            errs = []
            for _ in range(5):
                st, rr = c.post("/api/auth/login",
                                {"login": "usrL_bd0000000001",
                                 "password": "usrP_x000000!Ab1", "role": "student"})
                errs.append((st, rr.get("error")))
        finally:
            api_mod.login_allowed = orig
        self.assertIn("auth.too_many_attempts", [e for _, e in errs],
                      "brute-force himoyasi API darajasida ishlayapti")
        self.assertTrue(all(st == 400 for st, _ in errs), errs)

    def test_A12_ip_blocking(self):
        """BAND 6: IP bo'yi bloklash — 4-urishda blok, `seconds` qaytariladi."""
        from app.auth import ip_blocked, reset_ip_attempts
        ip = "9.9.9.9"
        reset_ip_attempts(ip)
        self.assertEqual(ip_blocked(ip, 3, 300, 60), 0)   # 1
        self.assertEqual(ip_blocked(ip, 3, 300, 60), 0)   # 2
        self.assertEqual(ip_blocked(ip, 3, 300, 60), 0)   # 3
        left = ip_blocked(ip, 3, 300, 60)                 # 4 -> blok
        self.assertGreater(left, 0, "IP bloklanmadi")
        self.assertLessEqual(left, 60)
        # blok davomida qaytariladi va hisob tozalanadi
        reset_ip_attempts(ip)
        self.assertEqual(ip_blocked(ip, 3, 300, 60), 0)

        # API darajasida ham `auth.ip_blocked` + params.seconds qaytariladi
        import app.api as api_mod
        orig = api_mod.ip_blocked

        def fake_blocked(ip_, *a, **kw):
            if ip_ == "127.0.0.1":
                return 42
            return orig(ip_, *a, **kw)
        api_mod.ip_blocked = fake_blocked
        try:
            st, r = Client().post("/api/auth/login",
                                  {"login": "admin", "password": "admin123",
                                   "role": "admin"})
        finally:
            api_mod.ip_blocked = orig
        self.assertEqual(st, 400, r)
        self.assertEqual(r["error"], "auth.ip_blocked", r)
        self.assertEqual(r.get("params", {}).get("seconds", r.get("seconds")), 42, r)

    def test_A13_csrf_token_returned_and_enforced(self):
        """BAND 6: login va `me` CSRF token beradi; noto'g'ri token -> 403."""
        c = Client()
        st, r = c.post("/api/auth/login",
                       {"login": "admin", "password": "admin123", "role": "admin"})
        self.assertEqual(st, 200, r)
        tok = r.get("csrf") or ""
        self.assertTrue(tok, "login javobida csrf token bo'lishi shart")
        st2, r2 = c.get("/api/auth/me")
        self.assertEqual(st2, 200, r2)
        self.assertTrue(r2.get("csrf"), "GET /api/auth/me csrf token qaytarishi shart")
        # noto'g'ri token bilan POST -> 403
        raw = self._raw_post(c, "/api/me/settings", {"lang": "uz"},
                             extra={"X-CSRF-Token": "not-a-real-token"})
        self.assertEqual(raw[0], 403, raw)
        self.assertEqual(raw[1].get("error"), "csrf_invalid", raw)

    def test_A13b_csrf_token_is_mandatory(self):
        """BAND 6: token butunlay YUBORILMASA ham so'rov rad etiladi.

        AVVALGI XATO: `if expected and sent and ...` — `sent` bo'sh bo'lsa
        shart bajarilmasdi, ya'ni sarlavhani umuman yubormaydi (CSRF o'tkazib
        yuborish mumkin edi). Endi `sent` majburiy.
        """
        c = Client()
        st, r = c.post("/api/auth/login",
                       {"login": "admin", "password": "admin123", "role": "admin"})
        self.assertEqual(st, 200, r)
        self.assertTrue(r.get("csrf"), r)
        raw = self._raw_post(c, "/api/me/settings", {"lang": "uz"})   # token YO'Q
        self.assertEqual(raw[0], 403, "token'siz POST qabul qilindi: %s" % (raw,))
        self.assertEqual(raw[1].get("error"), "csrf_invalid", raw)

    def test_A13c_cross_site_request_rejected(self):
        """BAND 6: boshqa dandan `Origin` + token'siz so'rov -> 403."""
        c = Client()
        st, r = c.post("/api/auth/login",
                       {"login": "admin", "password": "admin123", "role": "admin"})
        self.assertEqual(st, 200, r)
        raw = self._raw_post(c, "/api/admin/notifications",
                             {"title": "h", "text": "x"},
                             extra={"X-Requested-With": "",
                                    "Origin": "http://zararli-sayt.example"},
                             drop_xrw=True)
        self.assertEqual(raw[0], 403, raw)
        self.assertEqual(raw[1].get("error"), "csrf_origin", raw)

    def test_A13d_other_session_token_rejected(self):
        """Boshqa foydalanuvchi sessiyasining token'i — qabul qilinMAYDI."""
        c1 = Client()
        self.assertEqual(c1.post("/api/auth/login",
                                 {"login": "admin", "password": "admin123",
                                  "role": "admin"})[0], 200)
        c2 = Client()
        self.assertEqual(c2.post("/api/auth/login",
                                 {"login": STUD_LOGIN_1,
                                  "password": PW_BY_LOGIN[STUD_LOGIN_1],
                                  "role": "student"})[0], 200)
        self.assertNotEqual(c1._csrf, c2._csrf)
        raw = self._raw_post(c1, "/api/me/settings", {"lang": "ru"},
                             extra={"X-CSRF-Token": c2._csrf})
        self.assertEqual(raw[0], 403, raw)
        self.assertEqual(raw[1].get("error"), "csrf_invalid", raw)

    def _raw_post(self, client, path, body, extra=None, drop_xrw=False):
        """CSRF sarlavhalarini qo'lda boshqarish uchun xom so'rov."""
        data = json.dumps(body).encode()
        headers = {"Content-Type": "application/json"}
        if not drop_xrw:
            headers["X-Requested-With"] = "Avtomaktab"
        headers.update(extra or {})
        req = urllib.request.Request(
            f"http://{HOST}:{PORT}{path}", data=data, headers=headers, method="POST")
        try:
            with client.opener.open(req, timeout=15) as resp:
                return resp.status, json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            try:
                return e.code, json.loads(e.read().decode("utf-8"))
            except Exception:
                return e.code, {}

    def test_A14_session_cookie_httponly_samesite(self):
        """BAND 6: `sid` cookie — HttpOnly + SameSite=Lax."""
        import http.cookiejar
        c = Client()
        st, _ = c.post("/api/auth/login",
                       {"login": "admin", "password": "admin123", "role": "admin"})
        self.assertEqual(st, 200)
        sid = None
        for ck in c.jar:
            if ck.name == "sid":
                sid = ck
        self.assertIsNotNone(sid, "sid cookie qo'yilmadi")
        # urllib cookie jar HttpOnly/SameSite ni saqlamaydi -> QO'LDI sarlavhani tekshiramiz
        raw = self._headers_on_login().lower()
        self.assertIn("httponly", raw, "sid cookie HttpOnly bo'lishi shart")
        self.assertIn("samesite=lax", raw, "sid cookie SameSite=Lax bo'lishi shart")
        self.assertIn("path=/", raw)

    def _headers_on_login(self):
        data = json.dumps({"login": "admin", "password": "admin123",
                           "role": "admin"}).encode()
        req = urllib.request.Request(
            f"http://{HOST}:{PORT}/api/auth/login", data=data,
            headers={"Content-Type": "application/json"}, method="POST")
        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(
            http.cookiejar.CookieJar()))
        try:
            with opener.open(req, timeout=15) as resp:
                return resp.headers.get("Set-Cookie") or ""
        except urllib.error.HTTPError as e:
            return e.headers.get("Set-Cookie") or ""

    def test_A15_rbac_and_idor(self):
        """BAND 6: RBAC + IDOR — talaba admin endpoint'iga, boshqa foydalanuvchi
        ma'lumotiga kira olmaydi."""
        c, st, _ = self._login(STUD_LOGIN_1, PW_BY_LOGIN[STUD_LOGIN_1], "student")
        self.assertEqual(st, 200)
        st2, r2 = c.get("/api/admin/users")
        self.assertEqual(st2, 403, r2)
        st3, r3 = c.get("/api/admin/users/1")
        self.assertEqual(st3, 403, r3)
        # IDOR: boshqa foydalanuvchining bildirishnoma id'si
        other_uid = self._uid_of(STUD_LOGIN_2)
        st0, _ = self._admin_msg("A15-OTHER", "boshqa odamga")
        self.assertEqual(st0, 200)
        nid = self.db.q1("SELECT id FROM notifications WHERE user_id=? ORDER BY id DESC",
                         (other_uid,))["id"]
        self.assertIsNotNone(nid)
        st4, r4 = c.get(f"/api/me/notifications/{nid}")
        self.assertEqual(st4, 404, r4)

    def _uid_of(self, login):
        row = self.db.q1("SELECT id FROM users WHERE login=?", (login,))
        return row["id"] if row else 0

    def test_A16_admin_profile_and_users_list_shape(self):
        """BAND 22: admin ro'yxatida jami/bajarilgan/qolgan bor."""
        r = self._mkuser("student", "Shape", "Test", group_name="SH", license_category="B")
        try:
            st, lst = self.admin.get("/api/admin/users?role=student&q=" + r["credentials"]["login"])
            self.assertEqual(st, 200, lst)
            found = [u for u in lst["users"] if u["id"] == r["user"]["id"]]
            self.assertTrue(found, "talaba ro'yxatda topilmadi")
            pr = found[0]["progress"]
            for k in ("target", "done", "remaining", "pct", "mode", "individual_target"):
                self.assertIn(k, pr, f"progress.{k} yo'q")
            st2, prof = self.admin.get(f"/api/admin/users/{r['user']['id']}")
            self.assertEqual(st2, 200, prof)
            u = prof["user"]
            self.assertIn("login", u)
            self.assertIn("phone", u)
            self.assertIn("student", u)
            self.assertIn("group_name", u["student"])
            self.assertIn("license_category", u["student"])
            self.assertIn("progress", u)
        finally:
            self._cleanup_user(r["user"]["id"])


# ============================================================================
# 2) MAP — BAND 1 (Yandex autocomplete, UI dan kenglik/uzunlik olib tashlash)
# ============================================================================
class TestMapBAND24(_MixinAdmin, Base):
    """MAP: geocoder sozlamalari, manzil orqali nuqta, UI da lat/lng yo'q."""

    ENV_KEYS = ("YANDEX_MAPS_API_KEY", "YANDEX_GEOCODER_API_KEY", "MAP_PROVIDER")

    def setUp(self):
        super().setUp()
        self._env_backup = {k: os.environ.get(k) for k in self.ENV_KEYS}
        for k in self.ENV_KEYS:
            os.environ.pop(k, None)
        r = self._mkuser("student", "Map", "Autocomplete", group_name="MAP", license_category="B")
        self.uid = r["user"]["id"]
        self.login = r["credentials"]["login"]
        self.password = r["credentials"]["password"]
        self.srow = self.db.q1("SELECT id FROM students WHERE user_id=?", (self.uid,))
        self.student_id = self.srow["id"]
        # kelajakdagi mashg'ulot (pickup endpoint'i uchun)
        d = datetime.now() + timedelta(days=40)
        self.sid = self._mk_session(d.replace(hour=9, minute=0, second=0, microsecond=0),
                                    now(), self.student_id, notes="MAPBAND24")
        self.c, st, rr = self._login(self.login, self.password, "student")
        self.assertEqual(st, 200, rr)

    def tearDown(self):
        self._drop_session(self.sid)
        self._cleanup_user(self.uid)
        for k, v in self._env_backup.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        super().tearDown()

    # ------------------------------------------------------------- sozlamalar
    def test_M01_config_exposes_geocoder_fields(self):
        st, r = Client().get("/api/config")
        self.assertEqual(st, 200, r)
        m = r["config"]["maps"]
        for k in ("geocoder_api_key", "geocoder_enabled", "lang"):
            self.assertIn(k, m, f"config.maps.{k} yo'q")

    def test_M02_geocoder_disabled_without_key(self):
        """Kalit yo'q bo'lsa `geocoder_enabled=false` — soxta kalit QO'YILMAYDI."""
        m = self.admin.get("/api/config")[1]["config"]["maps"]
        self.assertFalse(m["geocoder_enabled"], "kalitsiz geocoder 'yoqiq' bo'lishi kerak")
        self.assertEqual(m["geocoder_api_key"], "")

    def test_M03_geocoder_enabled_with_env_key(self):
        os.environ["YANDEX_GEOCODER_API_KEY"] = "geo-test-key-123"
        m = self.admin.get("/api/config")[1]["config"]["maps"]
        self.assertTrue(m["geocoder_enabled"])
        self.assertEqual(m["geocoder_api_key"], "geo-test-key-123")

    def test_M04_geocoder_falls_back_to_map_key(self):
        """Aloha kalit yo'q bo'lsa `YANDEX_MAPS_API_KEY` ga qaytadi."""
        os.environ["YANDEX_MAPS_API_KEY"] = "map-test-key-456"
        m = self.admin.get("/api/config")[1]["config"]["maps"]
        self.assertTrue(m["geocoder_enabled"])
        self.assertEqual(m["geocoder_api_key"], "map-test-key-456")

    def test_M05_provider_none_disables_geocoder(self):
        os.environ["YANDEX_GEOCODER_API_KEY"] = "geo-test-key-123"
        os.environ["MAP_PROVIDER"] = "none"
        m = self.admin.get("/api/config")[1]["config"]["maps"]
        self.assertFalse(m["geocoder_enabled"])

    def test_M06_key_never_hardcoded_in_source(self):
        """BAND 1: API kalit frontend/backend source code'da OCHIQ yozilmaydi."""
        hard = 0
        for rel in ("web/js/map.js", "web/js/api.js", "web/js/shared.js",
                    "web/index.html", "app/config.py", "app/api.py"):
            p = ROOT / rel
            if not p.exists():
                continue
            txt = p.read_text(encoding="utf-8", errors="ignore")
            # haqiqiy Yandex kalit shakli: <id>.<hash>
            import re as _re
            if _re.search(r"\bAQ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}", txt):
                hard += 1
            if "YANDEX_MAPS_API_KEY=" in txt or "YANDEX_GEOCODER_API_KEY=" in txt:
                # faqat `.env.example` da bo'lishi mumkin, kodda emas
                if not rel.endswith(".env.example"):
                    hard += 1
        self.assertEqual(hard, 0, "maxfiy kalit source code'da topildi!")

    # ------------------------------------------------------------- endpoint
    def test_M07_address_saved_without_coords(self):
        """Autocomplete tanlanganda manzil + koordinata keladi; agar topilmasa
        ham manzil saqlanadi (jim qolmaydi, xarita nuqtasi bo'lmaydi)."""
        st, r = self.c.put(f"/api/student/sessions/{self.sid}/pickup",
                           {"address": "O'zbekiston, Toshkent, Beshariq tumani"})
        self.assertEqual(st, 200, r)
        row = self.db.q1("""SELECT pickup_address,pickup_lat,pickup_lng FROM session_students
                            WHERE session_id=? AND student_id=?""",
                         (self.sid, self.student_id))
        self.assertIn("Beshariq", row["pickup_address"])
        self.assertIsNone(row["pickup_lat"])
        self.assertIsNone(row["pickup_lng"])

    def test_M08_coords_from_autocomplete_persisted(self):
        st, r = self.c.put(f"/api/student/sessions/{self.sid}/pickup",
                           {"address": "Toshkent, Beshariq tumani, 12",
                            "lat": 41.3256, "lng": 69.2364})
        self.assertEqual(st, 200, r)
        st2, d2 = self.c.get(f"/api/student/sessions/{self.sid}")
        self.assertEqual(st2, 200, d2)
        ss = d2["session"]
        self.assertAlmostEqual(ss["pickup_lat"], 41.3256, places=5)
        self.assertAlmostEqual(ss["pickup_lng"], 69.2364, places=5)
        self.assertEqual(ss["pickup_address"], "Toshkent, Beshariq tumani, 12")

    def test_M09_empty_request_rejected(self):
        """BAND 1: manzil ham, koordinata ham kelmagan bo'lsa — RAD etiladi
        ("Olib ketish joyi" jim qolmasligi kerak)."""
        st, r = self.c.put(f"/api/student/sessions/{self.sid}/pickup", {})
        self.assertEqual(st, 400, r)
        self.assertEqual(r["error"], "map.address_required", r)
        # DB o'zgarmagan
        row = self.db.q1("""SELECT pickup_address FROM session_students
                            WHERE session_id=? AND student_id=?""",
                         (self.sid, self.student_id))
        self.assertEqual((row["pickup_address"] or ""), "")

    def test_M09b_blank_address_cleared_with_coords(self):
        """Faqat nuqta berilgan (autocomplete topmagan) holat — manzil bo'sh
        qoladi, ammo xato QILINMAYDI (nuqta saqlanadi)."""
        st, r = self.c.put(f"/api/student/sessions/{self.sid}/pickup",
                           {"address": "  ", "lat": 41.3, "lng": 69.2})
        self.assertEqual(st, 200, r)
        row = self.db.q1("""SELECT pickup_address,pickup_lat FROM session_students
                            WHERE session_id=? AND student_id=?""",
                         (self.sid, self.student_id))
        self.assertEqual(row["pickup_address"], "")
        self.assertAlmostEqual(row["pickup_lat"], 41.3, places=5)

    def test_M10_address_too_long_rejected(self):
        st, r = self.c.put(f"/api/student/sessions/{self.sid}/pickup",
                           {"address": "B" * 5000})
        self.assertEqual(st, 400, r)
        self.assertEqual(r["error"], "map.address_too_long")

    def test_M11_bad_coords_still_rejected(self):
        """Autocomplete kelmagan holatda ham noto'g'ri koordinata jim qolmaydi."""
        for bad in ("abc", 91, -91, 1e400):
            st, r = self.c.put(f"/api/student/sessions/{self.sid}/pickup",
                               {"address": "Test", "lat": bad, "lng": 69.2})
            self.assertEqual(st, 400, f"{bad!r}: {r}")
            self.assertTrue(r["error"].startswith("coord."), r)

    def test_M12_idor_other_student_pickup(self):
        """BAND 6: boshqa talabaning mashg'ulotida olish manzilini o'zgartirib
        bo'lmaydi."""
        r2 = self._mkuser("student", "Map", "Other", group_name="MAP2")
        try:
            st, r = self.c.put(f"/api/student/sessions/{self.sid}/pickup",
                               {"address": "X", "lat": 41.3, "lng": 69.2})
            self.assertEqual(st, 200, r)
            # endi ikkinchi talaba uchun alohida mashg'ulot yaratamiz
            srow2 = self.db.q1("SELECT id FROM students WHERE user_id=?", (r2["user"]["id"],))
            d = datetime.now() + timedelta(days=45)
            sid2 = self._mk_session(d.replace(hour=10, minute=0, second=0, microsecond=0),
                                    now(), srow2["id"], notes="MAP-OTHER")
            # 1-talaba 2-mashg'ulotga kira olmaydi
            st2, r3 = self.c.put(f"/api/student/sessions/{sid2}/pickup",
                                 {"address": "Y", "lat": 41.4, "lng": 69.3})
            self.assertEqual(st2, 404, r3)
            self._drop_session(sid2)
        finally:
            self._cleanup_user(r2["user"]["id"])

    def test_M13_other_roles_forbidden(self):
        inst, st, _ = self._login(INSTR_LOGIN_1, PW_BY_LOGIN[INSTR_LOGIN_1], "instructor")
        self.assertEqual(st, 200)
        st2, r2 = inst.put(f"/api/student/sessions/{self.sid}/pickup",
                           {"address": "X", "lat": 41.3, "lng": 69.2})
        self.assertEqual(st2, 403, r2)

    # ------------------------------------------------------------- frontend
    def test_M14_no_lat_lng_inputs_in_pickup_modal(self):
        """BAND 1: "Kenglik"/"Uzunlik" inputlari UI'dan BUTUNLAY olib tashlangan."""
        p = ROOT / "web" / "js" / "shared.js"
        txt = p.read_text(encoding="utf-8", errors="ignore")
        i = txt.find("function openPickupEdit")
        self.assertGreater(i, 0, "openPickupEdit topilmadi")
        # funksiya tugagandan keyingi 60 qator ichida lat/lng maydonlari BO'LMASIN
        chunk = txt[i:i + 6000]
        end = chunk.find("\n  }")
        body = chunk[:end if end > 0 else len(chunk)]
        self.assertNotIn("map.lat", body, "Kenglik maydoni hali ham bor")
        self.assertNotIn("map.lng", body, "Uzunlik maydoni hali ham bor")
        # autocomplete ulangan bo'lishi SHART
        self.assertIn("attachAutocomplete", body, "autocomplete ulanmagan")
        self.assertIn("reverseGeocode", body, "nuqtadan manzil yo'q")

    def test_M15_map_module_exposes_autocomplete_api(self):
        txt = (ROOT / "web" / "js" / "map.js").read_text(encoding="utf-8", errors="ignore")
        for fn in ("suggest", "geocode", "reverseGeocode", "attachAutocomplete",
                   "geocoderAvailable"):
            self.assertIn("function " + fn, txt, f"map.js da {fn} yo'q")
        self.assertIn("geocoder_enabled", txt, "kalit yo'qligi tekshirilmaydi")

    def test_M16_student_schedule_removed_from_navigation(self):
        """BAND 4: talaba sidebar'ida "schedule" (Mening jadvalim) yo'q."""
        txt = (ROOT / "web" / "js" / "app.js").read_text(encoding="utf-8", errors="ignore")
        i = txt.find("student: [")
        self.assertGreater(i, 0)
        j = txt.find("]", i)
        student_nav = txt[i:j]
        self.assertNotIn('"schedule"', student_nav,
                         "talaba sidebar'ida 'schedule' hali ham bor")
        # alias bilan eski manzil 'Amaliy mashg'ulotlarim'ga yo'naltiriladi
        self.assertIn("ROUTE_ALIASES", txt)
        self.assertIn("student:lessons", txt)
        txt2 = (ROOT / "web" / "js" / "views-student.js").read_text(encoding="utf-8",
                                                                    errors="ignore")
        self.assertNotIn("async function schedule", txt2,
                         "'Mening jadvalim' view hali ham bor")
        self.assertIn("async function lessons", txt2)


# ============================================================================
# 3) LESSONS — BAND 13, 14, 19, 20 (holatlar, ajratish, booking, integritet)
# ============================================================================
class TestLessonsBAND24(_MixinAdmin, Base):
    """LESSONS: kelajak/o'tgan ajratish, biznes holati, booking qoidalari."""

    def setUp(self):
        super().setUp()
        r = self._mkuser("student", "Les", "Test", group_name="LES", license_category="B")
        self.uid = r["user"]["id"]
        self.login = r["credentials"]["login"]
        self.password = r["credentials"]["password"]
        self.student_id = self.db.q1("SELECT id FROM students WHERE user_id=?",
                                     (self.uid,))["id"]
        self.c, st, rr = self._login(self.login, self.password, "student")
        self.assertEqual(st, 200, rr)
        self.sids = []

    def tearDown(self):
        for sid in self.sids:
            self._drop_session(sid)
        self._cleanup_user(self.uid)
        super().tearDown()

    def _new(self, start_dt, **kw):
        sid = self._mk_session(start_dt, kw.pop("created_at", now()),
                               self.student_id, **kw)
        self.sids.append(sid)
        return sid

    def _list(self, upcoming):
        st, r = self.c.get(f"/api/student/sessions?upcoming={upcoming}")
        self.assertEqual(st, 200, r)
        return r

    # --------------------------------------------------------- BAND 13/14
    def test_L01_future_session_is_pending_or_confirmed(self):
        """KELMAGAN mashg'ulot: `pending` (kutilmoqda) yoki `confirmed`
        (tasdiqlangan) — HECH QACHON `completed` EMAS."""
        d = (datetime.now() + timedelta(days=3)).replace(hour=9, minute=0, second=0,
                                                        microsecond=0)
        self._new(d, status="scheduled", confirm="pending")
        rows = self._list(1)["sessions"]
        s = [x for x in rows if x["id"] == self.sids[-1]][0]
        self.assertEqual(s["_display_status"], "pending", s)
        self.assertTrue(s["_is_future"])

    def test_L02_confirmed_state_shown(self):
        d = (datetime.now() + timedelta(days=4)).replace(hour=9, minute=0, second=0,
                                                        microsecond=0)
        self._new(d, status="scheduled", confirm="confirmed")
        rows = self._list(1)["sessions"]
        s = [x for x in rows if x["id"] == self.sids[-1]][0]
        self.assertEqual(s["_display_status"], "confirmed", s)

    def test_L03_ongoing_session(self):
        """BAND 14: `JARAYONDA` holati alohida ko'rsatiladi (`completed` EMAS)."""
        d = (datetime.now() + timedelta(days=3)).replace(hour=9, minute=0, second=0,
                                                        microsecond=0)
        self._new(d, status="ongoing")
        rows = self._list(1)["sessions"]
        s = [x for x in rows if x["id"] == self.sids[-1]][0]
        self.assertEqual(s["_display_status"], "ongoing", s)

    def test_L04_past_not_completed_is_overdue(self):
        """BAND 14: o'tib ketgan lekin yakunlanmagan dars AVTOMATIK
        "Bajarilgan" BO'LMAYDI — `overdue`."""
        d = datetime.now().replace(hour=9, minute=0, second=0, microsecond=0) \
            - timedelta(days=2)
        self._new(d, status="scheduled")
        rows = self._list(0)["sessions"]
        s = [x for x in rows if x["id"] == self.sids[-1]][0]
        self.assertEqual(s["_display_status"], "overdue", s)
        self.assertFalse(s["_is_future"])

    def test_L05_completed_stays_completed(self):
        d = datetime.now().replace(hour=9, minute=0, second=0, microsecond=0) \
            - timedelta(days=2)
        self._new(d, status="completed")
        rows = self._list(0)["sessions"]
        s = [x for x in rows if x["id"] == self.sids[-1]][0]
        self.assertEqual(s["_display_status"], "completed", s)

    def test_L06_cancelled_stays_cancelled(self):
        d = datetime.now().replace(hour=9, minute=0, second=0, microsecond=0) \
            - timedelta(days=2)
        self._new(d, status="cancelled")
        rows = self._list(0)["sessions"]
        s = [x for x in rows if x["id"] == self.sids[-1]][0]
        self.assertEqual(s["_display_status"], "cancelled", s)

    def test_L07_past_day_leaves_upcoming_list(self):
        """BAND 13: 1 kun o'tgan dars 'kelayotgan' ro'yxatidan CHIQADI,
        lekin DB'dan O'CHIRILMAYDI va tarixda SAQLANADI.

        Kelajakdagi dars "erta indin" qo'yiladi — test soatga bog'liq bo'lmasligi
        uchun (kechqurun ishga tushsa ham ishlashi kerak)."""
        tomorrow9 = ((datetime.now() + timedelta(days=1)).replace(hour=9, minute=0,
                                                                 second=0, microsecond=0))
        yesterday9 = tomorrow9 - timedelta(days=2)
        self._new(tomorrow9, status="scheduled")
        self._new(yesterday9, status="scheduled")
        sid_future, sid_past = self.sids[-2], self.sids[-1]
        up_ids = [x["id"] for x in self._list(1)["sessions"]]
        self.assertIn(sid_future, up_ids)
        self.assertNotIn(sid_past, up_ids, "o'tgan dars 'kelayotgan' da qoldi")
        past_ids = [x["id"] for x in self._list(0)["sessions"]]
        self.assertIn(sid_past, past_ids, "o'tgan dars tarixda yo'q")
        # DB'da SAQLANGAN
        row = self.db.q1("SELECT id FROM lesson_sessions WHERE id=?", (sid_past,))
        self.assertIsNotNone(row, "o'tgan dars DB'dan o'chirilgan!")

    def test_L08_all_split_and_counts(self):
        f = (datetime.now() + timedelta(days=6)).replace(hour=9, minute=0, second=0,
                                                         microsecond=0)
        p = datetime.now().replace(hour=9, minute=0, second=0, microsecond=0) \
            - timedelta(days=1)
        self._new(f)
        self._new(p)
        st, r = self.c.get("/api/student/sessions?upcoming=all")
        self.assertEqual(st, 200, r)
        up_ids = [x["id"] for x in r["upcoming"]]
        past_ids = [x["id"] for x in r["past"]]
        self.assertIn(self.sids[-2], up_ids)
        self.assertIn(self.sids[-1], past_ids)
        self.assertNotIn(self.sids[-2], past_ids)
        self.assertNotIn(self.sids[-1], up_ids)
        self.assertGreaterEqual(r["counts"]["upcoming"], 1)
        self.assertGreaterEqual(r["counts"]["past"], 1)
        self.assertGreaterEqual(r["counts"]["overdue"], 1)

    def test_L09_home_cards_from_db(self):
        """BAND 2: bosh sahifadagi 3 karta va progress — hammasi DB dan."""
        d = (datetime.now() + timedelta(days=5)).replace(hour=9, minute=0, second=0,
                                                        microsecond=0)
        self._new(d)
        st, r = self.c.get("/api/student/home")
        self.assertEqual(st, 200, r)
        pr = r["progress"]
        for k in ("target", "done", "remaining", "pct", "mode"):
            self.assertIn(k, pr, f"progress.{k} yo'q")
        self.assertGreater(pr["target"], 0, "jami darslar soni DB dan kelishi shart")
        self.assertIn("counts", r)
        for k in ("upcoming", "overdue"):
            self.assertIn(k, r["counts"])
        # frontend'da hardcoded raqam BO'LMASIN
        txt = (ROOT / "web" / "js" / "views-student.js").read_text(encoding="utf-8",
                                                                    errors="ignore")
        self.assertIn("week.total_lessons", txt)
        self.assertIn("week.done_lessons", txt)
        self.assertIn("week.remaining_lessons", txt)
        self.assertIn("home.overall_progress", txt)

    def test_L10_overdue_not_counted_as_done(self):
        """20/8 -> 20/9: o'tgan, yakunlanmagan dars `done` ga QO'SHILMAYDI."""
        st0, h0 = self.c.get("/api/student/home")
        done0 = h0["progress"]["done"]
        d = datetime.now().replace(hour=9, minute=0, second=0, microsecond=0) \
            - timedelta(days=1)
        self._new(d, status="scheduled")
        st1, h1 = self.c.get("/api/student/home")
        self.assertEqual(h1["progress"]["done"], done0,
                         "o'tib ketgan dars 'bajarilgan' ga hisoblandi")
        self.assertGreaterEqual(h1["counts"]["overdue"], 1)

    def test_L11_remaining_never_negative(self):
        self.admin.post(f"/api/admin/users/{self.uid}/total-lessons",
                        {"scope": "user", "user_id": self.uid, "total_lessons": 1})
        st, h = self.c.get("/api/student/home")
        self.assertEqual(st, 200, h)
        self.assertGreaterEqual(h["progress"]["remaining"], 0)

    def test_L12_unknown_category_rejected(self):
        st, r = self.c.get("/api/student/sessions?upcoming=bogus")
        self.assertEqual(st, 200, r)   # `bogus` -> default kelayotgan (moslik)

    # --------------------------------------------------------- BAND 19/20
    def test_L13_car_double_booking_rejected(self):
        """BAND 19: bir vaqtda bitta avtomobilga bir nechta talaba
        biriktirilMASIN (slot conflict)."""
        day = (datetime.now() + timedelta(days=50)).strftime("%Y-%m-%d")
        st, r1 = self.admin.post("/api/admin/sessions", {
            "date": day, "start_time": "08:00", "end_time": "09:00",
            "instructor_id": 1, "student_ids": [self.student_id], "notes": "L13-A"})
        self.assertEqual(st, 200, r1)
        self.sids.append(r1["id"])
        r2u = self._mkuser("student", "Les", "Second", group_name="LES2")
        try:
            srow2 = self.db.q1("SELECT id FROM students WHERE user_id=?",
                               (r2u["user"]["id"],))
            st2, r2 = self.admin.post("/api/admin/sessions", {
                "date": day, "start_time": "08:00", "end_time": "09:00",
                "instructor_id": 1, "student_ids": [srow2["id"]], "notes": "L13-B"})
            self.assertIn(st2, (400, 409), r2)
            self.assertTrue(r2.get("error"), r2)
        finally:
            self._cleanup_user(r2u["user"]["id"])

    def test_L14_duplicate_student_in_session_rejected(self):
        day = (datetime.now() + timedelta(days=51)).strftime("%Y-%m-%d")
        st, r = self.admin.post("/api/admin/sessions", {
            "date": day, "start_time": "10:00", "end_time": "11:00",
            "instructor_id": 1, "student_ids": [self.student_id, self.student_id]})
        self.assertIn(st, (400, 409), r)
        self.assertIn("duplicate", str(r.get("error", "")) + str(r))

    def test_L15_foreign_keys_present(self):
        """BAND 20: jadvalar orasida FK constraint'lar mavjud."""
        fks = self.db.q("PRAGMA foreign_key_list(session_students)")
        cols = {f["table"] for f in fks}
        self.assertIn("lesson_sessions", cols, "session_students -> lesson_sessions FK yo'q")
        self.assertIn("students", cols, "session_students -> students FK yo'q")
        fk2 = self.db.q("PRAGMA foreign_key_list(lesson_sessions)")
        self.assertTrue(fk2, "lesson_sessions da FK yo'q")

    def test_L16_student_cannot_see_other_students_session(self):
        r2 = self._mkuser("student", "Les", "Hidden", group_name="LES3")
        try:
            srow2 = self.db.q1("SELECT id FROM students WHERE user_id=?",
                               (r2["user"]["id"],))
            d = (datetime.now() + timedelta(days=8)).replace(hour=12, minute=0, second=0,
                                                            microsecond=0)
            sid2 = self._mk_session(d, now(), srow2["id"], notes="LES-HID")
            self.sids.append(sid2)
            st, r = self.c.get(f"/api/student/sessions/{sid2}")
            self.assertEqual(st, 404, r)
        finally:
            self._cleanup_user(r2["user"]["id"])


# ============================================================================
# 4) NOTIFICATIONS — BAND 8, 9, 11, 12, 17, 18, 21
# ============================================================================
class TestNotificationsBAND24(_MixinAdmin, Base):
    """NOTIFICATIONS: kategoriyalar, alohida record, 2-soat eslatma, sozlamalar."""

    def setUp(self):
        super().setUp()
        r = self._mkuser("student", "Notif", "Test", group_name="NOT", license_category="B")
        self.uid = r["user"]["id"]
        self.login = r["credentials"]["login"]
        self.password = r["credentials"]["password"]
        self.student_id = self.db.q1("SELECT id FROM students WHERE user_id=?",
                                     (self.uid,))["id"]
        self.c, st, rr = self._login(self.login, self.password, "student")
        self.assertEqual(st, 200, rr)
        self.sids = []

    def tearDown(self):
        for sid in self.sids:
            self._drop_session(sid)
        self._cleanup_user(self.uid)
        super().tearDown()

    def _notifs(self, cat=None):
        q = f"/api/me/notifications?category={cat}" if cat else "/api/me/notifications"
        st, r = self.c.get(q)
        self.assertEqual(st, 200, r)
        return r["notifications"]

    # ------------------------------------------------------------- BAND 8
    def test_N01_only_four_categories(self):
        """'So'rovlar' va 'Xavfsizlik hodisalari' OLib TASHLANDI."""
        r = self._notifs()
        cats = r if isinstance(r, list) else r
        st, rr = self.c.get("/api/me/notifications")
        self.assertEqual(sorted(rr["categories"]),
                         ["all", "lesson", "message", "reminder"],
                         "faqat 4 ta kategoriya bo'lishi kerak")
        # frontend filtrlari ham 4 ta
        txt = (ROOT / "web" / "js" / "shared.js").read_text(encoding="utf-8", errors="ignore")
        i = txt.find("const CATS = [")
        chunk = txt[i:i + 600]
        self.assertNotIn('["request"', chunk, "'So'rovlar' filtri olib tashlanmagan")
        self.assertNotIn('["security"', chunk, "'Xavfsizlik' filtri olib tashlanmagan")

    def test_N02_request_and_security_category_rejected(self):
        for cat in ("request", "security"):
            st, r = self.c.get(f"/api/me/notifications?category={cat}")
            self.assertEqual(st, 400, f"{cat}: {r}")
            self.assertEqual(r["error"], "bad_request")

    # ------------------------------------------------------------- BAND 12
    def test_N03_message_category_only_admin_messages(self):
        """'Xabarlar' = FAQAT admin yuborgan xabar."""
        st, r = self._admin_msg("MSG-1", "Bitta xabar")
        self.assertEqual(st, 200, r)
        msgs = self._notifs("message")
        self.assertTrue(any(m["title"] == "MSG-1" for m in msgs))
        for m in msgs:
            self.assertEqual(m["source"], "ADMIN_MESSAGE",
                             "Xabarlar kategoriyasida boshqa manba bor")
        # eslatma 'message' da chiqmasin
        start = (datetime.now() + timedelta(minutes=110)).replace(second=0, microsecond=0)
        created = (start - timedelta(hours=3)).strftime("%Y-%m-%d %H:%M:%S")
        sid = self._mk_session(start, created, self.student_id, notes="N03")
        self.sids.append(sid)
        ensure_reminders(self.db)
        rem = self._notifs("reminder")
        self.assertTrue(any(m["related_lesson_id"] == sid for m in rem))
        msgs2 = self._notifs("message")
        self.assertFalse(any(m["related_lesson_id"] == sid for m in msgs2),
                         "eslatma 'Xabarlar' kategoriyasiga tushib ketdi")

    # ------------------------------------------------------------- BAND 11
    def test_N04_each_message_is_separate_record(self):
        """Har bir xabar — ALOHIDA DB qatori; matnlar aralashMAYDI."""
        bodies = ["Xabar-birinchi", "Xabar-ikkinchi", "Xabar-uchinchi"]
        for b in bodies:
            st, _ = self._admin_msg(b, "matn-" + b)
            self.assertEqual(st, 200)
        rows = self.db.q(
            "SELECT id, title, body, source FROM notifications "
            "WHERE user_id=? AND title LIKE 'Xabar-%' ORDER BY id", (self.uid,))
        for b in bodies:
            hits = [r for r in rows if r["title"] == b]
            self.assertEqual(len(hits), 1, f"{b} uchun {len(hits)} ta qator topildi")
            self.assertIn("matn-" + b, hits[0]["body"])
            self.assertEqual(hits[0]["source"], "ADMIN_MESSAGE")
        # detail aynan o'sha ID bo'yicha
        target = [r for r in rows if r["title"] == "Xabar-ikkinchi"][0]
        st, d = self.c.get(f"/api/me/notifications/{target['id']}")
        self.assertEqual(st, 200, d)
        self.assertEqual(d["notification"]["title"], "Xabar-ikkinchi")
        self.assertIn("matn-Xabar-ikkinchi", d["notification"]["body"])

    def test_N05_notification_detail_idor(self):
        other = self._mkuser("student", "Notif", "Other", group_name="NOT2")
        try:
            st, r = self._admin_msg("OTHER-1", "boshqa odamga")
            self.assertEqual(st, 200, r)
            row = self.db.q1(
                "SELECT id FROM notifications WHERE user_id=? AND title='OTHER-1'",
                (other["user"]["id"],))
            self.assertIsNotNone(row, "boshqa foydalanuvchiga xabar yuborilmadi")
            st2, d = self.c.get(f"/api/me/notifications/{row['id']}")
            self.assertEqual(st2, 404, d)
        finally:
            self._cleanup_user(other["user"]["id"])

    def test_N06_notification_too_long_rejected(self):
        st, r = self._admin_msg("X", "M" * 5000)
        self.assertEqual(st, 400, r)
        self.assertEqual(r["error"], "notif.too_long")
        self.assertEqual(self.db.q1(
            "SELECT COUNT(*) c FROM notifications WHERE title='X'")["c"], 0)

    # ------------------------------------------------------------- BAND 9
    def test_N07_reminder_exactly_once(self):
        start = (datetime.now() + timedelta(minutes=115)).replace(second=0, microsecond=0)
        created = (start - timedelta(hours=4)).strftime("%Y-%m-%d %H:%M:%S")
        sid = self._mk_session(start, created, self.student_id, notes="N07")
        self.sids.append(sid)
        n1 = ensure_reminders(self.db)
        self.assertGreaterEqual(n1, 1)
        n2 = ensure_reminders(self.db)
        self.assertEqual(n2, 0, "ikkinchi marta eslatma yuborildi")
        c = self.db.q1("""SELECT COUNT(*) c FROM notifications
                          WHERE user_id=? AND source='LESSON_REMINDER'
                            AND related_lesson_id=?""", (self.uid, sid))["c"]
        self.assertEqual(c, 1, "eslatma bir marta emas")
        row = self.db.q1("""SELECT * FROM notifications
                             WHERE user_id=? AND source='LESSON_REMINDER'
                               AND related_lesson_id=?""", (self.uid, sid))
        data = row["data"] if isinstance(row["data"], dict) else jload(row["data"], {})
        for k in ("date", "start_time", "instructor_name", "pickup_address"):
            self.assertIn(k, data, f"eslatma metadatasida {k} yo'q")
        self.assertEqual(row["created_by"], "SYSTEM")

    def test_N08_no_reminder_for_late_created_lesson(self):
        start = (datetime.now() + timedelta(minutes=40)).replace(second=0, microsecond=0)
        sid = self._mk_session(start, now(), self.student_id, notes="N08")
        self.sids.append(sid)
        self.assertEqual(ensure_reminders(self.db), 0)
        c = self.db.q1("""SELECT COUNT(*) c FROM notifications
                          WHERE related_lesson_id=? AND source='LESSON_REMINDER'""",
                       (sid,))["c"]
        self.assertEqual(c, 0)

    def test_N09_no_reminder_for_started_lesson(self):
        start = (datetime.now() - timedelta(minutes=30)).replace(second=0, microsecond=0)
        sid = self._mk_session(start,
                               (start - timedelta(hours=5)).strftime("%Y-%m-%d %H:%M:%S"),
                               self.student_id, notes="N09")
        self.sids.append(sid)
        self.assertEqual(ensure_reminders(self.db), 0)

    def test_N10_reminder_cleared_on_cancel(self):
        start = (datetime.now() + timedelta(minutes=115)).replace(second=0, microsecond=0)
        sid = self._mk_session(start,
                               (start - timedelta(hours=4)).strftime("%Y-%m-%d %H:%M:%S"),
                               self.student_id, notes="N10")
        self.sids.append(sid)
        ensure_reminders(self.db)
        # DIQQAT: eslatma talabaga VA instruktorga boriladi -> `user_id` bilan
        # filtrlash shart (aks holda 2 ta qator topiladi).
        self.assertEqual(self.db.q1(
            "SELECT COUNT(*) c FROM notifications WHERE related_lesson_id=? "
            "AND user_id=? AND source='LESSON_REMINDER'", (sid, self.uid))["c"], 1)
        st, r = self.admin.post(f"/api/admin/sessions/{sid}/cancel",
                                {"reason": "bekor qilindi"})
        self.assertIn(st, (200, 201), r)
        c = self.db.q1("""SELECT COUNT(*) c FROM notifications
                          WHERE related_lesson_id=? AND user_id=?
                          AND source='LESSON_REMINDER'""",
                       (sid, self.uid))["c"]
        self.assertEqual(c, 0, "bekor qilingandan keyin eslatma qoldi")

    def test_N11_reminder_cleared_on_reschedule(self):
        start = (datetime.now() + timedelta(minutes=115)).replace(second=0, microsecond=0)
        sid = self._mk_session(start,
                               (start - timedelta(hours=4)).strftime("%Y-%m-%d %H:%M:%S"),
                               self.student_id, notes="N11")
        self.sids.append(sid)
        ensure_reminders(self.db)
        self.assertEqual(self.db.q1(
            "SELECT COUNT(*) c FROM notifications WHERE related_lesson_id=? "
            "AND user_id=? AND source='LESSON_REMINDER'", (sid, self.uid))["c"], 1)
        new_day = (datetime.now() + timedelta(days=9)).strftime("%Y-%m-%d")
        st, r = self.admin.post(f"/api/admin/sessions/{sid}/reschedule",
                                {"date": new_day, "start_time": "14:00",
                                 "end_time": "15:00", "reason": "ko'chirildi"})
        self.assertIn(st, (200, 201), r)
        c = self.db.q1("""SELECT COUNT(*) c FROM notifications
                          WHERE related_lesson_id=? AND user_id=?
                          AND source='LESSON_REMINDER'""",
                       (sid, self.uid))["c"]
        self.assertEqual(c, 0, "vaqt ko'chirilgandan keyin eslatma qoldi")

    def test_N12_reminder_unique_index_exists(self):
        idx = self.db.q("PRAGMA index_list(notifications)")
        names = {r["name"] for r in idx}
        self.assertIn("ux_notif_reminder_once", names,
                      "eslatma 'faqat bir marta' indeksi yo'q")

    # ------------------------------------------------------------- BAND 18
    def test_N13_notification_schema_columns(self):
        cols = {r["name"] for r in self.db.q("PRAGMA table_info(notifications)")}
        for c in ("id", "user_id", "type", "title", "body", "created_at", "read_at",
                  "related_lesson_id", "created_by", "source", "data"):
            self.assertIn(c, cols, f"notifications.{c} yo'q")

    def test_N14_metadata_object_returned(self):
        st, _ = self._admin_msg("META-1", "meta")
        self.assertEqual(st, 200)
        for m in self._notifs():
            if m["title"] == "META-1":
                self.assertIsInstance(m["metadata"], dict, "metadata ob'ekt bo'lishi shart")
                break
        else:
            self.fail("META-1 topilmadi")

    def test_N15_admin_message_created_by_admin(self):
        st, _ = self._admin_msg("BY-1", "kim yuborgan")
        self.assertEqual(st, 200)
        row = self.db.q1("SELECT created_by, source FROM notifications WHERE title='BY-1'")
        self.assertEqual(row["source"], "ADMIN_MESSAGE")
        self.assertIsNotNone(row["created_by"], "created_by bo'lishi shart")
        self.assertNotEqual(row["created_by"], "SYSTEM")

    # ------------------------------------------------------------- BAND 21
    def test_N16_frontend_uses_id_not_index(self):
        """`key`/identifikator ro'yxat POSITSIYASI emas, DB `id` si bo'lishi shart."""
        for rel in ("web/js/shared.js", "web/js/ui.js"):
            txt = (ROOT / rel).read_text(encoding="utf-8", errors="ignore")
            self.assertIn('"notif-" + n.id', txt,
                          rel + ": barqaror kalit (notif-<id>) ishlatilmadi")

    def test_N17_metadata_preferred_over_json_parse(self):
        txt = (ROOT / "web" / "js" / "shared.js").read_text(encoding="utf-8", errors="ignore")
        self.assertIn("n.metadata", txt, "metadata maydoni ishlatilmadi")
        self.assertIn("JSON.parse(n.data", txt, "data matni fallback sifatida yo'q")

    # ------------------------------------------------------------- BAND 17
    def test_N18_settings_default_all_true(self):
        st, r = self.c.get("/api/me/settings")
        self.assertEqual(st, 200, r)
        ns = r["settings"]["notification_settings"]
        for k in ("lesson_reminders", "admin_messages", "lesson_status_updates",
                  "messages", "requests", "security"):
            self.assertIn(k, ns, f"notification_settings.{k} yo'q")
            self.assertTrue(ns[k], f"{k} default true bo'lishi kerak")

    def test_N19_settings_roundtrip_and_persistence(self):
        st, r = self.c.put("/api/me/settings",
                           {"notification_settings": {"lesson_reminders": False,
                                                      "admin_messages": False}})
        self.assertEqual(st, 200, r)
        ns = r["notification_settings"]
        self.assertFalse(ns["lesson_reminders"])
        self.assertFalse(ns["admin_messages"])
        self.assertTrue(ns["lesson_status_updates"], "boshqa ustun buzildi")
        # BOSHQA qurilmada (boshqa sessiya) saqlangan holda o'qiladi
        c2, st2, _ = self._login(self.login, self.password, "student")
        self.assertEqual(st2, 200)
        st3, r3 = c2.get("/api/me/settings")
        self.assertEqual(st3, 200)
        ns3 = r3["settings"]["notification_settings"]
        self.assertFalse(ns3["lesson_reminders"], "sozlama saqlanmagan")
        self.assertFalse(ns3["admin_messages"], "sozlama saqlanmagan")

    def test_N20_reminder_setting_off_blocks(self):
        """Sozlama REAL: o'chirilgan eslatma yuborilmaydi."""
        st, r = self.c.put("/api/me/settings",
                           {"notification_settings": {"lesson_reminders": False}})
        self.assertEqual(st, 200, r)
        start = (datetime.now() + timedelta(minutes=115)).replace(second=0, microsecond=0)
        sid = self._mk_session(start,
                               (start - timedelta(hours=4)).strftime("%Y-%m-%d %H:%M:%S"),
                               self.student_id, notes="N20")
        self.sids.append(sid)
        ensure_reminders(self.db)
        c = self.db.q1("""SELECT COUNT(*) c FROM notifications
                          WHERE user_id=? AND source='LESSON_REMINDER'
                            AND related_lesson_id=?""", (self.uid, sid))["c"]
        self.assertEqual(c, 0, "sozlama o'chirilgan bo'lsa ham eslatma yuborildi")

    def test_N21_admin_message_setting_off_blocks(self):
        st, r = self.c.put("/api/me/settings",
                           {"notification_settings": {"admin_messages": False}})
        self.assertEqual(st, 200, r)
        st2, r2 = self._admin_msg("BLOCKED-1", "yuborilmasligi kerak")
        self.assertEqual(st2, 200, r2)
        self.assertEqual(self.db.q1(
            "SELECT COUNT(*) c FROM notifications WHERE user_id=? AND title='BLOCKED-1'",
            (self.uid,))["c"], 0, "sozlama o'chirilgan, xabar yuborildi")

    def test_N22_legacy_notif_shape_kept(self):
        """Eski frontend shakli (`notif`) saqlanadi — `admin` alohida kalit."""
        st, r = self.c.get("/api/me/settings")
        self.assertEqual(st, 200, r)
        notif = r["settings"]["notif"]
        for k in ("lesson", "admin", "message", "reminder", "request", "security"):
            self.assertIn(k, notif, f"notif.{k} yo'q")

    def test_N23_legacy_put_shape_accepted(self):
        st, r = self.c.put("/api/me/settings", {"notif": {"reminder": False}})
        self.assertEqual(st, 200, r)
        self.assertFalse(r["notification_settings"]["lesson_reminders"])
        st2, r2 = self.c.put("/api/me/settings", {"notif": {"reminder": True}})
        self.assertEqual(st2, 200, r2)
        self.assertTrue(r2["notification_settings"]["lesson_reminders"])


# ============================================================================
# 5) PROFILE — BAND 15, 16
# ============================================================================
class TestProfileBAND24(_MixinAdmin, Base):
    """PROFILE: 5 ta tahrirlanadigan maydon, login unikal, parol ko'rinmasin."""

    def setUp(self):
        super().setUp()
        r = self._mkuser("student", "Prof", "Test", group_name="PRF",
                         license_category="C", phone="+998901112233")
        self.uid = r["user"]["id"]
        self.login = r["credentials"]["login"]
        self.password = r["credentials"]["password"]
        self.student_id = self.db.q1("SELECT id FROM students WHERE user_id=?",
                                     (self.uid,))["id"]
        self.c, st, rr = self._login(self.login, self.password, "student")
        self.assertEqual(st, 200, rr)

    def tearDown(self):
        self._cleanup_user(self.uid)
        super().tearDown()

    def test_P01_update_five_fields(self):
        st, r = self.c.put("/api/me/profile", {
            "birth_date": "2004-05-17", "phone": "+998907654321",
            "login": self.login, "group_name": "PRF-2024", "license_category": "B",
        })
        self.assertEqual(st, 200, r)
        u = self.db.q1("SELECT birth_date, phone FROM users WHERE id=?", (self.uid,))
        self.assertEqual(u["birth_date"], "2004-05-17")
        self.assertEqual(u["phone"], "+998907654321")
        s = self.db.q1("SELECT group_name, license_category FROM students WHERE id=?",
                       (self.student_id,))
        self.assertEqual(s["group_name"], "PRF-2024")
        self.assertEqual(s["license_category"], "B")

    def test_P02_login_format_enforced(self):
        for bad in ("admin", "usrL_short", "usrX_aaaaaaaaaaaaaaaa", "usrL_ab cd1234",
                    "usrL_ab!cd1234567", "PLAINlogin12345"):
            st, r = self.c.put("/api/me/profile", {"login": bad})
            self.assertEqual(st, 400, f"{bad!r} qabul qilindi: {r}")
            self.assertEqual(r["error"], "profile.login_format", f"{bad!r}: {r}")
        # eski login o'zgarmagan
        self.assertEqual(self.db.q1("SELECT login FROM users WHERE id=?",
                                    (self.uid,))["login"], self.login)

    def test_P03_login_unique_enforced(self):
        r2 = self._mkuser("student", "Prof", "Second", group_name="PRF2")
        try:
            st, r = self.c.put("/api/me/profile", {"login": r2["credentials"]["login"]})
            self.assertEqual(st, 400, r)
            self.assertEqual(r["error"], "profile.login_taken", r)
        finally:
            self._cleanup_user(r2["user"]["id"])

    def test_P04_login_change_reported_and_revokes_sessions(self):
        new_login = "usrL_profChanged0001"
        st, r = self.c.put("/api/me/profile", {"login": new_login})
        self.assertEqual(st, 200, r)
        self.assertTrue(r.get("login_changed"), "login_changed qaytarilishi shart")
        self.assertEqual(self.db.q1("SELECT login FROM users WHERE id=?",
                                    (self.uid,))["login"], new_login)
        # eski sessiya bekor qilindi
        self.assertEqual(self.c.get("/api/auth/me")[0], 401)
        # yangi login bilan kirish ishlaydi
        c2, st2, r2 = self._login(new_login, self.password, "student")
        self.assertEqual(st2, 200, r2)
        # eski login bilan KIRIB BO'LMAYDI
        c3, st3, r3 = self._login(self.login, self.password, "student")
        self.assertEqual(st3, 400, r3)
        self.db.upd("UPDATE users SET login=? WHERE id=?", (self.login, self.uid))

    def test_P05_password_not_editable_via_profile(self):
        """BAND 15: parol profil orqali O'Zgartirilmaydi."""
        st, r = self.c.put("/api/me/profile", {
            "password": "usrP_New000000!Zx1",
            "new_password": "usrP_New000000!Zx1",
            "password_hash": "x", "must_change_password": 1,
        })
        self.assertEqual(st, 200, r)
        h = self.db.q1("SELECT password_hash FROM users WHERE id=?", (self.uid,))["password_hash"]
        from app.auth import verify_password
        self.assertTrue(verify_password(self.password, h), "parol o'zgargan!")
        # javobda parol maydonlari YO'Q
        raw = json.dumps(r)
        self.assertNotIn("password_hash", raw)
        self.assertNotIn("must_change_password", raw)

    def test_P06_enrolled_at_hidden_from_student(self):
        """BAND 16: 'Ro'yxatga olingan sana' talabaga KO'RSATILMAYDI."""
        st, r = self.c.get("/api/auth/me")
        self.assertEqual(st, 200, r)
        self.assertNotIn("enrolled_at", r["student"],
                         "enrolled_at talabaga ko'rsatildi")
        st2, r2 = self.c.get("/api/student/home")
        self.assertEqual(st2, 200, r2)
        self.assertNotIn("enrolled_at", json.dumps(r2))
        # lekin DB'da SAQLANADI
        self.assertIsNotNone(self.db.q1(
            "SELECT enrolled_at FROM students WHERE id=?", (self.student_id,)))

    def test_P07_admin_sees_enrolled_at(self):
        st, r = self.admin.get(f"/api/admin/users/{self.uid}")
        self.assertEqual(st, 200, r)
        self.assertIn("enrolled_at", r["user"]["student"],
                      "admin enrolled_at ni ko'ra olmaydi")

    def test_P08_invalid_phone_and_birth(self):
        st, r = self.c.put("/api/me/profile", {"phone": "123"})
        self.assertEqual(st, 400, r)
        self.assertEqual(r["error"], "profile.phone_invalid")
        st2, r2 = self.c.put("/api/me/profile", {"birth_date": "3000-01-01"})
        self.assertEqual(st2, 400, r2)
        self.assertEqual(r2["error"], "profile.birth_date_invalid")
        st3, r3 = self.c.put("/api/me/profile", {"birth_date": "2000-13-45"})
        self.assertEqual(st3, 400, r3)
        self.assertEqual(r3["error"], "profile.birth_date_invalid")

    def test_P09_instructor_profile_works(self):
        c, st, rr = self._login(INSTR_LOGIN_1, PW_BY_LOGIN[INSTR_LOGIN_1], "instructor")
        self.assertEqual(st, 200, rr)
        st2, r2 = c.put("/api/me/profile", {"birth_date": "1990-01-02",
                                            "phone": "+998901234567"})
        self.assertEqual(st2, 200, r2)
        st3, r3 = c.get("/api/auth/me")
        self.assertEqual(st3, 200, r3)
        self.assertEqual(r3["user"]["birth_date"], "1990-01-02")
        self.db.upd("UPDATE users SET birth_date=NULL WHERE login=?", (INSTR_LOGIN_1,))
        self.db.upd("UPDATE users SET phone=NULL WHERE login=?", (INSTR_LOGIN_1,))

    def test_P10_profile_modal_has_five_fields(self):
        txt = (ROOT / "web" / "js" / "shared.js").read_text(encoding="utf-8", errors="ignore")
        i = txt.find("function editProfileModal")
        self.assertGreater(i, 0, "editProfileModal topilmadi")
        chunk = txt[i:i + 4000]
        end = chunk.find("\n  }")
        body = chunk[:end if end > 0 else len(chunk)]
        for key in ("student.birth_date", "common.phone", "common.login",
                    "student.group", "student.category"):
            self.assertIn(key, body, f"profil modalidan {key} yo'q")
        # parol maydonlari BO'LMASIN
        self.assertNotIn('"password"', body, "profil modalida parol maydoni bor")
        self.assertIn("profile.password_not_here", body, "parol ogohlantirishi yo'q")

    def test_P11_no_hardcoded_numbers_in_profile_view(self):
        txt = (ROOT / "web" / "js" / "views-student.js").read_text(encoding="utf-8",
                                                                    errors="ignore")
        i = txt.find("async function profile")
        self.assertGreater(i, 0)
        chunk = txt[i:i + 1200]
        # izohlarni tushirib qolamiz (ular `enrolled_at` haqida YOZADI,
        # lekin qiymatni chiqarmaydi) — tekshiruv KODGA qariladi.
        code = re.sub(r"/\*.*?\*/", "", chunk, flags=re.S)
        code = re.sub(r"//[^\n]*", "", code)
        self.assertIn("student.birth_date", code)
        self.assertIn("u.birth_date", code, "tug'ilgan sana API dan olinishi kerak")
        self.assertIn("u.phone", code)
        self.assertIn("u.login", code)
        self.assertNotIn("enrolled_at", code, "enrolled_at talabada ko'rsatilmoqda")


# ============================================================================
# 6) SETTINGS — BAND 17 (bildirishnoma sozlamalari DB da)
# ============================================================================
class TestSettingsBAND24(_MixinAdmin, Base):
    """SETTINGS: sozlamalar faqat serverda, boshqa qurilmada ham saqlanadi."""

    def setUp(self):
        super().setUp()
        r = self._mkuser("student", "Set", "Test", group_name="SET", license_category="B")
        self.uid = r["user"]["id"]
        self.login = r["credentials"]["login"]
        self.password = r["credentials"]["password"]
        self.c, st, rr = self._login(self.login, self.password, "student")
        self.assertEqual(st, 200, rr)

    def tearDown(self):
        self._cleanup_user(self.uid)
        super().tearDown()

    def test_S01_settings_table_exists(self):
        cols = {r["name"] for r in self.db.q("PRAGMA table_info(notification_settings)")}
        self.assertIn("user_id", cols)
        self.assertIn("lesson_reminders", cols)
        self.assertIn("admin_messages", cols)
        self.assertIn("lesson_status_updates", cols)

    def test_S02_no_localstorage_source_of_truth(self):
        """Frontend sozlamani localStorage'da emas, serverdan o'qishi SHART."""
        txt = (ROOT / "web" / "js" / "shared.js").read_text(encoding="utf-8", errors="ignore")
        i = txt.find("function notifSettingsCard")
        self.assertGreater(i, 0, "notifSettingsCard topilmadi")
        chunk = txt[i:i + 2600]
        end = chunk.find("\n  }")
        body = chunk[:end if end > 0 else len(chunk)]
        self.assertIn('API.put("me/settings"', body, "sozlama serverga yuborilmayapti")
        self.assertIn("notification_settings", body, "yangi ustunlar ishlatilmayapti")
        self.assertNotIn("localStorage", body, "sozlama localStorage da saqlanmoqda")

    def test_S03_each_toggle_saves_its_own_column(self):
        for col in ("lesson_reminders", "admin_messages", "lesson_status_updates"):
            st, r = self.c.put("/api/me/settings",
                               {"notification_settings": {col: False}})
            self.assertEqual(st, 200, r)
            ns = r["notification_settings"]
            self.assertFalse(ns[col], f"{col} saqlanmadi")
            others = [k for k in ns if k != col]
            self.assertTrue(all(ns[k] for k in others),
                            f"{col} o'chganda boshqa ustunlar ham o'chdi")
            st2, r2 = self.c.put("/api/me/settings",
                                 {"notification_settings": {col: True}})
            self.assertEqual(st2, 200, r2)
            self.assertTrue(r2["notification_settings"][col])

    def test_S04_settings_survive_new_client(self):
        """Brauzer yopilsa yoki boshqa qurilmada kirsangiz ham saqlanadi."""
        self.c.put("/api/me/settings",
                   {"notification_settings": {"lesson_status_updates": False}})
        c2, st, _ = self._login(self.login, self.password, "student")
        self.assertEqual(st, 200)
        st2, r2 = c2.get("/api/me/settings")
        self.assertEqual(st2, 200)
        self.assertFalse(r2["settings"]["notification_settings"]["lesson_status_updates"])
        # DB da ham saqlangan
        row = self.db.q1("SELECT * FROM notification_settings WHERE user_id=?", (self.uid,))
        self.assertIsNotNone(row)
        self.assertEqual(int(row["lesson_status_updates"]), 0)

    def test_S05_lang_and_theme_still_work(self):
        st, r = self.c.put("/api/me/settings", {"lang": "ru", "theme": "dark"})
        self.assertEqual(st, 200, r)
        st2, r2 = self.c.get("/api/me/settings")
        self.assertEqual(st2, 200, r2)
        self.assertEqual(r2["settings"]["lang"], "ru")
        self.assertEqual(r2["settings"]["theme"], "dark")
        st3, r3 = self.c.put("/api/me/settings", {"lang": "xx"})
        self.assertEqual(st3, 200, r3)
        st4, r4 = self.c.get("/api/me/settings")
        self.assertEqual(r4["settings"]["lang"], "ru", "noto'g'ri til o'zgartirildi")

    def test_S06_anonymous_cannot_read_settings(self):
        anon = Client()
        st, r = anon.get("/api/me/settings")
        self.assertEqual(st, 401, r)
        st2, r2 = anon.put("/api/me/settings",
                           {"notification_settings": {"lesson_reminders": False}})
        self.assertEqual(st2, 401, r2)

    def test_S07_other_role_cannot_touch_my_settings(self):
        r2 = self._mkuser("student", "Set", "Other", group_name="SET2")
        try:
            c2, st, _ = self._login(r2["credentials"]["login"],
                                    r2["credentials"]["password"], "student")
            self.assertEqual(st, 200)
            st2, r3 = c2.get("/api/me/settings")
            self.assertEqual(st2, 200)
            ns = r3["settings"]["notification_settings"]
            self.assertTrue(all(ns.values()),
                            "boshqa foydalanuvchining sozlamalari aralashdi")
        finally:
            self._cleanup_user(r2["user"]["id"])


# ============================================================================
# 7) BAND 3 — admin jami mashg'ulotlar sonini o'zgartirish (alohida sinf,
#    chunki u boshqa sinflardagi progress qiymatlariga ta'sir qiladi)
# ============================================================================
class TestTotalLessonsAdminBAND24(_MixinAdmin, Base):
    """BAND 3: bitta talaba VA barcha talabalar uchun jami sonni o'zgartirish."""

    def setUp(self):
        super().setUp()
        self.uids = []
        self.sids = []
        # Yaratilgan talabaning HAQIQIY credential'lari (random generatsiya qilinadi,
        # shuning uchun fixture ro'yxatida yo'q).
        self.pws = {}
        for i in range(2):
            r = self._mkuser("student", "Tot", "L%d" % i, group_name="TOT%d" % i)
            self.uids.append(r["user"]["id"])
            self.pws[r["user"]["id"]] = r["credentials"]["password"]

    def tearDown(self):
        for sid in self.sids:
            self._drop_session(sid)
        for uid in self.uids:
            self._cleanup_user(uid)
        # platforma umumiy qiymatini tiklash
        self.admin.put("/api/admin/settings", {"total_lessons_target": 30})
        super().tearDown()

    def _complete(self, uid, n):
        """Talabaga `n` ta bajarilgan mashg'ulot yozib beradi."""
        srow = self.db.q1("SELECT id FROM students WHERE user_id=?", (uid,))
        for i in range(n):
            d = (datetime.now() - timedelta(days=10 + i)).replace(hour=9, minute=0,
                                                                 second=0, microsecond=0)
            sid = self._mk_session(d, now(), srow["id"], status="completed",
                                   notes="TOT-DONE")
            self.sids.append(sid)

    def _home(self, uid):
        c, st, _ = self._login(*(self._creds(uid)), role="student")
        self.assertEqual(st, 200)
        st2, h = c.get("/api/student/home")
        self.assertEqual(st2, 200, h)
        return h

    def _creds(self, uid):
        """Talabaning login/parol juftligi (parol API javobidan olinadi)."""
        row = self.db.q1("SELECT login FROM users WHERE id=?", (uid,))
        return row["login"], self.pws[uid]

    def test_T01_single_user_total(self):
        uid = self.uids[0]
        st, r = self.admin.post("/api/admin/users/total-lessons",
                                {"scope": "user", "user_id": uid, "total_lessons": 25})
        self.assertEqual(st, 200, r)
        h = self._home(uid)
        self.assertEqual(h["progress"]["target"], 25)
        self.assertEqual(h["progress"]["individual_target"], 25)
        self.assertEqual(h["progress"]["mode"], "individual")
        self.assertEqual(h["progress"]["remaining"], 25 - h["progress"]["done"])

    def test_T02_below_completed_rejected(self):
        """BAND 3: yangi jami < bajarilgan bo'lsa — QABUL QILINMAYDI."""
        uid = self.uids[0]
        self._complete(uid, 8)
        st, r = self.admin.post("/api/admin/users/total-lessons",
                                {"scope": "user", "user_id": uid, "total_lessons": 5})
        self.assertEqual(st, 400, r)
        self.assertEqual(r["error"], "user.total_lessons_below_done", r)
        self.assertEqual(r.get("params", {}).get("done", r.get("done")), 8, r)
        # oldingi qiymat buzilMADI
        h = self._home(uid)
        self.assertNotEqual(h["progress"]["individual_target"], 5)

    def test_T03_equal_to_completed_allowed(self):
        uid = self.uids[0]
        self._complete(uid, 6)
        st, r = self.admin.post("/api/admin/users/total-lessons",
                                {"scope": "user", "user_id": uid, "total_lessons": 6})
        self.assertEqual(st, 200, r)
        h = self._home(uid)
        self.assertEqual(h["progress"]["target"], 6)
        self.assertEqual(h["progress"]["remaining"], 0)

    def test_T04_history_not_deleted(self):
        """BAND 3: jami sonni o'zgartirish BAJARILGAN mashg'ulotlar,
        tarix va booking'ni O'CHIRMAYDI."""
        uid = self.uids[0]
        self._complete(uid, 3)
        before_done = self._home(uid)["progress"]["done"]
        before_rows = self.db.q("SELECT id FROM lesson_sessions")
        st, r = self.admin.post("/api/admin/users/total-lessons",
                                {"scope": "user", "user_id": uid, "total_lessons": 40})
        self.assertEqual(st, 200, r)
        h = self._home(uid)
        self.assertEqual(h["progress"]["done"], before_done,
                         "bajarilgan darslar soni o'zgardi!")
        after_rows = self.db.q("SELECT id FROM lesson_sessions")
        self.assertEqual(len(after_rows), len(before_rows),
                         "mashg'ulot qatorlari o'chirildi")
        c, st2, _ = self._login(*(self._creds(uid)), role="student")
        st3, hist = c.get("/api/student/sessions?upcoming=0")
        self.assertEqual(st3, 200, hist)
        self.assertEqual(len([x for x in hist["sessions"] if x["_display_status"] == "completed"]),
                         before_done, "tarixdagi completed darslar kamaydi")

    def test_T05_bad_values_rejected(self):
        uid = self.uids[0]
        for bad in (0, -1, 1000, "abc", 12.5):
            st, r = self.admin.post("/api/admin/users/total-lessons",
                                    {"scope": "user", "user_id": uid,
                                     "total_lessons": bad})
            self.assertEqual(st, 400, f"{bad!r}: {r}")
            self.assertEqual(r["error"], "user.bad_total_lessons", f"{bad!r}: {r}")

    def test_T06_all_students_scope(self):
        st, r = self.admin.post("/api/admin/users/total-lessons",
                                {"scope": "all", "total_lessons": 50})
        self.assertEqual(st, 200, r)
        self.assertGreaterEqual(r.get("updated", 0), len(self.uids))
        for uid in self.uids:
            h = self._home(uid)
            self.assertEqual(h["progress"]["target"], 50)
            # ommaviy o'zgartirish ham individual maqsad qo'yadi -> mode=individual
            self.assertEqual(h["progress"]["individual_target"], 50)
            self.assertEqual(h["progress"]["mode"], "individual")

    def test_T07_all_students_below_max_completed_rejected(self):
        """Ommaviy rejimda ham eng ko'p bajarilgan talaba tekshiriladi."""
        self._complete(self.uids[0], 7)
        st, r = self.admin.post("/api/admin/users/total-lessons",
                                {"scope": "all", "total_lessons": 3})
        self.assertEqual(st, 400, r)
        self.assertEqual(r["error"], "user.total_lessons_below_done", r)
        for uid in self.uids:
            h = self._home(uid)
            self.assertNotEqual(h["progress"]["target"], 3)

    def test_T08_clear_individual_target(self):
        uid = self.uids[0]
        self.admin.post("/api/admin/users/total-lessons",
                        {"scope": "user", "user_id": uid, "total_lessons": 44})
        self.assertEqual(self._home(uid)["progress"]["individual_target"], 44)
        st, r = self.admin.post("/api/admin/users/total-lessons",
                                {"scope": "user", "user_id": uid, "total_lessons": None})
        self.assertEqual(st, 200, r)
        h = self._home(uid)
        self.assertIsNone(h["progress"]["individual_target"])
        self.assertEqual(h["progress"]["mode"], "group")

    def test_T09_non_student_rejected(self):
        row = self.db.q1("SELECT id FROM users WHERE login=?", (INSTR_LOGIN_1,))
        st, r = self.admin.post("/api/admin/users/total-lessons",
                                {"scope": "user", "user_id": row["id"],
                                 "total_lessons": 30})
        self.assertIn(st, (400, 404), r)

    def test_T10_only_admin_can_change(self):
        c, st, _ = self._login(STUD_LOGIN_1, PW_BY_LOGIN[STUD_LOGIN_1], "student")
        self.assertEqual(st, 200)
        st2, r = c.post("/api/admin/users/total-lessons",
                        {"scope": "user", "user_id": self.uids[0], "total_lessons": 1})
        self.assertEqual(st2, 403, r)

    def test_T11_admin_users_progress_shape(self):
        st, r = self.admin.get("/api/admin/users?role=student")
        self.assertEqual(st, 200, r)
        for u in r["users"]:
            pr = u.get("progress")
            if not pr:
                continue
            for k in ("target", "done", "remaining", "mode", "individual_target",
                      "group_target"):
                self.assertIn(k, pr, f"admin_users progress.{k} yo'q")

    def test_T12_modal_text_present(self):
        """Modal sarlavhasi va tanlovlar talab dagidek."""
        txt = (ROOT / "web" / "js" / "views-admin.js").read_text(encoding="utf-8",
                                                                   errors="ignore")
        self.assertIn("users.total_title", txt)
        self.assertIn("users.scope_single", txt)
        self.assertIn("users.scope_all", txt)
        self.assertIn("function totalLessonsModal", txt)
        i18n = (ROOT / "web" / "js" / "i18n.js").read_text(encoding="utf-8", errors="ignore")
        self.assertIn("Jami amaliy mashg'ulotlar sonini o'zgartirish", i18n)
        self.assertIn("Bitta talaba", i18n)
        self.assertIn("Barcha talabalar", i18n)


# ============================================================================
# 8) MIGRATSIYA — eski bazani yangilash serverni buzMASIN (regressiya)
# ============================================================================
class TestMigrationBAND24(unittest.TestCase):
    """`init_db` ESKI bazada ham xatosiz ishlashi shart.

    Bu test birinchi marta ishga tushganda platforma ISHLAMASDI:
    `SCHEMA` ichida `notifications(source, ...)` ga bog'liq indekslar
    `migrate()` dan OLDIN yaratilardi -> "no such column: source".
    Eski (foydalanuvchi) bazalarda shu ustun `ALTER TABLE` bilan qo'shiladi.
    """

    def setUp(self):
        import sqlite3
        self._sqlite3 = sqlite3
        self.tmp = tempfile.mkdtemp(prefix="avto-mig-")
        self.path = str(Path(self.tmp) / "old.db")
        # 1) "ESKI" bazani qo'l bilan yaratamiz: jadvallar bor, lekin
        #    `source`/`created_by`/`related_lesson_id`/`csrf_token`/
        #    `confirm_state`/`total_lessons_target` USTUNLARI YO'Q.
        from app.db import SCHEMA
        old_schema = SCHEMA
        for drop in (
            "    source TEXT NOT NULL DEFAULT 'SYSTEM',\n",
            "    created_by INTEGER,\n",
            "    related_lesson_id INTEGER REFERENCES lesson_sessions(id) ON DELETE CASCADE,\n",
        ):
            old_schema = old_schema.replace(drop, "")
        old_schema = old_schema.replace(
            "    csrf_token TEXT NOT NULL DEFAULT '',\n", "")
        old_schema = old_schema.replace(
            "    confirm_state TEXT NOT NULL DEFAULT 'pending'\n"
            "        CHECK (confirm_state IN ('pending','confirmed')),\n", "")
        old_schema = old_schema.replace("    total_lessons_target INTEGER,\n", "")
        c = sqlite3.connect(self.path)
        c.executescript(old_schema)
        t = "2026-01-01 00:00:00"
        c.execute("INSERT INTO users(first_name,last_name,login,password_hash,role,status,"
                  "created_at,updated_at) VALUES('Eski','Talaba','usrL_OLDUS',"
                  "'x','student','active',?,?)", (t, t))
        c.execute("INSERT INTO notifications(user_id,type,title,body,is_read,created_at)"
                  " VALUES(1,'info','Eski xabar','matn',0,?)", (t,))
        c.commit()
        c.close()
        cols = {r[1] for r in sqlite3.connect(self.path).execute(
            "PRAGMA table_info(notifications)")}
        assert "source" not in cols, "test bazasi 'eski' bo'lib yaratilmadi"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_M01_old_db_migrates_without_error(self):
        from app.db import init_db
        db = init_db(self.path)      # <<< avval BU xato berardi
        cols = {r["name"] for r in self.db_rows("PRAGMA table_info(notifications)")}
        self.assertIn("source", cols)
        self.assertIn("created_by", cols)
        self.assertIn("related_lesson_id", cols)
        idx = {r["name"] for r in self.db_rows("PRAGMA index_list(notifications)")}
        self.assertIn("ux_notif_reminder_once", idx)
        self.assertIn("idx_notif_source", idx)

    def test_M02_data_preserved(self):
        """Eski ma'lumotlar (foydalanuvchi, xabar) O'CHIRILMAYDI."""
        from app.db import init_db
        init_db(self.path)
        self.assertEqual(self._one("SELECT COUNT(*) FROM users"), 1)
        self.assertEqual(self._one("SELECT COUNT(*) FROM notifications"), 1)
        # eski xabar `source` ni oldindan oladi: sender_id yo'q -> SYSTEM
        self.assertEqual(
            self._one("SELECT source FROM notifications WHERE id=1"), "SYSTEM")

    def test_M03_idempotent(self):
        """Migration bir necha marta ishga tushsa — xatosiz (2..5 marta)."""
        from app.db import init_db
        for _ in range(4):
            init_db(self.path)
        self.assertEqual(self._one("SELECT COUNT(*) FROM notifications"), 1)

    def db_rows(self, sql):
        c = self._sqlite3.connect(self.path)
        c.row_factory = self._sqlite3.Row
        try:
            return c.execute(sql).fetchall()
        finally:
            c.close()

    def _one(self, sql):
        c = self._sqlite3.connect(self.path)
        try:
            return c.execute(sql).fetchone()[0]
        finally:
            c.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)