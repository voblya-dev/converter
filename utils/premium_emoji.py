"""Premium/custom Telegram emoji helpers."""
from __future__ import annotations

import re
from html import escape

from aiogram.types import InlineKeyboardButton


EMOJI_IDS: dict[str, str] = {
    "default": "5472221053059078763",
    "👋": "5472235990955334730",
    "🎨": "5274090977584234781",
    "📤": "5472367477084134145",
    "🔄": "5472012979073456920",
    "📚": "5472386598278536459",
    "🌐": "5388658581664993142",
    "🎛": "5472170432574528133",
    "📐": "5472355270787079946",
    "💧": "5472209190359407741",
    "⬅️": "5472012979073456920",
    "🏠": "5472170432574528133",
    "✅": "5472180551517477902",
    "❌": "5382355635553739365",
    "🪄": "5456289640673719977",
    "😀": "5202166634906687918",
    "🖼": "5280643001733882743",
    "🎞": "5222175680652917218",
    "✏️": "5382316645840619380",
    "↔️": "5472012979073456920",
    "↕️": "5472012979073456920",
    "↘️": "5472012979073456920",
    "🌈": "5472185383355685814",
    "📦": "5472170432574528133",
    "📏": "5472355270787079946",
    "💎": "5472221053059078763",
    "🎬": "5222175680652917218",
    "⏱": "5319272710688226013",
    "🗂": "5472170432574528133",
    "📁": "5472170432574528133",
    "📍": "5472145951260941641",
    "🌀": "5472012979073456920",
    "✨": "5472221053059078763",
    "⏳": "5319272710688226013",
    "⚠️": "5229231985502723757",
    "ℹ️": "5471930335312747865",
    "🏷": "5472170432574528133",
    "🔥": "5273731647735348062",
    "🔍": "5472252840112037845",
    "💻": "5339181821135431228",
    "👍": "5318771518069551523",
    "🎉": "5388674524583572460",
    "🛑": "5472030751648127392",
    "📱": "5472200252532464654",
}

_CUSTOM_EMOJI_RE = re.compile(r"<tg-emoji\s+emoji-id=\"\d+\">.*?</tg-emoji>", re.DOTALL)
_TEXT_EMOJI_RE = re.compile(
    "|".join(re.escape(k) for k in sorted((k for k in EMOJI_IDS if k != "default"), key=len, reverse=True))
)


def tg_emoji(symbol: str, emoji_id: str | None = None) -> str:
    return f'<tg-emoji emoji-id="{emoji_id or EMOJI_IDS.get(symbol, EMOJI_IDS["default"])}">{escape(symbol)}</tg-emoji>'


def premiumize_text(text: str) -> str:
    """Replace known plain emoji in HTML text with Telegram custom emoji tags."""
    chunks: list[str] = []
    pos = 0
    for match in _CUSTOM_EMOJI_RE.finditer(text):
        chunks.append(_TEXT_EMOJI_RE.sub(lambda m: tg_emoji(m.group(0)), text[pos:match.start()]))
        chunks.append(match.group(0))
        pos = match.end()
    chunks.append(_TEXT_EMOJI_RE.sub(lambda m: tg_emoji(m.group(0)), text[pos:]))
    return "".join(chunks)


def premium_button(
    text: str,
    callback_data: str,
    *,
    icon: str | None = None,
    style: str | None = None,
) -> InlineKeyboardButton:
    data: dict[str, str] = {"text": text, "callback_data": callback_data}
    if icon:
        data["icon_custom_emoji_id"] = EMOJI_IDS.get(icon, EMOJI_IDS["default"])
    if style:
        data["style"] = style
    return InlineKeyboardButton(**data)
