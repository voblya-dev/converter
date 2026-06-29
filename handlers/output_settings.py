"""
Меню параметров вывода: формат, разрешение, FPS, качество, скорость.
"""
from aiogram import Router, F
from aiogram.types import CallbackQuery

from utils import state, keyboards
from utils.i18n import t
from utils.labels import quality_label
from utils.messages import edit_or_answer

router = Router(name="output")


def _colorize_cfg(s: dict) -> dict:
    cfg = s["input"].setdefault("colorize", {})
    cfg.setdefault("enabled", False)
    cfg.setdefault("auto", False)
    cfg.setdefault("color", "#FFFFFF")
    cfg.setdefault("strength", 100)
    return cfg


def _out_text(s: dict, lang: str) -> str:
    o = s["output"]
    c = _colorize_cfg(s)
    colorize = t(
        lang,
        "input_colorize_auto_on" if c.get("enabled") and c.get("auto")
        else "input_colorize_on" if c.get("enabled") else "input_colorize_off",
        color=c.get("color", "#FFFFFF"),
        strength=c.get("strength", 100),
    )
    return t(lang, "out_menu",
             format=o["format"].upper(),
             w=o["width"], h=o["height"],
             fps=o["fps"],
             quality=quality_label(o["quality"], lang),
             speed=o.get("speed", 1.0),
             input_size=s["input"].get("size_pct", 80),
             colorize=colorize)


async def _show_output_menu(call: CallbackQuery, text: str, markup) -> None:
    await edit_or_answer(call.message, text, parse_mode="HTML", reply_markup=markup)


@router.callback_query(F.data == "out:menu")
async def cb_menu(call: CallbackQuery):
    uid = call.from_user.id
    s = state.get(uid)
    lang = s["lang"]
    state.set_await(uid, None)
    await _show_output_menu(call, _out_text(s, lang), keyboards.out_menu(lang))
    await call.answer()


@router.callback_query(F.data == "out:format")
async def cb_format(call: CallbackQuery):
    uid = call.from_user.id
    s = state.get(uid)
    lang = s["lang"]
    await call.message.edit_text(_out_text(s, lang), parse_mode="HTML",
                                 reply_markup=keyboards.out_formats(lang, s["output"]["format"]))
    await call.answer()


@router.callback_query(F.data.startswith("out:setformat:"))
async def cb_setformat(call: CallbackQuery):
    uid = call.from_user.id
    s = state.get(uid)
    s["output"]["format"] = call.data.split(":")[2]
    state.save(uid)
    await call.answer("✓")
    await call.message.edit_text(_out_text(s, s["lang"]), parse_mode="HTML",
                                 reply_markup=keyboards.out_formats(s["lang"], s["output"]["format"]))


@router.callback_query(F.data == "out:res")
async def cb_res(call: CallbackQuery):
    uid = call.from_user.id
    s = state.get(uid)
    lang = s["lang"]
    await call.message.edit_text(_out_text(s, lang), parse_mode="HTML",
                                 reply_markup=keyboards.out_resolutions(
                                     lang, (s["output"]["width"], s["output"]["height"])))
    await call.answer()


@router.callback_query(F.data.startswith("out:setres:"))
async def cb_setres(call: CallbackQuery):
    uid = call.from_user.id
    s = state.get(uid)
    wh = call.data.split(":")[2]
    w, h = wh.split("x")
    s["output"]["width"]  = int(w)
    s["output"]["height"] = int(h)
    state.save(uid)
    await call.answer(f"✓ {w}×{h}")
    await call.message.edit_text(_out_text(s, s["lang"]), parse_mode="HTML",
                                 reply_markup=keyboards.out_resolutions(
                                     s["lang"], (int(w), int(h))))


@router.callback_query(F.data == "out:resCustom")
async def cb_res_custom(call: CallbackQuery):
    uid = call.from_user.id
    lang = state.lang(uid)
    state.set_await(uid, "out_res_custom")
    await call.message.answer(t(lang, "out_custom_res_prompt"), parse_mode="HTML",
                              reply_markup=keyboards.back_to_main(lang))
    await call.answer()


@router.callback_query(F.data == "out:fps")
async def cb_fps(call: CallbackQuery):
    uid = call.from_user.id
    s = state.get(uid)
    lang = s["lang"]
    await call.message.edit_text(_out_text(s, lang), parse_mode="HTML",
                                 reply_markup=keyboards.out_fps_kb(lang, s["output"]["fps"]))
    await call.answer()


@router.callback_query(F.data.startswith("out:setfps:"))
async def cb_setfps(call: CallbackQuery):
    uid = call.from_user.id
    s = state.get(uid)
    raw = call.data.split(":")[2]
    s["output"]["fps"] = "source" if raw == "source" else int(raw)
    state.save(uid)
    await call.answer(f"✓ {raw} fps")
    await call.message.edit_text(_out_text(s, s["lang"]), parse_mode="HTML",
                                 reply_markup=keyboards.out_fps_kb(s["lang"], s["output"]["fps"]))


@router.callback_query(F.data == "out:quality")
async def cb_quality(call: CallbackQuery):
    uid = call.from_user.id
    s = state.get(uid)
    lang = s["lang"]
    await call.message.edit_text(_out_text(s, lang), parse_mode="HTML",
                                 reply_markup=keyboards.out_quality_kb(lang, s["output"]["quality"]))
    await call.answer()


