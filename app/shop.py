from aiogram import types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, LabeledPrice, PreCheckoutQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
import asyncio

from common import bot, dp, load_data, save_data

# Список ID администраторов
ADMIN_IDS = {"1809630966", "7053559428"}

# Реквизиты для оплаты (для ручных переводов)
PAYMENT_DETAILS = {
    "rub": "2204120118196936",
    "ton": "UQB-qPuyNz9Ib75AHe43Jz39HBlThp9Bnvcetb06OfCnhsi2"
}

# Словарь для хранения ожидающих оплат пользователей (для RUB и TON).
pending_shop_payments = {}

# --- Обработчик команды /shop ---
@dp.message(Command("shop"))
async def shop_command(message: types.Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💸 Оплата RUB", callback_data="shop_method:rub")],
        [InlineKeyboardButton(text="💱 Оплата TON", callback_data="shop_method:ton")],
        [InlineKeyboardButton(text="⭐️ Оплата Stars", callback_data="shop_method:stars")]
    ])
    await message.answer("💰 <b>Выберите способ оплаты:</b>", parse_mode="HTML", reply_markup=keyboard)

# --- Выбор способа оплаты (callback) ---
@dp.callback_query(lambda c: c.data and c.data.startswith("shop_method:"))
async def shop_method_callback(callback_query: types.CallbackQuery):
    method = callback_query.data.split(":")[1]
    if method == "rub":
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💎 50 алмазов — 100₽", callback_data="shop_option:50:100:rub")],
            [InlineKeyboardButton(text="💎 100 алмазов — 190₽", callback_data="shop_option:100:190:rub")],
            [InlineKeyboardButton(text="💎 250 алмазов — 450₽", callback_data="shop_option:250:450:rub")]
        ])
        await callback_query.message.edit_text(
            "💎 <b>Выберите количество алмазов для оплаты рублями:</b>",
            parse_mode="HTML", reply_markup=keyboard
        )
    elif method == "ton":
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💎 50 алмазов — 0.2 TON", callback_data="shop_option:50:0.2:ton")],
            [InlineKeyboardButton(text="💎 100 алмазов — 0.55 TON", callback_data="shop_option:100:0.55:ton")],
            [InlineKeyboardButton(text="💎 250 алмазов — 1.25 TON", callback_data="shop_option:250:1.25:ton")]
        ])
        await callback_query.message.edit_text(
            "💎 <b>Выберите количество алмазов для оплаты в TON:</b>",
            parse_mode="HTML", reply_markup=keyboard
        )
    elif method == "stars":
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💎 50 алмазов — 50 ⭐️", callback_data="shop_option:50:50:stars")],
            [InlineKeyboardButton(text="💎 100 алмазов — 100 ⭐️", callback_data="shop_option:100:100:stars")],
            [InlineKeyboardButton(text="💎 250 алмазов — 250 ⭐️", callback_data="shop_option:250:250:stars")]
        ])
        await callback_query.message.edit_text(
            "💎 <b>Выберите количество алмазов для оплаты звездами:</b>",
            parse_mode="HTML", reply_markup=keyboard
        )
    await callback_query.answer()

