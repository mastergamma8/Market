from aiogram import types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import asyncio

# Импорт объектов бота, диспетчера и функций для работы с данными
from common import bot, dp, load_data, save_data

# Определённые ID администраторов (при необходимости можно импортировать из общего модуля)
ADMIN_IDS = {"1809630966", "7053559428"}

# Реквизиты для оплаты
PAYMENT_DETAILS = {
    "rub": "Реквизиты для оплаты (руб): 2204120118196936",
    "ton": "Реквизиты для оплаты (тон): UQB-qPuyNz9Ib75AHe43Jz39HBlThp9Bnvcetb06OfCnhsi2"
}

# Словарь для хранения ожидающих оплат пользователей
pending_shop_payments = {}  # Ключ: user_id (str), значение: dict с информацией о донате

# --- Обработчик команды /shop ---
@dp.message(Command("shop"))
async def shop_command(message: types.Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Оплата руб", callback_data="shop_method:rub")],
        [InlineKeyboardButton(text="Оплата тон", callback_data="shop_method:ton")]
    ])
    await message.answer("Выберите способ оплаты:", reply_markup=keyboard)

# --- Выбор способа оплаты (callback) ---
@dp.callback_query(lambda c: c.data and c.data.startswith("shop_method:"))
async def shop_method_callback(callback_query: types.CallbackQuery):
    method = callback_query.data.split(":")[1]
    if method == "rub":
        # Варианты для рублевой оплаты
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="50 алмазов - 100₽", callback_data="shop_option:50:100:rub")],
            [InlineKeyboardButton(text="100 алмазов - 190₽", callback_data="shop_option:100:190:rub")],
            [InlineKeyboardButton(text="250 алмазов - 450₽", callback_data="shop_option:250:450:rub")]
        ])
        await callback_query.message.edit_text("Выберите количество алмазов для оплаты рублями:", reply_markup=keyboard)
    elif method == "ton":
        # Варианты для оплаты в тон
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="50 алмазов - 0.002 TON", callback_data="shop_option:50:0.002:ton")],
            [InlineKeyboardButton(text="100 алмазов - 0.0038 TON", callback_data="shop_option:100:0.0038:ton")],
            [InlineKeyboardButton(text="250 алмазов - 0.009 TON", callback_data="shop_option:250:0.009:ton")]
        ])
        await callback_query.message.edit_text("Выберите количество алмазов для оплаты в тон:", reply_markup=keyboard)
    await callback_query.answer()

# --- Выбор товара (callback) ---
@dp.callback_query(lambda c: c.data and c.data.startswith("shop_option:"))
async def shop_option_callback(callback_query: types.CallbackQuery):
    # Формат данных: shop_option:<diamond_count>:<price>:<method>
    parts = callback_query.data.split(":")
    if len(parts) < 4:
        await callback_query.answer("Ошибка данных.", show_alert=True)
        return
    diamond_count = int(parts[1])
    price = parts[2]
    method = parts[3]
    
    user_id = str(callback_query.from_user.id)
    # Сохраняем заявку пользователя
    pending_shop_payments[user_id] = {
        "diamond_count": diamond_count,
        "price": price,
        "payment_method": method,
    }
    
    payment_info = PAYMENT_DETAILS.get(method, "")
    text = (f"Вы выбрали {diamond_count} алмазов за {price} {'₽' if method=='rub' else 'TON'}.\n"
            f"{payment_info}\n\n"
            "После оплаты отправьте, пожалуйста, скриншот оплаты.")
    await callback_query.message.edit_text(text)
    await callback_query.answer()

# --- Обработчик получения скриншота оплаты ---
@dp.message(lambda message: message.photo and str(message.from_user.id) in pending_shop_payments)
async def shop_payment_screenshot(message: types.Message):
    user_id = str(message.from_user.id)
    payment_info = pending_shop_payments.get(user_id)
    if not payment_info:
        return  # Заявка не найдена
    
    diamond_count = payment_info["diamond_count"]
    price = payment_info["price"]
    method = payment_info["payment_method"]
    
    admin_text = (f"Новый донат от пользователя {user_id}.\n"
                  f"Количество алмазов: {diamond_count}\n"
                  f"Метод оплаты: {method}\n"
                  f"Сумма: {price} {'₽' if method=='rub' else 'TON'}\n\n"
                  "Нажмите кнопку ниже, чтобы подтвердить донат.")
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Подтвердить Донат", callback_data=f"confirm_donation:{user_id}:{diamond_count}")]
    ])
    
    # Отправляем скриншот и данные каждому админу
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_photo(
                chat_id=int(admin_id),
                photo=message.photo[-1].file_id,
                caption=admin_text,
                reply_markup=keyboard
            )
        except Exception as e:
            print(f"Ошибка отправки админу {admin_id}: {e}")
    
    await message.answer("Скриншот отправлен администрации на проверку. Ожидайте ответа.")

# --- Подтверждение оплаты администратором (callback) ---
@dp.callback_query(lambda c: c.data and c.data.startswith("confirm_donation:"))
async def confirm_donation_callback(callback_query: types.CallbackQuery):
    # Формат данных: confirm_donation:<user_id>:<diamond_count>
    parts = callback_query.data.split(":")
    if len(parts) < 3:
        await callback_query.answer("Ошибка данных.", show_alert=True)
        return
    target_user_id = parts[1]
    diamond_count = int(parts[2])
    
    data = load_data()
    user = data.get("users", {}).get(target_user_id)
    if user is None:
        await callback_query.answer("Пользователь не найден.", show_alert=True)
        return
    user["balance"] = user.get("balance", 0) + diamond_count
    save_data(data)
    
    try:
        await bot.send_message(chat_id=int(target_user_id), text=f"Оплата прошла успешно! На ваш баланс зачислено {diamond_count} алмазов.")
    except Exception as e:
        print(f"Ошибка уведомления пользователя {target_user_id}: {e}")
    
    await callback_query.message.edit_caption(
        caption=f"Донат подтвержден. {diamond_count} алмазов отправлены пользователю {target_user_id}."
    )
    await callback_query.answer("Донат подтвержден.")
    
    pending_shop_payments.pop(target_user_id, None)
