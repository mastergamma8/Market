from aiogram import Dispatcher, types
from aiogram.filters import Command
from auction import auction_instance  # Глобальный экземпляр аукциона
# from common import ADMIN_IDS  # Проверка администратора больше не нужна

dp: Dispatcher  # Предполагается, что диспетчер уже инициализирован

@dp.message(Command("startauction"))
async def bot_start_auction(message: types.Message):
    # Ограничение для администратора удалено – теперь каждый пользователь может запустить аукцион.
    # (При необходимости можно добавить проверку, что токен принадлежит пользователю.)
    parts = message.text.split()
    if len(parts) < 3:
        await message.answer("❗ Формат: /startauction <номер токена> <длительность в секундах>")
        return

    token = parts[1]
    try:
        duration = int(parts[2])
    except ValueError:
        await message.answer("❗ Длительность аукциона должна быть числом (секунды).")
        return

    try:
        await auction_instance.start_auction(token, duration)
        await message.answer(f"🚀 Аукцион для токена {token} запущен на {duration} секунд.")
    except Exception as e:
        await message.answer(f"❗ Ошибка запуска аукциона: {e}")

@dp.message(Command("bid"))
async def bot_place_bid(message: types.Message):
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("❗ Формат: /bid <ставка>")
        return

    try:
        bid_amount = int(parts[1])
    except ValueError:
        await message.answer("❗ Ставка должна быть числом.")
        return

    try:
        # Передаем ID и имя пользователя (full_name)
        success = await auction_instance.place_bid(str(message.from_user.id), message.from_user.full_name, bid_amount)
        if success:
            await message.answer(
                f"✅ Ваша ставка {bid_amount} принята.\n"
                f"Текущая максимальная ставка: {auction_instance.highest_bid} от {auction_instance.highest_bidder_name}"
            )
        else:
            await message.answer(
                f"❗ Ваша ставка должна быть больше текущей максимальной: {auction_instance.highest_bid}"
            )
    except Exception as e:
        await message.answer(f"❗ Ошибка при размещении ставки: {e}")

@dp.message(Command("auctionstatus"))
async def bot_auction_status(message: types.Message):
    if auction_instance.active:
        time_remaining = auction_instance.get_time_remaining()
        await message.answer(
            f"📢 Аукцион активен для токена {auction_instance.token}.\n"
            f"Текущая максимальная ставка: {auction_instance.highest_bid} от {auction_instance.highest_bidder_name}\n"
            f"Осталось времени: {time_remaining} секунд"
        )
    else:
        await message.answer("ℹ️ В данный момент аукцион не проводится.")
