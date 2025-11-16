import os
import json
import random
import itertools
import math
import datetime
import time
import asyncio
import hashlib
import hmac
import zipfile
import io
import uuid
import shutil
import shop
import urllib.parse
from pathlib import Path
from typing import Tuple
import exchange_commands
from auctions import router as auctions_router, register_auction_tasks
from offer import router as offer_router
import admin_commands
# Импорт роутера из exchange_web
from exchange_web import router as exchange_router

# Импорт общих функций, шаблонов и объектов бота из common.py
from common import load_data, save_data, ensure_user, templates, bot, dp, DATA_FILE, BOT_TOKEN, cleanup_expired_attempts

# Импорт функции auto_cancel_exchanges из exchange_commands
from exchange_commands import auto_cancel_exchanges

from aiogram import Bot, Dispatcher, F
from aiogram.client.bot import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, LabeledPrice, WebAppInfo
from aiogram.types.input_file import FSInputFile  # Для отправки файлов

# Импорт для веб-приложения
import uvicorn
from fastapi import FastAPI, Request, Form, Body
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi import UploadFile, File

BASE_DIR = Path(__file__).parent.parent  # корень проекта

DISK_PATH = Path(os.getenv("DISK_MOUNT_PATH", BASE_DIR / "data"))
STATIC_DIR  = DISK_PATH / "static"

ADMIN_IDS = {"1809630966", "7053559428"}
BOT_USERNAME = "tthnftbot"

# URL вашего веб-интерфейса (используется для ссылки, которую бот пришлёт пользователю)
WEB_HOST = os.getenv("WEB_HOST", "https://market-production-b55a.up.railway.app/")

# --- Декоратор для проверки входа пользователя ---
# Теперь авто-регистрируем / авто-логиним пользователя при обращении к командам.
def require_login(handler):
    async def wrapper(message: Message):
        data = load_data()
        user_id = str(message.from_user.id)
        # ensure_user создаст пользователя, если его нет
        user = ensure_user(data, user_id, message.from_user.username)
        # отмечаем, что пользователь "вошёл" (для совместимости с старыми полями)
        if not user.get("logged_in"):
            user["logged_in"] = True
            save_data(data)
        await handler(message)
    return wrapper

# --- Функции для вычисления редкости номера, цвета цифр и фона ---
def compute_number_rarity(token_str: str) -> str:
    length = len(token_str)
    max_repeats = max(len(list(group)) for _, group in itertools.groupby(token_str))
    base_score = 10 - length  # Чем меньше цифр, тем больше базовый бонус
    bonus = max_repeats - 1
    total_score = base_score + bonus

    if total_score >= 9:
        return "0.1%"
    elif total_score == 8:
        return "0.3%"
    elif total_score == 7:
        return "0.5%"
    elif total_score == 6:
        return "0.8%"
    elif total_score == 5:
        return "1%"
    elif total_score == 4:
        return "1.5%"
    elif total_score == 3:
        return "2%"
    elif total_score == 2:
        return "2.5%"
    else:
        return "3%"

def generate_text_attributes() -> tuple:
    r = random.random()
    if r < 0.007:
        text_pool = ["#FFFFFF", "#000000"]
        text_rarity = "0.1%"
    elif r < 0.02:
        text_pool = [
            "linear-gradient(45deg, #00c2e6, #48d9af, #00cc1f)",
            "linear-gradient(45deg, #0099ff, #00ccff, #00ffcc)",
            "linear-gradient(45deg, #00bfff, #00f5ff, #00ff99)",
            "linear-gradient(45deg, #1e3c72, #2a5298, #1e90ff)",
            "linear-gradient(45deg, #3a1c71, #d76d77, #ffaf7b)",
            "linear-gradient(45deg, #134E5E, #71B280, #B2F4B8)"
        ]
        text_rarity = "0.5%"
    elif r < 0.05:
        text_pool = [
            "linear-gradient(45deg, #e60000, #e6b800, #66cc00)",
            "linear-gradient(45deg, #FF4500, #FFA500, #ADFF2F)",
            "linear-gradient(45deg, #FF6347, #FFD700, #98FB98)",
            "linear-gradient(45deg, #B22222, #FF8C00, #9ACD32)",
            "linear-gradient(45deg, #DC143C, #FFD700, #32CD32)",
            "linear-gradient(45deg, #8B0000, #FFA07A, #90EE90)"
        ]
        text_rarity = "1%"
    elif r < 0.08:
        text_pool = [
            "linear-gradient(45deg, #8E44AD, #3498DB, #2ECC71)",
            "linear-gradient(45deg, #9932CC, #00BFFF, #3CB371)",
            "linear-gradient(45deg, #8A2BE2, #1E90FF, #32CD32)",
            "linear-gradient(45deg, #6A0DAD, #4169E1, #3CB371)",
            "linear-gradient(45deg, #9400D3, #00CED1, #2E8B57)",
            "linear-gradient(45deg, #800080, #0000FF, #008000)"
        ]
        text_rarity = "1.5%"
    elif r < 0.18:
        text_pool = ["#FF5733", "#33FFCE", "#FFD700", "#FF69B4", "#00FA9A"]
        text_rarity = "2%"
    elif r < 0.30:
        text_pool = ["#8e44ad", "#2c3e50", "#DC143C", "#20B2AA", "#FFDAB9"]
        text_rarity = "2.5%"
    else:
        text_pool = ["#d35400", "#e67e22", "#27ae60", "#FF7F50", "#4682B4", "#9ACD32"]
        text_rarity = "3%"
    return random.choice(text_pool), text_rarity


