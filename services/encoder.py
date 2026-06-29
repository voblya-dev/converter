"""
Кодирование готовой последовательности PNG-кадров в финальный файл.
Использует ffmpeg-CLI; поддерживает GIF / MP4 / WEBM / PNG (одиночный).
"""
from __future__ import annotations
from pathlib import Path
from typing import Callable
from services.ffmpeg_runner import run_ffmpeg

CancelCb = Callable[[], bool]

_QUALITY_MAP = {
    # CRF для libx264 / libvpx-vp9 (ниже = качественнее)
    "low":      {"crf": 32, "preset": "ultrafast"},
    "medium":   {"crf": 26, "preset": "ultrafast"},
    "high":     {"crf": 20, "preset": "superfast"},
    "lossless": {"crf": 14, "preset": "superfast"},
}


def encode(
    frames_pattern: str,
    out_path: Path,
    fps: int,
    fmt: str,
    quality: str = "high",
    speed: float = 1.0,
    width: int | None = None,
    height: int | None = None,
    cancelled: CancelCb | None = None,
) -> Path:
    """
    frames_pattern: `…/frame_%04d.png`
    fmt: gif | mp4 | webm | png
    """
    q = _QUALITY_MAP.get(quality, _QUALITY_MAP["high"])
    speed = max(0.1, float(speed))
    input_fps = max(1.0, float(fps) * speed)
    output_fps = max(1, int(round(fps)))

    if fmt == "png":
        # Берём первый кадр как итоговую PNG
        src = Path(frames_pattern.replace("%04d", "0000"))
        out_path.write_bytes(src.read_bytes())
        return out_path

    if fmt == "gif":
        # Двухпроходный GIF: палитра -> финальный
        palette = out_path.with_suffix(".palette.png")
        palette_stats = "full" if quality in {"high", "lossless"} else "diff"
        dither = "sierra2_4a" if quality in {"high", "lossless"} else "bayer:bayer_scale=3"
        run_ffmpeg(
            ["-y", "-framerate", f"{input_fps:.3f}", "-i", frames_pattern,
             "-vf", f"fps={output_fps},format=rgb24,palettegen=stats_mode={palette_stats}:max_colors=256",
             str(palette)],
            cancelled=cancelled,
        )
        run_ffmpeg(
            ["-y", "-framerate", f"{input_fps:.3f}", "-i", frames_pattern,
             "-i", str(palette),
             "-lavfi", f"fps={output_fps},format=rgb24[x];[x][1:v]paletteuse=dither={dither}:diff_mode=rectangle",
             "-loop", "0", str(out_path)],
            cancelled=cancelled,
        )
        if palette.exists():
            try:
                palette.unlink()
            except OSError:
                pass
        return out_path

    if fmt == "mp4":
        cmd = [
            "-y", "-framerate", f"{input_fps:.3f}", "-i", frames_pattern,
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-preset", q["preset"], "-crf", str(q["crf"]),
            "-tune", "animation",
            "-threads", "0",
            "-vf", f"fps={output_fps},pad=ceil(iw/2)*2:ceil(ih/2)*2",
            "-movflags", "+faststart",
            str(out_path),
        ]
        run_ffmpeg(cmd, cancelled=cancelled)
        return out_path

    if fmt == "webm":
        cmd = [
            "-y", "-framerate", f"{input_fps:.3f}", "-i", frames_pattern,
            "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p",
            "-b:v", "0", "-crf", str(q["crf"]),
            "-deadline", "realtime", "-cpu-used", "8", "-row-mt", "1", "-threads", "0",
            "-vf", f"fps={output_fps}",
            str(out_path),
        ]
        run_ffmpeg(cmd, cancelled=cancelled)
        return out_path

    raise ValueError(f"Unsupported format: {fmt}")


def encode_centered_on_color(
    frames_pattern: str,
    out_path: Path,
    fps: int,
    fmt: str,
    canvas_size: tuple[int, int],
    input_size_pct: int,
    bg_color: str,
    quality: str = "high",
    speed: float = 1.0,
    cancelled: CancelCb | None = None,
) -> Path:
    """Fast path: let ffmpeg scale, pad and encode source frames on a solid background."""
    if fmt not in {"mp4", "webm"}:
        return encode(frames_pattern, out_path, fps, fmt, quality, speed)

    q = _QUALITY_MAP.get(quality, _QUALITY_MAP["high"])
    speed = max(0.1, float(speed))
    input_fps = max(1.0, float(fps) * speed)
    output_fps = max(1, int(round(fps)))
    width, height = canvas_size
    inner_w = max(2, int(width * input_size_pct / 100))
    inner_h = max(2, int(height * input_size_pct / 100))
    color = bg_color if bg_color.startswith("#") else f"#{bg_color}"
    vf = (
        f"fps={output_fps},"
        f"scale={inner_w}:{inner_h}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color={color},"
        "pad=ceil(iw/2)*2:ceil(ih/2)*2"
    )

    if fmt == "mp4":
        cmd = [
            "-y", "-framerate", f"{input_fps:.3f}", "-i", frames_pattern,
            "-vf", vf,
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-preset", q["preset"], "-crf", str(q["crf"]),
            "-tune", "animation", "-threads", "0",
            "-movflags", "+faststart",
            str(out_path),
        ]
    else:
        cmd = [
            "-y", "-framerate", f"{input_fps:.3f}", "-i", frames_pattern,
            "-vf", vf,
            "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p",
            "-b:v", "0", "-crf", str(q["crf"]),
            "-deadline", "realtime", "-cpu-used", "8", "-row-mt", "1", "-threads", "0",
            str(out_path),
        ]
    run_ffmpeg(cmd, cancelled=cancelled)
    return out_path
