import asyncio
import json
import os
from datetime import datetime, timedelta
import pytz
from dotenv import load_dotenv
import aiohttp
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from db import (
    init_db, ensure_user_started, get_user, save_user, update_user_name, update_user_subgroup,
    get_all_active_users, get_all_users_raw, get_user_stats, get_current_week, set_current_week,
    add_material, get_material, update_material_status, get_approved_materials, get_stats
)

load_dotenv("/root/bot_u451/.env")

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "1298779741"))
TIMEZONE = pytz.timezone("Europe/Moscow")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
scheduler = AsyncIOScheduler(timezone=TIMEZONE)

class AdminRenameState(StatesGroup):
    waiting_for_new_name = State()

class RegistrationState(StatesGroup):
    waiting_for_full_name = State()
    waiting_for_subgroup = State()

class ChangeNameState(StatesGroup):
    waiting_for_new_name = State()

class UploadMaterialState(StatesGroup):
    waiting_for_file = State()
    waiting_for_subject = State()
    waiting_for_title = State()

SUBJECTS_LIST = [
    "Основы IT-технологий", "Экономическая безопасность", "Основы рад",
    "Математическая логика и ТА", "Физкультура", "Электроника",
    "Философия", "БОС", "Экономика", "Другое"
]

MONTHS_RU = {
    1: "января", 2: "февраля", 3: "марта", 4: "апреля", 5: "мая", 6: "июня",
    7: "июля", 8: "августа", 9: "сентября", 10: "октября", 11: "ноября", 12: "декабря"
}
DAYS_RU = {
    1: "Понедельник", 2: "Вторник", 3: "Среда", 4: "Четверг",
    5: "Пятница", 6: "Суббота", 7: "Воскресенье"
}

def parse_wmo_code(c: int) -> str:
    codes = {0: "Ясно ☀️", 1: "В основном ясно 🌤", 2: "Переменная облачность ⛅", 3: "Пасмурно ☁️",
             45: "Туман 🌫", 51: "Морось 🌦", 61: "Дождь 🌧", 71: "Снег 🌨", 95: "Гроза ⚡"}
    return codes.get(c, "Облачно")

async def get_makhachkala_weather():
    url = "https://api.open-meteo.com/v1/forecast?latitude=42.98&longitude=47.50&current=temperature_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m&timezone=Europe%2FMoscow"
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(url, timeout=5) as r:
                if r.status == 200:
                    d = (await r.json()).get("current", {})
                    cond = parse_wmo_code(d.get("weather_code", 0))
                    return f"🌤 <b>Погода в Махачкале:</b>\n{cond}\n🌡 <b>{d.get('temperature_2m')}°C</b> (ощущается {d.get('apparent_temperature')}°C) | Ветер: {d.get('wind_speed_10m')} км/ч\n"
    except Exception:
        pass
    return "Сводка погоды временно недоступна.\n"

def format_schedule(target_date: datetime, week_type: str, user_subgroup: int):
    day_num = target_date.isoweekday()
    date_header = f"📅 <b>{DAYS_RU.get(day_num, '')}, {target_date.day} {MONTHS_RU.get(target_date.month, '')}</b>"
    if day_num in (6, 7):
        return f"{date_header}\n\n🎉 Выходной день! Занятий нет."
    try:
        with open("/root/bot_u451/schedule.json", "r", encoding="utf-8") as f:
            full = json.load(f)
    except Exception:
        return "Ошибка чтения schedule.json."
    pairs = [p for p in full.get(week_type, {}).get(str(day_num), []) if p["subgroup"] in (0, user_subgroup)]
    if not pairs:
        return f"{date_header}\n\n🎉 У твоей подгруппы сегодня пар нет!"
    w_str = "1-я / 3-я" if week_type == "1_3" else "2-я / 4-я"
    res = f"{date_header} ({w_str} неделя)\n👤 Подгруппа: {user_subgroup}\n\n"
    for p in pairs:
        sub = f" [п/г {p['subgroup']}]" if p['subgroup'] != 0 else ""
        res += f"🔹 <b>{p['num']} пара</b> ({p['time']}){sub}\n   📖 {p['name']}\n   🏛 {p['room']} | 👨‍🏫 {p['teacher']}\n\n"
    return res

