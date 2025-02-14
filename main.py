import os
import json
import random
import itertools
import math
import datetime
import asyncio
import hashlib
import hmac
import urllib.parse
from typing import Tuple
from functools import wraps

from aiogram import Bot, Dispatcher, F
from aiogram.client.bot import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.types.input_file import FSInputFile  # Для отправки файлов

# Импорт для веб‑приложения
import uvicorn
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# Замените на токен вашего бота
BOT_TOKEN = "7846917008:AAGaj9ZsWnb_2GmZC0q7YqTQEV39l0eBHxs"
DATA_FILE = "data.json"
ADMIN_IDS = {"1809630966", "7053559428"}
BOT_USERNAME = "TestMacprobot"

# Инициализация бота (aiogram)
bot = Bot(
    token=BOT_TOKEN,
    default_bot_properties=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()

# --- Функции для работы с данными ---
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
        # Новый пользователь – по умолчанию не залогинен
        data["users"][user_id] = {
            "last_activation_date": today,
            "activation_count": 0,
            "tokens": [],
            "balance": 1000,
            "username": username,
            "photo_url": photo_url,
            "logged_in": False,
            "login_code": None,
            "code_expiry": None,
            "verified": False
        }
    return data["users"][user_id]

# --- Функции для вычисления редкости номера, цвета цифр и фона ---
def compute_number_rarity(token_str: str) -> str:
    length = len(token_str)
    max_repeats = max(len(list(group)) for _, group in itertools.groupby(token_str))
    base_score = 10 - length  # Чем меньше цифр, тем больше бонус
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
    if r < 0.001:
        text_pool = ["#FFFFFF", "#000000"]
        text_rarity = "0.1%"
    elif r < 0.01:
        text_pool = ["#FFD700", "#C0C0C0"]
        text_rarity = "0.5%"
    elif r < 0.03:
        text_pool = ["#1abc9c", "#2ecc71"]
        text_rarity = "1%"
    elif r < 0.06:
        text_pool = ["#3498db", "#9b59b6", "#34495e"]
        text_rarity = "1.5%"
    elif r < 0.16:
        text_pool = ["#FF5733", "#33FFCE"]
        text_rarity = "2%"
    elif r < 0.3:
        text_pool = ["#8e44ad", "#2c3e50"]
        text_rarity = "2.5%"
    else:
        text_pool = ["#d35400", "#e67e22", "#27ae60"]
        text_rarity = "3%"
    return random.choice(text_pool), text_rarity

def generate_bg_attributes() -> tuple:
    r = random.random()
    if r < 0.001:
        bg_pool = ["#FFFFFF", "#000000"]
        bg_rarity = "0.1%"
    elif r < 0.01:
        bg_pool = ["#FF69B4", "#8A2BE2"]
        bg_rarity = "0.5%"
    elif r < 0.03:
        bg_pool = ["#e74c3c", "#e67e22"]
        bg_rarity = "1%"
    elif r < 0.06:
        bg_pool = ["#16a085", "#27ae60"]
        bg_rarity = "1.5%"
    elif r < 0.16:
        bg_pool = ["#f1c40f", "#1abc9c"]
        bg_rarity = "2%"
    elif r < 0.3:
        bg_pool = ["#2ecc71", "#3498db"]
        bg_rarity = "2.5%"
    else:
        bg_pool = ["#9b59b6", "#34495e", "#808000"]
        bg_rarity = "3%"
    return random.choice(bg_pool), bg_rarity

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
    number_rarity = compute_number_rarity(token_str)
    text_color, text_rarity = generate_text_attributes()
    bg_color, bg_rarity = generate_bg_attributes()
    overall_rarity = compute_overall_rarity(number_rarity, text_rarity, bg_rarity)
    return {
        "token": token_str,
        "number_rarity": number_rarity,
        "text_color": text_color,
        "text_rarity": text_rarity,
        "bg_color": bg_color,
        "bg_rarity": bg_rarity,
        "overall_rarity": overall_rarity,
        "timestamp": datetime.datetime.now().isoformat()
    }

def generate_number() -> dict:
    length = random.choice([3, 4, 5, 6])
    token_str = "".join(random.choices("0123456789", k=length))
    return generate_number_from_value(token_str)

def generate_login_code() -> str:
    return str(random.randint(100000, 999999))

# Для шаблонов (в веб‑части)
def get_rarity(score: int) -> str:
    if score > 12:
        return "2.5%"
    elif score > 8:
        return "2%"
    else:
        return "1.5%"

# --- Декоратор для проверки авторизации пользователя ---
def require_login(func):
    @wraps(func)
    async def wrapper(message: Message, *args, **kwargs):
        data = load_data()
        user = ensure_user(
            data,
            str(message.from_user.id),
            message.from_user.username or message.from_user.first_name
        )
        if not user.get("logged_in"):
            await message.answer(
                "❗ Пожалуйста, зарегистрируйтесь через Telegram‑бота, используя команду /login <Ваш Telegram ID>."
            )
            return
        return await func(message, *args, **kwargs)
    return wrapper

# -------------------- Основные команды бота --------------------
@dp.message(Command("start"))
async def start_cmd(message: Message) -> None:
    data = load_data()
    user = ensure_user(
        data,
        str(message.from_user.id),
        message.from_user.username or message.from_user.first_name
    )
    
    parts = message.text.split(maxsplit=1)
    args = parts[1].strip() if len(parts) > 1 else ""
    
    if args.startswith("redeem_"):
        voucher_code = args[len("redeem_"):]
        voucher = None
        for v in data.get("vouchers", []):
            if v["code"] == voucher_code:
                voucher = v
                break

        if voucher is None:
            await message.answer("❗ Ваучер не найден или недействителен.")
        else:
            if voucher.get("redeemed_count", 0) >= voucher.get("max_uses", 1):
                await message.answer("❗ Этот ваучер уже исчерпан.")
            else:
                redeemed_by = voucher.get("redeemed_by", [])
                if str(message.from_user.id) in redeemed_by:
                    await message.answer("❗ Вы уже активировали этот ваучер.")
                else:
                    if voucher["type"] == "activation":
                        today = datetime.date.today().isoformat()
                        if user.get("last_activation_date") != today:
                            user["last_activation_date"] = today
                            user["activation_count"] = 0
                            user["extra_attempts"] = 0
                        user["extra_attempts"] = user.get("extra_attempts", 0) + voucher["value"]
                        redemption_message = (
                            f"✅ Ваучер активирован! Вам добавлено {voucher['value']} дополнительных попыток активации на сегодня."
                        )
                    elif voucher["type"] == "money":
                        user["balance"] = user.get("balance", 0) + voucher["value"]
                        redemption_message = (
                            f"✅ Ваучер активирован! Вам зачислено {voucher['value']} единиц на баланс."
                        )
                    else:
                        redemption_message = "❗ Неизвестный тип ваучера."
                    
                    redeemed_by.append(str(message.from_user.id))
                    voucher["redeemed_by"] = redeemed_by
                    voucher["redeemed_count"] = voucher.get("redeemed_count", 0) + 1
                    save_data(data)
                    
                    await message.answer(redemption_message)
        return

    welcome_text = (
        "🎉 Добро пожаловать в Market коллекционных номеров! 🎉\n\n"
        "Чтобы войти, используйте команду /login <Ваш Telegram ID>.\n"
        "После этого бот отправит вам код подтверждения, который нужно ввести командой /verify <код>.\n"
        "Если вы уже вошли, можете использовать команды: /mint, /collection, /balance, /sell, /market, /buy, /participants, /exchange, /logout.\n"
        "Для установки аватарки отправьте фото с подписью: /setavatar\n"
        "\nДля автоматического входа на сайте воспользуйтесь ссылкой: "
        f"https://market-production-84b2.up.railway.app/auto_login?user_id={message.from_user.id}"
    )
    await message.answer(welcome_text)

@dp.message(Command("login"))
async def bot_login(message: Message) -> None:
    parts = message.text.split()
    if len(parts) != 2:
        await message.answer("❗ Формат: /login <Ваш Telegram ID>")
        return
    user_id = parts[1]
    if user_id != str(message.from_user.id):
        await message.answer("❗ Вы можете войти только в свой аккаунт.")
        return
    data = load_data()
    user = ensure_user(data, user_id, message.from_user.username or message.from_user.first_name)
    if user.get("logged_in"):
        await message.answer("Вы уже вошли!")
        return
    code = generate_login_code()
    expiry = (datetime.datetime.now() + datetime.timedelta(minutes=5)).timestamp()
    user["login_code"] = code
    user["code_expiry"] = expiry
    save_data(data)
    try:
        await bot.send_message(int(user_id), f"Ваш код для входа: {code}")
        await message.answer("Код подтверждения отправлен. Используйте команду /verify <код> для входа.")
    except Exception as e:
        await message.answer("Ошибка при отправке кода. Попробуйте позже.")
        print("Ошибка отправки кода:", e)

@dp.message(Command("verify"))
async def bot_verify(message: Message) -> None:
    parts = message.text.split()
    if len(parts) != 2:
        await message.answer("❗ Формат: /verify <код>")
        return
    code = parts[1]
    user_id = str(message.from_user.id)
    data = load_data()
    user = data.get("users", {}).get(user_id)
    if not user:
        await message.answer("Пользователь не найден.")
        return
    if user.get("code_expiry", 0) < datetime.datetime.now().timestamp():
        await message.answer("Код устарел. Попробуйте /login снова.")
        return
    if user.get("login_code") != code:
        await message.answer("Неверный код.")
        return
    user["logged_in"] = True
    user["login_code"] = None
    user["code_expiry"] = None
    save_data(data)
    await message.answer("Вход выполнен успешно!")

@dp.message(Command("logout"))
async def bot_logout(message: Message) -> None:
    user_id = str(message.from_user.id)
    data = load_data()
    user = data.get("users", {}).get(user_id)
    if user:
        user["logged_in"] = False
        save_data(data)
    await message.answer("Вы вышли из аккаунта. Для входа используйте /login <Ваш Telegram ID>.")

@dp.message(F.photo)
async def handle_setavatar_photo(message: Message) -> None:
    if message.caption and message.caption.startswith("/setavatar"):
        photo = message.photo[-1]
        file = await bot.get_file(photo.file_id)
        file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file.file_path}"
        data = load_data()
        user = ensure_user(data, str(message.from_user.id),
                           message.from_user.username or message.from_user.first_name)
        user["photo_url"] = file_url
        save_data(data)
        await message.answer("✅ Аватар обновлён!")

