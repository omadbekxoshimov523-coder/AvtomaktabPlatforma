"""Admin paneli — avtomaktablar boshqaruvi.

Buyruqlar: /add_school /list_schools /edit_school /set_status
          /remove_school (/delete_school alias) /stats /qr <id|slug> /cancel
"""
import io

import qrcode
from qrcode.constants import ERROR_CORRECT_M

from aiogram import F, Router
from aiogram.filters import BaseFilter, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import BufferedInputFile, CallbackQuery, Message

from .. import i18n
from ..config import Config
from ..db import BotDB
from ..keyboards import edit_fields_kb, schools_kb, yesno_kb
from ..utils import bot_username, esc, slugify, user_lang

router = Router()


# ---------------------------------------------------------------- admin filter
class IsAdmin(BaseFilter):
    async def __call__(self, message: Message, cfg: Config) -> bool:
        return bool(message.from_user and message.from_user.id in cfg.admins)


# ---------------------------------------------------------------- FSM holatlar
class AddSchool(StatesGroup):
    name = State()
    url = State()
    district = State()
    address = State()
    phone = State()
    logo = State()
    confirm = State()


class EditSchool(StatesGroup):
    value = State()


# ------------------------------------------------------------------ umumiy
async def _cancel_state(message: Message, state: FSMContext, db: BotDB, cfg: Config) -> bool:
    """Wizard faol bo'lsa bekor qiladi. False — hech narsa yo'q edi."""
    if await state.get_state() is not None:
        lang = user_lang(db, message.from_user.id, cfg)
        await state.clear()
        await message.answer(i18n.t(lang, "cancelled"))
        return True
    return False


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext, db: BotDB, cfg: Config) -> None:
    if not await _cancel_state(message, state, db, cfg):
        lang = user_lang(db, message.from_user.id, cfg)
        await message.answer(i18n.t(lang, "cancelled"))


@router.message(IsAdmin(), Command("admin"))
async def cmd_admin(message: Message, db: BotDB, cfg: Config) -> None:
    lang = user_lang(db, message.from_user.id, cfg)
    await message.answer(i18n.t(lang, "admin_cmds"))


# =============================================================== /add_school
@router.message(IsAdmin(), Command("add_school"))
async def add_school(message: Message, state: FSMContext, db: BotDB, cfg: Config) -> None:
    lang = user_lang(db, message.from_user.id, cfg)
    await state.clear()
    await state.set_state(AddSchool.name)
    await message.answer(i18n.t(lang, "add_ask_name"))


@router.message(AddSchool.name, F.text)
async def add_name(message: Message, state: FSMContext, db: BotDB, cfg: Config) -> None:
    lang = user_lang(db, message.from_user.id, cfg)
    if not message.text.strip():
        return
    await state.update_data(name=message.text.strip())
    await state.set_state(AddSchool.url)
    await message.answer(i18n.t(lang, "add_ask_url"))


@router.message(AddSchool.url, F.text)
async def add_url(message: Message, state: FSMContext, db: BotDB, cfg: Config) -> None:
    lang = user_lang(db, message.from_user.id, cfg)
    url = message.text.strip()
    if not url.startswith(("http://", "https://")):
        await message.answer(i18n.t(lang, "invalid_url"))
        return
    await state.update_data(url=url)
    await state.set_state(AddSchool.district)
    await message.answer(i18n.t(lang, "add_ask_district"))


@router.message(AddSchool.district, F.text)
async def add_district(message: Message, state: FSMContext, db: BotDB, cfg: Config) -> None:
    lang = user_lang(db, message.from_user.id, cfg)
    v = "" if message.text.strip() == "/skip" else message.text.strip()
    await state.update_data(district=v)
    await state.set_state(AddSchool.address)
    await message.answer(i18n.t(lang, "add_ask_address"))


@router.message(AddSchool.address, F.text)
async def add_address(message: Message, state: FSMContext, db: BotDB, cfg: Config) -> None:
    lang = user_lang(db, message.from_user.id, cfg)
    v = "" if message.text.strip() == "/skip" else message.text.strip()
    await state.update_data(address=v)
    await state.set_state(AddSchool.phone)
    await message.answer(i18n.t(lang, "add_ask_phone"))