def get_main_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📅 Расписание на сегодня"), KeyboardButton(text="📆 Расписание на завтра")],
            [KeyboardButton(text="📚 Материалы"), KeyboardButton(text="🌤 Погода сейчас")],
            [KeyboardButton(text="👤 Мой профиль")]
        ],
        resize_keyboard=True
    )

def get_subgroup_inline():
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="1-я подгруппа", callback_data="sub_1"),
        InlineKeyboardButton(text="2-я подгруппа", callback_data="sub_2")
    ]])

def get_profile_inline():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Изменить ФИО", callback_data="change_name")],
        [InlineKeyboardButton(text="⚙️ Сменить подгруппу", callback_data="change_sub")]
    ])

def get_materials_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📂 Просмотреть материалы", callback_data="mat_view")],
        [InlineKeyboardButton(text="📤 Отправить материал", callback_data="mat_upload")]
    ])

async def morning_broadcast_job():
    now = datetime.now(TIMEZONE)
    if now.isoweekday() == 7:
        return
    week = await get_current_week()
    weather = await get_makhachkala_weather()
    users = await get_all_active_users()
    for uid, name, sub in users:
        try:
            greeting = f", {name.split()[0]}" if name else ""
            txt = f"🌅 <b>Доброе утро{greeting}! (07:30)</b>\n\n{weather}\n{format_schedule(now, week, sub)}"
            await bot.send_message(uid, txt, parse_mode="HTML")
            await asyncio.sleep(0.05)
        except Exception:
            pass

@dp.message(AdminRenameState.waiting_for_new_name, F.text)
async def process_adm_rename_msg(msg: Message, state: FSMContext):
    if msg.from_user.id != ADMIN_ID:
        return
    new_name = msg.text.strip()
    data = await state.get_data()
    uid = data.get("target_uid")
    await state.clear()

    if not uid:
        await msg.answer("Ошибка: студент не найден.")
        return

    await update_user_name(uid, new_name)

    try:
        await bot.send_message(uid, f"ℹ️ Староста обновил твое имя в системе на: <b>{new_name}</b>.", parse_mode="HTML")
    except Exception:
        pass

    user = await get_user(uid)
    curr_sub = user[1] if user and user[1] else 1

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="1-я подгруппа", callback_data=f"adm_set_{uid}_1"),
            InlineKeyboardButton(text="2-я подгруппа", callback_data=f"adm_set_{uid}_2")
        ],
        [InlineKeyboardButton(text="✏️ Изменить ФИО", callback_data=f"adm_rename_{uid}")],
        [InlineKeyboardButton(text="💬 Открыть чат в Telegram", url=f"tg://user?id={uid}")],
        [InlineKeyboardButton(text="⬅️ Назад к списку", callback_data="adm_students_list")]
    ])
    txt = (
        f"✅ ФИО успешно обновлено!\n\n"
        f"👤 Студент: <b>{new_name}</b>\n"
        f"🆔 ID: <code>{uid}</code>\n"
        f"🔗 Ссылка: <a href=\"tg://user?id={uid}\">Перейти в профиль</a>\n"
        f"Текущая подгруппа: <b>{curr_sub}-я</b>\n\n"
        "Выберите действие:"
    )
    await msg.answer(txt, reply_markup=kb, parse_mode="HTML")

@dp.message(CommandStart())
async def cmd_start(msg: Message, state: FSMContext):
    await state.clear()
    await ensure_user_started(msg.from_user.id)
    user = await get_user(msg.from_user.id)
    if user and user[0] and user[1]:
        await msg.answer(f"С возвращением, <b>{user[0]}</b>!\nТвоя подгруппа: <b>{user[1]}</b>.", reply_markup=get_main_keyboard(), parse_mode="HTML")
    else:
        await state.set_state(RegistrationState.waiting_for_full_name)
        await msg.answer("👋 Привет! Добро пожаловать в бот <b>У451 ДГТУ</b>.\n\nНапиши свои <b>Фамилию и Имя</b> (например: <i>Магомедов Ахмед</i>):", parse_mode="HTML")