def generate_bg_attributes() -> tuple:
    data = load_data()
    limited_bgs = data.get("limited_backgrounds", {})
    chance = 0.007  # вероятность выбора лимитированного фона (0.7%)
    r = random.random()
    if r < chance:
        # собираем только те лимитированные фоны, у которых ещё есть неиспользованные слоты
        available = [
            (filename, info)
            for filename, info in limited_bgs.items()
            if info.get("used", 0) < info.get("max", 0)
        ]
        if available:
            chosen_file, info = random.choice(available)
            # увеличиваем счётчик использования
            info["used"] = info.get("used", 0) + 1
            save_data(data)
            bg_value = f"/static/image/{chosen_file}"
            bg_rarity = "0.1%"
            bg_is_image = True
            bg_availability = f"{info['used']}/{info['max']}"
            return bg_value, bg_rarity, bg_is_image, bg_availability

    # Если лимитированные варианты не выбраны, продолжаем обычную генерацию
    r = random.random()
    if r < 0.02:
        bg_pool = [
            "linear-gradient(45deg, #00e4ff, #58ffca, #00ff24)",
            "linear-gradient(45deg, #00bfff, #66ffe0, #00ff88)",
            "linear-gradient(45deg, #0099ff, #33ccff, #66ffcc)",
            "linear-gradient(45deg, #0F2027, #203A43, #2C5364)",
            "linear-gradient(45deg, #3E5151, #DECBA4, #F4E2D8)",
            "linear-gradient(45deg, #1D4350, #A43931, #E96443)"
        ]
        bg_rarity = "0.5%"
        return random.choice(bg_pool), bg_rarity, False, None
    elif r < 0.05:
        bg_pool = [
            "linear-gradient(45deg, #ff0000, #ffd358, #82ff00)",
            "linear-gradient(45deg, #FF1493, #00CED1, #FFD700)",
            "linear-gradient(45deg, #FF69B4, #40E0D0, #FFFACD)",
            "linear-gradient(45deg, #B22222, #FF8C00, #9ACD32)",
            "linear-gradient(45deg, #DC143C, #FFD700, #32CD32)",
            "linear-gradient(45deg, #8B0000, #FFA07A, #90EE90)"
        ]
        bg_rarity = "1%"
        return random.choice(bg_pool), bg_rarity, False, None
    elif r < 0.08:
        bg_pool = [
            "linear-gradient(45deg, #FFC0CB, #FF69B4, #FF1493)",
            "linear-gradient(45deg, #FFB6C1, #FF69B4, #FF4500)",
            "linear-gradient(45deg, #FF69B4, #FF1493, #C71585)",
            "linear-gradient(45deg, #FFB347, #FFCC33, #FFD700)",
            "linear-gradient(45deg, #F7971E, #FFD200, #FF9A00)",
            "linear-gradient(45deg, #FF7E5F, #FEB47B, #FFDAB9)"
        ]
        bg_rarity = "1.5%"
        return random.choice(bg_pool), bg_rarity, False, None
    elif r < 0.18:
        bg_pool = ["#f1c40f", "#1abc9c", "#FF4500", "#32CD32", "#87CEEB"]
        bg_rarity = "2%"
        return random.choice(bg_pool), bg_rarity, False, None
    elif r < 0.30:
        bg_pool = ["#2ecc71", "#3498db", "#FF8C00", "#6A5ACD", "#40E0D0"]
        bg_rarity = "2.5%"
        return random.choice(bg_pool), bg_rarity, False, None
    else:
        bg_pool = ["#9b59b6", "#34495e", "#808000", "#FFD700", "#FF69B4", "#00CED1"]
        bg_rarity = "3%"
        return random.choice(bg_pool), bg_rarity, False, None

def compute_overall_rarity(num_rarity: str, text_rarity: str, bg_rarity: str) -> str:
    try:
        num_val = float(num_rarity.replace('%','').replace(',', '.'))
    except:
        num_val = 3.0
    try:
        text_val = float(text_rarity.replace('%','').replace(',', '.'))
    except:
        text_val = 3.0
    try:
        bg_val = float(bg_rarity.replace('%','').replace(',', '.'))
    except:
        bg_val = 3.0

    overall = (num_val * text_val * bg_val) ** (1/3)
    if overall.is_integer():
        return f"{int(overall)}%"
    else:
        return f"{overall:.1f}%"

def generate_number_from_value(token_str: str) -> dict:
    token_uuid = str(uuid.uuid4())
    max_repeats = max(len(list(group)) for _, group in itertools.groupby(token_str))
    number_rarity = compute_number_rarity(token_str)
    text_color, text_rarity = generate_text_attributes()
    bg_color, bg_rarity, bg_is_image, bg_availability = generate_bg_attributes()
    overall_rarity = compute_overall_rarity(number_rarity, text_rarity, bg_rarity)
    return {
        "uuid": token_uuid,
        "token": token_str,
        "max_repeats": max_repeats,  # Это поле используется для сортировки по повторениям
        "number_rarity": number_rarity,
        "text_color": text_color,
        "text_rarity": text_rarity,
        "bg_color": bg_color,
        "bg_rarity": bg_rarity,
        "bg_is_image": bg_is_image,
        "bg_availability": bg_availability,
        "overall_rarity": overall_rarity,
        "timestamp": datetime.datetime.now().isoformat()
    }

def generate_number() -> dict:
    length = random.choices([3, 4, 5, 6], weights=[1, 3, 6, 10])[0]
    token_str = "".join(random.choices("0123456789", k=length))
    return generate_number_from_value(token_str)

def get_rarity(score: int) -> str:
    if score > 12:
        return "2.5%"
    elif score > 8:
        return "2%"
    else:
        return "1.5%"


# ------------------ Обработчики команд бота ------------------

