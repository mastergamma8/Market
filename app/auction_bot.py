# Auction_bot.py
from aiogram import types
from aiogram.filters import Command
from common import dp, bot
from Auction import auction_instance

@dp.message(Command("startauction"))
async def bot_start_auction(message: types.Message) -> None:
    """
    Команда для запуска аукциона.
    Формат:
      /startauction <номер токена> <длительность> <фон> <цвет_цифр> <редкость>
    Пример:
      /startauction 1234 60 #ffffff #000000 0.1%
    """
    parts = message.text.split()
    if len(parts) < 6:
        await message.answer("❗ Формат: /startauction <номер токена> <длительность> <фон> <цвет_цифр> <редкость>")
        return

    token = parts[1]
    try:
        duration = int(parts[2])
    except ValueError:
        await message.answer("❗ Длительность должна быть числом (секунды).")
        return
    bg = parts[3]
    digit_color = parts[4]
    rarity = parts[5]
    seller_id = str(message.from_user.id)

    try:
        await auction_instance.start_auction(token, duration, seller_id, {"bg": bg, "digit_color": digit_color, "rarity": rarity})
        await message.answer(f"🚀 Аукцион для токена {token} запущен на {duration} секунд.")
    except Exception as e:
        await message.answer(f"❗ Ошибка запуска аукциона: {e}")

@dp.message(Command("bid"))
async def bot_place_bid(message: types.Message) -> None:
    """
    Команда для размещения ставки.
    Формат: /bid <ставка>
    """
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("❗ Формат: /bid <ставка>")
        return

    try:
        bid_amount = int(parts[1])
    except ValueError:
        await message.answer("❗ Ставка должна быть числом.")
        return

    bidder_id = str(message.from_user.id)
    bidder_name = message.from_user.full_name if message.from_user.full_name else "Неизвестно"

    try:
        success = await auction_instance.place_bid(bidder_id, bidder_name, bid_amount)
        if success:
            await message.answer(
                f"✅ Ваша ставка {bid_amount} принята.\n"
                f"Текущая максимальная ставка: {auction_instance.highest_bid} от {auction_instance.highest_bidder_name}"
            )
            if auction_instance.seller_id:
                await bot.send_message(
                    auction_instance.seller_id,
                    f"📢 На ваш аукцион поступила новая ставка: {bid_amount} от {bidder_name}"
                )
        else:
            await message.answer(f"❗ Ваша ставка должна быть выше текущей: {auction_instance.highest_bid}")
    except Exception as e:
        await message.answer(f"❗ Ошибка при размещении ставки: {e}")

@dp.message(Command("auctionstatus"))
async def bot_auction_status(message: types.Message) -> None:
    """
    Команда для проверки статуса аукциона.
    """
    if auction_instance.active:
        time_remaining = auction_instance.get_time_remaining()
        await message.answer(
            f"📢 Аукцион активен для токена {auction_instance.token}.\n"
            f"Текущая максимальная ставка: {auction_instance.highest_bid} от {auction_instance.highest_bidder_name}\n"
            f"Осталось времени: {time_remaining} секунд"
        )
    else:
        await message.answer("ℹ️ В данный момент аукцион не проводится.")
