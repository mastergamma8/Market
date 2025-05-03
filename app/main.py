import os
import json
import random
import itertools
import math
import datetime
import asyncio
import hashlib
import hmac
import zipfile
import io
import shutil
import shop
import urllib.parse
from typing import Tuple
import exchange_commands
from auctions import router as auctions_router, register_auction_tasks
from offer import router as offer_router
import admin_commands
# Импорт роутера из exchange_web
from exchange_web import router as exchange_router

# Импорт общих функций, шаблонов и объектов бота из common.py
from common import load_data, save_data, ensure_user, templates, bot, dp, DATA_FILE, BOT_TOKEN

# Импорт функции auto_cancel_exchanges из exchange_commands
from exchange_commands import auto_cancel_exchanges

from aiogram import Bot, Dispatcher, F
from aiogram.client.bot import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, LabeledPrice
from aiogram.types.input_file import FSInputFile  # Для отправки файлов

# Импорт для веб‑приложения
import uvicorn
from fastapi import FastAPI, Request, Form, Body
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi import UploadFile, File

ADMIN_IDS = {"1809630966", "7053559428"}
BOT_USERNAME = "tthnftbot"

# --- Декоратор для проверки входа пользователя ---
def require_login(handler):
    async def wrapper(message: Message):
        data = load_data()
        user_id = str(message.from_user.id)
        user = data.get("users", {}).get(user_id)
        if not user:
            await message.answer("Пользователь не найден. Пожалуйста, зарегистрируйтесь через /login")
            return
        if not user.get("logged_in"):
            await message.answer("❗ Для выполнения этой команды необходимо войти. Используйте /login")
            return
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
        # 0.5% редкость: градиенты для текста.
        # Исходные:
        # 1. Blue-green gradient: linear-gradient(45deg, #00c2e6, #48d9af, #00cc1f)
        # 2. Vivid blue-cyan gradient: linear-gradient(45deg, #0099ff, #00ccff, #00ffcc)
        # 3. Sky blue to mint gradient: linear-gradient(45deg, #00bfff, #00f5ff, #00ff99)
        # Новые:
        # 4. Dark blue gradient: linear-gradient(45deg, #1e3c72, #2a5298, #1e90ff)
        # 5. Purple to pink to light orange: linear-gradient(45deg, #3a1c71, #d76d77, #ffaf7b)
        # 6. Teal to soft green: linear-gradient(45deg, #134E5E, #71B280, #B2F4B8)
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
        # 1% редкость: градиенты для текста.
        # Исходные:
        # 1. Red-orange to yellow-green: linear-gradient(45deg, #e60000, #e6b800, #66cc00)
        # 2. Orange-red to light green: linear-gradient(45deg, #FF4500, #FFA500, #ADFF2F)
        # 3. Tomato red to gold to pale green: linear-gradient(45deg, #FF6347, #FFD700, #98FB98)
        # Новые:
        # 4. Firebrick to dark orange to yellowgreen: linear-gradient(45deg, #B22222, #FF8C00, #9ACD32)
        # 5. Crimson to gold to limegreen: linear-gradient(45deg, #DC143C, #FFD700, #32CD32)
        # 6. Dark red to light salmon to light green: linear-gradient(45deg, #8B0000, #FFA07A, #90EE90)
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
        # 1.5% редкость: градиенты для текста.
        # Исходные:
        # 1. Purple to blue to green: linear-gradient(45deg, #8E44AD, #3498DB, #2ECC71)
        # 2. Dark orchid to deep sky blue to medium sea green: linear-gradient(45deg, #9932CC, #00BFFF, #3CB371)
        # 3. Blue violet to dodger blue to lime green: linear-gradient(45deg, #8A2BE2, #1E90FF, #32CD32)
        # Новые:
        # 4. Amethyst to royal blue to medium sea green: linear-gradient(45deg, #6A0DAD, #4169E1, #3CB371)
        # 5. Dark violet to dark turquoise to sea green: linear-gradient(45deg, #9400D3, #00CED1, #2E8B57)
        # 6. Purple to blue to green (вариант 2): linear-gradient(45deg, #800080, #0000FF, #008000)
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
        # 2% редкость: добавлены 3 новых сплошных цвета
        # Исходные: "#FF5733", "#33FFCE"
        # Новые: Gold (#FFD700), Hot Pink (#FF69B4), Medium Spring Green (#00FA9A)
        text_pool = ["#FF5733", "#33FFCE", "#FFD700", "#FF69B4", "#00FA9A"]
        text_rarity = "2%"
    elif r < 0.30:
        # 2.5% редкость: добавлены 3 новых сплошных цвета
        # Исходные: "#8e44ad", "#2c3e50"
        # Новые: Crimson (#DC143C), Light Sea Green (#20B2AA), Peach Puff (#FFDAB9)
        text_pool = ["#8e44ad", "#2c3e50", "#DC143C", "#20B2AA", "#FFDAB9"]
        text_rarity = "2.5%"
    else:
        # 3% редкость: добавлены 3 новых сплошных цвета
        # Исходные: "#d35400", "#e67e22", "#27ae60"
        # Новые: Coral (#FF7F50), Steel Blue (#4682B4), Yellow Green (#9ACD32)
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
    # Вычисляем максимальное количество подряд идущих одинаковых цифр
    max_repeats = max(len(list(group)) for _, group in itertools.groupby(token_str))
    number_rarity = compute_number_rarity(token_str)
    text_color, text_rarity = generate_text_attributes()
    bg_color, bg_rarity, bg_is_image, bg_availability = generate_bg_attributes()
    overall_rarity = compute_overall_rarity(number_rarity, text_rarity, bg_rarity)
    return {
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

def generate_login_code() -> str:
    return str(random.randint(100000, 999999))

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
    data = load_data()
    # Если пользователя ещё нет, он будет создан
    user = ensure_user(
        data, 
        str(message.from_user.id),
        message.from_user.username or message.from_user.first_name
    )
    # Отмечаем, что пользователь запустил бота (если это нужно для логики)
    if not user.get("started"):
        user["started"] = True
        save_data(data)
    
    parts = message.text.split(maxsplit=1)
    args = parts[1].strip() if len(parts) > 1 else ""
    
    # Обработка ваучера
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
                redeemed_by = voucher.get("redeemed_by", [])
                if str(message.from_user.id) in redeemed_by:
                    await message.answer("❗ Вы уже активировали этот ваучер.", parse_mode="HTML")
                else:
                    if voucher["type"] == "activation":
                        today = datetime.date.today().isoformat()
                        if user.get("last_activation_date") != today:
                            user["last_activation_date"] = today
                            user["activation_count"] = 0
                            user["extra_attempts"] = 0
                        user["extra_attempts"] = user.get("extra_attempts", 0) + voucher["value"]
                        redemption_message = (
                            f"✅ Ваучер активирован! Вам добавлено {voucher['value']} дополнительных попыток активации номера."
                        )
                    elif voucher["type"] == "money":
                        user["balance"] = user.get("balance", 0) + voucher["value"]
                        redemption_message = (
                            f"✅ Ваучер активирован! Вам зачислено {voucher['value']} 💎 на баланс."
                        )
                    else:
                        redemption_message = "❗ Неизвестный тип ваучера."
                    redeemed_by.append(str(message.from_user.id))
                    voucher["redeemed_by"] = redeemed_by
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
    
    # Приветственное сообщение
    welcome_text = (
        "✨ <b>Добро пожаловать в TTH NFT</b> – мир уникальных коллекционных номеров и бесконечных возможностей! ✨\n\n"
        "Ваш Telegram ID: <b>{}</b>\n\n".format(message.from_user.id) +
        "Чтобы начать своё приключение, выполните команду:\n"
        "   <code>/login &lt;Ваш Telegram ID&gt;</code>\n\n"
        "После входа в систему вы сможете использовать команды: /mint, /collection, /balance, /sell, /market, /buy, /participants, /exchange, /logout\n\n"
        "Для смены аватарки отправьте фото с подписью: /setavatar\n\n"
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📜 Список команд", callback_data="help_commands")]
    ])
    await message.answer(welcome_text, reply_markup=keyboard, parse_mode="HTML")


