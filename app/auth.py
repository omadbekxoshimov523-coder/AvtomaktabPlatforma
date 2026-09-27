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


def create_session(db, user_id: int, remember: bool) -> tuple:
    token = new_token()
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    days = 30 if remember else 1
    db.ex(
        "INSERT INTO sessions_ring(user_id, token_hash, created_at, expires_at) VALUES(?,?,?,?)",
        (user_id, token_hash, now(), _expires(days)),
    )
    return token


def get_session_user(db, token: str):
    if not token:
        return None
    th = hashlib.sha256(token.encode()).hexdigest()
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


def destroy_session(db, token: str) -> None:
    if token:
        db.upd(
            "DELETE FROM sessions_ring WHERE token_hash=?",
            (hashlib.sha256(token.encode()).hexdigest(),),
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