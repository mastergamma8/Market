import datetime
import uuid
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse

# Если общие функции и объекты вынесены в отдельный модуль common.py:
from common import load_data, save_data, ensure_user, templates, bot

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

router = APIRouter()

@router.get("/exchange", response_class=HTMLResponse)
async def web_exchange_form(request: Request):
    user_id = request.cookies.get("user_id")
    if not user_id:
        return HTMLResponse("Ошибка: не найден Telegram ID. Пожалуйста, войдите.", status_code=400)
    data = load_data()
    pending_exchanges = data.get("pending_exchanges", [])
    # Фильтруем сделки, где пользователь является инициатором или получателем
    user_exchanges = [ex for ex in pending_exchanges if ex["initiator_id"] == user_id or ex["target_id"] == user_id]
    return templates.TemplateResponse("exchange.html", {
        "request": request,
        "pending_exchanges": user_exchanges,
        "current_user_id": user_id
    })
    
@router.post("/exchange", response_class=HTMLResponse)
async def web_exchange_post(request: Request,
                            user_id: str = Form(None),
                            my_index: int = Form(...),
                            target_id: str = Form(...),
                            target_index: int = Form(...)):
    """
    Обрабатывает отправку формы обмена.
    """
    if not user_id:
        user_id = request.cookies.get("user_id")
    if not user_id:
        return HTMLResponse("Ошибка: не найден Telegram ID. Пожалуйста, войдите.", status_code=400)
    
    data = load_data()
    initiator = data.get("users", {}).get(user_id)
    target = data.get("users", {}).get(target_id)
    if not initiator or not target:
        return HTMLResponse("Один из пользователей не найден.", status_code=404)
    
    my_tokens = initiator.get("tokens", [])
    target_tokens = target.get("tokens", [])
    if my_index < 1 or my_index > len(my_tokens) or target_index < 1 or target_index > len(target_tokens):
        return HTMLResponse("Неверный номер у одного из пользователей.", status_code=400)
    
    # Извлекаем выбранные токены и удаляем их из списка
    my_token = my_tokens.pop(my_index - 1)
    target_token = target_tokens.pop(target_index - 1)
    
    exchange_id = str(uuid.uuid4())
    pending_exchange = {
        "exchange_id": exchange_id,
        "initiator_id": user_id,
        "target_id": target_id,
        "initiator_token": my_token,
        "target_token": target_token,
        "timestamp": datetime.datetime.now().isoformat(),
        "expires_at": (datetime.datetime.now() + datetime.timedelta(hours=24)).timestamp()
    }
    if "pending_exchanges" not in data:
        data["pending_exchanges"] = []
    data["pending_exchanges"].append(pending_exchange)
    save_data(data)

    # Формируем inline-клавиатуру для подтверждения/отказа обмена (для целевого пользователя)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Принять", callback_data=f"accept_exchange:{exchange_id}")],
        [InlineKeyboardButton(text="❌ Отклонить", callback_data=f"decline_exchange:{exchange_id}")]
    ])
    try:
        await bot.send_message(
            int(target_id),
            f"🔄 Пользователь {initiator.get('username', 'Неизвестный')} предлагает обмен:\n"
            f"Ваш номер: {target_token['token']}\n"
            f"на его номер: {my_token['token']}\n\n"
            "Нажмите «Принять» для подтверждения или «Отклонить» для отказа.\n\n"
            "Для отмены обмена введите /cancel_exchange <ID обмена>.",
            reply_markup=keyboard
        )
    except Exception as e:
        print("Ошибка отправки сообщения о предложении обмена:", e)
    
    # Возвращаем страницу с информацией о созданном обмене
    return templates.TemplateResponse("exchange_pending.html", {
        "request": request,
        "message": f"Предложение обмена отправлено. Ваш ID обмена: {exchange_id}",
        "exchange_id": exchange_id,
        "expires_at": datetime.datetime.fromtimestamp(pending_exchange["expires_at"]).strftime("%Y-%m-%d %H:%M:%S")
    })

@router.get("/accept_exchange_web/{exchange_id}", response_class=HTMLResponse)
async def accept_exchange_web(request: Request, exchange_id: str):
    """
    Веб‑эндпоинт для подтверждения обмена.
    После успешного подтверждения перенаправляет пользователя на страницу активных сделок.
    """
    user_id = request.cookies.get("user_id")
    if not user_id:
        return HTMLResponse("Ошибка: не найден Telegram ID. Пожалуйста, войдите.", status_code=400)
    
    data = load_data()
    pending = next((ex for ex in data.get("pending_exchanges", []) if ex["exchange_id"] == exchange_id), None)
    if not pending:
        return HTMLResponse("Предложение обмена не найдено или уже обработано.", status_code=404)
    if user_id != pending["target_id"]:
        return HTMLResponse("Вы не являетесь получателем этого предложения.", status_code=403)
    
    now_ts = datetime.datetime.now().timestamp()
    if now_ts > pending.get("expires_at", 0):
        return HTMLResponse("Предложение обмена истекло.", status_code=400)
    
    initiator = ensure_user(data, pending["initiator_id"])
    target = ensure_user(data, pending["target_id"])
    
    # Завершаем обмен: возвращаем токены соответствующим пользователям
    initiator.setdefault("tokens", []).append(pending["target_token"])
    target.setdefault("tokens", []).append(pending["initiator_token"])
    
    data["pending_exchanges"].remove(pending)
    save_data(data)
    
    # Редирект на страницу активных сделок с сообщением (можно реализовать flash‑сообщение)
    return RedirectResponse(url="/active_deals?message=Обмен+подтверждён", status_code=302)
    