@dp.message(Command("mint"))
@require_login
async def mint_number(message: Message) -> None:
    data = load_data()
    user = ensure_user(data, str(message.from_user.id), message.from_user.username or message.from_user.first_name)
    today = datetime.date.today().isoformat()
    if user.get("last_activation_date") != today:
        user["last_activation_date"] = today
        user["activation_count"] = 0
        user["extra_attempts"] = 0
    effective_limit = 3 + user.get("extra_attempts", 0)
    if user["activation_count"] >= effective_limit:
        await message.answer("😔 Вы исчерпали активации на сегодня. Попробуйте завтра!")
        return
    user["activation_count"] += 1
    token_data = generate_number()
    token_data["timestamp"] = datetime.datetime.now().isoformat()
    user["tokens"].append(token_data)
    save_data(data)
    await message.answer(
        f"✨ Ваш новый коллекционный номер: {token_data['token']}\n"
        f"🎨 Редкость номера: {token_data['number_rarity']}\n"
        f"🎨 Редкость цвета цифр: {token_data['text_rarity']}\n"
        f"🎨 Редкость фона: {token_data['bg_rarity']}\n"
        f"💎 Общая редкость: {token_data['overall_rarity']}"
    )
    
@dp.message(Command("collection"))
@require_login
async def show_collection(message: Message) -> None:
    data = load_data()
    user = ensure_user(data, str(message.from_user.id))
    tokens = user.get("tokens", [])
    if not tokens:
        await message.answer("😕 У вас пока нет номеров. Используйте /mint для создания.")
        return
    msg = "🎨 " + "\n".join(
        f"{idx}. {t['token']} | Редкость: {t.get('overall_rarity', 'неизвестно')}" 
        for idx, t in enumerate(tokens, start=1)
    )
    await message.answer(msg)

