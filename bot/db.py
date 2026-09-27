"""Bot ma'lumotlar bazasi (SQLite, faqat stdlib).

Jadval `avtomaktablar` — bot orqali taqdim etiladigan avtomaktablar ro'yxati
(id, nomi, slug, login_url, logotip_url, manzil, telefon, tuman, faol).
Qo'shimcha jadvallar: `users` (til + so'nggi tanlov), `clicks` (statistika).
"""
import os
import sqlite3
import threading
from datetime import datetime


def now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# Asosiy platforma yozuvi uchun barqaror slug.
# Deep link shu slug orqali ishlaydi: t.me/<bot>?start=platforma
PLATFORM_SLUG = "platforma"


class BotDB:
    def __init__(self, path: str):
        self.path = path
        parent = os.path.dirname(os.path.abspath(path))
        os.makedirs(parent, exist_ok=True)
        self._lock = threading.Lock()
        self._init_schema()

    def _conn(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.path)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("PRAGMA foreign_keys=ON")
        return con

    def _init_schema(self):
        with self._lock, self._conn() as con:
            con.executescript(
                """
                CREATE TABLE IF NOT EXISTS avtomaktablar (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    nomi        TEXT NOT NULL,
                    slug        TEXT NOT NULL UNIQUE,
                    login_url   TEXT NOT NULL,
                    logotip_url TEXT NOT NULL DEFAULT '',
                    manzil      TEXT NOT NULL DEFAULT '',
                    telefon     TEXT NOT NULL DEFAULT '',
                    tuman       TEXT NOT NULL DEFAULT '',
                    faol        INTEGER NOT NULL DEFAULT 1,
                    created_at  TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS users (
                    user_id        INTEGER PRIMARY KEY,
                    first_name     TEXT NOT NULL DEFAULT '',
                    username       TEXT NOT NULL DEFAULT '',
                    lang           TEXT NOT NULL DEFAULT 'uz',
                    last_school_id INTEGER,
                    last_seen      TEXT
                );
                CREATE TABLE IF NOT EXISTS clicks (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    school_id  INTEGER NOT NULL,
                    user_id    INTEGER NOT NULL,
                    clicked_at TEXT NOT NULL
                );
                """
            )

    # ---------------------------------------------------------------- avtomaktablar
    def list_schools(self, active_only: bool = True) -> list[dict]:
        q = "SELECT * FROM avtomaktablar"
        if active_only:
            q += " WHERE faol=1"
        q += " ORDER BY nomi COLLATE NOCASE"
        with self._lock, self._conn() as con:
            return [dict(r) for r in con.execute(q).fetchall()]

    def get_school(self, school_id: int) -> dict | None:
        with self._lock, self._conn() as con:
            r = con.execute("SELECT * FROM avtomaktablar WHERE id=?", (school_id,)).fetchone()
            return dict(r) if r else None

    def get_school_by_slug(self, slug: str) -> dict | None:
        with self._lock, self._conn() as con:
            r = con.execute("SELECT * FROM avtomaktablar WHERE slug=?", (slug,)).fetchone()
            return dict(r) if r else None

    def add_school(self, nomi, slug, login_url, manzil="", telefon="", tuman="", logotip_url=""):
        with self._lock, self._conn() as con:
            cur = con.execute(
                "INSERT INTO avtomaktablar(nomi,slug,login_url,logotip_url,manzil,telefon,tuman,faol,created_at) "
                "VALUES(?,?,?,?,?,?,?,1,?)",
                (nomi, slug, login_url, logotip_url, manzil, telefon, tuman, now()),
            )
            return cur.lastrowid

    def ensure_school(self, nomi: str, slug: str, login_url: str, **fields) -> tuple[int, bool]:
        """Slug bo'yicha avtomaktabni kafolatlaydi.

        Yo'q bo'lsa — yaratadi. Bor bo'lsa — faqat `login_url` o'zgarganda
        yangilaydi (admin tomonidan tahrirlangan nom/manzil/telefon saqlanib qoladi).

        Qaytaradi: (id, yangi_yaratildi_mi)
        """
        existing = self.get_school_by_slug(slug)
        if existing:
            if existing["login_url"] != login_url:
                self.update_school(existing["id"], login_url=login_url)
            return existing["id"], False
        return self.add_school(nomi, slug, login_url, **fields), True

    def update_school(self, school_id: int, **fields) -> None:
        allowed = {"nomi", "slug", "login_url", "logotip_url", "manzil", "telefon", "tuman"}
        sets = {k: v for k, v in fields.items() if k in allowed}
        if not sets:
            return
        cols = ", ".join(f"{k}=?" for k in sets)
        vals = list(sets.values()) + [school_id]
        with self._lock, self._conn() as con:
            con.execute(f"UPDATE avtomaktablar SET {cols} WHERE id=?", vals)

    def set_active(self, school_id: int, faol: bool) -> None:
        with self._lock, self._conn() as con:
            con.execute("UPDATE avtomaktablar SET faol=? WHERE id=?", (1 if faol else 0, school_id))

    def delete_school(self, school_id: int) -> None:
        with self._lock, self._conn() as con:
            con.execute("DELETE FROM clicks WHERE school_id=?", (school_id,))
            con.execute("DELETE FROM avtomaktablar WHERE id=?", (school_id,))

    # ------------------------------------------------------------------- users
    def upsert_user(self, user_id: int, first_name: str = "", username: str = "", lang: str = "uz") -> None:
        with self._lock, self._conn() as con:
            con.execute(
                "INSERT INTO users(user_id,first_name,username,lang,last_seen) VALUES(?,?,?,?,?) "
                "ON CONFLICT(user_id) DO UPDATE SET first_name=excluded.first_name, "
                "username=excluded.username, last_seen=excluded.last_seen",
                (user_id, first_name, username, lang, now()),
            )

    def get_user(self, user_id: int) -> dict | None:
        with self._lock, self._conn() as con:
            r = con.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
            return dict(r) if r else None

    def set_lang(self, user_id: int, lang: str) -> None:
        with self._lock, self._conn() as con:
            con.execute("UPDATE users SET lang=? WHERE user_id=?", (lang, user_id))

    # --------------------------------------------------------------- statistika
    def record_click(self, school_id: int, user_id: int) -> None:
        with self._lock, self._conn() as con:
            con.execute("INSERT INTO clicks(school_id,user_id,clicked_at) VALUES(?,?,?)", (school_id, user_id, now()))

    def stats(self) -> tuple[list[dict], int]:
        with self._lock, self._conn() as con:
            rows = con.execute(
                "SELECT s.id, s.nomi, s.faol, COUNT(c.id) AS bosilgan "
                "FROM avtomaktablar s LEFT JOIN clicks c ON c.school_id=s.id "
                "GROUP BY s.id ORDER BY bosilgan DESC, s.nomi COLLATE NOCASE"
            ).fetchall()
            users = con.execute("SELECT COUNT(*) c FROM users").fetchone()["c"]
            return [dict(r) for r in rows], users