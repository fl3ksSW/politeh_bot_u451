from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from datetime import datetime, timedelta

admin_router = Router()

def get_admin_menu_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👥 Список группы и подгруппы", callback_data="adm_students_list")],
        [InlineKeyboardButton(text="📋 Полный список текстом", callback_data="adm_export_text")],
        [
            InlineKeyboardButton(text="🌙 Тест вечер (22:00)", callback_data="adm_run_test_evening"),
            InlineKeyboardButton(text="🌅 Тест утро (07:30)", callback_data="adm_run_test_morning")
        ],
        [InlineKeyboardButton(text="❌ Закрыть", callback_data="adm_close")]
    ])

async def build_students_keyboard(get_all_active_users):
    users = await get_all_active_users()
    kb = []
    sorted_users = sorted(users, key=lambda u: u[1] if u[1] else "")
    for uid, name, sub in sorted_users:
        sub_str = str(sub) + " п/г" if sub else "? п/г"
        display_name = name if name else ("ID: " + str(uid))
        btn_text = display_name + " — [" + sub_str + "]"
        kb.append([InlineKeyboardButton(text=btn_text, callback_data="adm_edit_" + str(uid))])
    kb.append([InlineKeyboardButton(text="⬅️ Назад в меню", callback_data="adm_main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=kb)
