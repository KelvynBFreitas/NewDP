from fastapi import APIRouter, Request, Form, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from jose import JWTError, jwt
import os
import math # <<< NOVO IMPORT
from typing import Optional # <<< NOVO IMPORT
from sqlalchemy.future import select
from sqlalchemy import func, or_ # <<< NOVOS IMPORTS
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_postgres_session
from app.core.config import SECRET_KEY

# Importe seus modelos
from app.models.user import User
from app.models.aprovadores import app_dp_pj_aprovador 

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

@router.get("/aprovador", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    session: AsyncSession = Depends(get_postgres_session),
    # <<< NOVOS PARÂMETROS PARA PAGINAÇÃO E BUSCA >>>
    page: int = Query(1, ge=1),
    per_page: int = Query(7, ge=1, le=100),
    search: Optional[str] = Query(None)
):
    token = request.cookies.get("access_token")
    if not token:
        return RedirectResponse(url="/", status_code=302)
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        username = payload.get("sub")
    except JWTError:
        return RedirectResponse(url="/", status_code=302)

    # ... (Seu código de cards, menus, notifications permanece o mesmo) ...
    cards = [
        {"icon": "bi-people", "title": "Usuários", "description": "Gerencie os usuários", "url": "/usuarios"},
        {"icon": "bi-gear", "title": "Configurações", "description": "Gerencie suas preferências", "url": "/config"},
        {"icon": "bi-bar-chart-line", "title": "Relatórios", "description": "Visualize seus dados", "url": "/relatorios"},
        {"icon": "bi-chat-dots", "title": "E-Mail PJ", "description": "Enviar E-Mail PJ para emissao de nota", "url": "/emailpj"},
    ]
    notifications = [
        {"title": "Novo relatório disponível", "url": "#"},
    ]
    menus = [
        {"title": "Início", "url": "/dashboard"},
        {"title": "Administração", "submenu": [
            {"title": "Usuários", "url": "/usuarios"},
            {"title": "Areas", "url": "#"},
        ]},
        {"title": "Contato", "url": "#"},
        {"title": "Area Pessoa Judica", "submenu": [
            {"title": "Cadastro Colaborador", "url": "/prestadoresdeservico"},
            {"title": "Cadastro Aprovador", "url": "/aprovador"},
            {"title": "E-Mail PJ", "url": "#"},
        ]}
    ]
    
    # ... (Seu código de lógica de usuário permanece o mesmo) ...
    result_user = await session.execute(select(User).where(User.username == username))
    user = result_user.scalar()
    if user:
        email = user.email
        username_display = user.username.title()
        nomes = username_display.split()
        if len(nomes) >= 2:
            primeiro_nome = nomes[0]
            ultimo_nome = nomes[-1]
            username_display = f"{primeiro_nome} {ultimo_nome}"
    else:
        email = ""
        username_display = ""
    
    # --- LÓGICA DE BUSCA E PAGINAÇÃO ---

    # 1. Define as queries base
    base_query = select(app_dp_pj_aprovador)
    count_query = select(func.count(app_dp_pj_aprovador.id))
    
    search_term = search.strip() if search else None
    
    # 2. Adiciona o filtro de busca, se existir
    if search_term:
        like_term = f"%{search_term}%"
        search_filter = or_(
            app_dp_pj_aprovador.nome.ilike(like_term),
            app_dp_pj_aprovador.cpf.ilike(like_term),
            app_dp_pj_aprovador.email.ilike(like_term)
        )
        base_query = base_query.where(search_filter)
        count_query = count_query.where(search_filter)

    # 3. Conta o total de itens (com o filtro aplicado)
    total_result = await session.execute(count_query)
    total_items = total_result.scalar() or 0
    total_pages = math.ceil(total_items / per_page) if total_items > 0 else 1
    
    # Garante que a página não seja maior que o total de páginas
    page = min(page, total_pages)
    
    # 4. Calcula o offset
    offset = (page - 1) * per_page

    # 5. Busca os itens da página atual
    items_query = base_query.order_by(app_dp_pj_aprovador.nome).offset(offset).limit(per_page)
    items_result = await session.execute(items_query)
    aprovadores_list = items_result.scalars().all()
    # --- FIM DA LÓGICA ---

    return templates.TemplateResponse("cad_aprovador.html", {
        "request": request,
        "user_username": email,
        "username": username_display,
        "cards": cards,
        "empresa": "Grupo New",
        "menus": menus,
        "notifications": notifications,
        "notification_count": len(notifications),
        
        # --- NOVOS DADOS PARA O TEMPLATE ---
        "aprovadores": aprovadores_list,
        "page": page,
        "total_pages": total_pages,
        "search_term": search_term # Para preencher o campo de busca
    })

# --- ROTAS POST ATUALIZADAS (PARA REDIRECIONAMENTO) ---

@router.post("/aprovador/novo", response_class=RedirectResponse)
async def adicionar_aprovador(
    request: Request, # Precisamos do request
    cpf: str = Form(...),
    nome: str = Form(...),
    email: str = Form(...),
    session: AsyncSession = Depends(get_postgres_session)
):
    result = await session.execute(
        select(app_dp_pj_aprovador).where(
            (app_dp_pj_aprovador.nome == nome) | (app_dp_pj_aprovador.email == email)
        )
    )
    if result.scalar():
        raise HTTPException(status_code=400, detail="Nome ou E-mail já cadastrado.")

    novo_aprovador = app_dp_pj_aprovador(cpf=cpf, nome=nome, email=email, situacao=True)
    session.add(novo_aprovador)
    await session.commit()
    
    # <<< MUDANÇA AQUI: Redireciona para a página de origem
    referer_url = request.headers.get('Referer', '/aprovador')
    return RedirectResponse(url=referer_url, status_code=303)

@router.post("/aprovador/alterar", response_class=RedirectResponse)
async def alterar_aprovador(
    request: Request, # Precisamos do request
    id: int = Form(...), 
    cpf: str = Form(...),
    nome: str = Form(...),
    email: str = Form(...),
    situacao: str = Form(...), 
    session: AsyncSession = Depends(get_postgres_session)
):
    result = await session.execute(
        select(app_dp_pj_aprovador).where(app_dp_pj_aprovador.id == id)
    )
    aprovador = result.scalar()
    
    if not aprovador:
        raise HTTPException(status_code=404, detail="Aprovador não encontrado.")
    
    aprovador.cpf = cpf 
    aprovador.nome = nome
    aprovador.email = email
    aprovador.situacao = (situacao == "ativo") 
    
    await session.commit()
    
    # <<< MUDANÇA AQUI: Redireciona para a página de origem
    referer_url = request.headers.get('Referer', '/aprovador')
    return RedirectResponse(url=referer_url, status_code=303)

@router.post("/aprovador/status/{id}", response_class=RedirectResponse)
async def mudar_status_aprovador(
    request: Request, # Precisamos do request
    id: int, 
    session: AsyncSession = Depends(get_postgres_session)
):
    result = await session.execute(
        select(app_dp_pj_aprovador).where(app_dp_pj_aprovador.id == id)
    )
    aprovador = result.scalar()
    
    if not aprovador:
        raise HTTPException(status_code=404, detail="Aprovador não encontrado.")

    aprovador.situacao = not aprovador.situacao
    
    await session.commit()
    
    # <<< MUDANÇA AQUI: Redireciona para a página de origem
    referer_url = request.headers.get('Referer', '/aprovador')
    return RedirectResponse(url=referer_url, status_code=303)


@router.get("/logout")
async def logout():
    response = RedirectResponse(url="/", status_code=302)
    response.delete_cookie("access_token", path="/")
    return response