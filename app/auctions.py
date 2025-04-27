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
from common import load_data, save_data, ensure_user, templates, bot
from common import dp

router = APIRouter()

ADMIN_ID = "1809630966"

#############################
# Телеграм-обработчики аукционов
#############################

@dp.message(Command("auction"))
async def create_auction(message: Message) -> None:
    parts = message.text.split()
    if len(parts) != 4:
        await message.answer("❗ Формат: /auction <номер nft> <начальная цена> <длительность (мин)>")
        return
    try:
        token_index = int(parts[1]) - 1
        starting_price = int(parts[2])
        duration_minutes = int(parts[3])
    except ValueError:
        await message.answer("❗ Проверьте, что номер nft, начальная цена и длительность — числа.")
        return

    data = load_data()
    user = ensure_user(data, str(message.from_user.id))
    tokens = user.get("tokens", [])
    if token_index < 0 or token_index >= len(tokens):
        await message.answer("❗ Неверный номер nft в вашей коллекции.")
        return

    token = tokens.pop(token_index)
    if user.get("custom_number") and user["custom_number"].get("token") == token["token"]:
        del user["custom_number"]
    auction_id = hashlib.sha256(
        (str(message.from_user.id) + token["token"] + str(datetime.datetime.now())).encode()
    ).hexdigest()[:8]
    end_time = (datetime.datetime.now() + datetime.timedelta(minutes=duration_minutes)).timestamp()

    auction = {
        "auction_id": auction_id,
        "seller_id": str(message.from_user.id),
        "token": token,
        "starting_price": starting_price,
        "current_bid": starting_price,
        "highest_bidder": None,
        "end_time": end_time
    }
    data.setdefault("auctions", []).append(auction)
    save_data(data)

    await message.answer(
        f"🚀 Аукцион создан!\n"
        f"ID аукциона: {auction_id}\n"
        f"NFT №{token['token']} выставлен по стартовой цене {starting_price} 💎\n"
        f"Окончание: {datetime.datetime.fromtimestamp(end_time).strftime('%Y-%m-%d %H:%M:%S')}"
    )


@dp.message(Command("bid"))
async def bid_on_auction(message: Message) -> None:
    parts = message.text.split()
    if len(parts) != 3:
        await message.answer("❗ Формат: /bid <auction_id> <ставка>")
        return
    auction_id = parts[1]
    try:
        bid_amount = int(parts[2])
    except ValueError:
        await message.answer("❗ Ставка должна быть числом.")
        return

    data = load_data()
    auction = next((a for a in data.get("auctions", []) if a["auction_id"] == auction_id), None)
    if auction is None:
        await message.answer("❗ Аукцион не найден.")
        return

    now = datetime.datetime.now().timestamp()
    if now > auction["end_time"]:
        await message.answer("❗ Аукцион уже завершён.")
        return

    if bid_amount <= auction["current_bid"]:
        await message.answer("❗ Ваша ставка должна быть выше текущей.")
        return

    bidder = ensure_user(data, str(message.from_user.id))
    if bidder.get("balance", 0) < bid_amount:
        await message.answer("❗ Недостаточно средств для ставки.")
        return

    prev_id = auction.get("highest_bidder")
    prev_bid = auction["current_bid"]

    if prev_id == str(message.from_user.id):
        # тот же участник повышает свою ставку
        additional = bid_amount - prev_bid
        if additional <= 0 or bidder["balance"] < additional:
            await message.answer("❗ Недостаточно средств или ставка должна быть выше текущей.")
            return
        bidder["balance"] -= additional
    else:
        # возвращаем предыдущему участнику всю его ставку и уведомляем
        if prev_id:
            prev_user = ensure_user(data, prev_id)
            prev_user["balance"] += prev_bid
            try:
                await bot.send_message(
                    int(prev_id),
                    f"⚠️ Ваша ставка {prev_bid} 💎 на NFT №{auction['token']['token']} была перебита в аукционе {auction_id}! Сумма возвращена вам на баланс."
                )
            except Exception as e:
                print("Ошибка уведомления предыдущего участника:", e)
        bidder["balance"] -= bid_amount
        auction["highest_bidder"] = str(message.from_user.id)

    auction["current_bid"] = bid_amount
    save_data(data)
    await message.answer(f"✅ Ваша ставка {bid_amount} 💎 принята для аукциона {auction_id}!")