@dp.message(RegistrationState.waiting_for_full_name)
async def process_reg_name(msg: Message, state: FSMContext):
    name = msg.text.strip()
    if len(name.split()) < 2:
        await msg.answer("Пожалуйста, напиши Фамилию и Имя через пробел:")
        return
    await state.update_data(full_name=name)
    await state.set_state(RegistrationState.waiting_for_subgroup)
    await msg.answer(f"Принято, <b>{name}</b>!\nВыбери свою подгруппу:", reply_markup=get_subgroup_inline(), parse_mode="HTML")

@dp.callback_query(RegistrationState.waiting_for_subgroup, F.data.startswith("sub_"))
async def process_reg_sub(cb: CallbackQuery, state: FSMContext):
    sub = int(cb.data.split("_")[1])
    data = await state.get_data()
    name = data.get("full_name")
    await save_user(cb.from_user.id, name, sub)
    await state.clear()
    await cb.message.delete()
    await cb.message.answer(f"✅ Регистрация завершена: <b>{name}</b> ({sub}-я подгруппа).", reply_markup=get_main_keyboard(), parse_mode="HTML")
    await cb.answer()

@dp.message(F.text == "👤 Мой профиль")
async def show_profile(msg: Message):
    user = await get_user(msg.from_user.id)
    if not user or not user[0]:
        await msg.answer("Пройди регистрацию через /start.")
        return
    await msg.answer(f"👤 <b>Профиль:</b>\n• ФИО: <b>{user[0]}</b>\n• Подгруппа: <b>{user[1]}</b>\n• Рассылка: <b>07:30</b>", reply_markup=get_profile_inline(), parse_mode="HTML")

@dp.callback_query(F.data == "change_name")
async def cb_change_name(cb: CallbackQuery, state: FSMContext):
    await state.set_state(ChangeNameState.waiting_for_new_name)
    await cb.message.answer("Введи новые Фамилию и Имя:")
    await cb.answer()

@dp.message(ChangeNameState.waiting_for_new_name)
async def process_new_name(msg: Message, state: FSMContext):
    if len(msg.text.strip().split()) < 2:
        await msg.answer("Напиши Фамилию и Имя через пробел:")
        return
    await update_user_name(msg.from_user.id, msg.text.strip())
    await state.clear()
    await msg.answer(f"✅ ФИО обновлено на: <b>{msg.text.strip()}</b>", reply_markup=get_main_keyboard())

@dp.callback_query(F.data == "change_sub")
async def cb_change_sub(cb: CallbackQuery):
    await cb.message.answer("Выбери новую подгруппу:", reply_markup=get_subgroup_inline())
    await cb.answer()

@dp.callback_query(F.data.startswith("sub_"))
async def cb_sub_direct(cb: CallbackQuery):
    sub = int(cb.data.split("_")[1])
    await update_user_subgroup(cb.from_user.id, sub)
    await cb.message.delete()
    await cb.message.answer(f"✅ Подгруппа изменена на: <b>{sub}</b>", reply_markup=get_main_keyboard())
    await cb.answer()

@dp.message(F.text == "🌤 Погода сейчас")
@dp.message(Command("weather"))
async def cmd_weather(msg: Message):
    await msg.answer(await get_makhachkala_weather(), parse_mode="HTML")

@dp.message(F.text == "📅 Расписание на сегодня")
@dp.message(Command("today"))
async def sched_today(msg: Message):
    u = await get_user(msg.from_user.id)
    if not u or not u[1]:
        await msg.answer("Сначала выбери подгруппу через /start.")
        return
    await msg.answer(format_schedule(datetime.now(TIMEZONE), await get_current_week(), u[1]), parse_mode="HTML")

@dp.message(F.text == "📆 Расписание на завтра")
@dp.message(Command("tomorrow"))
async def sched_tom(msg: Message):
    u = await get_user(msg.from_user.id)
    if not u or not u[1]:
        await msg.answer("Сначала выбери подгруппу через /start.")
        return
    await msg.answer(format_schedule(datetime.now(TIMEZONE) + timedelta(days=1), await get_current_week(), u[1]), parse_mode="HTML")

@dp.message(F.text == "📚 Материалы")
async def mat_menu(msg: Message):
    await msg.answer("📚 <b>База учебных материалов группы У451</b>", reply_markup=get_materials_menu(), parse_mode="HTML")