@dp.callback_query(F.data == "help_commands")
async def process_help_callback(callback_query: CallbackQuery) -> None:
    commands_text = (
        "💡 <b>Список команд TTH NFT</b> 💡\n\n"
        "🔸 <b>/start</b> – Приветствие и инструкции\n"
        "🔸 <b>/login &lt;Ваш Telegram ID&gt;</b> – Вход в аккаунт для получения кода подтверждения\n"
        "🔸 <b>/verify &lt;код&gt;</b> – Подтверждение входа\n"
        "🔸 <b>/logout</b> – Выход из аккаунта\n"
        "🔸 <b>/setavatar</b> – Обновление аватарки (отправьте фото с подписью)\n"
        "🔸 <b>/setdesc &lt;описание&gt;</b> – Изменение описания профиля\n"
        "🔸 <b>/mint</b> – Создание нового уникального токена\n"
        "🔸 <b>/transfer &lt;ID получателя&gt; &lt;номер токена&gt;</b> – Передача токена другому пользователю\n"
        "🔸 <b>/collection</b> – Просмотр вашей коллекции токенов\n"
        "🔸 <b>/balance</b> – Просмотр баланса аккаунта\n"
        "🔸 <b>/sell &lt;номер токена&gt; &lt;цена&gt;</b> – Выставление токена на продажу\n"
        "🔸 <b>/market</b> – Просмотр маркетплейса\n"
        "🔸 <b>/buy &lt;номер листинга&gt;</b> – Покупка токена\n"
        "🔸 <b>/updateprice &lt;номер листинга&gt; &lt;новая цена&gt;</b> – Обновление цены для вашего листинга\n"
        "🔸 <b>/withdraw &lt;номер листинга&gt;</b> – Снятие токена с продажи и возвращение его в коллекцию\n"
        "🔸 <b>/participants</b> – Список участников сообщества\n"
        "🔸 <b>/referral</b> – Получить реферальную ссылку\n"
        "🔸 <b>/referrals</b> – Посмотреть статистику по вашим рефералам\n\n"
        "🔸 <b>/auction &lt;номер токена&gt; &lt;начальная цена&gt; &lt;длительность (мин)&gt;</b> – Создание аукциона для вашего токена\n"
        "🔸 <b>/bid &lt;auction id&gt; &lt;ставка&gt;</b> – Сделать ставку в активном аукционе\n\n"
        "Наслаждайтесь миром TTH NFT и удачных коллекций! 🚀"
    )
    await callback_query.message.answer(commands_text, parse_mode="HTML")
    await callback_query.answer()

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
    banned = data.get("banned", [])
    if user_id in banned:
        await message.answer("❗ Ваш аккаунт заблокирован.")
        return
    # Если пользователь уже существует и зарегистрирован, повторная регистрация недопустима
    existing_user = data.get("users", {}).get(user_id)
    if existing_user and existing_user.get("started"):
        if existing_user.get("logged_in"):
            await message.answer("Вы уже вошли!")
        else:
            await message.answer("Вы уже зарегистрированы. Используйте /verify <код> для входа.")
        return
    # Иначе создаём пользователя и отмечаем регистрацию
    user = ensure_user(data, user_id, message.from_user.username or message.from_user.first_name)
    user["started"] = True
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
@require_login
async def handle_setavatar_photo(message: Message) -> None:
    if message.caption and message.caption.startswith("/setavatar"):
        photo = message.photo[-1]
        file_info = await bot.get_file(photo.file_id)
        file_bytes = await bot.download_file(file_info.file_path)
        
        avatars_dir = os.path.join("static", "avatars")
        if not os.path.exists(avatars_dir):
            os.makedirs(avatars_dir)
        
        data = load_data()
        user = ensure_user(
            data, 
            str(message.from_user.id),
            message.from_user.username or message.from_user.first_name
        )
        old_photo_url = user.get("photo_url")
        if old_photo_url and old_photo_url.startswith("/static/avatars/"):
            old_filename = old_photo_url.replace("/static/avatars/", "")
            old_path = os.path.join(avatars_dir, old_filename)
            if os.path.exists(old_path):
                os.remove(old_path)
        
        filename = f"{message.from_user.id}.jpg"
        file_path = os.path.join(avatars_dir, filename)
        
        with open(file_path, "wb") as f:
            f.write(file_bytes.getvalue())
        
        user["photo_url"] = f"/static/avatars/{filename}"
        save_data(data)
        
        await message.answer("✅ Аватар обновлён!")

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

