import os
from fastapi import APIRouter, Request, Form, File, UploadFile
from fastapi.responses import RedirectResponse, HTMLResponse
from common import (
    load_data, save_data,
    ensure_chats, get_new_chat_id,
    templates, require_web_login
)

router = APIRouter(prefix="/chats", tags=["chats"])

@router.get("/", response_class=HTMLResponse)
async def chats_list(request: Request):
    user_id = require_web_login(request)
    if not user_id:
        return RedirectResponse("/login", 303)
    data = load_data()
    chats = list(data.get("chats", {}).values())
    return templates.TemplateResponse("chats.html", {
        "request": request,
        "chats": chats,
        "user_id": user_id
    })

@router.post("/create")
async def create_chat(
    request: Request,
    name: str = Form(...),
    photo: UploadFile = File(None)
):
    user_id = require_web_login(request)
    if not user_id:
        return RedirectResponse("/login", 303)
    data = load_data()
    chats = ensure_chats(data)
    chat_id = get_new_chat_id()
    photo_url = None

    if photo and photo.filename:
        ext = photo.filename.rsplit(".", 1)[-1]
        fn = f"{chat_id}.{ext}"
        avatars_dir = os.path.join("static", "chat_avatars")
        os.makedirs(avatars_dir, exist_ok=True)
        path = os.path.join(avatars_dir, fn)
        with open(path, "wb") as f:
            f.write(await photo.read())
        photo_url = f"/static/chat_avatars/{fn}"

    chats[chat_id] = {
        "id": chat_id,
        "name": name,
        "photo_url": photo_url,
        "participants": [user_id]
    }
    save_data(data)
    return RedirectResponse(f"/chats/{chat_id}", 303)

@router.get("/{chat_id}", response_class=HTMLResponse)
async def view_chat(request: Request, chat_id: str):
    user_id = require_web_login(request)
    if not user_id:
        return RedirectResponse("/login", 303)
    data = load_data()
    chat = data.get("chats", {}).get(chat_id)
    if not chat:
        return HTMLResponse("Чат не найден", 404)
    is_participant = user_id in chat["participants"]
    return templates.TemplateResponse("chat.html", {
        "request": request,
        "chat": chat,
        "user_id": user_id,
        "is_participant": is_participant
    })

@router.post("/{chat_id}/join")
async def join_chat(request: Request, chat_id: str):
    user_id = require_web_login(request)
    if not user_id:
        return RedirectResponse("/login", 303)
    data = load_data()
    chat = data.get("chats", {}).get(chat_id)
    if chat and user_id not in chat["participants"]:
        chat["participants"].append(user_id)
        save_data(data)
    return RedirectResponse(f"/chats/{chat_id}", 303)
