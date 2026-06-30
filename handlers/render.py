"""
Хендлер рендера.

Поток:
  1. Проверяем, что у пользователя есть исходник.
  2. Отправляем сообщение «🌀 Начинаю рендеринг...».
  3. Запускаем рендер в отдельном потоке через asyncio.to_thread.
  4. Параллельно крутим анимацию прогресса (редактируем сообщение).
  5. По завершении высылаем готовый файл нужным методом
     (send_document для GIF/WEBM, send_video для MP4,
     send_photo для png).
"""
from __future__ import annotations
import asyncio
import copy
import shutil
import time
import uuid
from pathlib import Path
from html import escape

from aiogram import Router, F, Bot
from aiogram.exceptions import TelegramRetryAfter
from aiogram.types import CallbackQuery, FSInputFile

from config import MAX_RENDER_SECONDS, TMP_DIR
from utils import state, keyboards
from utils.files import find_background, find_input, find_watermark_image
from utils.i18n import t
from utils.progress import bar
from utils.render_queue import RenderQueueFull, enqueue_render
from utils.auto_palette import apply_auto_palette_async
from services import renderer
from services import sticker_processor, tgs_processor

router = Router(name="render")

# хранилище «отмена» по user_id
_cancel_flags: dict[int, bool] = {}


async def _telegram_retry(factory, attempts: int = 5):
    last_exc = None
    for _ in range(max(1, attempts)):
        try:
            return await factory()
        except TelegramRetryAfter as exc:
            last_exc = exc
            await asyncio.sleep(max(1, int(exc.retry_after)) + 1)
    if last_exc:
        raise last_exc


def _copy_optional(src: Path | None, dst_dir: Path, name: str) -> Path | None:
    if not src or not src.exists():
        return None
    dst = dst_dir / f"{name}{src.suffix.lower()}"
    shutil.copy2(src, dst)
    return dst


def _snapshot_render_job(uid: int, settings: dict) -> tuple[dict, Path | None, Path | None, Path | None, Path]:
    snapshot = copy.deepcopy(settings)
    job_dir = TMP_DIR / "queue" / uuid.uuid4().hex[:8]
    job_dir.mkdir(parents=True, exist_ok=True)
    input_path = _copy_optional(find_input(uid, snapshot), job_dir, "input")
    bg_path = _copy_optional(find_background(uid, snapshot), job_dir, "background")
    wm_path = _copy_optional(find_watermark_image(uid, snapshot), job_dir, "watermark")
    return snapshot, input_path, bg_path, wm_path, job_dir


def _format_bytes(value: int) -> str:
    size = float(value)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def _result_summary(path: Path, settings: dict, input_path: Path | None, lang: str) -> str:
    out = settings["output"]
    fmt = path.suffix.lstrip(".").upper() or out["format"].upper()
    width = int(out["width"])
    height = int(out["height"])
    fps = out["fps"]
    frames = 1
    src_type = settings["input"].get("type")
    try:
        if src_type == "tgs" and input_path:
            _w, _h, src_fps, frames = tgs_processor.tgs_info(input_path)
            if fps == "source":
                fps = int(round(src_fps)) or fps
        elif src_type == "sticker" and input_path:
            src_fps, frames = sticker_processor.webp_info(input_path)
            if fps == "source":
                fps = int(round(src_fps)) or fps
        elif src_type == "sticker_video" and input_path:
            src_fps, frames = sticker_processor.webm_info(input_path)
            if fps == "source":
                fps = int(round(src_fps)) or fps
    except Exception:
        frames = 1
    duration = 0.0
    try:
        duration = max(0.0, frames / max(1, int(fps))) if fmt != "PNG" else 0.0
    except Exception:
        duration = 0.0
    return t(
        lang,
        "render_summary",
        fmt=fmt,
        w=width,
        h=height,
        fps=fps,
        duration=f"{duration:.1f}",
        size=_format_bytes(path.stat().st_size),
    )


@router.callback_query(F.data == "render:cancel")
async def cb_cancel(call: CallbackQuery):
    _cancel_flags[call.from_user.id] = True
    await call.answer("Cancel requested")


async def render_for_message(message, bot: Bot, uid: int) -> None:
    s = state.get(uid)
    lang = s["lang"]

    if not s["input"].get("type"):
        await message.answer(t(lang, "no_input"), parse_mode="HTML")
        return
    if await apply_auto_palette_async(s, find_input(uid, s)):
        state.save(uid)
    job_settings, input_path, bg_path, wm_path, snapshot_dir = _snapshot_render_job(uid, s)
    if s["input"].get("type") != "emoji" and input_path is None:
        shutil.rmtree(snapshot_dir, ignore_errors=True)
        await message.answer(t(lang, "no_input"), parse_mode="HTML")
        return

    queue_msg = None
    try:
        ticket = await enqueue_render(uid)
    except RenderQueueFull:
        shutil.rmtree(snapshot_dir, ignore_errors=True)
        await message.answer(t(lang, "render_queue_full"), parse_mode="HTML")
        return

    try:
        position = await ticket.position()
        if position > 1:
            queue_msg = await message.answer(
                t(lang, "render_queued", position=position),
                parse_mode="HTML",
            )
            while await ticket.position() > 1:
                new_position = await ticket.position()
                try:
                    await _telegram_retry(
                        lambda: queue_msg.edit_text(
                            t(lang, "render_queued", position=new_position),
                            parse_mode="HTML",
                        ),
                        attempts=2,
                    )
                except Exception:
                    pass
                await asyncio.sleep(4)
            try:
                await queue_msg.delete()
            except Exception:
                pass

        await ticket.wait_until_ready()
        async with ticket:
            await _render_for_message_locked(
                message, bot, uid, job_settings, lang, input_path, bg_path, wm_path
            )
    finally:
        await ticket.release()
        shutil.rmtree(snapshot_dir, ignore_errors=True)


