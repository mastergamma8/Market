# common.py
import os
import json
import datetime
import random
import itertools
import asyncio

from fastapi.templating import Jinja2Templates

DATA_FILE = "data.json"

def load_data() -> dict:
    """
    Загружает data.json. Если файла нет или он невалиден, возвращает пустой словарь.
    Гарантирует, что в результате всегда есть ключ "limited_backgrounds".
    """
    if not os.path.exists(DATA_FILE):
        data = {}
    else:
        with open(DATA_FILE, "r", encoding="utf-8") as file:
            try:
                data = json.load(file)
            except json.JSONDecodeError:
                data = {}
    # Гарантируем, что раздел для лимитированных фонов существует
    data.setdefault("limited_backgrounds", {})
    return data

def save_data(data: dict) -> None:
    """
    Сохраняет переданный словарь в data.json с отступами.
    """
    with open(DATA_FILE, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)

def ensure_user(data: dict, user_id: str, username: str = "Unknown", photo_url: str = None) -> dict:
    """
    Убеждается, что в data["users"] есть запись о данном user_id.
    Если нет — создаёт её с базовыми полями.
    """
    today = datetime.date.today().isoformat()

    if "users" not in data:
        data["users"] = {}

    if user_id not in data["users"]:
        data["users"][user_id] = {
            "registration_date": today,
            "last_activation_date": today,
            "activation_count": 0,
            "tokens": [],
            "balance": 0,
            "username": username,
            "photo_url": photo_url,
            "logged_in": False,
            "login_code": None,
            "code_expiry": None,
            "verified": False
        }
    return data["users"][user_id]

templates = Jinja2Templates(directory="templates")
# Добавляем, если нужно, дополнительные глобальные функции для шаблонов:
templates.env.globals["enumerate"] = enumerate

# Инициализация бота для aiogram
from aiogram import Bot, Dispatcher, F
from aiogram.client.bot import DefaultBotProperties
from aiogram.enums import ParseMode

BOT_TOKEN = "7964268980:AAH5QFV0PY98hSiNw0v6rjYDutkWa1CN0hM"
bot = Bot(
    token=BOT_TOKEN,
    default_bot_properties=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()
