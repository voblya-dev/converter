"""
Главный пайплайн рендеринга:

  1. Подготовка PNG-кадров исходника (TGS / sticker / video-sticker / emoji)
  2. Подготовка фоновых кадров нужного размера и FPS
  3. Композитинг: фон  + (исходный кадр)  + (водяной знак)
  4. Кодирование в финальный формат через ffmpeg

Используется в render-хендлере; вызывается в отдельном потоке (asyncio.to_thread),
прогресс репортится через колбэк ``progress_cb(stage, percent)``.
"""
from __future__ import annotations
import shutil
import uuid
import math
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable
import numpy as np
from PIL import Image

from config import TMP_DIR
from services import (
    tgs_processor, sticker_processor, emoji_renderer,
    background_builder, watermark_engine, encoder,
)


ProgressCb = Callable[[str, int], None]
CancelCb = Callable[[], bool]
MAX_SOURCE_RENDER_SIDE = 768
DEFAULT_STATIC_VIDEO_SECONDS = 3
COMPOSITE_WORKERS = max(1, min(4, (os.cpu_count() or 2)))


class RenderCancelled(RuntimeError):
    """Raised when a user cancels an active render."""


def _effective_fps(raw_fps, src_fps: int, fmt: str) -> int:
    if raw_fps == "source":
        return max(1, int(round(src_fps or 30)))
    return max(1, int(raw_fps))


def _max_frames_for(total_frames: int, fmt: str) -> int | None:
    if fmt == "png":
        return 1
    return max(1, int(total_frames)) if total_frames else None


def _resample_frame_paths(frames: list[Path], src_fps: int, target_fps: int) -> list[Path]:
    if not frames or src_fps <= 0 or target_fps <= 0 or src_fps == target_fps:
        return frames
    duration = len(frames) / src_fps
    out_count = max(1, int(round(duration * target_fps)))
    if out_count == len(frames):
        return frames
    result: list[Path] = []
    for i in range(out_count):
        src_index = min(len(frames) - 1, int(math.floor(i * src_fps / target_fps)))
        result.append(frames[src_index])
    return result


def _decode_source(
    input_cfg: dict,
    src_file: Path | None,
    work: Path,
    target_fps: int,
    render_size: tuple[int, int] = (512, 512),
    max_frames: int | None = None,
) -> tuple[list[Path], int]:
    """Получить список PNG-кадров исходника + рекомендованный FPS источника."""
    it = input_cfg.get("type")
    if it == "tgs" and src_file:
        w, h, fps, _ = tgs_processor.tgs_info(src_file)
        render_w, render_h = render_size
        frames, effective_fps = tgs_processor.render_tgs_to_frames(
            src_file,
            work / "src",
            width=max(1, render_w),
            height=max(1, render_h),
            max_frames=max_frames,
            target_fps=target_fps,
        )
        return frames, max(1, int(round(effective_fps or fps or target_fps)))
    if it == "sticker" and src_file:
        fps, _ = sticker_processor.webp_info(src_file)
        frames = sticker_processor.render_webp_to_frames(src_file, work / "src", max_frames=max_frames)
        return frames, int(round(fps)) or target_fps
    if it == "sticker_video" and src_file:
        fps, _ = sticker_processor.webm_info(src_file)
        frames = sticker_processor.render_webm_to_frames(src_file, work / "src", fps=None, max_frames=max_frames)
        return frames, int(round(fps)) or target_fps
    if it == "emoji":
        frames = emoji_renderer.render_emoji(input_cfg.get("emoji") or "✨", work / "src")
        return frames, target_fps
    # Фолбэк — пустой прозрачный кадр
    work.mkdir(parents=True, exist_ok=True)
    p = work / "src" / "frame_0000.png"
    p.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGBA", (512, 512), (0, 0, 0, 0)).save(p)
    return [p], target_fps


def _scale_keep_aspect(img: Image.Image, max_w: int, max_h: int) -> Image.Image:
    iw, ih = img.size
    scale = min(max_w / iw, max_h / ih)
    nw = max(1, int(iw * scale))
    nh = max(1, int(ih * scale))
    return img.resize((nw, nh), Image.LANCZOS)


def _colorize_source(img: Image.Image, cfg: dict) -> Image.Image:
    if not cfg.get("enabled"):
        return img
    color = cfg.get("color", "#FFFFFF").lstrip("#")
    if len(color) != 6:
        return img
    try:
        target = np.array([int(color[i:i + 2], 16) for i in (0, 2, 4)], dtype=np.float32)
    except ValueError:
        return img

    strength = max(0.0, min(1.0, float(cfg.get("strength", 85)) / 100.0))
    rgba = np.asarray(img.convert("RGBA"), dtype=np.float32)
    rgb = rgba[..., :3]
    alpha = rgba[..., 3:4]
    luminance = (0.2126 * rgb[..., 0:1] + 0.7152 * rgb[..., 1:2] + 0.0722 * rgb[..., 2:3]) / 255.0
    shading = 0.28 + luminance * 1.05
    tinted = np.clip(target.reshape((1, 1, 3)) * shading, 0, 255)
    out_rgb = rgb * (1.0 - strength) + tinted * strength
    out = np.dstack((np.clip(out_rgb, 0, 255), alpha)).astype(np.uint8)
    return Image.fromarray(out, "RGBA")


