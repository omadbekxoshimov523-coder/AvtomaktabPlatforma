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
    -- MODUL 5: individual rejimda jami darslar soni. NULL = platformaning umumiy
    -- sozlamasi (system_settings.total_lessons_target) qo'llaniladi.
    total_lessons_target INTEGER,
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
    -- BAND 14: aniq biznes holati. 'pending' = KUTILMOQDA (tasdiqlanmagan),
    -- 'confirmed' = TASDIQLANGAN. Bajarilgan/bekor qilingan o'z holicha
    -- `status` ustunida qoladi. Noto'g'ri qiymat CHECK bilan bloklanadi.
    confirm_state TEXT NOT NULL DEFAULT 'pending'
        CHECK (confirm_state IN ('pending','confirmed')),
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
    processed_at TEXT DEFAULT '',
    -- MODUL 5: so'rov eskirgan VAQTI (fon vazifa to'ldiradi). Bo'sh = hali
    -- muddati kelmagan. Ro'yxat mantig'i bu ustunga emas, `preferred_date`
    -- (so'ralgan mashg'ulot sanasi) ga tayanadi — bu faqat tarix uchun.
    expired_at TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_pr_pending ON practice_requests(status, preferred_date);

-- BAND 11/12/18: har bir bildirishnoma MUSTAQIL DB record. `source` — uning
-- TABIATI (kim yuborgan / qanday hodisa):
--     ADMIN_MESSAGE | LESSON_REMINDER | LESSON_ASSIGNED | LESSON_COMPLETED
--     | LESSON_CANCELLED | LESSON_RESCHEDULED | PRACTICE_REQUEST | MESSAGE
--     | SECURITY | SYSTEM
-- `data` — metadata (JSON). `related_lesson_id` — qaysi mashg'ulotga tegishli.
-- Eski `type` ustuni (kategoriya: lesson/cancel/request/...) saqlanib qoldi:
-- u `user_settings` bildirishnoma filtrlari bilan bog'liq.
CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id),
    type TEXT DEFAULT 'info',
    source TEXT NOT NULL DEFAULT 'SYSTEM',
    title TEXT DEFAULT '',
    body TEXT DEFAULT '',
    data TEXT DEFAULT '{}',
    is_read INTEGER NOT NULL DEFAULT 0,
    read_at TEXT DEFAULT '',
    sender_id INTEGER REFERENCES users(id),
    sender_role TEXT DEFAULT '',
    related_lesson_id INTEGER REFERENCES lesson_sessions(id) ON DELETE CASCADE,
    created_by INTEGER,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_notif_user ON notifications(user_id, is_read);
-- MUHIM: `source` ustuni va unga bog'liq indekslar (`idx_notif_source`,
-- `ux_notif_reminder_once`) ataylab SHU YERGA yozilmaydi. Sababi: eski
-- bazalarda `notifications` jadvali allaqachon mavjud bo'lib, `source` ustuni
-- faqat `migrate()` da `ALTER TABLE ... ADD COLUMN` bilan qo'shiladi. Agar
-- indeks shu yerda yaratilsa, `migrate()` ishlashidan OLDIN
-- "no such column: source" xatosi bilan server ISHLAMAY qolardi.
-- Har ikkala indeks `migrate()` da (442-446-qatorlar) yaratiladi — yangi va
-- eski bazalar uchun ham xavfsiz.

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
    csrf_token TEXT NOT NULL DEFAULT '',
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

-- BAND 17: "Bildirishnoma sozlamalari" — har bir foydalanuvchi uchun alohida
-- qator. Brauzer yopilsa ham, boshqa qurilmadan kirilsa ham shu yerdan
-- o'qiladi (frontend localStorage'ga YOZMAS).
CREATE TABLE IF NOT EXISTS notification_settings (
    user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    lesson_reminders INTEGER NOT NULL DEFAULT 1,
    admin_messages INTEGER NOT NULL DEFAULT 1,
    lesson_status_updates INTEGER NOT NULL DEFAULT 1,
    messages INTEGER NOT NULL DEFAULT 1,
    requests INTEGER NOT NULL DEFAULT 1,
    security INTEGER NOT NULL DEFAULT 1,
    updated_at TEXT NOT NULL
);

