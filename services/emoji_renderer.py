"""Render a regular Unicode emoji into one transparent PNG frame."""
from __future__ import annotations
from io import BytesIO
from pathlib import Path
import urllib.request

from PIL import Image, ImageDraw, ImageFont

from config import FONTS_DIR


_TWEMOJI_BASE = "https://cdnjs.cloudflare.com/ajax/libs/twemoji/14.0.2/72x72"
_VARIATION_SELECTOR_16 = 0xFE0F
_SKIN_TONE_RANGE = range(0x1F3FB, 0x1F400)


def _twemoji_code(emoji: str) -> str:
    codepoints = [ord(ch) for ch in emoji if ord(ch) != _VARIATION_SELECTOR_16]
    return "-".join(f"{cp:x}" for cp in codepoints)


def _load_twemoji(emoji: str) -> Image.Image | None:
    code = _twemoji_code(emoji)
    if not code:
        return None
    url = f"{_TWEMOJI_BASE}/{code}.png"
    try:
        with urllib.request.urlopen(url, timeout=6) as response:
            return Image.open(BytesIO(response.read())).convert("RGBA")
    except Exception:
        return None


def _font_candidates() -> list[Path | str]:
    return [
        FONTS_DIR / "NotoColorEmoji.ttf",
        FONTS_DIR / "seguiemj.ttf",
        r"C:\Windows\Fonts\seguiemj.ttf",
        FONTS_DIR / "DejaVuSans.ttf",
        "DejaVuSans.ttf",
    ]


def _load_font(font_size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for candidate in _font_candidates():
        try:
            return ImageFont.truetype(str(candidate), font_size)
        except Exception:
            continue
    return ImageFont.load_default()


def _draw_text_fallback(emoji: str, size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    font = _load_font(int(size * 0.72))
    d = ImageDraw.Draw(img)
    try:
        bbox = d.textbbox((0, 0), emoji, font=font, embedded_color=True)
    except Exception:
        bbox = d.textbbox((0, 0), emoji, font=font)
    x = (size - (bbox[2] - bbox[0])) // 2 - bbox[0]
    y = (size - (bbox[3] - bbox[1])) // 2 - bbox[1]
    try:
        d.text((x, y), emoji, font=font, fill=(255, 255, 255, 255), embedded_color=True)
    except Exception:
        d.text((x, y), emoji, font=font, fill=(255, 255, 255, 255))
    return img


def _has_visible_pixels(img: Image.Image) -> bool:
    return img.convert("RGBA").getchannel("A").getbbox() is not None


def render_emoji(emoji: str, out_dir: Path, size: int = 512) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    src = _load_twemoji(emoji) or _draw_text_fallback(emoji, size)

    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    margin = int(size * 0.1)
    max_side = size - margin * 2
    scale = min(max_side / max(1, src.width), max_side / max(1, src.height))
    src = src.resize((max(1, int(src.width * scale)), max(1, int(src.height * scale))), Image.LANCZOS)
    x = (size - src.width) // 2
    y = (size - src.height) // 2
    img.alpha_composite(src, (x, y))

    if not _has_visible_pixels(img):
        raise RuntimeError(f"Emoji renderer produced an empty image for {emoji!r}")

    out = out_dir / "frame_0000.png"
    img.save(out)
    return [out]
