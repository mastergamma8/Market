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
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.types.input_file import FSInputFile  # Для отправки файлов

# Импорт для веб‑приложения
import uvicorn
from fastapi import FastAPI, Request, Form, Body
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

ADMIN_IDS = {"1809630966", "7053559428"}
BOT_USERNAME = "tthnftbot"

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
    if r < 0.006:
        text_pool = ["#FFFFFF", "#000000"]
        text_rarity = "0.1%"
    elif r < 0.01:
        # 0.5% редкость: используем градиент, чуть темнее фонового варианта
        text_pool = [
            "linear-gradient(45deg, #00c2e6, #48d9af, #00cc1f)",
            "linear-gradient(45deg, #00b3d1, #3fbba0, #00b81a)",
            "linear-gradient(45deg, #00a9cc, #389d9c, #00b016)"
        ]
        text_rarity = "0.5%"
    elif r < 0.03:
        # 1% редкость: используем градиент, темнее фонового варианта
        text_pool = [
            "linear-gradient(45deg, #e60000, #e6b800, #66cc00)",
            "linear-gradient(45deg, #cc0000, #cca700, #5fa600)",
            "linear-gradient(45deg, #b30000, #b3a100, #558f00)"
        ]
        text_rarity = "1%"
    elif r < 0.06:
        # 1.5% редкость: придуманный плавный градиент для текста, немного темнее фонового варианта
        text_pool = [
            "linear-gradient(45deg, #00a3b8, #1c9a90, #007070)",
            "linear-gradient(45deg, #0097ac, #179087, #006664)",
            "linear-gradient(45deg, #008b9f, #14827a, #005a58)"
        ]
        text_rarity = "1.5%"
    elif r < 0.16:
        text_pool = ["#FF5733", "#33FFCE"]
        text_rarity = "2%"
    elif r < 0.28:
        text_pool = ["#8e44ad", "#2c3e50"]
        text_rarity = "2.5%"
    else:
        text_pool = ["#d35400", "#e67e22", "#27ae60"]
        text_rarity = "3%"
    return random.choice(text_pool), text_rarity

