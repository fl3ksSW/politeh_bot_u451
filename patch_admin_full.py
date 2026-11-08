import re

path = "/root/bot_u451/bot.py"
with open(path, "r", encoding="utf-8") as f:
    code = f.read()

# 1. Удаляем старые обработчики cmd_admin
code = re.sub(r'@dp\.message\(Command\("admin"\)\)[\s\S]*?(?=\n@dp|\nasync def|\Z)', '', code)
code = re.sub(r'# ================= АДМИН-ПАНЕЛЬ[\s\S]*?(?=\nasync def main|\Z)', '', code)

# 2. Добавляем новую админку прямо перед async def main()
new_admin_code = '''
# ================= НОВАЯ ИНТЕРАКТИВНАЯ АДМИН-ПАНЕЛЬ =================
def get_admin_menu_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👥 Список группы и подгруппы", callback_data="adm_students_list")],
        [
            InlineKeyboardButton(text="🌙 Тест вечер (22:00)", callback_data="adm_run_test_evening"),
            InlineKeyboardButton(text="🌅 Тест утро (07:30)", callback_data="adm_run_test_morning")
        ],
        [InlineKeyboardButton(text="❌ Закрыть панель", callback_data="adm_close")]
    ])

async def build_students_keyboard():
    users = await get_all_active_users()
    kb = []
    # Сортировка по ФИО
    sorted_users = sorted(users, key=lambda u: u[1] if u[1] else "")
    for uid, name, sub in sorted_users:
        sub_str = f"{sub} п/г" if sub else "? п/г"
        display_name = name if name else f"ID: {uid}"
        kb.append([InlineKeyboardButton(text=f"{display_name} — [{sub_str}]", callback_data=f"adm_edit_{uid}")])
    kb.append([InlineKeyboardButton(text="⬅️ Назад в меню", callback_data="adm_main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

@dp.message(Command("admin"))
async def cmd_admin(msg: Message):
    if msg.from_user.id != ADMIN_ID:
        return
    await msg.answer("👑 <b>Панель администратора У451</b>\nВыберите действие:", reply_markup=get_admin_menu_keyboard(), parse_mode="HTML")

@dp.callback_query(F.data == "adm_main_menu")
async def cb_adm_main_menu(cb: CallbackQuery):
    if cb.from_user.id != ADMIN_ID:
        return
    await cb.message.edit_text("👑 <b>Панель администратора У451</b>\nВыберите действие:", reply_markup=get_admin_menu_keyboard(), parse_mode="HTML")
    await cb.answer()

@dp.callback_query(F.data == "adm_students_list")
async def cb_adm_students_list(cb: CallbackQuery):
    if cb.from_user.id != ADMIN_ID:
        return
    markup = await build_students_keyboard()
    await cb.message.edit_text("👥 <b>Список группы У451</b>\nНажмите на студента, чтобы сменить его подгруппу:", reply_markup=markup, parse_mode="HTML")
    await cb.answer()

@dp.callback_query(F.data.startswith("adm_edit_"))
async def cb_adm_edit_student(cb: CallbackQuery):
    if cb.from_user.id != ADMIN_ID:
        return
    uid = int(cb.data.split("_")[2])
    user = await get_user(uid)
    name = user[0] if user and user[0] else "Без имени"
    curr_sub = user[1] if user and user[1] else 1

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="1-я подгруппа", callback_data=f"adm_set_{uid}_1"),
            InlineKeyboardButton(text="2-я подгруппа", callback_data=f"adm_set_{uid}_2")
        ],
        [InlineKeyboardButton(text="⬅️ Назад к списку", callback_data="adm_students_list")]
    ])
    await cb.message.edit_text(
        f"👤 Студент: <b>{name}</b>\n🆔 Telegram ID: <code>{uid}</code>\nТекущая подгруппа: <b>{curr_sub}-я</b>\n\nВыберите новую подгруппу:",
        reply_markup=kb,
        parse_mode="HTML"
    )
    await cb.answer()

@dp.callback_query(F.data.startswith("adm_set_"))
async def cb_adm_set_subgroup(cb: CallbackQuery):
    if cb.from_user.id != ADMIN_ID:
        return
    _, _, uid_str, new_sub_str = cb.data.split("_")
    uid = int(uid_str)
    new_sub = int(new_sub_str)

    await update_user_subgroup(uid, new_sub)
    user = await get_user(uid)
    name = user[0] if user and user[0] else f"ID: {uid}"

    # Оповещаем студента о смене
    try:
        await bot.send_message(uid, f"ℹ️ Староста изменил твою подгруппу на: <b>{new_sub}-я</b>.", parse_mode="HTML")
    except Exception:
        pass

    await cb.answer(f"{name} переведен в {new_sub}-ю подгруппу!", show_alert=True)
    markup = await build_students_keyboard()
    await cb.message.edit_text("👥 <b>Список группы У451</b>\nНажмите на студента, чтобы сменить его подгруппу:", reply_markup=markup, parse_mode="HTML")

@dp.callback_query(F.data == "adm_run_test_evening")
async def cb_adm_test_evening(cb: CallbackQuery):
    if cb.from_user.id != ADMIN_ID:
        return
    await cb.answer("Формирую вечернее расписание...")
    now = datetime.now(TIMEZONE)
    tomorrow = now + timedelta(days=1)
    week = await get_current_week()
    user = await get_user(cb.from_user.id)
    sub = int(user[1]) if user and user[1] else 2
    name = user[0] if user and user[0] else ""
    greeting = f", {name.split()[0]}" if name else ""
    d_str = tomorrow.strftime("%d.%m")
    sched = format_schedule(tomorrow, week, sub)
    txt = f"🌙 <b>[ТЕСТ] Вечернее расписание на завтра ({d_str}){greeting}:</b>\n\n{sched}\n\nСпокойной ночи и продуктивной подготовки! 😴"
    await cb.message.answer(txt, parse_mode="HTML")

@dp.callback_query(F.data == "adm_run_test_morning")
async def cb_adm_test_morning(cb: CallbackQuery):
    if cb.from_user.id != ADMIN_ID:
        return
    await cb.answer("Формирую утреннюю рассылку...")
    now = datetime.now(TIMEZONE)
    week = await get_current_week()
    weather = await get_makhachkala_weather()
    user = await get_user(cb.from_user.id)
    sub = int(user[1]) if user and user[1] else 2
    name = user[0] if user and user[0] else ""
    greeting = f", {name.split()[0]}" if name else ""
    txt = f"🌅 <b>[ТЕСТ] Доброе утро{greeting}! (07:30)</b>\n\n{weather}\n{format_schedule(now, week, sub)}"
    await cb.message.answer(txt, parse_mode="HTML")

@dp.callback_query(F.data == "adm_close")
async def cb_adm_close(cb: CallbackQuery):
    await cb.message.delete()
'''

code = code.replace("async def main():", new_admin_code.strip() + "\n\nasync def main():")
compile(code, path, "exec")

with open(path, "w", encoding="utf-8") as f:
    f.write(code)

print("Интерактивная админка успешно установлена!")