-- BAND 5/7: generatsiya qilingan parollarning BIR O'LCHAMLI izi (SHA-256).
-- Parolning O'ZI saqlanmaydi — shuning uchun admin uni ko'ra olmaydi;
-- faqat "bu parol ilgari chiqarilganmi?" degan savolga javob oladi.
CREATE TABLE IF NOT EXISTS used_credentials (
    login_digest TEXT PRIMARY KEY,
    password_digest TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL
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

    QOID'A: hech qanday mavjud ma'lumot O'CHIRILMAYDI. Faqat `ALTER TABLE
    ... ADD COLUMN` va `CREATE ... IF NOT EXISTS` ishlatiladi — ikkalasi ham
    mavjud qatorlarga tegmaydi va qayta ishga tushirilsa xatosiz o'tadi.
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
    # BAND 18: bildirishnoma arxitekturasi — manba, tegishli mashg'ulot,
    # yaratuvchi. `data` ustuni allaqachon metadata (JSON) uchun ishlatiladi.
    if "source" not in ncols:
        db.upd("ALTER TABLE notifications ADD COLUMN source TEXT NOT NULL DEFAULT 'SYSTEM'")
    if "related_lesson_id" not in ncols:
        db.upd("ALTER TABLE notifications ADD COLUMN related_lesson_id INTEGER")
    if "created_by" not in ncols:
        db.upd("ALTER TABLE notifications ADD COLUMN created_by INTEGER")
    db.upd("CREATE INDEX IF NOT EXISTS idx_notif_source ON notifications(user_id, source, id)")
    db.upd(
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_notif_reminder_once "
        "ON notifications(user_id, related_lesson_id) WHERE source = 'LESSON_REMINDER'"
    )
    # MODUL 5: talaba uchun JUMLI darslar soni. NULL = platforma umumiy
    # sozlamasidan foydalaniladi (individual rejim).
    scols = {r["name"] for r in db.q("PRAGMA table_info(students)")}
    if "total_lessons_target" not in scols:
        db.upd("ALTER TABLE students ADD COLUMN total_lessons_target INTEGER")
    # BAND 14: mashg'ulot tasdiqlash holati (KUTILMOQDA / TASDIQLANGAN)
    lcols = {r["name"] for r in db.q("PRAGMA table_info(lesson_sessions)")}
    if "confirm_state" not in lcols:
        db.upd("ALTER TABLE lesson_sessions ADD COLUMN confirm_state TEXT NOT NULL DEFAULT 'pending'")
    # MODUL 5: so'rov eskirgan vaqti (fon vazifa to'ldiradi). Mavjud ma'lumot
    # O'CHIRILMAYDI — eski qatorlarda bo'sh qoladi va ulardagi muddat
    # `preferred_date` dan to'g'ri hisoblanadi.
    prcols = {r["name"] for r in db.q("PRAGMA table_info(practice_requests)")}
    if "expired_at" not in prcols:
        db.upd("ALTER TABLE practice_requests ADD COLUMN expired_at TEXT DEFAULT ''")
    db.upd("CREATE INDEX IF NOT EXISTS idx_pr_pending ON practice_requests(status, preferred_date)")
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
    # BAND 17: bildirishnoma sozlamalari — alohida jadval (eski bazalarda ham)
    db.upd(
        """CREATE TABLE IF NOT EXISTS notification_settings (
               user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
               lesson_reminders INTEGER NOT NULL DEFAULT 1,
               admin_messages INTEGER NOT NULL DEFAULT 1,
               lesson_status_updates INTEGER NOT NULL DEFAULT 1,
               messages INTEGER NOT NULL DEFAULT 1,
               requests INTEGER NOT NULL DEFAULT 1,
               security INTEGER NOT NULL DEFAULT 1,
               updated_at TEXT NOT NULL)"""
    )
    # BAND 7: chiqarilgan credential izlari (parolning o'zi saqlanmaydi)
    db.upd(
        """CREATE TABLE IF NOT EXISTS used_credentials (
               login_digest TEXT PRIMARY KEY,
               password_digest TEXT NOT NULL UNIQUE,
               created_at TEXT NOT NULL)"""
    )
    # BAND 6: sessiya darajasidagi CSRF token'i (global emas — har sessiyaga alohida)
    sess_cols = {r["name"] for r in db.q("PRAGMA table_info(sessions_ring)")}
    if "csrf_token" not in sess_cols:
        db.upd("ALTER TABLE sessions_ring ADD COLUMN csrf_token TEXT NOT NULL DEFAULT ''")
    # Eski bazalarda bildirishnomalarga tabiiy manba beriladi: `sender_id`
    # bo'lganlar ADMIN_MESSAGE, qolganlari SYSTEM. Hujjatlashtirish/filtrlash
    # to'g'ri ishlashi uchun — matn yoki ID hech qanday o'zgartirilmaydi.
    db.upd(
        "UPDATE notifications SET source = CASE "
        "WHEN sender_id IS NOT NULL THEN 'ADMIN_MESSAGE' ELSE 'SYSTEM' END "
        "WHERE (source IS NULL OR source = '' OR source = 'SYSTEM') "
        "AND sender_id IS NOT NULL"
    )
    # MODUL 1: Audit jurnali (yangi jadval)
    db.upd(
        """CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            user_name TEXT DEFAULT '',
            action_type TEXT NOT NULL,
            target_type TEXT DEFAULT '',
            target_id INTEGER,
            description TEXT DEFAULT '',
            ip_address TEXT DEFAULT '',
            timestamp TEXT NOT NULL
        )"""
    )
    db.upd("CREATE INDEX IF NOT EXISTS idx_audit_log_timestamp ON audit_log(timestamp)")
    db.upd("CREATE INDEX IF NOT EXISTS idx_audit_log_action ON audit_log(action_type)")
    db.upd("CREATE INDEX IF NOT EXISTS idx_audit_log_user ON audit_log(user_id)")


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
    """Avtomatik login/parol: `usrL_<14 xavfsiz random>`, `usrP_<14 xavfsiz random>`.

    BAND 5/7: avvalgi ketma-ket format (`usrL_00001`, `usrP_00001`) olib
    tashlandi — u taxmin qilinishi mumkin edi. Endi har bir qiymat
    `secrets` (cryptographically secure, os.urandom asosida) bilan
    generatsiya qilinadi. Ketma-ket/increment ishlatilmaydi.

    Takrorlanish (collision) bo'lsa — avtomatik qayta generatsiya qilinadi:
    login `users.login UNIQUE`, parol esa `used_credentials.password_digest
    UNIQUE` orqali qayta tekshiriladi. UNIQUE constraint buzilmaydi.

    Transaction ichida bajarilishi shart (ketma-ketlik kafolati).
    """
    from .auth import generate_credentials  # circular import dan qochish uchun lokal
    return generate_credentials(conn)


def jload(value, default=None):
    try:
        return json.loads(value) if value else (default if default is not None else {})
    except Exception:
        return default if default is not None else {}


def jdump(value) -> str:
    return json.dumps(value, ensure_ascii=False)