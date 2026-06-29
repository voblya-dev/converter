"""
Помощники для работы с цветом: HEX <-> RGB(A), валидация, генерация градиентов.
"""
import re
from PIL import Image, ImageColor

_HEX_RE = re.compile(r"^#?([0-9a-fA-F]{6})$")

_RU_COLOR_ALIASES = {
    "белый": "#FFFFFF",
    "белая": "#FFFFFF",
    "white": "#FFFFFF",
    "черный": "#000000",
    "чёрный": "#000000",
    "черная": "#000000",
    "чёрная": "#000000",
    "black": "#000000",
    "красный": "#FF0000",
    "красная": "#FF0000",
    "red": "#FF0000",
    "зеленый": "#008000",
    "зелёный": "#008000",
    "зеленая": "#008000",
    "зелёная": "#008000",
    "green": "#008000",
    "синий": "#0000FF",
    "синяя": "#0000FF",
    "blue": "#0000FF",
    "голубой": "#00BFFF",
    "голубая": "#00BFFF",
    "skyblue": "#87CEEB",
    "желтый": "#FFFF00",
    "жёлтый": "#FFFF00",
    "желтая": "#FFFF00",
    "жёлтая": "#FFFF00",
    "yellow": "#FFFF00",
    "оранжевый": "#FFA500",
    "оранжевая": "#FFA500",
    "orange": "#FFA500",
    "розовый": "#FFC0CB",
    "розовая": "#FFC0CB",
    "pink": "#FFC0CB",
    "фиолетовый": "#800080",
    "фиолетовая": "#800080",
    "purple": "#800080",
    "серый": "#808080",
    "серая": "#808080",
    "gray": "#808080",
    "grey": "#808080",
    "коричневый": "#A52A2A",
    "коричневая": "#A52A2A",
    "brown": "#A52A2A",
    "бирюзовый": "#40E0D0",
    "бирюзовая": "#40E0D0",
    "turquoise": "#40E0D0",
    "золотой": "#FFD700",
    "золотая": "#FFD700",
    "gold": "#FFD700",
    "серебряный": "#C0C0C0",
    "серебряная": "#C0C0C0",
    "silver": "#C0C0C0",
}


def parse_hex(text: str) -> str | None:
    """Принять HEX или имя цвета и вернуть канонический `#RRGGBB` либо None."""
    text = text.strip()
    m = _HEX_RE.match(text)
    if m:
        return "#" + m.group(1).upper()

    normalized = text.casefold().replace(" ", "")
    alias = _RU_COLOR_ALIASES.get(normalized)
    if alias:
        return alias

    try:
        r, g, b = ImageColor.getrgb(normalized)[:3]
    except ValueError:
        return None
    return f"#{r:02X}{g:02X}{b:02X}"


def hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore


def rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    return "#{:02X}{:02X}{:02X}".format(*rgb)


def hex_to_rgba(h: str, alpha: int = 255) -> tuple[int, int, int, int]:
    r, g, b = hex_to_rgb(h)
    return (r, g, b, alpha)


def make_gradient(
    size: tuple[int, int],
    color1: str,
    color2: str,
    direction: str = "vertical",
) -> Image.Image:
    """
    Сгенерировать градиентное изображение требуемого размера.

    direction: 'horizontal' | 'vertical' | 'diagonal'
    """
    w, h = size
    c1 = hex_to_rgb(color1)
    c2 = hex_to_rgb(color2)
    img = Image.new("RGB", (w, h), c1)
    px = img.load()

    if direction == "horizontal":
        denom = max(w - 1, 1)
        for x in range(w):
            t = x / denom
            r = int(c1[0] + (c2[0] - c1[0]) * t)
            g = int(c1[1] + (c2[1] - c1[1]) * t)
            b = int(c1[2] + (c2[2] - c1[2]) * t)
            for y in range(h):
                px[x, y] = (r, g, b)
    elif direction == "diagonal":
        denom = max(w + h - 2, 1)
        for y in range(h):
            for x in range(w):
                t = (x + y) / denom
                r = int(c1[0] + (c2[0] - c1[0]) * t)
                g = int(c1[1] + (c2[1] - c1[1]) * t)
                b = int(c1[2] + (c2[2] - c1[2]) * t)
                px[x, y] = (r, g, b)
    else:  # vertical
        denom = max(h - 1, 1)
        for y in range(h):
            t = y / denom
            r = int(c1[0] + (c2[0] - c1[0]) * t)
            g = int(c1[1] + (c2[1] - c1[1]) * t)
            b = int(c1[2] + (c2[2] - c1[2]) * t)
            for x in range(w):
                px[x, y] = (r, g, b)
    return img
