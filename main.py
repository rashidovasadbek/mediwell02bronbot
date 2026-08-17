# -*- coding: utf-8 -*-
"""mediwell02_bron_bot — kirish nuqtasi.

Ishga tushirish:
    venv\\Scripts\\activate      (Windows)
    source venv/bin/activate    (Linux)
    python -m db.migrate        # baza sxemasini qo'llash
    python main.py
"""
import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand

from config import ConfigError, load_settings, setup_logging
from db.pool import close_pool, init_pool
from handlers import admin, bron, common, pharmacy_admin
from middlewares.auth import AuthMiddleware
from middlewares.context import CompanyMiddleware
from services import company as company_service

logger = logging.getLogger(__name__)

COMMANDS = [
    BotCommand(command="start", description="Botni qayta ishga tushirish"),
    BotCommand(command="help", description="Yordam va qo'llanma"),
    BotCommand(command="id", description="ID raqamimni ko'rsatish"),
    BotCommand(command="admin", description="Admin panel (faqat adminlar)"),
]


def build_dispatcher(settings) -> Dispatcher:
    # workflow_data — handlerlar `settings` argumentini so'rasa shu keladi
    dp = Dispatcher(settings=settings)

    # Outer middleware: filtrlar chaqirilishidan oldin ishlaydi, shuning
    # uchun `is_admin` router filtrlariga ham yetib boradi.
    auth = AuthMiddleware(bootstrap_admin_id=settings.bootstrap_admin_id)
    company_mw = CompanyMiddleware(company_code=settings.company_code)
    for observer in (dp.message, dp.callback_query, dp.inline_query):
        observer.outer_middleware(auth)
        observer.outer_middleware(company_mw)

    # Tartib muhim: admin routerlari oldinroq (ular IsAdmin bilan
    # cheklangan, o'tmasa keyingisiga tushadi).
    dp.include_router(admin.router)
    dp.include_router(pharmacy_admin.router)
    dp.include_router(bron.router)
    dp.include_router(common.router)
    return dp


async def main() -> None:
    try:
        settings = load_settings()
    except ConfigError as e:
        logging.basicConfig(level=logging.INFO)
        logger.error("❌ Sozlama xatosi: %s", e)
        raise SystemExit(1)

    setup_logging(settings.log_level)

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = build_dispatcher(settings)

    await init_pool(settings)
    company = await company_service.get(settings.company_code)
    logger.info(
        "Kompaniya: %s (sho't kodi %s)", company["name"], company["account_code"]
    )

    await bot.set_my_commands(COMMANDS)
    me = await bot.get_me()
    logger.info("Bot ishga tushdi... 🚀  @%s", me.username)

    try:
        await dp.start_polling(bot)
    finally:
        await close_pool()
        await bot.session.close()
        logger.info("Bot to'xtatildi.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
