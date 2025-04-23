# common.py

import os
import json
import datetime
import random
import itertools
import asyncio

from fastapi import Request
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
            "balance": 0,
            "username": username,
            "photo_url": photo_url,
            "logged_in": False,
            "login_code": None,
            "code_expiry": None,
            "verified": False
        }
    return data["users"][user_id]

def ensure_chats(data: dict) -> dict:
    """
    Убедиться, что в структуре данных есть ключ 'chats'.
    Если его нет — создать пустой словарь.
    """
    if "chats" not in data:
        data["chats"] = {}
    return data["chats"]

def get_new_chat_id() -> str:
    """
    Возвращает уникальный ID чата на основе текущей метки времени (в миллисекундах).
    """
    return str(int(datetime.datetime.now().timestamp() * 1000))

# --- ВАЖНО: указываем путь к папке с шаблонами, лежащей на уровень выше ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))        # /app
PROJECT_ROOT = os.path.dirname(BASE_DIR)                     # корень проекта
TEMPLATES_DIR = os.path.join(PROJECT_ROOT, "templates")      # /templates

templates = Jinja2Templates(directory=TEMPLATES_DIR)
templates.env.globals["enumerate"] = enumerate

def require_web_login(request: Request) -> str | None:
    """
    Проверяет, есть ли в куках залогиненный user_id.
    Если есть — возвращает user_id, иначе — None.
    """
    user_id = request.cookies.get("user_id")
    if not user_id:
        return None
    data = load_data()
    user = data.get("users", {}).get(user_id)
    if not user or not user.get("logged_in"):
        return None
    return user_id

# --- Aiogram bot setup (не менялось) ---
from aiogram import Bot, Dispatcher, F
from aiogram.client.bot import DefaultBotProperties
from aiogram.enums import ParseMode

BOT_TOKEN = "7964268980:AAH5QFV0PY98hSiNw0v6rjYDutkWa1CN0hM"
bot = Bot(
    token=BOT_TOKEN,
    default_bot_properties=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()
