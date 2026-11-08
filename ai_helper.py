import base64
import os
import aiohttp
from dotenv import load_dotenv

load_dotenv("/root/bot_u451/.env")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

SYSTEM_PROMPT = (
    "Ты — академический ассистент группы У451 ДГТУ (Махачкала). "
    "Помогай студентам решать задачи по техническим и гуманитарным дисциплинам, "
    "объясняй сложные темы простым языком, считывай условия с фотографий конспектов/тетрадей, "
    "расписывай подробное пошаговое решение (Дано, Формулы, Решение, Ответ). "
    "Отвечай на русском языке."
)

async def ask_gemini(prompt: str, image_bytes: bytes = None) -> str:
    key = os.getenv("GEMINI_API_KEY") or GEMINI_API_KEY
    if not key:
        return "⚠️ Ошибка: GEMINI_API_KEY не задан."

    parts = []
    if image_bytes:
        parts.append({
            "inline_data": {
                "mime_type": "image/jpeg",
                "data": base64.b64encode(image_bytes).decode("utf-8")
            }
        })
    parts.append({"text": prompt or "Разбери материал на этом фото и подробно распиши решение."})

    payload = {
        "system_instruction": {
            "parts": [{"text": SYSTEM_PROMPT}]
        },
        "contents": [{"parts": parts}]
    }

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.8-flash:generateContent?key={key}"

    headers = {"Content-Type": "application/json"}

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers, timeout=60) as resp:
                data = await resp.json()
                if resp.status == 200:
                    candidates = data.get("candidates", [])
                    if candidates:
                        content_parts = candidates[0].get("content", {}).get("parts", [])
                        if content_parts:
                            return content_parts[0].get("text", "Ответ пуст.")
                    return "Не удалось прочитать ответ модели."
                else:
                    err_msg = data.get("error", {}).get("message", "Неизвестная ошибка")
                    return f"⚠️ Ошибка Gemini ({resp.status}): {err_msg}"
    except Exception as e:
        return f"⚠️ Ошибка запроса: {e}"
