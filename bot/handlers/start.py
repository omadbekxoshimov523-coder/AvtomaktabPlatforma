"""/start, til tanlash (/lang), yordam (/help).

Deep link:  t.me/<bot>?start=<slug>  -> tanlangan avtomaktab to'g'ridan-to'g'ri
ochiladi (QR kod uchun tayyor havola).
"""
from aiogram import F, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from .. import i18n
from ..config import Config
from ..db import BotDB
from ..keyboards import lang_kb, menu_kb
from ..utils import esc, user_lang
from .schools import send_school_card

router = Router()

SUPPORTED_LANGS = ("uz", "ru", "en")


def _menu_text(lang: str, name: str, note: str = "") -> str:
    head = note + "\n\n" if note else ""
    return head + i18n.t(lang, "welcome", name=name) + "\n\n" + i18n.t(lang, "choose_school")


async def _empty_text(db: BotDB, cfg: Config, lang: str, user_id: int) -> str:
    """Bo'sh ro'yxat holati — admin uchun qo'shish ishorasi bilan."""
    hint = "empty_admin_hint" if user_id in cfg.admins else "empty_hint"
    return i18n.t(lang, "empty_list") + "\n\n" + i18n.t(lang, hint)


async def _show_menu(message: Message, db: BotDB, cfg: Config, lang: str, note: str = "") -> None:
    schools = db.list_schools(active_only=True)
    if not schools:
        await message.answer(
            await _empty_text(db, cfg, lang, message.from_user.id), reply_markup=lang_kb()
        )
        return
    name = esc(message.from_user.first_name or "")
    await message.answer(_menu_text(lang, name, note), reply_markup=menu_kb(db, lang))


@router.message(CommandStart())
async def cmd_start(message: Message, command: CommandObject, state: FSMContext, db: BotDB, cfg: Config) -> None:
    user = message.from_user
    if await state.get_state() is not None:
        await state.clear()  # /start — joriy amalni tozalaydi

    rec = db.get_user(user.id)
    lang = (rec or {}).get("lang") or cfg.default_lang
    first_time = rec is None
    payload = (command.args or "").strip()

    if not first_time:
        db.upsert_user(user.id, user.first_name or "", user.username or "", lang)

    # ---- Deep link: t.me/<bot>?start=<slug> ----
    if payload:
        school = db.get_school_by_slug(payload)
        if school and school["faol"]:
            db.record_click(school["id"], user.id)
            await send_school_card(message, db, cfg, school)
            return
        return await _show_menu(message, db, cfg, lang, note=i18n.t(lang, "not_found"))

    # Birinchi marta — tilni aniq tanlatsin (default til: BOT_DEFAULT_LANG=uz).
    # Sabab: Telegram profili ko'pincha boshqa tilda bo'ladi (masalan en) —
    # o'zbek mijozlari uchun default UZ to'g'ri.
    if first_time:
        db.upsert_user(user.id, user.first_name or "", user.username or "", cfg.default_lang)
        await message.answer(i18n.t(cfg.default_lang, "welcome_first"), reply_markup=lang_kb())
        return

    await _show_menu(message, db, cfg, lang)


@router.message(Command("lang"))
async def cmd_lang(message: Message, db: BotDB, cfg: Config) -> None:
    lang = user_lang(db, message.from_user.id, cfg)
    await message.answer(i18n.t(lang, "choose_lang"), reply_markup=lang_kb())


@router.message(Command("help"))
async def cmd_help(message: Message, db: BotDB, cfg: Config) -> None:
    lang = user_lang(db, message.from_user.id, cfg)
    await message.answer(i18n.t(lang, "help"))


@router.callback_query(F.data == "lang")
async def cb_lang_menu(callback: CallbackQuery, db: BotDB, cfg: Config) -> None:
    lang = user_lang(db, callback.from_user.id, cfg)
    await callback.message.edit_text(i18n.t(lang, "choose_lang"), reply_markup=lang_kb())
    await callback.answer()


@router.callback_query(F.data.startswith("lang:"))
async def cb_lang_set(callback: CallbackQuery, state: FSMContext, db: BotDB, cfg: Config) -> None:
    lang = callback.data.split(":", 1)[1]
    if lang not in SUPPORTED_LANGS:
        return await callback.answer()
    db.set_lang(callback.from_user.id, lang)
    # Wizard'da bo'lsa (admin) — tilga xalaqit bermaslik uchun amalni tozalaymiz
    if await state.get_state() is not None:
        await state.clear()
    schools = db.list_schools(active_only=True)
    if not schools:
        await callback.message.edit_text(
            await _empty_text(db, cfg, lang, callback.from_user.id), reply_markup=lang_kb()
        )
    else:
        text = i18n.t(lang, "lang_saved", lang=i18n.LANG_NAMES[lang]) + "\n\n" + i18n.t(lang, "choose_school")
        await callback.message.edit_text(text, reply_markup=menu_kb(db, lang))
    await callback.answer()