"""
Композитинг водяного знака поверх кадра.

Учитываются:
* источник (текст / изображение / пресет),
* позиция (anchor + offset_x/y),
* размер (% от ширины холста),
* прозрачность (alpha %),
* поворот (deg),
* эффекты (тень / обводка / свечение),
* для текста — шрифт, цвет, кернинг, размер.
"""
from __future__ import annotations
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from config import FONTS_DIR, BUILTIN_FONTS, PRESETS_DIR
from utils.colors import hex_to_rgb


def _find_font_path(font_name: str) -> Path | None:
    for name, file in BUILTIN_FONTS:
        if name == font_name:
            p = FONTS_DIR / file
            if p.exists():
                return p
    # Пробуем имя файла как есть
    candidate = FONTS_DIR / font_name
    if candidate.exists():
        return candidate
    return None


def _load_font(font_name: str, size: int) -> ImageFont.FreeTypeFont:
    p = _find_font_path(font_name)
    try:
        if p:
            return ImageFont.truetype(str(p), size)
        # Системный фолбэк
        return ImageFont.truetype("DejaVuSans.ttf", size)
    except Exception:
        return ImageFont.load_default()


def _render_text_layer(
    text: str,
    canvas_size: tuple[int, int],
    wm: dict,
) -> Image.Image:
    """Отрисовать текстовый водяной знак на отдельном прозрачном слое."""
    cw, ch = canvas_size
    font_size = max(8, int(ch * wm["font_size_pct"] / 100))
    font = _load_font(wm["font"], font_size)

    # Расчёт ширины с кернингом
    kerning = int(wm.get("kerning", 0))
    if kerning == 0:
        bbox = font.getbbox(text)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
    else:
        tw = 0
        th = 0
        for ch_ in text:
            bb = font.getbbox(ch_)
            tw += (bb[2] - bb[0]) + kerning
            th = max(th, bb[3] - bb[1])
        tw = max(1, tw - kerning)

    pad = wm["effect_radius"] * 3 + 4
    layer = Image.new("RGBA", (tw + pad * 2, th + pad * 2), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    color = (*hex_to_rgb(wm["font_color"]), 255)
    eff_color = (*hex_to_rgb(wm["effect_color"]), 255)
    r = wm["effect_radius"]

    def _draw_text(xy, fill):
        if kerning == 0:
            draw.text(xy, text, font=font, fill=fill)
        else:
            x, y = xy
            for c in text:
                draw.text((x, y), c, font=font, fill=fill)
                bb = font.getbbox(c)
                x += (bb[2] - bb[0]) + kerning

    base_xy = (pad, pad)

    # Эффекты — порядок: glow -> shadow -> stroke -> text
    if wm.get("glow"):
        glow_layer = Image.new("RGBA", layer.size, (0, 0, 0, 0))
        gd = ImageDraw.Draw(glow_layer)
        if kerning == 0:
            gd.text(base_xy, text, font=font, fill=eff_color)
        else:
            x, y = base_xy
            for c in text:
                gd.text((x, y), c, font=font, fill=eff_color)
                bb = font.getbbox(c)
                x += (bb[2] - bb[0]) + kerning
        glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(radius=r * 2))
        layer = Image.alpha_composite(layer, glow_layer)
        draw = ImageDraw.Draw(layer)

    if wm.get("shadow"):
        shadow_layer = Image.new("RGBA", layer.size, (0, 0, 0, 0))
        sd = ImageDraw.Draw(shadow_layer)
        shadow_xy = (base_xy[0] + r, base_xy[1] + r)
        if kerning == 0:
            sd.text(shadow_xy, text, font=font, fill=eff_color)
        else:
            x, y = shadow_xy
            for c in text:
                sd.text((x, y), c, font=font, fill=eff_color)
                bb = font.getbbox(c)
                x += (bb[2] - bb[0]) + kerning
        shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(radius=max(1, r // 2)))
        layer = Image.alpha_composite(layer, shadow_layer)
        draw = ImageDraw.Draw(layer)

    if wm.get("stroke"):
        # Восьминаправленная обводка
        for dx in range(-r, r + 1):
            for dy in range(-r, r + 1):
                if dx * dx + dy * dy <= r * r and (dx or dy):
                    _draw_text((base_xy[0] + dx, base_xy[1] + dy), eff_color)

    _draw_text(base_xy, color)
    return layer


def _render_image_layer(src: Path, canvas_size: tuple[int, int], wm: dict) -> Image.Image:
    cw, ch = canvas_size
    target_w = max(8, int(cw * wm["size_pct"] / 100))
    img = Image.open(src).convert("RGBA")
    iw, ih = img.size
    scale = target_w / max(1, iw)
    nw = int(iw * scale)
    nh = int(ih * scale)
    return img.resize((nw, nh), Image.LANCZOS)


def build_watermark_layer(
    wm: dict,
    canvas_size: tuple[int, int],
    image_path: Path | None = None,
) -> Image.Image | None:
    """Собрать готовый слой водяного знака (RGBA) или вернуть None, если выключен."""
    if not wm.get("enabled"):
        return None

    src = wm.get("source", "text")
    if src == "text":
        if not wm.get("text"):
            return None
        layer = _render_text_layer(wm["text"], canvas_size, wm)
    elif src == "image" and image_path and image_path.exists():
        layer = _render_image_layer(image_path, canvas_size, wm)
    elif src == "preset" and wm.get("preset"):
        preset_path = PRESETS_DIR / wm["preset"]
        if not preset_path.exists():
            return None
        layer = _render_image_layer(preset_path, canvas_size, wm)
    else:
        return None

    # Поворот
    rot = int(wm.get("rotation", 0)) % 360
    if rot:
        layer = layer.rotate(-rot, resample=Image.BICUBIC, expand=True)

    # Прозрачность
    alpha = max(0, min(100, int(wm.get("alpha", 100)))) / 100.0
    if alpha < 0.999:
        a = layer.split()[-1].point(lambda v: int(v * alpha))
        layer.putalpha(a)
    return layer


def _anchor_xy(anchor: str, canvas: tuple[int, int], wm_size: tuple[int, int]) -> tuple[int, int]:
    cw, ch = canvas
    ww, wh = wm_size
    pad = max(16, int(min(cw, ch) * 0.035))
    table = {
        "tl": (pad, pad),
        "tc": ((cw - ww) // 2, pad),
        "tr": (cw - ww - pad, pad),
        "ml": (pad, (ch - wh) // 2),
        "mc": ((cw - ww) // 2, (ch - wh) // 2),
        "mr": (cw - ww - pad, (ch - wh) // 2),
        "bl": (pad, ch - wh - pad),
        "bc": ((cw - ww) // 2, ch - wh - pad),
        "br": (cw - ww - pad, ch - wh - pad),
    }
    return table.get(anchor, table["br"])


def paste_watermark(frame: Image.Image, layer: Image.Image, wm: dict) -> Image.Image:
    """Наложить готовый WM-слой на кадр. `frame` — RGBA."""
    if layer is None:
        return frame
    anchor = wm["anchor"]
    offset_x = int(wm.get("offset_x", 0))
    offset_y = int(wm.get("offset_y", 0))
    x, y = _anchor_xy(wm["anchor"], frame.size, layer.size)
    if anchor.endswith("r"):
        x -= offset_x
    elif anchor.endswith("l"):
        x += offset_x
    else:
        x += offset_x
    if anchor.startswith("b"):
        y -= offset_y
    elif anchor.startswith("t"):
        y += offset_y
    else:
        y += offset_y
    x = max(0, min(frame.width - layer.width, x))
    y = max(0, min(frame.height - layer.height, y))
    frame.alpha_composite(layer, (x, y))
    return frame