def _compose_frame(
    idx: int,
    src_path: Path,
    bg_img: Image.Image,
    wm_layer: Image.Image | None,
    settings: dict,
    size: tuple[int, int],
    input_size_pct: int,
    fmt: str,
    comp_dir: Path,
) -> Path:
    W, H = size
    with Image.open(src_path) as src:
        src_img = src.convert("RGBA")
    src_img = _colorize_source(src_img, settings["input"].get("colorize", {}))
    inner_w = int(W * input_size_pct / 100)
    inner_h = int(H * input_size_pct / 100)
    scaled = _scale_keep_aspect(src_img, inner_w, inner_h)
    canvas = bg_img.convert("RGBA")
    ox = (W - scaled.width) // 2
    oy = (H - scaled.height) // 2
    canvas.alpha_composite(scaled, (ox, oy))
    if wm_layer is not None:
        watermark_engine.paste_watermark(canvas, wm_layer, settings["watermark"])
    out_png = comp_dir / f"frame_{idx:04d}.png"
    save_img = canvas.convert("RGB" if fmt in ("mp4", "gif", "png") else "RGBA")
    save_img.save(out_png, optimize=False, compress_level=1)
    return out_png


def _can_use_fast_color_path(settings: dict, fmt: str, bg_path: Path | None) -> bool:
    bg = settings.get("background", {})
    colorize = settings.get("input", {}).get("colorize", {})
    return (
        fmt in {"mp4", "webm"}
        and bg.get("mode") == "color"
        and bg_path is None
        and not settings.get("watermark", {}).get("enabled")
        and not colorize.get("enabled")
    )


def _raise_if_cancelled(cancelled: CancelCb | None) -> None:
    if cancelled and cancelled():
        raise RenderCancelled("Render cancelled")


def _scaled_preview_size(width: int, height: int, max_side: int = 512) -> tuple[int, int]:
    scale = min(1.0, max_side / max(width, height, 1))
    return max(1, int(width * scale)), max(1, int(height * scale))


def _copy_preview_settings(settings: dict) -> dict:
    import copy

    preview = copy.deepcopy(settings)
    out = preview["output"]
    out["width"], out["height"] = _scaled_preview_size(int(out["width"]), int(out["height"]))
    out["format"] = "png"
    out["fps"] = 1
    return preview


