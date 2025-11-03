from fastapi import APIRouter, Request, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from jose import JWTError, jwt
import os
from pydantic import ValidationError
from app.core.database import get_session
from app.models.user import User
from app.services.auth_service import verify_password, create_access_token
from app.schemas.user_schema import UserLogin
from app.core.config import SECRET_KEY

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")
@router.get("/", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request,"empresa":"Grupo New"})

@router.post("/")
async def login(
    request: Request,
    username: str = Form(..., alias="usuario"),
    perfil: str = Form(..., alias="area"),
    password: str = Form(...),
    session: AsyncSession = Depends(get_session)
):
    # Validação com Pydantic manual
    print(perfil)
    try:
        form_data = UserLogin(username=username, password=password)
    except ValidationError:
        # CORREÇÃO 2: Mensagem de erro atualizada
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Formato de usuário inválido (use apenas letras e números).",
            "empresa":"Grupo New"
        })

    # CORREÇÃO 1: Usando form_data.username
    result = await session.execute(select(User).where(User.username == form_data.username))
    user = result.scalar()
    
    # PONTO DE ATENÇÃO 3: Verifique se 'user.hashed_password' é o nome correto
    if not user or not verify_password(form_data.password, user.hashed_password):
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Usuario ou senha inválidos",
            "empresa":"Grupo New"
        })

    token = create_access_token({"sub": user.username})
    response = RedirectResponse(url="/dashboard", status_code=302)
    response.set_cookie(key="access_token", value=token, httponly=True, samesite="Lax", secure=False)
    return response