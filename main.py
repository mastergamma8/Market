import os
import json
import random
import itertools
import datetime
import asyncio
import hashlib
import hmac
import urllib.parse
from typing import Tuple

from aiogram import Bot, Dispatcher
from aiogram.client.bot import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import Message

# Импорт для веб-приложения
import uvicorn
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# Замените на токен вашего бота
BOT_TOKEN = "7846917008:AAGaj9ZsWnb_2GmZC0q7YqTQEV39l0eBHxs"
DATA_FILE = "data.json"

# Инициализация бота (aiogram)
bot = Bot(
    token=BOT_TOKEN,
    default_bot_properties=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()

# Функции работы с данными
def load_data() -> dict:
    """Загружает данные из JSON-файла."""
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, "r", encoding="utf-8") as file:
        try:
            return json.load(file)
        except json.JSONDecodeError:
            return {}

def save_data(data: dict) -> None:
    """Сохраняет данные в JSON-файл."""
    with open(DATA_FILE, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)

def ensure_user(data: dict, user_id: str, username: str = "Unknown", photo_url: str = None) -> dict:
    """
    Проверяет, существует ли запись пользователя по user_id.
    Если нет – создаёт её с начальными значениями.
    """
    today = datetime.date.today().isoformat()
    if "users" not in data:
        data["users"] = {}
    if user_id not in data["users"]:
        data["users"][user_id] = {
            "last_activation_date": today,
            "activation_count": 0,
            "tokens": [],
            "balance": 1000,
            "username": username,
            "photo_url": photo_url,
            "login_code": None,
            "code_expiry": None
        }
    return data["users"][user_id]

def beauty_score(num_str: str) -> int:
    """Вычисляет «красоту» номера."""
    zeros = num_str.count("0")
    max_repeats = max(len(list(group)) for _, group in itertools.groupby(num_str))
    bonus = 6 - len(num_str)
    return zeros + max_repeats + bonus

def generate_number() -> Tuple[str, int]:
    """Генерирует номер с учетом редкости."""
    while True:
        length = random.choices([3, 4, 5, 6], weights=[1, 2, 3, 4])[0]
        candidate = "".join(random.choices("0123456789", k=length))
        score = beauty_score(candidate)
        if random.random() < 1 / (score + 1):
            return candidate, score

def generate_login_code() -> str:
    """Генерирует 6-значный код для подтверждения входа."""
    return str(random.randint(100000, 999999))

# --------------------- Telegram Bot Handlers ---------------------
@dp.message(Command("start"))
async def start_cmd(message: Message) -> None:
    data = load_data()
    user = ensure_user(data, str(message.from_user.id),
                        message.from_user.username or message.from_user.first_name)
    save_data(data)
    text = (
        "🎉 Добро пожаловать в Market коллекционных номеров! 🎉\n\n"
        "Чтобы войти в аккаунт, используйте команду /login <Ваш Telegram ID>.\n"
        "После этого бот отправит вам код подтверждения, который нужно ввести на сайте.\n"
        "Также доступны следующие команды:\n"
        "• /mint, /collection, /balance, /sell, /market, /buy, /participants, /exchange."
    )
    await message.answer(text)

@dp.message(Command("login"))
async def login_cmd(message: Message) -> None:
    """
    Команда /login <ID> инициирует отправку кода подтверждения на указанный Telegram ID.
    Если ID совпадает с вашим (message.from_user.id), код будет отправлен на ваш аккаунт.
    """
    parts = message.text.split()
    if len(parts) != 2:
        await message.answer("❗ Формат: /login <Ваш Telegram ID>")
        return
    user_id = parts[1]
    # Для безопасности проверяем, что ID из команды совпадает с ID отправителя
    if user_id != str(message.from_user.id):
        await message.answer("❗ Вы можете войти только в свой аккаунт.")
        return
    data = load_data()
    user = ensure_user(data, user_id,
                       message.from_user.username or message.from_user.first_name)
    # Генерируем код и устанавливаем время истечения (например, 5 минут)
    code = generate_login_code()
    expiry = (datetime.datetime.now() + datetime.timedelta(minutes=5)).timestamp()
    user["login_code"] = code
    user["code_expiry"] = expiry
    save_data(data)
    # Отправляем код на Telegram
    try:
        await bot.send_message(int(user_id), f"Ваш код для входа: {code}")
        await message.answer("Код подтверждения отправлен на ваш Telegram. Введите его на сайте для входа.")
    except Exception as e:
        await message.answer("Ошибка при отправке кода. Попробуйте позже.")
        print("Ошибка отправки кода:", e)

