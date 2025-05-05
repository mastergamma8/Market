# app/common.py
import os
import json
import shutil
import datetime

from fastapi.templating import Jinja2Templates
from aiogram import Bot, Dispatcher, F
from aiogram.client.bot import DefaultBotProperties
from aiogram.enums import ParseMode

# ── Пути и шаблон ───────────────────────────────────────────────────────────
BASE_DIR      = os.path.dirname(__file__)
TEMPLATE_FILE = os.path.join(BASE_DIR, "..", "data.template.json")

DATA_FOLDER   = "/data"
DATA_FILE     = os.path.join(DATA_FOLDER, "data.json")
AVATARS_DIR   = os.path.join(DATA_FOLDER, "static", "avatars")

# ── Создаём необходимые папки и файлы ───────────────────────────────────────
# 1) Папка /data
os.makedirs(DATA_FOLDER, exist_ok=True)
# 2) Если БД ещё не создана — копируем шаблон
if not os.path.exists(DATA_FILE):
    shutil.copy(TEMPLATE_FILE, DATA_FILE)

# 3) Папка для аватарок
os.makedirs(AVATARS_DIR, exist_ok=True)


# ── Функции для работы с data.json ──────────────────────────────────────────
def load_data() -> dict:
    """
    Загружает data.json. Если файл отсутствует или битый — возвращает пустую структуру.
    Всегда гарантирует наличие ключей "limited_backgrounds", "users", "banned", "vouchers".
    """
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        data = {}

    # Убедимся, что все разделы есть
    data.setdefault("limited_backgrounds", {})
    data.setdefault("users", {})
    data.setdefault("banned", [])
    data.setdefault("vouchers", [])
    return data

def save_data(data: dict) -> None:
    """
    Сохраняет всю структуру в data.json с отступами.
    """
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def ensure_user(data: dict, user_id: str, username: str = "Unknown", photo_url: str = None) -> dict:
    """
    Гарантирует, что в data['users'][user_id] есть запись; если нет — создаёт.
    Возвращает словарь пользователя для дальнейшей модификации.
    """
    today = datetime.date.today().isoformat()

    users = data.setdefault("users", {})
    if user_id not in users:
        users[user_id] = {
            "registration_date": today,
            "last_activation_date": today,
            "activation_count": 0,
            "extra_attempts": 0,
            "tokens": [],
            "balance": 0,
            "username": username,
            "photo_url": photo_url,
            "logged_in": False,
            "login_code": None,
            "code_expiry": None,
            "verified": False
        }
    return users[user_id]


# ── Настройка шаблонов для FastAPI ─────────────────────────────────────────
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "..", "templates"))
templates.env.globals["enumerate"] = enumerate


# ── Инициализация бота Aiogram ─────────────────────────────────────────────
BOT_TOKEN = os.getenv("BOT_TOKEN", "7964268980:AAH5QFV0PY98hSiNw0v6rjYDutkWa1CN0hM")
bot = Bot(
    token=BOT_TOKEN,
    default_bot_properties=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()
