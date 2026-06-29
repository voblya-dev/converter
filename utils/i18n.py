"""
Минималистичная система переводов (RU/EN) на основе JSON-файлов.
"""
import json
from pathlib import Path
from config import BASE_DIR
from utils.premium_emoji import premiumize_text

_LOCALES_DIR = BASE_DIR / "locales"
_CACHE: dict[str, dict] = {}


def _load(lang: str) -> dict:
    if lang not in _CACHE:
        path = _LOCALES_DIR / f"{lang}.json"
        if not path.exists():
            path = _LOCALES_DIR / "ru.json"
        _CACHE[lang] = json.loads(path.read_text(encoding="utf-8"))
    return _CACHE[lang]


def t(lang: str, key: str, plain: bool = False, **kwargs) -> str:
    """
    Получить переведённую строку. Если ключа нет — вернуть сам ключ
    (удобно для отладки). Поддерживает .format(**kwargs).
    """
    data = _load(lang)
    template = data.get(key, key)
    if kwargs:
        try:
            rendered = template.format(**kwargs)
        except (KeyError, IndexError):
            rendered = template
    else:
        rendered = template

    if plain:
        return rendered
    return premiumize_text(rendered)
