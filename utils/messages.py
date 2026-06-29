"""Telegram message helpers."""
from __future__ import annotations

from aiogram.types import Message


async def edit_or_answer(message: Message, text: str, **kwargs) -> None:
    """Edit text messages; send a new message for media/caption messages."""
    if message.text:
        await message.edit_text(text, **kwargs)
    else:
        await message.answer(text, **kwargs)
