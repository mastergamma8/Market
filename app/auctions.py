import asyncio
import datetime
import hashlib

from aiogram import Dispatcher
from aiogram.types import Message
from aiogram.filters import Command

from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse

# Импорт общих функций и объектов
from common import load_data, save_data, ensure_user, templates, bot

# Если у вас уже есть глобальный диспетчер (dp) в common.py или main.py, можно его импортировать:
from common import dp

router = APIRouter()


#############################
# Телеграм‑обработчики аукционов
#############################

@dp.message(Command("auction"))
async def create_auction(message: Message) -> None:
    """
    Команда для создания аукциона.
    Формат: /auction <номер токена> <начальная цена> <длительность (мин)>
    Пример: /auction 2 500 10
    """
    parts = message.text.split()
    if len(parts) != 4:
        await message.answer("❗ Формат: /auction <номер токена> <начальная цена> <длительность (мин)>")
        return
    try:
        token_index = int(parts[1]) - 1
        starting_price = int(parts[2])
        duration_minutes = int(parts[3])
    except ValueError:
        await message.answer("❗ Проверьте, что номер токена, начальная цена и длительность — числа.")
        return

    data = load_data()
    user = ensure_user(data, str(message.from_user.id))
    tokens = user.get("tokens", [])
    if token_index < 0 or token_index >= len(tokens):
        await message.answer("❗ Неверный номер токена в вашей коллекции.")
        return

    # Извлекаем токен из коллекции пользователя
    token = tokens.pop(token_index)

    # Генерируем уникальный идентификатор аукциона (используем хэш)
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

    if "auctions" not in data:
        data["auctions"] = []
    data["auctions"].append(auction)
    save_data(data)
    await message.answer(
        f"🚀 Аукцион создан!\nID аукциона: {auction_id}\nНачальная цена: {starting_price} 💎\n"
        f"Окончание: {datetime.datetime.fromtimestamp(end_time).strftime('%Y-%m-%d %H:%M:%S')}"
    )


@dp.message(Command("bid"))
async def bid_on_auction(message: Message) -> None:
    """
    Команда для размещения ставки.
    Формат: /bid <auction_id> <ставка>
    Пример: /bid a1b2c3d4 750
    """
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
    auctions = data.get("auctions", [])
    auction = next((a for a in auctions if a["auction_id"] == auction_id), None)
    if auction is None:
        await message.answer("❗ Аукцион не найден.")
        return

    current_time = datetime.datetime.now().timestamp()
    if current_time > auction["end_time"]:
        await message.answer("❗ Аукцион уже завершён.")
        return

    if bid_amount <= auction["current_bid"]:
        await message.answer("❗ Ваша ставка должна быть выше текущей.")
        return

    bidder = ensure_user(data, str(message.from_user.id))
    if bidder.get("balance", 0) < bid_amount:
        await message.answer("❗ Недостаточно средств для ставки.")
        return

    auction["current_bid"] = bid_amount
    auction["highest_bidder"] = str(message.from_user.id)
    save_data(data)
    await message.answer(f"✅ Ваша ставка {bid_amount} 💎 для аукциона {auction_id} принята!")


##########################################
# Фоновая задача проверки завершения аукционов
##########################################

async def check_auctions():
    """
    Фоновая функция, которая каждые 30 секунд проверяет активные аукционы.
    Если время завершения истекло:
      - Если есть победитель и у него достаточно средств – перевод токена и списание средств.
      - Иначе – токен возвращается продавцу.
    """
    while True:
        data = load_data()
        if "auctions" in data:
            auctions = data["auctions"]
            current_time = datetime.datetime.now().timestamp()
            ended_auctions = [a for a in auctions if current_time > a["end_time"]]
            for auction in ended_auctions:
                seller_id = auction["seller_id"]
                highest_bidder = auction["highest_bidder"]
                final_price = auction["current_bid"]
                token = auction["token"]
                seller = ensure_user(data, seller_id)
                if highest_bidder is not None:
                    buyer = ensure_user(data, highest_bidder)
                    if buyer.get("balance", 0) < final_price:
                        seller.setdefault("tokens", []).append(token)
                        try:
                            await bot.send_message(int(seller_id),
                                                   f"Ваш аукцион {auction['auction_id']} завершился, "
                                                   f"но победитель не имел достаточного баланса. Токен возвращён вам.")
                        except Exception as e:
                            print("Ошибка уведомления продавца:", e)
                    else:
                        buyer["balance"] -= final_price
                        seller["balance"] += final_price
                        buyer.setdefault("tokens", []).append(token)
                        try:
                            await bot.send_message(int(highest_bidder),
                                                   f"Поздравляем! Вы выиграли аукцион {auction['auction_id']} "
                                                   f"за {final_price} 💎. Токен зачислен в вашу коллекцию.")
                        except Exception as e:
                            print("Ошибка уведомления покупателя:", e)
                else:
                    seller.setdefault("tokens", []).append(token)
                    try:
                        await bot.send_message(int(seller_id),
                                               f"Ваш аукцион {auction['auction_id']} завершился без ставок. "
                                               f"Токен возвращён вам.")
                    except Exception as e:
                        print("Ошибка уведомления продавца:", e)
                auctions.remove(auction)
            save_data(data)
        await asyncio.sleep(30)


##########################################
# Веб‑эндпоинты аукционов (FastAPI)
##########################################