@dp.message(Command("balance"))
@require_login
async def show_balance(message: Message) -> None:
    data = load_data()
    user = ensure_user(data, str(message.from_user.id))
    await message.answer(f"💎 Ваш баланс: {user.get('balance', 0)} 💎")

@dp.message(Command("sell"))
@require_login
async def sell_number(message: Message) -> None:
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
    user = ensure_user(data, str(message.from_user.id))
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
    data = load_data()
    market = data.get("market", [])
    if not market:
        await message.answer("🌐 На маркетплейсе нет активных продаж.")
        return
    msg = "🌐 Номера на продаже:\n"
    for idx, listing in enumerate(market, start=1):
        seller_id = listing.get("seller_id")
        seller_name = data.get("users", {}).get(seller_id, {}).get("username", seller_id)
        token_info = listing["token"]
        msg += (f"{idx}. {token_info['token']} | Цена: {listing['price']} 💎 | "
                f"Продавец: {seller_name} | Редкость: {token_info.get('overall_rarity', 'неизвестно')}\n")
    await message.answer(msg)

@dp.message(Command("buy"))
@require_login
async def buy_number(message: Message) -> None:
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
    buyer = ensure_user(data, buyer_id)
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

    token = listing["token"]
    token["bought_price"] = price
    token["seller_id"] = seller_id

    buyer.setdefault("tokens", []).append(token)
    market.pop(listing_index)
    save_data(data)
    await message.answer(f"🎉 Вы купили номер {token['token']} за {price} 💎!\nНовый баланс: {buyer['balance']} 💎.")
    if seller:
        try:
            await bot.send_message(int(seller_id),
                                   f"Уведомление: Ваш номер {token['token']} куплен за {price} 💎.")
        except Exception as e:
            print("Ошибка уведомления продавца:", e)

