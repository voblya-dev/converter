"""
Сборка всех инлайн-клавиатур бота. Колбэк-данные используют префиксы
вида ``ns:bg:color:#1E88E5`` чтобы упростить роутинг.

Префиксы:
  main:*   — главное меню
  bg:*     — фон
  out:*    — настройки вывода
  wm:*     — водяной знак
  pos:*    — стрелки позиционирования
  lang:*   — переключатель языка
  noop     — пустое нажатие (для подсветки текущей ячейки)
"""
from __future__ import annotations
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from config import (
    BACKGROUNDS_DIR, RESOLUTION_PRESETS, FPS_OPTIONS,
    QUALITY_LEVELS, OUTPUT_FORMATS, WM_ROTATIONS, BUILTIN_FONTS,
)
from utils.i18n import t
from utils.premium_emoji import premium_button


def _plain(label: str) -> str:
    for symbol in (
        "👋", "🎛", "📐", "🎨", "💧", "📤", "🔄", "📚", "🌐", "⬅️", "🏠",
        "🖼", "🎞", "✏️", "↔️", "↕️", "↘️", "📦", "📏", "💎", "🎬", "⏱",
        "✅", "❌", "🗂", "📁", "📍", "🔍", "🌀", "✨", "🛑", "🧪",
        "🌈", "⚠️", "ℹ️", "🏷", "🔥", "💻", "👍", "🎉", "📱", "💎",
    ):
        label = label.replace(symbol, "").strip()
    return " ".join(label.split())


def kt(lang: str, key: str, **kwargs) -> str:
    return t(lang, key, plain=True, **kwargs)


def _add(kb: InlineKeyboardBuilder, text: str, callback_data: str, icon: str | None = None, style: str | None = None) -> None:
    kb.add(premium_button(_plain(text), callback_data, icon=icon, style=style))