@dp.message(Command("setdesc"))
@require_login
async def set_description(message: Message) -> None:
    parts = message.text.split(maxsplit=1)
    if len(parts) != 2:
        await message.answer("❗ Формат: /setdesc <описание>")
        return
    description = parts[1]
    data = load_data()
    user = ensure_user(data, str(message.from_user.id),
                       message.from_user.username or message.from_user.first_name)
    user["description"] = description
    save_data(data)
    await message.answer("✅ Описание профиля обновлено!")

@dp.message(Command("mint"))
@require_login
async def mint_number(message: Message) -> None:
    data = load_data()
    user_id = str(message.from_user.id)
    user = ensure_user(data, user_id)
    
    # Обновляем данные, если день сменился
    today = datetime.date.today().isoformat()
    if user.get("last_activation_date") != today:
        user["last_activation_date"] = today
        user["activation_count"] = 0
        # Если поля "extra_attempts" нет, устанавливаем его равным 0
        user.setdefault("extra_attempts", 0)
    
    base_daily_limit = 0  # базовое количество бесплатных попыток
    used_attempts = user.get("activation_count", 0)
    extra_attempts = user.get("extra_attempts", 0)
    attempts_left = (base_daily_limit + extra_attempts) - used_attempts
    
    if attempts_left > 0:
        user["activation_count"] = used_attempts + 1
        token_data = generate_number()
        token_data["timestamp"] = datetime.datetime.now().isoformat()
        user.setdefault("tokens", []).append(token_data)
        save_data(data)
        message_text = (
            f"✨ Ваш новый коллекционный номер: {token_data['token']}\n"
            f"🎨 Редкость номера: {token_data['number_rarity']}\n"
            f"🎨 Редкость цвета цифр: {token_data['text_rarity']}\n"
            f"🎨 Редкость фона: {token_data['bg_rarity']}\n"
            f"💎 Общая редкость: {token_data['overall_rarity']}"
        )
        await message.answer(message_text)
    else:
        if user.get("balance", 0) < 100:
            await message.answer("Бесплатные попытки закончились и у вас недостаточно алмазов для создания номера.")
        else:
            markup = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Создать номер за 100 💎", callback_data="mint_pay_100")]
            ])
            await message.answer("Бесплатные попытки на сегодня исчерпаны. Хотите создать номер за 100 💎?", reply_markup=markup)