@dp.message(Command("participants"))
async def list_participants(message: Message) -> None:
    data = load_data()
    users = data.get("users", {})
    if not users:
        await message.answer("❗ Нет зарегистрированных участников.")
        return
    msg = "👥 Участники:\n"
    for uid, info in users.items():
        cnt = len(info.get("tokens", []))
        verified_mark = " ✅" if info.get("verified", False) else ""
        msg += f"{info.get('username', 'Неизвестный')}{verified_mark} (ID: {uid}) — Баланс: {info.get('balance', 0)} 💎, номеров: {cnt}\n"
    await message.answer(msg)
    
@dp.message(Command("exchange"))
@require_login
async def exchange_numbers(message: Message) -> None:
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
    initiator = ensure_user(data, str(message.from_user.id))
    if target_uid == str(message.from_user.id):
        await message.answer("❗ Нельзя обмениваться с самим собой!")
        return
    target = data.get("users", {}).get(target_uid)
    if not target:
        await message.answer("❗ Пользователь не найден.")
        return
    my_tokens = initiator.get("tokens", [])
    target_tokens = target.get("tokens", [])
    if my_index < 1 or my_index > len(my_tokens):
        await message.answer("❗ Неверный номер вашего номера.")
        return
    if target_index < 1 or target_index > len(target_tokens):
        await message.answer("❗ Неверный номер у пользователя.")
        return
    my_token = my_tokens.pop(my_index - 1)
    target_token = target_tokens.pop(target_index - 1)
    my_tokens.append(target_token)
    target_tokens.append(my_token)
    save_data(data)
    await message.answer(f"🎉 Обмен завершён!\nВы отдали номер {my_token['token']} и получили {target_token['token']}.")
    try:
        await bot.send_message(int(target_uid),
                               f"🔄 Пользователь {initiator.get('username', 'Неизвестный')} обменял с вами номера.\n"
                               f"Вы отдали {target_token['token']} и получили {my_token['token']}.")
    except Exception as e:
        print("Ошибка уведомления партнёра:", e)

