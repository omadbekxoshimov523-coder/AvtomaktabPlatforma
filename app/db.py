"""SQLite ma'lumotlar bazasi: sxema, ulanish, yordamchi funksiyalar.
Sxema mijoz talablaridagi barcha jadvallarni o'z ichiga oladi:
users, students, instructors, cars, car_brands, car_models, license_categories,
lesson_sessions, session_students, practice_requests, attendance, notifications,
messages, audit_logs, password_reset_tokens, credential_sequence,
system_settings, translations, branches.
"""
import json
import os
import sqlite3
import threading
from datetime import datetime

SCHEMA = """
CREATE TABLE IF NOT EXISTS credential_sequence (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    last_number INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    middle_name TEXT DEFAULT '',
    birth_date TEXT DEFAULT '',
    gender TEXT DEFAULT '',
    phone TEXT DEFAULT '',
    secondary_phone TEXT DEFAULT '',
    login TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('admin','student','instructor')),
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','blocked','archived')),
    profile_image TEXT DEFAULT '',
    must_change_password INTEGER NOT NULL DEFAULT 0,
    last_login_at TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    deleted_at TEXT DEFAULT NULL
);
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);
CREATE INDEX IF NOT EXISTS idx_users_deleted ON users(deleted_at);

CREATE TABLE IF NOT EXISTS students (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    group_name TEXT DEFAULT '',
    license_category TEXT DEFAULT 'B',
    study_status TEXT DEFAULT 'active' CHECK (study_status IN ('active','paused','graduated','expelled')),
    enrolled_at TEXT DEFAULT '',
    address TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    status TEXT NOT NULL DEFAULT 'active'
);

CREATE TABLE IF NOT EXISTS instructors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    license_categories TEXT DEFAULT 'B',
    experience_years INTEGER DEFAULT 0,
    bio TEXT DEFAULT '',
    work_days TEXT NOT NULL DEFAULT '["mon","tue","wed","thu","fri","sat"]',
    work_start TEXT NOT NULL DEFAULT '08:00',
    work_end TEXT NOT NULL DEFAULT '18:00',
    break_start TEXT DEFAULT '13:00',
    break_end TEXT DEFAULT '14:00',
    assigned_car_id INTEGER REFERENCES cars(id) ON DELETE SET NULL,
    status TEXT NOT NULL DEFAULT 'active'
);

CREATE TABLE IF NOT EXISTS car_brands (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS car_models (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    brand_id INTEGER NOT NULL REFERENCES car_brands(id),
    name TEXT NOT NULL,
    UNIQUE(brand_id, name)
);

CREATE TABLE IF NOT EXISTS cars (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    brand_id INTEGER REFERENCES car_brands(id),
    model_id INTEGER REFERENCES car_models(id),
    custom_model_name TEXT DEFAULT '',
    brand TEXT DEFAULT '',
    model TEXT DEFAULT '',
    plate_number TEXT NOT NULL UNIQUE,
    year INTEGER DEFAULT 0,
    color TEXT DEFAULT '',
    seat_count INTEGER DEFAULT 4,
    practice_capacity INTEGER NOT NULL DEFAULT 4,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','repair','checkup','inactive')),
    technical_inspection_date TEXT DEFAULT '',
    insurance_expiry TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    deleted_at TEXT DEFAULT NULL
);
CREATE INDEX IF NOT EXISTS idx_cars_plate ON cars(plate_number);

CREATE TABLE IF NOT EXISTS car_photos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    car_id INTEGER NOT NULL REFERENCES cars(id) ON DELETE CASCADE,
    path TEXT NOT NULL,
    position INTEGER DEFAULT 0,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_car_photos_car ON car_photos(car_id);

CREATE TABLE IF NOT EXISTS lesson_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL,
    instructor_id INTEGER NOT NULL REFERENCES instructors(id),
    car_id INTEGER REFERENCES cars(id),
    car_name_snapshot TEXT DEFAULT '',
    car_plate_snapshot TEXT DEFAULT '',
    capacity_snapshot INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'scheduled' CHECK (status IN ('scheduled','ongoing','completed','cancelled')),
    notes TEXT DEFAULT '',
    cancel_reason TEXT DEFAULT '',
    started_at TEXT DEFAULT '',
    completed_at TEXT DEFAULT '',
    original_date TEXT DEFAULT '',
    original_start_time TEXT DEFAULT '',
    original_end_time TEXT DEFAULT '',
    original_instructor_id INTEGER,
    rescheduled_from_id INTEGER,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sessions_date ON lesson_sessions(date);
CREATE INDEX IF NOT EXISTS idx_sessions_instructor ON lesson_sessions(instructor_id);
CREATE INDEX IF NOT EXISTS idx_sessions_status ON lesson_sessions(status);

CREATE TABLE IF NOT EXISTS session_students (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL REFERENCES lesson_sessions(id) ON DELETE CASCADE,
    student_id INTEGER NOT NULL REFERENCES students(id),
    pickup_address TEXT DEFAULT '',
    pickup_lat REAL,
    pickup_lng REAL,
    attendance_status TEXT NOT NULL DEFAULT 'unmarked' CHECK (attendance_status IN ('unmarked','present','late','absent')),
    student_status TEXT NOT NULL DEFAULT 'active' CHECK (student_status IN ('active','removed')),
    joined_at TEXT NOT NULL,
    removed_at TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    UNIQUE(session_id, student_id)
);
CREATE INDEX IF NOT EXISTS idx_ss_session ON session_students(session_id);
CREATE INDEX IF NOT EXISTS idx_ss_student ON session_students(student_id);

CREATE TABLE IF NOT EXISTS attendance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL REFERENCES lesson_sessions(id),
    student_id INTEGER NOT NULL REFERENCES students(id),
    status TEXT NOT NULL,
    marked_by INTEGER,
    marked_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS practice_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL REFERENCES students(id),
    preferred_date TEXT DEFAULT '',
    preferred_start_time TEXT DEFAULT '',
    preferred_end_time TEXT DEFAULT '',
    message TEXT DEFAULT '',
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','approved','rejected','cancelled','rescheduled')),
    admin_note TEXT DEFAULT '',
    session_id INTEGER,
    created_at TEXT NOT NULL,
    processed_at TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id),
    type TEXT DEFAULT 'info',
    title TEXT DEFAULT '',
    body TEXT DEFAULT '',
    data TEXT DEFAULT '{}',
    is_read INTEGER NOT NULL DEFAULT 0,
    read_at TEXT DEFAULT '',
    sender_id INTEGER REFERENCES users(id),
    sender_role TEXT DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_notif_user ON notifications(user_id, is_read);

-- M6: 2FA SMS kodlar (QR'siz oqim). Kod bildirishnoma orqali simulyatsiya qilinadi.
CREATE TABLE IF NOT EXISTS twofa_codes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id),
    code_hash TEXT NOT NULL,
    phone TEXT DEFAULT '',
    expires_at TEXT NOT NULL,
    used_at TEXT DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_twofa_codes_user ON twofa_codes(user_id, used_at);

-- M4/M5: soft-delete — foydalanuvchi o'chirgan tarix/so'rovlar shu yerda "yashirinadi",
-- asl jadval qatorlari audit uchun saqlanadi.
CREATE TABLE IF NOT EXISTS hidden_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    session_id INTEGER NOT NULL,
    hidden_at TEXT NOT NULL,
    UNIQUE(user_id, session_id)
);
CREATE INDEX IF NOT EXISTS idx_hidden_history_user ON hidden_history(user_id);

CREATE TABLE IF NOT EXISTS hidden_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    request_id INTEGER NOT NULL,
    hidden_at TEXT NOT NULL,
    UNIQUE(user_id, request_id)
);
CREATE INDEX IF NOT EXISTS idx_hidden_requests_user ON hidden_requests(user_id);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER,
    from_user_id INTEGER NOT NULL REFERENCES users(id),
    to_user_id INTEGER NOT NULL REFERENCES users(id),
    text TEXT NOT NULL,
    is_read INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_msg_pair ON messages(from_user_id, to_user_id);

CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    admin_id INTEGER,
    action TEXT NOT NULL,
    entity_type TEXT DEFAULT '',
    entity_id INTEGER,
    details TEXT DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions_ring (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    token_hash TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    last_seen TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS password_reset_tokens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    token_hash TEXT NOT NULL UNIQUE,
    expires_at TEXT NOT NULL,
    used_at TEXT DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS user_settings (
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    key TEXT NOT NULL,
    value TEXT DEFAULT '',
    updated_at TEXT NOT NULL,
    PRIMARY KEY (user_id, key)
);

CREATE TABLE IF NOT EXISTS system_settings (
    key TEXT PRIMARY KEY,
    value TEXT DEFAULT '',
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS translations (
    key TEXT PRIMARY KEY,
    uz TEXT DEFAULT '',
    ru TEXT DEFAULT '',
    en TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS branches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    address TEXT DEFAULT '',
    phone TEXT DEFAULT '',
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""

_LOCK = threading.Lock()


def now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


class Db:
    """Har bir so'rov uchun yangi ulanish ochadigan yengil wrapper."""

    def __init__(self, path: str):
        self.path = path

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        return conn

    def q(self, sql, params=()) -> list:
        with self.connect() as c:
            return [dict(r) for r in c.execute(sql, params).fetchall()]

    def q1(self, sql, params=()):
        with self.connect() as c:
            r = c.execute(sql, params).fetchone()
            return dict(r) if r else None

    def ex(self, sql, params=()) -> int:
        with self.connect() as c:
            cur = c.execute(sql, params)
            c.commit()
            return cur.lastrowid

    def exmany(self, sql, rows) -> None:
        with self.connect() as c:
            c.executemany(sql, rows)
            c.commit()

    def upd(self, sql, params=()) -> int:
        with self.connect() as c:
            cur = c.execute(sql, params)
            c.commit()
            return cur.rowcount

    def transaction(self, fn):
        """fn(conn) ichida bajariladi, xato bo'lsa rollback."""
        with self.connect() as c:
            try:
                result = fn(c)
                c.commit()
                return result
            except Exception:
                c.rollback()
                raise