@dp.message(Command("start"))
async def start_cmd(message: Message) -> None:
    """Авто-регистрация пользователя и отправка ссылки для привязки веб-сессии."""
    data = load_data()
    user_id = str(message.from_user.id)
    user = ensure_user(data, user_id, message.from_user.username)

    # Авто-логин/авто-маркер
    if not user.get("logged_in"):
        user["logged_in"] = True

    # Всегда подтягиваем актуальную аватарку (попытка)
    user["photo_url"] = f"https://t.me/i/userpic/320/{user_id}.jpg"
    if not user.get("started"):
        user["started"] = True

    save_data(data)

    parts = message.text.split(maxsplit=1)
    args = parts[1].strip() if len(parts) > 1 else ""

    # Обработка ваучера (как было)
    if args.startswith("redeem_"):
        voucher_code = args[len("redeem_"):]
        voucher = None
        for v in data.get("vouchers", []):
            if v.get("code") == voucher_code:
                voucher = v
                break
        if voucher is None:
            await message.answer("❗ Ваучер не найден или недействителен.", parse_mode="HTML")
        else:
            if voucher.get("redeemed_count", 0) >= voucher.get("max_uses", 1):
                await message.answer("❗ Этот ваучер уже исчерпан.", parse_mode="HTML")
            else:
                redeemed_by = voucher.setdefault("redeemed_by", [])
                if str(message.from_user.id) in redeemed_by:
                    await message.answer("❗ Вы уже активировали этот ваучер.", parse_mode="HTML")
                else:
                    if voucher["type"] == "activation":
                        today = datetime.date.today().isoformat()
                        # при новом дне сбрасываем счётчики и очищаем старые записи
                        if user.get("last_activation_date") != today:
                            user["last_activation_date"] = today
                            user["activation_count"] = 0
                            user.setdefault("extra_attempt_entries", [])
                        # добавляем запись о новых попытках
                        entries = user.setdefault("extra_attempt_entries", [])
                        entries.append({
                            "count": voucher["value"],
                            "timestamp": time.time()
                        })
                        # считаем все валидные доп. попытки за последние 24 ч.
                        extra = cleanup_expired_attempts(user)
                        effective_limit = 1 + extra
                        remaining = effective_limit - user.get("activation_count", 0)
                        redemption_message = (
                            f"✅ Ваучер активирован! Вам добавлено {voucher['value']} дополнительных попыток активации. "
                            f"Осталось попыток: {remaining}.")
                    elif voucher["type"] == "money":
                        user["balance"] = user.get("balance", 0) + voucher["value"]
                        redemption_message = (
                            f"✅ Ваучер активирован! Вам зачислено {voucher['value']} 💎 на баланс."
                        )
                    else:
                        redemption_message = "❗ Неизвестный тип ваучера."
                    redeemed_by.append(str(message.from_user.id))
                    voucher["redeemed_count"] = voucher.get("redeemed_count", 0) + 1
                    save_data(data)
                    await message.answer(redemption_message, parse_mode="HTML")
        return

    # Обработка реферальной ссылки
    if args.startswith("referral_"):
        referrer_id = args[len("referral_"):]
        if "referrer" not in user and referrer_id != str(message.from_user.id) and referrer_id in data.get("users", {}):
            user["referrer"] = referrer_id
            save_data(data)
            referrer_username = data["users"][referrer_id].get("username", referrer_id)
            await message.answer(
                f"Вы присоединились по реферальной ссылке пользователя {referrer_username}!",
                parse_mode="HTML"
            )

    # Приветственное сообщение с ссылкой на сайт для установки cookie
    web_link = f"{WEB_HOST}/?user_id={user_id}"
    welcome_text = (
        "✨ Добро пожаловать в TTH NFT!\n\n"
        f"Ваш Telegram ID: <code>{user_id}</code>\n\n"
        "Чтобы начать, нажмите кнопку «Market» ниже или откройте веб-версию (это свяжет ваш аккаунт):\n"
        f"{web_link}\n\n"
        "Доступные команды:\n"
        "/referral — получить реферальную ссылку\n"
        "/referrals — статистика ваших рефералов\n"
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="Market",
                web_app=WebAppInfo(url="https://market-production-b55a.up.railway.app/")
            ),
            InlineKeyboardButton(
                text="Открыть сайт",
                web_app=WebAppInfo(url=web_link)
            )
        ]
    ])

    await message.answer(welcome_text, reply_markup=keyboard, parse_mode="HTML")


@dp.message(Command("referral"))
@require_login
async def referral_link(message: Message) -> None:
    user_id = str(message.from_user.id)
    referral_link = f"https://t.me/{BOT_USERNAME}?start=referral_{user_id}"
    await message.answer(f"Ваша реферальная ссылка:\n{referral_link}")

@dp.message(Command("referrals"))
@require_login
async def referrals_info(message: Message) -> None:
    data = load_data()
    user_id = str(message.from_user.id)
    referrals = [(uid, user) for uid, user in data.get("users", {}).items() if user.get("referrer") == user_id]
    count = len(referrals)
    if count == 0:
        await message.answer("Вы ещё не привели ни одного реферала.")
    else:
        referral_list = "\n".join(f"- {user.get('username', uid)} (ID: {uid})" for uid, user in referrals)
        await message.answer(f"Вы привели {count} рефералов:\n{referral_list}")


@dp.message(Command("balance"))
@require_login
async def show_balance(message: Message) -> None:
    data = load_data()
    user = ensure_user(data, str(message.from_user.id))
    await message.answer(f"💎 Ваш баланс: {user.get('balance', 0)} 💎")


# --------------------- Веб-приложение (FastAPI) ---------------------
app = FastAPI()