# ---- Команды администратора и верификации аккаунтов ----
@dp.message(Command("verifycation"))
async def verify_user_admin(message: Message) -> None:
    if str(message.from_user.id) not in ADMIN_IDS:
        await message.answer("У вас нет доступа для выполнения этой команды.")
        return
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("❗ Формат: /verifycation <user_id>")
        return
    target_user_id = parts[1]
    data = load_data()
    if "users" not in data or target_user_id not in data["users"]:
        await message.answer("❗ Пользователь не найден.")
        return
    user = data["users"][target_user_id]
    VERIFICATION_ICON_URL = "https://i.ibb.co/4ZjYfn0w/verificationtth.png"
    user["verified"] = True
    user["verification_icon"] = VERIFICATION_ICON_URL
    save_data(data)
    await message.answer(f"✅ Пользователь {user.get('username', 'Неизвестный')} (ID: {target_user_id}) верифицирован.")

@dp.message(Command("unverify"))
async def unverify_user_admin(message: Message) -> None:
    if str(message.from_user.id) not in ADMIN_IDS:
        await message.answer("У вас нет доступа для выполнения этой команды.")
        return
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("❗ Формат: /unverify <user_id>")
        return
    target_user_id = parts[1]
    data = load_data()
    if "users" not in data or target_user_id not in data["users"]:
        await message.answer("❗ Пользователь не найден.")
        return
    user = data["users"][target_user_id]
    user["verified"] = False
    if "verification_icon" in user:
        del user["verification_icon"]
    save_data(data)
    await message.answer(f"✅ Верификация для пользователя {user.get('username', 'Неизвестный')} (ID: {target_user_id}) удалена.")

@dp.message(Command("setbalance"))
async def set_balance(message: Message) -> None:
    if str(message.from_user.id) not in ADMIN_IDS:
        await message.answer("У вас нет доступа для выполнения этой команды.")
        return
    parts = message.text.split()
    if len(parts) != 3:
        await message.answer("❗ Формат: /setbalance <user_id> <новый баланс>")
        return
    target_user_id = parts[1]
    try:
        new_balance = int(parts[2])
    except ValueError:
        await message.answer("❗ Новый баланс должен быть числом.")
        return
    data = load_data()
    if "users" not in data or target_user_id not in data["users"]:
        await message.answer("❗ Пользователь не найден.")
        return
    user = data["users"][target_user_id]
    old_balance = user.get("balance", 0)
    user["balance"] = new_balance
    save_data(data)
    await message.answer(
        f"✅ Баланс пользователя {user.get('username', 'Неизвестный')} (ID: {target_user_id}) изменён с {old_balance} на {new_balance}."
    )

@dp.message(Command("listtokens"))
async def list_tokens_admin(message: Message) -> None:
    if str(message.from_user.id) not in ADMIN_IDS:
        await message.answer("У вас нет доступа для выполнения этой команды.")
        return
    args = message.text.split()[1:]
    if not args:
        await message.answer("Используйте: /listtokens <user_id>")
        return
    target_user_id = args[0]
    data = load_data()
    if "users" not in data or target_user_id not in data["users"]:
        await message.answer("❗ Пользователь не найден.")
        return
    user = data["users"][target_user_id]
    tokens = user.get("tokens", [])
    if not tokens:
        await message.answer("У пользователя нет коллекционных номеров.")
        return
    msg = f"Коллекционные номера пользователя {user.get('username', 'Неизвестный')} (ID: {target_user_id}):\n"
    for idx, token in enumerate(tokens, start=1):
        msg += f"{idx}. {token['token']} | Редкость: {token.get('overall_rarity', 'неизвестно')}\n"
    await message.answer(msg)

@dp.message(Command("settoken"))
async def set_token_admin(message: Message) -> None:
    if str(message.from_user.id) not in ADMIN_IDS:
        await message.answer("У вас нет доступа для выполнения этой команды.")
        return
    parts = message.text.split()
    if len(parts) < 4:
        await message.answer("❗ Формат: /settoken <user_id> <номер_позиции> <новый_номер>")
        return
    target_user_id = parts[1]
    try:
        token_index = int(parts[2]) - 1
    except ValueError:
        await message.answer("❗ Проверьте, что номер позиции является числом.")
        return
    new_token_value = parts[3]
    data = load_data()
    if "users" not in data or target_user_id not in data["users"]:
        await message.answer("❗ Пользователь не найден.")
        return
    user = data["users"][target_user_id]
    tokens = user.get("tokens", [])
    if token_index < 0 or token_index >= len(tokens):
        await message.answer("❗ Неверный номер позиции токена.")
        return
    old_token = tokens[token_index].copy()
    new_token_data = generate_number_from_value(new_token_value)
    tokens[token_index] = new_token_data
    save_data(data)
    await message.answer(
        f"✅ Токен для пользователя {user.get('username', 'Неизвестный')} (ID: {target_user_id}) изменён.\n"
        f"Было: {old_token}\nСтало: {tokens[token_index]}"
    )

