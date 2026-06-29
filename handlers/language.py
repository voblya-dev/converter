"""
Переключатель языка RU ↔ EN.
"""
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.types import CallbackQuery

from utils import state, keyboards
from utils.i18n import t
from handlers.start import main_menu_text

router = Router(name="language")


@router.message(Command("lang"))
async def cmd_lang(message: Message):
    uid = message.from_user.id
    s = state.get(uid)
    new_lang = "en" if s["lang"] == "ru" else "ru"
    state.update(uid, lang=new_lang)
    s = state.get(uid)
    await message.answer(
        t(new_lang, "lang_switched"),
        parse_mode="HTML",
        reply_markup=keyboards.main_menu(new_lang),
    )


@router.callback_query(F.data == "lang:toggle")
async def cb_toggle(call: CallbackQuery):
    uid = call.from_user.id
    s = state.get(uid)
    new_lang = "en" if s["lang"] == "ru" else "ru"
    state.update(uid, lang=new_lang)
    s = state.get(uid)
    await call.answer(t(new_lang, "lang_switched", plain=True))
    await call.message.edit_text(
        main_menu_text(s, new_lang),
        parse_mode="HTML",
        reply_markup=keyboards.main_menu(new_lang),
    )
