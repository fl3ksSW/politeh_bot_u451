import re

path = "/root/bot_u451/bot.py"
with open(path, "r", encoding="utf-8") as f:
    lines = f.readlines()

clean_lines = []
skip = False
for line in lines:
    if "async def evening_broadcast_job():" in line or '@dp.message(Command("test_evening"))' in line:
        skip = True
    elif skip and line.startswith("async def main():"):
        skip = False
    
    if not skip and "evening_broadcast_job" not in line:
        clean_lines.append(line)

new_code = "".join(clean_lines)

evening_code = '''
async def evening_broadcast_job():
    now = datetime.now()
    if now.isoweekday() in (5, 6):
        return
    tomorrow_date = now + timedelta(days=1)
    users = await get_all_users()
    for uid in users:
        try:
            subgroup = await get_user_subgroup(uid)
            sched_text = get_schedule_for_date(tomorrow_date, subgroup)
            d_str = tomorrow_date.strftime("%d.%m")
            msg = (
                f"🌙 <b>Расписание на завтра</b> ({d_str}):\n\n"
                f"{sched_text}\n\n"
                "Спокойной ночи и продуктивной подготовки! 😴"
            )
            await bot.send_message(uid, msg, parse_mode="HTML")
            await asyncio.sleep(0.05)
        except Exception:
            pass

@dp.message(Command("test_evening"))
async def cmd_test_evening(message: Message):
    now = datetime.now()
    tomorrow_date = now + timedelta(days=1)
    subgroup = await get_user_subgroup(message.from_user.id)
    if subgroup is None:
        subgroup = 2
    sched_text = get_schedule_for_date(tomorrow_date, subgroup)
    d_str = tomorrow_date.strftime("%d.%m")
    msg = (
        f"🌙 <b>[ТЕСТ] Вечернее расписание на завтра</b> ({d_str}):\n\n"
        f"{sched_text}\n\n"
        "Спокойной ночи и продуктивной подготовки! 😴"
    )
    await message.answer(msg, parse_mode="HTML")
'''

new_code = new_code.replace("async def main():", evening_code.strip() + "\n\nasync def main():")

sched_line = '    scheduler.add_job(evening_broadcast_job, "cron", hour=22, minute=0)\n'
new_code = new_code.replace("scheduler.add_job(morning_broadcast_job", sched_line + "    scheduler.add_job(morning_broadcast_job")

compile(new_code, path, "exec")

with open(path, "w", encoding="utf-8") as f:
    f.write(new_code)

print("Все успешно пропатчено!")
