import os
import json
import random
import hashlib
import datetime
import asyncio

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.filters import Command
from fastapi import APIRouter, Request, Form, Body
from fastapi.responses import HTMLResponse, RedirectResponse

# Импорт общих функций и объектов из вашего проекта (файл common.py)
from common import load_data, save_data, ensure_user, templates, bot, dp

# Новый функционал – предложение цены для токена
# --- Команды бота ---

@dp.message(Command("offer"))
async def offer_price_command(message: Message) -> None:
    parts = message.text.split()
    if len(parts) != 3:
        await message.answer("❗ Формат: /offer <номер токена> <предложенная цена>")
        return
    token_value = parts[1]
    try:
        proposed_price = int(parts[2])
    except ValueError:
        await message.answer("❗ Цена должна быть числом.")
        return
    data = load_data()
    # Поиск токена в коллекциях пользователей
    found = None
    for uid, user in data.get("users", {}).items():
        for token in user.get("tokens", []):
            if token.get("token") == token_value:
                found = (uid, token)
                break
        if found:
            break
    if not found:
        await message.answer("❗ Токен не найден.")
        return
    seller_id, token = found
    buyer_id = str(message.from_user.id)
    if buyer_id == seller_id:
        await message.answer("❗ Вы не можете предложить цену своему собственному номеру.")
        return
    # Создаем уникальный идентификатор предложения
    offer_id = hashlib.md5(f"{buyer_id}{seller_id}{token_value}{datetime.datetime.now()}".encode()).hexdigest()[:8]
    offer = {
        "offer_id": offer_id,
        "buyer_id": buyer_id,
        "seller_id": seller_id,
        "token": token,
        "proposed_price": proposed_price,
        "timestamp": datetime.datetime.now().isoformat(),
        "status": "pending"
    }
    if "offers" not in data:
        data["offers"] = []
    data["offers"].append(offer)
    save_data(data)
    await message.answer(f"Предложение цены для номера {token_value} отправлено продавцу.")
    # Отправляем продавцу уведомление с inline-кнопками для принятия/отклонения
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Принять", callback_data=f"offer_accept_{offer_id}")],
        [InlineKeyboardButton(text="Отклонить", callback_data=f"offer_decline_{offer_id}")]
    ])
    try:
        await bot.send_message(int(seller_id),
                               f"Вам поступило предложение цены для номера {token_value}.\n"
                               f"Предложенная цена: {proposed_price} 💎",
                               reply_markup=keyboard)
    except Exception as e:
        await message.answer("Ошибка отправки уведомления продавцу.")
        print("Ошибка уведомления продавца по предложению цены:", e)

@dp.callback_query(lambda c: c.data.startswith("offer_accept_"))
async def offer_accept(callback_query: CallbackQuery) -> None:
    offer_id = callback_query.data[len("offer_accept_"):]
    data = load_data()
    offer = None
    for o in data.get("offers", []):
        if o.get("offer_id") == offer_id and o.get("status") == "pending":
            offer = o
            break
    if not offer:
        await callback_query.answer("Предложение уже обработано или не найдено.", show_alert=True)
        return
    offer["status"] = "accepted"
    save_data(data)
    await callback_query.answer("Вы приняли предложение цены.")
    try:
        await bot.send_message(int(offer["buyer_id"]),
                               f"Ваше предложение цены для номера {offer['token']['token']} было принято продавцом!")
    except Exception as e:
        print("Ошибка уведомления покупателя:", e)
    # Здесь можно добавить дополнительную логику перевода средств и передачи номера

@dp.callback_query(lambda c: c.data.startswith("offer_decline_"))
async def offer_decline(callback_query: CallbackQuery) -> None:
    offer_id = callback_query.data[len("offer_decline_"):]
    data = load_data()
    offer = None
    for o in data.get("offers", []):
        if o.get("offer_id") == offer_id and o.get("status") == "pending":
            offer = o
            break
    if not offer:
        await callback_query.answer("Предложение уже обработано или не найдено.", show_alert=True)
        return
    offer["status"] = "declined"
    save_data(data)
    await callback_query.answer("Вы отклонили предложение цены.")
    try:
        await bot.send_message(int(offer["buyer_id"]),
                               f"Ваше предложение цены для номера {offer['token']['token']} было отклонено продавцом.")
    except Exception as e:
        print("Ошибка уведомления покупателя:", e)

# --- Веб‑эндпоинты с использованием FastAPI ---
router = APIRouter()

@router.post("/offer", response_class=HTMLResponse)
async def web_offer(request: Request, token_value: str = Form(...), proposed_price: int = Form(...)):
    data = load_data()
    found = None
    for uid, user in data.get("users", {}).items():
        for token in user.get("tokens", []):
            if token.get("token") == token_value:
                found = (uid, token)
                break
        if found:
            break
    if not found:
        return HTMLResponse("Токен не найден.", status_code=404)
    seller_id, token = found
    buyer_id = request.cookies.get("user_id")
    if not buyer_id:
        return HTMLResponse("Ошибка: не авторизован.", status_code=403)
    if buyer_id == seller_id:
        return HTMLResponse("Вы не можете предложить цену своему собственному номеру.", status_code=400)
    offer_id = hashlib.md5(f"{buyer_id}{seller_id}{token_value}{datetime.datetime.now()}".encode()).hexdigest()[:8]
    offer = {
        "offer_id": offer_id,
        "buyer_id": buyer_id,
        "seller_id": seller_id,
        "token": token,
        "proposed_price": proposed_price,
        "timestamp": datetime.datetime.now().isoformat(),
        "status": "pending"
    }
    if "offers" not in data:
        data["offers"] = []
    data["offers"].append(offer)
    save_data(data)
    # В вебе просто возвращаем сообщение о том, что предложение отправлено
    return HTMLResponse(f"Предложение цены для номера {token_value} отправлено продавцу. (Offer ID: {offer_id})")

@router.post("/offer/accept", response_class=HTMLResponse)
async def web_offer_accept(request: Request, offer_id: str = Form(...)):
    data = load_data()
    offer = None
    for o in data.get("offers", []):
        if o.get("offer_id") == offer_id and o.get("status") == "pending":
            offer = o
            break
    if not offer:
        return HTMLResponse("Предложение уже обработано или не найдено.", status_code=404)
    offer["status"] = "accepted"
    save_data(data)
    try:
        await bot.send_message(int(offer["buyer_id"]),
                               f"Ваше предложение цены для номера {offer['token']['token']} было принято продавцом!")
    except Exception as e:
        print("Ошибка уведомления покупателя:", e)
    return HTMLResponse("Предложение принято.")

@router.post("/offer/decline", response_class=HTMLResponse)
async def web_offer_decline(request: Request, offer_id: str = Form(...)):
    data = load_data()
    offer = None
    for o in data.get("offers", []):
        if o.get("offer_id") == offer_id and o.get("status") == "pending":
            offer = o
            break
    if not offer:
        return HTMLResponse("Предложение уже обработано или не найдено.", status_code=404)
    offer["status"] = "declined"
    save_data(data)
    try:
        await bot.send_message(int(offer["buyer_id"]),
                               f"Ваше предложение цены для номера {offer['token']['token']} было отклонено продавцом.")
    except Exception as e:
        print("Ошибка уведомления покупателя:", e)
    return HTMLResponse("Предложение отклонено.")

# Если необходимо, можно добавить дополнительные эндпоинты для просмотра списка предложений и др.