@dp.callback_query(F.data == "mat_upload")
async def mat_up(cb: CallbackQuery, state: FSMContext):
    await state.set_state(UploadMaterialState.waiting_for_file)
    await cb.message.answer("📎 Отправь файл, фото или видео:")
    await cb.answer()

@dp.message(UploadMaterialState.waiting_for_file, F.content_type.in_({'document', 'photo', 'video'}))
async def mat_file(msg: Message, state: FSMContext):
    fid = msg.document.file_id if msg.document else (msg.photo[-1].file_id if msg.photo else msg.video.file_id)
    ftype = "document" if msg.document else ("photo" if msg.photo else "video")
    await state.update_data(file_id=fid, file_type=ftype)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=s, callback_data=f"sel_{i}")] for i, s in enumerate(SUBJECTS_LIST)])
    await state.set_state(UploadMaterialState.waiting_for_subject)
    await msg.answer("Выбери предмет:", reply_markup=kb)

@dp.callback_query(UploadMaterialState.waiting_for_subject, F.data.startswith("sel_"))
async def mat_sub(cb: CallbackQuery, state: FSMContext):
    subj = SUBJECTS_LIST[int(cb.data.split("_")[1])]
    await state.update_data(subject=subj)
    await state.set_state(UploadMaterialState.waiting_for_title)
    await cb.message.edit_text(f"Предмет: <b>{subj}</b>\n\nНапиши название материала (например: <i>Лекция 2</i>):", parse_mode="HTML")
    await cb.answer()

@dp.message(UploadMaterialState.waiting_for_title)
async def mat_title(msg: Message, state: FSMContext):
    d = await state.get_data()
    title = msg.text.strip()
    mid = await add_material(msg.from_user.id, d["file_id"], d["file_type"], d["subject"], title)
    await state.clear()
    await msg.answer("✅ Материал отправлен старосте на проверку!")

    user = await get_user(msg.from_user.id)
    sname = user[0] if user else f"ID {msg.from_user.id}"
    akb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Одобрить", callback_data=f"appr_{mid}"),
        InlineKeyboardButton(text="❌ Отклонить", callback_data=f"rejc_{mid}")
    ]])
    cap = f"🔔 <b>Новый материал!</b>\nОт: <b>{sname}</b>\nПредмет: <b>{d['subject']}</b>\nНазвание: <b>{title}</b>"
    if d["file_type"] == "document":
        await bot.send_document(ADMIN_ID, d["file_id"], caption=cap, parse_mode="HTML", reply_markup=akb)
    elif d["file_type"] == "photo":
        await bot.send_photo(ADMIN_ID, d["file_id"], caption=cap, parse_mode="HTML", reply_markup=akb)
    elif d["file_type"] == "video":
        await bot.send_video(ADMIN_ID, d["file_id"], caption=cap, parse_mode="HTML", reply_markup=akb)

@dp.callback_query(F.data.startswith(("appr_", "rejc_")))
async def mat_mod(cb: CallbackQuery):
    if cb.from_user.id != ADMIN_ID:
        return
    act, mid_str = cb.data.split("_")
    mid = int(mid_str)
    row = await get_material(mid)
    if not row:
        await cb.answer("Материал не найден.")
        return
    uid, title, subject = row
    status = "approved" if act == "appr" else "rejected"
    await update_material_status(mid, status)
    await cb.message.edit_reply_markup(reply_markup=None)
    txt = f"✅ Материал «{title}» одобрен." if act == "appr" else f"❌ Материал «{title}» отклонен."
    await cb.message.reply(txt)
    try:
        user_msg = f"🎉 Твой материал <b>«{title}»</b> по предмету <b>{subject}</b> одобрен!" if act == "appr" else f"😔 Материал <b>«{title}»</b> отклонен старостой."
        await bot.send_message(uid, user_msg, parse_mode="HTML")
    except Exception:
        pass
    await cb.answer()

@dp.callback_query(F.data == "mat_view")
async def mat_view(cb: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=s, callback_data=f"vw_{i}")] for i, s in enumerate(SUBJECTS_LIST)] + [[InlineKeyboardButton(text="⬅️ Назад", callback_data="mat_back")]])
    await cb.message.edit_text("Выбери предмет для просмотра:", reply_markup=kb)
    await cb.answer()