if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")
# Подключаем роутеры веб-приложения
app.include_router(exchange_router)
app.include_router(auctions_router)
app.include_router(offer_router)

# Настройка шаблонов
templates = Jinja2Templates(directory="templates")
templates.env.globals["enumerate"] = enumerate
# Предполагается, что функция get_rarity определена в одном из модулей (например, в common.py)
templates.env.globals["get_rarity"] = get_rarity

# Для защищённых маршрутов проверяем наличие cookie (и существование пользователя).
def require_web_login(request: Request):
    user_id = request.cookies.get("user_id")
    if not user_id:
        return None
    data = load_data()
    user = data.get("users", {}).get(user_id)
    if not user:
        return None
    return user_id

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """
    Если в query присутствует ?user_id=..., ставим cookie и создаём/обновляем пользователя.
    Это позволяет пользователю кликнуть ссылку из бота и автоматически получить веб-сессию.
    """
    data = load_data()
    qp_user_id = request.query_params.get("user_id")
    response = templates.TemplateResponse("index.html", {
        "request": request,
        "user": None,
        "user_id": None,
        "market": data.get("market", []),
        "users": data.get("users", {}),
        "buyer_id": None
    })
    if qp_user_id:
        # ensure_user создаст запись, если нет
        user = ensure_user(data, qp_user_id)
        # пометим logged_in и установим cookie
        if not user.get("logged_in"):
            user["logged_in"] = True
        save_data(data)
        # ставим cookie (30 дней)
        response.set_cookie("user_id", qp_user_id, max_age=60*60*24*30, path="/")
        # обновляем контекст
        response.context["user"] = user
        response.context["user_id"] = qp_user_id
        response.context["buyer_id"] = qp_user_id
    else:
        # пробуем подтянуть текущего пользователя по cookie
        cookie_user_id = request.cookies.get("user_id")
        user = data.get("users", {}).get(cookie_user_id) if cookie_user_id else None
        response.context["user"] = user
        response.context["user_id"] = cookie_user_id
        response.context["buyer_id"] = cookie_user_id
    return response

# Удалены маршруты /login, /verify, /logout — регистрация и вход происходят автоматически через бота и ссылку /?user_id=...

@app.post("/create-invoice")
async def create_invoice(
    request: Request,
    diamond_count: int = Form(...),
    price:         int = Form(...),
):
    user_id = request.cookies.get("user_id")
    if not user_id:
        return JSONResponse({"error": "Не авторизован"}, status_code=401)

    # Формируем полезную нагрузку для успешного платежа
    payload = f"shop_stars:{diamond_count}"

    # Выставляем инвойс на сумму `price` звезд, но метка остаётся с количеством алмазов
    prices = [LabeledPrice(label=f"{diamond_count} 💎", amount=price)]

    invoice_link: str = await bot.create_invoice_link(
        title="Покупка алмазов",
        description=f"Вы получите {diamond_count} алмазов за {price} ⭐️.",
        payload=payload,
        provider_token="",    # Stars
        currency="XTR",       # Telegram Stars
        prices=prices
    )
    return {"invoiceLink": invoice_link}

@app.get("/profile/{user_id}", response_class=HTMLResponse)
async def profile(request: Request, user_id: str):
    # 1) Проверяем авторизацию (наличие cookie и пользователя)
    current_user_id = request.cookies.get("user_id")
    data = load_data()
    current_user = data.get("users", {}).get(current_user_id)
    if not current_user:
        return RedirectResponse(url="/", status_code=303)

    # 2) Проверяем, что запрашиваемый пользователь есть в БД
    user = data["users"].get(user_id)
    if not user:
        return HTMLResponse("Пользователь не найден.", status_code=404)

    # 3) Если ещё нет photo_url, пробуем подтянуть из Telegram
    if not user.get("photo_url"):
        try:
            photos = await bot.get_user_profile_photos(int(user_id), limit=1)
            if photos.total_count > 0:
                photo = photos.photos[0][-1]
                tg_file = await bot.get_file(photo.file_id)
                file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{tg_file.file_path}"
                user["photo_url"] = file_url
                save_data(data)
        except Exception:
            pass

    # 4) Подготавливаем контекст для шаблона
    is_owner     = (current_user_id == user_id)
    tokens_count = len(user.get("tokens", []))

    # --- Маркируем токены только для отображения, без изменения модели ---
    custom_uuid = user.get("custom_number_uuid")
    for t in user.get("tokens", []):
        # всегда сохраняем оригинальный токен в display_token
        t["display_token"] = t["token"]
        if t.get("uuid") == custom_uuid:
            # добавляем невидимый символ только в поле для отображения
            t["display_token"] = t["token"] + "\u200b"
            # сохраняем в user.custom_number сам объект (с display_token и всеми полями)
            user["custom_number"] = t

    # 5) Рендерим шаблон
    return templates.TemplateResponse("profile.html", {
        "request":      request,
        "user":         user,
        "user_id":      user_id,
        "is_owner":     is_owner,
        "tokens_count": tokens_count
    })

@app.post("/update_profile", response_class=HTMLResponse)
async def update_profile(
    request: Request,
    user_id: str = Form(...),
    username: str = Form(None),
    description: str = Form("")       # По умолчанию пустая строка
):
    # Проверяем, что пользователь меняет только свой профиль
    cookie_user_id = request.cookies.get("user_id")
    if cookie_user_id != user_id:
        return HTMLResponse("Вы не можете изменять чужой профиль.", status_code=403)

    data = load_data()
    user = data.get("users", {}).get(user_id)
    if not user:
        return HTMLResponse("Пользователь не найден.", status_code=404)

    # 1) Обновляем никнейм
    if username and username.strip():
        user["username"] = username.strip()

    # 2) Обновляем описание с проверкой длины
    if description is not None:
        if len(description) > 85:
            return HTMLResponse("Описание не может превышать 85 символов.", status_code=400)
        user["description"] = description

    # Сохраняем изменения и перенаправляем на профиль
    save_data(data)
    return RedirectResponse(url=f"/profile/{user_id}", status_code=303)

