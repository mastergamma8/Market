import datetime
import random
import asyncio

from common import load_data, save_data, ensure_user, bot, dp
from aiogram.filters import Command
from aiogram.types import Message
from fastapi import APIRouter, Request, Form, Body
from fastapi.responses import HTMLResponse, RedirectResponse

# Создаем роутер для веб-части ежедневной награды
router = APIRouter()

# =========================
# БОТ: Команда /daily
# =========================

@dp.message(Command("daily"))
async def daily_reward_bot(message: Message) -> None:
    """
    Обработчик команды /daily для бота.
    Если пользователь не получил награду сегодня, начисляется 25 алмазов.
    При последовательном входе увеличивается счетчик; если 7 дней подряд – сброс.
    """
    data = load_data()
    user_id = str(message.from_user.id)
    user = ensure_user(data, user_id, message.from_user.username or message.from_user.first_name)
    
    today = datetime.date.today()
    last_reward_str = user.get("last_daily_reward")
    consecutive = user.get("consecutive_daily_logins", 0)
    
    if last_reward_str:
        last_reward_date = datetime.date.fromisoformat(last_reward_str)
        if last_reward_date == today:
            await message.answer("Вы уже получили ежедневную награду сегодня!")
            return
        elif last_reward_date == today - datetime.timedelta(days=1):
            consecutive += 1
        else:
            consecutive = 1
    else:
        consecutive = 1

    reward_amount = 25
    user["balance"] = user.get("balance", 0) + reward_amount
    user["last_daily_reward"] = today.isoformat()
    
    if consecutive >= 7:
        user["consecutive_daily_logins"] = 0
        msg = (f"Поздравляем! Вы получили награду за 7 последовательных дней и заработали {reward_amount} 💎!\n"
               "Ваш счет обновлен, и счетчик последовательных входов сброшен. Завтра начинайте заново.")
    else:
        user["consecutive_daily_logins"] = consecutive
        msg = (f"Ежедневная награда получена! Вы заработали {reward_amount} 💎.\n"
               f"Последовательных дней входа: {consecutive}.")

    save_data(data)
    await message.answer(msg)

# =========================
# ВЕБ: Эндпоинт /daily
# =========================

@router.post("/daily", response_class=HTMLResponse)
async def daily_reward_web(request: Request):
    """
    Эндпоинт для ежедневной награды в веб-интерфейсе.
    Если пользователь не получил награду сегодня, начисляется 25 алмазов.
    """
    data = load_data()
    user_id = request.cookies.get("user_id")
    if not user_id:
        return HTMLResponse("Ошибка: не найден Telegram ID. Пожалуйста, войдите.", status_code=400)
    
    user = data.get("users", {}).get(user_id)
    if not user:
        return HTMLResponse("Пользователь не найден.", status_code=404)
    
    today = datetime.date.today()
    last_reward_str = user.get("last_daily_reward")
    consecutive = user.get("consecutive_daily_logins", 0)
    
    if last_reward_str:
        last_reward_date = datetime.date.fromisoformat(last_reward_str)
        if last_reward_date == today:
            # Если награда уже получена сегодня, перенаправляем с сообщением
            return RedirectResponse(url=f"/profile/{user_id}?msg=reward_already", status_code=303)
        elif last_reward_date == today - datetime.timedelta(days=1):
            consecutive += 1
        else:
            consecutive = 1
    else:
        consecutive = 1

    reward_amount = 25
    user["balance"] = user.get("balance", 0) + reward_amount
    user["last_daily_reward"] = today.isoformat()
    
    if consecutive >= 7:
        user["consecutive_daily_logins"] = 0
    else:
        user["consecutive_daily_logins"] = consecutive
    
    save_data(data)
    return RedirectResponse(url=f"/profile/{user_id}?msg=daily_success", status_code=303)

# =========================
# Если файл запускается напрямую (для тестирования)
# =========================

if __name__ == "__main__":
    # Если вы хотите запустить daily.py как отдельное приложение для веб, создайте FastAPI-приложение
    import uvicorn
    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(router)
    uvicorn.run(app, host="0.0.0.0", port=8001)
