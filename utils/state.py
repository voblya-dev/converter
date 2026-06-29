"""
Простое хранилище состояний пользователей: in-memory + JSON-снапшоты
на диск (data/users/<user_id>.json). Достаточно для одиночного инстанса бота.
"""
import json
import copy
import threading
from pathlib import Path
from config import USERS_DIR, DEFAULT_SETTINGS

_lock = threading.RLock()
_cache: dict[int, dict] = {}


def _path(uid: int) -> Path:
    return USERS_DIR / f"{uid}.json"


def get(uid: int) -> dict:
    """Получить настройки пользователя (с загрузкой с диска при первом обращении)."""
    with _lock:
        if uid in _cache:
            return _cache[uid]
        p = _path(uid)
        if p.exists():
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                # Дозаполняем недостающие ключи из дефолта
                merged = copy.deepcopy(DEFAULT_SETTINGS)
                _deep_merge(merged, data)
                _migrate(merged)
                _cache[uid] = merged
                return merged
            except Exception:
                pass
        _cache[uid] = copy.deepcopy(DEFAULT_SETTINGS)
        return _cache[uid]


def save(uid: int) -> None:
    """Сохранить состояние пользователя на диск."""
    with _lock:
        if uid not in _cache:
            return
        _path(uid).write_text(
            json.dumps(_cache[uid], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def reset(uid: int) -> dict:
    """Полный сброс настроек пользователя к дефолту."""
    with _lock:
        _cache[uid] = copy.deepcopy(DEFAULT_SETTINGS)
        save(uid)
        return _cache[uid]


def update(uid: int, **kv) -> dict:
    """Поверхностное обновление верхнего уровня (например, lang)."""
    s = get(uid)
    s.update(kv)
    save(uid)
    return s


# ───────── FSM «ожидание ввода» ─────────
# Когда пользователь нажимает «ввести HEX» / «свой размер» / «текст водяного
# знака», бот выставляет ему ожидание определённого типа сообщения.
_awaiting: dict[int, str] = {}


def set_await(uid: int, key: str | None) -> None:
    if key is None:
        _awaiting.pop(uid, None)
    else:
        _awaiting[uid] = key


def get_await(uid: int) -> str | None:
    return _awaiting.get(uid)


# ───────── Помощники ─────────
def _deep_merge(dst: dict, src: dict) -> None:
    for k, v in src.items():
        if isinstance(v, dict) and isinstance(dst.get(k), dict):
            _deep_merge(dst[k], v)
        else:
            dst[k] = v


def _migrate(settings: dict) -> None:
    colorize = settings.get("input", {}).get("colorize", {})
    if colorize.get("enabled") is False and colorize.get("strength") == 85:
        colorize["strength"] = DEFAULT_SETTINGS["input"]["colorize"]["strength"]
    output = settings.get("output", {})
    if output.get("quality") == "high":
        output["quality"] = DEFAULT_SETTINGS["output"]["quality"]


def lang(uid: int) -> str:
    return get(uid).get("lang", "ru")