def render(
    settings: dict,
    input_path: Path | None,
    bg_path: Path | None,
    wm_image_path: Path | None,
    progress: ProgressCb | None = None,
    cancelled: CancelCb | None = None,
) -> Path:
    """
    Запустить полный пайплайн. Возвращает путь к финальному файлу.
    Кидает Exception при критической ошибке.
    """
    job_id = uuid.uuid4().hex[:8]
    work = TMP_DIR / f"job_{job_id}"
    work.mkdir(parents=True, exist_ok=True)
    try:
        _raise_if_cancelled(cancelled)
        # ── 1. Исходные кадры ─────────────────────────────────
        if progress:
            progress("frames", 5)

        out = settings["output"]
        fmt = out["format"]
        if settings["background"].get("mode") == "video" and fmt == "png":
            fmt = "mp4"
        W, H = int(out["width"]), int(out["height"])
        fps_raw = out["fps"]
        input_size_pct = max(5, min(100, int(settings["input"].get("size_pct", 80))))
        source_render_size = (
            max(1, int(W * input_size_pct / 100)),
            max(1, int(H * input_size_pct / 100)),
        )
        scale_down = min(
            1.0,
            MAX_SOURCE_RENDER_SIDE / max(source_render_size[0], source_render_size[1], 1),
        )
        if scale_down < 1.0:
            source_render_size = (
                max(1, int(source_render_size[0] * scale_down)),
                max(1, int(source_render_size[1] * scale_down)),
            )

        src_fps = target_fps = 30
        try:
            src_total_frames = 0
            if settings["input"].get("type") == "tgs" and input_path:
                _, _, src_fps_float, src_total_frames = tgs_processor.tgs_info(input_path)
                src_fps = int(round(src_fps_float)) or 30
            elif settings["input"].get("type") == "sticker" and input_path:
                src_fps_float, src_total_frames = sticker_processor.webp_info(input_path)
                src_fps = int(round(src_fps_float)) or 30
            elif settings["input"].get("type") == "sticker_video" and input_path:
                src_fps_float, src_total_frames = sticker_processor.webm_info(input_path)
                src_fps = int(round(src_fps_float)) or 30
        except Exception:
            src_fps = 30
            src_total_frames = 0
        target_fps = _effective_fps(fps_raw, src_fps, fmt)
        max_frames = _max_frames_for(src_total_frames, fmt)

        src_frames, src_fps = _decode_source(
            settings["input"], input_path, work, target_fps=target_fps,
            render_size=source_render_size, max_frames=max_frames,
        )
        _raise_if_cancelled(cancelled)
        src_frames = _resample_frame_paths(src_frames, src_fps, target_fps)
        if settings["background"].get("mode") == "video" and len(src_frames) == 1 and fmt != "png":
            repeat_count = max(1, int(target_fps * DEFAULT_STATIC_VIDEO_SECONDS))
            src_frames = src_frames * repeat_count
        # PNG — статичный: ограничиваем 1 кадром
        if fmt == "png":
            src_frames = src_frames[:1]
        frame_count = len(src_frames)

        if progress:
            progress("frames", 25)

        if _can_use_fast_color_path(settings, fmt, bg_path):
            _raise_if_cancelled(cancelled)
            if progress:
                progress("final", 80)
            ext = {"mp4": "mp4", "webm": "webm"}[fmt]
            out_file = work / f"result.{ext}"
            encoder.encode_centered_on_color(
                str(work / "src" / "frame_%04d.png"),
                out_file,
                fps=target_fps,
                fmt=fmt,
                canvas_size=(W, H),
                input_size_pct=input_size_pct,
                bg_color=settings["background"]["color"],
                quality=out["quality"],
                speed=float(out.get("speed", 1.0)),
            )
            _raise_if_cancelled(cancelled)
            if progress:
                progress("final", 100)
            if not out_file.exists() or out_file.stat().st_size == 0:
                raise RuntimeError("Encoder produced empty file (check ffmpeg installation)")
            return out_file

        # ── 2. Фоновые кадры ─────────────────────────────────
        bg_iter = background_builder.iter_background(
            settings["background"], (W, H), target_fps,
            frame_count, bg_path, work,
        )
        _raise_if_cancelled(cancelled)

        # ── 3. Водяной знак (один слой на все кадры — статичный) ─
        wm_layer = watermark_engine.build_watermark_layer(
            settings["watermark"], (W, H), wm_image_path,
        )
        _raise_if_cancelled(cancelled)

        if progress:
            progress("watermark", 45)

        # ── 4. Композитинг ───────────────────────────────────
        comp_dir = work / "comp"
        comp_dir.mkdir(exist_ok=True)
        frames_to_compose = list(enumerate(zip(src_frames, bg_iter)))
        if frame_count > 1 and COMPOSITE_WORKERS > 1 and cancelled is None:
            done = 0
            with ThreadPoolExecutor(max_workers=COMPOSITE_WORKERS) as pool:
                futures = [
                    pool.submit(
                        _compose_frame,
                        idx, src_path, bg_img, wm_layer, settings, (W, H),
                        input_size_pct, fmt, comp_dir,
                    )
                    for idx, (src_path, bg_img) in frames_to_compose
                ]
                for future in futures:
                    _raise_if_cancelled(cancelled)
                    future.result()
                    done += 1
                    if progress and frame_count:
                        pct = 45 + int(35 * done / frame_count)
                        progress("watermark", pct)
        else:
            for idx, (src_path, bg_img) in frames_to_compose:
                _raise_if_cancelled(cancelled)
                _compose_frame(
                    idx, src_path, bg_img, wm_layer, settings, (W, H),
                    input_size_pct, fmt, comp_dir,
                )
                if progress and frame_count:
                    pct = 45 + int(35 * (idx + 1) / frame_count)
                    progress("watermark", pct)

        # ── 5. Кодирование ───────────────────────────────────
        if progress:
            progress("final", 85)

        _raise_if_cancelled(cancelled)
        ext = {"gif": "gif", "mp4": "mp4", "webm": "webm", "png": "png"}[fmt]
        out_file = work / f"result.{ext}"
        encoder.encode(
            str(comp_dir / "frame_%04d.png"),
            out_file,
            fps=target_fps,
            fmt=fmt,
            quality=out["quality"],
            speed=float(out.get("speed", 1.0)),
            width=W,
            height=H,
        )
        _raise_if_cancelled(cancelled)

        if progress:
            progress("final", 100)

        if not out_file.exists() or out_file.stat().st_size == 0:
            raise RuntimeError("Encoder produced empty file (check ffmpeg installation)")
        return out_file

    except Exception:
        # Оставляем папку для диагностики, но прокидываем ошибку выше
        raise
    finally:
        # Подчищаем промежуточные подпапки, но финальный файл должен остаться
        for sub in ("src", "bgframes", "comp"):
            p = work / sub
            if p.exists():
                shutil.rmtree(p, ignore_errors=True)


def render_preview(
    settings: dict,
    input_path: Path | None,
    bg_path: Path | None,
    wm_image_path: Path | None,
) -> Path:
    """Render a lightweight PNG preview using the same composition pipeline."""
    return render(
        _copy_preview_settings(settings),
        input_path,
        bg_path,
        wm_image_path,
        progress=None,
        cancelled=None,
    )