@router.callback_query(F.data.startswith("out:setquality:"))
async def cb_setquality(call: CallbackQuery):
    uid = call.from_user.id
    s = state.get(uid)
    s["output"]["quality"] = call.data.split(":")[2]
    state.save(uid)
    await call.answer("✓")
    await call.message.edit_text(_out_text(s, s["lang"]), parse_mode="HTML",
                                 reply_markup=keyboards.out_quality_kb(s["lang"], s["output"]["quality"]))


@router.callback_query(F.data == "out:speed")
async def cb_speed(call: CallbackQuery):
    uid = call.from_user.id
    s = state.get(uid)
    lang = s["lang"]
    await call.message.edit_text(_out_text(s, lang), parse_mode="HTML",
                                 reply_markup=keyboards.out_speed_kb(lang, s["output"].get("speed", 1.0)))
    await call.answer()


@router.callback_query(F.data.startswith("out:setspeed:"))
async def cb_setspeed(call: CallbackQuery):
    uid = call.from_user.id
    s = state.get(uid)
    s["output"]["speed"] = float(call.data.split(":")[2])
    state.save(uid)
    await call.answer("✓")
    await call.message.edit_text(_out_text(s, s["lang"]), parse_mode="HTML",
                                 reply_markup=keyboards.out_speed_kb(s["lang"], s["output"]["speed"]))


@router.callback_query(F.data == "out:inputsize")
async def cb_input_size(call: CallbackQuery):
    uid = call.from_user.id
    s = state.get(uid)
    lang = s["lang"]
    await call.message.edit_text(_out_text(s, lang), parse_mode="HTML",
                                 reply_markup=keyboards.input_size_kb(lang, s["input"].get("size_pct", 80)))
    await call.answer()


@router.callback_query(F.data.startswith("out:setinputsize:"))
async def cb_set_input_size(call: CallbackQuery):
    uid = call.from_user.id
    s = state.get(uid)
    s["input"]["size_pct"] = int(call.data.split(":")[2])
    state.save(uid)
    await call.answer(f"{s['input']['size_pct']}%")
    await call.message.edit_text(_out_text(s, s["lang"]), parse_mode="HTML",
                                 reply_markup=keyboards.input_size_kb(s["lang"], s["input"]["size_pct"]))


@router.callback_query(F.data.startswith("out:inputsize:"))
async def cb_step_input_size(call: CallbackQuery):
    uid = call.from_user.id
    s = state.get(uid)
    delta = int(call.data.split(":")[2])
    s["input"]["size_pct"] = max(5, min(100, s["input"].get("size_pct", 80) + delta))
    state.save(uid)
    await call.answer(f"{s['input']['size_pct']}%")
    await call.message.edit_text(_out_text(s, s["lang"]), parse_mode="HTML",
                                 reply_markup=keyboards.input_size_kb(s["lang"], s["input"]["size_pct"]))


@router.callback_query(F.data == "out:colorize")
async def cb_colorize(call: CallbackQuery):
    uid = call.from_user.id
    s = state.get(uid)
    lang = s["lang"]
    await call.message.edit_text(_out_text(s, lang), parse_mode="HTML",
                                 reply_markup=keyboards.input_colorize_kb(
                                     lang, _colorize_cfg(s)))
    await call.answer()


@router.callback_query(F.data == "out:colorize:toggle")
async def cb_colorize_toggle(call: CallbackQuery):
    uid = call.from_user.id
    s = state.get(uid)
    cfg = _colorize_cfg(s)
    cfg["enabled"] = not cfg.get("enabled", False)
    if not cfg["enabled"]:
        cfg["auto"] = False
    state.save(uid)
    await call.answer("✓")
    await call.message.edit_text(_out_text(s, s["lang"]), parse_mode="HTML",
                                 reply_markup=keyboards.input_colorize_kb(s["lang"], cfg))


@router.callback_query(F.data == "out:colorize:auto")
async def cb_colorize_auto(call: CallbackQuery):
    uid = call.from_user.id
    s = state.get(uid)
    cfg = _colorize_cfg(s)
    cfg["auto"] = not cfg.get("auto", False)
    cfg["enabled"] = cfg["auto"] or cfg.get("enabled", False)
    state.save(uid)
    await call.answer("✓")
    await call.message.edit_text(_out_text(s, s["lang"]), parse_mode="HTML",
                                 reply_markup=keyboards.input_colorize_kb(s["lang"], cfg))


@router.callback_query(F.data == "out:colorize:hex")
async def cb_colorize_hex(call: CallbackQuery):
    uid = call.from_user.id
    lang = state.lang(uid)
    state.set_await(uid, "input_colorize_hex")
    await call.message.answer(t(lang, "input_colorize_hex_prompt"), parse_mode="HTML",
                              reply_markup=keyboards.back_to_main(lang))
    await call.answer()


@router.callback_query(F.data.startswith("out:colorize:strength:"))
async def cb_colorize_strength(call: CallbackQuery):
    uid = call.from_user.id
    s = state.get(uid)
    cfg = _colorize_cfg(s)
    cfg["strength"] = int(call.data.split(":")[3])
    cfg["enabled"] = True
    state.save(uid)
    await call.answer("✓")
    await call.message.edit_text(_out_text(s, s["lang"]), parse_mode="HTML",
                                 reply_markup=keyboards.input_colorize_kb(s["lang"], cfg))
