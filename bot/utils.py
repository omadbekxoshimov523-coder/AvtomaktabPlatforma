"""Umumiy yordamchi funksiyalar."""
import html
import re

from . import i18n
from .config import Config
from .db import BotDB


def user_lang(db: BotDB, user_id: int, cfg: Config) -> str:
    rec = db.get_user(user_id)
    return rec["lang"] if rec and rec.get("lang") else cfg.default_lang


def esc(value) -> str:
    """Telegram HTML uchun xavfsiz matn."""
    return html.escape(str(value or ""), quote=False)


def slugify(text: str) -> str:
    """«Avtomaktab Chilonzor» -> avtomaktab-chilonzor (deep link slug)."""
    s = (text or "").lower()
    for k, v in (("o'", "o"), ("g'", "g"), ("ʻ", ""), ("'", ""), ("ʼ", "")):
        s = s.replace(k, v)
    s = re.sub(r"[^a-z0-9\u0400-\u04ff]+", "-", s).strip("-")
    # Agar kirill/tartibsiz qoldiq bo'lsa — lotin'ga yaqinlashtirishga urinib ko'ramiz
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or "avtomaktab"