@dp.message(Command("addattempts"))
async def add_attempts_admin(message: Message) -> None:
    if str(message.from_user.id) not in ADMIN_IDS:
        await message.answer("У вас нет доступа для выполнения этой команды.")
        return
    parts = message.text.split()
    if len(parts) != 3:
        await message.answer("❗ Формат: /addattempts <user_id> <количество попыток>")
        return
    target_user_id = parts[1]
    try:
        additional = int(parts[2])
    except ValueError:
        await message.answer("❗ Количество попыток должно быть числом.")
        return
    data = load_data()
    if "users" not in data or target_user_id not in data["users"]:
        await message.answer("❗ Пользователь не найден.")
        return
    user = data["users"][target_user_id]
    today = datetime.date.today().isoformat()
    if user.get("last_activation_date") != today:
        user["last_activation_date"] = today
        user["activation_count"] = 0
        user["extra_attempts"] = 0
    user["extra_attempts"] = user.get("extra_attempts", 0) + additional
    effective_limit = 3 + user["extra_attempts"]
    save_data(data)
    await message.answer(
        f"✅ Дополнительные попытки для пользователя {user.get('username', 'Неизвестный')} (ID: {target_user_id}) добавлены.\n"
        f"Сегодняшний лимит попыток: {effective_limit} (из них базовых 3)."
    )
    
@dp.message(Command("createvoucher"))
async def create_voucher_admin(message: Message) -> None:
    if str(message.from_user.id) not in ADMIN_IDS:
        await message.answer("У вас нет доступа для выполнения этой команды.")
        return

    parts = message.text.split()
    if len(parts) < 4:
        await message.answer("❗ Формат: /createvoucher <тип: activation|money> <значение> <кол-во активаций> [<код>]")
        return

    voucher_type = parts[1].lower()
    if voucher_type not in ["activation", "money"]:
        await message.answer("❗ Тип ваучера должен быть 'activation' или 'money'.")
        return

    try:
        value = int(parts[2])
        max_uses = int(parts[3])
    except ValueError:
        await message.answer("❗ Значение и количество активаций должны быть числами.")
        return

    if len(parts) >= 5:
        code = parts[4]
    else:
        code = ''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', k=8))

    data = load_data()
    if "vouchers" not in data:
        data["vouchers"] = []

    voucher = {
        "code": code,
        "type": voucher_type,
        "value": value,
        "max_uses": max_uses,
        "redeemed_count": 0,
        "created_at": datetime.datetime.now().isoformat(),
        "created_by": str(message.from_user.id)
    }

    data["vouchers"].append(voucher)
    save_data(data)

    voucher_link = f"https://t.me/{BOT_USERNAME}?start=redeem_{code}"
    await message.answer(
        f"✅ Ваучер создан:\n"
        f"Тип: {voucher_type}\n"
        f"Значение: {value}\n"
        f"Количество активаций: {max_uses}\n"
        f"Код: {code}\n"
        f"Ссылка для активации ваучера: {voucher_link}"
    )
    
@dp.message(Command("getdata"))
async def get_data_file(message: Message) -> None:
    if str(message.from_user.id) not in ADMIN_IDS:
        await message.answer("У вас нет доступа для выполнения этой команды.")
        return
    if not os.path.exists(DATA_FILE):
        await message.answer("Файл data.json не найден.")
        return
    document = FSInputFile(DATA_FILE)
    await message.answer_document(document=document, caption="Содержимое файла data.json")

@dp.message(F.document)
async def set_db_from_document(message: Message) -> None:
    if message.caption and message.caption.strip().startswith("/setdb"):
        if str(message.from_user.id) not in ADMIN_IDS:
            await message.answer("У вас нет доступа для выполнения этой команды.")
            return
        try:
            file_info = await bot.get_file(message.document.file_id)
            file_bytes = await bot.download_file(file_info.file_path)
            with open(DATA_FILE, "wb") as f:
                f.write(file_bytes.getvalue())
            await message.answer("✅ База данных успешно обновлена из полученного файла.")
        except Exception as e:
            await message.answer(f"❗ Произошла ошибка при обновлении базы данных: {e}")

