import asyncio
import datetime
import hashlib
from urllib.parse import quote_plus

from aiogram import Dispatcher
from aiogram.types import Message
from aiogram.filters import Command

from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse

# Импорт общих функций и объектов
from common import load_data, save_data, ensure_user, templates, bot, dp

router = APIRouter()

ADMIN_ID = "1809630966"

#############################
# Телеграм-обработчики аукционов
#############################

@dp.message(Command("auction"))
async def create_auction(message: Message) -> None:
    parts = message.text.split()
    if len(parts) != 4:
        await message.answer("❗ Формат: /auction <номер токена> <начальная цена> <длительность (мин)>")
        return
    try:
        idx = int(parts[1]) - 1
        start_price = int(parts[2])
        duration = int(parts[3])
    except ValueError:
        await message.answer("❗ Проверьте, что номер токена, цена и длительность — числа.")
        return

    data = load_data()
    user = ensure_user(data, str(message.from_user.id))
    tokens = user.get("tokens", [])
    if idx < 0 or idx >= len(tokens):
        await message.answer("❗ Неверный номер токена.")
        return

    token = tokens.pop(idx)
    # Если токен профильно установлен — убрать
    if user.get("custom_number", {}).get("token") == token["token"]:
        del user["custom_number"]

    auction_id = hashlib.sha256(f"{message.from_user.id}{token['token']}{datetime.datetime.now()}".encode()).hexdigest()[:8]
    end_ts = (datetime.datetime.now() + datetime.timedelta(minutes=duration)).timestamp()

    auction = {
        "auction_id": auction_id,
        "seller_id": str(message.from_user.id),
        "token": token,
        "starting_price": start_price,
        "current_bid": start_price,
        "highest_bidder": None,
        "end_time": end_ts
    }
    data.setdefault("auctions", []).append(auction)
    save_data(data)

    await message.answer(
        f"🚀 Аукцион создан!\n"
        f"ID: {auction_id}\n"
        f"NFT №{token['token']} стартует с {start_price} 💎\n"
        f"Завершение: {datetime.datetime.fromtimestamp(end_ts):%Y-%m-%d %H:%M:%S}"
    )


@dp.message(Command("bid"))
async def bid_on_auction(message: Message) -> None:
    parts = message.text.split()
    if len(parts) != 3:
        await message.answer("❗ Формат: /bid <auction_id> <ставка>")
        return
    aid, amt = parts[1], parts[2]
    try:
        bid_amount = int(amt)
    except ValueError:
        await message.answer("❗ Ставка должна быть числом.")
        return

    data = load_data()
    auction = next((a for a in data.get("auctions", []) if a["auction_id"] == aid), None)
    if not auction:
        await message.answer("❗ Аукцион не найден.")
        return

    now = datetime.datetime.now().timestamp()
    if now > auction["end_time"]:
        await message.answer("❗ Аукцион завершён.")
        return
    if bid_amount <= auction["current_bid"]:
        await message.answer("❗ Ставка должна быть выше текущей.")
        return

    user = ensure_user(data, str(message.from_user.id))
    if user.get("balance", 0) < bid_amount:
        await message.answer("❗ Недостаточно средств.")
        return

    prev_id = auction.get("highest_bidder")
    prev_bid = auction["current_bid"]

    if prev_id == str(message.from_user.id):
        # повышение собственной ставки
        delta = bid_amount - prev_bid
        if delta <= 0 or user["balance"] < delta:
            await message.answer("❗ Ставка должна быть выше текущей.")
            return
        user["balance"] -= delta
    else:
        # вернуть средства предыдущему и уведомить
        if prev_id:
            prev = ensure_user(data, prev_id)
            prev["balance"] += prev_bid
            try:
                await bot.send_message(
                    int(prev_id),
                    f"⚠️ Ваша ставка {prev_bid} 💎 на NFT №{auction['token']['token']} была перебита в аукционе {aid}. Сумма возвращена."
                )
            except Exception:
                pass
        user["balance"] -= bid_amount
        auction["highest_bidder"] = str(message.from_user.id)

    auction["current_bid"] = bid_amount
    save_data(data)
    await message.answer(f"✅ Ваша ставка {bid_amount} 💎 принята в аукционе {aid}.")


