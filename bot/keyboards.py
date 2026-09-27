"""Inline klaviaturalar (tugmalar)."""
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from . import i18n
from .db import BotDB

FIELD_LABELS = ("nomi", "login_url", "tuman", "manzil", "telefon", "logotip_url")


def _b(text: str, cb: str | None = None, url: str | None = None) -> InlineKeyboardButton:
    if url:
        return InlineKeyboardButton(text=text, url=url)
    return InlineKeyboardButton(text=text, callback_data=cb)


def lang_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=i18n.LANG_NAMES["uz"], callback_data="lang:uz"),
            InlineKeyboardButton(text=i18n.LANG_NAMES["ru"], callback_data="lang:ru"),
            InlineKeyboardButton(text=i18n.LANG_NAMES["en"], callback_data="lang:en"),
        ]
    ])


def menu_kb(db: BotDB, lang: str, user_id: int) -> InlineKeyboardMarkup:
    """Asosiy menyu: so'nggi tanlov (agar bo'lsa) + faol avtomaktablar + til."""
    rows = []
    rec = db.get_user(user_id)
    if rec and rec.get("last_school_id"):
        s = db.get_school(rec["last_school_id"])
        if s and s["faol"]:
            rows.append([_b(i18n.t(lang, "last_btn", nomi=s["nomi"]), cb=f"school:{s['id']}")])
    for s in db.list_schools(active_only=True):
        rows.append([_b(s["nomi"], cb=f"school:{s['id']}")])
    rows.append([_b("🌐 Til / Язык / Language", cb="lang")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def card_kb(school: dict, lang: str) -> InlineKeyboardMarkup:
    """Avtomaktab kartochkasi: Kirish (URL) + muammo + orqaga."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [_b(i18n.t(lang, "open"), url=school["login_url"])],
        [
            _b(i18n.t(lang, "report"), cb=f"report:{school['id']}"),
            _b(i18n.t(lang, "back"), cb="back"),
        ],
    ])


def report_kb(school_id: int, lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            _b(i18n.t(lang, "report_yes"), cb=f"report_yes:{school_id}"),
            _b(i18n.t(lang, "report_no"), cb=f"report_no:{school_id}"),
        ]
    ])


def yesno_kb(yes_cb: str, yes_text: str, no_cb: str, no_text: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [_b(yes_text, cb=yes_cb), _b(no_text, cb=no_cb)]
    ])


def schools_kb(schools: list[dict], prefix: str, lang: str) -> InlineKeyboardMarkup:
    """Admin ro'yxatlari: bitta tugma = bitta avtomaktab (callback: {prefix}:{id})."""
    rows = []
    for s in schools:
        icon = "🟢" if s["faol"] else "⚪"
        rows.append([_b(f"{icon} {s['nomi']} (ID {s['id']})", cb=f"{prefix}:{s['id']}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def edit_fields_kb(school_id: int, lang: str) -> InlineKeyboardMarkup:
    rows = []
    for f in FIELD_LABELS:
        label = i18n.t(lang, f"field_{f}")
        rows.append([_b(f"✏️ {label}", cb=f"ef:{school_id}:{f}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)