@app.post("/update_order")
async def update_order(request: Request, payload: dict = Body(...)):
    user_id = request.cookies.get("user_id")
    if not user_id:
        return {"status": "error", "message": "Пользователь не авторизован."}
    data = load_data()
    user = data.get("users", {}).get(user_id)
    if not user:
        return {"status": "error", "message": "Пользователь не авторизован."}
    order = payload.get("order")
    if not order or not isinstance(order, list):
        return {"status": "error", "message": "Неверный формат данных."}
    tokens = user.get("tokens", [])
    token_dict = { token["token"]: token for token in tokens }
    new_tokens = [token_dict[t] for t in order if t in token_dict]
    if len(new_tokens) != len(tokens):
        for token in tokens:
            if token["token"] not in order:
                new_tokens.append(token)
    user["tokens"] = new_tokens
    save_data(data)
    return {"status": "ok", "message": "Порядок обновлён"}


@app.get("/mint", response_class=HTMLResponse)
async def web_mint(request: Request):
    user_id = require_web_login(request)
    if not user_id:
        return RedirectResponse(url="/", status_code=303)

    data = load_data()
    user = data["users"][user_id]

    # Сброс по дню
    today = datetime.date.today().isoformat()
    if user.get("last_activation_date") != today:
        user["last_activation_date"] = today
        user["activation_count"] = 0
        user.setdefault("extra_attempt_entries", [])

    # Чистим устаревшие и считаем оставшиеся
    extra = cleanup_expired_attempts(user)
    base_daily_limit = 0
    used = user.get("activation_count", 0)
    attempts_left = (base_daily_limit + extra) - used
    balance = user.get("balance", 0)

    recent_tokens = sorted(
        user.get("tokens", []),
        key=lambda t: t.get("timestamp", ""),
        reverse=True
    )[:5]

    # Сохраняем, чтобы обновлённые записи extra_attempt_entries попали в БД
    save_data(data)

    return templates.TemplateResponse("mint.html", {
        "request":       request,
        "user_id":       user_id,
        "attempts_left": max(0, attempts_left),
        "balance":       balance,
        "error":         None,
        "recent_tokens": recent_tokens
    })


@app.post("/mint", response_class=HTMLResponse)
async def web_mint_post(request: Request, user_id: str = Form(None)):
    if not user_id or not require_web_login(request):
        return HTMLResponse("Ошибка: не найден Telegram ID.", status_code=400)

    data = load_data()
    user = ensure_user(data, user_id)

    # Сброс по дню
    today = datetime.date.today().isoformat()
    if user.get("last_activation_date") != today:
        user["last_activation_date"] = today
        user["activation_count"] = 0
        user.setdefault("extra_attempt_entries", [])

    # Удаляем просроченные и считаем оставшиеся
    extra = cleanup_expired_attempts(user)
    base_daily_limit = 0
    used = user.get("activation_count", 0)
    attempts_left = (base_daily_limit + extra) - used

    if attempts_left > 0:
        # бесплатный mint
        user["activation_count"] += 1
        token_data = generate_number()
        token_data["timestamp"] = datetime.datetime.now().isoformat()
        user.setdefault("tokens", []).append(token_data)
        save_data(data)
        return RedirectResponse(url=f"/profile/{user_id}", status_code=303)

    # платный mint
    if user.get("balance", 0) < 100:
        # недостаточно алмазов — ререндерим страницу с ошибкой
        recent_tokens = sorted(
            user.get("tokens", []),
            key=lambda t: t.get("timestamp", ""),
            reverse=True
        )[:5]
        save_data(data)
        return templates.TemplateResponse("mint.html", {
            "request":       request,
            "user_id":       user_id,
            "attempts_left": 0,
            "balance":       user.get("balance", 0),
            "error":         "Недостаточно алмазов для платного создания номера.",
            "recent_tokens": recent_tokens
        })

    # списываем 100 алмазов и создаём
    user["balance"] -= 100
    token_data = generate_number()
    token_data["timestamp"] = datetime.datetime.now().isoformat()
    user.setdefault("tokens", []).append(token_data)
    save_data(data)
    return RedirectResponse(url=f"/profile/{user_id}", status_code=303)

@app.get("/token/{token_value}", response_class=HTMLResponse)
async def token_detail(request: Request, token_value: str):
    data = load_data()
    matching_tokens = []
    for uid, user in data.get("users", {}).items():
        for token in user.get("tokens", []):
            if token.get("token") == token_value:
                matching_tokens.append({
                    "token": token,
                    "owner_id": uid,
                    "source": "collection"
                })
    for listing in data.get("market", []):
        token = listing.get("token")
        if token and token.get("token") == token_value:
            matching_tokens.append({
                "token": token,
                "owner_id": listing.get("seller_id"),
                "source": "market",
                "price": listing.get("price")
            })
    for auction in data.get("auctions", []):
        token = auction.get("token")
        if token and token.get("token") == token_value:
            matching_tokens.append({
                "token": token,
                "owner_id": auction.get("seller_id"),
                "source": "auction",
                "auction_status": auction.get("status"),
                "current_bid": auction.get("current_bid")
            })
    if matching_tokens:
        return templates.TemplateResponse("token_detail.html", {
            "request": request,
            "token_value": token_value,
            "tokens": matching_tokens,
            "error": None
        })
    else:
        return templates.TemplateResponse("token_detail.html", {
            "request": request,
            "token_value": token_value,
            "tokens": [],
            "error": "Токен не найден."
        })

