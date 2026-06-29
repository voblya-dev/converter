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
import shutil
from pathlib import Path
from html import escape

from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, FSInputFile

from config import MAX_RENDER_SECONDS
from utils import state, keyboards
from utils.files import find_background, find_input, find_watermark_image
from utils.i18n import t
from utils.progress import bar
from services import renderer
from services import sticker_processor, tgs_processor

router = Router(name="render")

# хранилище «отмена» по user_id
_cancel_flags: dict[int, bool] = {}


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

    _cancel_flags[uid] = False

    # Стартовое сообщение
    progress_msg = await message.answer(
        t(lang, "render_start"),
        parse_mode="HTML",
        reply_markup=keyboards.cancel_render(lang),
    )

    # Состояние прогресса, которое будет обновляться из колбэка рендера
    progress_state = {"stage": "frames", "pct": 0, "last_render_pct": 0}
    def progress_cb(stage: str, pct: int):
        progress_state["stage"] = stage
        progress_state["last_render_pct"] = pct

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
                    await progress_msg.edit_text(
                        txt, parse_mode="HTML",
                        reply_markup=keyboards.cancel_render(lang),
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
                find_input(uid, s),
                find_background(uid, s),
                find_watermark_image(uid, s),
                progress_cb,
                lambda: _cancel_flags.get(uid, False),
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
        await progress_msg.edit_text(t(lang, "render_timeout"), parse_mode="HTML")
        return
    except renderer.RenderCancelled:
        progress_state["done"] = True
        await anim_task
        try:
            await progress_msg.edit_text(t(lang, "render_cancelled"), parse_mode="HTML")
        except Exception:
            await message.answer(t(lang, "render_cancelled"), parse_mode="HTML")
        return
    except Exception as e:
        progress_state["done"] = True
        await anim_task
        try:
            await progress_msg.edit_text(
                t(lang, "render_error", err=escape(str(e)[:200])),
                parse_mode="HTML",
            )
        except Exception:
            await message.answer(t(lang, "render_error", err=escape(str(e)[:200])), parse_mode="HTML")
        return
    finally:
        progress_state["done"] = True

    await anim_task

    try:
        await progress_msg.delete()
    except Exception:
        pass

    fmt = result_path.suffix.lstrip(".").lower() or s["output"]["format"]
    file = FSInputFile(str(result_path))
    result_kb = keyboards.render_result(lang)
    summary = _result_summary(result_path, s, find_input(uid, s), lang)
    if fmt == "gif":
        await message.answer_document(file, caption=summary, parse_mode="HTML", reply_markup=result_kb)
    elif fmt == "mp4":
        await message.answer_video(file, caption=summary, parse_mode="HTML", reply_markup=result_kb)
    elif fmt == "webm":
        await message.answer_document(file, caption=summary, parse_mode="HTML", reply_markup=result_kb)
    elif fmt == "png":
        await message.answer_photo(file, caption=summary, parse_mode="HTML", reply_markup=result_kb)
    else:
        await message.answer_document(file, caption=summary, parse_mode="HTML", reply_markup=result_kb)

    shutil.rmtree(result_path.parent, ignore_errors=True)
    _cancel_flags.pop(uid, None)


@router.callback_query(F.data == "main:render")
async def cb_render(call: CallbackQuery, bot: Bot):
    await call.answer()
    await render_for_message(call.message, bot, call.from_user.id)
