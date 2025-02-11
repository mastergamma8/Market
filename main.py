import os
import json
import random
import itertools
import datetime
import asyncio
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

# Функции работы с данными (одинаковые для бота и веб-приложения)
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

def ensure_user(data: dict, message: Message) -> dict:
    """
    Проверяет, существует ли запись пользователя.
    Если нет – создаёт её с начальными значениями.
    """
    user_id = str(message.from_user.id)
    today = datetime.date.today().isoformat()
    if "users" not in data:
        data["users"] = {}
    if user_id not in data["users"]:
        data["users"][user_id] = {
            "last_activation_date": today,
            "activation_count": 0,
            "tokens": [],
            "balance": 1000,  # Начальный баланс
            "username": message.from_user.username or message.from_user.first_name
        }
    return data["users"][user_id]

def beauty_score(num_str: str) -> int:
    """
    Вычисляет «красоту» номера по количеству нулей, максимальной длине последовательности
    одинаковых цифр и бонусу за короткую длину.
    """
    zeros = num_str.count("0")
    max_repeats = max(len(list(group)) for _, group in itertools.groupby(num_str))
    bonus = 6 - len(num_str)
    return zeros + max_repeats + bonus

def generate_number() -> Tuple[str, int]:
    """
    Генерирует номер заданной длины (от 3 до 6 цифр) с учётом редкости.
    Чем выше оценка, тем ниже вероятность принять данный номер.
    """
    while True:
        length = random.choices([3, 4, 5, 6], weights=[1, 2, 3, 4])[0]
        candidate = "".join(random.choices("0123456789", k=length))
        score = beauty_score(candidate)
        if random.random() < 1 / (score + 1):
            return candidate, score

# --------------------- Telegram Bot Handlers ---------------------
@dp.message(Command("start"))
async def start_cmd(message: Message) -> None:
    """
    Команда /start — приветствует пользователя и показывает список доступных команд.
    """
    data = load_data()
    ensure_user(data, message)
    save_data(data)
    text = (
        "🎉 Добро пожаловать в Market коллекционных номеров! 🎉\n\n"
        "💡 Команды:\n"
        "• /mint — создать новый коллекционный номер (бесплатно 3 раза в день) 🚀\n"
        "• /collection — посмотреть свою коллекцию номеров 😎\n"
        "• /balance — узнать баланс 💎\n"
        "• /sell <номер> <цена> — выставить номер на продажу 🛒\n"
        "• /market — просмотреть номера на продаже 🌐\n"
        "• /buy <номер листинга> — купить номер из маркетплейса 💰\n"
        "• /participants — список участников 👥\n"
        "• /exchange <мой номер> <ID пользователя> <их номер> — обмен номерами 🔄\n"
        "\nТакже откройте наш <a href='http://<YOUR_GLITCH_APP_URL>'>маркетплейс</a> для удобного управления!"
    )
    await message.answer(text)

@dp.message(Command("mint"))
async def mint_number(message: Message) -> None:
    """
    Команда /mint — создаёт новый коллекционный номер.
    Бесплатно доступно 3 активации в день.
    """
    data = load_data()
    user = ensure_user(data, message)
    today = datetime.date.today().isoformat()
    if user["last_activation_date"] != today:
        user["last_activation_date"] = today
        user["activation_count"] = 0
    if user["activation_count"] >= 3:
        await message.answer("😔 Вы исчерпали бесплатные активации на сегодня. Попробуйте завтра!")
        return
    user["activation_count"] += 1
    num, score = generate_number()
    entry = {"token": num, "score": score, "timestamp": datetime.datetime.now().isoformat()}
    user["tokens"].append(entry)
    save_data(data)
    reply = (
        f"✨ Ваш новый коллекционный номер: {num}\n"
        f"🔥 Оценка: {score}\n"
        f"🔢 Активация: {user['activation_count']}/3 за сегодня."
    )
    await message.answer(reply)