# --- Выбор товара (callback) ---
@dp.callback_query(lambda c: c.data and c.data.startswith("shop_option:"))
async def shop_option_callback(callback_query: types.CallbackQuery):
    # Формат callback_data: shop_option:<diamond_count>:<price>:<method>
    parts = callback_query.data.split(":")
    if len(parts) < 4:
        await callback_query.answer("❗ <b>Ошибка данных.</b>", show_alert=True, parse_mode="HTML")
        return
    diamond_count = int(parts[1])
    price = parts[2]
    method = parts[3]
    
    if method == "stars":
        # Оплата через Telegram Stars – сразу отправляем инвойс
        prices = [LabeledPrice(label="XTR", amount=int(price))]
        payload = f"shop_stars:{diamond_count}"
        # Создаём клавиатуру с кнопкой оплаты
        builder = InlineKeyboardBuilder()
        builder.button(text=f"Оплатить {price} ⭐️", pay=True)
        invoice_keyboard = builder.as_markup()
        await callback_query.message.answer_invoice(
            title="Покупка алмазов",
            description=f"Вы получите {diamond_count} алмазов после успешной оплаты звездами.",
            prices=prices,
            provider_token="",  # Для Telegram Stars оставляем пустую строку
            payload=payload,
            currency="XTR",
            reply_markup=invoice_keyboard
        )
        await callback_query.answer()
    else:
        # Для RUB и TON – сохраняем заявку и просим отправить скриншот оплаты
        user_id = str(callback_query.from_user.id)
        pending_shop_payments[user_id] = {
            "diamond_count": diamond_count,
            "price": price,
            "payment_method": method,
            "processed": False,
            "processed_by": None,
            "action": None
        }
        payment_info = PAYMENT_DETAILS.get(method, "")
        text = (
            f"🎁 <b>Вы выбрали {diamond_count} алмазов</b> за <code>{price}</code> "
            f"{'₽' if method=='rub' else 'TON'}.\n"
            f"💳 Реквизиты для оплаты: <code>{payment_info}</code>\n\n"
            "📸 После оплаты отправьте, пожалуйста, скриншот оплаты."
        )
        await callback_query.message.edit_text(text, parse_mode="HTML")
        await callback_query.answer()

# --- Обработчик получения скриншота оплаты (для RUB и TON) ---
@dp.message(lambda message: message.photo and str(message.from_user.id) in pending_shop_payments)
async def shop_payment_screenshot(message: types.Message):
    user_id = str(message.from_user.id)
    payment_info = pending_shop_payments.get(user_id)
    if not payment_info:
        return  # Заявка не найдена
    
    diamond_count = payment_info["diamond_count"]
    price = payment_info["price"]
    method = payment_info["payment_method"]
    
    admin_text = (
        f"📢 <b>Новый донат от пользователя {user_id}</b>!\n"
        f"💎 Количество алмазов: <b>{diamond_count}</b>\n"
        f"💳 Метод оплаты: <b>{method.upper()}</b>\n"
        f"💰 Сумма: <code>{price}</code> {'₽' if method=='rub' else 'TON'}\n\n"
        "Нажмите кнопку ниже, чтобы <b>подтвердить</b> или <b>отклонить</b> донат."
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Подтвердить Донат", callback_data=f"confirm_donation:{user_id}:{diamond_count}"),
            InlineKeyboardButton(text="❌ Отклонить Донат", callback_data=f"reject_donation:{user_id}")
        ]
    ])
    
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_photo(
                chat_id=int(admin_id),
                photo=message.photo[-1].file_id,
                caption=admin_text,
                parse_mode="HTML",
                reply_markup=keyboard
            )
        except Exception as e:
            print(f"Ошибка отправки админу {admin_id}: {e}")
    
    await message.answer("✅ Скриншот отправлен администрации на проверку. Ожидайте ответа.", parse_mode="HTML")

# --- Обработчик pre_checkout для оплаты звездами ---
@dp.pre_checkout_query(lambda query: query.invoice_payload.startswith("shop_stars:"))
async def pre_checkout_handler(pre_checkout_query: PreCheckoutQuery):
    # Подтверждаем предчек-аут
    await pre_checkout_query.answer(ok=True)

# --- Обработчик успешного платежа через Stars ---
@dp.message(lambda message: message.successful_payment and message.successful_payment.invoice_payload.startswith("shop_stars:"))
async def stars_success_payment_handler(message: types.Message):
    payload = message.successful_payment.invoice_payload
    try:
        _, diamond_count_str = payload.split(":")
        diamond_count = int(diamond_count_str)
    except Exception:
        await message.answer("Ошибка обработки платежа.")
        return

    # Распаковываем реальную сумму, которую заплатил пользователь
    price = message.successful_payment.total_amount

    user_id = str(message.from_user.id)
    data = load_data()
    user = data.get("users", {}).get(user_id)
    if user is None:
        await message.answer("Пользователь не найден.")
        return

    # Начисляем алмазы
    user["balance"] = user.get("balance", 0) + diamond_count
    save_data(data)

    # Уведомляем администраторов
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                chat_id=int(admin_id),
                text=(
                    f"🛒 Покупка звёздами:\n"
                    f"Пользователь: <b>{message.from_user.username or user_id}</b> (ID: <code>{user_id}</code>)\n"
                    f"Получил: <b>{diamond_count} 💎</b>\n"
                    f"Заплатил: <b>{price} ⭐️</b>"
                ),
                parse_mode="HTML"
            )
        except Exception:
            pass

    # Сообщаем самому пользователю
    await message.answer(
        f"✅ Оплата прошла успешно! На ваш баланс зачислено <code>{diamond_count}</code> алмазов.",
        parse_mode="HTML"
    )

