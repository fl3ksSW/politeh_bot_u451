import re

path = "/root/bot_u451/bot.py"
with open(path, "r", encoding="utf-8") as f:
    code = f.read()

# Проверяем импорт InlineKeyboardButton / InlineKeyboardMarkup
if "InlineKeyboardMarkup" not in code:
    code = code.replace(
        "from aiogram.types import Message",
        "from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton"
    )

admin_panel_code = '''
# ================= АДМИН-ПАНЕЛЬ: УПРАВЛЕНИЕ ПОДГРУППАМИ =================
async def build_group_list_keyboard():
    users = await get_all_active_users()
    kb = []
    # Сортируем по фамилии/имени
    sorted_users = sorted(users, key=lambda u: u[1] if u[1] else "")
    for uid, name, sub in sorted_users:
        sub_label = f"[{sub} п/г]" if sub else "[? п/г]"
        display_name = name if name else f"ID: {uid}"
        # Кнопка со студентом
        btn_text = f"{display_name} — {sub_label}"
        kb.append([InlineKeyboardButton(text=btn_text, callback_data=f"adm_user_{uid}")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

@dp.message(Command("admin"))
@dp.message(Command("users"))
async def cmd_admin_panel(msg: Message):
    if msg.from_user.id != ADMIN_ID:
        return
    markup = await build_group_list_keyboard()
    txt = (
        "⚙️ <b>Панель управления группой У451</b>\n\n"
        "Нажмите на студента, чтобы быстро изменить его подгруппу:"
    )
    await msg.answer(txt, reply_markup=markup, parse_mode="HTML")

@dp.callback_query(F.data.startswith("adm_user_"))
async def callback_admin_user_select(cb: CallbackQuery):
    if cb.from_user.id != ADMIN_ID:
        await cb.answer("Доступ запрещен.", show_alert=True)
        return
    
    uid = int(cb.data.split("_")[2])
    user = await get_user(uid)
    name = user[0] if user and user[0] else "Без имени"
    curr_sub = user[1] if user and user[1] else 1

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Поставить в 1-ю подгруппу", callback_data=f"setsub_{uid}_1"),
            InlineKeyboardButton(text="Поставить во 2-ю подгруппу", callback_data=f"setsub_{uid}_2")
        ],
        [
            InlineKeyboardButton(text="⬅️ Назад к списку", callback_data="adm_back_list")
        ]
    ])
    
    txt = (
        f"👤 Студент: <b>{name}</b>\n"
        f"🆔 ID: <code>{uid}</code>\n"
        f"Текущая подгруппа: <b>{curr_sub}-я</b>\n\n"
        f"Выберите новую подгруппу:"
    )
    await cb.message.edit_text(txt, reply_markup=kb, parse_mode="HTML")
    await cb.answer()

@dp.callback_query(F.data.startswith("setsub_"))
async def callback_admin_set_subgroup(cb: CallbackQuery):
    if cb.from_user.id != ADMIN_ID:
        await cb.answer("Доступ запрещен.", show_alert=True)
        return
    
    parts = cb.data.split("_")
    uid = int(parts[1])
    new_sub = int(parts[2])

    await update_user_subgroup(uid, new_sub)
    user = await get_user(uid)
    name = user[0] if user and user[0] else f"ID: {uid}"

    # Оповещаем студента об изменении подгруппы
    try:
        await bot.send_message(
            uid,
            f"ℹ️ Староста обновил твою подгруппу на: <b>{new_sub}-я подгруппа</b>.",
            parse_mode="HTML"
        )
    except Exception:
        pass

    await cb.answer(f"{name} переведен в {new_sub}-ю подгруппу!", show_alert=True)
    
    # Возвращаем обновленный список
    markup = await build_group_list_keyboard()
    txt = (
        "⚙️ <b>Панель управления группой У451</b>\n\n"
        "Нажмите на студента, чтобы быстро изменить его подгруппу:"
    )
    await cb.message.edit_text(txt, reply_markup=markup, parse_mode="HTML")

@dp.callback_query(F.data == "adm_back_list")
async def callback_admin_back(cb: CallbackQuery):
    if cb.from_user.id != ADMIN_ID:
        return
    markup = await build_group_list_keyboard()
    txt = (
        "⚙️ <b>Панель управления группой У451</b>\n\n"
        "Нажмите на студента, чтобы быстро изменить его подгруппу:"
    )
    await cb.message.edit_text(txt, reply_markup=markup, parse_mode="HTML")
    await cb.answer()
'''

# Вставляем блок перед main()
if "build_group_list_keyboard" not in code:
    code = code.replace("async def main():", admin_panel_code.strip() + "\n\nasync def main():")

compile(code, path, "exec")

with open(path, "w", encoding="utf-8") as f:
    f.write(code)

print("Панель администратора успешно добавлена в bot.py!")
