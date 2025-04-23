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
from aiogram.filters import Command
from aiogram import F
# Импорт роутера из exchange_web
from exchange_web import router as exchange_router

# Импорт общих функций, шаблонов и объектов бота из common.py
from common import load_data, save_data, ensure_user, templates, bot, dp, DATA_FILE, BOT_TOKEN
# Импорт функции auto_cancel_exchanges из exchange_commands
from exchange_commands import auto_cancel_exchanges

ADMIN_IDS = {"1809630966", "7053559428"}
BOT_USERNAME = "tthnftbot"

# ── Вспомогательные функции ─────────────────────────────────────────────────────

def compute_overall_rarity(num_rarity: str, text_rarity: str, bg_rarity: str) -> str:
    """
    Вычисляет «среднюю» редкость как геометрическое среднее трёх процентных значений.
    """
    def to_val(s):
        try:
            return float(s.strip('%').replace(',', '.'))
        except:
            return 1.0
    a, b, c = to_val(num_rarity), to_val(text_rarity), to_val(bg_rarity)
    overall = (a * b * c) ** (1/3)
    return f"{overall:.2f}%"

def generate_number_from_value(token_str: str) -> dict:
    """
    Создаёт минимальный объект токена по строковому значению.
    """
    max_repeats = max(len(list(group)) for _, group in itertools.groupby(token_str))
    # Для простоты кладём «неизвестные» редкости
    return {
        "token": token_str,
        "max_repeats": max_repeats,
        "number_rarity": "unknown",
        "text_color": "#000000",
        "text_rarity": "unknown",
        "bg_color": "#ffffff",
        "bg_rarity": "unknown",
        "bg_is_image": False,
        "bg_availability": None,
        "overall_rarity": "unknown",
        "timestamp": datetime.datetime.now().isoformat()
    }

# --- Административные команды ---

@dp.message(Command("verifycation"))
async def verify_user_admin(message) -> None:
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
async def unverify_user_admin(message) -> None:
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
async def set_balance(message) -> None:
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
async def ban_user_admin(message) -> None:
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
async def unban_user_admin(message) -> None:
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
async def list_tokens_admin(message) -> None:
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
async def set_token_admin(message) -> None:
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
async def set_token_bg_admin(message) -> None:
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
async def add_limited_bg(message) -> None:
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
    image_path = os.path.join("static", "image", filename)
    if not os.path.exists(image_path):
        await message.answer("❗ Файл не найден в папке static/image.")
        return
    data = load_data()
    if "limited_backgrounds" not in data:
        data["limited_backgrounds"] = {}
    if filename in data["limited_backgrounds"]:
        data["limited_backgrounds"][filename]["max"] = max_count
    else:
        data["limited_backgrounds"][filename] = {"used": 0, "max": max_count}
    
    target_bg = f"/static/image/{filename}"
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
async def add_attempts_admin(message) -> None:
    if str(message.from_user.id) not in ADMIN_IDS:
        await message.answer("❗ У вас нет доступа для выполнения этой команды.")
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