# --- FastAPI: эндпоинт для веб-формы обмена на /profile ---
@app.post("/swap49")
async def swap49_web(request: Request,
                     user_id: str = Form(...),
                     token_index: int = Form(...)):
    # Проверка авторизации
    cookie_uid = request.cookies.get("user_id")
    if cookie_uid != user_id or not require_web_login(request):
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JSONResponse({"success": False, "error": "auth", 
                                 "message": "Ошибка: не авторизован."},
                                status_code=403)
        return HTMLResponse("Ошибка: не авторизован.", status_code=403)

    data = load_data()
    user = data.get("users", {}).get(user_id)
    if not user:
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JSONResponse({"success": False, "error": "no_user", 
                                 "message": "Пользователь не найден."},
                                status_code=404)
        return HTMLResponse("Пользователь не найден.", status_code=404)

    tokens = user.get("tokens", [])
    idx = token_index - 1
    if idx < 0 or idx >= len(tokens):
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JSONResponse({"success": False, "error": "bad_index", 
                                 "message": "Неверный индекс номера."},
                                status_code=400)
        return HTMLResponse("Неверный индекс номера.", status_code=400)

    token = tokens[idx]
    created = datetime.datetime.fromisoformat(token["timestamp"])
    if (datetime.datetime.now() - created) > datetime.timedelta(days=7):
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JSONResponse({"success": False, "error": "expired", 
                                 "message": "Нельзя обменять номер — прошло более 7 дней."},
                                status_code=400)
        return HTMLResponse("Обмен запрещён: номер старше 7 дней.", status_code=400)

    # Собственно обмен
    tokens.pop(idx)
    user["balance"] = user.get("balance", 0) + 49
    save_data(data)

    # Возвращаем результат
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JSONResponse({"success": True, "new_balance": user["balance"]})
    return RedirectResponse(url=f"/profile/{user_id}", status_code=303)

@app.get("/transfer", response_class=HTMLResponse)
async def transfer_page(request: Request):
    if not require_web_login(request):
        return RedirectResponse(url="/", status_code=303)
    return templates.TemplateResponse("transfer.html", {"request": request})

@app.post("/transfer", response_class=HTMLResponse)
async def transfer_post(
    request: Request,
    user_id: str = Form(None),
    token_index: int = Form(...),
    target_id: str = Form(...)
):
    # если в форме нет — берём из куки
    if not user_id:
        user_id = request.cookies.get("user_id")

    if not user_id or not require_web_login(request):
        return HTMLResponse("Ошибка: не найден Telegram ID. Пожалуйста, войдите.", status_code=400)

    # резолвим target_id по скрещённому номеру
    data = load_data()
    resolved_id = None
    for uid, u in data.get("users", {}).items():
        if u.get("crossed_number", {}).get("token") == target_id:
            resolved_id = uid
            break
    if resolved_id is None:
        resolved_id = target_id

    sender = data.get("users", {}).get(user_id)
    if not sender:
        return HTMLResponse("Пользователь не найден.", status_code=404)

    tokens = sender.get("tokens", [])
    if token_index < 1 or token_index > len(tokens):
        return HTMLResponse("Неверный номер из вашей коллекции.", status_code=400)

    token = tokens.pop(token_index - 1)
    if sender.get("custom_number", {}).get("token") == token["token"]:
        del sender["custom_number"]
    save_data(data)

    receiver = ensure_user(data, resolved_id)
    receiver.setdefault("tokens", []).append(token)
    save_data(data)

    sender_name = sender.get("username", "Неизвестный")
    try:
        await bot.send_message(
            int(resolved_id),
            f"Вам передали коллекционный номер: {token['token']}!\nОтправитель: {sender_name} (ID: {user_id})"
        )
    except Exception:
        pass

    # при рендере можно показать, что вы передали `target_id` (как ввёл юзер)
    return templates.TemplateResponse("profile.html", {
        "request": request,
        "user": sender,
        "user_id": user_id,
        "message": f"Номер {token['token']} передан пользователю {target_id}."
    })

@app.get("/sell", response_class=HTMLResponse)
async def web_sell(request: Request):
    if not require_web_login(request):
        return RedirectResponse(url="/", status_code=303)
    return templates.TemplateResponse("sell.html", {"request": request})

@app.post("/sell", response_class=HTMLResponse)
async def web_sell_post(request: Request, user_id: str = Form(None), token_index: int = Form(...), price: int = Form(...)):
    if not user_id:
        user_id = request.cookies.get("user_id")
    if not user_id or not require_web_login(request):
        return HTMLResponse("Ошибка: не найден Telegram ID. Пожалуйста, войдите.", status_code=400)
    data = load_data()
    user = data.get("users", {}).get(user_id)
    if not user:
        return HTMLResponse("Пользователь не найден.", status_code=404)
    tokens = user.get("tokens", [])
    if token_index < 1 or token_index > len(tokens):
        return HTMLResponse("Неверный номер из вашей коллекции.", status_code=400)
    token = tokens.pop(token_index - 1)
    if user.get("custom_number") and user["custom_number"].get("token") == token["token"]:
        del user["custom_number"]
    if "market" not in data:
        data["market"] = []
    listing = {
        "seller_id": user_id,
        "token": token,
        "price": price,
        "timestamp": datetime.datetime.now().isoformat()
    }
    data["market"].insert(0, listing)
    save_data(data)
    return RedirectResponse(url="/", status_code=303)

