"""
Расширенное меню водяного знака:
  * вкл/выкл, источник (текст/картинка/пресет)
  * визуальное позиционирование (стрелки + 3×3 сетка)
  * прозрачность, размер, поворот, эффекты
  * выбор шрифта (+ загрузка пользовательского)
"""
from aiogram import Router, F
from aiogram.types import CallbackQuery

from utils import state, keyboards
from utils.i18n import t
from utils.canvas_grid import label
from utils.premium_emoji import premiumize_text
from config import WM_OFFSET_STEP

router = Router(name="watermark")


def _eff_str(wm: dict, lang: str) -> str:
    parts = []
    if wm.get("shadow"):
        parts.append("тень" if lang == "ru" else "shadow")
    if wm.get("stroke"):
        parts.append("обводка" if lang == "ru" else "stroke")
    if wm.get("glow"):
        parts.append("свечение" if lang == "ru" else "glow")
    if not parts:
        return "—"
    return ", ".join(parts) + f" (r={wm['effect_radius']}, {wm['effect_color']})"


def _wm_text(s: dict, lang: str) -> str:
    wm = s["watermark"]
    status = ("✅ включён" if lang == "ru" else "✅ enabled") if wm["enabled"] else \
             ("❌ выключен" if lang == "ru" else "❌ disabled")
    return t(lang, "wm_menu",
             status=status, source=wm["source"],
             anchor=label(wm["anchor"], lang),
             ox=wm["offset_x"], oy=wm["offset_y"],
             alpha=wm["alpha"], size=wm["size_pct"],
             rot=wm["rotation"], effects=_eff_str(wm, lang),
             grid="")


@router.callback_query(F.data == "wm:menu")
async def cb_menu(call: CallbackQuery):
    uid = call.from_user.id
    s = state.get(uid)
    lang = s["lang"]
    state.set_await(uid, None)
    await call.message.edit_text(_wm_text(s, lang), parse_mode="HTML",
                                 reply_markup=keyboards.wm_menu(lang, s["watermark"]["enabled"]))
    await call.answer()


@router.callback_query(F.data == "wm:toggle")
async def cb_toggle(call: CallbackQuery):
    uid = call.from_user.id
    s = state.get(uid)
    s["watermark"]["enabled"] = not s["watermark"]["enabled"]
    state.save(uid)
    await call.answer("✓")
    await call.message.edit_text(_wm_text(s, s["lang"]), parse_mode="HTML",
                                 reply_markup=keyboards.wm_menu(s["lang"], s["watermark"]["enabled"]))


@router.callback_query(F.data == "wm:source")
async def cb_source(call: CallbackQuery):
    uid = call.from_user.id
    s = state.get(uid)
    lang = s["lang"]
    await call.message.edit_text(_wm_text(s, lang), parse_mode="HTML",
                                 reply_markup=keyboards.wm_source_kb(lang, s["watermark"]["source"]))
    await call.answer()


@router.callback_query(F.data.startswith("wm:setsource:"))
async def cb_setsource(call: CallbackQuery):
    uid = call.from_user.id
    s = state.get(uid)
    s["watermark"]["source"] = call.data.split(":")[2]
    state.save(uid)
    await call.answer("✓")
    await call.message.edit_text(_wm_text(s, s["lang"]), parse_mode="HTML",
                                 reply_markup=keyboards.wm_source_kb(s["lang"], s["watermark"]["source"]))


@router.callback_query(F.data == "wm:upload")
async def cb_upload(call: CallbackQuery):
    uid = call.from_user.id
    s = state.get(uid)
    lang = s["lang"]
    src = s["watermark"]["source"]
    if src == "text":
        state.set_await(uid, "wm_text")
        await call.message.answer(t(lang, "wm_text_prompt"), parse_mode="HTML",
                                  reply_markup=keyboards.back_to_main(lang))
    elif src == "image":
        state.set_await(uid, "wm_image")
        await call.message.answer(t(lang, "wm_image_prompt"), parse_mode="HTML",
                                  reply_markup=keyboards.back_to_main(lang))
    else:
        await call.message.answer("Пресеты подключаются по умолчанию (см. assets/presets/)."
                                  if lang == "ru" else
                                  "Presets are loaded from assets/presets/.")
    await call.answer()


# ─── Позиционирование ───
@router.callback_query(F.data == "wm:position")
async def cb_position(call: CallbackQuery):
    uid = call.from_user.id
    s = state.get(uid)
    lang = s["lang"]
    wm = s["watermark"]
    txt = t(lang, "wm_pos_title")
    await call.message.edit_text(txt, parse_mode="HTML",
                                 reply_markup=keyboards.wm_position_kb(lang, wm["anchor"]))
    await call.answer()


