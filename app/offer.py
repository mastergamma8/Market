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

# Импорт общих функций и объектов из вашего проекта (common.py)
from common import load_data, save_data, ensure_user, templates, bot, dp

# --- БОТ: команды для предложения цены ---

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
    # Поиск токена: сначала в коллекциях пользователей, затем в маркетплейсе
    found = None
    # Поиск в коллекциях пользователей
    for uid, user in data.get("users", {}).items():
        for token in user.get("tokens", []):
            if token.get("token") == token_value:
                found = (uid, token)
                break
        if found:
            break
    # Если не найден, ищем его среди листингов в маркетплейсе
    if not found:
        for listing in data.get("market", []):
            token = listing.get("token")
            if token and token.get("token") == token_value:
                found = (listing.get("seller_id"), token)
                break

    if not found:
        await message.answer("❗ Токен не найден.")
        return

    seller_id, token = found
    buyer_id = str(message.from_user.id)
    if buyer_id == seller_id:
        await message.answer("❗ Вы не можете предложить цену своему собственному номеру.")
        return

    # Проверяем баланс покупателя
    buyer = data.get("users", {}).get(buyer_id)
    if not buyer or buyer.get("balance", 0) < proposed_price:
        await message.answer("❗ Недостаточно средств для предложения цены.")
        return

    # Списываем средства (замораживаем их)
    buyer["balance"] -= proposed_price

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

    await message.answer(f"Предложение цены для номера {token_value} отправлено продавцу. Средства временно заморожены.")
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

    # Выполняем перевод средств и передачу токена
    buyer_id = offer["buyer_id"]
    seller_id = offer["seller_id"]
    proposed_price = offer["proposed_price"]
    token_value = offer["token"]["token"]

    # Найти продавца и покупателя
    buyer = data.get("users", {}).get(buyer_id)
    seller = data.get("users", {}).get(seller_id)
    if not seller or not buyer:
        await callback_query.answer("Ошибка: пользователь не найден.", show_alert=True)
        return

    # Добавляем списанные средства продавцу
    seller["balance"] = seller.get("balance", 0) + proposed_price

    # Передаём токен: удаляем его у продавца, добавляем покупателю
    token = offer["token"]
    # Ищем токен у продавца
    token_removed = False
    for idx, t in enumerate(seller.get("tokens", [])):
        if t.get("token") == token_value:
            seller["tokens"].pop(idx)
            token_removed = True
            break
    if not token_removed:
        # Если токен не найден в коллекции продавца, возможно, он выставлен на маркет
        for idx, listing in enumerate(data.get("market", [])):
            t = listing.get("token")
            if t and t.get("token") == token_value:
                data["market"].pop(idx)
                token_removed = True
                break
    # Добавляем токен покупателю
    buyer.setdefault("tokens", []).append(token)

    offer["status"] = "accepted"
    save_data(data)

    # Удаляем сообщение с inline кнопками (если возможно)
    try:
        await callback_query.message.delete()
    except Exception as e:
        print("Ошибка удаления сообщения:", e)

    try:
        await bot.send_message(int(buyer_id),
                               f"Ваше предложение цены для номера {token_value} было принято. Токен теперь ваш!")
    except Exception as e:
        print("Ошибка уведомления покупателя:", e)
    await callback_query.answer("Предложение принято.")

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

    # Возвращаем средства покупателю
    buyer_id = offer["buyer_id"]
    buyer = data.get("users", {}).get(buyer_id)
    if buyer:
        buyer["balance"] = buyer.get("balance", 0) + offer["proposed_price"]

    offer["status"] = "declined"
    save_data(data)

    # Удаляем сообщение с inline кнопками
    try:
        await callback_query.message.delete()
    except Exception as e:
        print("Ошибка удаления сообщения:", e)

    try:
        await bot.send_message(int(buyer_id),
                               f"Ваше предложение цены для номера {offer['token']['token']} было отклонено. Средства возвращены.")
    except Exception as e:
        print("Ошибка уведомления покупателя:", e)
    await callback_query.answer("Предложение отклонено.")

# --- ВЕБ: эндпоинты с использованием FastAPI ---

router = APIRouter()

@router.post("/offer", response_class=HTMLResponse)
async def web_offer(request: Request, token_value: str = Form(...), proposed_price: int = Form(...)):
    data = load_data()
    found = None
    # Поиск токена в коллекциях пользователей
    for uid, user in data.get("users", {}).items():
        for token in user.get("tokens", []):
            if token.get("token") == token_value:
                found = (uid, token)
                break
        if found:
            break
    # Если не найден, ищем его среди листингов на маркетплейсе
    if not found:
        for listing in data.get("market", []):
            token = listing.get("token")
            if token and token.get("token") == token_value:
                found = (listing.get("seller_id"), token)
                break

    if not found:
        return HTMLResponse("Токен не найден.", status_code=404)

    seller_id, token = found
    buyer_id = request.cookies.get("user_id")
    if not buyer_id:
        return HTMLResponse("Ошибка: не авторизован.", status_code=403)
    if buyer_id == seller_id:
        return HTMLResponse("Вы не можете предложить цену своему собственному номеру.", status_code=400)

    # Проверяем и списываем средства у покупателя
    buyer = data.get("users", {}).get(buyer_id)
    if not buyer or buyer.get("balance", 0) < proposed_price:
        return HTMLResponse("Недостаточно средств для предложения цены.", status_code=400)
    buyer["balance"] -= proposed_price

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
    buyer_id = offer["buyer_id"]
    seller_id = offer["seller_id"]
    proposed_price = offer["proposed_price"]
    token_value = offer["token"]["token"]

    # Найти продавца и покупателя
    buyer = data.get("users", {}).get(buyer_id)
    seller = data.get("users", {}).get(seller_id)
    if not seller or not buyer:
        return HTMLResponse("Ошибка: пользователь не найден.", status_code=404)
    # Передаем токен от продавца покупателю
    token = offer["token"]
    token_removed = False
    for idx, t in enumerate(seller.get("tokens", [])):
        if t.get("token") == token_value:
            seller["tokens"].pop(idx)
            token_removed = True
            break
    if not token_removed:
        for idx, listing in enumerate(data.get("market", [])):
            t = listing.get("token")
            if t and t.get("token") == token_value:
                data["market"].pop(idx)
                token_removed = True
                break
    buyer.setdefault("tokens", []).append(token)
    # Переводим списанные средства продавцу
    seller["balance"] = seller.get("balance", 0) + proposed_price

    offer["status"] = "accepted"
    save_data(data)
    try:
        await bot.send_message(int(buyer_id),
                               f"Ваше предложение цены для номера {token_value} было принято. Токен передан вам!")
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
    buyer_id = offer["buyer_id"]
    buyer = data.get("users", {}).get(buyer_id)
    if buyer:
        buyer["balance"] = buyer.get("balance", 0) + offer["proposed_price"]
    offer["status"] = "declined"
    save_data(data)
    try:
        await bot.send_message(int(buyer_id),
                               f"Ваше предложение цены для номера {offer['token']['token']} было отклонено. Средства возвращены.")
    except Exception as e:
        print("Ошибка уведомления покупателя:", e)
    return HTMLResponse("Предложение отклонено.")