@dp.callback_query(F.data == "mint_pay_100")
async def mint_pay_100_callback(callback_query: CallbackQuery) -> None:
    data = load_data()
    user_id = str(callback_query.from_user.id)
    user = data.get("users", {}).get(user_id)
    if not user:
        await callback_query.answer("Пользователь не найден.", show_alert=True)
        return
    if user.get("balance", 0) < 100:
        await callback_query.answer("Недостаточно алмазов для создания номера.", show_alert=True)
        return
    user["balance"] -= 100
    token_data = generate_number()
    token_data["timestamp"] = datetime.datetime.now().isoformat()
    user.setdefault("tokens", []).append(token_data)
    save_data(data)
    message_text = (
        f"✨ Номер {token_data['token']} успешно создан за 100 💎!\n"
        f"🎨 Редкость номера: {token_data['number_rarity']}\n"
        f"🎨 Редкость цвета цифр: {token_data['text_rarity']}\n"
        f"🎨 Редкость фона: {token_data['bg_rarity']}\n"
        f"💎 Общая редкость: {token_data['overall_rarity']}"
    )
    await callback_query.message.edit_text(message_text)
    await callback_query.answer()

@dp.message(Command("transfer"))
@require_login
async def transfer_number(message: Message) -> None:
    parts = message.text.split()
    if len(parts) != 3:
        await message.answer("❗ Формат: /transfer <Telegram ID или скрещённый номер> <номер вашего номера (1-based)>")
        return

    identifier = parts[1]
    # сначала попробуем найти по скрещённому номеру
    data = load_data()
    target_user_id = None
    for uid, u in data.get("users", {}).items():
        if u.get("crossed_number", {}).get("token") == identifier:
            target_user_id = uid
            break
    # если не нашли — берём как обычный ID
    if target_user_id is None:
        target_user_id = identifier

    try:
        token_index = int(parts[2]) - 1
    except ValueError:
        await message.answer("❗ Номер вашего номера должен быть числом.")
        return

    sender_id = str(message.from_user.id)
    if target_user_id == sender_id:
        await message.answer("❗ Вы не можете передать номер самому себе.")
        return

    sender = ensure_user(data, sender_id)
    tokens = sender.get("tokens", [])
    if token_index < 0 or token_index >= len(tokens):
        await message.answer("❗ Неверный номер из вашей коллекции.")
        return

    token = tokens.pop(token_index)
    # если убираем профильный — то и из него
    if sender.get("custom_number", {}).get("token") == token["token"]:
        del sender["custom_number"]
    save_data(data)

    receiver = ensure_user(data, target_user_id)
    receiver.setdefault("tokens", []).append(token)
    save_data(data)

    await message.answer(f"✅ Номер {token['token']} успешно передан пользователю {identifier}!")
    sender_name = sender.get("username", "Неизвестный")
    try:
        await bot.send_message(
            int(target_user_id),
            f"Вам передали коллекционный номер: {token['token']}!\nОтправитель: {sender_name} (ID: {sender_id})"
        )
    except Exception:
        pass