# --------------------- Веб-приложение (FastAPI) ---------------------
app = FastAPI()

if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")
templates.env.globals["enumerate"] = enumerate

# Страница входа (если пользователь не авторизован)
@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

# Обработка формы входа: пользователь вводит свой Telegram ID,
# бот отправляет код и затем перенаправляет на страницу подтверждения.
@app.post("/login", response_class=HTMLResponse)
async def login_post(request: Request, user_id: str = Form(...)):
    data = load_data()
    user = ensure_user(data, user_id)
    # Генерируем код и время истечения (5 минут)
    code = generate_login_code()
    expiry = (datetime.datetime.now() + datetime.timedelta(minutes=5)).timestamp()
    user["login_code"] = code
    user["code_expiry"] = expiry
    save_data(data)
    # Отправляем код через бота
    try:
        await bot.send_message(int(user_id), f"Ваш код для входа: {code}")
    except Exception as e:
        return HTMLResponse("Ошибка при отправке кода через Telegram.", status_code=500)
    return templates.TemplateResponse("verify.html", {"request": request, "user_id": user_id})

# Обработка подтверждения кода
@app.post("/verify", response_class=HTMLResponse)
async def verify_post(request: Request, user_id: str = Form(...), code: str = Form(...)):
    data = load_data()
    user = data.get("users", {}).get(user_id)
    if not user:
        return HTMLResponse("Пользователь не найден.", status_code=404)
    # Проверяем срок действия кода
    if user.get("code_expiry", 0) < datetime.datetime.now().timestamp():
        return HTMLResponse("Код устарел. Повторите попытку входа.", status_code=400)
    # Проверяем правильность кода
    if user.get("login_code") != code:
        return HTMLResponse("Неверный код.", status_code=400)
    # Если всё верно – очищаем код и устанавливаем cookie
    user["login_code"] = None
    user["code_expiry"] = None
    save_data(data)
    response = RedirectResponse(url=f"/profile/{user_id}", status_code=303)
    response.set_cookie("user_id", user_id, max_age=60*60*24*30, path="/")
    return response

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    user_id = request.cookies.get("user_id")
    user = None
    if user_id:
        data = load_data()
        user = data.get("users", {}).get(user_id)
    return templates.TemplateResponse("index.html", {"request": request, "user": user, "user_id": user_id})

@app.get("/market", response_class=HTMLResponse)
async def web_market(request: Request):
    data = load_data()
    market = data.get("market", [])
    buyer_id = request.cookies.get("user_id", "")
    return templates.TemplateResponse("market.html", {"request": request, "market": market, "users": data.get("users", {}), "buyer_id": buyer_id})

@app.get("/profile/{user_id}", response_class=HTMLResponse)
async def profile(request: Request, user_id: str):
    data = load_data()
    user = data.get("users", {}).get(user_id)
    if not user:
        return HTMLResponse("Пользователь не найден.", status_code=404)
    return templates.TemplateResponse("profile.html", {"request": request, "user": user, "user_id": user_id})

@app.get("/mint", response_class=HTMLResponse)
async def web_mint(request: Request):
    return templates.TemplateResponse("mint.html", {"request": request})

@app.post("/mint", response_class=HTMLResponse)
async def web_mint_post(request: Request, user_id: str = Form(...)):
    data = load_data()
    user = ensure_user(data, user_id)
    today = datetime.date.today().isoformat()
    if user["last_activation_date"] != today:
        user["last_activation_date"] = today
        user["activation_count"] = 0
    if user["activation_count"] >= 3:
        return templates.TemplateResponse("mint.html", {"request": request, "error": "Вы исчерпали бесплатные активации на сегодня. Попробуйте завтра!", "user_id": user_id})
    user["activation_count"] += 1
    num, score = generate_number()
    entry = {"token": num, "score": score, "timestamp": datetime.datetime.now().isoformat()}
    user["tokens"].append(entry)
    save_data(data)
    return templates.TemplateResponse("profile.html", {"request": request, "user": user, "user_id": user_id})

