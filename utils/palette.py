"""Extract simple color palettes from user source files."""
from __future__ import annotations

import gzip
import json
import shutil
from collections import Counter
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
        if a < 48:
            continue
        if r > 245 and g > 245 and b > 245:
            continue
        if r < 12 and g < 12 and b < 12:
            continue
        bucket = (round(r / 32) * 32, round(g / 32) * 32, round(b / 32) * 32)
        pixels.append(tuple(max(0, min(255, c)) for c in bucket))
    if not pixels:
        return []
    counts: dict[tuple[int, int, int], int] = {}
    for color in pixels:
        counts[color] = counts.get(color, 0) + 1

    def score(item: tuple[tuple[int, int, int], int]) -> float:
        (r, g, b), count = item
        saturation = max(r, g, b) - min(r, g, b)
        brightness = (r + g + b) / 3
        return count * (1.0 + saturation / 96.0) * (0.75 + min(brightness, 220) / 440.0)

    result: list[tuple[int, int, int]] = []
    for color, _count in sorted(counts.items(), key=score, reverse=True):
        if all(sum(abs(color[i] - old[i]) for i in range(3)) > 80 for old in result):
            result.append(color)
        if len(result) >= limit:
            break
    return [_rgb_to_hex(color) for color in result]


def _dominant_colors_from_paths(paths: list[Path], limit: int = 3) -> list[str]:
    colors: list[str] = []
    for path in paths[:5]:
        with Image.open(path) as img:
            for color in _dominant_colors(img, limit=limit):
                if color not in colors:
                    colors.append(color)
                if len(colors) >= limit:
                    return colors
    return colors


def _normalize_lottie_rgb(values: list) -> tuple[int, int, int] | None:
    if len(values) < 3:
        return None
    rgb = list(values[:3])
    try:
        numeric = [float(c) for c in rgb]
    except (TypeError, ValueError):
        return None
    if all(0 <= c <= 1 for c in numeric):
        numeric = [c * 255 for c in numeric]
    result = tuple(max(0, min(255, int(round(c)))) for c in numeric)
    r, g, b = result
    if r > 245 and g > 245 and b > 245:
        return None
    if r < 12 and g < 12 and b < 12:
        return None
    return result


def _looks_like_rgb(values: list) -> bool:
    if len(values) < 3:
        return False
    try:
        rgb = [float(c) for c in values[:3]]
    except (TypeError, ValueError):
        return False
    return all(0 <= c <= 1 for c in rgb) or all(0 <= c <= 255 for c in rgb)


def _color_candidates(value) -> list[tuple[int, int, int]]:
    colors: list[tuple[int, int, int]] = []
    if isinstance(value, list):
        if _looks_like_rgb(value):
            rgb = _normalize_lottie_rgb(value)
            if rgb:
                colors.append(rgb)
        for item in value:
            colors.extend(_color_candidates(item))
    elif isinstance(value, dict):
        for key in ("k", "s", "e"):
            if key in value:
                colors.extend(_color_candidates(value[key]))
    return colors


def _normalize_lottie_gradient_stops(values: list) -> list[tuple[int, int, int]]:
    colors: list[tuple[int, int, int]] = []
    if not values:
        return colors
    if all(isinstance(v, (int, float)) for v in values):
        # Lottie gradient format: offset, r, g, b, offset, r, g, b...
        for i in range(0, len(values) - 3, 4):
            rgb = _normalize_lottie_rgb(values[i + 1:i + 4])
            if rgb:
                colors.append(rgb)
        return colors
    for item in values:
        colors.extend(_color_candidates(item))
    return colors


def _lottie_color_values(node) -> list[tuple[int, int, int]]:
    colors: list[tuple[int, int, int]] = []
    if isinstance(node, dict):
        if node.get("ty") in {"fl", "st"}:
            colors.extend(_color_candidates((node.get("c") or {}).get("k") or []))
        if node.get("ty") == "gf":
            stops = (((node.get("g") or {}).get("k") or {}).get("k") or [])
            if isinstance(stops, list):
                colors.extend(_normalize_lottie_gradient_stops(stops))
        for value in node.values():
            colors.extend(_lottie_color_values(value))
    elif isinstance(node, list):
        for value in node:
            colors.extend(_lottie_color_values(value))
    return colors


def _dominant_colors_from_lottie(path: Path, limit: int = 3) -> list[str]:
    raw = path.read_bytes()
    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    data = json.loads(raw)
    counts = Counter(_lottie_color_values(data))
    if not counts:
        return []

    def score(item: tuple[tuple[int, int, int], int]) -> float:
        (r, g, b), count = item
        saturation = max(r, g, b) - min(r, g, b)
        brightness = (r + g + b) / 3
        return count * (1.0 + saturation / 96.0) * (0.75 + min(brightness, 220) / 440.0)

    result: list[tuple[int, int, int]] = []
    for color, _count in sorted(counts.items(), key=score, reverse=True):
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
            frames = sticker_processor.render_webp_to_frames(src_file, work, max_frames=5)
            return _dominant_colors_from_paths(frames)
        if input_type == "sticker_video" and src_file and src_file.exists():
            frames = sticker_processor.render_webm_to_frames(src_file, work, max_frames=5)
            return _dominant_colors_from_paths(frames)
        if input_type == "tgs" and src_file and src_file.exists():
            colors = _dominant_colors_from_lottie(src_file)
            if colors:
                return colors
            frames, _fps = tgs_processor.render_tgs_to_frames(src_file, work, max_frames=5, target_fps=5)
            return _dominant_colors_from_paths(frames)
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