# --------------------- Веб‑приложение (FastAPI) ---------------------
app = FastAPI()

if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")
templates.env.globals["enumerate"] = enumerate
templates.env.globals["get_rarity"] = get_rarity

# Middleware для проверки авторизации
@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    # Из разрешённых путей теперь только /first_visit, /logged_out и /auto_login (а также /static)
    allowed_paths = ["/first_visit", "/logged_out", "/auto_login"]
    if any(request.url.path.startswith(path) for path in allowed_paths) or request.url.path.startswith("/static"):
        return await call_next(request)
    
    user_id = request.cookies.get("user_id")
    if not user_id:
        return HTMLResponse(
            "<h1>Доступ ограничен</h1>"
            "<p>Пожалуйста, зарегистрируйтесь через Telegram‑бота и войдите, чтобы пользоваться сайтом.</p>",
            status_code=401
        )
    
    data = load_data()
    user = data.get("users", {}).get(user_id)
    if not user or not user.get("logged_in"):
        return HTMLResponse(
            "<h1>Доступ ограничен</h1>"
            "<p>Пожалуйста, зарегистрируйтесь через Telegram‑бота и войдите, чтобы пользоваться сайтом.</p>",
            status_code=401
        )
    
    return await call_next(request)

# Веб‑маршруты

# Новые маршруты для незалогиненного пользователя и для выхода
@app.get("/first_visit", response_class=HTMLResponse)
async def first_visit(request: Request):
    return templates.TemplateResponse("first_visit.html", {"request": request})

@app.get("/logged_out", response_class=HTMLResponse)
async def logged_out(request: Request):
    return templates.TemplateResponse("logged_out.html", {"request": request})

@app.get("/auto_login", response_class=HTMLResponse)
async def auto_login(request: Request, user_id: str):
    data = load_data()
    user = data.get("users", {}).get(user_id)
    if not user or not user.get("logged_in"):
        return RedirectResponse(url="/first_visit", status_code=303)
    response = RedirectResponse(url=f"/profile/{user_id}", status_code=303)
    response.set_cookie("user_id", user_id, max_age=60*60*24*30, path="/")
    return response

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    user_id = request.cookies.get("user_id")
    data = load_data()
    user = data.get("users", {}).get(user_id) if user_id else None
    market = data.get("market", [])
    return templates.TemplateResponse("index.html", {
        "request": request,
        "user": user,
        "user_id": user_id,
        "market": market,
        "users": data.get("users", {})
    })

@app.get("/profile/{user_id}", response_class=HTMLResponse)
async def profile(request: Request, user_id: str):
    data = load_data()
    user = data.get("users", {}).get(user_id)
    if not user:
        return HTMLResponse("Пользователь не найден.", status_code=404)
    current_user_id = request.cookies.get("user_id")
    is_owner = (current_user_id == user_id)
    return templates.TemplateResponse("profile.html", {
        "request": request,
        "user": user,
        "user_id": user_id,
        "is_owner": is_owner
    })

@app.get("/mint", response_class=HTMLResponse)
async def web_mint(request: Request):
    return templates.TemplateResponse("mint.html", {"request": request})

@app.post("/mint", response_class=HTMLResponse)
async def web_mint_post(request: Request, user_id: str = Form(None)):
    if not user_id:
        user_id = request.cookies.get("user_id")
    if not user_id:
        return HTMLResponse("Ошибка: не найден Telegram ID. Пожалуйста, войдите.", status_code=400)
    data = load_data()
    user = ensure_user(data, user_id)
    today = datetime.date.today().isoformat()
    if user.get("last_activation_date") != today:
        user["last_activation_date"] = today
        user["activation_count"] = 0
        user["extra_attempts"] = 0
    effective_limit = 3 + user.get("extra_attempts", 0)
    if user["activation_count"] >= effective_limit:
        return templates.TemplateResponse("mint.html", {
            "request": request,
            "error": "Вы исчерпали активации на сегодня. Попробуйте завтра!",
            "user_id": user_id
        })
    user["activation_count"] += 1
    token_data = generate_number()
    token_data["timestamp"] = datetime.datetime.now().isoformat()
    user["tokens"].append(token_data)
    save_data(data)
    return templates.TemplateResponse("profile.html", {"request": request, "user": user, "user_id": user_id})
    