@app.get("/sell", response_class=HTMLResponse)
async def web_sell(request: Request):
    return templates.TemplateResponse("sell.html", {"request": request})

@app.post("/sell", response_class=HTMLResponse)
async def web_sell_post(request: Request, user_id: str = Form(...), token_index: int = Form(...), price: int = Form(...)):
    data = load_data()
    user = data.get("users", {}).get(user_id)
    if not user:
        return HTMLResponse("Пользователь не найден.", status_code=404)
    tokens = user.get("tokens", [])
    if token_index < 1 or token_index > len(tokens):
        return HTMLResponse("Неверный номер из вашей коллекции.", status_code=400)
    token = tokens.pop(token_index - 1)
    if "market" not in data:
        data["market"] = []
    listing = {
        "seller_id": user_id,
        "token": token,
        "price": price,
        "timestamp": datetime.datetime.now().isoformat()
    }
    data["market"].append(listing)
    save_data(data)
    return templates.TemplateResponse("profile.html", {"request": request, "user": user, "user_id": user_id})

@app.get("/exchange", response_class=HTMLResponse)
async def web_exchange(request: Request):
    return templates.TemplateResponse("exchange.html", {"request": request})

@app.post("/exchange", response_class=HTMLResponse)
async def web_exchange_post(request: Request, user_id: str = Form(...), my_index: int = Form(...), target_id: str = Form(...), target_index: int = Form(...)):
    data = load_data()
    initiator = data.get("users", {}).get(user_id)
    target = data.get("users", {}).get(target_id)
    if not initiator or not target:
        return HTMLResponse("Один из пользователей не найден.", status_code=404)
    my_tokens = initiator.get("tokens", [])
    target_tokens = target.get("tokens", [])
    if my_index < 1 or my_index > len(my_tokens) or target_index < 1 or target_index > len(target_tokens):
        return HTMLResponse("Неверный номер у одного из пользователей.", status_code=400)
    my_token = my_tokens.pop(my_index - 1)
    target_token = target_tokens.pop(target_index - 1)
    my_tokens.append(target_token)
    target_tokens.append(my_token)
    save_data(data)
    return templates.TemplateResponse("profile.html", {"request": request, "user": initiator, "user_id": user_id})

@app.get("/participants", response_class=HTMLResponse)
async def web_participants(request: Request):
    data = load_data()
    users = data.get("users", {})
    return templates.TemplateResponse("participants.html", {"request": request, "users": users})

@app.post("/buy/{listing_index}")
async def web_buy(request: Request, listing_index: int, buyer_id: str = Form(...)):
    data = load_data()
    market = data.get("market", [])
    if listing_index < 0 or listing_index >= len(market):
        return HTMLResponse("Неверный номер листинга.", status_code=400)
    listing = market[listing_index]
    seller_id = listing.get("seller_id")
    price = listing["price"]
    buyer = data.get("users", {}).get(buyer_id)
    if not buyer:
        return HTMLResponse("Покупатель не найден.", status_code=404)
    if buyer.get("balance", 0) < price:
        return HTMLResponse("Недостаточно средств.", status_code=400)
    buyer["balance"] -= price
    seller = data.get("users", {}).get(seller_id)
    if seller:
        seller["balance"] = seller.get("balance", 0) + price
    buyer.setdefault("tokens", []).append(listing["token"])
    market.pop(listing_index)
    save_data(data)
    return templates.TemplateResponse("profile.html", {"request": request, "user": buyer, "user_id": buyer_id})

# --------------------- Запуск бота и веб-сервера ---------------------
async def main():
    bot_task = asyncio.create_task(dp.start_polling(bot))
    config = uvicorn.Config(app, host="0.0.0.0", port=8000, log_level="info")
    server = uvicorn.Server(config)
    web_task = asyncio.create_task(server.serve())
    await asyncio.gather(bot_task, web_task)

if __name__ == "__main__":
    asyncio.run(main())