def migrate(db: Db) -> None:
    """Mavjud bazaga yangi ustunlarni xavfsiz qo'shadi (idempotent).

    `CREATE TABLE IF NOT EXISTS` mavjud jadvalga ustun qo'shmaydi, shuning
    uchun yangi xususiyatlar (masalan 2FA) eski bazalar uchun bu yerda
    migratsiya qilinadi.
    """
    cols = {r["name"] for r in db.q("PRAGMA table_info(users)")}
    if "totp_secret" not in cols:
        db.upd("ALTER TABLE users ADD COLUMN totp_secret TEXT DEFAULT ''")
    if "totp_enabled" not in cols:
        db.upd("ALTER TABLE users ADD COLUMN totp_enabled INTEGER NOT NULL DEFAULT 0")
    # M1: bildirishnoma jo'natuvchisi (eski bazalar uchun ham xavfsiz)
    ncols = {r["name"] for r in db.q("PRAGMA table_info(notifications)")}
    if "sender_id" not in ncols:
        db.upd("ALTER TABLE notifications ADD COLUMN sender_id INTEGER")
    if "sender_role" not in ncols:
        db.upd("ALTER TABLE notifications ADD COLUMN sender_role TEXT DEFAULT ''")
    # M5: avtomobil fotosuratlari (eski bazalar uchun ham xavfsiz)
    db.upd(
        """CREATE TABLE IF NOT EXISTS car_photos (
               id INTEGER PRIMARY KEY AUTOINCREMENT,
               car_id INTEGER NOT NULL REFERENCES cars(id) ON DELETE CASCADE,
               path TEXT NOT NULL,
               position INTEGER DEFAULT 0,
               created_at TEXT NOT NULL)"""
    )
    db.upd("CREATE INDEX IF NOT EXISTS idx_car_photos_car ON car_photos(car_id)")
    # M12: foydalanuvchi sozlamalari (til/tema/bildirishnoma prefs) — eski bazalar uchun ham xavfsiz
    db.upd(
        """CREATE TABLE IF NOT EXISTS user_settings (
               user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
               key TEXT NOT NULL,
               value TEXT DEFAULT '',
               updated_at TEXT NOT NULL,
               PRIMARY KEY (user_id, key))"""
    )


def init_db(path: str) -> Db:
    db = Db(path)
    with db.connect() as c:
        c.executescript(SCHEMA)
        c.execute(
            "INSERT OR IGNORE INTO credential_sequence(id,last_number,created_at,updated_at) VALUES(1,0,?,?)",
            (now(), now()),
        )
        c.commit()
    migrate(db)
    return db


def next_credentials(conn: sqlite3.Connection) -> tuple:
    """Avtomatik login/parol: usrL_00001, usrP_00001 ...
    Transaction ichida bajarilishi shart — takrorlanmasligi kafolatlanadi."""
    row = conn.execute("SELECT last_number FROM credential_sequence WHERE id=1").fetchone()
    n = int(row["last_number"]) + 1
    conn.execute(
        "UPDATE credential_sequence SET last_number=?, updated_at=? WHERE id=1",
        (n, now()),
    )
    return f"usrL_{n:05d}", f"usrP_{n:05d}"


def jload(value, default=None):
    try:
        return json.loads(value) if value else (default if default is not None else {})
    except Exception:
        return default if default is not None else {}


def jdump(value) -> str:
    return json.dumps(value, ensure_ascii=False)