# ─────────────────────────  ГЛАВНОЕ МЕНЮ  ─────────────────────────
def main_menu(lang: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    _add(kb, kt(lang, "btn_background"), "bg:menu", icon="🎨", style="primary")
    _add(kb, kt(lang, "btn_watermark"), "wm:menu", icon="💧", style="primary")
    _add(kb, kt(lang, "btn_settings"), "out:menu", icon="📐", style="primary")
    _add(kb, kt(lang, "btn_reset"), "main:reset", icon="🔄", style="danger")
    kb.adjust(2, 2)
    return kb.as_markup()


# ─────────────────────────  ФОН  ─────────────────────────
def bg_menu(lang: str, mode: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    def mark(curr: str) -> str:
        return "● " if mode == curr else ""
    _add(kb, mark("color") + kt(lang, "bg_mode_color"), "bg:mode:color", icon="🎨", style="primary")
    _add(kb, mark("gradient") + kt(lang, "bg_mode_gradient"), "bg:mode:gradient", icon="🌈", style="primary")
    _add(kb, mark("image") + kt(lang, "bg_mode_image"), "bg:mode:image", icon="🖼")
    _add(kb, mark("video") + kt(lang, "bg_mode_video"), "bg:mode:video", icon="🎬")
    _add(kb, mark("global_image") + kt(lang, "bg_mode_global"), "bg:global", icon="📚")
    _add(kb, kt(lang, "btn_back"), "main:home", icon="⬅️", style="danger")
    kb.adjust(2, 2, 2)
    return kb.as_markup()


def hex_color_kb(lang: str, slot: int = 1) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    _add(kb, kt(lang, "bg_enter_hex"), f"bg:hex:{slot}", icon="✏️", style="primary")
    _add(kb, kt(lang, "btn_back"), "bg:menu", icon="⬅️", style="primary")
    kb.adjust(1, 1)
    return kb.as_markup()


def gradient_menu(lang: str, direction: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    _add(kb, kt(lang, "bg_pick_color1"), "bg:pick:1", icon="🎨", style="primary")
    _add(kb, kt(lang, "bg_pick_color2"), "bg:pick:2", icon="🎨", style="primary")
    def mark(d: str) -> str:
        return "● " if direction == d else ""
    _add(kb, mark("horizontal") + kt(lang, "bg_dir_h"), "bg:dir:horizontal", icon="🔄")
    _add(kb, mark("vertical") + kt(lang, "bg_dir_v"), "bg:dir:vertical", icon="🔄")
    _add(kb, mark("diagonal") + kt(lang, "bg_dir_d"), "bg:dir:diagonal", icon="🔄")
    _add(kb, kt(lang, "btn_back"), "bg:menu", icon="⬅️", style="danger")
    kb.adjust(2, 2, 2)
    return kb.as_markup()


def global_backgrounds_kb(lang: str, current: str | None) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    files = [
        p.name for p in sorted(BACKGROUNDS_DIR.iterdir())
        if p.is_file() and p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}
    ][:30]
    for idx, name in enumerate(files):
        label = BACKGROUNDS_DIR.joinpath(name).stem
        mark = "● " if name == current else ""
        kb.button(text=f"{mark}{label[:32]}", callback_data=f"bg:setglobal:{idx}")
    _add(kb, kt(lang, "btn_back"), "bg:menu", icon="⬅️", style="danger")
    if files:
        kb.adjust(1)
    return kb.as_markup()


def admin_menu(lang: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    _add(kb, kt(lang, "admin_add_bg"), "admin:add_bg", icon="🖼", style="primary")
    _add(kb, kt(lang, "admin_list_bg"), "admin:list_bg", icon="📚")
    _add(kb, kt(lang, "btn_main"), "main:home", icon="🏠")
    kb.adjust(1)
    return kb.as_markup()


# ─────────────────────────  НАСТРОЙКИ ВЫВОДА  ─────────────────────────
def out_menu(lang: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    _add(kb, kt(lang, "out_format"), "out:format", icon="📦")
    _add(kb, kt(lang, "out_resolution"), "out:res", icon="📏")
    _add(kb, kt(lang, "out_fps"), "out:fps", icon="🎬")
    _add(kb, kt(lang, "out_quality"), "out:quality", icon="💎")
    _add(kb, kt(lang, "out_speed"), "out:speed", icon="⏱")
    _add(kb, kt(lang, "input_size"), "out:inputsize", icon="🔍")
    _add(kb, kt(lang, "input_colorize"), "out:colorize", icon="🎨")
    _add(kb, kt(lang, "btn_back"), "main:home", icon="⬅️", style="danger")
    kb.adjust(2, 2, 2, 2)
    return kb.as_markup()


def out_formats(lang: str, current: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for f in OUTPUT_FORMATS:
        mark = "● " if f == current else ""
        kb.button(text=f"{mark}{f.upper()}", callback_data=f"out:setformat:{f}")
    _add(kb, kt(lang, "btn_back"), "out:menu", icon="⬅️", style="danger")
    kb.adjust(4, 1)
    return kb.as_markup()


def out_resolutions(lang: str, current_wh: tuple[int, int]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for label, w, h in RESOLUTION_PRESETS:
        mark = "● " if (w, h) == current_wh else ""
        kb.button(text=f"{mark}{label}", callback_data=f"out:setres:{w}x{h}")
    _add(kb, kt(lang, "out_custom_res"), "out:resCustom", icon="✏️", style="primary")
    _add(kb, kt(lang, "btn_back"), "out:menu", icon="⬅️", style="danger")
    kb.adjust(2, 2, 1, 1, 1)
    return kb.as_markup()


def out_fps_kb(lang: str, current) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for f in FPS_OPTIONS:
        mark = "● " if f == current else ""
        kb.button(text=f"{mark}{f}", callback_data=f"out:setfps:{f}")
    mark = "● " if current == "source" else ""
    _add(kb, mark + kt(lang, "out_fps_source"), "out:setfps:source", icon="🎬")
    _add(kb, kt(lang, "btn_back"), "out:menu", icon="⬅️", style="danger")
    kb.adjust(4, 1, 1)
    return kb.as_markup()


def out_quality_kb(lang: str, current: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    titles = {"low": "Низкое", "medium": "Среднее", "high": "Высокое", "lossless": "Без сжатия"}
    titles_en = {"low": "Low", "medium": "Medium", "high": "High", "lossless": "Lossless"}
    src = titles_en if lang == "en" else titles
    for q in QUALITY_LEVELS:
        mark = "● " if q == current else ""
        kb.button(text=f"{mark}{src[q]}", callback_data=f"out:setquality:{q}")
    _add(kb, kt(lang, "btn_back"), "out:menu", icon="⬅️", style="danger")
    kb.adjust(2, 2, 1)
    return kb.as_markup()


def out_speed_kb(lang: str, current: float) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for s in (0.5, 0.75, 1.0, 1.25, 1.5, 2.0):
        mark = "● " if abs(s - current) < 1e-6 else ""
        kb.button(text=f"{mark}×{s}", callback_data=f"out:setspeed:{s}")
    _add(kb, kt(lang, "btn_back"), "out:menu", icon="⬅️", style="danger")
    kb.adjust(3, 3, 1)
    return kb.as_markup()


def input_size_kb(lang: str, current: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for pct in (50, 60, 70, 80, 90, 100):
        mark = "● " if pct == current else ""
        kb.button(text=f"{mark}{pct}%", callback_data=f"out:setinputsize:{pct}")
    kb.button(text="−", callback_data="out:inputsize:-5")
    kb.button(text=f"{current}%", callback_data="noop")
    kb.button(text="+", callback_data="out:inputsize:+5")
    _add(kb, kt(lang, "btn_back"), "out:menu", icon="⬅️", style="danger")
    kb.adjust(3, 3, 3, 1)
    return kb.as_markup()


def input_colorize_kb(lang: str, cfg: dict) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    enabled = bool(cfg.get("enabled"))
    _add(
        kb,
        kt(lang, "input_colorize_disable" if enabled else "input_colorize_enable"),
        "out:colorize:toggle",
        icon="✅" if enabled else "❌",
        style="success" if enabled else "danger",
    )
    _add(kb, kt(lang, "input_colorize_hex"), "out:colorize:hex", icon="✏️", style="primary")
    for value in (50, 70, 85, 100):
        mark = "● " if int(cfg.get("strength", 85)) == value else ""
        kb.button(text=f"{mark}{value}%", callback_data=f"out:colorize:strength:{value}")
    _add(kb, kt(lang, "btn_back"), "out:menu", icon="⬅️")
    kb.adjust(2, 4, 1)
    return kb.as_markup()


# ─────────────────────────  ВОДЯНОЙ ЗНАК  ─────────────────────────
def wm_menu(lang: str, enabled: bool) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    if enabled:
        _add(kb, kt(lang, "wm_disable"), "wm:toggle", icon="❌")
    else:
        _add(kb, kt(lang, "wm_enable"), "wm:toggle", icon="✅")
    _add(kb, kt(lang, "wm_source"), "wm:source", icon="🗂")
    _add(kb, kt(lang, "wm_upload"), "wm:upload", icon="📁")
    _add(kb, kt(lang, "wm_position"), "wm:position", icon="📍")
    _add(kb, kt(lang, "wm_size"), "wm:size", icon="🔍")
    _add(kb, kt(lang, "wm_alpha"), "wm:alpha", icon="🌀")
    _add(kb, kt(lang, "wm_rotation"), "wm:rotation", icon="🔄")
    _add(kb, kt(lang, "wm_font"), "wm:font", icon="✏️")
    _add(kb, kt(lang, "wm_font_color"), "wm:fontcolor", icon="🎨")
    _add(kb, kt(lang, "wm_effects"), "wm:effects", icon="✨")
    _add(kb, kt(lang, "btn_back"), "main:home", icon="⬅️", style="danger")
    kb.adjust(2, 2, 2, 2, 2, 2)
    return kb.as_markup()


def wm_source_kb(lang: str, current: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    items = [("text", "Текст" if lang == "ru" else "Text", "✏️"),
             ("image", "Изображение" if lang == "ru" else "Image", "🖼"),
             ("preset", "Пресет" if lang == "ru" else "Preset", "📚")]
    for code, label, icon in items:
        mark = "● " if code == current else ""
        _add(kb, f"{mark}{label}", f"wm:setsource:{code}", icon=icon)
    _add(kb, kt(lang, "btn_back"), "wm:menu", icon="⬅️", style="danger")
    kb.adjust(3, 1)
    return kb.as_markup()


def wm_position_kb(lang: str, current: str = "mc") -> InlineKeyboardMarkup:
    """Only position arrows/anchors. Selected anchor is highlighted with success style."""
    kb = InlineKeyboardBuilder()
    anchors = [
        ("↖", "tl"), ("↑", "tc"), ("↗", "tr"),
        ("←", "ml"), ("•", "mc"), ("→", "mr"),
        ("↙", "bl"), ("↓", "bc"), ("↘", "br"),
    ]
    for text, code in anchors:
        style = "success" if code == current else None
        kb.add(premium_button(text, f"pos:anchor:{code}", icon="✅" if code == current else None, style=style))
    kb.button(text="↑",      callback_data="pos:nudge:up")
    kb.button(text="←",      callback_data="pos:nudge:left")
    kb.button(text="·",      callback_data="pos:reset")
    kb.button(text="→",      callback_data="pos:nudge:right")
    kb.button(text="↓",      callback_data="pos:nudge:down")
    _add(kb, kt(lang, "btn_back"), "wm:menu", icon="⬅️", style="danger")
    kb.adjust(3, 3, 3, 1, 3, 1, 1)
    return kb.as_markup()


def wm_alpha_kb(lang: str, alpha: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="−10", callback_data="wm:alpha:-10")
    kb.button(text="−",   callback_data="wm:alpha:-5")
    kb.button(text=f"{alpha}%", callback_data="noop")
    kb.button(text="+",   callback_data="wm:alpha:+5")
    kb.button(text="+10", callback_data="wm:alpha:+10")
    _add(kb, kt(lang, "btn_back"), "wm:menu", icon="⬅️", style="danger")
    kb.adjust(5, 1)
    return kb.as_markup()


def wm_size_kb(lang: str, size: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="−10", callback_data="wm:size:-10")
    kb.button(text="−",   callback_data="wm:size:-5")
    kb.button(text=f"{size}%", callback_data="noop")
    kb.button(text="+",   callback_data="wm:size:+5")
    kb.button(text="+10", callback_data="wm:size:+10")
    _add(kb, kt(lang, "btn_back"), "wm:menu", icon="⬅️", style="danger")
    kb.adjust(5, 1)
    return kb.as_markup()


def wm_rotation_kb(lang: str, current: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for r in WM_ROTATIONS:
        mark = "● " if r == current else ""
        kb.button(text=f"{mark}{r}°", callback_data=f"wm:setrot:{r}")
    _add(kb, kt(lang, "btn_back"), "wm:menu", icon="⬅️", style="danger")
    kb.adjust(4, 4, 1)
    return kb.as_markup()


def wm_font_kb(lang: str, current: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for name, _file in BUILTIN_FONTS:
        mark = "● " if name == current else ""
        kb.button(text=f"{mark}{name}", callback_data=f"wm:setfont:{name}")
    # Кнопка загрузки своего шрифта
    _add(kb, "TTF/OTF", "wm:fontupload", icon="📁", style="primary")
    _add(kb, kt(lang, "btn_back"), "wm:menu", icon="⬅️", style="danger")
    kb.adjust(2, 2, 2, 2, 2, 1, 1, 1)
    return kb.as_markup()


def wm_font_color_kb(lang: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    _add(kb, kt(lang, "bg_enter_hex"), "wm:fontcolorHex", icon="✏️", style="primary")
    _add(kb, kt(lang, "btn_back"), "wm:menu", icon="⬅️", style="danger")
    kb.adjust(1, 1)
    return kb.as_markup()


def wm_effects_kb(lang: str, wm: dict) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    _add(kb, ("● " if wm["shadow"] else "") + ("Тень" if lang == "ru" else "Shadow"), "wm:effect:shadow", icon="✅" if wm["shadow"] else "✨", style="success" if wm["shadow"] else None)
    _add(kb, ("● " if wm["stroke"] else "") + ("Обводка" if lang == "ru" else "Stroke"), "wm:effect:stroke", icon="✅" if wm["stroke"] else "✨", style="success" if wm["stroke"] else None)
    _add(kb, ("● " if wm["glow"] else "") + ("Свечение" if lang == "ru" else "Glow"), "wm:effect:glow", icon="✅" if wm["glow"] else "✨", style="success" if wm["glow"] else None)
    _add(kb, ("Цвет эффекта" if lang == "ru" else "Effect color"), "wm:effectcolor", icon="🎨", style="primary")
    kb.button(text=("Радиус −" if lang == "ru" else "Radius −"),         callback_data="wm:radius:-1")
    kb.button(text=f"r={wm['effect_radius']}", callback_data="noop")
    kb.button(text=("Радиус +" if lang == "ru" else "Radius +"),         callback_data="wm:radius:+1")
    _add(kb, kt(lang, "btn_back"), "wm:menu", icon="⬅️")
    kb.adjust(3, 1, 3, 1)
    return kb.as_markup()


# ─────────────────────────  СЕРВИСНЫЕ  ─────────────────────────
def back_to_main(lang: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    _add(kb, kt(lang, "btn_main"), "main:home", icon="🏠", style="danger")
    return kb.as_markup()


def cancel_render(lang: str = "ru") -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    _add(kb, kt(lang, "render_cancel"), "render:cancel", icon="🛑", style="danger")
    return kb.as_markup()


def render_result(lang: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    _add(kb, kt(lang, "btn_settings"), "out:menu", icon="📐", style="primary")
    _add(kb, kt(lang, "btn_background"), "bg:menu", icon="🎨", style="primary")
    kb.adjust(2)
    return kb.as_markup()


def preview_result(lang: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    _add(kb, kt(lang, "btn_render"), "main:render", icon="🌀", style="success")
    _add(kb, kt(lang, "btn_settings"), "out:menu", icon="📐", style="primary")
    _add(kb, kt(lang, "btn_background"), "bg:menu", icon="🎨", style="primary")
    _add(kb, kt(lang, "btn_watermark"), "wm:menu", icon="💧", style="primary")
    kb.adjust(1, 3)
    return kb.as_markup()
