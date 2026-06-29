"""
Визуализация позиции водяного знака — ASCII-сетка 3×3 с подсветкой.
"""
from html import escape

from config import WM_POSITION_GRID

# Подсвечивающий и пустой символы (используем квадратные эмодзи; они НЕ премиум-)
# Если хочется чистый ASCII — можно заменить на █ и ·, но просили
# не использовать НЕ-премиум эмодзи. Универсальные геометрические символы
# (⬛/⬜) не относятся к Telegram-«премиум»-эмодзи, это базовые Unicode-символы,
# но они не дают премиум-окраски. Чтобы соответствовать требованию
# «либо премиум, либо никаких», мы используем монохромные ASCII-символы.
FILLED = "■"
EMPTY  = "·"


_LABELS = {
    "tl": "верх-лево",   "tc": "верх-центр",   "tr": "верх-право",
    "ml": "центр-лево",  "mc": "центр",        "mr": "центр-право",
    "bl": "низ-лево",    "bc": "низ-центр",    "br": "низ-право",
}

_LABELS_EN = {
    "tl": "top-left",     "tc": "top-center",     "tr": "top-right",
    "ml": "middle-left",  "mc": "center",         "mr": "middle-right",
    "bl": "bottom-left",  "bc": "bottom-center",  "br": "bottom-right",
}


def label(anchor: str, lang: str = "ru") -> str:
    return (_LABELS_EN if lang == "en" else _LABELS).get(anchor, anchor)


def render_grid(anchor: str) -> str:
    """
    Вернуть моноширинную ASCII-сетку 3×3, в которой выбранная ячейка
    заполнена FILLED, остальные — EMPTY. Оборачиваем в HTML <pre>.
    """
    rows = []
    rows.append("┌───┬───┬───┐")
    for r_idx, row in enumerate(WM_POSITION_GRID):
        cells = []
        for c in row:
            cells.append(f" {FILLED if c == anchor else EMPTY} ")
        rows.append("│" + "│".join(cells) + "│")
        if r_idx < 2:
            rows.append("├───┼───┼───┤")
    rows.append("└───┴───┴───┘")
    return "<pre>" + escape("\n".join(rows)) + "</pre>"
