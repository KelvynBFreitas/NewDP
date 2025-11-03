from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from jose import JWTError, jwt
import os
from app.models.user import User
from sqlalchemy.future import select
from app.core.database import get_session
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Request, Form, Depends, HTTPException
from app.core.config import SECRET_KEY
router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request,
                    session: AsyncSession = Depends(get_session)
):
    token = request.cookies.get("access_token")
    if not token:
        return RedirectResponse(url="/", status_code=302)
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        username = payload.get("sub")
        
    except JWTError:
        return RedirectResponse(url="/", status_code=302)
    cards = [
    {
        "icon": "bi-people",
        "title": "Usuários",
        "description": "Gerencie os usuários",
        "url": "/usuarios"
    },
    {
        "icon": "bi-gear",
        "title": "Configurações",
        "description": "Gerencie suas preferências",
        "url": "/config"
    },
    {
        "icon": "bi-bar-chart-line",
        "title": "Relatórios",
        "description": "Visualize seus dados",
        "url": "/relatorios"
    },
    {
        "icon": "bi-chat-dots",
        "title": "E-Mail PJ",
        "description": "Enviar E-Mail PJ para emissao de nota",
        "url": "/emailpj"
    },
        
]
    notifications = [
    {"title": "Novo relatório disponível", "url": "#"},
    # {"title": "Mensagem da equipe de suporte", "url": "#"},
    # {"title": "Atualização de perfil recomendada", "url": "#"}
    ]

    menus = [
        {"title": "Início", "url": "/dashboard"},
        {"title": "Administração", "submenu": [
            {"title": "Usuários", "url": "/usuarios"},
            {"title": "Areas", "url": "#"},
            
        ]},
        {"title": "Contato", "url": "#"},
       
        {"title": "Area Pessoa Judica", "submenu": [
            {"title": "Cadastro Colaborador", "url": "#"},
            {"title": "Cadastro Aprovador", "url": "#"},
            {"title": "E-Mail PJ", "url": "#"},
        ]}
    ]
    result = await session.execute(select(User).where(User.username == username))
    user = result.scalar()
    if user:
        username = user.username
        email = user.email
        username = username.title()
        nomes = username.split()
        if len(nomes) >= 2:
            primeiro_nome = nomes[0]
            ultimo_nome = nomes[-1]
            username = f"{primeiro_nome} {ultimo_nome}"
           
    else:
        username = ""
    
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "user_username": email,
        "username":username,
        "cards": cards,
        "empresa":"Grupo New",
        "menus": menus,
        "notifications": notifications,
        "notification_count": len(notifications)
    })
@router.get("/logout")
async def logout():
    response = RedirectResponse(url="/", status_code=302)
    response.delete_cookie("access_token", path="/")
    return response

