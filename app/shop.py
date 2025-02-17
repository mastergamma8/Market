from aiogram import types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from common import bot, dp, load_data, save_data
from main import ADMIN_IDS

import datetime

# --- Конфигурация пакетов (придуманные цены) ---
DIAMONDS_PACKAGES = [
    {"amount": 50,  "price_rub": 99, "price_ton": 0.99},
    {"amount": 100, "price_rub": 189, "price_ton": 1.89},
    {"amount": 250, "price_rub": 449, "price_ton": 4.49},
]

ACTIVATIONS_PACKAGES = [
    {"amount": 1, "price_rub": 99, "price_ton": 0.99},
    {"amount": 3, "price_rub": 269, "price_ton": 2.69},
    {"amount": 5, "price_rub": 419, "price_ton": 4.19},
]

# Реквизиты для оплаты
PAYMENT_DETAILS_RUB = "Карта Юмани: 2204120118196936"
PAYMENT_DETAILS_TON = (
    "TON: UQB-qPuyNz9Ib75AHe43Jz39HBlThp9Bnvcetb06OfCnhsi2\n"
    "Cryptobot: t.me/send?start=IVnVvwBFGe5t"
)

# --- Команда /shop – вход в магазин ---
@dp.message(Command("shop"))
async def cmd_shop(message: types.Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton("Оплата RUB", callback_data="shop:payment:rub"),
            InlineKeyboardButton("Оплата TON/Cryptobot", callback_data="shop:payment:ton")
        ]
    ])
    await message.answer("Выберите способ оплаты:", reply_markup=keyboard)


# --- Обработчик выбора способа оплаты ---
@dp.callback_query_handler(lambda c: c.data and c.data.startswith("shop:payment:"))
async def process_payment_selection(callback_query: types.CallbackQuery):
    payment_method = callback_query.data.split(":")[2]
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton("Купить алмазы", callback_data=f"shop:product:diamonds:{payment_method}"),
            InlineKeyboardButton("Купить активации номера", callback_data=f"shop:product:activations:{payment_method}")
        ]
    ])
    await callback_query.message.edit_text("Выберите, что хотите купить:", reply_markup=keyboard)
    await callback_query.answer()


# --- Обработчик выбора продукта ---
@dp.callback_query_handler(lambda c: c.data and c.data.startswith("shop:product:"))
async def process_product_selection(callback_query: types.CallbackQuery):
    parts = callback_query.data.split(":")
    # parts: shop, product, <тип продукта>, <payment_method>
    product = parts[2]
    payment_method = parts[3]

    keyboard = InlineKeyboardMarkup(row_width=1)
    if product == "diamonds":
        for pkg in DIAMONDS_PACKAGES:
            amount = pkg["amount"]
            if payment_method == "rub":
                price = pkg["price_rub"]
                button_text = f"{amount} алмазов за {price}₽"
            else:
                price = pkg["price_ton"]
                button_text = f"{amount} алмазов за {price} USD"
            callback_data = f"shop:buy:diamonds:{amount}:{payment_method}"
            keyboard.add(InlineKeyboardButton(button_text, callback_data=callback_data))
    elif product == "activations":
        for pkg in ACTIVATIONS_PACKAGES:
            amount = pkg["amount"]
            if payment_method == "rub":
                price = pkg["price_rub"]
                button_text = f"{amount} активация(й) за {price}₽"
            else:
                price = pkg["price_ton"]
                button_text = f"{amount} активация(й) за {price} USD"
            callback_data = f"shop:buy:activations:{amount}:{payment_method}"
            keyboard.add(InlineKeyboardButton(button_text, callback_data=callback_data))
    else:
        await callback_query.answer("Неизвестный продукт.", show_alert=True)
        return

    await callback_query.message.edit_text("Выберите пакет:", reply_markup=keyboard)
    await callback_query.answer()


# --- Обработчик выбора пакета для покупки ---
@dp.callback_query_handler(lambda c: c.data and c.data.startswith("shop:buy:"))
async def process_purchase(callback_query: types.CallbackQuery):
    parts = callback_query.data.split(":")
    # parts: shop, buy, <продукт>, <amount>, <payment_method>
    product = parts[2]
    amount = parts[3]
    payment_method = parts[4]

    price = None
    if product == "diamonds":
        for pkg in DIAMONDS_PACKAGES:
            if str(pkg["amount"]) == amount:
                price = pkg["price_rub"] if payment_method == "rub" else pkg["price_ton"]
                break
    elif product == "activations":
        for pkg in ACTIVATIONS_PACKAGES:
            if str(pkg["amount"]) == amount:
                price = pkg["price_rub"] if payment_method == "rub" else pkg["price_ton"]
                break

    if price is None:
        await callback_query.answer("Пакет не найден.", show_alert=True)
        return

    details = PAYMENT_DETAILS_RUB if payment_method == "rub" else PAYMENT_DETAILS_TON
    text = (
        f"Вы выбрали покупку {amount} "
        f"{'алмазов' if product=='diamonds' else 'попытки активации'}.\n"
        f"Сумма к оплате: {price} {'₽' if payment_method=='rub' else 'TON'}.\n\n"
        f"Реквизиты для оплаты:\n{details}\n\n"
        f"После оплаты отправьте скриншот через команду:\n"
        f"/sendpayment {product} {amount}"
    )
    await callback_query.message.edit_text(text)
    await callback_query.answer()


# --- Команда для отправки скриншота оплаты ---
@dp.message(Command("sendpayment"))
async def send_payment(message: types.Message):
    parts = message.text.split()
    if len(parts) < 3:
        await message.answer("Используйте: /sendpayment <продукт: diamonds/activations> <количество>")
        return

    product = parts[1]
    amount = parts[2]

    if not message.photo:
        await message.answer("Пожалуйста, отправьте скриншот оплаты как фото вместе с командой /sendpayment.")
        return

    user_id = str(message.from_user.id)
    # Здесь можно сохранить заявку в базу или просто уведомить админов
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                int(admin_id),
                f"Поступила заявка на покупку:\n"
                f"Пользователь: {message.from_user.username or message.from_user.full_name} (ID: {user_id})\n"
                f"Продукт: {product}\n"
                f"Количество: {amount}\n"
                f"Скриншот оплаты:"
            )
            await bot.send_photo(int(admin_id), photo=message.photo[-1].file_id)
        except Exception as e:
            print(f"Ошибка отправки уведомления администратору {admin_id}: {e}")

    await message.answer("Ваше подтверждение оплаты отправлено администрации на рассмотрение. Ожидайте ответа.")


# --- Команда для администратора для отправки сообщения пользователю ---
@dp.message(Command("sendmsg"))
async def send_message_to_user(message: types.Message):
    if str(message.from_user.id) not in ADMIN_IDS:
        await message.answer("У вас нет прав для выполнения этой команды.")
        return

    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        await message.answer("Используйте: /sendmsg <user_id> <сообщение>")
        return

    target_user_id = parts[1]
    text = parts[2]
    try:
        await bot.send_message(int(target_user_id), f"Сообщение от администрации:\n{text}")
        await message.answer("Сообщение отправлено пользователю.")
    except Exception as e:
        await message.answer(f"Ошибка отправки сообщения: {e}")