@dp.message(Command("collection"))
@require_login
async def show_collection(message: Message) -> None:
    data = load_data()
    user = ensure_user(data, str(message.from_user.id))
    tokens = user.get("tokens", [])
    if not tokens:
        await message.answer("😕 У вас пока нет номеров. Используйте /mint для создания.")
        return
    msg = "🎨 " + "\n".join(f"{idx}. {t['token']} | Редкость: {t.get('overall_rarity', 'неизвестно')}" 
                             for idx, t in enumerate(tokens, start=1))
    MAX_LENGTH = 4096
    if len(msg) > MAX_LENGTH:
        for i in range(0, len(msg), MAX_LENGTH):
            await message.answer(msg[i:i+MAX_LENGTH])
    else:
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
    if user.get("custom_number") and user["custom_number"].get("token") == item["token"]:
        del user["custom_number"]
    if "market" not in data:
        data["market"] = []
    listing = {
        "seller_id": str(message.from_user.id),
        "token": item,
        "price": price,
        "timestamp": datetime.datetime.now().isoformat()
    }
    data["market"].insert(0, listing)
    save_data(data)
    await message.answer(f"🚀 Номер {item['token']} выставлен на продажу за {price} 💎!")

@dp.message(Command("market"))
@require_login
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
        msg += (f"{idx}. {token_info['token']} | Цена: {listing['price']} 💎 | Продавец: {seller_name} | "
                f"Редкость: {token_info.get('overall_rarity', 'неизвестно')}\n")
    MAX_LENGTH = 4096
    if len(msg) > MAX_LENGTH:
        for i in range(0, len(msg), MAX_LENGTH):
            await message.answer(msg[i:i+MAX_LENGTH])
    else:
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
    commission_rate = 0.05
    if "referrer" in buyer:
        referrer_id = buyer["referrer"]
        referrer = data.get("users", {}).get(referrer_id)
        if referrer:
            commission = int(price * commission_rate)
            referrer["balance"] = referrer.get("balance", 0) + commission
    seller = data.get("users", {}).get(seller_id)
    if seller:
        seller["balance"] = seller.get("balance", 0) + price
    if seller.get("custom_number") and seller["custom_number"].get("token") == listing["token"].get("token"):
            del seller["custom_number"]
    token = listing["token"]
    token["bought_price"] = price
    token["bought_date"] = datetime.datetime.now().isoformat()
    token["bought_source"] = "market"
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

@dp.message(Command("updateprice"))
@require_login
async def update_price(message: Message) -> None:
    parts = message.text.split()
    if len(parts) != 3:
        await message.answer("❗ Формат: /updateprice <номер листинга> <новая цена>")
        return
    try:
        listing_index = int(parts[1]) - 1
        new_price = int(parts[2])
    except ValueError:
        await message.answer("❗ Номер листинга и новая цена должны быть числами.")
        return
    data = load_data()
    market = data.get("market", [])
    seller_id = str(message.from_user.id)
    seller_listings = [i for i, listing in enumerate(market) if listing.get("seller_id") == seller_id]
    if listing_index < 0 or listing_index >= len(seller_listings):
        await message.answer("❗ Неверный номер листинга.")
        return
    actual_index = seller_listings[listing_index]
    market[actual_index]["price"] = new_price
    save_data(data)
    token_str = market[actual_index]["token"].get("token", "номер")
    await message.answer(f"🚀 Цена для номера {token_str} обновлена до {new_price} 💎!")

@dp.message(Command("withdraw"))
@require_login
async def withdraw_listing(message: Message) -> None:
    parts = message.text.split()
    if len(parts) != 2:
        await message.answer("❗ Формат: /withdraw <номер листинга>")
        return
    try:
        listing_index = int(parts[1]) - 1
    except ValueError:
        await message.answer("❗ Номер листинга должен быть числом.")
        return
    data = load_data()
    market = data.get("market", [])
    seller_id = str(message.from_user.id)
    seller_listings = [i for i, listing in enumerate(market) if listing.get("seller_id") == seller_id]
    if listing_index < 0 or listing_index >= len(seller_listings):
        await message.answer("❗ Неверный номер листинга.")
        return
    actual_index = seller_listings[listing_index]
    listing = market.pop(actual_index)
    user = data.get("users", {}).get(seller_id)
    if user:
        user.setdefault("tokens", []).append(listing["token"])
    save_data(data)
    token_str = listing["token"].get("token", "номер")
    await message.answer(f"🚀 Номер {token_str} снят с продажи и возвращён в вашу коллекцию.")

