"""SQLite-backed user settings storage with JSON migration compatibility."""
import json
import copy
import threading
import sqlite3
from config import DB_PATH, USERS_DIR, DEFAULT_SETTINGS

_lock = threading.RLock()
_cache: dict[int, dict] = {}
_initialized = False


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def init() -> None:
    global _initialized
    with _lock:
        if _initialized:
            return
        with _connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    settings_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS awaits (
                    user_id INTEGER PRIMARY KEY,
                    await_key TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        _initialized = True
        _migrate_json_files()


def _load_from_db(uid: int) -> dict | None:
    init()
    with _connect() as conn:
        row = conn.execute("SELECT settings_json FROM users WHERE user_id = ?", (uid,)).fetchone()
    if not row:
        return None
    return json.loads(row[0])


def _save_to_db(uid: int, settings: dict) -> None:
    if not _initialized:
        init()
    payload = json.dumps(settings, ensure_ascii=False, separators=(",", ":"))
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO users(user_id, settings_json, updated_at)
            VALUES(?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id) DO UPDATE SET
                settings_json = excluded.settings_json,
                updated_at = CURRENT_TIMESTAMP
            """,
            (uid, payload),
        )


def _migrate_json_files() -> None:
    for path in USERS_DIR.glob("*.json"):
        try:
            uid = int(path.stem)
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        with _connect() as conn:
            exists = conn.execute("SELECT 1 FROM users WHERE user_id = ?", (uid,)).fetchone()
        if exists:
            continue
        merged = copy.deepcopy(DEFAULT_SETTINGS)
        _deep_merge(merged, data)
        _migrate(merged)
        _save_to_db(uid, merged)


def get(uid: int) -> dict:
    """Получить настройки пользователя."""
    with _lock:
        if uid in _cache:
            return _cache[uid]
        data = _load_from_db(uid)
        merged = copy.deepcopy(DEFAULT_SETTINGS)
        if data:
            _deep_merge(merged, data)
        _migrate(merged)
        _cache[uid] = merged
        return _cache[uid]


def save(uid: int) -> None:
    """Сохранить состояние пользователя на диск."""
    with _lock:
        if uid not in _cache:
            return
        _save_to_db(uid, _cache[uid])


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
    with _lock:
        if key is None:
            _awaiting.pop(uid, None)
            init()
            with _connect() as conn:
                conn.execute("DELETE FROM awaits WHERE user_id = ?", (uid,))
        else:
            _awaiting[uid] = key
            init()
            with _connect() as conn:
                conn.execute(
                    """
                    INSERT INTO awaits(user_id, await_key, updated_at)
                    VALUES(?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(user_id) DO UPDATE SET
                        await_key = excluded.await_key,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    (uid, key),
                )


def get_await(uid: int) -> str | None:
    with _lock:
        if uid in _awaiting:
            return _awaiting[uid]
        init()
        with _connect() as conn:
            row = conn.execute("SELECT await_key FROM awaits WHERE user_id = ?", (uid,)).fetchone()
        if row:
            _awaiting[uid] = row[0]
            return row[0]
        return None


# ───────── Помощники ─────────
def _deep_merge(dst: dict, src: dict) -> None:
    for k, v in src.items():
        if isinstance(v, dict) and isinstance(dst.get(k), dict):
            _deep_merge(dst[k], v)
        else:
            dst[k] = v


def _migrate(settings: dict) -> None:
    colorize = settings.get("input", {}).get("colorize", {})
    colorize.setdefault("auto", DEFAULT_SETTINGS["input"]["colorize"].get("auto", False))
    if colorize.get("enabled") is False and colorize.get("strength") == 85:
        colorize["strength"] = DEFAULT_SETTINGS["input"]["colorize"]["strength"]
    settings.get("background", {}).setdefault(
        "auto_palette",
        DEFAULT_SETTINGS["background"].get("auto_palette", False),
    )
    output = settings.get("output", {})
    if output.get("quality") == "high":
        output["quality"] = DEFAULT_SETTINGS["output"]["quality"]


def lang(uid: int) -> str:
    return get(uid).get("lang", "ru")
