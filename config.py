"""
Конфигурация проекта. Все константы, пути, дефолтные значения настроек.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ───────── Пути ─────────
BASE_DIR = Path(__file__).resolve().parent
ASSETS_DIR = BASE_DIR / "assets"
FONTS_DIR = ASSETS_DIR / "fonts"
PRESETS_DIR = ASSETS_DIR / "presets"
BACKGROUNDS_DIR = ASSETS_DIR / "backgrounds"
DATA_DIR = BASE_DIR / "data"
USERS_DIR = DATA_DIR / "users"
TMP_DIR = DATA_DIR / "tmp"

for _d in (USERS_DIR, TMP_DIR, FONTS_DIR, PRESETS_DIR, BACKGROUNDS_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# ───────── Бот ─────────
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0") or 0)
FFMPEG_PATH = os.getenv("FFMPEG_PATH", "ffmpeg")
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "20"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# ───────── Палитра (20 цветов) ─────────
COLOR_PALETTE = [
    ("Белый",     "#FFFFFF"), ("Чёрный",    "#000000"),
    ("Красный",   "#E53935"), ("Розовый",   "#EC407A"),
    ("Фиолет.",   "#8E24AA"), ("Индиго",    "#3949AB"),
    ("Синий",     "#1E88E5"), ("Голубой",   "#039BE5"),
    ("Бирюза",    "#00ACC1"), ("Зелёный",   "#43A047"),
    ("Лайм",      "#C0CA33"), ("Жёлтый",    "#FDD835"),
    ("Оранжев.",  "#FB8C00"), ("Коричнев.", "#6D4C41"),
    ("Серый",     "#757575"), ("Графит",    "#37474F"),
    ("Мята",      "#80CBC4"), ("Лаванда",   "#B39DDB"),
    ("Персик",    "#FFAB91"), ("Золото",    "#FFD700"),
]

# ───────── Разрешения ─────────
RESOLUTION_PRESETS = [
    ("512×512",   512, 512),
    ("1080×1080", 1080, 1080),
    ("1920×1080", 1920, 1080),
    ("1080×1920", 1080, 1920),
    ("1920×530",  1920, 530),
]

FPS_OPTIONS = [10, 24, 30, 60]            # + "как в исходнике"
QUALITY_LEVELS = ["low", "medium", "high", "lossless"]
OUTPUT_FORMATS = ["gif", "mp4", "webm", "png"]

# ───────── Водяной знак ─────────
WM_POSITION_GRID = [
    ["tl", "tc", "tr"],
    ["ml", "mc", "mr"],
    ["bl", "bc", "br"],
]
WM_ROTATIONS = [0, 45, 90, 135, 180, 225, 270, 315]
WM_OFFSET_STEP = 10   # пикселей за один шаг стрелкой
WM_ALPHA_STEP  = 5    # %
WM_SIZE_STEP   = 5    # %

# ───────── Встроенные шрифты ─────────
# Файлы должны лежать в assets/fonts/.  При отсутствии шрифта рендер
# использует системный DejaVuSans.
BUILTIN_FONTS = [
    ("Classic",       "DejaVuSans.ttf"),
    ("Classic Bold",  "DejaVuSans-Bold.ttf"),
    ("Mono",          "DejaVuSansMono.ttf"),
    ("Serif",         "DejaVuSerif.ttf"),
    ("Decorative",    "KMKDSKBW.ttf"),
]

# ───────── Дефолтные настройки ─────────
DEFAULT_SETTINGS = {
    "lang":        "ru",
    "background": {
        "mode":   "color",        # color | gradient | image | video | global_image
        "color":  "#000000",
        "color2": "#8E24AA",      # для градиента
        "direction": "vertical",  # vertical | horizontal | diagonal
        "file_id": None,          # для image/video
        "global_file": None,
    },
    "output": {
        "format":  "mp4",
        "width":   1920,
        "height":  530,
        "fps":     "source",      # int или "source"
        "quality": "lossless",
        "duration": None,         # None = как в исходнике
        "speed":   1.0,
    },
    "watermark": {
        "enabled":  False,
        "source":   "text",       # text | image | preset
        "text":     "@my_channel",
        "file_id":  None,
        "preset":   None,
        # Позиционирование
        "anchor":   "br",         # tl tc tr ml mc mr bl bc br
        "offset_x": 0,
        "offset_y": 0,
        # Внешний вид
        "alpha":    80,           # %
        "size_pct": 15,           # % от ширины холста
        "rotation": 0,
        # Эффекты
        "shadow":   False,
        "stroke":   False,
        "glow":     False,
        "effect_color": "#000000",
        "effect_radius": 4,
        # Текст
        "font":         "Classic",
        "font_size_pct": 8,       # % от высоты холста
        "font_color":   "#FFFFFF",
        "kerning":      0,
    },
    "input": {
        "type":     None,         # tgs | sticker | sticker_video | emoji
        "file_id":  None,
        "emoji":    None,
        "size_pct": 80,           # % от холста для исходного стикера/эмодзи
        "colorize": {
            "enabled": False,
            "color": "#FFFFFF",
            "strength": 100,
        },
    },
}
