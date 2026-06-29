"""Cleanup helpers for generated temporary render files."""
from __future__ import annotations

import shutil
import time
from pathlib import Path

from config import TMP_DIR, TMP_MAX_AGE_HOURS


def cleanup_tmp(max_age_hours: int = TMP_MAX_AGE_HOURS) -> int:
    """Remove stale generated files from data/tmp and return removed item count."""
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    cutoff = time.time() - max(1, max_age_hours) * 3600
    removed = 0

    for path in TMP_DIR.iterdir():
        name = path.name
        if name.startswith("u"):
            continue
        if not (
            name.startswith("job_")
            or name.startswith("test_")
            or name.startswith("check_")
            or name.startswith("pycache_")
        ):
            continue
        try:
            mtime = path.stat().st_mtime
        except OSError:
            continue
        if mtime > cutoff:
            continue
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
            removed += 1
        else:
            try:
                path.unlink()
                removed += 1
            except OSError:
                pass

    return removed