@app.get("/cross", response_class=HTMLResponse)
async def cross_page(request: Request):
    user_id = request.cookies.get("user_id")
    data = load_data()
    user = data.get("users", {}).get(user_id) if user_id else None
    return templates.TemplateResponse("cross.html", {
        "request": request,
        "user": user,
        "user_id": user_id
    })

@app.post("/cross")
async def cross_submit(
    user_id: str   = Form(...),
    order:   str   = Form(...),   # новое поле с порядком "tok1,tok2,…"
    request: Request = None
):
    # Проверка авторизации
    if request and request.cookies.get("user_id") != user_id:
        return HTMLResponse("Ошибка: не авторизован.", status_code=403)

    data = load_data()
    user = data["users"][user_id]

    # Проверяем баланс
    if user.get("balance", 0) < 199:
        return RedirectResponse(url="/cross?error=Недостаточно+алмазов", status_code=303)

    # Разбиваем строку "tok1,tok2,..." в список
    tokens = [t for t in order.split(',') if t]

    # Проверяем, что выбрано 2–3 токена
    if not (2 <= len(tokens) <= 3):
        return RedirectResponse(url="/cross?error=Неверный+порядок", status_code=303)

    # Списываем алмазы и создаём новый токен в том же порядке
    user["balance"] -= 199
    new_token = '+' + ''.join(tokens)

    user["crossed_number"] = {
        "token": new_token,
        "text_color": "#000000",
        "bg_color": "#ffffff",
        "bg_is_image": False,
        "text_rarity": "3%",
        "bg_rarity": "3%",
        "overall_rarity": "обычно"
    }

    save_data(data)
    return RedirectResponse(url=f"/profile/{user_id}", status_code=303)

@app.get("/participants", response_class=HTMLResponse)
async def web_participants(request: Request):
    if not require_web_login(request):
        return RedirectResponse(url="/", status_code=303)
    data = load_data()
    users = data.get("users", {})
    current_user_id = request.cookies.get("user_id")
    
    sorted_total = sorted(users.items(),
                          key=lambda item: len(item[1].get("tokens", [])),
                          reverse=True)
    sorted_total_enum = list(enumerate(sorted_total, start=1))
    
    def count_rare_tokens(user, threshold=1.0):
        rare_count = 0
        for token in user.get("tokens", []):
            try:
                rarity_value = float(token.get("overall_rarity", "100%").replace("%", "").replace(",", "."))
            except Exception:
                rarity_value = 3.0
            if rarity_value <= threshold:
                rare_count += 1
        return rare_count

    sorted_rare = sorted(users.items(),
                         key=lambda item: count_rare_tokens(item[1], threshold=1.0),
                         reverse=True)
    sorted_rare_enum = [(i, uid, user, count_rare_tokens(user, threshold=1.0))
                         for i, (uid, user) in enumerate(sorted_rare, start=1)]
    
    current_total = next(((pos, uid, user) for pos, (uid, user) in sorted_total_enum if uid == current_user_id), None)
    all_total = [(pos, uid, user) for pos, (uid, user) in sorted_total_enum]
    current_rare = next(((pos, uid, user, rare_count) for pos, uid, user, rare_count in sorted_rare_enum if uid == current_user_id), None)
    all_rare = sorted_rare_enum
    
    return templates.TemplateResponse("participants.html", {
        "request": request,
        "current_user_id": current_user_id,
        "current_total": current_total,
        "all_total": all_total,
        "current_rare": current_rare,
        "all_rare": all_rare
    })

@app.get("/market", response_class=HTMLResponse)
async def web_market(request: Request):
    data = load_data()
    market = data.get("market", [])
    return templates.TemplateResponse("market.html", {"request": request, "market": market, "users": data.get("users", {}), "buyer_id": request.cookies.get("user_id")})

@app.post("/buy/{listing_id}")
async def web_buy(request: Request, listing_id: str, buyer_id: str = Form(None)):
    if not buyer_id:
        buyer_id = request.cookies.get("user_id")
    if not buyer_id or not require_web_login(request):
        return HTMLResponse(
            "Ошибка: не найден Telegram ID. Пожалуйста, войдите.",
            status_code=400
        )

    data = load_data()
    market = data.get("market", [])
    listing_index = next(
        (i for i, lst in enumerate(market) if lst["token"].get("token") == listing_id),
        None
    )
    if listing_index is None:
        return HTMLResponse("Неверный номер листинга.", status_code=400)

    listing = market[listing_index]
    seller_id = listing.get("seller_id")
    price = listing["price"]

    buyer = data.get("users", {}).get(buyer_id)
    if not buyer:
        return HTMLResponse("Покупатель не найден.", status_code=404)

    # Проверяем баланс
    if buyer.get("balance", 0) < price:
        # Для AJAX-запроса вернём JSON с ошибкой, иначе редирект
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JSONResponse({"error": "Недостаточно средств"}, status_code=402)
        return RedirectResponse(url=f"/?error=Недостаточно%20средств", status_code=303)

    # Спишем средства и переведём токен
    buyer["balance"] -= price
    seller = data.get("users", {}).get(seller_id)
    if seller:
        seller["balance"] = seller.get("balance", 0) + price
        if seller.get("custom_number") and seller["custom_number"].get("token") == listing_id:
            del seller["custom_number"]

    # Начислим комиссию рефереру, если есть
    if "referrer" in buyer:
        commission = int(price * 0.05)
        referrer = data["users"].get(buyer["referrer"])
        if referrer:
            referrer["balance"] = referrer.get("balance", 0) + commission

    # Переносим токен в коллекцию покупателя
    token = listing["token"]
    token.update({
        "bought_price": price,
        "bought_date": datetime.datetime.now().isoformat(),
        "bought_source": "market",
        "seller_id": seller_id
    })
    buyer.setdefault("tokens", []).append(token)
    market.pop(listing_index)
    save_data(data)

    # Уведомление продавцу
    if seller:
        try:
            await bot.send_message(
                int(seller_id),
                f"Уведомление: Ваш номер {token['token']} куплен за {price} 💎."
            )
        except Exception as e:
            print("Ошибка уведомления продавца:", e)

    # Возвращаем ответ в зависимости от типа запроса
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JSONResponse({"new_balance": buyer["balance"]})
    else:
        return RedirectResponse(url="/", status_code=303)