@dp.message(Command("collection"))
async def show_collection(message: Message) -> None:
    """Команда /collection — выводит коллекцию номеров пользователя."""
    data = load_data()
    user = ensure_user(data, message)
    tokens = user.get("tokens", [])
    if not tokens:
        await message.answer("😕 У вас пока нет номеров. Используйте /mint для создания.")
        return
    msg = "🎨 Ваша коллекция номеров:\n" + "\n".join(
        f"{idx}. {t['token']} | Оценка: {t['score']} | {t['timestamp']}"
        for idx, t in enumerate(tokens, start=1)
    )
    await message.answer(msg)

@dp.message(Command("balance"))
async def show_balance(message: Message) -> None:
    """Команда /balance — показывает баланс пользователя."""
    data = load_data()
    user = ensure_user(data, message)
    await message.answer(f"💎 Ваш баланс: {user.get('balance', 0)} 💎")

@dp.message(Command("sell"))
async def sell_number(message: Message) -> None:
    """
    Команда /sell <номер> <цена> — выставляет выбранный номер на продажу.
    Пример: /sell 2 500
    """
    parts = message.text.split()
    if len(parts) != 3:
        await message.answer("❗ Формат: /sell номер цена (например, /sell 2 500)")
        return
    try:
        index = int(parts[1]) - 1
        price = int(parts[2])
    except ValueError:
        await message.answer("❗ Проверьте формат номера и цены.")
        return
    data = load_data()
    user = ensure_user(data, message)
    tokens = user.get("tokens", [])
    if index < 0 or index >= len(tokens):
        await message.answer("❗ Неверный номер из вашей коллекции.")
        return
    item = tokens.pop(index)
    if "market" not in data:
        data["market"] = []
    listing = {
        "seller_id": str(message.from_user.id),
        "token": item,
        "price": price,
        "timestamp": datetime.datetime.now().isoformat()
    }
    data["market"].append(listing)
    save_data(data)
    await message.answer(f"🚀 Номер {item['token']} выставлен на продажу за {price} 💎!")

@dp.message(Command("market"))
async def show_market(message: Message) -> None:
    """Команда /market — показывает номера на продаже."""
    data = load_data()
    market = data.get("market", [])
    if not market:
        await message.answer("🌐 На маркетплейсе нет активных продаж.")
        return
    msg = "🌐 Номера на продаже:\n"
    for idx, listing in enumerate(market, start=1):
        seller_id = listing.get("seller_id")
        seller_name = data.get("users", {}).get(seller_id, {}).get("username", seller_id)
        item = listing["token"]
        msg += f"{idx}. {item['token']} | Оценка: {item['score']} | Цена: {listing['price']} 💎 | Продавец: {seller_name}\n"
    await message.answer(msg)

@dp.message(Command("buy"))
async def buy_number(message: Message) -> None:
    """
    Команда /buy <номер листинга> — покупка номера из маркетплейса.
    Пример: /buy 1
    """
    parts = message.text.split()
    if len(parts) != 2:
        await message.answer("❗ Формат: /buy номер_листинга (например, /buy 1)")
        return
    try:
        listing_index = int(parts[1]) - 1
    except ValueError:
        await message.answer("❗ Неверный формат номера листинга.")
        return
    data = load_data()
    market = data.get("market", [])
    if listing_index < 0 or listing_index >= len(market):
        await message.answer("❗ Неверный номер листинга.")
        return
    listing = market[listing_index]
    seller_id = listing.get("seller_id")
    price = listing["price"]
    buyer_id = str(message.from_user.id)
    buyer = ensure_user(data, message)
    if buyer_id == seller_id:
        await message.answer("❗ Нельзя купить свой номер!")
        return
    if buyer.get("balance", 0) < price:
        await message.answer("😔 Недостаточно средств для покупки.")
        return
    buyer["balance"] -= price
    seller = data.get("users", {}).get(seller_id)
    if seller:
        seller["balance"] = seller.get("balance", 0) + price
    buyer.setdefault("tokens", []).append(listing["token"])
    market.pop(listing_index)
    save_data(data)
    await message.answer(
        f"🎉 Вы купили номер {listing['token']['token']} за {price} 💎!\nНовый баланс: {buyer['balance']} 💎."
    )
    if seller:
        try:
            await bot.send_message(int(seller_id),
                                   f"Уведомление: Ваш номер {listing['token']['token']} куплен за {price} 💎.")
        except Exception as e:
            print("Ошибка уведомления продавца:", e)