@dp.message(Command("participants"))
@require_login
async def list_participants(message: Message) -> None:
    data = load_data()
    users = data.get("users", {})
    if not users:
        await message.answer("❗ Нет зарегистрированных участников.")
        return

    current_user_id = str(message.from_user.id)
    
    sorted_total = sorted(users.items(),
                          key=lambda item: len(item[1].get("tokens", [])),
                          reverse=True)
    sorted_total = list(enumerate(sorted_total, start=1))
    
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
    sorted_rare = [(i, uid, user, count_rare_tokens(user, threshold=1.0))
                   for i, (uid, user) in enumerate(sorted_rare, start=1)]
    
    msg = "🏆 Лидерборд участников:\n\n"
    msg += "🔹 По общему количеству номеров:\n"
    for position, (uid, user) in sorted_total:
        tokens_count = len(user.get("tokens", []))
        msg += f"{position}. {user.get('username', 'Неизвестный')} (ID: {uid}) — номеров: {tokens_count}\n"
    
    msg += "\n🔹 По количеству редких номеров (overall_rarity ≤ 1.0%):\n"
    for position, uid, user, rare_count in sorted_rare:
        msg += f"{position}. {user.get('username', 'Неизвестный')} (ID: {uid}) — редких номеров: {rare_count}\n"
    
    MAX_LENGTH = 4096
    if len(msg) > MAX_LENGTH:
        for i in range(0, len(msg), MAX_LENGTH):
            await message.answer(msg[i:i+MAX_LENGTH])
    else:
        await message.answer(msg)


# --------------------- Веб‑приложение (FastAPI) ---------------------
app = FastAPI()

if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

# Подключаем роутеры веб‑приложения
app.include_router(exchange_router)
app.include_router(auctions_router)
app.include_router(offer_router)

# Настройка шаблонов
templates = Jinja2Templates(directory="templates")
templates.env.globals["enumerate"] = enumerate
# Предполагается, что функция get_rarity определена в одном из модулей (например, в common.py)
templates.env.globals["get_rarity"] = get_rarity

# Для защищённых маршрутов проверяем наличие cookie и флага logged_in
def require_web_login(request: Request):
    user_id = request.cookies.get("user_id")
    if not user_id:
        return None
    data = load_data()
    user = data.get("users", {}).get(user_id)
    if not user or not user.get("logged_in"):
        return None
    return user_id

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
        "users": data.get("users", {}),
        "buyer_id": user_id
    })

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login", response_class=HTMLResponse)
async def login_post(request: Request, user_id: str = Form(None)):
    if not user_id:
        user_id = request.cookies.get("user_id")
    if not user_id:
        return HTMLResponse("Ошибка: не найден Telegram ID.", status_code=400)
    data = load_data()
    user = ensure_user(data, user_id)
    code = generate_login_code()
    expiry = (datetime.datetime.now() + datetime.timedelta(minutes=5)).timestamp()
    user["login_code"] = code
    user["code_expiry"] = expiry
    save_data(data)
    try:
        await bot.send_message(int(user_id), f"Ваш код для входа: {code}")
    except Exception as e:
        return HTMLResponse("Ошибка при отправке кода через Telegram.", status_code=500)
    return templates.TemplateResponse("verify.html", {"request": request, "user_id": user_id})

@app.post("/verify", response_class=HTMLResponse)
async def verify_post(request: Request, user_id: str = Form(...), code: str = Form(...)):
    data = load_data()
    user = data.get("users", {}).get(user_id)
    if not user:
        return HTMLResponse("Пользователь не найден.", status_code=404)
    if user.get("code_expiry", 0) < datetime.datetime.now().timestamp():
        return HTMLResponse("Код устарел. Повторите попытку входа.", status_code=400)
    if user.get("login_code") != code:
        return HTMLResponse("Неверный код.", status_code=400)
    user["logged_in"] = True
    user["login_code"] = None
    user["code_expiry"] = None
    save_data(data)
    response = RedirectResponse(url=f"/profile/{user_id}", status_code=303)
    response.set_cookie("user_id", user_id, max_age=60*60*24*30, path="/")
    return response

@app.get("/logout", response_class=HTMLResponse)
async def logout(request: Request):
    user_id = request.cookies.get("user_id")
    if user_id:
        data = load_data()
        user = data.get("users", {}).get(user_id)
        if user:
            user["logged_in"] = False
            save_data(data)
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie("user_id", path="/")
    return response

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
    # Проверка авторизации: текущий пользователь должен быть залогинен
    current_user_id = request.cookies.get("user_id")
    data = load_data()
    current_user = data.get("users", {}).get(current_user_id) if current_user_id else None
    if not current_user or not current_user.get("logged_in"):
        return RedirectResponse(url="/login", status_code=303)
    user = data.get("users", {}).get(user_id)
    if not user:
        return HTMLResponse("Пользователь не найден.", status_code=404)
    is_owner = (current_user_id == user_id)
    tokens_count = len(user.get("tokens", []))
    return templates.TemplateResponse("profile.html", {
        "request": request,
        "user": user,
        "user_id": user_id,
        "is_owner": is_owner,
        "tokens_count": tokens_count
    })