@dp.message(Command("finish"))
async def finish_auction_bot(message: Message) -> None:
    parts = message.text.split()
    if len(parts) != 2:
        await message.answer("❗ Формат: /finish <auction_id>")
        return
    aid = parts[1]

    data = load_data()
    auction = next((a for a in data.get("auctions", []) if a["auction_id"] == aid), None)
    if not auction:
        await message.answer("❗ Аукцион не найден.")
        return
    if auction["seller_id"] != str(message.from_user.id):
        await message.answer("❗ Только создатель аукциона может завершить его.")
        return

    prev_id = auction.get("highest_bidder")
    prev_bid = auction["current_bid"]
    token = auction["token"]

    # вернуть ставку последнему участнику и уведомить
    if prev_id:
        prev = ensure_user(data, prev_id)
        prev["balance"] += prev_bid
        try:
            await bot.send_message(
                int(prev_id),
                f"⚠️ Аукцион {aid} отменён продавцом. Ваша ставка {prev_bid} 💎 возвращена."
            )
        except Exception:
            pass

    # вернуть NFT продавцу
    seller = ensure_user(data, auction["seller_id"])
    seller.setdefault("tokens", []).append(token)

    data["auctions"].remove(auction)
    save_data(data)

    await message.answer(f"🛑 Аукцион {aid} отменён. NFT №{token['token']} возвращён, ставка выкупщика возвращена.")


##########################################
# Фоновая задача завершения аукционов
##########################################

async def check_auctions():
    while True:
        data = load_data()
        now = datetime.datetime.now().timestamp()
        to_close = [a for a in data.get("auctions", []) if now > a["end_time"]]
        for auction in to_close:
            seller = ensure_user(data, auction["seller_id"])
            winner = auction.get("highest_bidder")
            price = auction["current_bid"]
            token = auction["token"]

            if winner:
                buyer = ensure_user(data, winner)
                admin_cut = price * 5 // 100
                seller_cut = price - admin_cut
                seller["balance"] += seller_cut
                ensure_user(data, ADMIN_ID)["balance"] += admin_cut

                token.update({
                    "bought_price": price,
                    "bought_date": datetime.datetime.now().isoformat(),
                    "bought_source": "auction"
                })
                buyer.setdefault("tokens", []).append(token)

                try:
                    await bot.send_message(
                        int(winner),
                        f"🎉 Вы выиграли аукцион {auction['auction_id']} за {price} 💎. NFT №{token['token']} зачислен в коллекцию."
                    )
                except Exception:
                    pass
            else:
                seller.setdefault("tokens", []).append(token)
                try:
                    await bot.send_message(
                        int(auction["seller_id"]),
                        f"Ваш аукцион {auction['auction_id']} завершился без ставок. NFT №{token['token']} возвращён."
                    )
                except Exception:
                    pass

            data["auctions"].remove(auction)
        save_data(data)
        await asyncio.sleep(30)


def register_auction_tasks(loop):
    loop.create_task(check_auctions())


##########################################
# Веб-эндпоинты аукционов (FastAPI)
##########################################

@router.get("/auctions")
async def auctions_page(request: Request):
    data = load_data()
    return templates.TemplateResponse("auctions.html", {
        "request": request,
        "auctions": data.get("auctions", []),
        "users": data.get("users", {}),
        "buyer_id": request.cookies.get("user_id"),
        "info": request.query_params.get("info"),
        "error": request.query_params.get("error"),
    })