@dp.message(Command("gen_token"))
async def admin_generate_token(message) -> None:
    if str(message.from_user.id) not in ADMIN_IDS:
        await message.answer("❗ У вас нет доступа для выполнения этой команды.")
        return

    parts = message.text.split()
    if len(parts) != 6:
        await message.answer("❗ Формат: /gen_token <user_id> <номер токена> <редкость номера> <редкость фона> <редкость цвета цифр>\nНапример: /gen_token 123456789 888 0.1% 0.1% 0.1%")
        return

    target_user_id = parts[1]
    token_value   = parts[2]
    number_rarity = parts[3]
    bg_rarity     = parts[4]
    text_rarity   = parts[5]

    allowed_number = {"0.1%", "0.3%", "0.5%", "0.8%", "1%", "1.5%", "2%", "2.5%", "3%"}
    allowed_text   = {"0.1%", "0.5%", "1%", "1.5%", "2%", "2.5%", "3%"}
    allowed_bg     = {"0.1%", "0.5%", "1%", "1.5%", "2%", "2.5%", "3%"}

    if number_rarity not in allowed_number:
        await message.answer(f"❗ Недопустимая редкость номера. Допустимые: {', '.join(allowed_number)}")
        return
    if text_rarity not in allowed_text:
        await message.answer(f"❗ Недопустимая редкость цвета цифр. Допустимые: {', '.join(allowed_text)}")
        return
    if bg_rarity not in allowed_bg:
        await message.answer(f"❗ Недопустимая редкость фона. Допустимые: {', '.join(allowed_bg)}")
        return

    if text_rarity == "0.1%":
        text_pool = ["#FFFFFF", "#000000"]
    elif text_rarity == "0.5%":
        text_pool = [
            "linear-gradient(45deg, #00c2e6, #48d9af, #00cc1f)",
            "linear-gradient(45deg, #0099ff, #00ccff, #00ffcc)",
            "linear-gradient(45deg, #00bfff, #00f5ff, #00ff99)"
        ]
    elif text_rarity == "1%":
        text_pool = [
            "linear-gradient(45deg, #e60000, #e6b800, #66cc00)",
            "linear-gradient(45deg, #FF4500, #FFA500, #ADFF2F)",
            "linear-gradient(45deg, #FF6347, #FFD700, #98FB98)"
        ]
    elif text_rarity == "1.5%":
        text_pool = [
            "linear-gradient(45deg, #8E44AD, #3498DB, #2ECC71)",
            "linear-gradient(45deg, #9932CC, #00BFFF, #3CB371)",
            "linear-gradient(45deg, #8A2BE2, #1E90FF, #32CD32)"
        ]
    elif text_rarity == "2%":
        text_pool = ["#FF5733", "#33FFCE", "#FFD700", "#FF69B4", "#00FA9A"]
    elif text_rarity == "2.5%":
        text_pool = ["#8e44ad", "#2c3e50", "#DC143C", "#20B2AA", "#FFDAB9"]
    else:  # "3%"
        text_pool = ["#d35400", "#e67e22", "#27ae60", "#FF7F50", "#4682B4", "#9ACD32"]
    text_color = random.choice(text_pool)

    if bg_rarity == "0.1%":
        data = load_data()
        limited_bgs = data.get("limited_backgrounds", {})
        available = [(filename, info) for filename, info in limited_bgs.items() if info.get("used", 0) < info.get("max", 8)]
        if available:
            chosen_file, info = random.choice(available)
            info["used"] = info.get("used", 0) + 1
            save_data(data)
            bg_color = f"/static/image/{chosen_file}"
            bg_is_image = True
            bg_availability = f"{info['used']}/{info['max']}"
        else:
            bg_pool = ["linear-gradient(45deg, #000000, #111111, #222222)"]
            bg_color = random.choice(bg_pool)
            bg_is_image = False
            bg_availability = None
    elif bg_rarity == "0.5%":
        bg_pool = [
            "linear-gradient(45deg, #00e4ff, #58ffca, #00ff24)",
            "linear-gradient(45deg, #00bfff, #66ffe0, #00ff88)",
            "linear-gradient(45deg, #0099ff, #33ccff, #66ffcc)"
        ]
        bg_color = random.choice(bg_pool)
        bg_is_image = False
        bg_availability = None
    elif bg_rarity == "1%":
        bg_pool = [
            "linear-gradient(45deg, #ff0000, #ffd358, #82ff00)",
            "linear-gradient(45deg, #FF1493, #00CED1, #FFD700)",
            "linear-gradient(45deg, #FF6347, #FFD700, #98FB98)"
        ]
        bg_color = random.choice(bg_pool)
        bg_is_image = False
        bg_availability = None
    elif bg_rarity == "1.5%":
        bg_pool = [
            "linear-gradient(45deg, #FFC0CB, #FF69B4, #FF1493)",
            "linear-gradient(45deg, #FFB6C1, #FF69B4, #FF4500)",
            "linear-gradient(45deg, #FF69B4, #FF1493, #C71585)"
        ]
        bg_color = random.choice(bg_pool)
        bg_is_image = False
        bg_availability = None
    elif bg_rarity == "2%":
        bg_pool = ["#f1c40f", "#1abc9c", "#FF4500", "#32CD32", "#87CEEB"]
        bg_color = random.choice(bg_pool)
        bg_is_image = False
        bg_availability = None
    elif bg_rarity == "2.5%":
        bg_pool = ["#2ecc71", "#3498db", "#FF8C00", "#6A5ACD", "#40E0D0"]
        bg_color = random.choice(bg_pool)
        bg_is_image = False
        bg_availability = None
    else:
        bg_pool = ["#9b59b6", "#34495e", "#808000", "#FFD700", "#FF69B4", "#00CED1"]
        bg_color = random.choice(bg_pool)
        bg_is_image = False
        bg_availability = None

    overall_rarity = compute_overall_rarity(number_rarity, text_rarity, bg_rarity)

    token_data = {
        "token": token_value,
        "max_repeats": len(token_value),
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

    data = load_data()
    if "users" not in data or target_user_id not in data["users"]:
        await message.answer("❗ Пользователь не найден.")
        return

    user = data["users"][target_user_id]
    user.setdefault("tokens", []).append(token_data)
    data.setdefault("admin_generated", []).append(token_data)
    save_data(data)

    response_text = (
        f"✅ Сгенерирован токен для пользователя {target_user_id}:\n"
        f"Номер: {token_data['token']}\n"
        f"Редкость номера: {token_data['number_rarity']}\n"
        f"Цвет цифр: {token_data['text_color']} (редкость {token_data['text_rarity']})\n"
        f"Фон: {token_data['bg_color']} (редкость {token_data['bg_rarity']})\n"
        f"Общая редкость: {token_data['overall_rarity']}\n"
        f"Временная метка: {token_data['timestamp']}"
    )
    await message.answer(response_text, parse_mode="HTML")

@dp.message(Command("remove_token"))
async def remove_token_admin(message) -> None:
    if str(message.from_user.id) not in ADMIN_IDS:
        await message.answer("❗ У вас нет доступа для выполнения этой команды.")
        return

    parts = message.text.split()
    if len(parts) < 3:
        await message.answer("❗ Формат: /remove_token <user_id> <номер_позиции или диапазон (например, 5-10)> [дополнительные номера или диапазоны...]")
        return

    target_user_id = parts[1]
    indices_str = parts[2:]
    
    def parse_index_token(token: str):
        token = token.strip()
        if '-' in token:
            try:
                start, end = token.split('-', 1)
                start = int(start)
                end = int(end)
                if start > end:
                    start, end = end, start
                return list(range(start, end + 1))
            except ValueError:
                return None
        else:
            try:
                return [int(token)]
            except ValueError:
                return None

    all_indices = []
    for token in indices_str:
        parsed = parse_index_token(token)
        if parsed is None:
            await message.answer("❗ Проверьте, что все номера позиций или диапазоны заданы корректно.")
            return
        all_indices.extend(parsed)

    indices = [i - 1 for i in all_indices]
    
    data = load_data()
    if "users" not in data or target_user_id not in data["users"]:
        await message.answer("❗ Пользователь не найден.")
        return

    user = data["users"][target_user_id]
    tokens = user.get("tokens", [])
    if any(i < 0 or i >= len(tokens) for i in indices):
        await message.answer("❗ Один или несколько номеров позиций токенов неверны.")
        return

    indices = sorted(set(indices), reverse=True)
    removed_tokens = []
    for i in indices:
        token_removed = tokens.pop(i)
        if token_removed.get("bg_rarity") == "0.1%" and token_removed.get("bg_is_image"):
            bg_color_value = token_removed.get("bg_color", "")
            if bg_color_value.startswith("/static/image/"):
                filename = bg_color_value.replace("/static/image/", "")
                if "limited_backgrounds" in data and filename in data["limited_backgrounds"]:
                    info = data["limited_backgrounds"][filename]
                    if info.get("used", 0) > 0:
                        info["used"] -= 1
        removed_tokens.append((i + 1, token_removed))
    
    if "admin_generated" in data:
        for _, token_removed in removed_tokens:
            data["admin_generated"] = [
                t for t in data["admin_generated"]
                if t.get("token") != token_removed.get("token")
            ]
    
    save_data(data)
    removed_info = "\n".join([f"Позиция {pos}: токен {token['token']}" for pos, token in removed_tokens])
    await message.answer(
        f"✅ Успешно удалены следующие токены из коллекции пользователя {user.get('username', 'Неизвестный')} (ID: {target_user_id}):\n{removed_info}"
    )

@dp.message(Command("createvoucher"))
async def create_voucher_admin(message) -> None:
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

# Фолбэк для активации ваучеров (для сообщений, не начинающихся со слэша)
@dp.message(lambda message: message.text and not message.text.startswith("/"))
async def redeem_voucher_handler(message) -> None:
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
async def set_avatar_gif(message) -> None:
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
    old_photo_url = user.get("photo_url")
    if old_photo_url and old_photo_url.startswith("/static/avatars/"):
        old_filename = old_photo_url.replace("/static/avatars/", "")
        old_path = os.path.join(avatars_dir, old_filename)
        if os.path.exists(old_path):
            os.remove(old_path)
    filename = f"{target_user_id}.gif"
    file_path = os.path.join(avatars_dir, filename)
    with open(file_path, "wb") as f:
        f.write(file_bytes.getvalue())
    user["photo_url"] = f"/static/avatars/{filename}"
    save_data(data)
    await message.answer(f"✅ GIF-аватар для пользователя {target_user_id} обновлён!")

@dp.message(Command("getavatars"))
async def get_avatars(message) -> None:
    if str(message.from_user.id) not in ADMIN_IDS:
        await message.answer("У вас нет доступа для выполнения этой команды.")
        return
    data = load_data()
    temp_dir = "temp_avatars"
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)
    os.makedirs(temp_dir)
    avatars_dir = os.path.join("static", "avatars")
    for user_id, user in data.get("users", {}).items():
        photo_url = user.get("photo_url")
        if photo_url and photo_url.startswith("/static/avatars/"):
            filename = os.path.basename(photo_url)
            src_path = os.path.join(avatars_dir, filename)
            if os.path.exists(src_path):
                ext = os.path.splitext(filename)[1]
                dst_filename = f"{user_id}{ext}"
                dst_path = os.path.join(temp_dir, dst_filename)
                shutil.copy(src_path, dst_path)
    archive_name = "avatars"
    shutil.make_archive(archive_name, 'zip', temp_dir)
    from aiogram.types.input_file import FSInputFile
    document = FSInputFile(f"{archive_name}.zip")
    await message.answer_document(document=document, caption="Архив с аватарками пользователей")
    shutil.rmtree(temp_dir)
    os.remove(f"{archive_name}.zip")

@dp.message(Command("getdata"))
async def get_data_file(message) -> None:
    if str(message.from_user.id) not in ADMIN_IDS:
        await message.answer("У вас нет доступа для выполнения этой команды.")
        return
    if not os.path.exists(DATA_FILE):
        await message.answer("Файл data.json не найден.")
        return
    from aiogram.types.input_file import FSInputFile
    document = FSInputFile(DATA_FILE)
    await message.answer_document(document=document, caption="Содержимое файла data.json")

@dp.message(F.document)
async def handle_documents(message) -> None:
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
