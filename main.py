"""
Точка входа Telegram-бота. Запускает long-polling.

Перед запуском:
  1.  Скопируй .env.example -> .env  и впиши свой BOT_TOKEN.
  2.  Установи зависимости из requirements.txt.
  3.  Убедись, что ffmpeg в PATH (или укажи путь в .env).
"""
import asyncio
import logging
from logging.handlers import RotatingFileHandler
import sys
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramUnauthorizedError
from aiogram.types import BotCommand

from config import BOT_TOKEN, LOG_DIR, LOG_LEVEL
from handlers import setup_routers
from utils.cleanup import cleanup_tmp


def _setup_logging() -> None:
    level = getattr(logging, LOG_LEVEL.upper(), logging.INFO)
    fmt = logging.Formatter(
        "%(asctime)s · %(levelname)-7s · %(name)s · %(message)s",
        datefmt="%H:%M:%S",
    )
    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()

    stream = logging.StreamHandler()
    stream.setFormatter(fmt)
    root.addHandler(stream)

    file_handler = RotatingFileHandler(
        LOG_DIR / "bot.log",
        maxBytes=2_000_000,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(fmt)
    root.addHandler(file_handler)


async def main() -> None:
    _setup_logging()
    log = logging.getLogger("bot")
    removed_tmp = cleanup_tmp()
    if removed_tmp:
        log.info("Удалено устаревших временных элементов: %s", removed_tmp)

    if not BOT_TOKEN:
        log.error("BOT_TOKEN не задан. Создайте файл .env на основе .env.example.")
        sys.exit(1)

    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()
    dp.include_router(setup_routers())

    # Сбрасываем pending updates, чтобы не подхватить старые при перезапуске.
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await bot.set_my_commands([
            BotCommand(command="start", description="Главное меню"),
            BotCommand(command="menu", description="Открыть меню"),
            BotCommand(command="help", description="Как пользоваться ботом"),
            BotCommand(command="lang", description="Сменить язык"),
        ])
        me = await bot.get_me()
        log.info("Бот @%s запущен. Готов к работе.", me.username)
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    except TelegramUnauthorizedError:
        log.error("Telegram отклонил BOT_TOKEN. Проверьте токен в .env и получите новый у @BotFather при необходимости.")
        sys.exit(1)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