@app.post("/update_profile", response_class=HTMLResponse)
async def update_profile(
    request: Request,
    user_id: str = Form(...),
    username: str = Form(None),
    description: str = Form(""),  # По умолчанию пустая строка
    remove_avatar: str = Form("0"),  # Новый флаг: "1" — удалить аватар
    avatar: UploadFile = File(None)
):
    # Проверяем, что пользователь изменяет только свой профиль
    cookie_user_id = request.cookies.get("user_id")
    if cookie_user_id != user_id:
        return HTMLResponse("Вы не можете изменять чужой профиль.", status_code=403)

    data = load_data()
    user = data.get("users", {}).get(user_id)
    if not user:
        return HTMLResponse("Пользователь не найден.", status_code=404)

    # Обновляем никнейм
    if username is not None and username.strip():
        user["username"] = username.strip()

    # Обновляем описание с проверкой длины
    if description is not None:
        if len(description) > 85:
            return HTMLResponse("Описание не может превышать 85 символов.", status_code=400)
        user["description"] = description

    avatars_dir = os.path.join("static", "avatars")
    # 1) Обработка удаления аватарки
    if remove_avatar == "1" and user.get("photo_url"):
        old = user["photo_url"]
        # Удаляем файл, если он в нашей папке
        if old.startswith("/static/avatars/"):
            path = old.lstrip("/")
            if os.path.exists(path):
                os.remove(path)
        user.pop("photo_url", None)

    # 2) Обработка загрузки новой аватарки (перекрывает старую, если была)
    if avatar is not None and avatar.filename:
        # Удаляем старый файл, если остался (на всякий случай)
        old = user.get("photo_url", "")
        if old.startswith("/static/avatars/"):
            path = old.lstrip("/")
            if os.path.exists(path):
                os.remove(path)

        # Сохраняем новый файл
        if not os.path.exists(avatars_dir):
            os.makedirs(avatars_dir)
        ext = avatar.filename.rsplit(".", 1)[-1]
        file_path = os.path.join(avatars_dir, f"{user_id}.{ext}")
        content = await avatar.read()
        with open(file_path, "wb") as f:
            f.write(content)
        user["photo_url"] = f"/static/avatars/{user_id}.{ext}"

    # Сохраняем изменения
    save_data(data)

    # Перенаправляем обратно на профиль
    return RedirectResponse(url=f"/profile/{user_id}", status_code=303)

@app.post("/update_order")
async def update_order(request: Request, payload: dict = Body(...)):
    user_id = request.cookies.get("user_id")
    if not user_id:
        return {"status": "error", "message": "Пользователь не авторизован."}
    data = load_data()
    user = data.get("users", {}).get(user_id)
    if not user or not user.get("logged_in"):
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
        return RedirectResponse(url="/login", status_code=303)

    data = load_data()
    user = data["users"][user_id]

    # Обновляем счётчики за день
    today = datetime.date.today().isoformat()
    if user.get("last_activation_date") != today:
        user["last_activation_date"] = today
        user["activation_count"] = 0
        user.setdefault("extra_attempts", 0)
    base_daily_limit = 0
    used = user.get("activation_count", 0)
    extra = user.get("extra_attempts", 0)
    attempts_left = (base_daily_limit + extra) - used

    balance = user.get("balance", 0)

    # Собираем 5 последних токенов
    all_tokens = user.get("tokens", [])
    recent_tokens = sorted(
        all_tokens,
        key=lambda t: t.get("timestamp", ""),
        reverse=True
    )[:5]

    return templates.TemplateResponse("mint.html", {
        "request": request,
        "user_id": user_id,
        "attempts_left": max(0, attempts_left),
        "balance": balance,
        "error": None,
        "recent_tokens": recent_tokens
    })