@router.get("/auctions", response_class=HTMLResponse)
async def auctions_page(request: Request):
    data = load_data()
    auctions = data.get("auctions", [])
    return templates.TemplateResponse("auctions.html", {
        "request": request,
        "auctions": auctions,
        "users": data.get("users", {}),
        "buyer_id": request.cookies.get("user_id")
    })


@router.post("/bid_web")
async def bid_web(request: Request, auction_id: str = Form(...), bid_amount: int = Form(...)):
    buyer_id = request.cookies.get("user_id")
    if not buyer_id:
        return HTMLResponse("Ошибка: войдите в систему.", status_code=400)
    
    data = load_data()
    auctions = data.get("auctions", [])
    auction = next((a for a in auctions if a["auction_id"] == auction_id), None)
    if auction is None:
        return HTMLResponse("Аукцион не найден.", status_code=404)
    
    current_time = datetime.datetime.now().timestamp()
    if current_time > auction["end_time"]:
        return HTMLResponse("Аукцион завершён.", status_code=400)
    
    if bid_amount <= auction["current_bid"]:
        return HTMLResponse("Ставка должна быть выше текущей.", status_code=400)
    
    buyer = ensure_user(data, buyer_id)
    if buyer.get("balance", 0) < bid_amount:
        return HTMLResponse("Недостаточно средств.", status_code=400)
    
    auction["current_bid"] = bid_amount
    auction["highest_bidder"] = buyer_id
    save_data(data)
    return RedirectResponse(url="/auctions", status_code=303)


@router.post("/auction_create")
async def create_auction_web(request: Request,
                             token_index: int = Form(...),
                             starting_price: int = Form(...),
                             duration_minutes: int = Form(...)):
    """
    Обработка создания аукциона через веб‑форму (модальное окно).
    """
    user_id = request.cookies.get("user_id")
    if not user_id:
        return HTMLResponse("Ошибка: войдите в систему.", status_code=400)
    
    try:
        token_index = int(token_index) - 1  # если пользователь вводит номер начиная с 1
        starting_price = int(starting_price)
        duration_minutes = int(duration_minutes)
    except ValueError:
        return HTMLResponse("Ошибка: Проверьте, что все поля заполнены корректно.", status_code=400)
    
    data = load_data()
    user = ensure_user(data, user_id)
    tokens = user.get("tokens", [])
    if token_index < 0 or token_index >= len(tokens):
        return HTMLResponse("Ошибка: Неверный номер токена.", status_code=400)
    
    token = tokens.pop(token_index)
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
    
    if "auctions" not in data:
        data["auctions"] = []
    data["auctions"].append(auction)
    save_data(data)
    return RedirectResponse(url="/auctions", status_code=303)


@router.post("/finish_auction")
async def finish_auction(request: Request, auction_id: str = Form(...)):
    """
    Ручное завершение аукциона.
    Только продавец данного аукциона может его завершить досрочно.
    После завершения производится финализация (аналог фоновой задачи).
    """
    user_id = request.cookies.get("user_id")
    if not user_id:
        return HTMLResponse("Ошибка: войдите в систему.", status_code=400)
    
    data = load_data()
    auctions = data.get("auctions", [])
    auction = next((a for a in auctions if a["auction_id"] == auction_id), None)
    if auction is None:
        return HTMLResponse("Ошибка: Аукцион не найден.", status_code=404)
    
    if auction["seller_id"] != user_id:
        return HTMLResponse("Ошибка: Только продавец может завершить аукцион.", status_code=403)
    
    current_time = datetime.datetime.now().timestamp()
    if current_time > auction["end_time"]:
        return HTMLResponse("Ошибка: Аукцион уже завершён.", status_code=400)
    
    # Завершаем аукцион досрочно: устанавливаем end_time равным текущему времени
    auction["end_time"] = current_time
    
    # Финализируем аукцион (аналог логики в check_auctions)
    seller_id = auction["seller_id"]
    highest_bidder = auction["highest_bidder"]
    final_price = auction["current_bid"]
    token = auction["token"]
    seller = ensure_user(data, seller_id)
    if highest_bidder is not None:
        buyer = ensure_user(data, highest_bidder)
        if buyer.get("balance", 0) < final_price:
            seller.setdefault("tokens", []).append(token)
            try:
                await bot.send_message(int(seller_id),
                                       f"Ваш аукцион {auction_id} завершился, но победитель не имел достаточного баланса. Токен возвращён вам.")
            except Exception as e:
                print("Ошибка уведомления продавца:", e)
        else:
            buyer["balance"] -= final_price
            seller["balance"] += final_price
            buyer.setdefault("tokens", []).append(token)
            try:
                await bot.send_message(int(highest_bidder),
                                       f"Поздравляем! Вы выиграли аукцион {auction_id} за {final_price} 💎. Токен зачислен в вашу коллекцию.")
            except Exception as e:
                print("Ошибка уведомления покупателя:", e)
    else:
        seller.setdefault("tokens", []).append(token)
        try:
            await bot.send_message(int(seller_id),
                                   f"Ваш аукцион {auction_id} завершился без ставок. Токен возвращён вам.")
        except Exception as e:
            print("Ошибка уведомления продавца:", e)
    
    auctions.remove(auction)
    save_data(data)
    return RedirectResponse(url="/auctions", status_code=303)


##########################################
# Регистрация фоновой задачи проверки аукционов
##########################################

def register_auction_tasks(loop):
    loop.create_task(check_auctions())
