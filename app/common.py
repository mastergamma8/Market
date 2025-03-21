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
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, "r", encoding="utf-8") as file:
        try:
            return json.load(file)
        except json.JSONDecodeError:
            return {}

def save_data(data: dict) -> None:
    with open(DATA_FILE, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)

def ensure_user(data: dict, user_id: str, username: str = "Unknown", photo_url: str = None) -> dict:
    today = datetime.date.today().isoformat()
    if "users" not in data:
        data["users"] = {}
    if user_id not in data["users"]:
        data["users"][user_id] = {
            "last_activation_date": today,
            "activation_count": 0,
            "tokens": [],
            "pinned_tokens": [],  # Инициализируем закреплённые номера
            "balance": 0,
            "username": username,
            "photo_url": photo_url,
            "logged_in": False,
            "login_code": None,
            "code_expiry": None,
            "verified": False
        }
    user = data["users"][user_id]
    # Если по какой-то причине поле не установлено, добавляем его
    if "pinned_tokens" not in user:
        user["pinned_tokens"] = []
    return user

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