@router.message(AddSchool.phone, F.text)
async def add_phone(message: Message, state: FSMContext, db: BotDB, cfg: Config) -> None:
    lang = user_lang(db, message.from_user.id, cfg)
    v = "" if message.text.strip() == "/skip" else message.text.strip()
    await state.update_data(phone=v)
    await state.set_state(AddSchool.logo)
    await message.answer(i18n.t(lang, "add_ask_logo"))


@router.message(AddSchool.logo, F.text)
async def add_logo(message: Message, state: FSMContext, db: BotDB, cfg: Config) -> None:
    lang = user_lang(db, message.from_user.id, cfg)
    v = "" if message.text.strip() == "/skip" else message.text.strip()
    await state.update_data(logotip_url=v)
    data = await state.get_data()
    await state.set_state(AddSchool.confirm)
    await message.answer(
        i18n.t(lang, "add_confirm_q",
               nomi=esc(data.get("name", "")), url=esc(data.get("url", "")),
               tuman=esc(data.get("district", "")), manzil=esc(data.get("address", "")),
               telefon=esc(data.get("phone", ""))),
        reply_markup=yesno_kb("add_yes", i18n.t(lang, "add_yes"), "add_no", i18n.t(lang, "add_no")),
    )


@router.message(AddSchool.confirm, F.text)
async def add_confirm_repeat(message: Message, state: FSMContext, db: BotDB, cfg: Config) -> None:
    lang = user_lang(db, message.from_user.id, cfg)
    data = await state.get_data()
    await message.answer(
        i18n.t(lang, "add_confirm_q",
               nomi=esc(data.get("name", "")), url=esc(data.get("url", "")),
               tuman=esc(data.get("district", "")), manzil=esc(data.get("address", "")),
               telefon=esc(data.get("phone", ""))),
        reply_markup=yesno_kb("add_yes", i18n.t(lang, "add_yes"), "add_no", i18n.t(lang, "add_no")),
    )


async def _save_add(callback: CallbackQuery, state: FSMContext, db: BotDB, cfg: Config) -> None:
    data = await state.get_data()
    await state.clear()
    lang = user_lang(db, callback.from_user.id, cfg)
    base = slugify(data.get("name") or "avtomaktab")
    slug, n = base, 1
    while db.get_school_by_slug(slug):
        n += 1
        slug = f"{base}-{n}"
    sid = db.add_school(
        data.get("name", "?"), slug, data.get("url", ""),
        manzil=data.get("address", ""), telefon=data.get("phone", ""),
        tuman=data.get("district", ""), logotip_url=data.get("logotip_url", ""),
    )
    username = await bot_username(callback.bot)
    await callback.message.edit_text(
        i18n.t(lang, "saved", id=sid, bot=username, slug=slug)
    )
    await callback.answer()


@router.callback_query(F.data == "add_yes")
async def cb_add_yes(callback: CallbackQuery, state: FSMContext, db: BotDB, cfg: Config) -> None:
    await _save_add(callback, state, db, cfg)


@router.callback_query(F.data == "add_no")
async def cb_add_no(callback: CallbackQuery, state: FSMContext, db: BotDB, cfg: Config) -> None:
    lang = user_lang(db, callback.from_user.id, cfg)
    await state.clear()
    await callback.message.edit_text(i18n.t(lang, "cancelled"))
    await callback.answer()


# ============================================================= /list_schools
@router.message(IsAdmin(), Command("list_schools"))
async def list_schools(message: Message, db: BotDB, cfg: Config) -> None:
    lang = user_lang(db, message.from_user.id, cfg)
    schools = db.list_schools(active_only=False)
    if not schools:
        return await message.answer(i18n.t(lang, "list_empty"))
    lines = []
    for s in schools:
        icon = "🟢" if s["faol"] else "⚪"
        lines.append(i18n.t(lang, "list_row", icon=icon, nomi=esc(s["nomi"]), id=s["id"], url=s["login_url"]))
    await message.answer(i18n.t(lang, "list_header") + "\n".join(lines))


