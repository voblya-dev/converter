"""
Регистрация всех роутеров. Импортируется из main.py.
"""
from aiogram import Router
from . import start, input_handler, background, watermark, output_settings, render, language

def setup_routers() -> Router:
    root = Router(name="root")
    root.include_router(start.router)
    root.include_router(language.router)
    root.include_router(background.router)
    root.include_router(watermark.router)
    root.include_router(output_settings.router)
    root.include_router(render.router)
    # input_handler ловит «всё остальное» (сообщения со стикерами/эмодзи/текстом
    # в режиме ожидания ввода), поэтому регистрируется последним.
    root.include_router(input_handler.router)
    return root
