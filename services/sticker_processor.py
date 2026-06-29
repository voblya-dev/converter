"""
Обработка обычных стикеров (WEBP — статичный или анимированный) и
видео-стикеров (WEBM).  Возвращаем последовательность RGBA-кадров.
"""
from __future__ import annotations
import json
from pathlib import Path
from PIL import Image
from services.ffmpeg_runner import run_ffmpeg, resolve_ffmpeg
import subprocess


def webp_info(src: Path) -> tuple[float, int]:
    with Image.open(src) as im:
        frame_count = getattr(im, "n_frames", 1)
        durations = []
        for i in range(frame_count):
            im.seek(i)
            durations.append(int(im.info.get("duration") or 100))
        avg_ms = max(1, sum(durations) / max(1, len(durations)))
        return 1000.0 / avg_ms, frame_count


def webm_info(src: Path) -> tuple[float, int]:
    ffmpeg = Path(resolve_ffmpeg())
    ffprobe = ffmpeg.with_name("ffprobe.exe" if ffmpeg.suffix.lower() == ".exe" else "ffprobe")
    cmd = [
        str(ffprobe),
        "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=avg_frame_rate,r_frame_rate,nb_frames,duration",
        "-of", "json",
        str(src),
    ]
    result = subprocess.run(cmd, check=False, capture_output=True)
    if result.returncode != 0:
        return 30.0, 0
    data = json.loads(result.stdout.decode("utf-8", errors="replace") or "{}")
    stream = (data.get("streams") or [{}])[0]

    def parse_rate(value: str | None) -> float:
        if not value or value == "0/0":
            return 0.0
        if "/" in value:
            n, d = value.split("/", 1)
            return float(n) / max(1.0, float(d))
        return float(value)

    fps = parse_rate(stream.get("avg_frame_rate")) or parse_rate(stream.get("r_frame_rate")) or 30.0
    frames = int(float(stream.get("nb_frames") or 0))
    if not frames:
        duration = float(stream.get("duration") or 0)
        frames = int(round(duration * fps)) if duration > 0 else 0
    return fps, frames


def render_webp_to_frames(src: Path, out_dir: Path, max_frames: int | None = 180) -> list[Path]:
    """Разложить WEBP (возможно анимированный) на PNG-кадры."""
    out_dir.mkdir(parents=True, exist_ok=True)
    frames: list[Path] = []
    with Image.open(src) as im:
        im.seek(0)
        i = 0
        while True:
            png = out_dir / f"frame_{i:04d}.png"
            im.convert("RGBA").save(png)
            frames.append(png)
            i += 1
            if max_frames is not None and i >= max_frames:
                break
            try:
                im.seek(im.tell() + 1)
            except EOFError:
                break
    if not frames:
        png = out_dir / "frame_0000.png"
        Image.new("RGBA", (512, 512), (0, 0, 0, 0)).save(png)
        frames = [png]
    return frames


def render_webm_to_frames(src: Path, out_dir: Path, fps: int | None = None, max_frames: int | None = 180) -> list[Path]:
    """Распаковать WEBM-стикер в PNG-кадры через ffmpeg (с альфа-каналом)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    pattern = out_dir / "frame_%04d.png"
    cmd = ["-y", "-i", str(src)]
    if fps:
        cmd += ["-vf", f"fps={fps}"]
    if max_frames is not None:
        cmd += ["-vframes", str(max_frames)]
    cmd += ["-pix_fmt", "rgba", str(pattern)]
    run_ffmpeg(cmd)
    frames = sorted(out_dir.glob("frame_*.png"))
    if not frames:
        png = out_dir / "frame_0000.png"
        Image.new("RGBA", (512, 512), (0, 0, 0, 0)).save(png)
        frames = [png]
    return frames