@dp.message(Command("participants"))
async def list_participants(message: Message) -> None:
    """Команда /participants — выводит список участников."""
    data = load_data()
    users = data.get("users", {})
    if not users:
        await message.answer("❗ Нет зарегистрированных участников.")
        return
    msg = "👥 Участники:\n"
    for uid, info in users.items():
        cnt = len(info.get("tokens", []))
        msg += f"{info.get('username', 'Неизвестный')} (ID: {uid}) — Баланс: {info.get('balance', 0)} 💎, номеров: {cnt}\n"
    await message.answer(msg)

@dp.message(Command("exchange"))
async def exchange_numbers(message: Message) -> None:
    """
    Команда /exchange <мой номер> <ID пользователя> <их номер> — обмен номерами.
    Пример: /exchange 1 123456789 2
    """
    parts = message.text.split()
    if len(parts) != 4:
        await message.answer("❗ Формат: /exchange <мой номер> <ID пользователя> <их номер>")
        return
    try:
        my_index = int(parts[1]) - 1
        target_uid = parts[2]
        target_index = int(parts[3]) - 1
    except ValueError:
        await message.answer("❗ Проверьте, что индексы и ID числа.")
        return
    data = load_data()
    initiator = ensure_user(data, message)
    if target_uid == str(message.from_user.id):
        await message.answer("❗ Нельзя обмениваться с самим собой!")
        return
    target = data.get("users", {}).get(target_uid)
    if not target:
        await message.answer("❗ Пользователь не найден.")
        return
    my_tokens = initiator.get("tokens", [])
    target_tokens = target.get("tokens", [])
    if my_index < 0 or my_index >= len(my_tokens):
        await message.answer("❗ Неверный номер вашего номера.")
        return
    if target_index < 0 or target_index >= len(target_tokens):
        await message.answer("❗ Неверный номер у пользователя.")
        return
    my_item = my_tokens.pop(my_index)
    target_item = target_tokens.pop(target_index)
    my_tokens.append(target_item)
    target_tokens.append(my_item)
    save_data(data)
    await message.answer(
        f"🎉 Обмен завершён!\nВы отдали номер {my_item['token']} и получили {target_item['token']}."
    )
    try:
        await bot.send_message(
            int(target_uid),
            f"🔄 Пользователь {initiator.get('username', 'Неизвестный')} обменял с вами номера.\n"
            f"Вы отдали {target_item['token']} и получили {my_item['token']}."
        )
    except Exception as e:
        print("Ошибка уведомления партнёра:", e)

# --------------------- Мини-приложение (FastAPI) ---------------------
app = FastAPI()

if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")
templates.env.globals["enumerate"] = enumerate

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/market", response_class=HTMLResponse)
async def web_market(request: Request):
    data = load_data()
    market = data.get("market", [])
    return templates.TemplateResponse("market.html", {"request": request, "market": market, "users": data.get("users", {})})

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
    if "users" not in data:
        data["users"] = {}
    if user_id not in data["users"]:
        data["users"][user_id] = {
            "last_activation_date": datetime.date.today().isoformat(),
            "activation_count": 0,
            "tokens": [],
            "balance": 1000,
            "username": user_id
        }
    user = data["users"][user_id]
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
    return RedirectResponse(url=f"/profile/{user_id}", status_code=303)

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
    return RedirectResponse(url=f"/profile/{user_id}", status_code=303)

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
    return RedirectResponse(url=f"/profile/{user_id}", status_code=303)

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
    return RedirectResponse(url=f"/profile/{buyer_id}", status_code=303)

# --------------------- Запуск бота и веб-сервера ---------------------
async def main():
    bot_task = asyncio.create_task(dp.start_polling(bot))
    config = uvicorn.Config(app, host="0.0.0.0", port=8000, log_level="info")
    server = uvicorn.Server(config)
    web_task = asyncio.create_task(server.serve())
    await asyncio.gather(bot_task, web_task)

if __name__ == "__main__":
    asyncio.run(main())