# ============================================================= /edit_school
@router.message(IsAdmin(), Command("edit_school"))
async def edit_school(message: Message, state: FSMContext, db: BotDB, cfg: Config) -> None:
    lang = user_lang(db, message.from_user.id, cfg)
    schools = db.list_schools(active_only=False)
    if not schools:
        return await message.answer(i18n.t(lang, "list_empty"))
    await message.answer(i18n.t(lang, "edit_choose"), reply_markup=schools_kb(schools, "ed", lang))


@router.callback_query(F.data.startswith("ed:"))
async def cb_edit_pick(callback: CallbackQuery, db: BotDB, cfg: Config) -> None:
    try:
        sid = int(callback.data.split(":", 1)[1])
    except (ValueError, IndexError):
        return await callback.answer()
    school = db.get_school(sid)
    lang = user_lang(db, callback.from_user.id, cfg)
    if not school:
        return await callback.answer()
    await callback.message.edit_text(
        i18n.t(lang, "edit_field_ask", school=esc(school["nomi"])),
        reply_markup=edit_fields_kb(sid, lang),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("ef:"))
async def cb_edit_field(callback: CallbackQuery, state: FSMContext, db: BotDB, cfg: Config) -> None:
    parts = callback.data.split(":")
    if len(parts) < 3:
        return await callback.answer()
    try:
        sid = int(parts[1])
    except ValueError:
        return await callback.answer()
    field = parts[2]
    school = db.get_school(sid)
    lang = user_lang(db, callback.from_user.id, cfg)
    if not school:
        return await callback.answer()
    await state.update_data(edit_sid=sid, edit_field=field)
    await state.set_state(EditSchool.value)
    await callback.message.edit_text(
        i18n.t(lang, "edit_value_ask", school=esc(school["nomi"]), field=i18n.t(lang, f"field_{field}"))
    )
    await callback.answer()


@router.message(EditSchool.value, F.text)
async def cb_edit_value(message: Message, state: FSMContext, db: BotDB, cfg: Config) -> None:
    lang = user_lang(db, message.from_user.id, cfg)
    data = await state.get_data()
    value = message.text.strip()
    if value == "/cancel":
        await state.clear()
        return await message.answer(i18n.t(lang, "cancelled"))
    if not value:
        return
    field = data.get("edit_field")
    db.update_school(data.get("edit_sid"), **{field: value})
    await state.clear()
    await message.answer(i18n.t(lang, "edited", field=i18n.t(lang, f"field_{field}"), value=esc(value)))


# ============================================================= /set_status
@router.message(IsAdmin(), Command("set_status"))
async def set_status(message: Message, db: BotDB, cfg: Config) -> None:
    lang = user_lang(db, message.from_user.id, cfg)
    schools = db.list_schools(active_only=False)
    if not schools:
        return await message.answer(i18n.t(lang, "list_empty"))
    await message.answer(i18n.t(lang, "status_choose"), reply_markup=schools_kb(schools, "ss", lang))


@router.callback_query(F.data.startswith("ss:"))
async def cb_status_pick(callback: CallbackQuery, db: BotDB, cfg: Config) -> None:
    try:
        sid = int(callback.data.split(":", 1)[1])
    except (ValueError, IndexError):
        return await callback.answer()
    school = db.get_school(sid)
    lang = user_lang(db, callback.from_user.id, cfg)
    if not school:
        return await callback.answer()
    state_now = i18n.t(lang, "status_on" if school["faol"] else "status_off")
    await callback.message.edit_text(
        i18n.t(lang, "status_confirm_q", nomi=esc(school["nomi"]), state=state_now),
        reply_markup=yesno_kb(f"ss_yes:{sid}", i18n.t(lang, "yes_btn"), f"ss_no:{sid}", i18n.t(lang, "no_btn")),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("ss_yes:"))
async def cb_status_yes(callback: CallbackQuery, db: BotDB, cfg: Config) -> None:
    sid = int(callback.data.split(":", 1)[1])
    school = db.get_school(sid)
    lang = user_lang(db, callback.from_user.id, cfg)
    if not school:
        return await callback.answer()
    new_faol = not school["faol"]
    db.set_active(sid, new_faol)
    await callback.message.edit_text(
        i18n.t(lang, "status_updated", nomi=esc(school["nomi"]),
               state=i18n.t(lang, "status_on" if new_faol else "status_off"))
    )
    await callback.answer()


