# store.py
import logging
from aiogram import Router, types
from aiogram.filters import Command, Text
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from common import bot  # Используем экземпляр бота из common.py

# Список ID администраторов
ADMIN_IDS = {"1809630966", "7053559428"}

# Создаём роутер для магазина
router = Router()

# Опции для покупки алмазов
DIAMONDS_OPTIONS = [
    {"id": "1", "amount": 100, "price_rub": 100, "price_ton": 0.99},
    {"id": "2", "amount": 250, "price_rub": 240, "price_ton": 2.39},
    {"id": "3", "amount": 500, "price_rub": 450, "price_ton": 4.49},
]

# Опции для активации номера
ACTIVATION_OPTIONS = [
    {"id": "1", "amount": 1, "price_rub": 100, "price_ton": 0.99},
    {"id": "2", "amount": 3, "price_rub": 250, "price_ton": 2.45},
    {"id": "3", "amount": 5, "price_rub": 400, "price_ton": 3.99},
]

########################################################################
# 1. Команда /store – выбор способа оплаты
########################################################################
@router.message(Command("store"))
async def store_command(message: Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Оплата руб", callback_data="store:payment:rub")],
        [InlineKeyboardButton(text="Оплата TON/Cryptobot", callback_data="store:payment:ton")]
    ])
    await message.answer("Выберите способ оплаты:", reply_markup=keyboard)

########################################################################
# 2. Выбор способа оплаты – вывод кнопок для выбора товара
########################################################################
@router.callback_query(Text(startswith="store:payment:"))
async def payment_method_callback(callback: CallbackQuery):
    # callback.data имеет вид: "store:payment:<method>"
    parts = callback.data.split(":")
    if len(parts) < 3:
        return
    method = parts[2]
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Купить алмазы", callback_data=f"store:product:diamonds:{method}")],
        [InlineKeyboardButton(text="Активация номера", callback_data=f"store:product:activation:{method}")]
    ])
    await callback.message.edit_text("Выберите, что хотите приобрести:", reply_markup=keyboard)
    await callback.answer()

########################################################################
# 3. Выбор товара (алмазы или активация номера) – показ опций
########################################################################
@router.callback_query(Text(startswith="store:product:"))
async def product_selection_callback(callback: CallbackQuery):
    # callback.data имеет вид: "store:product:<product_type>:<method>"
    parts = callback.data.split(":")
    if len(parts) < 4:
        return
    product_type = parts[2]
    method = parts[3]

    keyboard = InlineKeyboardMarkup()
    if product_type == "diamonds":
        for opt in DIAMONDS_OPTIONS:
            if method == "rub":
                button_text = f"{opt['amount']} алмазов - {opt['price_rub']}₽"
            else:
                button_text = f"{opt['amount']} алмазов - {opt['price_ton']} TON"
            keyboard.add(InlineKeyboardButton(
                text=button_text,
                callback_data=f"store:buy:diamonds:{opt['id']}:{method}"
            ))
    elif product_type == "activation":
        for opt in ACTIVATION_OPTIONS:
            if method == "rub":
                button_text = f"{opt['amount']} активация - {opt['price_rub']}₽"
            else:
                button_text = f"{opt['amount']} активация - {opt['price_ton']} TON"
            keyboard.add(InlineKeyboardButton(
                text=button_text,
                callback_data=f"store:buy:activation:{opt['id']}:{method}"
            ))
    else:
        await callback.answer("Неверный тип продукта.", show_alert=True)
        return

    await callback.message.edit_text("Выберите опцию:", reply_markup=keyboard)
    await callback.answer()

########################################################################
# 4. Выбор конкретной опции – вывод данных для оплаты и инструкции
########################################################################
@router.callback_query(Text(startswith="store:buy:"))
async def buy_option_callback(callback: CallbackQuery):
    # callback.data имеет вид: "store:buy:<product_type>:<option_id>:<method>"
    parts = callback.data.split(":")
    if len(parts) < 5:
        return
    product_type = parts[2]
    option_id = parts[3]
    method = parts[4]

    if product_type == "diamonds":
        options = DIAMONDS_OPTIONS
    elif product_type == "activation":
        options = ACTIVATION_OPTIONS
    else:
        await callback.answer("Неверный тип продукта.", show_alert=True)
        return

    option = next((opt for opt in options if opt["id"] == option_id), None)
    if not option:
        await callback.answer("Опция не найдена.", show_alert=True)
        return

    # Определяем цену и реквизиты в зависимости от способа оплаты
    if method == "rub":
        price = option["price_rub"]
        currency = "₽"
        payment_details = "Карта ЮMoney: 2204120118196936"
    else:
        price = option["price_ton"]
        currency = "TON"
        payment_details = ("TON: UQB-qPuyNz9Ib75AHe43Jz39HBlThp9Bnvcetb06OfCnhsi2\n"
                           "Cryptobot: t.me/send?start=IVnVvwBFGe5t")

    if product_type == "diamonds":
        product_name = "покупку алмазов"
        amount = option["amount"]
    else:
        product_name = "активацию номера"
        amount = option["amount"]

    confirmation_text = (
        f"Вы выбрали {product_name}:\n"
        f"Количество: {amount}\n"
        f"Сумма к оплате: {price} {currency}\n\n"
        f"Реквизиты для оплаты:\n{payment_details}\n\n"
        "После оплаты отправьте скриншот оплаты командой /sendpayment "
        f"(например, `/sendpayment {product_type} {amount}`), прикрепив изображение скриншота."
    )

    await callback.message.edit_text(confirmation_text)
    await callback.answer()

########################################################################
# 5. Обработка команды /sendpayment – получение скриншота оплаты от пользователя
########################################################################
@router.message(Command("sendpayment"))
async def send_payment_handler(message: Message):
    args = message.get_args().split()
    if len(args) < 2:
        await message.reply("Использование: /sendpayment <тип: diamonds/activation> <количество>")
        return
    product_type = args[0]
    quantity = args[1]

    if not message.photo:
        await message.reply("Пожалуйста, прикрепите скриншот оплаты.")
        return

    photo = message.photo[-1]

    await message.reply("Данные отправлены администрации на рассмотрение, ожидайте ответа от администратора.")

    admin_text = (
        f"Новый платёж!\n"
        f"Пользователь: {message.from_user.full_name} (ID: {message.from_user.id})\n"
        f"Продукт: {product_type}\n"
        f"Количество: {quantity}"
    )
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_photo(chat_id=int(admin_id), photo=photo.file_id, caption=admin_text)
        except Exception as e:
            logging.error(f"Ошибка отправки уведомления админу {admin_id}: {e}")

########################################################################
# 6. Команда для администратора для отправки сообщения пользователю
########################################################################
@router.message(Command("adminmsg"))
async def admin_message_handler(message: Message):
    if str(message.from_user.id) not in ADMIN_IDS:
        await message.reply("У вас нет доступа для выполнения этой команды.")
        return

    args = message.get_args().split(maxsplit=1)
    if len(args) < 2:
        await message.reply("Использование: /adminmsg <user_id> <сообщение>")
        return

    target_user_id = args[0]
    admin_message = args[1]

    try:
        await bot.send_message(chat_id=int(target_user_id), text=admin_message)
        await message.reply("Сообщение отправлено пользователю.")
    except Exception as e:
        await message.reply(f"Ошибка при отправке сообщения: {e}")