@router.callback_query(F.data.startswith("pos:anchor:"))
async def cb_pos_anchor(call: CallbackQuery):
    uid = call.from_user.id
    s = state.get(uid)
    s["watermark"]["anchor"] = call.data.split(":")[2]
    state.save(uid)
    await call.answer("✓")
    await cb_position(call)  # перерисовать


@router.callback_query(F.data.startswith("pos:nudge:"))
async def cb_pos_nudge(call: CallbackQuery):
    uid = call.from_user.id
    s = state.get(uid)
    direction = call.data.split(":")[2]
    dx = {"left": -WM_OFFSET_STEP, "right": +WM_OFFSET_STEP}.get(direction, 0)
    dy = {"up":   -WM_OFFSET_STEP, "down":  +WM_OFFSET_STEP}.get(direction, 0)
    s["watermark"]["offset_x"] += dx
    s["watermark"]["offset_y"] += dy
    state.save(uid)
    await call.answer(f"X={s['watermark']['offset_x']}, Y={s['watermark']['offset_y']}")
    await cb_position(call)


@router.callback_query(F.data == "pos:reset")
async def cb_pos_reset(call: CallbackQuery):
    uid = call.from_user.id
    s = state.get(uid)
    s["watermark"]["offset_x"] = 0
    s["watermark"]["offset_y"] = 0
    state.save(uid)
    await call.answer("✓")
    await cb_position(call)


# ─── Прозрачность ───
@router.callback_query(F.data == "wm:alpha")
async def cb_alpha(call: CallbackQuery):
    uid = call.from_user.id
    s = state.get(uid)
    lang = s["lang"]
    await call.message.edit_text(_wm_text(s, lang), parse_mode="HTML",
                                 reply_markup=keyboards.wm_alpha_kb(lang, s["watermark"]["alpha"]))
    await call.answer()


@router.callback_query(F.data.startswith("wm:alpha:"))
async def cb_alpha_step(call: CallbackQuery):
    uid = call.from_user.id
    s = state.get(uid)
    raw = call.data.split(":")[2]
    delta = int(raw)
    s["watermark"]["alpha"] = max(0, min(100, s["watermark"]["alpha"] + delta))
    state.save(uid)
    await call.answer(f"α={s['watermark']['alpha']}%")
    await call.message.edit_text(_wm_text(s, s["lang"]), parse_mode="HTML",
                                 reply_markup=keyboards.wm_alpha_kb(s["lang"], s["watermark"]["alpha"]))


# ─── Размер ───
@router.callback_query(F.data == "wm:size")
async def cb_size(call: CallbackQuery):
    uid = call.from_user.id
    s = state.get(uid)
    lang = s["lang"]
    await call.message.edit_text(_wm_text(s, lang), parse_mode="HTML",
                                 reply_markup=keyboards.wm_size_kb(lang, s["watermark"]["size_pct"]))
    await call.answer()


@router.callback_query(F.data.startswith("wm:size:"))
async def cb_size_step(call: CallbackQuery):
    uid = call.from_user.id
    s = state.get(uid)
    delta = int(call.data.split(":")[2])
    s["watermark"]["size_pct"] = max(2, min(100, s["watermark"]["size_pct"] + delta))
    state.save(uid)
    await call.answer(f"{s['watermark']['size_pct']}%")
    await call.message.edit_text(_wm_text(s, s["lang"]), parse_mode="HTML",
                                 reply_markup=keyboards.wm_size_kb(s["lang"], s["watermark"]["size_pct"]))


# ─── Поворот ───
@router.callback_query(F.data == "wm:rotation")
async def cb_rot(call: CallbackQuery):
    uid = call.from_user.id
    s = state.get(uid)
    lang = s["lang"]
    await call.message.edit_text(_wm_text(s, lang), parse_mode="HTML",
                                 reply_markup=keyboards.wm_rotation_kb(lang, s["watermark"]["rotation"]))
    await call.answer()


@router.callback_query(F.data.startswith("wm:setrot:"))
async def cb_setrot(call: CallbackQuery):
    uid = call.from_user.id
    s = state.get(uid)
    s["watermark"]["rotation"] = int(call.data.split(":")[2])
    state.save(uid)
    await call.answer(f"{s['watermark']['rotation']}°")
    await call.message.edit_text(_wm_text(s, s["lang"]), parse_mode="HTML",
                                 reply_markup=keyboards.wm_rotation_kb(s["lang"], s["watermark"]["rotation"]))