@router.get("/decline_exchange_web/{exchange_id}", response_class=HTMLResponse)
async def decline_exchange_web(request: Request, exchange_id: str):
    """
    Веб‑эндпоинт для отклонения обмена.
    При отклонении возвращается страница с модальным окном.
    """
    user_id = request.cookies.get("user_id")
    if not user_id:
        return HTMLResponse("Ошибка: не найден Telegram ID. Пожалуйста, войдите.", status_code=400)
    
    data = load_data()
    pending = next((ex for ex in data.get("pending_exchanges", []) if ex["exchange_id"] == exchange_id), None)
    if not pending:
        return HTMLResponse("Предложение обмена не найдено или уже обработано.", status_code=404)
    if user_id != pending["target_id"]:
        return HTMLResponse("Вы не являетесь получателем этого предложения.", status_code=403)
    
    initiator = ensure_user(data, pending["initiator_id"])
    target = ensure_user(data, pending["target_id"])
    
    # Возвращаем токены обратно владельцам
    initiator.setdefault("tokens", []).append(pending["initiator_token"])
    target.setdefault("tokens", []).append(pending["target_token"])
    
    data["pending_exchanges"].remove(pending)
    save_data(data)
    
    return templates.TemplateResponse("exchange_result_modal.html", {
        "request": request,
        "title": "Обмен отменён",
        "message": "Обмен был отклонён. Попробуйте ещё раз позже.",
        "image_url": "/static/image/declined.png"
    })

@router.get("/cancel_exchange_web/{exchange_id}", response_class=HTMLResponse)
async def cancel_exchange_web(request: Request, exchange_id: str):
    """
    Веб‑эндпоинт для ручной отмены обмена.
    Здесь обмен отменяется, токены возвращаются владельцам, и обоим участникам через бота отправляется уведомление об отмене.
    """
    user_id = request.cookies.get("user_id")
    if not user_id:
        return HTMLResponse("Ошибка: не найден Telegram ID. Пожалуйста, войдите.", status_code=400)
    
    data = load_data()
    pending = next((ex for ex in data.get("pending_exchanges", []) if ex["exchange_id"] == exchange_id), None)
    if not pending:
        return HTMLResponse("Предложение обмена не найдено или уже обработано.", status_code=404)
    if user_id not in [pending["initiator_id"], pending["target_id"]]:
        return HTMLResponse("Вы не участвуете в этом обмене.", status_code=403)
    
    initiator = ensure_user(data, pending["initiator_id"])
    target = ensure_user(data, pending["target_id"])
    
    # Возвращаем токены обратно владельцам
    initiator.setdefault("tokens", []).append(pending["initiator_token"])
    target.setdefault("tokens", []).append(pending["target_token"])
    
    data["pending_exchanges"].remove(pending)
    save_data(data)
    
    # Отправляем уведомления через бота обоим участникам
    try:
        await bot.send_message(
            int(pending["initiator_id"]),
            f"Обмен с ID {exchange_id} был отменён вручную."
        )
    except Exception as e:
        print("Ошибка отправки уведомления инициатору:", e)
    
    try:
        await bot.send_message(
            int(pending["target_id"]),
            f"Обмен с ID {exchange_id} был отменён вручную."
        )
    except Exception as e:
        print("Ошибка отправки уведомления получателю:", e)
    
    return templates.TemplateResponse("exchange_result_modal.html", {
        "request": request,
        "title": "Обмен отменён",
        "message": "Обмен был отменён вручную.",
        "image_url": "/static/image/declined.png"
    })
    
@router.get("/active_deals", response_class=HTMLResponse)
async def active_deals(request: Request):
    user_id = request.cookies.get("user_id")
    if not user_id:
        return HTMLResponse("Ошибка: не найден Telegram ID. Пожалуйста, войдите.", status_code=400)
    data = load_data()
    pending_exchanges = data.get("pending_exchanges", [])
    # Фильтруем сделки, где пользователь является инициатором или получателем
    user_exchanges = [ex for ex in pending_exchanges if ex["initiator_id"] == user_id or ex["target_id"] == user_id]
    return templates.TemplateResponse("active_deals.html", {
        "request": request,
        "pending_exchanges": user_exchanges
    })