@app.post("/mint", response_class=HTMLResponse)
async def web_mint_post(request: Request, user_id: str = Form(None)):
    if not user_id or not require_web_login(request):
        return HTMLResponse("Ошибка: не найден Telegram ID.", status_code=400)

    data = load_data()
    user = ensure_user(data, user_id)

    # Обновляем счётчики за день
    today = datetime.date.today().isoformat()
    if user.get("last_activation_date") != today:
        user["last_activation_date"] = today
        user["activation_count"] = 0
        user.setdefault("extra_attempts", 0)
    base_daily_limit = 0
    used = user.get("activation_count", 0)
    extra = user.get("extra_attempts", 0)
    attempts_left = (base_daily_limit + extra) - used

    if attempts_left > 0:
        # бесплатный mint
        user["activation_count"] += 1
        token_data = generate_number()
        token_data["timestamp"] = datetime.datetime.now().isoformat()
        user.setdefault("tokens", []).append(token_data)
        save_data(data)
        return RedirectResponse(url=f"/profile/{user_id}", status_code=303)
    else:
        # платный mint
        if user.get("balance", 0) < 100:
            # недостаточно алмазов — ререндерим страницу с ошибкой, но также показываем recent_tokens
            all_tokens = user.get("tokens", [])
            recent_tokens = sorted(
                all_tokens,
                key=lambda t: t.get("timestamp", ""),
                reverse=True
            )[:5]
            return templates.TemplateResponse("mint.html", {
                "request": request,
                "user_id": user_id,
                "attempts_left": 0,
                "balance": user.get("balance", 0),
                "error": "Недостаточно алмазов для платного создания номера.",
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
        return RedirectResponse(url="/login", status_code=303)
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
        return RedirectResponse(url="/login", status_code=303)
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
        return RedirectResponse(url="/login", status_code=303)
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
        return HTMLResponse("Ошибка: не найден Telegram ID. Пожалуйста, войдите.", status_code=400)
    data = load_data()
    market = data.get("market", [])
    listing_index = None
    for i, listing in enumerate(market):
        if listing["token"].get("token") == listing_id:
            listing_index = i
            break
    if listing_index is None:
        return HTMLResponse("Неверный номер листинга.", status_code=400)
    listing = market[listing_index]
    seller_id = listing.get("seller_id")
    price = listing["price"]
    buyer = data.get("users", {}).get(buyer_id)
    if not buyer:
        return HTMLResponse("Покупатель не найден.", status_code=404)
    if buyer.get("balance", 0) < price:
        return RedirectResponse(url=f"/?error=Недостаточно%20средств", status_code=303)
    buyer["balance"] -= price
    seller = data.get("users", {}).get(seller_id)
    if seller:
        seller["balance"] = seller.get("balance", 0) + price
    if seller.get("custom_number") and seller["custom_number"].get("token") == listing["token"].get("token"):
        del seller["custom_number"]
    commission_rate = 0.05
    if "referrer" in buyer:
        referrer_id = buyer["referrer"]
        referrer = data.get("users", {}).get(referrer_id)
        if referrer:
            commission = int(price * commission_rate)
            referrer["balance"] = referrer.get("balance", 0) + commission
    token = listing["token"]
    token["bought_price"] = price
    token["bought_date"] = datetime.datetime.now().isoformat()
    token["bought_source"] = "market"
    token["seller_id"] = seller_id
    buyer.setdefault("tokens", []).append(token)
    market.pop(listing_index)
    save_data(data)
    if seller:
        try:
            await bot.send_message(int(seller_id), f"Уведомление: Ваш номер {token['token']} куплен за {price} 💎.")
        except Exception as e:
            print("Ошибка уведомления продавца:", e)
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
    user["custom_number"] = tokens[token_index - 1]
    save_data(data)
    response = RedirectResponse(url=f"/profile/{user_id}", status_code=303)
    return response

@app.post("/remove_profile_token", response_class=HTMLResponse)
async def remove_profile_token(request: Request, user_id: str = Form(...)):
    cookie_user_id = request.cookies.get("user_id")
    if cookie_user_id != user_id or not require_web_login(request):
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
    # Запускаем бота
    bot_task = asyncio.create_task(dp.start_polling(bot))
    # Запускаем функцию автоотмены обменов
    auto_cancel_task = asyncio.create_task(auto_cancel_exchanges())
    # Регистрируем фоновую задачу аукционов через функцию register_auction_tasks из auctions.py
    register_auction_tasks(asyncio.get_event_loop())
    # Запуск веб‑сервера
    config = uvicorn.Config(app, host="0.0.0.0", port=8000, log_level="info")
    server = uvicorn.Server(config)
    web_task = asyncio.create_task(server.serve())
    await asyncio.gather(bot_task, auto_cancel_task, web_task)

if __name__ == "__main__":
    asyncio.run(main())
