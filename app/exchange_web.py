import datetime
import uuid
from fastapi import APIRouter, Request, Form, BackgroundTasks
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
    
@router.post("/exchange")
async def web_exchange_post(
        request: Request,
        background_tasks: BackgroundTasks,
        user_id: str = Form(None),
        my_index: int = Form(...),
        target_id: str = Form(...),
        target_index: int = Form(...),
):
    # 1) Получаем свой user_id
    if not user_id:
        user_id = request.cookies.get("user_id")
    if not user_id:
        return HTMLResponse("Ошибка: не найден Telegram ID. Пожалуйста, войдите.", status_code=400)

    data = load_data()
    initiator = data.get("users", {}).get(user_id)
    if not initiator:
        return HTMLResponse("Инициатор не найден.", status_code=404)

    # 2) Пытаемся найти target по анонимному номеру или custom_number
    resolved_uid = None
    for uid, u in data.get("users", {}).items():
        if (u.get("crossed_number", {}).get("token") == target_id
            or u.get("custom_number",    {}).get("token") == target_id):
            resolved_uid = uid
            break
    # если не нашли по анонимке — считаем, что ввели просто ID
    if resolved_uid is None:
        resolved_uid = target_id

    # валидируем, что это число и пользователь есть в БД
    if not resolved_uid.isdigit() or resolved_uid not in data.get("users", {}):
        return HTMLResponse("Пользователь не найден по указанному анонимному номеру.", status_code=404)
    target = data["users"][resolved_uid]

    # 3) Проверяем границы индексов и извлекаем токены
    my_tokens     = initiator.get("tokens", [])
    target_tokens = target.get("tokens", [])
    if my_index < 1 or my_index > len(my_tokens):
        return HTMLResponse("Неверный индекс вашего номера.", status_code=400)
    if target_index < 1 or target_index > len(target_tokens):
        return HTMLResponse("Неверный индекс номера у пользователя.", status_code=400)

    my_token     = my_tokens.pop(my_index - 1)
    target_token = target_tokens.pop(target_index - 1)

    # 4) Сбрасываем профильные номера, если они задействованы
    if initiator.get("custom_number", {}).get("token") == my_token["token"]:
        del initiator["custom_number"]
    if target.get("custom_number", {}).get("token") == target_token["token"]:
        del target["custom_number"]

    # 5) Создаём pending_exchange
    exchange_id = str(uuid.uuid4())
    pending = {
        "exchange_id":     exchange_id,
        "initiator_id":    user_id,
        "target_id":       resolved_uid,
        "initiator_token": my_token,
        "target_token":    target_token,
        "timestamp":       datetime.datetime.now().isoformat(),
        "expires_at":      (datetime.datetime.now() + datetime.timedelta(hours=24)).timestamp()
    }
    data.setdefault("pending_exchanges", []).append(pending)
    save_data(data)

    # 6) Запускаем уведомление в фоне
    background_tasks.add_task(_notify_exchange, resolved_uid, my_token, target_token, exchange_id)

    # 7) Редиректим пользователя на список активных сделок с флеш-сообщением
    return RedirectResponse(
        url=f"{request.url_for('active_deals')}?msg=exchange_sent",
        status_code=303
    )

@router.get("/accept_exchange_web/{exchange_id}", response_class=HTMLResponse)
async def accept_exchange_web(request: Request, exchange_id: str):
    """
    Веб‑эндпоинт для подтверждения обмена.
    После успешного подтверждения обмена уведомления отправляются обоим участникам через Telegram-бота,
    в которых указаны детали сделки (какой токен отдали и какой получили).
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

    # Завершаем обмен: инициатор получает токен получателя, а получатель – токен инициатора
    initiator.setdefault("tokens", []).append(pending["target_token"])
    target.setdefault("tokens", []).append(pending["initiator_token"])

    data["pending_exchanges"].remove(pending)
    save_data(data)

    # Отправляем уведомление инициатору через Telegram-бота
    try:
        await bot.send_message(
            int(pending["initiator_id"]),
            f"Обмен с ID {exchange_id} принят.\n"
            f"Вы отдали токен {pending['initiator_token']} и получили токен {pending['target_token']}."
        )
    except Exception as e:
        print("Ошибка отправки уведомления инициатору:", e)

    # Отправляем уведомление получателю через Telegram-бота
    try:
        await bot.send_message(
            int(pending["target_id"]),
            f"Обмен с ID {exchange_id} принят.\n"
            f"Вы отдали токен {pending['target_token']} и получили токен {pending['initiator_token']}."
        )
    except Exception as e:
        print("Ошибка отправки уведомления получателю:", e)

    return templates.TemplateResponse("exchange_result_modal.html", {
        "request": request,
        "title": "Обмен подтверждён",
        "message": "Обмен был подтверждён. Проверьте сообщения в Telegram для подробностей.",
        "image_url": "/static/image/confirmed.png"  # Убедитесь, что указанное изображение существует
    })
    
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
