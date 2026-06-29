from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Callable

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


CancelCb = Callable[[], bool]


class FfmpegCancelled(RuntimeError):
    """Raised when an active ffmpeg process is cancelled."""


def run_ffmpeg(args: list[str], cancelled: CancelCb | None = None) -> subprocess.CompletedProcess[bytes]:
    cmd = [resolve_ffmpeg(), *args]
    if cancelled is None:
        result = subprocess.run(cmd, check=False, capture_output=True)
    else:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        while proc.poll() is None:
            if cancelled():
                proc.terminate()
                try:
                    stdout, stderr = proc.communicate(timeout=2)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    stdout, stderr = proc.communicate()
                raise FfmpegCancelled("ffmpeg cancelled")
            try:
                stdout, stderr = proc.communicate(timeout=0.2)
            except subprocess.TimeoutExpired:
                continue
        if proc.stdout is not None or proc.stderr is not None:
            stdout, stderr = proc.communicate()
        else:
            stdout, stderr = b"", b""
        result = subprocess.CompletedProcess(cmd, proc.returncode, stdout, stderr)
    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="replace").strip()
        stdout = result.stdout.decode("utf-8", errors="replace").strip()
        detail = stderr or stdout or f"exit code {result.returncode}"
        raise RuntimeError(f"ffmpeg failed: {detail[-800:]}")
    return result
