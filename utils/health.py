"""Runtime diagnostics for admin health checks."""
from __future__ import annotations

import importlib
import sqlite3
from pathlib import Path

from config import DB_PATH, TMP_DIR
from services.ffmpeg_runner import resolve_ffmpeg


def _dir_size(path: Path) -> int:
    total = 0
    if not path.exists():
        return 0
    for item in path.rglob("*"):
        if item.is_file():
            try:
                total += item.stat().st_size
            except OSError:
                pass
    return total


def _fmt_bytes(value: int) -> str:
    size = float(value)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def health_report() -> dict[str, str]:
    report: dict[str, str] = {}
    try:
        report["ffmpeg"] = resolve_ffmpeg()
    except Exception as exc:
        report["ffmpeg"] = f"ERROR: {exc}"

    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("SELECT 1").fetchone()
        report["sqlite"] = str(DB_PATH)
    except Exception as exc:
        report["sqlite"] = f"ERROR: {exc}"

    report["tmp_size"] = _fmt_bytes(_dir_size(TMP_DIR))
    for module in ("aiogram", "PIL", "numpy", "emoji", "pyrlottie"):
        try:
            mod = importlib.import_module(module)
            report[module] = getattr(mod, "__version__", "installed")
        except Exception as exc:
            report[module] = f"ERROR: {exc}"
    return report
