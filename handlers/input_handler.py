"""
Приём входящего контента:
    * стикер (TGS / WEBP / WEBM)
    * текстовое сообщение с одним эмодзи
    * текстовые ответы на «ожидающие» вопросы (HEX, кастомный размер, текст WM, …)
    * фото / видео — как пользовательский фон или картинка-водяной знак.
    * документ — TTF/OTF-шрифт.
"""
from __future__ import annotations
import shutil
import re
import time
from pathlib import Path
from html import escape

import emoji as emoji_lib
from aiogram import Router, F, Bot
from aiogram.types import Message

from config import ADMIN_ID, BACKGROUNDS_DIR, TMP_DIR, FONTS_DIR, MAX_UPLOAD_MB
from utils import state, keyboards
from utils.i18n import t
from utils.premium_emoji import premiumize_text
from utils.colors import parse_hex
from handlers.start import main_menu_text
from handlers.render import render_for_message

router = Router(name="input")


def _msg(text: str) -> str:
    return premiumize_text(re.sub(r"`([^`]+)`", r"<code>\1</code>", text))


def _user_dir(uid: int) -> Path:
    d = TMP_DIR / f"u{uid}"
    d.mkdir(parents=True, exist_ok=True)
    return d


async def _download(bot: Bot, file_id: str, dst: Path) -> Path:
    f = await bot.get_file(file_id)
    await bot.download_file(f.file_path, destination=dst)
    return dst


async def _telegram_file_path(bot: Bot, file_id: str) -> str:
    f = await bot.get_file(file_id)
    return f.file_path or ""


async def _accept_premium_emoji_sticker(message: Message, bot: Bot, st) -> None:
    uid = message.from_user.id
    s = state.get(uid)
    state.set_await(uid, None)

    udir = _user_dir(uid)
    for old in udir.glob("input.*"):
        old.unlink(missing_ok=True)

    premium_animation = getattr(st, "premium_animation", None)
    if not st.is_animated and not st.is_video and premium_animation:
        mime = (getattr(premium_animation, "mime_type", "") or "").lower()
        file_id = premium_animation.file_id
        file_path = (getattr(premium_animation, "file_path", "") or "").lower()
        if not file_path:
            file_path = (await _telegram_file_path(bot, file_id)).lower()
        if "tgsticker" in mime or "gzip" in mime or mime.endswith("tgs") or file_path.endswith(".tgs"):
            dst = udir / "input.tgs"
            in_type = "tgs"
        elif "webm" in mime or "video" in mime or file_path.endswith(".webm"):
            dst = udir / "input.webm"
            in_type = "sticker_video"
        else:
            dst = udir / "input.tgs"
            in_type = "tgs"
        await _download(bot, file_id, dst)
        s["input"]["type"] = in_type
        s["input"]["file_id"] = file_id
        s["input"]["emoji"] = getattr(st, "emoji", None)
        if s["output"].get("format") == "png":
            s["output"]["format"] = "mp4"
        state.save(uid)
        await render_for_message(message, bot, uid)
        return

    await _accept_sticker(message, bot, st)


def _safe_bg_name(original: str, suffix: str) -> str:
    stem = Path(original).stem if original else "background"
    stem = re.sub(r"[^a-zA-Z0-9_-]+", "_", stem).strip("_")[:40] or "background"
    return f"{stem}_{int(time.time())}{suffix.lower()}"


def _safe_named_bg(title: str, suffix: str) -> str:
    stem = re.sub(r"[^a-zA-Z0-9а-яА-ЯёЁ_-]+", "_", title).strip("_")[:50]
    if not stem:
        stem = "background"
    candidate = f"{stem}{suffix.lower()}"
    i = 2
    while (BACKGROUNDS_DIR / candidate).exists():
        candidate = f"{stem}_{i}{suffix.lower()}"
        i += 1
    return candidate


async def _accept_sticker(message: Message, bot: Bot, st) -> None:
    uid = message.from_user.id
    s = state.get(uid)
    lang = s["lang"]
    state.set_await(uid, None)

    udir = _user_dir(uid)
    for old in udir.glob("input.*"):
        old.unlink(missing_ok=True)

    if st.is_animated:
        dst = udir / "input.tgs"
        in_type = "tgs"
    elif st.is_video:
        dst = udir / "input.webm"
        in_type = "sticker_video"
    else:
        dst = udir / "input.webp"
        in_type = "sticker"

    await _download(bot, st.file_id, dst)
    s["input"]["type"] = in_type
    s["input"]["file_id"] = st.file_id
    s["input"]["emoji"] = getattr(st, "emoji", None)
    sticker_type = str(getattr(st, "type", "")).lower()
    if in_type == "sticker" and "custom_emoji" in sticker_type:
        s["output"]["format"] = "png"
    if in_type in {"tgs", "sticker_video"} and s["output"].get("format") == "png":
        s["output"]["format"] = "mp4"
    state.save(uid)

    await render_for_message(message, bot, uid)


