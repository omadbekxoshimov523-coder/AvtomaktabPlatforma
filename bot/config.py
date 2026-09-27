"""Bot konfiguratsiyasi — barcha qiymatlar muhit o'zgaruvchilari (.env) dan o'qiladi.

Qattiq yozilgan token / parol kod ichida YO'Q.
"""
import os
from dataclasses import dataclass, field


@dataclass
class Config:
    token: str
    admins: set[int] = field(default_factory=set)
    default_lang: str = "uz"
    db_path: str = "data/bot.db"


def load_config() -> Config:
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