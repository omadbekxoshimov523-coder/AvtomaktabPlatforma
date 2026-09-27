"""AVTOMAKTAB Telegram boti — ishga tushirish nuqtasi.

Ishga tushirish:
    pip install -r bot/requirements.txt
    BOT_TOKEN=... BOT_ADMINS=... python -m bot.main
    (yoki Docker:  docker compose -f docker-compose.prod.yml up -d --build)
"""
import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramAPIError
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, BotCommandScopeChat, ErrorEvent

from .config import load_config
from .db import PLATFORM_SLUG, BotDB
from .handlers import admin_router, schools_router, start_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

# Eslatma: PLATFORM_SLUG (`platforma`) `bot/db.py` da — bot/db.py, bot/main.py
# va admin paneli (/set_url) bir xil qiymatdan foydalanadi.


async def main() -> None:
    cfg = load_config()
    db = BotDB(cfg.db_path)

    bot = Bot(token=cfg.token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    # @username deep link (QR) uchun kerak. DIQQAT: `bot.me` — aiogram metodi,
    # uni qiymat bilan almashtirmaymiz.
    me = await bot.get_me()

    dp = Dispatcher(storage=MemoryStorage())
    dp["cfg"] = cfg
    dp["db"] = db

    dp.include_router(start_router)
    dp.include_router(schools_router)
    dp.include_router(admin_router)

    # ------------------------------------------------------------------ error handler
    @dp.error()
    async def on_error(event: ErrorEvent) -> None:
        logging.exception("Bot xatolik", exc_info=event.exception)
        try:
            if event.update.message:
                await event.update.message.answer("⚠️ Kechirasiz, texnik xatolik yuz berdi. Qaytadan urinib ko'ring.")
            elif event.update.callback_query:
                await event.update.callback_query.answer("Xatolik yuz berdi 😔", show_alert=True)
        except Exception:
            pass

    await bot.set_my_commands([
        BotCommand(command="start", description="🏠 Asosiy menyu"),
        BotCommand(command="lang", description="🌐 Til / Язык / Language"),
        BotCommand(command="help", description="❓ Yordam"),
    ])

    # Admin buyruqlari — faqat admin chatlarida ko'rinadi
    admin_commands = [
        BotCommand(command="admin", description="🛠️ Admin yordami"),
        BotCommand(command="add_school", description="➕ Avtomaktab qo'shish"),
        BotCommand(command="list_schools", description="📋 Ro'yxat"),
        BotCommand(command="edit_school", description="✏️ Tahrirlash"),
        BotCommand(command="set_url", description="🌐 Platforma manzilini yangilash"),
        BotCommand(command="stats", description="📊 Statistika"),
        BotCommand(command="qr", description="🔲 QR kod"),
    ]
    for admin_id in cfg.admins:
        try:
            await bot.set_my_commands(admin_commands, scope=BotCommandScopeChat(chat_id=admin_id))
        except TelegramAPIError as exc:  # admin botni hali boshlagan bo'lishi mumkin
            logging.debug("Admin %s uchun buyruqlarni o'rnatib bo'lmadi: %s", admin_id, exc)

    if not cfg.admins:
        logging.warning("ADMIN_IDS bo'sh — admin buyruqlari ishlamaydi (.env ni tekshiring)")

    # Asosiy platformani ro'yxatga olish: PLATFORM_URL .env da bo'lsa, bot
    # ishga tushganda avtomatik (va takror ishga tushganda xatosiz) qo'shiladi.
    if cfg.platform_url:
        pid, created = db.ensure_school(cfg.platform_name, PLATFORM_SLUG, cfg.platform_url)
        logging.info(
            "Platforma %s: %s (ID %d)", "qo'shildi" if created else "yangilandi",
            cfg.platform_url, pid,
        )
    else:
        logging.info(
            "PLATFORM_URL .env da bo'sh — platforma ro'yxatga qo'shilmadi "
            "(faqat qo'lda qo'shilgan avtomaktablar ko'rinadi)"
        )

    logging.info("Bot ishga tushdi: @%s (adminlar: %s)", me.username, ", ".join(map(str, sorted(cfg.admins))) or "-")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
    except TelegramAPIError as e:
        logging.error("Telegram API xatolik (token to'g'rimi?): %s", e)