@app.get("/assets", response_class=HTMLResponse)
async def all_assets_page(request: Request):
    data = load_data()
    all_purchased_tokens = []
    for uid, user_data in data.get("users", {}).items():
        for t in user_data.get("tokens", []):
            if t.get("bought_price"):
                all_purchased_tokens.append({
                    "owner_id": uid,
                    "owner_username": user_data.get("username", uid),
                    "token": t
                })
    all_purchased_tokens.sort(
        key=lambda x: x["token"].get("bought_date", ""),
        reverse=True
    )
    return templates.TemplateResponse("assets_global.html", {
        "request": request,
        "all_purchased_tokens": all_purchased_tokens
    })

@app.post("/updateprice")
async def web_updateprice(request: Request, market_index: str = Form(...), new_price: int = Form(...)):
    user_id = request.cookies.get("user_id")
    if not user_id or not require_web_login(request):
        return HTMLResponse("Ошибка: не найден Telegram ID. Пожалуйста, войдите.", status_code=400)
    data = load_data()
    market = data.get("market", [])
    listing_index = None
    for i, listing in enumerate(market):
        if listing["token"].get("token") == market_index:
            listing_index = i
            break
    if listing_index is None:
        return HTMLResponse("❗ Неверный номер листинга.", status_code=400)
    listing = market[listing_index]
    if listing.get("seller_id") != user_id:
        return HTMLResponse("❗ Вы не являетесь продавцом этого номера.", status_code=403)
    market[listing_index]["price"] = new_price
    save_data(data)
    return RedirectResponse(url="/", status_code=303)

@app.post("/withdraw", response_class=HTMLResponse)
async def web_withdraw(request: Request, market_index: str = Form(...)):
    user_id = request.cookies.get("user_id")
    if not user_id or not require_web_login(request):
        return HTMLResponse("Ошибка: не найден Telegram ID. Пожалуйста, войдите.", status_code=400)
    data = load_data()
    market = data.get("market", [])
    listing_index = None
    for i, listing in enumerate(market):
        if listing["token"].get("token") == market_index:
            listing_index = i
            break
    if listing_index is None:
        return HTMLResponse("❗ Неверный номер листинга.", status_code=400)
    listing = market.pop(listing_index)
    if listing.get("seller_id") != user_id:
        return HTMLResponse("❗ Вы не являетесь продавцом этого номера.", status_code=403)
    user = data.get("users", {}).get(user_id)
    if user:
        user.setdefault("tokens", []).append(listing["token"])
    save_data(data)
    return RedirectResponse(url=f"/profile/{user_id}", status_code=303)
    
# --- Эндпоинты для установки/снятия профильного номера ---
@app.post("/set_profile_token", response_class=HTMLResponse)
async def set_profile_token(request: Request, user_id: str = Form(...), token_index: int = Form(...)):
    # Проверяем, что пользователь — хозяин профиля
    cookie_user_id = request.cookies.get("user_id")
    if cookie_user_id != user_id or not require_web_login(request):
        return HTMLResponse("Вы не можете изменять чужой профиль.", status_code=403)

    data = load_data()
    user = data.get("users", {}).get(user_id)
    if not user:
        return HTMLResponse("Пользователь не найден", status_code=404)

    tokens = user.get("tokens", [])
    if token_index < 1 or token_index > len(tokens):
        return HTMLResponse("Неверный индекс номера", status_code=400)

    # Сохраняем только UUID:
    chosen = tokens[token_index - 1]
    user["custom_number_uuid"] = chosen["uuid"]
    # Удаляем старый объект, если он был
    user.pop("custom_number", None)

    save_data(data)
    return RedirectResponse(url=f"/profile/{user_id}", status_code=303)


@app.post("/remove_profile_token", response_class=HTMLResponse)
async def remove_profile_token(request: Request, user_id: str = Form(...)):
    # Проверяем, что пользователь — хозяин профиля
    cookie_user_id = request.cookies.get("user_id")
    if cookie_user_id != user_id or not require_web_login(request):
        return HTMLResponse("Вы не можете изменять чужой профиль.", status_code=403)

    data = load_data()
    user = data.get("users", {}).get(user_id)
    if not user:
        return HTMLResponse("Пользователь не найден", status_code=404)

    # Убираем UUID и объект
    user.pop("custom_number_uuid", None)
    user.pop("custom_number", None)

    save_data(data)
    return RedirectResponse(url=f"/profile/{user_id}", status_code=303)

# --------------------- Запуск бота и веб-сервера ---------------------
async def main():
    # Запускаем бота
    bot_task = asyncio.create_task(dp.start_polling(bot))
    # Запускаем функцию автоотмены обменов
    auto_cancel_task = asyncio.create_task(auto_cancel_exchanges())
    # Регистрируем фоновую задачу аукционов через функцию register_auction_tasks из auctions.py
    register_auction_tasks(asyncio.get_event_loop())
    # Запуск веб-сервера
    config = uvicorn.Config(app, host="0.0.0.0", port=8000, log_level="info")
    server = uvicorn.Server(config)
    web_task = asyncio.create_task(server.serve())
    await asyncio.gather(bot_task, auto_cancel_task, web_task)

if __name__ == "__main__":
    asyncio.run(main())