# ─── Шрифт ───
@router.callback_query(F.data == "wm:font")
async def cb_font(call: CallbackQuery):
    uid = call.from_user.id
    s = state.get(uid)
    lang = s["lang"]
    await call.message.edit_text(_wm_text(s, lang), parse_mode="HTML",
                                 reply_markup=keyboards.wm_font_kb(lang, s["watermark"]["font"]))
    await call.answer()


@router.callback_query(F.data.startswith("wm:setfont:"))
async def cb_setfont(call: CallbackQuery):
    uid = call.from_user.id
    s = state.get(uid)
    s["watermark"]["font"] = call.data.split(":", 2)[2]
    state.save(uid)
    await call.answer("✓")
    await call.message.edit_text(_wm_text(s, s["lang"]), parse_mode="HTML",
                                 reply_markup=keyboards.wm_font_kb(s["lang"], s["watermark"]["font"]))


@router.callback_query(F.data == "wm:fontupload")
async def cb_fontupload(call: CallbackQuery):
    uid = call.from_user.id
    lang = state.lang(uid)
    state.set_await(uid, "wm_font")
    await call.message.answer(
        premiumize_text("📁 Отправь .TTF или .OTF файл как документ.")
        if lang == "ru" else
        premiumize_text("📁 Send a .TTF or .OTF file as a document."),
        parse_mode="HTML",
        reply_markup=keyboards.back_to_main(lang),
    )
    await call.answer()


# ─── Цвет шрифта ───
@router.callback_query(F.data == "wm:fontcolor")
async def cb_fontcolor(call: CallbackQuery):
    uid = call.from_user.id
    s = state.get(uid)
    lang = s["lang"]
    await call.message.edit_text(_wm_text(s, lang), parse_mode="HTML",
                                 reply_markup=keyboards.wm_font_color_kb(lang))
    await call.answer()


@router.callback_query(F.data.startswith("wm:setfontcolor:"))
async def cb_setfontcolor(call: CallbackQuery):
    uid = call.from_user.id
    s = state.get(uid)
    s["watermark"]["font_color"] = call.data.split(":")[2]
    state.save(uid)
    await call.answer("✓")
    await call.message.edit_text(_wm_text(s, s["lang"]), parse_mode="HTML",
                                 reply_markup=keyboards.wm_menu(s["lang"], s["watermark"]["enabled"]))


@router.callback_query(F.data == "wm:fontcolorHex")
async def cb_fontcolor_hex(call: CallbackQuery):
    uid = call.from_user.id
    lang = state.lang(uid)
    state.set_await(uid, "wm_fontcolor_hex")
    await call.message.answer(t(lang, "bg_hex_prompt"), parse_mode="HTML",
                              reply_markup=keyboards.back_to_main(lang))
    await call.answer()


# ─── Эффекты ───
@router.callback_query(F.data == "wm:effects")
async def cb_effects(call: CallbackQuery):
    uid = call.from_user.id
    s = state.get(uid)
    lang = s["lang"]
    await call.message.edit_text(_wm_text(s, lang), parse_mode="HTML",
                                 reply_markup=keyboards.wm_effects_kb(lang, s["watermark"]))
    await call.answer()


@router.callback_query(F.data.startswith("wm:effect:"))
async def cb_effect_toggle(call: CallbackQuery):
    uid = call.from_user.id
    s = state.get(uid)
    key = call.data.split(":")[2]
    s["watermark"][key] = not s["watermark"].get(key, False)
    state.save(uid)
    await call.answer("✓")
    await call.message.edit_text(_wm_text(s, s["lang"]), parse_mode="HTML",
                                 reply_markup=keyboards.wm_effects_kb(s["lang"], s["watermark"]))


@router.callback_query(F.data.startswith("wm:radius:"))
async def cb_radius(call: CallbackQuery):
    uid = call.from_user.id
    s = state.get(uid)
    delta = int(call.data.split(":")[2])
    s["watermark"]["effect_radius"] = max(0, min(30, s["watermark"]["effect_radius"] + delta))
    state.save(uid)
    await call.answer(f"r={s['watermark']['effect_radius']}")
    await call.message.edit_text(_wm_text(s, s["lang"]), parse_mode="HTML",
                                 reply_markup=keyboards.wm_effects_kb(s["lang"], s["watermark"]))


@router.callback_query(F.data == "wm:effectcolor")
async def cb_effectcolor(call: CallbackQuery):
    uid = call.from_user.id
    lang = state.lang(uid)
    state.set_await(uid, "wm_effectcolor_hex")
    await call.message.answer(t(lang, "bg_hex_prompt"), parse_mode="HTML",
                              reply_markup=keyboards.back_to_main(lang))
    await call.answer()
