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
from aiogram.types import Message
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
        available = [(filename, info) for filename, info in limited_bgs.items() if info.get("used", 0) < info.get("max", 8)]
        if available:
            chosen_file, info = random.choice(available)
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

# ── Удаление пользователей без токенов ───────────────────────────────────────────
@dp.message(Command("cleanup_empty"))
async def cleanup_empty_accounts(message) -> None:
    if str(message.from_user.id) not in ADMIN_IDS:
        await message.answer("У вас нет прав для выполнения этой команды.")
        return

    data = load_data()
    users = data.get("users", {})
    # Собираем ID, у которых нет токенов или коллекция пуста
    empty_ids = [uid for uid, u in users.items() if not u.get("tokens")]
    if not empty_ids:
        await message.answer("✅ Нет аккаунтов без токенов.")
        return

    for uid in empty_ids:
        # удаляем пользователя
        users.pop(uid, None)
        # если он в бане — удаляем оттуда
        if uid in data.get("banned", []):
            data["banned"].remove(uid)

    save_data(data)
    await message.answer(
        f"✅ Удалены аккаунты без токенов: {', '.join(empty_ids)}"
    )

# ── Перенос аккаунта на другой ID ───────────────────────────────────────────────
@dp.message(Command("transfer_account"))
async def transfer_account_admin(message) -> None:
    if str(message.from_user.id) not in ADMIN_IDS:
        await message.answer("У вас нет прав для выполнения этой команды.")
        return

    parts = message.text.split()
    if len(parts) != 3:
        await message.answer("❗ Формат: /transfer_account <старый_id> <новый_id>")
        return

    old_id, new_id = parts[1], parts[2]
    data = load_data()
    users = data.get("users", {})

    if old_id not in users:
        await message.answer(f"❗ Пользователь с ID {old_id} не найден.")
        return
    if new_id in users:
        await message.answer(f"❗ Пользователь с новым ID {new_id} уже существует.")
        return

    # Переносим все данные
    users[new_id] = users.pop(old_id)

    # Обновляем также все упоминания в списке заблокированных
    banned = data.get("banned", [])
    if old_id in banned:
        banned.remove(old_id)
        banned.append(new_id)
        data["banned"] = banned

    save_data(data)
    await message.answer(
        f"✅ Аккаунт перенесён с ID {old_id} на ID {new_id}.\n"
        f"Старый ID более не активен, все данные теперь привязаны к {new_id}."
    )

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

@dp.message(Command("broadcast"))
async def broadcast(message: Message) -> None:
    if str(message.from_user.id) not in ADMIN_IDS:
        return await message.answer("❗ У вас нет доступа для выполнения этой команды.")

    # 1) Считаем «raw» — либо caption для фото/документа, 
    #    либо полный text для простого текста
    if message.photo or (message.document and message.document.mime_type.startswith("image/")):
        raw = message.caption or ""
    else:
        raw = message.text or ""

    # 2) Разбираем raw на три части: команда, опциональные ID, остальной текст
    #    .split(maxsplit=2) даст до трёх элементов
    parts = raw.split(maxsplit=2)

    # Обязательный минимум: ['/broadcast', ...]
    if len(parts) < 2:
        return await message.answer("❗ Формат: /broadcast [id1,id2,...] <сообщение> или пришлите фото с подписью")

    # 3) Попытаемся распознать parts[1] как список ID: цифры и запятые
    id_list = None
    if all(ch.isdigit() or ch==',' for ch in parts[1]):
        # распариваем "123,456,789"
        id_list = [uid.strip() for uid in parts[1].split(',') if uid.strip()]
        # текст сообщения будет в parts[2]
        if len(parts) < 3 or not parts[2].strip():
            return await message.answer("❗ После списка ID укажите текст сообщения")
        caption = parts[2].strip()
    else:
        # без списка ID — значит все, а весь остаток текста в parts[1]
        id_list = None
        caption = parts[1] if len(parts)==2 else parts[1] + ' ' + (parts[2] if len(parts)>2 else "")

    # 4) Определяем, что шлём: фото + текст или просто текст
    photo = None
    if message.photo:
        photo = message.photo[-1].file_id
    elif message.document and message.document.mime_type.startswith("image/"):
        photo = message.document.file_id

    # 5) Загружаем список пользователей и бан
    data = load_data()
    users = data.get("users", {})
    banned = set(data.get("banned", []))

    # 6) Определяем получателей: либо переданные ID, либо все
    if id_list:
        # оставляем только тех, кто есть в users и не в бане
        targets = [uid for uid in id_list if uid in users and uid not in banned]
    else:
        targets = [uid for uid in users if uid not in banned]

    # 7) Рассылка
    sent = failed = 0
    for uid in targets:
        try:
            if photo:
                await bot.send_photo(int(uid), photo=photo, caption=caption)
            else:
                await bot.send_message(int(uid), caption)
            sent += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.05)  # немного спим, чтобы не зря ограничение не поймать

    # 8) Ответ администратору
    await message.answer(
        f"📢 Рассылка выполнена:\n"
        f"‣ Запланировано: {len(targets)}\n"
        f"‣ Отправлено: {sent}\n"
        f"‣ Не доставлено: {failed}"
    )