# ─────────────── СТИКЕРЫ ───────────────
@router.message(F.sticker)
async def on_sticker(message: Message, bot: Bot):
    await _accept_sticker(message, bot, message.sticker)


# ─────────────── ФОТО / ВИДЕО / ДОКУМЕНТЫ ───────────────
@router.message(F.photo)
async def on_photo(message: Message, bot: Bot):
    uid = message.from_user.id
    awaiting = state.get_await(uid)
    s = state.get(uid)
    lang = s["lang"]
    udir = _user_dir(uid)
    photo = message.photo[-1]   # самое крупное превью

    if awaiting == "admin_bg" and ADMIN_ID and uid == ADMIN_ID:
        dst = _user_dir(uid) / "admin_bg_pending.jpg"
        await _download(bot, photo.file_id, dst)
        state.set_await(uid, f"admin_bg_name:{dst.name}")
        await message.answer(t(lang, "admin_bg_name_prompt"), parse_mode="HTML",
                             reply_markup=keyboards.back_to_main(lang))
        return

    if awaiting == "bg_image":
        dst = udir / "bg.jpg"
        await _download(bot, photo.file_id, dst)
        s["background"]["mode"] = "image"
        s["background"]["file_id"] = photo.file_id
        state.save(uid)
        state.set_await(uid, None)
        await message.answer(_msg("✅ Фон-изображение принято!" if lang == "ru" else "✅ Background image saved!"), parse_mode="HTML")
        await message.answer(main_menu_text(s, lang), parse_mode="HTML",
                             reply_markup=keyboards.main_menu(lang))
        return

    if awaiting == "wm_image":
        dst = udir / "wm.png"
        await _download(bot, photo.file_id, dst)
        s["watermark"]["source"] = "image"
        s["watermark"]["file_id"] = photo.file_id
        s["watermark"]["enabled"] = True
        state.save(uid)
        state.set_await(uid, None)
        await message.answer(_msg("✅ Водяной знак (изображение) принят!" if lang == "ru" else "✅ Watermark image saved!"), parse_mode="HTML")
        await message.answer(main_menu_text(s, lang), parse_mode="HTML",
                             reply_markup=keyboards.main_menu(lang))
        return

    await message.answer(_msg(
        "ℹ️ Используй меню «🎨 Фон» или «💧 Водяной знак», чтобы загрузить изображение."
        if lang == "ru" else
        "ℹ️ Use the «🎨 Background» or «💧 Watermark» menu to upload an image."
    ), parse_mode="HTML")


@router.message(F.video)
async def on_video(message: Message, bot: Bot):
    uid = message.from_user.id
    awaiting = state.get_await(uid)
    s = state.get(uid)
    lang = s["lang"]
    udir = _user_dir(uid)
    v = message.video
    if v.file_size and v.file_size > MAX_UPLOAD_MB * 1024 * 1024:
        await message.answer(_msg(f"⚠️ Файл больше {MAX_UPLOAD_MB} МБ."), parse_mode="HTML")
        return

    if awaiting == "bg_video":
        dst = udir / "bg.mp4"
        await _download(bot, v.file_id, dst)
        s["background"]["mode"] = "video"
        s["background"]["file_id"] = v.file_id
        state.save(uid)
        state.set_await(uid, None)
        await message.answer(_msg("✅ Фон-видео принято!" if lang == "ru" else "✅ Background video saved!"), parse_mode="HTML")
        await message.answer(main_menu_text(s, lang), parse_mode="HTML",
                             reply_markup=keyboards.main_menu(lang))
        return

    await message.answer(_msg(
        "ℹ️ Используй меню «🎨 Фон» → «🎞 Видео», чтобы установить видео-фон."
        if lang == "ru" else
        "ℹ️ Use «🎨 Background» → «🎞 Video» to set a video background."
    ), parse_mode="HTML")