@router.callback_query(F.data.startswith("ss_no:"))
async def cb_status_no(callback: CallbackQuery, db: BotDB, cfg: Config) -> None:
    lang = user_lang(db, callback.from_user.id, cfg)
    await callback.message.edit_text(i18n.t(lang, "cancelled"))
    await callback.answer()


# ============================================== /remove_school (alias: /delete_school)
@router.message(IsAdmin(), Command("remove_school", "delete_school", "del_school"))
async def delete_school(message: Message, db: BotDB, cfg: Config) -> None:
    lang = user_lang(db, message.from_user.id, cfg)
    schools = db.list_schools(active_only=False)
    if not schools:
        return await message.answer(i18n.t(lang, "list_empty"))
    await message.answer(i18n.t(lang, "delete_choose"), reply_markup=schools_kb(schools, "dd", lang))


@router.callback_query(F.data.startswith("dd:"))
async def cb_delete_pick(callback: CallbackQuery, db: BotDB, cfg: Config) -> None:
    try:
        sid = int(callback.data.split(":", 1)[1])
    except (ValueError, IndexError):
        return await callback.answer()
    school = db.get_school(sid)
    lang = user_lang(db, callback.from_user.id, cfg)
    if not school:
        return await callback.answer()
    await callback.message.edit_text(
        i18n.t(lang, "delete_confirm_q", nomi=esc(school["nomi"])),
        reply_markup=yesno_kb(f"dd_yes:{sid}", i18n.t(lang, "delete_yes"), f"dd_no:{sid}", i18n.t(lang, "no_btn")),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("dd_yes:"))
async def cb_delete_yes(callback: CallbackQuery, db: BotDB, cfg: Config) -> None:
    sid = int(callback.data.split(":", 1)[1])
    school = db.get_school(sid)
    lang = user_lang(db, callback.from_user.id, cfg)
    if school:
        db.delete_school(sid)
        await callback.message.edit_text(i18n.t(lang, "deleted", nomi=esc(school["nomi"])))
    await callback.answer()


@router.callback_query(F.data.startswith("dd_no:"))
async def cb_delete_no(callback: CallbackQuery, db: BotDB, cfg: Config) -> None:
    lang = user_lang(db, callback.from_user.id, cfg)
    await callback.message.edit_text(i18n.t(lang, "cancelled"))
    await callback.answer()


# ==================================================================== /stats
@router.message(IsAdmin(), Command("stats"))
async def stats(message: Message, db: BotDB, cfg: Config) -> None:
    lang = user_lang(db, message.from_user.id, cfg)
    rows, users = db.stats()
    if not rows:
        await message.answer(i18n.t(lang, "stats_header") + i18n.t(lang, "stats_empty"))
        return
    lines = [i18n.t(lang, "stats_row", nomi=esc(r["nomi"]), count=r["bosilgan"]) for r in rows]
    await message.answer(i18n.t(lang, "stats_header") + "\n".join(lines) + "\n\n" + i18n.t(lang, "stats_users", users=users))


# ====================================================================== /qr
@router.message(IsAdmin(), Command("qr"))
async def qr_cmd(message: Message, db: BotDB, cfg: Config) -> None:
    lang = user_lang(db, message.from_user.id, cfg)
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2:
        return await message.answer(i18n.t(lang, "qr_usage"))
    ref = parts[1].strip()
    school = db.get_school(int(ref)) if ref.isdigit() else db.get_school_by_slug(ref)
    if not school:
        return await message.answer(i18n.t(lang, "qr_error"))
    username = await bot_username(message.bot)
    link = f"https://t.me/{username}?start={school['slug']}"

    img = qrcode.make(link, error_correction=ERROR_CORRECT_M, box_size=8, border=2)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    await message.answer_photo(
        BufferedInputFile(buf.getvalue(), filename="avtomaktab_qr.png"),
        caption=i18n.t(lang, "qr_sent", bot=username, slug=school["slug"]),
    )