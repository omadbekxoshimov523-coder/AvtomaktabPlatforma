"""Bot konfiguratsiyasi — barcha qiymatlar muhit o'zgaruvchilaridan (.env) o'qiladi.

QOID'A: token / parol kod ichida QATTIQ YOZILMAYDI. Faqat `os.environ`
(read-only) orqali o'qiladi. `.env` fayl esa `.gitignore`'da.

Muhit o'zgaruvchilari:
    BOT_TOKEN        — @BotFather'dan olingan token (SHART)
    ADMIN_IDS        — admin Telegram user_id'lari, vergul bilan (alias: BOT_ADMINS)
    BOT_DEFAULT_LANG — default til: uz | ru | en
    BOT_DB           — SQLite fayl yo'li (default: data/bot.db)
"""
import os
from dataclasses import dataclass, field

try:  # python-dotenv (requirements.txt da bor)
    from dotenv import load_dotenv as _dotenv_load
except ImportError:  # pragma: no cover — pip install qilinmagan muhit uchun zaxira
    _dotenv_load = None

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # loyiha ildizi
_BOT_DIR = os.path.dirname(os.path.abspath(__file__))


def _simple_load(path: str) -> None:
    """python-dotenv yo'q bo'lsa — sodda .env o'quvchi (stdlib, faqat yangi qiymat qo'shadi)."""
    try:
        with open(path, encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, val = line.partition("=")
                os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))
    except OSError:
        pass  # .env yo'q/ochib bo'lmaydi — muhit o'zgaruvchilariga tayanamiz


def _load_dotenv() -> None:
    """`.env` faylini yuklaydi (loyiha ildizi yoki bot/ ichida).

    Muhit o'zgaruvchilari ALLERTAQCHON o'rnatilgan bo'lsa, ular QAYTA
    yozilmaydi (override=False) — shuning uchun Docker'da compose'ning
    bergan qiymatlari ustun bo'lib qoladi.
    """
    for path in (os.path.join(_ROOT, ".env"), os.path.join(_BOT_DIR, ".env")):
        if not os.path.isfile(path):
            continue
        if _dotenv_load:
            _dotenv_load(path, override=False)
        else:
            _simple_load(path)


@dataclass
class Config:
    token: str
    admins: set[int] = field(default_factory=set)
    default_lang: str = "uz"
    db_path: str = "data/bot.db"


def load_db_path() -> str:
    """Faqat SQLite fayl yo'lini o'qish (seed/backup skriptlari uchun — token talab qilmaydi)."""
    _load_dotenv()
    return os.environ.get("BOT_DB") or os.path.join("data", "bot.db")


def load_config() -> Config:
    _load_dotenv()
    token = os.environ.get("BOT_TOKEN", "").strip()
    if not token:
        raise SystemExit(
            "XATO: BOT_TOKEN muhit o'zgaruvchisi ko'rsatilmagan.\n"
            "  → .env faylga qo'ying:  BOT_TOKEN=<BotFather tokeni>\n"
            "  → namuna uchun:        bot/.env.example"
        )

    # ADMIN_IDS — asosiy nom; BOT_ADMINS — eski nom (moslik uchun qo'llab-quvvatlanadi)
    raw_admins = os.environ.get("ADMIN_IDS") or os.environ.get("BOT_ADMINS", "")
    admins: set[int] = set()
    for part in raw_admins.split(","):
        part = part.strip()
        if part.isdigit():
            admins.add(int(part))

    default_lang = os.environ.get("BOT_DEFAULT_LANG", "uz").strip().lower()
    if default_lang not in ("uz", "ru", "en"):
        default_lang = "uz"

    return Config(
        token=token,
        admins=admins,
        default_lang=default_lang,
        db_path=load_db_path(),
    )
