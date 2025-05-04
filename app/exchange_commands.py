import datetime
import uuid
import asyncio

from aiogram import Bot, Dispatcher, types
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command

# Импорт общих функций и объектов из common.py
from common import bot, dp, load_data, save_data, ensure_user

@dp.message(Command("exchange"))
async def exchange_numbers(message: Message) -> None:
    """
    Команда для создания предложения обмена.
    Формат: /exchange <мой индекс в коллекции> <ID пользователя или его анонимный номер> <их индекс в коллекции>
    """
    parts = message.text.split()
    if len(parts) != 4:
        await message.answer("❗ Формат: /exchange <мой индекс> <ID пользователя или его анонимный номер> <их индекс>")
        return

    # парсим индексы
    try:
        my_index = int(parts[1]) - 1
        target_identifier = parts[2]
        target_index = int(parts[3]) - 1
    except ValueError:
        await message.answer("❗ Проверьте, что индексы являются числами.")
        return

    data = load_data()
    initiator = ensure_user(data, str(message.from_user.id))

    # разрешаем себе не обмениваться с самим собой
    if target_identifier == str(message.from_user.id) or \
       (initiator.get("crossed_number", {}).get("token") == target_identifier):
        await message.answer("❗ Нельзя обмениваться с самим собой!")
        return

    # сначала пытаемся найти пользователя по анонимному номеру
    target_uid = None
    for uid, u in data.get("users", {}).items():
        if u.get("crossed_number", {}).get("token") == target_identifier:
            target_uid = uid
            break
    # если не нашли — считаем, что передали Telegram-ID
    if target_uid is None:
        target_uid = target_identifier

    target = data.get("users", {}).get(target_uid)
    if not target:
        await message.answer("❗ Пользователь не найден.")
        return

    # проверяем индексы в коллекциях
    my_tokens    = initiator.get("tokens", [])
    target_tokens = target.get("tokens", [])

    if my_index < 0 or my_index >= len(my_tokens):
        await message.answer("❗ Неверный индекс вашего номера.")
        return
    if target_index < 0 or target_index >= len(target_tokens):
        await message.answer("❗ Неверный индекс номера пользователя.")
        return

    # извлекаем и блокируем токены
    my_token     = my_tokens.pop(my_index)
    target_token = target_tokens.pop(target_index)

    # если они были профильными — сбрасываем
    if initiator.get("custom_number", {}).get("token") == my_token["token"]:
        del initiator["custom_number"]
    if target.get("custom_number", {}).get("token") == target_token["token"]:
        del target["custom_number"]

    # создаём запись об обмене
    exchange_id = str(uuid.uuid4())
    pending = {
        "exchange_id":     exchange_id,
        "initiator_id":    str(message.from_user.id),
        "target_id":       target_uid,
        "initiator_token": my_token,
        "target_token":    target_token,
        "timestamp":       datetime.datetime.now().isoformat(),
        "expires_at":      (datetime.datetime.now() + datetime.timedelta(hours=24)).timestamp()
    }
    data.setdefault("pending_exchanges", []).append(pending)
    save_data(data)

    # Формируем inline-клавиатуру для подтверждения/отказа обмена (для целевого пользователя)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Принять", callback_data=f"accept_exchange:{exchange_id}")],
        [InlineKeyboardButton(text="❌ Отклонить", callback_data=f"decline_exchange:{exchange_id}")]
    ])

    try:
        # Отправляем сообщение целевому пользователю
        await bot.send_message(
            int(target_uid),
            f"🔄 Пользователь {initiator.get('username', 'Неизвестный')} предлагает обмен:\n"
            f"Ваш номер: {target_token['token']}\n"
            f"на его номер: {my_token['token']}\n\n"
            "Нажмите «Принять» для подтверждения или «Отклонить» для отказа.\n\n"
            "Для отмены обмена введите /cancel_exchange <ID обмена>.",
            reply_markup=keyboard
        )
    except Exception as e:
        # Если отправка не удалась, возвращаем токены обратно
        my_tokens.append(my_token)
        target_tokens.append(target_token)
        data["pending_exchanges"].remove(pending_exchange)
        save_data(data)
        await message.answer("❗ Не удалось отправить предложение обмена. Попробуйте позже.")
        return

    # Для инициатора добавляем отдельное сообщение с inline-кнопкой для отмены обмена
    initiator_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚫 Отменить обмен", callback_data=f"cancel_exchange_initiator:{exchange_id}")]
    ])
    await message.answer(
        f"✅ Предложение обмена отправлено. ID обмена: {exchange_id}\nОжидайте ответа партнёра.",
        reply_markup=initiator_keyboard
    )

