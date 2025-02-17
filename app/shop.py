# shop.py
import datetime
from aiogram import types, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from common import bot, dp, load_data, save_data, ensure_user
from main import ADMIN_IDS  # Список администраторов определяется в main.py

# Глобальный словарь для хранения ожидающих покупок
pending_purchases = {}

# Определяем доступные пакеты для покупки алмазов и активации номера в двух валютах
packages = {
    "diamonds": {
        "rub": [
            {"id": "d1", "amount": 50, "price": 100},
            {"id": "d2", "amount": 120, "price": 200},
            {"id": "d3", "amount": 250, "price": 350},
        ],
        "ton": [
            {"id": "d1", "amount": 50, "price": 0.99},
            {"id": "d2", "amount": 120, "price": 1.79},
            {"id": "d3", "amount": 250, "price": 3.29},
        ],
    },
    "activation": {
        "rub": [
            {"id": "a1", "amount": 1, "price": 100},
            {"id": "a2", "amount": 5, "price": 450},
            {"id": "a3", "amount": 10, "price": 800},
        ],
        "ton": [
            {"id": "a1", "amount": 1, "price": 0.99},
            {"id": "a2", "amount": 5, "price": 4.49},
            {"id": "a3", "amount": 10, "price": 8.99},
        ],
    },
}

# ──────────────────────────────
# 1. Команда для входа в магазин
# ──────────────────────────────
@dp.message(Command("shop"))
async def shop_command(message: Message):
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Оплата в рублях", callback_data="shop:method:rub")],
            [InlineKeyboardButton(text="Оплата в TON/Cryptobot", callback_data="shop:method:ton")],
        ]
    )
    await message.answer("Выберите способ оплаты:", reply_markup=keyboard)

# ──────────────────────────────
# 2. Выбор способа оплаты
# ──────────────────────────────
@dp.callback_query(F.data.startswith("shop:method:"))
async def choose_payment_method(callback: CallbackQuery):
    parts = callback.data.split(":")
    if len(parts) < 3:
        await callback.answer("Ошибка данных")
        return
    payment_method = parts[2]  # rub или ton
    # Создаем клавиатуру для выбора типа покупки
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Купить алмазы", callback_data=f"shop:buy:diamonds:{payment_method}")],
            [InlineKeyboardButton(text="Купить активацию номера", callback_data=f"shop:buy:activation:{payment_method}")],
        ]
    )
    await callback.message.edit_text("Выберите, что хотите купить:", reply_markup=keyboard)
    await callback.answer()

# ──────────────────────────────
# 3. Выбор типа покупки и пакета
# ──────────────────────────────
@dp.callback_query(F.data.startswith("shop:buy:"))
async def choose_purchase_type(callback: CallbackQuery):
    parts = callback.data.split(":")
    if len(parts) < 4:
        await callback.answer("Ошибка данных")
        return
    purchase_type = parts[2]  # diamonds или activation
    payment_method = parts[3]  # rub или ton

    pkg_list = packages.get(purchase_type, {}).get(payment_method, [])
    if not pkg_list:
        await callback.answer("Нет доступных пакетов.")
        return

    # Создаем пустую клавиатуру с row_width=1
    keyboard = InlineKeyboardMarkup(inline_keyboard=[], row_width=1)
    for pkg in pkg_list:
        if purchase_type == "diamonds":
            text = f"{pkg['amount']} алмазов за {pkg['price']} " + ("₽" if payment_method == "rub" else "TON")
        else:
            text = f"{pkg['amount']} активация(ий) за {pkg['price']} " + ("₽" if payment_method == "rub" else "TON")
        callback_data = f"shop:select:{purchase_type}:{payment_method}:{pkg['id']}"
        keyboard.add(InlineKeyboardButton(text=text, callback_data=callback_data))

    await callback.message.edit_text("Выберите пакет:", reply_markup=keyboard)
    await callback.answer()