@router.message(F.document)
async def on_document(message: Message, bot: Bot):
    uid = message.from_user.id
    awaiting = state.get_await(uid)
    s = state.get(uid)
    lang = s["lang"]
    doc = message.document
    name = (doc.file_name or "").lower()

    if awaiting == "admin_bg" and ADMIN_ID and uid == ADMIN_ID:
        suffix = Path(name).suffix.lower()
        if suffix not in {".jpg", ".jpeg", ".png", ".webp"}:
            await message.answer(_msg("⚠️ Отправь JPG, PNG или WEBP."), parse_mode="HTML")
            return
        dst = _user_dir(uid) / f"admin_bg_pending{suffix}"
        await _download(bot, doc.file_id, dst)
        state.set_await(uid, f"admin_bg_name:{dst.name}")
        await message.answer(t(lang, "admin_bg_name_prompt"), parse_mode="HTML",
                             reply_markup=keyboards.back_to_main(lang))
        return

    if awaiting == "wm_font" and (name.endswith(".ttf") or name.endswith(".otf")):
        dst = FONTS_DIR / doc.file_name
        await _download(bot, doc.file_id, dst)
        s["watermark"]["font"] = doc.file_name      # храним имя файла
        state.save(uid)
        state.set_await(uid, None)
        await message.answer(_msg("✅ Шрифт загружен и выбран!" if lang == "ru" else "✅ Font uploaded and selected!"), parse_mode="HTML")
        await message.answer(main_menu_text(s, lang), parse_mode="HTML",
                             reply_markup=keyboards.main_menu(lang))
        return

    # PNG-документ как водяной знак
    if awaiting == "wm_image" and name.endswith(".png"):
        dst = _user_dir(uid) / "wm.png"
        await _download(bot, doc.file_id, dst)
        s["watermark"]["source"] = "image"
        s["watermark"]["file_id"] = doc.file_id
        s["watermark"]["enabled"] = True
        state.save(uid)
        state.set_await(uid, None)
        await message.answer(_msg("✅ PNG-водяной знак принят!" if lang == "ru" else "✅ PNG watermark saved!"), parse_mode="HTML")
        await message.answer(main_menu_text(s, lang), parse_mode="HTML",
                             reply_markup=keyboards.main_menu(lang))
        return

    await message.answer(_msg(
        "ℹ️ Документ не распознан. Используй кнопки меню для загрузки."
        if lang == "ru" else "ℹ️ Document not recognized — use menu buttons."
    ), parse_mode="HTML")