@dp.callback_query(F.data == "mat_back")
async def mat_back(cb: CallbackQuery):
    await cb.message.edit_text("📚 <b>База учебных материалов группы У451</b>", reply_markup=get_materials_menu(), parse_mode="HTML")
    await cb.answer()

@dp.callback_query(F.data.startswith("vw_"))
async def mat_show_sub(cb: CallbackQuery):
    subj = SUBJECTS_LIST[int(cb.data.split("_")[1])]
    mats = await get_approved_materials(subj)
    if not mats:
        await cb.answer(f"По предмету «{subj}» материалов пока нет.", show_alert=True)
        return
    await cb.message.answer(f"📁 <b>Материалы по предмету «{subj}»:</b>", parse_mode="HTML")
    for _, title, fid, ftype in mats:
        c = f"📖 <b>{title}</b>\nПредмет: {subj}"
        try:
            if ftype == "document":
                await cb.message.answer_document(fid, caption=c, parse_mode="HTML")
            elif ftype == "photo":
                await cb.message.answer_photo(fid, caption=c, parse_mode="HTML")
            elif ftype == "video":
                await cb.message.answer_video(fid, caption=c, parse_mode="HTML")
            await asyncio.sleep(0.05)
        except Exception:
            pass
    await cb.answer()

# ================= РАССЫЛКА И ИНТЕРАКТИВНАЯ АДМИНКА =================
async def evening_broadcast_job():
    now = datetime.now(TIMEZONE)
    if now.isoweekday() in (5, 6):
        return
    tomorrow = now + timedelta(days=1)
    week = await get_current_week()
    users = await get_all_active_users()
    for uid, name, sub in users:
        try:
            greeting = f", {name.split()[0]}" if name else ""
            d_str = tomorrow.strftime("%d.%m")
            sched = format_schedule(tomorrow, week, int(sub) if sub else 0)
            txt = f"🌙 <b>Расписание на завтра ({d_str}){greeting}:</b>\n\n{sched}\n\nСпокойной ночи и продуктивной подготовки! 😴"
            await bot.send_message(uid, txt, parse_mode="HTML")
            await asyncio.sleep(0.05)
        except Exception:
            pass

def get_admin_menu_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👥 Список группы и подгруппы", callback_data="adm_students_list")],
        [InlineKeyboardButton(text="📋 Полный список текстом с ссылками", callback_data="adm_export_text")],
        [
            InlineKeyboardButton(text="🌙 Тест вечер (22:00)", callback_data="adm_run_test_evening"),
            InlineKeyboardButton(text="🌅 Тест утро (07:30)", callback_data="adm_run_test_morning")
        ],
        [InlineKeyboardButton(text="❌ Закрыть меню", callback_data="adm_close")]
    ])

async def build_students_keyboard():
    users = await get_all_active_users()
    kb = []
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
    await msg.answer("👑 <b>Панель администратора У451</b>\nВыберите нужный раздел:", reply_markup=get_admin_menu_keyboard(), parse_mode="HTML")

@dp.callback_query(F.data == "adm_main_menu")
async def cb_adm_main_menu(cb: CallbackQuery):
    if cb.from_user.id != ADMIN_ID:
        return
    await cb.message.edit_text("👑 <b>Панель администратора У451</b>\nВыберите нужный раздел:", reply_markup=get_admin_menu_keyboard(), parse_mode="HTML")
    await cb.answer()

@dp.callback_query(F.data == "adm_students_list")
async def cb_adm_students_list(cb: CallbackQuery):
    if cb.from_user.id != ADMIN_ID:
        return
    markup = await build_students_keyboard()
    await cb.message.edit_text("👥 <b>Список группы У451</b>\nНажмите на студента для смены подгруппы:", reply_markup=markup, parse_mode="HTML")
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
        [InlineKeyboardButton(text="✏️ Изменить ФИО", callback_data=f"adm_rename_{uid}")],
        [InlineKeyboardButton(text="💬 Открыть чат в Telegram", url=f"tg://user?id={uid}")],
        [InlineKeyboardButton(text="⬅️ Назад к списку", callback_data="adm_students_list")]
    ])
    txt = (
        f"👤 Студент: <b>{name}</b>\n"
        f"🆔 ID: <code>{uid}</code>\n"
        f"🔗 Ссылка: <a href=\"tg://user?id={uid}\">Перейти в профиль</a>\n"
        f"Текущая подгруппа: <b>{curr_sub}-я</b>\n\n"
        "Выберите подгруппу или свяжитесь со студентом:"
    )
    await cb.message.edit_text(txt, reply_markup=kb, parse_mode="HTML")
    await cb.answer()

