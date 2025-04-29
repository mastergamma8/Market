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

    # Если пользователь новый — фиксируем дату регистрации
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


def get_chats(data: dict) -> dict:
    return data.setdefault("chats", {})

def create_chat(data: dict, owner_id: str, name: str) -> str:
    chats = get_chats(data)
    new_id = str(max((int(i) for i in chats.keys()), default=0) + 1)
    chats[new_id] = {
        "name": name,
        "owner_id": owner_id,
        "participants": [owner_id],
        "messages": []
    }
    save_data(data)
    return new_id

def join_chat(data: dict, user_id: str, chat_id: str) -> bool:
    chats = get_chats(data)
    chat = chats.get(chat_id)
    if not chat or user_id in chat["participants"]:
        return False
    chat["participants"].append(user_id)
    save_data(data)
    return True

def post_message(data: dict, user_id: str, chat_id: str, text: str):
    chats = get_chats(data)
    chat = chats.get(chat_id)
    if not chat or user_id not in chat["participants"]:
        return False
    chat["messages"].append({
        "user_id": user_id,
        "text": text,
        "timestamp": datetime.datetime.now().isoformat()
    })
    save_data(data)
    return True