# ─────────────── ТЕКСТ ───────────────
@router.message(F.text)
async def on_text(message: Message, bot: Bot):
    uid = message.from_user.id
    s = state.get(uid)
    lang = s["lang"]
    awaiting = state.get_await(uid)
    text = (message.text or "").strip()

    # 1) ожидаем HEX-цвет фона (слот 1 / 2)
    if awaiting and awaiting.startswith("bg_hex:"):
        slot = awaiting.split(":")[1]
        h = parse_hex(text)
        if not h:
            await message.answer(_msg("⚠️ Некорректный цвет. Пример: `#1E88E5`, `gray` или `серый`"), parse_mode="HTML")
            return
        key = "color" if slot == "1" else "color2"
        s["background"][key] = h
        if slot == "1" and s["background"].get("mode") != "gradient":
            s["background"]["mode"] = "color"
        state.save(uid)
        state.set_await(uid, None)
        await message.answer(_msg(f"✅ Цвет установлен: `{h}`"), parse_mode="HTML")
        await message.answer(main_menu_text(s, lang), parse_mode="HTML",
                             reply_markup=keyboards.main_menu(lang))
        return

    # 2) кастомное разрешение
    if awaiting == "out_res_custom":
        sep = "x" if "x" in text.lower() else "×"
        parts = text.lower().replace("×", "x").split("x")
        if len(parts) != 2 or not all(p.strip().isdigit() for p in parts):
            await message.answer(_msg("⚠️ Формат: `1280x720`"), parse_mode="HTML")
            return
        w, h = int(parts[0]), int(parts[1])
        w = max(64, min(3840, w))
        h = max(64, min(3840, h))
        s["output"]["width"] = w
        s["output"]["height"] = h
        state.save(uid)
        state.set_await(uid, None)
        await message.answer(_msg(f"✅ Разрешение: {w}×{h}"), parse_mode="HTML")
        await message.answer(main_menu_text(s, lang), parse_mode="HTML",
                             reply_markup=keyboards.main_menu(lang))
        return

    # 3) текст водяного знака
    if awaiting == "wm_text":
        s["watermark"]["text"] = text[:120]
        s["watermark"]["source"] = "text"
        s["watermark"]["enabled"] = True
        state.save(uid)
        state.set_await(uid, None)
        await message.answer(_msg("✅ Текст водяного знака установлен."), parse_mode="HTML")
        await message.answer(main_menu_text(s, lang), parse_mode="HTML",
                             reply_markup=keyboards.main_menu(lang))
        return

    # 4) HEX цвета шрифта водяного знака
    if awaiting == "wm_fontcolor_hex":
        h = parse_hex(text)
        if not h:
            await message.answer(_msg("⚠️ Некорректный цвет. Пример: `#FFFFFF`, `white` или `белый`"), parse_mode="HTML")
            return
        s["watermark"]["font_color"] = h
        state.save(uid)
        state.set_await(uid, None)
        await message.answer(_msg(f"✅ Цвет шрифта: `{h}`"), parse_mode="HTML")
        await message.answer(main_menu_text(s, lang), parse_mode="HTML",
                             reply_markup=keyboards.main_menu(lang))
        return

    # 5) HEX цвета эффекта
    if awaiting == "wm_effectcolor_hex":
        h = parse_hex(text)
        if not h:
            await message.answer(_msg("⚠️ Некорректный цвет. Пример: `#000000`, `black` или `черный`"), parse_mode="HTML")
            return
        s["watermark"]["effect_color"] = h
        state.save(uid)
        state.set_await(uid, None)
        await message.answer(_msg(f"✅ Цвет эффекта: `{h}`"), parse_mode="HTML")
        await message.answer(main_menu_text(s, lang), parse_mode="HTML",
                             reply_markup=keyboards.main_menu(lang))
        return

    if awaiting == "input_colorize_hex":
        h = parse_hex(text)
        if not h:
            await message.answer(_msg("⚠️ Некорректный цвет. Пример: `#00AEEF`, `gray` или `серый`"), parse_mode="HTML")
            return
        cfg = s["input"].setdefault("colorize", {})
        cfg.setdefault("strength", 100)
        cfg["color"] = h
        cfg["enabled"] = True
        state.save(uid)
        state.set_await(uid, None)
        await message.answer(_msg(f"✅ Цвет исходника: `{h}`"), parse_mode="HTML")
        await message.answer(main_menu_text(s, lang), parse_mode="HTML",
                             reply_markup=keyboards.main_menu(lang))
        return

    if awaiting and awaiting.startswith("admin_bg_name:") and ADMIN_ID and uid == ADMIN_ID:
        pending_name = awaiting.split(":", 1)[1]
        pending = _user_dir(uid) / pending_name
        if not pending.exists():
            state.set_await(uid, None)
            await message.answer(t(lang, "admin_bg_missing"), parse_mode="HTML")
            return
        final_name = _safe_named_bg(text[:80], pending.suffix)
        final = BACKGROUNDS_DIR / final_name
        pending.replace(final)
        state.set_await(uid, None)
        await message.answer(t(lang, "admin_bg_saved", name=escape(final.stem)), parse_mode="HTML")
        await message.answer(main_menu_text(s, lang), parse_mode="HTML",
                             reply_markup=keyboards.main_menu(lang))
        return

    custom_emoji_ids = [
        ent.custom_emoji_id
        for ent in (message.entities or [])
        if ent.type == "custom_emoji" and ent.custom_emoji_id
    ]
    if custom_emoji_ids and len(text) <= 8:
        stickers = await bot.get_custom_emoji_stickers(custom_emoji_ids=custom_emoji_ids[:1])
        if stickers:
            await _accept_premium_emoji_sticker(message, bot, stickers[0])
            return

    # 6) Эмодзи как исходный контент
    # Считаем сообщение «эмодзи», если в нём 1-2 видимых символа и хотя бы один —
    # это emoji-glyph по библиотеке `emoji`.
    if len(text) <= 8 and emoji_lib.emoji_count(text) >= 1:
        s["input"]["type"] = "emoji"
        s["input"]["emoji"] = text
        s["input"]["file_id"] = None
        s["output"]["format"] = "png"
        state.save(uid)
        await render_for_message(message, bot, uid)
        return

    # 7) Иначе — подсказка
    await message.answer(_msg(
        "ℹ️ Я не понял это сообщение. Используй меню или отправь стикер / эмодзи."
        if lang == "ru" else
        "ℹ️ I didn't get that. Use the menu or send a sticker / emoji."
    ), parse_mode="HTML")