async def _render_for_message_locked(
    message,
    bot: Bot,
    uid: int,
    s: dict,
    lang: str,
    input_path: Path | None,
    bg_path: Path | None,
    wm_image_path: Path | None,
) -> None:
    _cancel_flags[uid] = False

    # Стартовое сообщение
    progress_msg = await message.answer(
        t(lang, "render_start"),
        parse_mode="HTML",
        reply_markup=keyboards.cancel_render(lang),
    )

    # Состояние прогресса, которое будет обновляться из колбэка рендера
    progress_state = {"stage": "frames", "pct": 0, "last_render_pct": 0}
    deadline = time.monotonic() + max(1, MAX_RENDER_SECONDS)

    def progress_cb(stage: str, pct: int):
        progress_state["stage"] = stage
        progress_state["last_render_pct"] = pct

    def is_cancelled() -> bool:
        return _cancel_flags.get(uid, False) or time.monotonic() >= deadline

    async def animator():
        """Цикл, который раз в ~0.6 с обновляет сообщение прогресса."""
        last_text = ""
        while progress_state.get("done") is not True:
            await asyncio.sleep(0.6)
            stage = progress_state["stage"]
            # Сглаживаем «искусственный» прогресс анимацией:
            real = progress_state["last_render_pct"]
            cur = progress_state["pct"]
            # анимируем кратко вперёд каждую тик-секунду
            cur = min(99, max(cur + 2, real))
            progress_state["pct"] = cur

            key = {
                "download": "render_download",
                "draw":     "render_draw",
                "frames":   "render_draw",
                "watermark": "render_draw",
                "encode":   "render_encode",
                "final":    "render_encode",
                "send":     "render_send",
            }.get(stage, "render_draw")

            txt = t(lang, key, bar=bar(cur), pct=cur)
            if txt != last_text:
                try:
                    await _telegram_retry(
                        lambda: progress_msg.edit_text(
                            txt, parse_mode="HTML",
                            reply_markup=keyboards.cancel_render(lang),
                        ),
                        attempts=2,
                    )
                    last_text = txt
                except Exception:
                    pass

    async def runner():
        loop = asyncio.get_running_loop()
        # Запускаем рендер в пуле потоков
        return await loop.run_in_executor(
            None,
            lambda: renderer.render(
                s,
                input_path,
                bg_path,
                wm_image_path,
                progress_cb,
                is_cancelled,
            ),
        )

    anim_task = asyncio.create_task(animator())
    try:
        result_path: Path = await asyncio.wait_for(runner(), timeout=max(1, MAX_RENDER_SECONDS))
        progress_state["pct"] = 100
        progress_state["stage"] = "final"
    except asyncio.TimeoutError:
        _cancel_flags[uid] = True
        progress_state["done"] = True
        await anim_task
        await _telegram_retry(lambda: progress_msg.edit_text(t(lang, "render_timeout"), parse_mode="HTML"))
        return
    except renderer.RenderCancelled:
        progress_state["done"] = True
        await anim_task
        try:
            await _telegram_retry(lambda: progress_msg.edit_text(t(lang, "render_cancelled"), parse_mode="HTML"))
        except Exception:
            await _telegram_retry(lambda: message.answer(t(lang, "render_cancelled"), parse_mode="HTML"))
        return
    except Exception as e:
        progress_state["done"] = True
        await anim_task
        try:
            await _telegram_retry(
                lambda: progress_msg.edit_text(
                    t(lang, "render_error", err=escape(str(e)[:200])),
                    parse_mode="HTML",
                )
            )
        except Exception:
            try:
                await _telegram_retry(
                    lambda: message.answer(t(lang, "render_error", err=escape(str(e)[:200])), parse_mode="HTML")
                )
            except Exception:
                pass
        return
    finally:
        progress_state["done"] = True

    await anim_task

    fmt = result_path.suffix.lstrip(".").lower() or s["output"]["format"]
    file = FSInputFile(str(result_path))
    result_kb = keyboards.render_result(lang)
    summary = _result_summary(result_path, s, input_path, lang)
    try:
        if fmt == "gif":
            await _telegram_retry(lambda: message.answer_document(file, caption=summary, parse_mode="HTML", reply_markup=result_kb))
        elif fmt == "mp4":
            await _telegram_retry(lambda: message.answer_video(file, caption=summary, parse_mode="HTML", reply_markup=result_kb))
        elif fmt == "webm":
            await _telegram_retry(lambda: message.answer_document(file, caption=summary, parse_mode="HTML", reply_markup=result_kb))
        elif fmt == "png":
            await _telegram_retry(lambda: message.answer_photo(file, caption=summary, parse_mode="HTML", reply_markup=result_kb))
        else:
            await _telegram_retry(lambda: message.answer_document(file, caption=summary, parse_mode="HTML", reply_markup=result_kb))
    except Exception as e:
        try:
            await _telegram_retry(
                lambda: progress_msg.edit_text(
                    t(lang, "render_error", err=escape(str(e)[:200])),
                    parse_mode="HTML",
                )
            )
        except Exception:
            try:
                await _telegram_retry(
                    lambda: message.answer(t(lang, "render_error", err=escape(str(e)[:200])), parse_mode="HTML")
                )
            except Exception:
                pass
        return
    finally:
        shutil.rmtree(result_path.parent, ignore_errors=True)
        _cancel_flags.pop(uid, None)

    try:
        await progress_msg.delete()
    except Exception:
        pass


@router.callback_query(F.data == "main:render")
async def cb_render(call: CallbackQuery, bot: Bot):
    await call.answer()
    await render_for_message(call.message, bot, call.from_user.id)
