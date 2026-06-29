"""Filesystem helpers for user-scoped uploaded files."""
from __future__ import annotations

from pathlib import Path

from config import BACKGROUNDS_DIR, TMP_DIR


def user_dir(uid: int) -> Path:
    return TMP_DIR / f"u{uid}"


def find_input(uid: int, settings: dict) -> Path | None:
    udir = user_dir(uid)
    input_type = settings["input"].get("type")
    if input_type == "tgs":
        path = udir / "input.tgs"
    elif input_type == "sticker":
        path = udir / "input.webp"
    elif input_type == "sticker_video":
        path = udir / "input.webm"
    else:
        return None
    return path if path.exists() else None


def find_background(uid: int, settings: dict) -> Path | None:
    udir = user_dir(uid)
    mode = settings["background"]["mode"]
    if mode == "image":
        path = udir / "bg.jpg"
        return path if path.exists() else None
    if mode == "video":
        path = udir / "bg.mp4"
        return path if path.exists() else None
    if mode == "global_image":
        name = settings["background"].get("global_file")
        if name:
            path = BACKGROUNDS_DIR / name
            return path if path.exists() else None
    return None


def find_watermark_image(uid: int, settings: dict) -> Path | None:
    if settings["watermark"]["source"] == "image":
        path = user_dir(uid) / "wm.png"
        return path if path.exists() else None
    return None