##########################################
# Фоновая задача проверки завершения аукционов
##########################################

async def check_auctions():
    while True:
        data = load_data()
        auctions = data.get("auctions", [])
        now = datetime.datetime.now().timestamp()
        ended = [a for a in auctions if now > a["end_time"]]
        for auction in ended:
            seller = ensure_user(data, auction["seller_id"])
            highest = auction.get("highest_bidder")
            final_price = auction["current_bid"]
            token = auction["token"]

            if highest:
                buyer = ensure_user(data, highest)
                admin_cut = final_price * 5 // 100
                seller_cut = final_price - admin_cut
                seller["balance"] += seller_cut
                admin = ensure_user(data, ADMIN_ID)
                admin["balance"] += admin_cut

                token["bought_price"] = final_price
                token["bought_date"] = datetime.datetime.now().isoformat()
                token["bought_source"] = "auction"
                buyer.setdefault("tokens", []).append(token)

                try:
                    await bot.send_message(
                        int(highest),
                        f"🎉 Поздравляем! Вы выиграли аукцион {auction['auction_id']} за {final_price} 💎. "
                        f"NFT №{token['token']} зачислен в вашу коллекцию."
                    )
                except Exception as e:
                    print("Ошибка уведомления покупателя:", e)
            else:
                seller.setdefault("tokens", []).append(token)
                try:
                    await bot.send_message(
                        int(auction["seller_id"]),
                        f"Ваш аукцион {auction['auction_id']} завершился без ставок. NFT №{token['token']} возвращён вам."
                    )
                except Exception as e:
                    print("Ошибка уведомления продавца:", e)

            auctions.remove(auction)
        save_data(data)
        await asyncio.sleep(30)


##########################################
# Веб-эндпоинты аукционов (FastAPI)
##########################################

@router.get("/auctions", response_class=RedirectResponse)
async def auctions_page(request: Request):
    data = load_data()
    return templates.TemplateResponse("auctions.html", {
        "request": request,
        "auctions": data.get("auctions", []),
        "users": data.get("users", {}),
        "buyer_id": request.cookies.get("user_id")
    })


@router.post("/bid_web")
async def bid_web(request: Request, auction_id: str = Form(...), bid_amount: int = Form(...)):
    buyer_id = request.cookies.get("user_id")
    if not buyer_id:
        return RedirectResponse(url=f"/auctions?error={quote_plus('Ошибка: войдите в систему.')}", status_code=303)

    data = load_data()
    auction = next((a for a in data.get("auctions", []) if a["auction_id"] == auction_id), None)
    if not auction:
        return RedirectResponse(url=f"/auctions?error={quote_plus('Аукцион не найден.')}", status_code=303)

    now = datetime.datetime.now().timestamp()
    if now > auction["end_time"]:
        return RedirectResponse(url=f"/auctions?error={quote_plus('Аукцион завершён.')}", status_code=303)
    if bid_amount <= auction["current_bid"]:
        return RedirectResponse(url=f"/auctions?error={quote_plus('Ставка должна быть выше текущей.')}", status_code=303)

    buyer = ensure_user(data, buyer_id)
    if buyer.get("balance", 0) < bid_amount:
        return RedirectResponse(url=f"/auctions?error={quote_plus('Недостаточно средств.')}", status_code=303)

    prev_id = auction.get("highest_bidder")
    prev_bid = auction["current_bid"]

    if prev_id == buyer_id:
        additional = bid_amount - prev_bid
        if additional <= 0 or buyer["balance"] < additional:
            return RedirectResponse(
                url=f"/auctions?error={quote_plus('Недостаточно средств или ставка должна быть выше текущей.')}",
                status_code=303
            )
        buyer["balance"] -= additional
    else:
        if prev_id:
            prev_user = ensure_user(data, prev_id)
            prev_user["balance"] += prev_bid
            # уведомление через Telegram
            try:
                await bot.send_message(
                    int(prev_id),
                    f"⚠️ Ваша ставка {prev_bid} 💎 на NFT №{auction['token']['token']} была перебита в аукционе {auction_id}! Сумма возвращена вам на баланс."
                )
            except Exception as e:
                print("Ошибка уведомления предыдущего участника (веб):", e)
        buyer["balance"] -= bid_amount
        auction["highest_bidder"] = buyer_id

    auction["current_bid"] = bid_amount
    save_data(data)
    return RedirectResponse(url="/auctions", status_code=303)


