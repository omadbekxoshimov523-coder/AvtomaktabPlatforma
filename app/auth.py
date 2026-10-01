"""Xavfsizlik: parol hashing (scrypt), session/token boshqaruvi, RBAC, rate limiting.
Plaintext parol database'da saqlanmaydi — faqat hash.

BAND 5/7 — CREDENTIAL GENERATSIYASI
    Har bir yangi foydalanuvchi uchun login va parol AVTOMATIK yaratiladi:
        login    : usrL_ + 14 ta xavfsiz random belgi
        password : usrP_ + 14 ta xavfsiz random belgi
                   (katta harf, kichik harf, raqam va maxsus belgi majburiy)
    Generator: `secrets` moduli — tizimning CSPRNG manbasiga (os.urandom /
    getrandom) asoslanadi. Ketma-ket/increment ishlatilmaydi.

BAND 6 — HASHING
    Parol `scrypt` bilan hashlanadi: har bir parol uchun alohida 16 baytli
    TUZATILMAGNAN (random) salt yaratiladi va hash ichida saqlanadi. Parolning
    o'zi hech qayerda saqlanmaydi — admin uni ko'ra olmaydi. Taqqoslash
    `hmac.compare_digest` bilan (vaqt bo'yicha yondashuv zaifligi yo'q).
    `verify_password` N/r/p parametrlarini HASH ichidan o'qadi, shuning
    uchun kelgusi parametr kuchaytirilishi eski parollarni buzmaydi.
"""
import hashlib
import hmac
import os
import re
import secrets
import string
import threading
import time

from .db import now, jdump

# Algoritm: scrypt$N$r$p$salt$hash
_N = 2**14
_R = 8
_P = 1
_DKLEN = 64


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=_N, r=_R, p=_P, dklen=_DKLEN)
    return f"scrypt${_N}${_R}${_P}${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    if not stored:
        return False
    try:
        algo, n, r, p, salt_hex, hash_hex = stored.split("$")
        if algo != "scrypt":
            return False
        dk = hashlib.scrypt(
            password.encode("utf-8"),
            salt=bytes.fromhex(salt_hex),
            n=int(n), r=int(r), p=int(p), dklen=_DKLEN,
        )
        return hmac.compare_digest(dk.hex(), hash_hex)
    except Exception:
        return False


def new_token(length: int = 48) -> str:
    return secrets.token_urlsafe(length)


# ---------------------------------------------------------------------------
# BAND 5/7 — UNIKAL, KUCHLI, RANDOM CREDENTIAL GENERATSIYASI
# ---------------------------------------------------------------------------

LOGIN_PREFIX = "usrL_"
PASSWORD_PREFIX = "usrP_"
# Talab bo'yicha: login va parol tanasi 14 belgi.
CRED_BODY_LEN = 14

# Login tanasi: harflar + raqamlar (maxsus belgi yo'q — login'ni kiritishda
# chalkashlik chiqmasligi uchun).
_LOGIN_ALPHABET = string.ascii_letters + string.digits
# Parol tanasi: harflar, raqamlar va maxsus belgilar.
_PASSWORD_SPECIALS = "!@#$%^&*()-_=+[]{}?"
_PASSWORD_ALPHABET = string.ascii_letters + string.digits + _PASSWORD_SPECIALS

# Profil orqali login tahrirlangandagi format tekshiruvi (BAND 15).
LOGIN_RE = re.compile(r"^usrL_[A-Za-z0-9]{%d,32}$" % CRED_BODY_LEN)


def _rand_body(alphabet: str, length: int = CRED_BODY_LEN) -> str:
    """`length` ta xavfsiz random belgi (secrets.choice -> os.urandom)."""
    return "".join(secrets.choice(alphabet) for _ in range(length))


def generate_password() -> str:
    """`usrP_` + 14 belgi. Katta/kichik harf, raqam va maxsus belgi
    GARANTIYALANADI: har toifa kamida bitta bo'lguncha tasodifiy qiymat
    qayta tashlanadi. Boshlang'ich 4 ta belgi toifalarni ta'minlaydi,
    qolgani to'liq tasodifiy tanlanadi."""
    specials = list(_PASSWORD_SPECIALS)
    body = [
        secrets.choice(string.ascii_uppercase),
        secrets.choice(string.ascii_lowercase),
        secrets.choice(string.digits),
        secrets.choice(specials),
    ]
    alphabet = string.ascii_letters + string.digits + "".join(specials)
    while len(body) < CRED_BODY_LEN:
        body.append(secrets.choice(alphabet))
    # Aralashtirish — belgilar ketma-ket to'plam bo'lib qolmasin.
    for i in range(len(body) - 1, 0, -1):
        j = secrets.randbelow(i + 1)
        body[i], body[j] = body[j], body[i]
    return PASSWORD_PREFIX + "".join(body)