@dp.message(Command("stats"))
async def bot_stats(message) -> None:
    if str(message.from_user.id) not in ADMIN_IDS:
        return await message.answer("❗ У вас нет доступа для этой команды.")

    data = load_data()
    users = data.get("users", {})

    total_users   = len(users)
    total_balance = sum(u.get("balance", 0) for u in users.values())

    # Топ-3 самых редких
    tokens = [
        {"token": t["token"], "rarity": t["overall_rarity"], "owner": u.get("username", uid)}
        for uid, u in users.items()
        for t in u.get("tokens", [])
    ]
    top_3 = sorted(tokens, key=lambda x: float(x["rarity"].strip("%")))[:3]

    today = datetime.date.today().isoformat()
    tokens_today = sum(
        1
        for u in users.values()
        for t in u.get("tokens", [])
        if t.get("timestamp", "").startswith(today)
    )
    new_users_today = sum(1 for u in users.values() if u.get("registration_date") == today)

    lines = [
        "📊 <b>Статистика бота</b>:",
        f"– Пользователей: <b>{total_users}</b>",
        f"– Общий баланс: <b>{total_balance}</b> 💎",
        "",
        "🏅 <b>Топ-3 самых редких номеров</b>:"
    ]
    if top_3:
        for i, item in enumerate(top_3, start=1):
            lines.append(f"{i}. {item['token']} — {item['rarity']} (владелец: {item['owner']})")
    else:
        lines.append("Пока нет токенов.")

    lines += [
        "",
        f"🆕 Токенов создано сегодня: <b>{tokens_today}</b>",
        f"👥 Новых пользователей сегодня: <b>{new_users_today}</b>"
    ]

    await message.answer("\n".join(lines), parse_mode="HTML")

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

@dp.message(Command("rebuilddb"))
async def rebuild_database(message: Message) -> None:
    # Только для админов
    if str(message.from_user.id) not in ADMIN_IDS:
        return await message.answer("❗ У вас нет доступа для выполнения этой команды.")

    data = load_data()

    # 1) Убедиться, что ключи есть
    data.setdefault("users", {})
    data.setdefault("limited_backgrounds", {})

    # 2) Сначала обнулим счётчики used в limited_backgrounds
    for info in data["limited_backgrounds"].values():
        info["used"] = 0

    # 3) Пройдём по всем пользователям и их токенам,
    #    найдём те, у которых bg_is_image и bg_rarity == "0.1%"
    #    и пересчитаем used, а также обновим bg_availability в самих токенах
    for uid, user in data["users"].items():
        for token in user.get("tokens", []):
            if token.get("bg_is_image") and token.get("bg_rarity") == "0.1%":
                # извлечь имя файла
                bg = token.get("bg_color", "")
                if bg.startswith("/static/image/"):
                    filename = bg.split("/")[-1]
                    lb = data["limited_backgrounds"].setdefault(filename, {"used": 0, "max": 0})
                    lb["used"] += 1
                    # и сразу обновляем у токена
                    token["bg_availability"] = f"{lb['used']}/{lb['max']}"

    # 4) После пересчёта saved backgrounds — ещё раз пробежим по всем токенам
    #    чтобы скорректировать bg_availability на случай, если max был добавлен администратором позже
    for uid, user in data["users"].items():
        for token in user.get("tokens", []):
            if token.get("bg_is_image") and token.get("bg_rarity") == "0.1%":
                bg = token.get("bg_color", "")
                filename = bg.split("/")[-1]
                lb = data["limited_backgrounds"].get(filename, {"used": 0, "max": 0})
                token["bg_availability"] = f"{lb['used']}/{lb['max']}"

    # 5) Сохраняем и отчитываемся
    save_data(data)
    await message.answer("✅ База данных успешно пересобрана и нормализована.")

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

    # Загружаем данные и инициализируем раздел limited_backgrounds
    data = load_data()
    lb = data.setdefault("limited_backgrounds", {})

    # Обновляем или создаём запись о лимитированном фоне
    lb[filename] = lb.get(filename, {"used": 0, "max": 0})
    lb[filename]["max"] = max_count

    # Сохраняем сразу, чтобы new max попал в диск
    save_data(data)

    # Обновляем у существующих токенов поле bg_availability
    target_bg = f"/static/image/{filename}"
    for uid, user in data.get("users", {}).items():
        for token in user.get("tokens", []):
            if token.get("bg_color") == target_bg and token.get("bg_rarity") == "0.1%":
                token["bg_availability"] = f"{lb[filename]['used']}/{max_count}"

    # Финишный сохранённый снимок
    save_data(data)

    await message.answer(
        f"✅ Лимитированный фон {filename} добавлен с лимитом {max_count} использований. "
        f"Все токены с этим фоном обновлены."
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
