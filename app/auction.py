# Auction.py
import asyncio
import datetime
from fastapi import APIRouter, HTTPException, Form
from fastapi.responses import JSONResponse
from common import bot, load_data, save_data, ensure_user

# Функция для удаления номера из профиля продавца
def remove_token_from_profile(user_id: str, token: str) -> bool:
    data = load_data()
    user = ensure_user(data, user_id)
    tokens = user.get("tokens", [])
    for t in tokens:
        if isinstance(t, dict) and t.get("token") == token:
            tokens.remove(t)
            save_data(data)
            return True
        elif isinstance(t, str) and t == token:
            tokens.remove(t)
            save_data(data)
            return True
    return False

# Функция для добавления номера в профиль пользователя
def add_token_to_profile(user_id: str, token: str, token_info: dict):
    data = load_data()
    user = ensure_user(data, user_id)
    user.setdefault("tokens", []).append({"token": token, "info": token_info})
    save_data(data)

# Функция для обновления баланса пользователя (сумма может быть отрицательной)
def update_user_balance(user_id: str, amount: int):
    data = load_data()
    user = ensure_user(data, user_id)
    user["balance"] = user.get("balance", 0) + amount
    save_data(data)

def get_user_balance(user_id: str) -> int:
    data = load_data()
    user = ensure_user(data, user_id)
    return user.get("balance", 0)

class Auction:
    def __init__(self):
        self.active = False
        self.token = None         # Номер (токен), выставленный на аукцион
        self.start_time = None
        self.end_time = None
        self.highest_bid = 0
        self.highest_bidder_id = None
        self.highest_bidder_name = None
        self.bids = []  # Список ставок
        self.seller_id = None  # ID продавца, запустившего аукцион
        self.token_info = {}   # Информация о номере: bg, digit_color, rarity

    async def start_auction(self, token: str, duration: int, seller_id: str, token_info: dict):
        if self.active:
            raise Exception("Аукцион уже активен")
        # Удаляем номер из профиля продавца
        if not remove_token_from_profile(seller_id, token):
            raise Exception("Токен не найден в профиле продавца")
        self.active = True
        self.token = token
        self.seller_id = seller_id
        self.token_info = token_info
        self.start_time = datetime.datetime.now()
        self.end_time = self.start_time + datetime.timedelta(seconds=duration)
        self.highest_bid = 0
        self.highest_bidder_id = None
        self.highest_bidder_name = None
        self.bids = []
        asyncio.create_task(self._auction_timer())
        print(f"Запущен аукцион для токена '{token}' на {duration} секунд. Продавец ID: {seller_id}")

    async def _auction_timer(self):
        while self.active:
            now = datetime.datetime.now()
            if now >= self.end_time:
                await self.end_auction()
                break
            await asyncio.sleep(1)

    async def place_bid(self, bidder_id: str, bidder_name: str, bid_amount: int) -> bool:
        if not self.active:
            raise Exception("Аукцион не активен")
        if bid_amount <= self.highest_bid:
            return False
        # Проверка баланса участника и списание денег
        if get_user_balance(bidder_id) < bid_amount:
            raise Exception("Недостаточно средств для ставки")
        update_user_balance(bidder_id, -bid_amount)
        self.highest_bid = bid_amount
        self.highest_bidder_id = bidder_id
        self.highest_bidder_name = bidder_name
        self.bids.append({
            "bidder_id": bidder_id,
            "bidder_name": bidder_name,
            "bid_amount": bid_amount,
            "timestamp": datetime.datetime.now().isoformat()
        })
        print(f"Новая ставка: {bid_amount} от {bidder_name} (ID: {bidder_id})")
        return True

    async def end_auction(self):
        if not self.active:
            return
        self.active = False
        if self.highest_bidder_id:
            print(f"Аукцион завершён. Победитель: {self.highest_bidder_name} (ID: {self.highest_bidder_id}) с ставкой {self.highest_bid}")
            # Передача номера победителю и зачисление денег продавцу
            add_token_to_profile(self.highest_bidder_id, self.token, self.token_info)
            update_user_balance(self.seller_id, self.highest_bid)
            await bot.send_message(
                self.seller_id,
                f"✅ Аукцион завершён. Победитель: {self.highest_bidder_name} (ID: {self.highest_bidder_id}) с ставкой {self.highest_bid}."
            )
        else:
            # Если ставок не было – возвращаем номер продавцу
            add_token_to_profile(self.seller_id, self.token, self.token_info)
            await bot.send_message(
                self.seller_id,
                "ℹ️ Аукцион завершён без ставок. Токен возвращён в ваш профиль."
            )
        # Сброс состояния аукциона
        self.token = None
        self.seller_id = None
        self.token_info = {}
        self.start_time = None
        self.end_time = None
        self.highest_bid = 0
        self.highest_bidder_id = None
        self.highest_bidder_name = None
        self.bids = []

    def get_time_remaining(self) -> int:
        if not self.active or not self.end_time:
            return 0
        remaining = (self.end_time - datetime.datetime.now()).total_seconds()
        return max(0, int(remaining))

# Глобальный экземпляр аукциона
auction_instance = Auction()

auction_router = APIRouter()

@auction_router.post("/start_auction")
async def start_auction(
    token: str = Form(...),
    duration: int = Form(...),
    seller_id: str = Form(...),
    bg: str = Form(...),
    digit_color: str = Form(...),
    rarity: str = Form(...)
):
    token_info = {"bg": bg, "digit_color": digit_color, "rarity": rarity}
    try:
        await auction_instance.start_auction(token, duration, seller_id, token_info)
        return JSONResponse({
            "message": "Аукцион запущен",
            "token": token,
            "duration": duration
        })
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@auction_router.post("/place_bid")
async def place_bid(
    bidder_id: str = Form(...),
    bidder_name: str = Form(...),
    bid_amount: int = Form(...),
):
    try:
        success = await auction_instance.place_bid(bidder_id, bidder_name, bid_amount)
        if success:
            return JSONResponse({
                "message": "Ставка принята",
                "highest_bid": auction_instance.highest_bid,
                "highest_bidder_id": auction_instance.highest_bidder_id,
                "highest_bidder_name": auction_instance.highest_bidder_name
            })
        else:
            return JSONResponse({
                "message": "Ваша ставка должна быть выше текущей",
                "highest_bid": auction_instance.highest_bid
            }, status_code=400)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@auction_router.get("/auction_status")
async def auction_status():
    if auction_instance.active:
        return JSONResponse({
            "active": True,
            "token": auction_instance.token,
            "highest_bid": auction_instance.highest_bid,
            "highest_bidder_id": auction_instance.highest_bidder_id,
            "highest_bidder_name": auction_instance.highest_bidder_name,
            "time_remaining": auction_instance.get_time_remaining(),
            "token_info": auction_instance.token_info
        })
    else:
        return JSONResponse({
            "active": False,
            "message": "Нет активного аукциона"
        })

@auction_router.get("/bids")
async def get_bids():
    return JSONResponse({"bids": auction_instance.bids})
