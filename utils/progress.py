"""
Утилита для построения текстового прогресс-бара.
"""
def bar(pct: int, width: int = 10) -> str:
    """
    Сформировать прогресс-бар вида '▓▓▓▓░░░░░░' длиной `width`.
    pct: 0..100
    """
    pct = max(0, min(100, int(pct)))
    filled = int(round(width * pct / 100))
    return "▓" * filled + "░" * (width - filled)