@app.get("/sell", response_class=HTMLResponse)
async def web_sell(request: Request):
    return templates.TemplateResponse("sell.html", {"request": request})

@app.post("/sell", response_class=HTMLResponse)
async def web_sell_post(request: Request, user_id: str = Form(None), token_index: int = Form(...), price: int = Form(...)):
    if not user_id:
        user_id = request.cookies.get("user_id")
    if not user_id:
        return HTMLResponse("Ошибка: не найден Telegram ID. Пожалуйста, войдите.", status_code=400)
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
async def web_exchange_post(request: Request, user_id: str = Form(None), my_index: int = Form(...), target_id: str = Form(...), target_index: int = Form(...)):
    if not user_id:
        user_id = request.cookies.get("user_id")
    if not user_id:
        return HTMLResponse("Ошибка: не найден Telegram ID. Пожалуйста, войдите.", status_code=400)
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

@app.get("/market", response_class=HTMLResponse)
async def web_market(request: Request):
    data = load_data()
    market = data.get("market", [])
    return templates.TemplateResponse("market.html", {
        "request": request,
        "market": market,
        "users": data.get("users", {}),
        "buyer_id": request.cookies.get("user_id")
    })

@app.post("/buy/{listing_index}")
async def web_buy(request: Request, listing_index: int, buyer_id: str = Form(None)):
    if not buyer_id:
        buyer_id = request.cookies.get("user_id")
    if not buyer_id:
        return HTMLResponse("Ошибка: не найден Telegram ID. Пожалуйста, войдите.", status_code=400)
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

    token = listing["token"]
    token["bought_price"] = price
    token["seller_id"] = seller_id

    buyer.setdefault("tokens", []).append(token)
    market.pop(listing_index)
    save_data(data)
    return templates.TemplateResponse("profile.html", {"request": request, "user": buyer, "user_id": buyer_id})

# --- Эндпоинты для установки/снятия профильного номера ---
@app.post("/set_profile_token", response_class=HTMLResponse)
async def set_profile_token(request: Request, user_id: str = Form(...), token_index: int = Form(...)):
    cookie_user_id = request.cookies.get("user_id")
    if cookie_user_id != user_id:
        return HTMLResponse("Вы не можете изменять чужой профиль.", status_code=403)
    data = load_data()
    user = data.get("users", {}).get(user_id)
    if not user:
        return HTMLResponse("Пользователь не найден", status_code=404)
    tokens = user.get("tokens", [])
    if token_index < 1 or token_index > len(tokens):
        return HTMLResponse("Неверный индекс номера", status_code=400)
    user["custom_number"] = tokens[token_index - 1]
    save_data(data)
    response = RedirectResponse(url=f"/profile/{user_id}", status_code=303)
    return response

@app.post("/remove_profile_token", response_class=HTMLResponse)
async def remove_profile_token(request: Request, user_id: str = Form(...)):
    cookie_user_id = request.cookies.get("user_id")
    if cookie_user_id != user_id:
        return HTMLResponse("Вы не можете изменять чужой профиль.", status_code=403)
    data = load_data()
    user = data.get("users", {}).get(user_id)
    if not user:
        return HTMLResponse("Пользователь не найден", status_code=404)
    if "custom_number" in user:
        del user["custom_number"]
        save_data(data)
    response = RedirectResponse(url=f"/profile/{user_id}", status_code=303)
    return response

# --------------------- Запуск бота и веб‑сервера ---------------------
async def main():
    bot_task = asyncio.create_task(dp.start_polling(bot))
    config = uvicorn.Config(app, host="0.0.0.0", port=8000, log_level="info")
    server = uvicorn.Server(config)
    web_task = asyncio.create_task(server.serve())
    await asyncio.gather(bot_task, web_task)

if __name__ == "__main__":
    asyncio.run(main())