@router.post("/bid_web")
async def bid_web(request: Request, auction_id: str = Form(...), bid_amount: int = Form(...)):
    buyer_id = request.cookies.get("user_id")
    if not buyer_id:
        return RedirectResponse(f"/auctions?error={quote_plus('Войдите в систему')}", 303)

    data = load_data()
    auction = next((a for a in data.get("auctions", []) if a["auction_id"] == auction_id), None)
    if not auction:
        return RedirectResponse(f"/auctions?error={quote_plus('Аукцион не найден')}", 303)

    now = datetime.datetime.now().timestamp()
    if now > auction["end_time"]:
        return RedirectResponse(f"/auctions?error={quote_plus('Аукцион завершён')}", 303)
    if bid_amount <= auction["current_bid"]:
        return RedirectResponse(f"/auctions?error={quote_plus('Ставка должна быть выше')}", 303)

    user = ensure_user(data, buyer_id)
    if user.get("balance", 0) < bid_amount:
        return RedirectResponse(f"/auctions?error={quote_plus('Недостаточно средств')}", 303)

    prev_id = auction.get("highest_bidder")
    prev_bid = auction["current_bid"]

    # вернуть и уведомить предыдущего
    if prev_id and prev_id != buyer_id:
        prev = ensure_user(data, prev_id)
        prev["balance"] += prev_bid
        try:
            await bot.send_message(
                int(prev_id),
                f"⚠️ Ставка {prev_bid} 💎 на NFT №{auction['token']['token']} перебита в веб-версии аукциона {auction_id}. Сумма возвращена."
            )
        except Exception:
            pass

    if prev_id != buyer_id:
        user["balance"] -= bid_amount
        auction["highest_bidder"] = buyer_id
    else:
        delta = bid_amount - prev_bid
        user["balance"] -= delta

    auction["current_bid"] = bid_amount
    save_data(data)
    return RedirectResponse(f"/auctions?info={quote_plus('Ставка принята')}", 303)


@router.post("/auction_create")
async def create_auction_web(request: Request,
                             token_index: int = Form(...),
                             starting_price: int = Form(...),
                             duration_minutes: int = Form(...)):
    user_id = request.cookies.get("user_id")
    if not user_id:
        return RedirectResponse(f"/auctions?error={quote_plus('Войдите в систему')}", 303)
    try:
        idx = int(token_index) - 1
        start_price = int(starting_price)
        duration = int(duration_minutes)
    except ValueError:
        return RedirectResponse(f"/auctions?error={quote_plus('Проверьте корректность полей')}", 303)

    data = load_data()
    user = ensure_user(data, user_id)
    tokens = user.get("tokens", [])
    if idx < 0 or idx >= len(tokens):
        return RedirectResponse(f"/auctions?error={quote_plus('Неверный номер токена')}", 303)

    token = tokens.pop(idx)
    if user.get("custom_number", {}).get("token") == token["token"]:
        del user["custom_number"]

    auction_id = hashlib.sha256(f"{user_id}{token['token']}{datetime.datetime.now()}".encode()).hexdigest()[:8]
    end_ts = (datetime.datetime.now() + datetime.timedelta(minutes=duration)).timestamp()

    auction = {
        "auction_id": auction_id,
        "seller_id": user_id,
        "token": token,
        "starting_price": start_price,
        "current_bid": start_price,
        "highest_bidder": None,
        "end_time": end_ts
    }
    data.setdefault("auctions", []).append(auction)
    save_data(data)
    return RedirectResponse(f"/auctions?info={quote_plus('Аукцион создан')}", 303)


@router.post("/finish_auction")
async def finish_auction_web(request: Request, auction_id: str = Form(...)):
    user_id = request.cookies.get("user_id")
    if not user_id:
        return RedirectResponse(f"/auctions?error={quote_plus('Войдите в систему')}", 303)

    data = load_data()
    auction = next((a for a in data.get("auctions", []) if a["auction_id"] == auction_id), None)
    if not auction or auction["seller_id"] != user_id:
        return RedirectResponse(f"/auctions?error={quote_plus('Нет доступа или аукцион не найден')}", 303)

    prev_id = auction.get("highest_bidder")
    prev_bid = auction["current_bid"]
    token = auction["token"]

    if prev_id:
        prev = ensure_user(data, prev_id)
        prev["balance"] += prev_bid
        try:
            await bot.send_message(
                int(prev_id),
                f"⚠️ Аукцион {auction_id} отменён продавцом (веб). Ваша ставка {prev_bid} 💎 возвращена."
            )
        except Exception:
            pass

    seller = ensure_user(data, auction["seller_id"])
    seller.setdefault("tokens", []).append(token)

    data["auctions"].remove(auction)
    save_data(data)
    return RedirectResponse(f"/auctions?info={quote_plus('Аукцион отменён, ставка возвращена')}", 303)
