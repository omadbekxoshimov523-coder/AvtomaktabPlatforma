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
from aiogram.types import BotCommand, ErrorEvent

from .config import load_config
from .db import BotDB
from .handlers import admin_router, schools_router, start_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


async def main() -> None:
    cfg = load_config()
    db = BotDB(cfg.db_path)

    bot = Bot(token=cfg.token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    # @username va deep-link uchun kerak bo'ladi
    bot.me = await bot.get_me()

    dp = Dispatcher(storage=MemoryStorage())
    dp["cfg"] = cfg
    dp["db"] = db

    dp.include_router(start_router)
    dp.include_router(schools_router)
    dp.include_router(admin_router)

    # ------------------------------------------------------------------ error handler
    @dp.errors.register()
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

    if not cfg.admins:
        logging.warning("BOT_ADMINS bo'sh — admin buyruqlari ishlamaydi (.env ni tekshiring)")

    logging.info("Bot ishga tushdi: @%s (adminlar: %s)", bot.me.username, ", ".join(map(str, sorted(cfg.admins))) or "-")
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