@dp.callback_query(F.data.startswith("adm_rename_"))
async def cb_adm_rename_start(cb: CallbackQuery, state: FSMContext):
    if cb.from_user.id != ADMIN_ID:
        return
    uid = int(cb.data.split("_")[2])
    await state.set_state(AdminRenameState.waiting_for_new_name)
    await state.update_data(target_uid=uid)
    
    cancel_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data=f"adm_edit_{uid}")]
    ])
    await cb.message.edit_text(
        f"✏️ Введите новые <b>Фамилию и Имя</b> для студента (ID: <code>{uid}</code>):\n\n"
        f"<i>Отправьте сообщение в ответ в формате: Фамилия Имя</i>",
        reply_markup=cancel_kb,
        parse_mode="HTML"
    )
    await cb.answer()


@dp.callback_query(F.data.startswith("adm_set_"))
async def cb_adm_set_subgroup(cb: CallbackQuery):
    if cb.from_user.id != ADMIN_ID:
        return
    parts = cb.data.split("_")
    uid = int(parts[2])
    new_sub = int(parts[3])

    await update_user_subgroup(uid, new_sub)
    user = await get_user(uid)
    name = user[0] if user and user[0] else f"ID: {uid}"

    try:
        await bot.send_message(uid, f"ℹ️ Староста изменил твою подгруппу на: <b>{new_sub}-я</b>.", parse_mode="HTML")
    except Exception:
        pass

    await cb.answer(f"{name} переведен в {new_sub}-ю подгруппу!", show_alert=True)
    markup = await build_students_keyboard()
    await cb.message.edit_text("👥 <b>Список группы У451</b>\nНажмите на студента для смены подгруппы:", reply_markup=markup, parse_mode="HTML")

@dp.callback_query(F.data == "adm_export_text")
async def cb_adm_export_text(cb: CallbackQuery):
    if cb.from_user.id != ADMIN_ID:
        return
    await cb.answer("Формирую список...")
    users = await get_all_active_users()
    sub1, sub2, unk = [], [], []
    for uid, name, sub in users:
        item = f"<a href=\"tg://user?id={uid}\">{name if name else 'Без имени'}</a> (<code>{uid}</code>)"
        if sub == 1:
            sub1.append(item)
        elif sub == 2:
            sub2.append(item)
        else:
            unk.append(item)

    lines = ["📋 <b>Состав группы У451:</b>\n", f"<b>1-я подгруппа ({len(sub1)} чел.):</b>"]
    lines.extend([f"{i}. {u}" for i, u in enumerate(sorted(sub1), 1)] if sub1 else ["<i>Пусто</i>"])
    lines.append(f"\n<b>2-я подгруппа ({len(sub2)} чел.):</b>")
    lines.extend([f"{i}. {u}" for i, u in enumerate(sorted(sub2), 1)] if sub2 else ["<i>Пусто</i>"])
    if unk:
        lines.append(f"\n<b>Без подгруппы ({len(unk)} чел.):</b>")
        lines.extend([f"{i}. {u}" for i, u in enumerate(sorted(unk), 1)])

    await cb.message.answer("\n".join(lines), parse_mode="HTML", disable_web_page_preview=True)

@dp.callback_query(F.data == "adm_run_test_evening")
async def cb_adm_test_evening(cb: CallbackQuery):
    if cb.from_user.id != ADMIN_ID:
        return
    await cb.answer("Формирую вечер...")
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
    await cb.answer("Формирую утро...")
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

async def main():
    await init_db()
    scheduler = AsyncIOScheduler(timezone=TIMEZONE)
    scheduler.add_job(evening_broadcast_job, "cron", hour=22, minute=0)
    scheduler.add_job(morning_broadcast_job, "cron", hour=7, minute=30)
    scheduler.start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
