"""Auto-palette helpers for matching background colors to current input."""
from __future__ import annotations

import asyncio
from pathlib import Path

from utils.colors import hex_to_rgb, rgb_to_hex
from utils.palette import extract_palette


def _mix_rgb(c1: tuple[int, int, int], c2: tuple[int, int, int], amount: float) -> tuple[int, int, int]:
    amount = max(0.0, min(1.0, amount))
    return tuple(int(c1[i] * (1.0 - amount) + c2[i] * amount) for i in range(3))


def auto_palette_pair(colors: list[str]) -> tuple[str, str]:
    if len(colors) >= 2:
        return colors[0], colors[1]
    if colors:
        base = hex_to_rgb(colors[0])
        luminance = 0.2126 * base[0] + 0.7152 * base[1] + 0.0722 * base[2]
        accent = _mix_rgb(base, (255, 255, 255), 0.32) if luminance < 120 else _mix_rgb(base, (0, 0, 0), 0.28)
        return colors[0], rgb_to_hex(accent)
    raise ValueError("empty palette")


def emoji_palette_hint(emoji_text: str | None) -> list[str]:
    if not emoji_text:
        return []
    hints = [
        ("🟢💚✅☘🍀🥬🥦🌲🌳🌿", "#00AA00"),
        ("🔴❤️❤♥🌹🍎🍓🍒", "#E53935"),
        ("🔵💙🫐", "#1E88E5"),
        ("🟡💛⭐🌟✨🌕🍋", "#FDD835"),
        ("🟠🧡🍊🔥", "#FB8C00"),
        ("🟣💜🍇", "#8E24AA"),
        ("⚫🖤", "#202124"),
        ("⚪🤍", "#F1F3F4"),
    ]
    chars = set(emoji_text)
    for group, color in hints:
        if chars.intersection(group):
            return [color]
    return []


def resolve_auto_palette(input_type: str | None, src_file: Path | None, emoji: str | None) -> tuple[str, str] | None:
    colors = extract_palette(input_type, src_file, emoji)
    if not colors:
        colors = emoji_palette_hint(emoji)
    if not colors:
        return None
    return auto_palette_pair(colors)


def apply_auto_palette(settings: dict, src_file: Path | None = None) -> bool:
    if not settings["background"].get("auto_palette"):
        return False
    input_settings = settings.get("input", {})
    pair = resolve_auto_palette(
        input_settings.get("type"),
        src_file,
        input_settings.get("emoji"),
    )
    if not pair:
        return False
    color1, color2 = pair
    settings["background"].update({
        "mode": "gradient",
        "auto_palette": True,
        "color": color1,
        "color2": color2,
        "direction": "diagonal",
    })
    return True


async def resolve_auto_palette_async(input_type: str | None, src_file: Path | None, emoji: str | None) -> tuple[str, str] | None:
    colors = await asyncio.to_thread(extract_palette, input_type, src_file, emoji)
    if not colors:
        colors = emoji_palette_hint(emoji)
    if not colors:
        return None
    return auto_palette_pair(colors)


async def apply_auto_palette_async(settings: dict, src_file: Path | None = None) -> bool:
    if not settings["background"].get("auto_palette"):
        return False
    input_settings = settings.get("input", {})
    pair = await resolve_auto_palette_async(
        input_settings.get("type"),
        src_file,
        input_settings.get("emoji"),
    )
    if not pair:
        return False
    color1, color2 = pair
    settings["background"].update({
        "mode": "gradient",
        "auto_palette": True,
        "color": color1,
        "color2": color2,
        "direction": "diagonal",
    })
    return True
