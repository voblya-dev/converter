"""
Генерация фоновых слоёв нужного размера:
* однотонный цвет
* линейный градиент
* статичное изображение
* видеофон (на каждый кадр берётся соответствующий кадр исходного видео)
"""
from __future__ import annotations
from pathlib import Path
from typing import Callable, Iterable
from PIL import Image
from services.ffmpeg_runner import run_ffmpeg
from utils.colors import hex_to_rgb, make_gradient


def solid(size: tuple[int, int], color_hex: str) -> Image.Image:
    return Image.new("RGB", size, hex_to_rgb(color_hex))


def gradient(size: tuple[int, int], c1: str, c2: str, direction: str) -> Image.Image:
    return make_gradient(size, c1, c2, direction)


def image_fit(src: Path, size: tuple[int, int]) -> Image.Image:
    """
    Подогнать изображение под холст по принципу "cover":
    масштабируем так, чтобы покрыло, центрируем и обрезаем.
    """
    img = Image.open(src).convert("RGB")
    iw, ih = img.size
    tw, th = size
    scale = max(tw / iw, th / ih)
    nw, nh = int(iw * scale), int(ih * scale)
    img = img.resize((nw, nh), Image.LANCZOS)
    x = (nw - tw) // 2
    y = (nh - th) // 2
    return img.crop((x, y, x + tw, y + th))


CancelCb = Callable[[], bool]


def extract_video_frames(
    src: Path,
    out_dir: Path,
    size: tuple[int, int],
    fps: int,
    frames_needed: int,
    cancelled: CancelCb | None = None,
) -> list[Path]:
    """
    Достать `frames_needed` кадров из видео с заданным FPS, отмасштабировав
    их под размер холста (cover).
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    w, h = size
    pattern = out_dir / "bg_%04d.png"
    vf = (
        f"fps={fps},"
        f"scale={w}:{h}:force_original_aspect_ratio=increase,"
        f"crop={w}:{h}"
    )
    cmd = [
        "-y", "-stream_loop", "-1", "-i", str(src),
        "-vf", vf,
        "-frames:v", str(frames_needed),
        str(pattern),
    ]
    run_ffmpeg(cmd, cancelled=cancelled)
    return sorted(out_dir.glob("bg_*.png"))


def iter_background(
    bg_cfg: dict,
    size: tuple[int, int],
    fps: int,
    frame_count: int,
    src_file: Path | None,
    work_dir: Path,
    cancelled: CancelCb | None = None,
) -> Iterable[Image.Image]:
    """Генератор фоновых кадров (по одному на каждый кадр анимации)."""
    mode = bg_cfg["mode"]
    if mode == "color":
        bg = solid(size, bg_cfg["color"])
        for _ in range(frame_count):
            yield bg.copy()
    elif mode == "gradient":
        bg = gradient(size, bg_cfg["color"], bg_cfg["color2"], bg_cfg["direction"])
        for _ in range(frame_count):
            yield bg.copy()
    elif mode in {"image", "global_image"} and src_file and src_file.exists():
        bg = image_fit(src_file, size)
        for _ in range(frame_count):
            yield bg.copy()
    elif mode == "video" and src_file and src_file.exists():
        paths = extract_video_frames(src_file, work_dir / "bgframes", size, fps, frame_count, cancelled=cancelled)
        if not paths:                                            # фолбэк
            bg = solid(size, "#000000")
            for _ in range(frame_count):
                yield bg.copy()
            return
        for i in range(frame_count):
            p = paths[i % len(paths)]
            yield Image.open(p).convert("RGB")
    else:
        bg = solid(size, "#000000")
        for _ in range(frame_count):
            yield bg.copy()
