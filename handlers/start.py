"""Команда /start, главное меню, кнопки reset/home."""
from html import escape

from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery

from config import ADMIN_ID, BACKGROUNDS_DIR
from utils import state, keyboards
from utils.health import health_report
from utils.i18n import t
from utils.labels import quality_label
from utils.premium_emoji import premiumize_text

router = Router(name="start")


def _input_info(s: dict, lang: str) -> str:
    it = s["input"].get("type")
    if not it:
        return t(lang, "preview_input_none")
    if it == "tgs":
        return t(lang, "preview_input_tgs")
    if it == "sticker":
        return t(lang, "preview_input_sticker")
    if it == "sticker_video":
        return t(lang, "preview_input_sticker_video")
    if it == "emoji":
        return t(lang, "preview_input_emoji", emoji=escape(s["input"].get("emoji", "")))
    return escape(str(it))


def _bg_info(s: dict, lang: str) -> str:
    bg = s["background"]
    if bg.get("auto_palette"):
        return t(lang, "preview_bg_auto_palette")
    m = bg["mode"]
    if m == "color":
        return t(lang, "preview_bg_color", color=bg["color"])
    if m == "gradient":
        return t(lang, "preview_bg_gradient",
                 c1=bg["color"], c2=bg["color2"], direction=bg["direction"])
    if m == "image":
        return t(lang, "preview_bg_image")
    if m == "video":
        return t(lang, "preview_bg_video")
    if m == "global_image":
        return t(lang, "preview_bg_global")
    return m


def _wm_info(s: dict, lang: str) -> str:
    wm = s["watermark"]
    if not wm.get("enabled"):
        return t(lang, "preview_wm_off")
    return t(lang, "preview_wm_on", source=wm["source"])


def main_menu_text(s: dict, lang: str) -> str:
    return t(lang, "main_menu",
             input_info=_input_info(s, lang),
             bg_info=_bg_info(s, lang),
             fmt=s["output"]["format"].upper(),
             w=s["output"]["width"],
             h=s["output"]["height"],
             fps=s["output"]["fps"],
             quality=quality_label(s["output"]["quality"], lang),
             wm_info=_wm_info(s, lang))


def start_text(s: dict, lang: str) -> str:
    return f"{t(lang, 'welcome')}\n\n{main_menu_text(s, lang)}"


@router.message(CommandStart())
async def cmd_start(message: Message):
    uid = message.from_user.id
    s = state.get(uid)
    lang = s["lang"]
    state.set_await(uid, None)
    await message.answer(
        start_text(s, lang),
        parse_mode="HTML",
        reply_markup=keyboards.main_menu(lang),
    )


@router.message(Command("menu"))
async def cmd_menu(message: Message):
    uid = message.from_user.id
    s = state.get(uid)
    lang = s["lang"]
    state.set_await(uid, None)
    await message.answer(
        main_menu_text(s, lang),
        parse_mode="HTML",
        reply_markup=keyboards.main_menu(lang),
    )


@router.message(Command("help"))
async def cmd_help(message: Message):
    uid = message.from_user.id
    s = state.get(uid)
    lang = s["lang"]
    await message.answer(premiumize_text(t(lang, "help_text")), parse_mode="HTML")


@router.message(Command("admin"))
async def cmd_admin(message: Message):
    uid = message.from_user.id
    s = state.get(uid)
    lang = s["lang"]
    if not ADMIN_ID or uid != ADMIN_ID:
        await message.answer(t(lang, "admin_denied"), parse_mode="HTML")
        return
    state.set_await(uid, None)
    count = len([
        p for p in BACKGROUNDS_DIR.iterdir()
        if p.is_file() and p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}
    ])
    await message.answer(
        t(lang, "admin_menu", count=count), parse_mode="HTML",
        reply_markup=keyboards.admin_menu(lang),
    )


@router.message(Command("health"))
async def cmd_health(message: Message):
    uid = message.from_user.id
    lang = state.lang(uid)
    if not ADMIN_ID or uid != ADMIN_ID:
        await message.answer(t(lang, "admin_denied"), parse_mode="HTML")
        return
    report = health_report()
    body = "\n".join(f"{escape(k)}: <code>{escape(v)}</code>" for k, v in report.items())
    await message.answer(f"🩺 <b>Healthcheck</b>\n\n{body}", parse_mode="HTML")


@router.callback_query(F.data == "admin:add_bg")
async def cb_admin_add_bg(call: CallbackQuery):
    uid = call.from_user.id
    lang = state.lang(uid)
    if not ADMIN_ID or uid != ADMIN_ID:
        await call.answer(t(lang, "admin_denied", plain=True), show_alert=True)
        return
    state.set_await(uid, "admin_bg")
    await call.message.answer(
        t(lang, "admin_bg_prompt"), parse_mode="HTML",
        reply_markup=keyboards.back_to_main(lang),
    )
    await call.answer()


@router.callback_query(F.data == "admin:list_bg")
async def cb_admin_list_bg(call: CallbackQuery):
    uid = call.from_user.id
    lang = state.lang(uid)
    if not ADMIN_ID or uid != ADMIN_ID:
        await call.answer(t(lang, "admin_denied", plain=True), show_alert=True)
        return
    files = [
        p.name for p in sorted(BACKGROUNDS_DIR.iterdir())
        if p.is_file() and p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}
    ]
    body = "\n".join(f"• <code>{escape(name)}</code>" for name in files) or t(lang, "admin_bg_empty")
    await call.message.edit_text(
        t(lang, "admin_bg_list", list=body), parse_mode="HTML",
        reply_markup=keyboards.admin_menu(lang),
    )
    await call.answer()


@router.callback_query(F.data == "main:home")
async def cb_home(call: CallbackQuery):
    uid = call.from_user.id
    s = state.get(uid)
    lang = s["lang"]
    state.set_await(uid, None)
    try:
        await call.message.edit_text(
            main_menu_text(s, lang),
            parse_mode="HTML",
            reply_markup=keyboards.main_menu(lang),
        )
    except Exception:
        await call.message.answer(
            main_menu_text(s, lang),
            parse_mode="HTML",
            reply_markup=keyboards.main_menu(lang),
        )
    await call.answer()


@router.callback_query(F.data == "main:reset")
async def cb_reset(call: CallbackQuery):
    uid = call.from_user.id
    s = state.reset(uid)
    lang = s["lang"]
    await call.answer(t(lang, "settings_reset", plain=True))
    await call.message.edit_text(
        main_menu_text(s, lang),
        parse_mode="HTML",
        reply_markup=keyboards.main_menu(lang),
    )


@router.callback_query(F.data == "noop")
async def cb_noop(call: CallbackQuery):
    await call.answer()
