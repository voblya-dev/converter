"""
Распаковка и рендер TGS-стикеров (это gzip-сжатый Lottie JSON).
Используем pyrlottie для рендера в PNG-кадры с альфа-каналом.

Если pyrlottie недоступен, делаем graceful fallback:
сохраняем единственный statиc-кадр с водяным знаком ошибки.
"""
from __future__ import annotations
import asyncio
import gzip
import json
import math
import os
import platform
from pathlib import Path
import numpy as np
from PIL import Image, ImageChops

try:
    import pyrlottie  # type: ignore
    from pyrlottie import LottieFile, convSingleLottieFrames  # type: ignore
    _HAS_RLOTTIE = True
except Exception:                                                  # pragma: no cover
    _HAS_RLOTTIE = False


def _read_lottie_json(path: Path) -> dict:
    raw = path.read_bytes()
    # TGS — это gzip над Lottie JSON; .json — просто Lottie JSON
    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    return json.loads(raw)


def tgs_info(path: Path) -> tuple[int, int, float, int]:
    """Извлечь (width, height, fps, frame_count) из Lottie-JSON без рендера."""
    data = _read_lottie_json(path)
    w = int(data.get("w", 512))
    h = int(data.get("h", 512))
    fps = float(data.get("fr", 60))
    ip = float(data.get("ip", 0))
    op = float(data.get("op", 0))
    frames = max(1, int(round(op - ip)))
    return w, h, fps, frames


def _image_has_content(path: Path) -> bool:
    try:
        with Image.open(path).convert("RGBA") as img:
            alpha = img.getchannel("A")
            if alpha.getbbox() is None:
                return False
            return True
    except Exception:
        return False


def _restore_alpha(black: Image.Image, white: Image.Image) -> Image.Image:
    black_arr = np.asarray(black.convert("RGB"), dtype=np.float32)
    white_arr = np.asarray(white.convert("RGB"), dtype=np.float32)
    alpha = 255.0 - np.mean(white_arr - black_arr, axis=2)
    alpha = np.clip(alpha, 0, 255)

    alpha_safe = np.maximum(alpha, 1.0)
    rgb = black_arr * 255.0 / alpha_safe[..., None]
    rgb = np.where(alpha[..., None] <= 0.5, 0, rgb)
    rgba = np.dstack((np.clip(rgb, 0, 255), alpha)).astype(np.uint8)
    return Image.fromarray(rgba, "RGBA")


def _render_lottie_frames(lf: LottieFile, background: str, frame_skip: int, scale: float) -> list[Image.Image]:
    rendered = asyncio.run(
        convSingleLottieFrames(lf, backgroundColour=background, frameSkip=frame_skip, scale=scale)
    )
    return list(rendered[lf.path].frames)


def _ensure_pyrlottie_renderer_ready() -> None:
    """Validate pyrlottie's bundled native renderer before starting a job."""
    if not _HAS_RLOTTIE:
        return

    if platform.system().lower() != "linux":
        return

    package_dir = Path(pyrlottie.__file__).resolve().parent
    machine = platform.machine().lower()
    bin_dir = package_dir / f"linux_{machine}"
    candidates = [bin_dir / "lottie2gif", bin_dir / "lottie2gif" / "app"]
    binaries = [path for path in candidates if path.is_file()]
    if not binaries:
        if machine not in {"x86_64", "amd64", "aarch64", "arm64"}:
            raise RuntimeError(
                f"pyrlottie has no bundled renderer for Linux {platform.machine()}. "
                "Use an x86_64/amd64 or aarch64/arm64 VPS."
            )
        return

    for binary in binaries:
        if os.access(binary, os.X_OK):
            continue
        try:
            binary.chmod(binary.stat().st_mode | 0o755)
        except OSError as exc:
            raise RuntimeError(
                f"pyrlottie renderer is not executable: {binary}. "
                "Rebuild the Docker image so Dockerfile can chmod it during install."
            ) from exc


def _frame_is_opaque_rgba(img: Image.Image) -> bool:
    return img.getchannel("A").getextrema() == (255, 255)


def _frame_needs_alpha_restore(img: Image.Image) -> bool:
    alpha = img.getchannel("A")
    return alpha.getbbox() is None or alpha.getextrema() == (255, 255)


def render_tgs_to_frames(
    src: Path,
    out_dir: Path,
    width: int = 512,
    height: int = 512,
    max_frames: int | None = None,
    target_fps: int | None = None,
) -> tuple[list[Path], float]:
    """
    Отрендерить TGS в PNG-кадры с альфа-каналом.
    Возвращает список путей к PNG-файлам в правильном порядке.
    """
    out_dir.mkdir(parents=True, exist_ok=True)

    if not _HAS_RLOTTIE:
        raise RuntimeError("pyrlottie is not available, cannot render animated TGS stickers")
    _ensure_pyrlottie_renderer_ready()

    # pyrlottie ожидает несжатый JSON
    raw = src.read_bytes()
    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    tmp_json = out_dir / "_input.json"
    tmp_json.write_bytes(raw)

    lf = LottieFile(str(tmp_json))
    # Узнаём количество кадров заранее
    data = json.loads(raw)
    fps = float(data.get("fr", 30))
    ip = float(data.get("ip", 0))
    op = float(data.get("op", fps))
    total = max(1, int(round(op - ip)))
    if target_fps and target_fps > 0 and target_fps < fps:
        step = max(1, int(round(fps / target_fps)))
    else:
        step = 1
    frame_skip = max(0, step - 1)
    limit = max_frames or math.ceil(total / step)
    scale = min(width / max(1, int(data.get("w", width))), height / max(1, int(data.get("h", height))))

    try:
        black_frames = _render_lottie_frames(lf, "000000", frame_skip, scale)
        white_frames = None
    except RuntimeError as exc:
        raise RuntimeError(f"TGS renderer failed: {exc}") from exc

    frames: list[Path] = []
    for i, black in enumerate(black_frames):
        if i >= limit:
            break
        rgba = black.convert("RGBA")
        if _frame_needs_alpha_restore(rgba):
            if white_frames is None:
                try:
                    white_frames = _render_lottie_frames(lf, "ffffff", frame_skip, scale)
                except RuntimeError:
                    white_frames = []
            if white_frames:
                rgba = _restore_alpha(black, white_frames[min(i, len(white_frames) - 1)])
            elif _frame_is_opaque_rgba(rgba):
                rgba.putalpha(255)
        canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        x = (width - rgba.width) // 2
        y = (height - rgba.height) // 2
        canvas.alpha_composite(rgba, (x, y))
        out_png = out_dir / f"frame_{i:04d}.png"
        canvas.save(out_png)
        frames.append(out_png)

    if not frames:
        raise RuntimeError("TGS renderer produced no frames")
    if not any(_image_has_content(frame) for frame in frames):
        first = frames[0]
        with Image.open(first).convert("RGBA") as img:
            img.putalpha(255)
            img.save(first)

    return frames, fps / step
