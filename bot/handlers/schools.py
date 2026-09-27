"""Avtomaktab tanlash, kartochka ko'rsatish, muammo haqida xabar berish."""
import html
from datetime import datetime

from aiogram import F, Router
from aiogram.enums import ParseMode
from aiogram.types import CallbackQuery, InputMediaPhoto, Message

from .. import i18n
from ..config import Config
from ..db import BotDB
from ..keyboards import card_kb, menu_kb, report_kb
from ..utils import esc, user_lang

router = Router()


def compose_card_text(school: dict, lang: str) -> str:
    """«📍 Hudud / 📍 Manzil / 📞 Telefon» qatorlaridan kartochka matni."""
    meta = ""
    if school.get("tuman"):
        meta += i18n.t(lang, "school_meta_district", value=esc(school["tuman"]))
    if school.get("manzil"):
        meta += i18n.t(lang, "school_meta_local", value=esc(school["manzil"]))
    if school.get("telefon"):
        meta += i18n.t(lang, "school_meta_phone", value=esc(school["telefon"]))
    return i18n.t(
        lang, "school_card",
        nomi=esc(school["nomi"]), meta=meta, url=esc(school["login_url"]),
    )


async def send_school_card(obj, db: BotDB, cfg: Config, school: dict) -> None:
    """Kartochka + «Kirish» tugmasi. Message (yangi) yoki CallbackQuery (tahrirlash)."""
    lang = user_lang(db, obj.from_user.id, cfg)
    text = compose_card_text(school, lang)
    kb = card_kb(school, lang)
    logo = school.get("logotip_url") or ""

    if isinstance(obj, CallbackQuery):
        if logo:
            try:
                await obj.message.edit_media(
                    InputMediaPhoto(media=logo, caption=text, parse_mode=ParseMode.HTML),
                    reply_markup=kb,
                )
                return await obj.answer()
            except Exception:
                pass  # logotip yuklab bo'lmasa — matn ko'rinishida
        await obj.message.edit_text(text, reply_markup=kb)
        await obj.answer()
    else:
        if logo:
            try:
                await obj.answer_photo(photo=logo, caption=text, reply_markup=kb)
                return
            except Exception:
                pass
        await obj.answer(text, reply_markup=kb)


@router.callback_query(F.data.startswith("school:"))
async def cb_school(callback: CallbackQuery, db: BotDB, cfg: Config) -> None:
    try:
        sid = int(callback.data.split(":", 1)[1])
    except (ValueError, IndexError):
        return await callback.answer()
    school = db.get_school(sid)
    lang = user_lang(db, callback.from_user.id, cfg)
    if not school or not school["faol"]:
        await callback.message.edit_text(i18n.t(lang, "not_found"))
        return await callback.answer()
    db.record_click(sid, callback.from_user.id)
    db.set_last_school(callback.from_user.id, sid)
    await send_school_card(callback, db, cfg, school)


@router.callback_query(F.data == "back")
async def cb_back(callback: CallbackQuery, db: BotDB, cfg: Config) -> None:
    lang = user_lang(db, callback.from_user.id, cfg)
    schools = db.list_schools(active_only=True)
    if not schools:
        await callback.message.edit_text(i18n.t(lang, "empty_list"))
    else:
        await callback.message.edit_text(i18n.t(lang, "choose_school"), reply_markup=menu_kb(db, lang, callback.from_user.id))
    await callback.answer()


@router.callback_query(F.data.startswith("report:"))
async def cb_report(callback: CallbackQuery, db: BotDB, cfg: Config) -> None:
    try:
        sid = int(callback.data.split(":", 1)[1])
    except (ValueError, IndexError):
        return await callback.answer()
    lang = user_lang(db, callback.from_user.id, cfg)
    await callback.message.edit_text(i18n.t(lang, "report_q"), reply_markup=report_kb(sid, lang))
    await callback.answer()


@router.callback_query(F.data.startswith("report_yes:"))
async def cb_report_yes(callback: CallbackQuery, db: BotDB, cfg: Config) -> None:
    try:
        sid = int(callback.data.split(":", 1)[1])
    except (ValueError, IndexError):
        return await callback.answer()
    school = db.get_school(sid)
    lang = user_lang(db, callback.from_user.id, cfg)
    user = callback.from_user
    user_nick = esc(user.first_name or "")
    if user.username:
        user_nick += f" (@{user.username})"
    payload = i18n.t(
        lang, "report_payload",
        nomi=esc(school["nomi"] if school else sid), url=esc(school["login_url"] if school else ""),
        user=user_nick, date=datetime.now().strftime("%Y-%m-%d %H:%M"),
    )
    for admin_id in list(cfg.admins):
        try:
            await callback.bot.send_message(admin_id, payload)
        except Exception:
            pass
    await callback.message.edit_text(i18n.t(lang, "report_sent"))
    await callback.answer()


@router.callback_query(F.data.startswith("report_no:"))
async def cb_report_no(callback: CallbackQuery, db: BotDB, cfg: Config) -> None:
    try:
        sid = int(callback.data.split(":", 1)[1])
    except (ValueError, IndexError):
        return await callback.answer()
    school = db.get_school(sid)
    if school and school["faol"]:
        return await send_school_card(callback, db, cfg, school)  # kartochkaga qaytish
    lang = user_lang(db, callback.from_user.id, cfg)
    await callback.message.edit_text(i18n.t(lang, "report_cancelled"))
    await callback.answer()