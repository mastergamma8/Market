import asyncio
import datetime
from fastapi import APIRouter, HTTPException, Form
from fastapi.responses import JSONResponse

# Класс, реализующий логику аукциона с информацией о пользователе (ID и имя)
class Auction:
    def __init__(self):
        self.active = False
        self.token = None         # Токен (номер), выставленный на аукцион
        self.start_time = None
        self.end_time = None
        self.highest_bid = 0
        self.highest_bidder_id = None
        self.highest_bidder_name = None
        self.bids = []  # Список ставок. Каждая ставка – dict с ключами:
                        # bidder_id, bidder_name, bid_amount, timestamp

    async def start_auction(self, token: str, duration: int):
        if self.active:
            raise Exception("Аукцион уже активен")
        self.active = True
        self.token = token
        self.start_time = datetime.datetime.now()
        self.end_time = self.start_time + datetime.timedelta(seconds=duration)
        self.highest_bid = 0
        self.highest_bidder_id = None
        self.highest_bidder_name = None
        self.bids = []
        # Запускаем фоновую задачу, которая завершит аукцион по истечении времени
        asyncio.create_task(self._auction_timer())
        print(f"Запущен аукцион для токена '{token}' на {duration} секунд.")

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
            # Новая ставка должна быть строго больше текущей
            return False
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
            # Здесь можно добавить логику передачи токена победителю
        else:
            print("Аукцион завершён без ставок.")
        # Сброс состояния аукциона (история ставок можно сохранить отдельно, если потребуется)
        self.token = None
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

# Роутер для эндпоинтов аукциона
auction_router = APIRouter()

@auction_router.post("/start_auction")
async def start_auction(
    token: str = Form(...),
    duration: int = Form(...),
):
    """
    Запускает аукцион для заданного токена на указанное время (в секундах).
    Пример запроса: token=1234, duration=60
    """
    try:
        await auction_instance.start_auction(token, duration)
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
    """
    Размещает ставку. Ставка принимается, если она больше текущей максимальной.
    Пример запроса: bidder_id=123456, bidder_name=Иван, bid_amount=500
    """
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
    """
    Возвращает статус аукциона: активность, токен, текущую максимальную ставку, победителя и оставшееся время (в секундах).
    """
    if auction_instance.active:
        return JSONResponse({
            "active": True,
            "token": auction_instance.token,
            "highest_bid": auction_instance.highest_bid,
            "highest_bidder_id": auction_instance.highest_bidder_id,
            "highest_bidder_name": auction_instance.highest_bidder_name,
            "time_remaining": auction_instance.get_time_remaining()
        })
    else:
        return JSONResponse({
            "active": False,
            "message": "Нет активного аукциона"
        })

@auction_router.get("/bids")
async def get_bids():
    """
    Возвращает список всех ставок текущего аукциона.
    """
    return JSONResponse({"bids": auction_instance.bids})