def credential_digest(value: str) -> str:
    """Credential'ning bir o'lchamli izi (SHA-256) — uni qaytarish uchun
    ishlatiladi, credentialning O'ZINI saqlash uchun emas."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def generate_credentials(conn, attempts: int = 24) -> tuple:
    """Yangi, UNIKAL (login, password) juftligini qaytaradi.

    `conn` — ochiq sqlite3.Connection (transaction ichida bo'lishi shart).

    Takrorlanish (collision) bo'lsa — qayta generatsiya qilinadi:
      * login    — `users.login` UNIQUE constraint
      * password — `used_credentials.password_digest` UNIQUE constraint
    Bu `attempts` urinishdan keyin ham takrorlanib qolsa, xato ko'tariladi
    ( chegara 4^14 bo'lgani uchun amalda bo'lmaydi ).
    """
    from .db import now as _now
    for _ in range(attempts):
        login = LOGIN_PREFIX + _rand_body(_LOGIN_ALPHABET)
        password = generate_password()
        ld = credential_digest(login)
        pd = credential_digest(password)
        if conn.execute("SELECT 1 FROM users WHERE login=?", (login,)).fetchone():
            continue
        if conn.execute("SELECT 1 FROM used_credentials WHERE login_digest=?", (ld,)).fetchone():
            continue
        if conn.execute("SELECT 1 FROM used_credentials WHERE password_digest=?", (pd,)).fetchone():
            continue
        conn.execute(
            "INSERT INTO used_credentials(login_digest, password_digest, created_at) VALUES(?,?,?)",
            (ld, pd, _now()),
        )
        return login, password
    raise RuntimeError("credential generation: unique juftlik topilmadi")


def is_valid_login(value: str) -> bool:
    """Login formati: `usrL_` bilan boshlanadi, tanasi faqat harf/raqam.
    Profil tahrirlashda ham shu qoida qo'llaniladi (BAND 15)."""
    return bool(LOGIN_RE.match(str(value or "")))


def password_strength_errors(password: str) -> list:
    """Foydalanuvchi tomonidan belgilangan parol uchun minimal talablar."""
    p = str(password or "")
    out = []
    if len(p) < 8:
        out.append("auth.password_short")
    if not re.search(r"[a-z]", p):
        out.append("auth.password_need_lower")
    if not re.search(r"[A-Z]", p):
        out.append("auth.password_need_upper")
    if not re.search(r"\d", p):
        out.append("auth.password_need_digit")
    return out


def _expires(days: int) -> str:
    from datetime import datetime, timedelta
    return (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")


# ---------------------------------------------------------------------------
# TAB'GA XOS SESSIYA (bir brauzer = bir emas, har bir tab' = alohida sessiya)
#
# MUAMMO: sessiya bitta `sid` cookie'si orqali aniqlanardi. Cookie esa bitta
# brauzer bo'ylab UMUMIY — barcha tab'lar va oynalar bir xil qiymatni ko'radi.
# Shuning uchun ikki odam bir xil brauzerda (ikki tab'da) kirsa, ikkinchisi
# birinchisining sessiyasini almashtirib yuboradi: birinchi oyna o'zini
# instruktor deb o'ylashda davom etadi, lekin server undan TALABA ma'lumotini
# qaytaradi. Natijada boshqa odamning ismi, jadvali, xabarlari ko'rinadi.
#
# YECHIM: kalit bitta emas, IKKI qismdan yig'iladi:
#   * qurilma kaliti — HttpOnly `sid` cookie'sida. JS uni KO'RA OLMAYDI,
#     ya'ni XSS orqali olib chiqib ketish mumkin emas.
#   * tab kaliti — `X-Avto-Tab` sarlavhasida, tabga xos (sessionStorage).
#     Bu credential EMAS, faqat indeks: o'zi bilan hech naga kira olmaydi.
# Serverda saqlanadigan kalit ikkalasining kombinatsiyasidan hash qilinadi,
# shuning uchun hech qanday bitta qism credential hisoblanmaydi.
# ---------------------------------------------------------------------------

TAB_HEADER = "X-Avto-Tab"


def new_device_id() -> str:
    """Yangi qurilma (brauzer) kaliti — cookie'ga yoziladi, HttpOnly."""
    return new_token(32)


def session_hash(cred: str, tab: str = None) -> str:
    """So'rov keltirgan kalitdan sessiya kalitini (hash) hisoblaydi.

    `tab` berilsa: sha256(cred:tab) — har bir tab' alohida sessiya oladi.
    `tab` yo'q bo'lsa: sha256(cred) — eski mijozlar (curl, test, bot) uchun.
    """
    if tab:
        return hashlib.sha256(("%s:%s" % (cred, tab)).encode()).hexdigest()
    return hashlib.sha256(cred.encode()).hexdigest()


def create_session(db, user_id: int, remember: bool, tab: str = None, device: str = None) -> str:
    """Sessiya yaratadi va cookie'ga yoziladigan kalitni qaytaradi.

    `tab` berilgan holatda qaytarilgan qiymat — qurilma kaliti (barcha tab'lar
    uchun umumiy, ammo o'zi bilan kirishga imkon bermaydi). Aks holda — eski
    rejim: to'liq sessiya tokeni.

    YONDASHUV: sessiyaning o'zi sessiyaga xos CSRF token'idir
    (`sessions_ring.csrf_token`). `get_session` uni qaytaradi; server uni
    `X-CSRF-Token` sarlavhasi bilan solishtiradi. Token `sid` cookie'sida
    EMAS (HttpOnly), shuning uchun XSS orqali o'g'irlab bo'lmaydi.
    """
    days = 30 if remember else 1
    if tab:
        cred = device or new_device_id()
    else:
        cred = new_token()
    th = session_hash(cred, tab)
    csrf = new_token(24)
    # `token_hash` UNIQUE: bir xil tab'da qayta kiringanda (masalan avvalgi
    # chiqish so'rovi serverga yetib borilmagan bo'lsa) constraint buzilmasin.
    db.upd("DELETE FROM sessions_ring WHERE token_hash=?", (th,))
    db.ex(
        "INSERT INTO sessions_ring(user_id, token_hash, csrf_token, created_at, expires_at) VALUES(?,?,?,?,?)",
        (user_id, th, csrf, now(), _expires(days)),
    )
    return cred


def get_session(db, token: str, tab: str = None):
    """(sessiya qatori | None). CSRF token'i shu qatorning ichida."""
    if not token:
        return None
    th = session_hash(token, tab)
    row = db.q1(
        "SELECT id, user_id, token_hash, csrf_token, expires_at FROM sessions_ring WHERE token_hash=?", (th,)
    )
    if not row:
        return None
    if row["expires_at"] < now():
        db.upd("DELETE FROM sessions_ring WHERE token_hash=?", (th,))
        return None
    return row



def get_session_user(db, token: str, tab: str = None):
    if not token:
        return None
    th = session_hash(token, tab)
    row = db.q1(
        "SELECT user_id, expires_at FROM sessions_ring WHERE token_hash=?", (th,)
    )
    if not row:
        return None
    if row["expires_at"] < now():
        db.upd("DELETE FROM sessions_ring WHERE token_hash=?", (th,))
        return None
    db.upd(
        "UPDATE sessions_ring SET last_seen=? WHERE token_hash=?", (now(), th)
    )
    return db.q1("SELECT * FROM users WHERE id=? AND deleted_at IS NULL", (row["user_id"],))


def destroy_session(db, token: str, tab: str = None) -> None:
    if token:
        db.upd(
            "DELETE FROM sessions_ring WHERE token_hash=?",
            (session_hash(token, tab),),
        )


def destroy_all_sessions(db, user_id: int) -> None:
    db.upd("DELETE FROM sessions_ring WHERE user_id=?", (user_id,))


# ---------------------------------------------------------------------------
# BAND 6 — RATE LIMITING va BRUTE-FORCE HIMOYASI
#
# Ikki darajada:
#   1) login bo'yicha — bitta login'ga juda ko'p urinish (6 urinish / 5 daqiqa)
#   2) IP bo'yicha     — bitta IP'dan juda ko'p urinish (30 urinish / 5 daqiqa),
#                       keyin VAQTINCHalik blok (15 daqiqa). Bu credential
#                       stuffing'ga qarshi: barcha login'larni bir IP orqali
#                       sinab ko'rishni to'xtatadi.
# Ma'lumot xotirada saqlanadi (jarayon davomida) — server qayta ishga
# tushsa, urinishlar ham tozalanadi, bu qasddan shunday.
#
# CHEKLAR MUHIT ORQALI O'ZGARTIRILADI (`.env`):
#   MAX_LOGIN_TRIES, LOGIN_WINDOW_SEC, MAX_IP_TRIES, IP_WINDOW_SEC,
#   IP_BLOCK_SECONDS, API_RATE_MAX (0 = o'chirilgan — test muhiti uchun)
# ---------------------------------------------------------------------------
_ATTEMPTS = {}
_IP_BLOCKS = {}
_ATT_LOCK = threading.Lock()


def _int_env(name: str, default: int) -> int:
    try:
        v = int(str(os.environ.get(name, "") or "").strip())
    except (TypeError, ValueError):
        return default
    return v


MAX_TRIES = _int_env("MAX_LOGIN_TRIES", 6)       # bitta login uchun urinishlar soni
WINDOW = _int_env("LOGIN_WINDOW_SEC", 300)       # oyna (soniya)
MAX_IP_TRIES = _int_env("MAX_IP_TRIES", 30)      # bitta IP uchun urinishlar soni
IP_BLOCK_SECONDS = _int_env("IP_BLOCK_SECONDS", 900)   # bloklash davomiyligi
IP_WINDOW = _int_env("IP_WINDOW_SEC", 300)       # IP urinishlar oynasi (soniya)


def login_allowed(key: str, max_tries: int = MAX_TRIES, window: int = WINDOW) -> bool:
    with _ATT_LOCK:
        now_t = time.time()
        rec = _ATTEMPTS.get(key)
        if rec is None or now_t - rec[1] > window:
            _ATTEMPTS[key] = [1, now_t]
            return True
        if rec[0] >= max_tries:
            return False
        rec[0] += 1
        return True


def reset_login_attempts(key: str) -> None:
    with _ATT_LOCK:
        _ATTEMPTS.pop(key, None)


def ip_blocked(ip: str, max_tries: int = None, window: int = None,
               block_seconds: int = None) -> int:
    """IP bo'yicha vaqtinchalik blok. Qaytaradi: qolgan sekund (0 = blok yo'q).

    `max_tries=0` — bloklash butunlay o'chirilgan (test/ijro muhiti uchun
    `MAX_IP_TRIES=0` orqali sozlanadi).
    """
    max_tries = MAX_IP_TRIES if max_tries is None else max_tries
    window = IP_WINDOW if window is None else window
    block_seconds = IP_BLOCK_SECONDS if block_seconds is None else block_seconds
    if not ip or max_tries <= 0:
        return 0
    ip = str(ip)
    with _ATT_LOCK:
        now_t = time.time()
        until = _IP_BLOCKS.get(ip)
        if until and until > now_t:
            return int(until - now_t)
        if until:
            _IP_BLOCKS.pop(ip, None)  # blok o'tdi — yangi oyno
        rec = _ATTEMPTS.get("ip:" + ip)
        if rec is None or now_t - rec[1] > window:
            _ATTEMPTS["ip:" + ip] = [1, now_t]
            return 0
        rec[0] += 1
        if rec[0] > max_tries:
            _IP_BLOCKS[ip] = now_t + block_seconds
            _ATTEMPTS.pop("ip:" + ip, None)
            return block_seconds
        return 0


def reset_ip_attempts(ip: str) -> None:
    """Muvaffaqiyatli kirish — IP hisobini tozalaydi."""
    if not ip:
        return
    with _ATT_LOCK:
        _ATTEMPTS.pop("ip:" + str(ip), None)
        _IP_BLOCKS.pop(str(ip), None)


def unblock_ip(ip: str) -> None:
    """Blokni oldindan olib tashlash (boshqaruv/avto test uchun)."""
    reset_ip_attempts(ip)


# Umumiy API so'rov limiteri: bitta IP'dan juda ko'p so'rov (DoS ga qarshi).
# `API_RATE_MAX=0` — o'chirilgan (test muhiti uchun; ishlab chiqarishda
# o'chirilmasligi tavsiya etiladi).
_GENERIC = {}
GENERIC_MAX = _int_env("API_RATE_MAX", 1200)     # so'rov / daqiqa (20/soniya)
GENERIC_WINDOW = 60


def api_rate_allowed(ip: str) -> bool:
    if not ip or GENERIC_MAX <= 0:
        return True
    key = "api:" + str(ip)
    with _ATT_LOCK:
        now_t = time.time()
        rec = _GENERIC.get(key)
        if rec is None or now_t - rec[1] > GENERIC_WINDOW:
            _GENERIC[key] = [1, now_t]
            return True
        if rec[0] >= GENERIC_MAX:
            return False
        rec[0] += 1
        return True
