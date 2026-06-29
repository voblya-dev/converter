"""
Меню фона: режим, цвет(а), направление градиента, загрузка изображения/видео.
"""
from aiogram import Router, F
from aiogram.types import CallbackQuery

from config import BACKGROUNDS_DIR, MAX_UPLOAD_MB
from utils import state, keyboards
from utils.i18n import t
from utils.messages import edit_or_answer
from handlers.start import main_menu_text

router = Router(name="background")


def _global_background_files() -> list[str]:
    return [
        p.name for p in sorted(BACKGROUNDS_DIR.iterdir())
        if p.is_file() and p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}
    ][:30]


def _bg_text(s: dict, lang: str) -> str:
    bg = s["background"]
    return t(lang, "bg_menu",
             mode=bg["mode"], color=bg["color"],
             color2=bg["color2"], direction=bg["direction"])


@router.callback_query(F.data == "bg:menu")
async def cb_menu(call: CallbackQuery):
    uid = call.from_user.id
    s = state.get(uid)
    lang = s["lang"]
    state.set_await(uid, None)
    await edit_or_answer(
        call.message,
        _bg_text(s, lang), parse_mode="HTML",
        reply_markup=keyboards.bg_menu(lang, s["background"]["mode"]),
    )
    await call.answer()


@router.callback_query(F.data.startswith("bg:mode:"))
async def cb_mode(call: CallbackQuery):
    uid = call.from_user.id
    s = state.get(uid)
    lang = s["lang"]
    mode = call.data.split(":")[2]
    s["background"]["mode"] = mode
    state.save(uid)

    if mode == "color":
        state.set_await(uid, "bg_hex:1")
        await edit_or_answer(
            call.message,
            t(lang, "bg_hex_prompt"), parse_mode="HTML",
            reply_markup=keyboards.hex_color_kb(lang, slot=1),
        )
    elif mode == "gradient":
        await edit_or_answer(
            call.message,
            _bg_text(s, lang), parse_mode="HTML",
            reply_markup=keyboards.gradient_menu(lang, s["background"]["direction"]),
        )
    elif mode == "image":
        state.set_await(uid, "bg_image")
        await edit_or_answer(
            call.message,
            t(lang, "bg_send_image"), parse_mode="HTML",
            reply_markup=keyboards.back_to_main(lang),
        )
    elif mode == "video":
        state.set_await(uid, "bg_video")
        await edit_or_answer(
            call.message,
            t(lang, "bg_send_video", max_mb=MAX_UPLOAD_MB), parse_mode="HTML",
            reply_markup=keyboards.back_to_main(lang),
        )
    await call.answer()


@router.callback_query(F.data == "bg:global")
async def cb_global(call: CallbackQuery):
    uid = call.from_user.id
    s = state.get(uid)
    lang = s["lang"]
    await edit_or_answer(
        call.message,
        t(lang, "bg_global_title"), parse_mode="HTML",
        reply_markup=keyboards.global_backgrounds_kb(lang, s["background"].get("global_file")),
    )
    await call.answer()


@router.callback_query(F.data == "bg:styles")
async def cb_styles(call: CallbackQuery):
    uid = call.from_user.id
    lang = state.lang(uid)
    await edit_or_answer(
        call.message,
        t(lang, "bg_styles_title"), parse_mode="HTML",
        reply_markup=keyboards.bg_styles_kb(lang),
    )
    await call.answer()


@router.callback_query(F.data.startswith("bg:style:"))
async def cb_style_set(call: CallbackQuery):
    uid = call.from_user.id
    s = state.get(uid)
    lang = s["lang"]
    style = call.data.split(":")[2]
    if style == "auto_palette":
        s["background"]["mode"] = "auto_palette"
        state.save(uid)
        await call.answer(t(lang, "bg_auto_palette_enabled", plain=True))
        await edit_or_answer(
            call.message,
            _bg_text(s, lang), parse_mode="HTML",
            reply_markup=keyboards.bg_menu(lang, s["background"]["mode"]),
        )
        return
    presets = {
        "neon": {"mode": "gradient", "color": "#00E5FF", "color2": "#FF2BD6", "direction": "diagonal"},
        "clean_white": {"mode": "gradient", "color": "#FFFFFF", "color2": "#E8EEF7", "direction": "vertical"},
        "dark_glass": {"mode": "gradient", "color": "#05070D", "color2": "#243041", "direction": "diagonal"},
        "telegram_blue": {"mode": "gradient", "color": "#229ED9", "color2": "#0B5CAD", "direction": "vertical"},
        "story": {"mode": "gradient", "color": "#FF6A3D", "color2": "#7C3AED", "direction": "diagonal"},
    }
    s["background"].update(presets.get(style, presets["telegram_blue"]))
    state.save(uid)
    await call.answer(t(lang, "bg_style_applied", plain=True))
    await edit_or_answer(
        call.message,
        _bg_text(s, lang), parse_mode="HTML",
        reply_markup=keyboards.bg_menu(lang, s["background"]["mode"]),
    )


@router.callback_query(F.data.startswith("bg:setglobal:"))
async def cb_setglobal(call: CallbackQuery):
    uid = call.from_user.id
    s = state.get(uid)
    lang = s["lang"]
    raw = call.data.split(":", 2)[2]
    files = _global_background_files()
    if not raw.isdigit() or int(raw) >= len(files):
        await call.answer(t(lang, "bg_global_missing", plain=True), show_alert=True)
        return
    name = files[int(raw)]
    s["background"]["mode"] = "global_image"
    s["background"]["global_file"] = name
    state.save(uid)
    await call.answer("✓")
    await edit_or_answer(
        call.message,
        _bg_text(s, lang), parse_mode="HTML",
        reply_markup=keyboards.bg_menu(lang, s["background"]["mode"]),
    )


@router.callback_query(F.data.startswith("bg:hex:"))
async def cb_hex(call: CallbackQuery):
    uid = call.from_user.id
    lang = state.lang(uid)
    slot = call.data.split(":")[2]
    state.set_await(uid, f"bg_hex:{slot}")
    await call.message.answer(t(lang, "bg_hex_prompt"), parse_mode="HTML",
                              reply_markup=keyboards.back_to_main(lang))
    await call.answer()


@router.callback_query(F.data.startswith("bg:pick:"))
async def cb_pick(call: CallbackQuery):
    uid = call.from_user.id
    lang = state.lang(uid)
    slot = int(call.data.split(":")[2])
    state.set_await(uid, f"bg_hex:{slot}")
    await edit_or_answer(
        call.message,
        t(lang, "bg_hex_prompt"), parse_mode="HTML",
        reply_markup=keyboards.hex_color_kb(lang, slot=slot),
    )
    await call.answer()


@router.callback_query(F.data.startswith("bg:dir:"))
async def cb_dir(call: CallbackQuery):
    uid = call.from_user.id
    s = state.get(uid)
    lang = s["lang"]
    s["background"]["direction"] = call.data.split(":")[2]
    state.save(uid)
    await edit_or_answer(
        call.message,
        _bg_text(s, lang), parse_mode="HTML",
        reply_markup=keyboards.gradient_menu(lang, s["background"]["direction"]),
    )
    await call.answer()
