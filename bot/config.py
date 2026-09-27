"""Bot konfiguratsiyasi — barcha qiymatlar muhit o'zgaruvchilari (.env) dan o'qiladi.

Qattiq yozilgan token / parol kod ichida YO'Q.
"""
import os
from dataclasses import dataclass, field


def _load_dotenv(path: str | None = None) -> None:
    """Loyiha ildizidagi .env faylini muhit o'zgaruvchilariga yuklaydi.

    Docker'da compose allaqachon o'zgaruvchilarni beradi — shuning uchun
    allaqach mavjud bo'lgan qiymatlar HECH QACHON qayta yozilmaydi (setdefault).
    """
    if path is None:
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        path = os.path.join(root, ".env")
    if not os.path.isfile(path):
        return
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


@dataclass
class Config:
    token: str
    admins: set[int] = field(default_factory=set)
    default_lang: str = "uz"
    db_path: str = "data/bot.db"


def load_config() -> Config:
    _load_dotenv()
    token = os.environ.get("BOT_TOKEN", "").strip()
    if not token:
        raise SystemExit(
            "XATO: BOT_TOKEN muhit o'zgaruvchisi ko'rsatilmagan.\n"
            ".env faylida BOT_TOKEN=<BotFather tokeni> qo'ying."
        )

    admins: set[int] = set()
    for part in os.environ.get("BOT_ADMINS", "").split(","):
        part = part.strip()
        if part.isdigit():
            admins.add(int(part))

    default_lang = os.environ.get("BOT_DEFAULT_LANG", "uz").strip().lower()
    if default_lang not in ("uz", "ru", "en"):
        default_lang = "uz"

    db_path = os.environ.get("BOT_DB") or os.path.join("data", "bot.db")
    return Config(token=token, admins=admins, default_lang=default_lang, db_path=db_path)