@dp.callback_query(lambda c: c.data and c.data.startswith("accept_exchange:"))
async def process_accept_exchange(callback: CallbackQuery):
    """
    Обработка callback'а подтверждения обмена.
    """
    exchange_id = callback.data.split(":", 1)[1]
    data = load_data()
    pending_exchanges = data.get("pending_exchanges", [])
    pending = next((ex for ex in pending_exchanges if ex["exchange_id"] == exchange_id), None)
    if not pending:
        await callback.answer("❗ Предложение обмена не найдено или уже обработано.")
        return
    if str(callback.from_user.id) != pending["target_id"]:
        await callback.answer("❗ Это не ваше предложение обмена.")
        return
    now_ts = datetime.datetime.now().timestamp()
    if now_ts > pending.get("expires_at", 0):
        await callback.answer("❗ Срок предложения истёк.")
        return

    initiator = ensure_user(data, pending["initiator_id"])
    target = ensure_user(data, pending["target_id"])
    # Завершаем обмен: инициатор получает токен цели, а цель – токен инициатора
    initiator.setdefault("tokens", []).append(pending["target_token"])
    target.setdefault("tokens", []).append(pending["initiator_token"])
    data["pending_exchanges"].remove(pending)
    save_data(data)

    await callback.answer("✅ Обмен подтверждён!")
    try:
        await bot.send_message(
            int(pending["initiator_id"]),
            f"🎉 Пользователь {target.get('username', 'Неизвестный')} принял ваше предложение обмена!\n"
            f"Вы получили номер: {pending['target_token']['token']}"
        )
    except Exception as e:
        print("Ошибка уведомления инициатора:", e)
    await callback.message.edit_text("✅ Обмен подтверждён.")

@dp.callback_query(lambda c: c.data and c.data.startswith("decline_exchange:"))
async def process_decline_exchange(callback: CallbackQuery):
    """
    Обработка callback'а отказа обмена.
    Токены возвращаются их владельцам.
    """
    exchange_id = callback.data.split(":", 1)[1]
    data = load_data()
    pending_exchanges = data.get("pending_exchanges", [])
    pending = next((ex for ex in pending_exchanges if ex["exchange_id"] == exchange_id), None)
    if not pending:
        await callback.answer("❗ Предложение обмена не найдено или уже обработано.")
        return
    if str(callback.from_user.id) != pending["target_id"]:
        await callback.answer("❗ Это не ваше предложение обмена.")
        return

    initiator = ensure_user(data, pending["initiator_id"])
    target = ensure_user(data, pending["target_id"])
    # Возвращаем токены обратно владельцам
    initiator.setdefault("tokens", []).append(pending["initiator_token"])
    target.setdefault("tokens", []).append(pending["target_token"])
    data["pending_exchanges"].remove(pending)
    save_data(data)

    await callback.answer("❌ Обмен отклонён.")
    try:
        await bot.send_message(
            int(pending["initiator_id"]),
            f"ℹ️ Пользователь {target.get('username', 'Неизвестный')} отклонил ваше предложение обмена."
        )
    except Exception as e:
        print("Ошибка уведомления инициатора:", e)
    await callback.message.edit_text("❌ Обмен отклонён.")

