"""Extract simple color palettes from user source files."""
from __future__ import annotations

import shutil
from pathlib import Path
from PIL import Image

from config import TMP_DIR
from services import sticker_processor, tgs_processor


def _rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    return "#{:02X}{:02X}{:02X}".format(*rgb)


def _dominant_colors(img: Image.Image, limit: int = 3) -> list[str]:
    rgba = img.convert("RGBA")
    rgba.thumbnail((160, 160), Image.LANCZOS)
    pixels = []
    for r, g, b, a in rgba.getdata():
        if a < 32:
            continue
        if r > 245 and g > 245 and b > 245:
            continue
        bucket = (round(r / 32) * 32, round(g / 32) * 32, round(b / 32) * 32)
        pixels.append(tuple(max(0, min(255, c)) for c in bucket))
    if not pixels:
        return []
    counts: dict[tuple[int, int, int], int] = {}
    for color in pixels:
        counts[color] = counts.get(color, 0) + 1
    result: list[tuple[int, int, int]] = []
    for color, _count in sorted(counts.items(), key=lambda item: item[1], reverse=True):
        if all(sum(abs(color[i] - old[i]) for i in range(3)) > 80 for old in result):
            result.append(color)
        if len(result) >= limit:
            break
    return [_rgb_to_hex(color) for color in result]


def extract_palette(input_type: str | None, src_file: Path | None, emoji: str | None = None) -> list[str]:
    work = TMP_DIR / "palette_extract"
    shutil.rmtree(work, ignore_errors=True)
    try:
        if input_type == "sticker" and src_file and src_file.exists():
            frames = sticker_processor.render_webp_to_frames(src_file, work, max_frames=1)
            with Image.open(frames[0]) as img:
                return _dominant_colors(img)
        if input_type == "sticker_video" and src_file and src_file.exists():
            frames = sticker_processor.render_webm_to_frames(src_file, work, max_frames=1)
            with Image.open(frames[0]) as img:
                return _dominant_colors(img)
        if input_type == "tgs" and src_file and src_file.exists():
            frames, _fps = tgs_processor.render_tgs_to_frames(src_file, work, max_frames=1, target_fps=1)
            with Image.open(frames[0]) as img:
                return _dominant_colors(img)
        if input_type == "emoji":
            from services import emoji_renderer

            frames = emoji_renderer.render_emoji(emoji or "✨", work)
            with Image.open(frames[0]) as img:
                return _dominant_colors(img)
    except Exception:
        return []
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return []
