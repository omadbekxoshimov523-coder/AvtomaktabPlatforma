"""Xavfsizlik: parol hashing (scrypt), session/token boshqaruvi, RBAC, rate limiting.
Plaintext parol database'da saqlanmaydi — faqat hash.
"""
import hashlib
import hmac
import secrets
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
    """
    days = 30 if remember else 1
    if tab:
        cred = device or new_device_id()
    else:
        cred = new_token()
    th = session_hash(cred, tab)
    # `token_hash` UNIQUE: bir xil tab'da qayta kiringanda (masalan avvalgi
    # chiqish so'rovi serverga yetib borilmagan bo'lsa) constraint buzilmasin.
    db.upd("DELETE FROM sessions_ring WHERE token_hash=?", (th,))
    db.ex(
        "INSERT INTO sessions_ring(user_id, token_hash, created_at, expires_at) VALUES(?,?,?,?)",
        (user_id, th, now(), _expires(days)),
    )
    return cred


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
# Rate limiting (login urinishlari bo'yicha)
# ---------------------------------------------------------------------------
_ATTEMPTS = {}
_ATT_LOCK = threading.Lock()


def login_allowed(key: str, max_tries: int = 6, window: int = 300) -> bool:
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