# ──────────────────────────────
# 4. Обработка выбора пакета
# ──────────────────────────────
@dp.callback_query(F.data.startswith("shop:select:"))
async def select_package(callback: CallbackQuery):
    parts = callback.data.split(":")
    if len(parts) < 5:
        await callback.answer("Ошибка данных")
        return
    purchase_type = parts[2]       # diamonds или activation
    payment_method = parts[3]      # rub или ton
    pkg_id = parts[4]

    pkg_list = packages.get(purchase_type, {}).get(payment_method, [])
    selected_pkg = next((p for p in pkg_list if p["id"] == pkg_id), None)
    if not selected_pkg:
        await callback.answer("Пакет не найден")
        return

    # Сохраняем ожидаемую покупку для пользователя (идентифицируем по user_id)
    user_id = str(callback.from_user.id)
    pending_purchases[user_id] = {
        "type": purchase_type,
        "payment_method": payment_method,
        "amount": selected_pkg["amount"],
        "price": selected_pkg["price"],
        "timestamp": datetime.datetime.now().isoformat(),
    }

    # Формируем реквизиты для оплаты
    if payment_method == "rub":
        payment_details = "Переведите средства на карту ЮMoney:\n2204120118196936"
        currency = "₽"
    else:
        payment_details = (
            "Переведите средства на следующие реквизиты:\n"
            "TON: UQB-qPuyNz9Ib75AHe43Jz39HBlThp9Bnvcetb06OfCnhsi2\n"
            "Cryptobot: t.me/send?start=IVnVvwBFGe5t"
        )
        currency = "TON"

    if purchase_type == "diamonds":
        item_text = f"{selected_pkg['amount']} алмазов"
    else:
        item_text = f"{selected_pkg['amount']} активация(ий) номера"

    msg = (
        f"Вы выбрали: {item_text}\n"
        f"Сумма к оплате: {selected_pkg['price']} {currency}\n\n"
        f"{payment_details}\n\n"
        "После оплаты отправьте скриншот платежа, отправив фото с подписью:\n"
        "<code>/sendpayment</code>\n\n"
        "Данные будут переданы администрации для проверки."
    )
    await callback.message.edit_text(msg, parse_mode="HTML")
    await callback.answer()

# ──────────────────────────────
# 5. Обработка отправки скриншота оплаты
# ──────────────────────────────
@dp.message(F.photo, F.caption.startswith("/sendpayment"))
async def process_payment_proof(message: Message):
    user_id = str(message.from_user.id)
    if user_id not in pending_purchases:
        await message.answer("У вас нет активной покупки. Пожалуйста, выберите пакет через /shop")
        return

    # Получаем данные покупки и удаляем их из pending_purchases
    purchase_info = pending_purchases.pop(user_id)
    await message.answer("Спасибо! Ваш платёж отправлен администрации на проверку. Ожидайте ответа.")

    # Формируем сообщение для администраторов
    user_info = f"Пользователь: {message.from_user.full_name} (ID: {user_id})"
    if purchase_info["type"] == "diamonds":
        item_text = f"{purchase_info['amount']} алмазов"
    else:
        item_text = f"{purchase_info['amount']} активация(ий) номера"

    payment_method = purchase_info["payment_method"]
    currency = "₽" if payment_method == "rub" else "TON"
    details = (
        f"{user_info}\n"
        f"Тип покупки: {purchase_info['type']}\n"
        f"Пакет: {item_text}\n"
        f"Сумма: {purchase_info['price']} {currency}"
    )

    # Отправляем фотографию со скриншотом и деталями оплаты каждому админу
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_photo(
                chat_id=int(admin_id),
                photo=message.photo[-1].file_id,
                caption=details,
            )
        except Exception as e:
            print(f"Ошибка отправки админу {admin_id}: {e}")

# ──────────────────────────────
# 6. Команда для администратора отправить сообщение пользователю
# ──────────────────────────────
@dp.message(Command("sendto"))
async def admin_send_message(message: Message):
    if str(message.from_user.id) not in ADMIN_IDS:
        await message.answer("У вас нет доступа к этой команде.")
        return

    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        await message.answer("Используйте: /sendto <user_id> <сообщение>")
        return

    target_user_id = parts[1]
    msg_text = parts[2]
    try:
        await bot.send_message(chat_id=int(target_user_id), text=msg_text)
        await message.answer("Сообщение отправлено.")
    except Exception as e:
        await message.answer(f"Ошибка отправки сообщения: {e}")