@dp.callback_query(lambda c: c.data and c.data.startswith("cancel_exchange_initiator:"))
async def process_cancel_exchange_initiator(callback: CallbackQuery):
    """
    Обработка callback'а для отмены обмена инициатором.
    Только инициатор может отменить своё предложение.
    """
    exchange_id = callback.data.split(":", 1)[1]
    data = load_data()
    pending_exchanges = data.get("pending_exchanges", [])
    pending = next((ex for ex in pending_exchanges if ex["exchange_id"] == exchange_id), None)
    if not pending:
        await callback.answer("❗ Обмен не найден или уже обработан.")
        return
    if str(callback.from_user.id) != pending["initiator_id"]:
        await callback.answer("❗ Только инициатор может отменить этот обмен.")
        return

    initiator = ensure_user(data, pending["initiator_id"])
    target = ensure_user(data, pending["target_id"])
    # Возвращаем токены обратно владельцам
    initiator.setdefault("tokens", []).append(pending["initiator_token"])
    target.setdefault("tokens", []).append(pending["target_token"])
    pending_exchanges.remove(pending)
    save_data(data)

    await callback.answer("✅ Обмен отменён.")
    try:
        await bot.send_message(
            int(pending["target_id"]),
            "ℹ️ Инициатор отменил предложение обмена."
        )
    except Exception as e:
        print("Ошибка уведомления целевого пользователя об отмене обмена:", e)
    await callback.message.edit_text("✅ Обмен отменён.")

@dp.message(Command("cancel_exchange"))
async def cancel_exchange_command(message: Message) -> None:
    """
    Команда для ручной отмены обмена.
    Формат: /cancel_exchange <exchange_id>
    Может использовать инициатор или получатель обмена.
    """
    parts = message.text.split()
    if len(parts) != 2:
        await message.answer("❗ Формат: /cancel_exchange <exchange_id>")
        return
    exchange_id = parts[1]
    data = load_data()
    pending_exchanges = data.get("pending_exchanges", [])
    pending = next((ex for ex in pending_exchanges if ex["exchange_id"] == exchange_id), None)
    if not pending:
        await message.answer("❗ Обмен не найден или уже обработан.")
        return
    if str(message.from_user.id) not in [pending["initiator_id"], pending["target_id"]]:
        await message.answer("❗ Вы не участвуете в этом обмене.")
        return

    initiator = ensure_user(data, pending["initiator_id"])
    target = ensure_user(data, pending["target_id"])
    # Возвращаем токены обратно владельцам
    initiator.setdefault("tokens", []).append(pending["initiator_token"])
    target.setdefault("tokens", []).append(pending["target_token"])
    pending_exchanges.remove(pending)
    save_data(data)
    await message.answer("✅ Обмен отменён вручную.")
    # Уведомляем другую сторону
    other_party_id = pending["target_id"] if str(message.from_user.id) == pending["initiator_id"] else pending["initiator_id"]
    try:
        await bot.send_message(int(other_party_id), "ℹ️ Обмен был отменён другой стороной.")
    except Exception as e:
        print("Ошибка уведомления другой стороны:", e)

async def auto_cancel_exchanges():
    """
    Фоновая задача, которая каждые 60 секунд проверяет просроченные обмены.
    Если время истекло, обмен отменяется и токены возвращаются владельцам.
    """
    while True:
        data = load_data()
        pending_exchanges = data.get("pending_exchanges", [])
        now_ts = datetime.datetime.now().timestamp()
        changed = False
        expired_exchanges = [ex for ex in pending_exchanges if now_ts > ex.get("expires_at", 0)]
        for ex in expired_exchanges:
            initiator = ensure_user(data, ex["initiator_id"])
            target = ensure_user(data, ex["target_id"])
            initiator.setdefault("tokens", []).append(ex["initiator_token"])
            target.setdefault("tokens", []).append(ex["target_token"])
            pending_exchanges.remove(ex)
            changed = True
            try:
                await bot.send_message(
                    int(ex["initiator_id"]),
                    f"ℹ️ Ваш обмен с пользователем {target.get('username', 'Неизвестный')} истёк и был отменён."
                )
            except Exception as e:
                print("Ошибка уведомления инициатора об истечении:", e)
            try:
                await bot.send_message(
                    int(ex["target_id"]),
                    f"ℹ️ Обмен с пользователем {initiator.get('username', 'Неизвестный')} истёк и был отменён."
                )
            except Exception as e:
                print("Ошибка уведомления цели об истечении:", e)
        if changed:
            data["pending_exchanges"] = pending_exchanges
            save_data(data)
        await asyncio.sleep(60)