@router.post("/auction_create")
async def create_auction_web(request: Request,
                             token_index: int = Form(...),
                             starting_price: int = Form(...),
                             duration_minutes: int = Form(...)):
    user_id = request.cookies.get("user_id")
    if not user_id:
        return RedirectResponse(url=f"/auctions?error={quote_plus('Ошибка: войдите в систему.')}", status_code=303)

    try:
        token_index = int(token_index) - 1
        starting_price = int(starting_price)
        duration_minutes = int(duration_minutes)
    except ValueError:
        return RedirectResponse(url=f"/auctions?error={quote_plus('Ошибка: Проверьте корректность полей.')}", status_code=303)

    data = load_data()
    user = ensure_user(data, user_id)
    tokens = user.get("tokens", [])
    if token_index < 0 or token_index >= len(tokens):
        return RedirectResponse(url=f"/auctions?error={quote_plus('Ошибка: Неверный номер nft.')}", status_code=303)

    token = tokens.pop(token_index)
    if user.get("custom_number") and user["custom_number"].get("token") == token["token"]:
        del user["custom_number"]
    auction_id = hashlib.sha256((user_id + token["token"] + str(datetime.datetime.now())).encode()).hexdigest()[:8]
    end_time = (datetime.datetime.now() + datetime.timedelta(minutes=duration_minutes)).timestamp()

    auction = {
        "auction_id": auction_id,
        "seller_id": user_id,
        "token": token,
        "starting_price": starting_price,
        "current_bid": starting_price,
        "highest_bidder": None,
        "end_time": end_time
    }
    data.setdefault("auctions", []).append(auction)
    save_data(data)
    return RedirectResponse(url="/auctions", status_code=303)


@router.post("/finish_auction")
async def finish_auction(request: Request, auction_id: str = Form(...)):
    user_id = request.cookies.get("user_id")
    if not user_id:
        return RedirectResponse(url=f"/auctions?error={quote_plus('Ошибка: войдите в систему.')}", status_code=303)

    data = load_data()
    auction = next((a for a in data.get("auctions", []) if a["auction_id"] == auction_id), None)
    if not auction or auction["seller_id"] != user_id:
        return RedirectResponse(url=f"/auctions?error={quote_plus('Ошибка: нет доступа или аукцион не найден.')}", status_code=303)

    now = datetime.datetime.now().timestamp()
    if now > auction["end_time"]:
        return RedirectResponse(url=f"/auctions?error={quote_plus('Ошибка: аукцион уже завершён.')}", status_code=303)

    auction["end_time"] = now
    seller = ensure_user(data, auction["seller_id"])
    highest = auction.get("highest_bidder")
    final_price = auction["current_bid"]
    token = auction["token"]

    if highest:
        buyer = ensure_user(data, highest)
        admin_cut = final_price * 5 // 100
        seller_cut = final_price - admin_cut
        seller["balance"] += seller_cut
        admin = ensure_user(data, ADMIN_ID)
        admin["balance"] += admin_cut

        token["bought_price"] = final_price
        token["bought_date"] = datetime.datetime.now().isoformat()
        token["bought_source"] = "auction"
        buyer.setdefault("tokens", []).append(token)

        try:
            await bot.send_message(
                int(highest),
                f"🎉 Поздравляем! Вы выиграли аукцион {auction_id} за {final_price} 💎. "
                f"NFT №{token['token']} зачислен в вашу коллекцию."
            )
        except Exception as e:
            print("Ошибка уведомления покупателя:", e)
    else:
        seller.setdefault("tokens", []).append(token)
        try:
            await bot.send_message(
                int(auction["seller_id"]),
                f"Ваш аукцион {auction_id} завершился без ставок. NFT №{token['token']} возвращён вам."
            )
        except Exception as e:
            print("Ошибка уведомления продавца:", e)

    data["auctions"].remove(auction)
    save_data(data)
    return RedirectResponse(url="/auctions", status_code=303)


##########################################
# Регистрация фоновой задачи проверки аукционов
##########################################

def register_auction_tasks(loop):
    loop.create_task(check_auctions())
