from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from config import BASE_DIR, FFMPEG_PATH


def resolve_ffmpeg() -> str:
    """Return a usable ffmpeg executable path or raise a clear setup error."""
    configured = FFMPEG_PATH.strip().strip('"')
    candidates = [configured]

    if configured.lower() in {"ffmpeg", "ffmpeg.exe"}:
        candidates.extend(
            [
                str(BASE_DIR / "ffmpeg.exe"),
                str(BASE_DIR / "bin" / "ffmpeg.exe"),
                str(BASE_DIR / "tools" / "ffmpeg.exe"),
                str(BASE_DIR / "tools" / "ffmpeg" / "bin" / "ffmpeg.exe"),
            ]
        )

    for candidate in candidates:
        found = shutil.which(candidate)
        if found:
            return found

        path = Path(candidate)
        if path.is_file():
            return str(path)

    raise RuntimeError(
        "ffmpeg not found. Install ffmpeg and add it to PATH, or set FFMPEG_PATH "
        "in .env to the full path, for example: "
        r'FFMPEG_PATH=C:\ffmpeg\bin\ffmpeg.exe'
    )


def run_ffmpeg(args: list[str]) -> subprocess.CompletedProcess[bytes]:
    cmd = [resolve_ffmpeg(), *args]
    result = subprocess.run(cmd, check=False, capture_output=True)
    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="replace").strip()
        stdout = result.stdout.decode("utf-8", errors="replace").strip()
        detail = stderr or stdout or f"exit code {result.returncode}"
        raise RuntimeError(f"ffmpeg failed: {detail[-800:]}")
    return result