def generate_bg_attributes() -> tuple:
    data = load_data()
    limited_bgs = data.get("limited_backgrounds", {})
    chance = 0.006  # вероятность выбора лимитированного фона (0.1%)
    r = random.random()
    if r < chance:
        available = []
        # Ищем среди лимитированных фонов те, что ещё не исчерпали лимит
        for filename, info in limited_bgs.items():
            if info.get("used", 0) < info.get("max", 8):
                available.append((filename, info))
        if available:
            chosen_file, info = random.choice(available)
            info["used"] = info.get("used", 0) + 1
            save_data(data)
            bg_value = f"/static/image/{chosen_file}"
            bg_rarity = "0.1%"
            bg_is_image = True
            bg_availability = f"{info['used']}/{info['max']}"
            return bg_value, bg_rarity, bg_is_image, bg_availability
    # Если лимитированный фон не выбран, продолжаем обычную генерацию
    if r < 0.01:
        # 0.5% редкость: фон – заданный градиент
        bg_pool = [
            "linear-gradient(45deg, #00e4ff, #58ffca, #00ff24)",
            "linear-gradient(45deg, #00dfff, #54ffc9, #00ff20)",
            "linear-gradient(45deg, #00e0ff, #5cffcd, #00ff2a)"
        ]
        bg_rarity = "0.5%"
        return random.choice(bg_pool), bg_rarity, False, None
    elif r < 0.03:
        # 1% редкость: фон – заданный градиент
        bg_pool = [
            "linear-gradient(45deg, #ff0000, #ffd358, #82ff00)",
            "linear-gradient(45deg, #f20000, #ffcf50, #80f200)",
            "linear-gradient(45deg, #e60000, #ffc840, #7ef000)"
        ]
        bg_rarity = "1%"
        return random.choice(bg_pool), bg_rarity, False, None
    elif r < 0.06:
        # 1.5% редкость: придуманный плавный градиент для фона
        bg_pool = [
            "linear-gradient(45deg, #00ced1, #20b2aa, #008b8b)",
            "linear-gradient(45deg, #00c1c8, #1fb6a1, #007f7f)",
            "linear-gradient(45deg, #00b5bf, #1aa08d, #007575)"
        ]
        bg_rarity = "1.5%"
        return random.choice(bg_pool), bg_rarity, False, None
    elif r < 0.16:
        bg_pool = ["#f1c40f", "#1abc9c"]
        bg_rarity = "2%"
        return random.choice(bg_pool), bg_rarity, False, None
    elif r < 0.28:
        bg_pool = ["#2ecc71", "#3498db"]
        bg_rarity = "2.5%"
        return random.choice(bg_pool), bg_rarity, False, None
    else:
        bg_pool = ["#9b59b6", "#34495e", "#808000"]
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
    number_rarity = compute_number_rarity(token_str)
    text_color, text_rarity = generate_text_attributes()
    bg_color, bg_rarity, bg_is_image, bg_availability = generate_bg_attributes()
    overall_rarity = compute_overall_rarity(number_rarity, text_rarity, bg_rarity)
    return {
        "token": token_str,
        "number_rarity": number_rarity,
        "text_color": text_color,
        "text_rarity": text_rarity,
        "bg_color": bg_color,
        "bg_rarity": bg_rarity,
        "bg_is_image": bg_is_image,
        "bg_availability": bg_availability,  # новое поле с информацией о наличии
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

# --- Обработчики команд бота ---

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
        # Если у пользователя уже есть аватар, удаляем его
        old_photo_url = user.get("photo_url")
        if old_photo_url and old_photo_url.startswith("/static/avatars/"):
            old_filename = old_photo_url.replace("/static/avatars/", "")
            old_path = os.path.join(avatars_dir, old_filename)
            if os.path.exists(old_path):
                os.remove(old_path)
        
        # Формируем имя файла только по user_id, без временной метки
        filename = f"{message.from_user.id}.jpg"
        file_path = os.path.join(avatars_dir, filename)
        
        with open(file_path, "wb") as f:
            f.write(file_bytes.getvalue())
        
        user["photo_url"] = f"/static/avatars/{filename}"
        save_data(data)
        
        await message.answer("✅ Аватар обновлён!")

@dp.message(Command("referral"))
async def referral_link(message: Message) -> None:
    user_id = str(message.from_user.id)
    referral_link = f"https://t.me/{BOT_USERNAME}?start=referral_{user_id}"
    await message.answer(f"Ваша реферальная ссылка:\n{referral_link}")

@dp.message(Command("referrals"))
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
async def mint_number(message: Message) -> None:
    data = load_data()
    user_id = str(message.from_user.id)
    user = ensure_user(data, user_id)
    
    # Обновляем данные, если день сменился
    today = datetime.date.today().isoformat()
    if user.get("last_activation_date") != today:
        user["last_activation_date"] = today
        user["activation_count"] = 0
        user["extra_attempts"] = user.get("extra_attempts", 0)
    
    base_daily_limit = 1  # базовое количество бесплатных попыток
    used_attempts = user["activation_count"]
    extra_attempts = user["extra_attempts"]
    attempts_left = (base_daily_limit + extra_attempts) - used_attempts
    
    if attempts_left > 0:
        # Создаем номер бесплатно
        user["activation_count"] += 1
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
        # Бесплатные попытки закончились
        if user.get("balance", 0) < 100:
            await message.answer("Бесплатные попытки закончились и у вас недостаточно алмазов для создания номера.")
        else:
            # Предлагаем создать номер за 100 алмазов через inline-кнопку
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
    # Списываем 100 алмазов и создаем номер
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
async def transfer_number(message: Message) -> None:
    parts = message.text.split()
    if len(parts) != 3:
        await message.answer("❗ Формат: /transfer <Telegram ID получателя> <номер вашего номера (1-based)>")
        return
    target_user_id = parts[1]
    try:
        token_index = int(parts[2]) - 1
    except ValueError:
        await message.answer("❗ Номер вашего номера должен быть числом.")
        return
    sender_id = str(message.from_user.id)
    if target_user_id == sender_id:
        await message.answer("❗ Вы не можете передать номер самому себе.")
        return
    data = load_data()
    sender = ensure_user(data, sender_id)
    tokens = sender.get("tokens", [])
    if token_index < 0 or token_index >= len(tokens):
        await message.answer("❗ Неверный номер из вашей коллекции.")
        return
    token = tokens.pop(token_index)
    receiver = ensure_user(data, target_user_id)
    receiver.setdefault("tokens", []).append(token)
    save_data(data)
    await message.answer(f"✅ Номер {token['token']} успешно передан пользователю {target_user_id}!")
    sender_name = sender.get("username", "Неизвестный")
    try:
        await bot.send_message(
            int(target_user_id),
            f"Вам передали коллекционный номер: {token['token']}!\nОтправитель: {sender_name} (ID: {sender_id})"
        )
    except Exception as e:
        print("Ошибка уведомления получателя:", e)

@dp.message(Command("collection"))
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
async def show_balance(message: Message) -> None:
    data = load_data()
    user = ensure_user(data, str(message.from_user.id))
    await message.answer(f"💎 Ваш баланс: {user.get('balance', 0)} 💎")

@dp.message(Command("sell"))
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
        msg += (f"{idx}. {token_info['token']} | Цена: {listing['price']} 💎 | Продавец: {seller_name} | "
                f"Редкость: {token_info.get('overall_rarity', 'неизвестно')}\n")
    MAX_LENGTH = 4096
    if len(msg) > MAX_LENGTH:
        for i in range(0, len(msg), MAX_LENGTH):
            await message.answer(msg[i:i+MAX_LENGTH])
    else:
        await message.answer(msg)

@dp.message(Command("buy"))
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
async def list_participants(message: Message) -> None:
    data = load_data()
    users = data.get("users", {})
    if not users:
        await message.answer("❗ Нет зарегистрированных участников.")
        return
    current_user_id = str(message.from_user.id)
    msg = "👥 Участники:\n"
    for uid, info in users.items():
        cnt = len(info.get("tokens", []))
        verified_mark = " ✅" if info.get("verified", False) else ""
        balance_info = f"Баланс: {info.get('balance', 0)} 💎" if uid == current_user_id else "Баланс: скрыт"
        msg += f"{info.get('username', 'Неизвестный')}{verified_mark} (ID: {uid}) — {balance_info}, номеров: {cnt}\n"
    MAX_LENGTH = 4096
    if len(msg) > MAX_LENGTH:
        for i in range(0, len(msg), MAX_LENGTH):
            await message.answer(msg[i:i+MAX_LENGTH])
    else:
        await message.answer(msg)

# --- Административные команды ---

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
    await message.answer(f"✅ Баланс пользователя {user.get('username', 'Неизвестный')} (ID: {target_user_id}) изменён с {old_balance} на {new_balance}.")

@dp.message(Command("ban"))
async def ban_user_admin(message: Message) -> None:
    if str(message.from_user.id) not in ADMIN_IDS:
        await message.answer("❗ У вас нет доступа для выполнения этой команды.")
        return
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("❗ Формат: /ban <user_id>")
        return
    target_user_id = parts[1]
    data = load_data()
    if "users" in data and target_user_id in data["users"]:
        del data["users"][target_user_id]
    banned_list = data.get("banned", [])
    if target_user_id not in banned_list:
        banned_list.append(target_user_id)
    data["banned"] = banned_list
    save_data(data)
    await message.answer(f"✅ Пользователь с ID {target_user_id} забанен и удален из базы данных.")

@dp.message(Command("unban"))
async def unban_user_admin(message: Message) -> None:
    if str(message.from_user.id) not in ADMIN_IDS:
        await message.answer("❗ У вас нет доступа для выполнения этой команды.")
        return
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("❗ Формат: /unban <user_id>")
        return
    target_user_id = parts[1]
    data = load_data()
    banned_list = data.get("banned", [])
    if target_user_id not in banned_list:
        await message.answer("❗ Пользователь не находится в черном списке.")
        return
    banned_list.remove(target_user_id)
    data["banned"] = banned_list
    save_data(data)
    await message.answer(f"✅ Пользователь с ID {target_user_id} снят с блокировки.")

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

@dp.message(Command("settokenbg"))
async def set_token_bg_admin(message: Message) -> None:
    if str(message.from_user.id) not in ADMIN_IDS:
        await message.answer("У вас нет доступа для выполнения этой команды.")
        return
    parts = message.text.split()
    if len(parts) < 5:
        await message.answer("❗ Формат: /settokenbg <user_id> <номер_позиции> <новый_фон> <новая_редкость>")
        return
    target_user_id = parts[1]
    try:
        token_index = int(parts[2]) - 1
    except ValueError:
        await message.answer("❗ Номер позиции должен быть числом.")
        return
    new_bg_value = parts[3]
    new_bg_rarity = parts[4]
    data = load_data()
    if "users" not in data or target_user_id not in data["users"]:
        await message.answer("❗ Пользователь не найден.")
        return
    user = data["users"][target_user_id]
    tokens = user.get("tokens", [])
    if token_index < 0 or token_index >= len(tokens):
        await message.answer("❗ Неверный номер позиции токена.")
        return
    token = tokens[token_index]
    if new_bg_rarity == "0.1%":
        limited_bgs = data.get("limited_backgrounds", {})
        if new_bg_value in limited_bgs:
            info = limited_bgs[new_bg_value]
            # Увеличиваем счётчик использования для выбранного лимитированного фона
            info["used"] = info.get("used", 0) + 1
            token["bg_color"] = f"/static/image/{new_bg_value}"
            token["bg_is_image"] = True
            token["bg_availability"] = f"{info['used']}/{info['max']}"
        else:
            await message.answer("❗ Лимитированный фон не найден в базе.")
            return
    else:
        token["bg_color"] = new_bg_value
        token["bg_is_image"] = False
        token["bg_availability"] = None
    token["bg_rarity"] = new_bg_rarity
    token["overall_rarity"] = compute_overall_rarity(token["number_rarity"], token["text_rarity"], new_bg_rarity)
    save_data(data)
    await message.answer(f"✅ Фон для токена {token['token']} пользователя {target_user_id} изменён.")

@dp.message(Command("addlimitedbg"))
async def add_limited_bg(message: Message) -> None:
    if str(message.from_user.id) not in ADMIN_IDS:
        await message.answer("❗ У вас нет доступа для выполнения этой команды.")
        return
    parts = message.text.split()
    if len(parts) != 3:
        await message.answer("❗ Формат: /addlimitedbg <имя_файла> <максимальное_количество>")
        return
    filename = parts[1]
    try:
        max_count = int(parts[2])
    except ValueError:
        await message.answer("❗ Максимальное количество должно быть числом.")
        return
    # Проверяем наличие файла в папке static/image
    image_path = os.path.join("static", "image", filename)
    if not os.path.exists(image_path):
        await message.answer("❗ Файл не найден в папке static/image.")
        return
    data = load_data()
    if "limited_backgrounds" not in data:
        data["limited_backgrounds"] = {}
    # Если фон уже есть, обновляем max; иначе – создаём новую запись с used = 0
    if filename in data["limited_backgrounds"]:
        data["limited_backgrounds"][filename]["max"] = max_count
    else:
        data["limited_backgrounds"][filename] = {"used": 0, "max": max_count}
    
    target_bg = f"/static/image/{filename}"
    # Обновляем все токены, использующие этот лимитированный фон
    for uid, user in data.get("users", {}).items():
        tokens = user.get("tokens", [])
        for token in tokens:
            if token.get("bg_color") == target_bg and token.get("bg_rarity") == "0.1%":
                used = data["limited_backgrounds"][filename]["used"]
                token["bg_availability"] = f"{used}/{max_count}"
    save_data(data)
    await message.answer(
        f"✅ Лимитированный фон {filename} добавлен с лимитом {max_count} использований. Все токены с этим фоном обновлены."
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

@dp.message(Command("remove_token"))
async def remove_token_admin(message: Message) -> None:
    if str(message.from_user.id) not in ADMIN_IDS:
        await message.answer("❗ У вас нет доступа для выполнения этой команды.")
        return
    parts = message.text.split()
    if len(parts) < 3:
        await message.answer("❗ Формат: /remove_token <user_id> <номер_позиции1> [<номер_позиции2> ...]")
        return
    target_user_id = parts[1]
    indices_str = parts[2:]
    try:
        # Преобразуем номера позиций из строки в числа (с учетом 1-based нумерации)
        indices = [int(i) - 1 for i in indices_str]
    except ValueError:
        await message.answer("❗ Проверьте, что все номера позиций являются числами.")
        return
    data = load_data()
    if "users" not in data or target_user_id not in data["users"]:
        await message.answer("❗ Пользователь не найден.")
        return
    user = data["users"][target_user_id]
    tokens = user.get("tokens", [])
    # Проверяем, что все индексы корректны
    if any(i < 0 or i >= len(tokens) for i in indices):
        await message.answer("❗ Один или несколько номеров позиций токенов неверны.")
        return
    # Сортируем индексы в порядке убывания, чтобы удаление не сдвигало позиции
    indices.sort(reverse=True)
    removed_tokens = []
    for i in indices:
        removed_tokens.append((i + 1, tokens.pop(i)))  # сохраняем номер позиции (1-based) и данные токена
    save_data(data)
    removed_info = "\n".join([f"Позиция {pos}: токен {token['token']}" for pos, token in removed_tokens])
    await message.answer(
        f"✅ Успешно удалены следующие токены из коллекции пользователя {user.get('username', 'Неизвестный')} (ID: {target_user_id}):\n{removed_info}"
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
        f"✅ Ваучер создан:\nТип: {voucher_type}\nЗначение: {value}\nКоличество активаций: {max_uses}\nКод: {code}\n"
        f"Ссылка для активации ваучера: {voucher_link}"
    )

# Фолбэк для активации ваучеров (только для сообщений, не начинающихся со слэша)
@dp.message(lambda message: message.text and not message.text.startswith("/"))
async def redeem_voucher_handler(message: Message) -> None:
    text = message.text.strip()

    if not text.startswith("redeem_"):
        return

    voucher_code = text[len("redeem_"):]
    data = load_data()
    voucher = None
    for v in data.get("vouchers", []):
        if v.get("code") == voucher_code:
            voucher = v
            break
    if voucher is None:
        await message.answer("❗ Ваучер не найден или недействителен.")
        return
    if voucher.get("redeemed_count", 0) >= voucher.get("max_uses", 1):
        await message.answer("❗ Этот ваучер уже исчерпан.")
        return
    redeemed_by = voucher.get("redeemed_by", [])
    if str(message.from_user.id) in redeemed_by:
        await message.answer("❗ Вы уже активировали этот ваучер.")
        return

    user_id = str(message.from_user.id)
    user = data.get("users", {}).get(user_id)
    if not user:
        user = {"username": message.from_user.username or message.from_user.first_name}
        data.setdefault("users", {})[user_id] = user

    if voucher["type"] == "activation":
        today = datetime.date.today().isoformat()
        if user.get("last_activation_date") != today:
            user["last_activation_date"] = today
            user["activation_count"] = 0
            user["extra_attempts"] = 0
        user["extra_attempts"] = user.get("extra_attempts", 0) + voucher["value"]
        effective_limit = 1 + user.get("extra_attempts", 0)
        remaining = effective_limit - user.get("activation_count", 0)
        redemption_message = (f"✅ Ваучер активирован! Вам добавлено {voucher['value']} дополнительных попыток активации на сегодня. "
                              f"Осталось попыток: {remaining}.")
    elif voucher["type"] == "money":
        user["balance"] = user.get("balance", 0) + voucher["value"]
        redemption_message = f"✅ Ваучер активирован! Вам зачислено {voucher['value']} единиц на баланс."
    else:
        redemption_message = "❗ Неизвестный тип ваучера."

    redeemed_by.append(str(message.from_user.id))
    voucher["redeemed_by"] = redeemed_by
    voucher["redeemed_count"] = voucher.get("redeemed_count", 0) + 1
    save_data(data)
    await message.answer(redemption_message)

@dp.message(Command("setavatar_gif"))
async def set_avatar_gif(message: Message) -> None:
    if str(message.from_user.id) not in ADMIN_IDS:
        await message.answer("❗ У вас нет прав для выполнения этой команды.")
        return

    command_text = message.text or message.caption or ""
    parts = command_text.split()
    target_user_id = parts[1] if len(parts) > 1 else str(message.from_user.id)

    if not message.animation:
        await message.answer("❗ Пожалуйста, отправьте GIF-анимацию с командой /setavatar_gif.")
        return

    avatars_dir = os.path.join("static", "avatars")
    if not os.path.exists(avatars_dir):
        os.makedirs(avatars_dir)

    animation = message.animation
    file_info = await bot.get_file(animation.file_id)
    file_bytes = await bot.download_file(file_info.file_path)

    data = load_data()
    user = ensure_user(data, target_user_id, message.from_user.username or message.from_user.first_name)
    # Если у пользователя уже есть аватар, удаляем его
    old_photo_url = user.get("photo_url")
    if old_photo_url and old_photo_url.startswith("/static/avatars/"):
        old_filename = old_photo_url.replace("/static/avatars/", "")
        old_path = os.path.join(avatars_dir, old_filename)
        if os.path.exists(old_path):
            os.remove(old_path)
    
    # Формируем имя файла по target_user_id без временной метки
    filename = f"{target_user_id}.gif"
    file_path = os.path.join(avatars_dir, filename)
    with open(file_path, "wb") as f:
        f.write(file_bytes.getvalue())
    user["photo_url"] = f"/static/avatars/{filename}"
    save_data(data)
    await message.answer(f"✅ GIF-аватар для пользователя {target_user_id} обновлён!")

@dp.message(Command("getavatars"))
async def get_avatars(message: Message) -> None:
    if str(message.from_user.id) not in ADMIN_IDS:
        await message.answer("У вас нет доступа для выполнения этой команды.")
        return

    data = load_data()
    # Создаем временную папку для копирования аватарок
    temp_dir = "temp_avatars"
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)
    os.makedirs(temp_dir)

    avatars_dir = os.path.join("static", "avatars")
    # Для каждого пользователя из базы, если указан photo_url, копируем файл с переименованием
    for user_id, user in data.get("users", {}).items():
        photo_url = user.get("photo_url")
        if photo_url and photo_url.startswith("/static/avatars/"):
            filename = os.path.basename(photo_url)
            src_path = os.path.join(avatars_dir, filename)
            if os.path.exists(src_path):
                ext = os.path.splitext(filename)[1]  # получаем расширение
                dst_filename = f"{user_id}{ext}"
                dst_path = os.path.join(temp_dir, dst_filename)
                shutil.copy(src_path, dst_path)
    
    # Архивируем временную папку в ZIP‑файл
    archive_name = "avatars"
    shutil.make_archive(archive_name, 'zip', temp_dir)
    
    document = FSInputFile(f"{archive_name}.zip")
    await message.answer_document(document=document, caption="Архив с аватарками пользователей")
    
    # Чистим временную папку и архив
    shutil.rmtree(temp_dir)
    os.remove(f"{archive_name}.zip")

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
async def handle_documents(message: Message) -> None:
    if not message.caption:
        return  # Если подпись отсутствует, не обрабатываем документ

    caption = message.caption.strip()

    # Восстановление аватарок из архива
    if caption.startswith("/setavatars"):
        if str(message.from_user.id) not in ADMIN_IDS:
            await message.answer("У вас нет доступа для выполнения этой команды.")
            return

        if not message.document.file_name.endswith(".zip"):
            await message.answer("❗ Файл должен быть в формате ZIP.")
            return

        try:
            file_info = await bot.get_file(message.document.file_id)
            file_bytes = await bot.download_file(file_info.file_path)
            zip_data = io.BytesIO(file_bytes.getvalue())
            with zipfile.ZipFile(zip_data, 'r') as zip_ref:
                extract_path = os.path.join("static", "avatars")
                if not os.path.exists(extract_path):
                    os.makedirs(extract_path)
                zip_ref.extractall(extract_path)
            await message.answer("✅ Аватарки успешно восстановлены из архива.")
        except Exception as e:
            await message.answer(f"❗ Произошла ошибка при восстановлении аватарок: {e}")

    # Обновление базы данных из файла
    elif caption.startswith("/setdb"):
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

# Подключаем роутеры веб-приложения
app.include_router(exchange_router)
app.include_router(auctions_router)

# Настройка шаблонов
templates = Jinja2Templates(directory="templates")
templates.env.globals["enumerate"] = enumerate
# Предполагается, что функция get_rarity определена в одном из модулей (например, в common.py)
templates.env.globals["get_rarity"] = get_rarity

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
    if user.get("logged_in"):
        response = RedirectResponse(url=f"/profile/{user_id}", status_code=303)
        response.set_cookie("user_id", user_id, max_age=60*60*24*30, path="/")
        return response
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

@app.get("/auto_login", response_class=HTMLResponse)
async def auto_login(request: Request, user_id: str):
    data = load_data()
    user = data.get("users", {}).get(user_id)
    if not user or not user.get("logged_in"):
        return RedirectResponse(url="/login", status_code=303)
    response = RedirectResponse(url=f"/profile/{user_id}", status_code=303)
    response.set_cookie("user_id", user_id, max_age=60*60*24*30, path="/")
    return response

@app.get("/profile/{user_id}", response_class=HTMLResponse)
async def profile(request: Request, user_id: str):
    data = load_data()
    user = data.get("users", {}).get(user_id)
    if not user:
        return HTMLResponse("Пользователь не найден.", status_code=404)
    current_user_id = request.cookies.get("user_id")
    is_owner = (current_user_id == user_id)
    tokens_count = len(user.get("tokens", []))
    return templates.TemplateResponse("profile.html", {
        "request": request,
        "user": user,
        "user_id": user_id,
        "is_owner": is_owner,
        "tokens_count": tokens_count
    })

@app.post("/update_description", response_class=HTMLResponse)
async def update_description(request: Request, user_id: str = Form(...), description: str = Form(...)):
    cookie_user_id = request.cookies.get("user_id")
    if cookie_user_id != user_id:
        return HTMLResponse("Вы не можете изменять чужой профиль.", status_code=403)
    data = load_data()
    user = data.get("users", {}).get(user_id)
    if not user:
        return HTMLResponse("Пользователь не найден.", status_code=404)
    user["description"] = description
    save_data(data)
    response = RedirectResponse(url=f"/profile/{user_id}", status_code=303)
    return response

@app.post("/update_order")
async def update_order(request: Request, payload: dict = Body(...)):
    # Получаем user_id из cookies
    user_id = request.cookies.get("user_id")
    if not user_id:
        return {"status": "error", "message": "Пользователь не авторизован."}

    data = load_data()
    user = data.get("users", {}).get(user_id)
    if not user:
        return {"status": "error", "message": "Пользователь не найден."}

    order = payload.get("order")
    if not order or not isinstance(order, list):
        return {"status": "error", "message": "Неверный формат данных."}

    tokens = user.get("tokens", [])
    # Создаем словарь для быстрого поиска: ключ – уникальный идентификатор токена
    token_dict = { token["token"]: token for token in tokens }
    # Собираем новый список токенов согласно полученному порядку
    new_tokens = [token_dict[t] for t in order if t in token_dict]

    # Если вдруг получен неполный порядок – добавляем недостающие токены в конец
    if len(new_tokens) != len(tokens):
        for token in tokens:
            if token["token"] not in order:
                new_tokens.append(token)

    user["tokens"] = new_tokens
    save_data(data)
    return {"status": "ok", "message": "Порядок обновлён"}

@app.get("/mint", response_class=HTMLResponse)
async def web_mint(request: Request):
    user_id = request.cookies.get("user_id")
    if not user_id:
        return RedirectResponse(url="/login", status_code=303)

    data = load_data()
    user = data.get("users", {}).get(user_id)
    if not user:
        return HTMLResponse("Пользователь не найден.", status_code=404)

    # Обновляем счётчик, если день сменился
    today = datetime.date.today().isoformat()
    if user.get("last_activation_date") != today:
        user["last_activation_date"] = today
        user["activation_count"] = 0
        user["extra_attempts"] = user.get("extra_attempts", 0)

    base_daily_limit = 1
    used_attempts = user["activation_count"]
    extra_attempts = user["extra_attempts"]
    attempts_left = (base_daily_limit + extra_attempts) - used_attempts
    balance = user.get("balance", 0)

    return templates.TemplateResponse(
        "mint.html",
        {
            "request": request,
            "user_id": user_id,
            "attempts_left": max(0, attempts_left),
            "balance": balance,
            "error": None
        }
    )


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
        user["extra_attempts"] = user.get("extra_attempts", 0)

    base_daily_limit = 1
    used_attempts = user["activation_count"]
    extra_attempts = user["extra_attempts"]
    attempts_left = (base_daily_limit + extra_attempts) - used_attempts

    if attempts_left > 0:
        # Создаём номер бесплатно
        user["activation_count"] += 1
        token_data = generate_number()
        token_data["timestamp"] = datetime.datetime.now().isoformat()
        user.setdefault("tokens", []).append(token_data)
        save_data(data)
        return RedirectResponse(url=f"/profile/{user_id}", status_code=303)
    else:
        # Проверяем, есть ли 100 алмазов
        if user.get("balance", 0) < 100:
            return templates.TemplateResponse(
                "mint.html",
                {
                    "request": request,
                    "user_id": user_id,
                    "attempts_left": 0,
                    "balance": user.get("balance", 0),
                    "error": "Недостаточно алмазов для платного создания номера."
                }
            )
        # Списываем 100 алмазов и создаём номер
        user["balance"] -= 100
        token_data = generate_number()
        token_data["timestamp"] = datetime.datetime.now().isoformat()
        user.setdefault("tokens", []).append(token_data)
        save_data(data)
        return RedirectResponse(url=f"/profile/{user_id}", status_code=303)

@app.get("/token/{token_value}", response_class=HTMLResponse)
async def token_detail(request: Request, token_value: str):
    data = load_data()
    matching_tokens = []  # Список найденных токенов с одинаковым значением

    # Поиск токенов в коллекциях пользователей
    for uid, user in data.get("users", {}).items():
        for token in user.get("tokens", []):
            if token.get("token") == token_value:
                matching_tokens.append({
                    "token": token,
                    "owner_id": uid,
                    "source": "collection"  # Из коллекции пользователя
                })

    # Поиск токенов на маркетплейсе
    for listing in data.get("market", []):
        token = listing.get("token")
        if token and token.get("token") == token_value:
            matching_tokens.append({
                "token": token,
                "owner_id": listing.get("seller_id"),
                "source": "market",  # Выставлен на продажу
                "price": listing.get("price")
            })

    # Добавляем поиск токенов на аукционе (при условии, что такие данные хранятся в data["auctions"])
    for auction in data.get("auctions", []):
        token = auction.get("token")
        if token and token.get("token") == token_value:
            matching_tokens.append({
                "token": token,
                "owner_id": auction.get("seller_id"),
                "source": "auction",  # Выставлен на аукционе
                "auction_status": auction.get("status"),       # Например, статус аукциона
                "current_bid": auction.get("current_bid")        # Текущая ставка (если требуется)
            })

    if matching_tokens:
        return templates.TemplateResponse("token_detail.html", {
            "request": request,
            "token_value": token_value,
            "tokens": matching_tokens,
            "error": None
        })
    else:
        # Если токен не найден — возвращаем шаблон с параметром error
        return templates.TemplateResponse("token_detail.html", {
            "request": request,
            "token_value": token_value,
            "tokens": [],
            "error": "Токен не найден."
        })

@app.get("/transfer", response_class=HTMLResponse)
async def transfer_page(request: Request):
    return templates.TemplateResponse("transfer.html", {"request": request})

@app.post("/transfer", response_class=HTMLResponse)
async def transfer_post(request: Request, user_id: str = Form(...), token_index: int = Form(...), target_id: str = Form(...)):
    if not user_id:
        user_id = request.cookies.get("user_id")
    if not user_id:
        return HTMLResponse("Ошибка: не найден Telegram ID. Пожалуйста, войдите.", status_code=400)
    data = load_data()
    sender = data.get("users", {}).get(user_id)
    if not sender:
        return HTMLResponse("Пользователь не найден.", status_code=404)
    tokens = sender.get("tokens", [])
    if token_index < 1 or token_index > len(tokens):
        return HTMLResponse("Неверный номер из вашей коллекции.", status_code=400)
    token = tokens.pop(token_index - 1)
    receiver = ensure_user(data, target_id)
    receiver.setdefault("tokens", []).append(token)
    save_data(data)
    sender_name = sender.get("username", "Неизвестный")
    try:
        await bot.send_message(
            int(target_id),
            f"Вам передали коллекционный номер через веб: {token['token']}!\nОтправитель: {sender_name} (ID: {user_id})"
        )
    except Exception as e:
        print("Ошибка уведомления получателя через веб:", e)
    message_info = f"Номер {token['token']} передан пользователю {target_id}."
    return templates.TemplateResponse("profile.html", {"request": request, "user": sender, "user_id": user_id, "message": message_info})

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

@app.get("/participants", response_class=HTMLResponse)
async def web_participants(request: Request):
    data = load_data()
    users = data.get("users", {})
    current_user_id = request.cookies.get("user_id")
    return templates.TemplateResponse("participants.html", {"request": request, "users": users, "current_user_id": current_user_id})

@app.get("/market", response_class=HTMLResponse)
async def web_market(request: Request):
    data = load_data()
    market = data.get("market", [])
    return templates.TemplateResponse("market.html", {"request": request, "market": market, "users": data.get("users", {}), "buyer_id": request.cookies.get("user_id")})

@app.post("/buy/{listing_id}")
async def web_buy(request: Request, listing_id: str, buyer_id: str = Form(None)):
    if not buyer_id:
        buyer_id = request.cookies.get("user_id")
    if not buyer_id:
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
    if not user_id:
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
    if not user_id:
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
    market.pop(listing_index)
    user = data.get("users", {}).get(user_id)
    if user:
        user.setdefault("tokens", []).append(listing["token"])
    save_data(data)
    return RedirectResponse(url=f"/profile/{user_id}", status_code=303)

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