# --- Подтверждение доната администратором (для RUB и TON) ---
@dp.callback_query(lambda c: c.data and c.data.startswith("confirm_donation:"))
async def confirm_donation_callback(callback_query: types.CallbackQuery):
    # Формат callback_data: confirm_donation:<user_id>:<diamond_count>
    parts = callback_query.data.split(":")
    if len(parts) < 3:
        await callback_query.answer("❗ Ошибка данных.", show_alert=True, parse_mode="HTML")
        return
    target_user_id = parts[1]
    diamond_count = int(parts[2])
    
    donation = pending_shop_payments.get(target_user_id)
    if not donation:
        await callback_query.answer("❗ Донат не найден или уже обработан.", show_alert=True, parse_mode="HTML")
        return
    
    if donation["processed"]:
        await callback_query.answer(
            f"❗ Донат уже обработан администратором {donation['processed_by']} ({donation['action']}).",
            show_alert=True, parse_mode="HTML"
        )
        return
    
    donation["processed"] = True
    donation["processed_by"] = callback_query.from_user.id
    donation["action"] = "подтвержден"
    
    data = load_data()
    user = data.get("users", {}).get(target_user_id)
    if user is None:
        await callback_query.answer("❗ Пользователь не найден.", show_alert=True, parse_mode="HTML")
        return
    user["balance"] = user.get("balance", 0) + diamond_count
    save_data(data)
    
    try:
        await bot.send_message(
            chat_id=int(target_user_id),
            text=f"✅ Оплата прошла успешно! На ваш баланс зачислено <code>{diamond_count}</code> алмазов.",
            parse_mode="HTML"
        )
    except Exception as e:
        print(f"Ошибка уведомления пользователя {target_user_id}: {e}")
    
    await callback_query.message.edit_caption(
        caption=f"✅ Донат подтвержден администратором <b>{callback_query.from_user.id}</b>. "
                f"<b>{diamond_count}</b> алмазов отправлены пользователю <b>{target_user_id}</b>.",
        parse_mode="HTML"
    )
    await callback_query.answer("✅ Донат подтвержден.", parse_mode="HTML")
    
    pending_shop_payments.pop(target_user_id, None)

# --- Отклонение доната администратором (для RUB и TON) ---
@dp.callback_query(lambda c: c.data and c.data.startswith("reject_donation:"))
async def reject_donation_callback(callback_query: types.CallbackQuery):
    # Формат callback_data: reject_donation:<user_id>
    parts = callback_query.data.split(":")
    if len(parts) < 2:
        await callback_query.answer("❗ Ошибка данных.", show_alert=True, parse_mode="HTML")
        return
    target_user_id = parts[1]
    
    donation = pending_shop_payments.get(target_user_id)
    if not donation:
        await callback_query.answer("❗ Донат не найден или уже обработан.", show_alert=True, parse_mode="HTML")
        return
    
    if donation["processed"]:
        await callback_query.answer(
            f"❗ Донат уже обработан администратором {donation['processed_by']} ({donation['action']}).",
            show_alert=True, parse_mode="HTML"
        )
        return
    
    donation["processed"] = True
    donation["processed_by"] = callback_query.from_user.id
    donation["action"] = "отклонен"
    
    try:
        await bot.send_message(
            chat_id=int(target_user_id),
            text="❌ Ваш донат был отклонен администрацией.",
            parse_mode="HTML"
        )
    except Exception as e:
        print(f"Ошибка уведомления пользователя {target_user_id}: {e}")
    
    await callback_query.message.edit_caption(
        caption=f"❌ Донат отклонен администратором <b>{callback_query.from_user.id}</b> для пользователя <b>{target_user_id}</b>.",
        parse_mode="HTML"
    )
    await callback_query.answer("❌ Донат отклонен.", parse_mode="HTML")
    
    pending_shop_payments.pop(target_user_id, None)
