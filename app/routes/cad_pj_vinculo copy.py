from fastapi import APIRouter, Request, Form, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from jose import JWTError, jwt
import os
import math
import pathlib # <<< ADICIONADO PARA LER O ARQUIVO
from typing import Optional
from sqlalchemy.future import select
from sqlalchemy import func, or_, text # <<< 'text' ESTÁ AQUI
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_oracle_session,get_postgres_session
from app.core.config import SECRET_KEY

# Importe seus modelos
from app.models.user import User
from app.models.funcionarios_pj_postgres import app_dp_pj_aprovador_x_prestado
# from app.models.funcionarios_pj import ColaboradorInfo 

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

# --- BLOCO DE LEITURA DO ARQUIVO ---
# Pega o caminho do diretório ATUAL (onde este arquivo de rota está)
# Ajuste o '..' se seu arquivo de rota estiver em /routers e o 'app' for o pai
# Supondo que a estrutura é: app/routers/sua_rota.py e app/queries/prestadores.sql
BASE_DIR = pathlib.Path(__file__).resolve().parent.parent # Sobe um nível para 'app'
SQL_QUERY_FILE = BASE_DIR / "queries" / "colaboradores.sql"

QUERY_COLABORADORES = ""
try:
    with open(SQL_QUERY_FILE, "r", encoding="utf-8") as f:
        QUERY_COLABORADORES = f.read()
except FileNotFoundError:
    print(f"ERRO CRÍTICO: Arquivo de query não encontrado em {SQL_QUERY_FILE}")
    # Você pode lançar um erro aqui para impedir a aplicação de iniciar sem a query
    # raise RuntimeError("Não foi possível carregar a query SQL de prestadores.")
# --- FIM DO BLOCO DE LEITURA ---


@router.get("/prestadoresdeservico", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    session: AsyncSession = Depends(get_postgres_session),
    sessiondb: AsyncSession = Depends(get_oracle_session),
    page: int = Query(1, ge=1),
    per_page: int = Query(7, ge=1, le=100),
    search: Optional[str] = Query(None)
):
    
    # --- Verificação se a query foi carregada ---
    if not QUERY_COLABORADORES:
        raise HTTPException(status_code=500, 
                            detail="Erro interno: A query SQL principal não foi carregada.")

    token = request.cookies.get("access_token")
    if not token:
        return RedirectResponse(url="/", status_code=302)
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        username = payload.get("sub")
    except JWTError:
        return RedirectResponse(url="/", status_code=302)

    # ... (código dos cards, menus, notifications) ...
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
            {"title": "Cadastro Colaborador", "url": "#"},
            {"title": "Cadastro Aprovador", "url": "#"},
            {"title": "E-Mail PJ", "url": "#"},
        ]}
    ]
    
    # ... (código de lógica de usuário) ...
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
    
    ## Base
    # 1. Define as queries base
    base_query = select(app_dp_pj_aprovador_x_prestado)
    count_query = select(func.count(app_dp_pj_aprovador_x_prestado.id))
    search_term = search.strip() if search else None
    
    # 2. Adiciona o filtro de busca, se existir
    if search_term:
        like_term = f"%{search_term}%"
        search_filter = or_(
            app_dp_pj_aprovador_x_prestado.cpf_aprovador.ilike(like_term),
            app_dp_pj_aprovador_x_prestado.cpf_prestador.ilike(like_term),
            app_dp_pj_aprovador_x_prestado.razao_social.ilike(like_term)
        )
        base_query = base_query.where(search_filter)
        count_query = count_query.where(search_filter)

    # 3. Conta o total de itens (com o filtro aplicado)
    total_result = await session.execute(count_query)
    total_items = total_result.scalar() or 0
    
    print(total_result)
    # --- LÓGICA DE BUSCA E PAGINAÇÃO (USANDO A QUERY DO ARQUIVO) ---
    
    # 1. Envelopa a query lida do arquivo
    base_sql = f"({QUERY_COLABORADORES}) A"
    
    # 2. Dicionário de parâmetros
    params = {}

    # 3. Construção da cláusula WHERE
    where_clauses = []
    search_term = search.strip() if search else None
    
    if search_term:
        where_clauses.append(
            """
            (
              UPPER(A.NOMECOMPLETO) LIKE UPPER(:search_like) OR
              UPPER(A.CPF) LIKE UPPER(:search_like) OR
              UPPER(A.EMAIL_COLABORADOR) LIKE UPPER(:search_like)
            )
            """
        )
        params["search_like"] = f"%{search_term}%"
        
    where_sql = ""
    if where_clauses:
        where_sql = " WHERE " + " AND ".join(where_clauses)

    # 4. Query de contagem
    count_query_sql = f"SELECT COUNT(*) FROM {base_sql} {where_sql}"
    
    total_result = await sessiondb.execute(text(count_query_sql), params)
    total_items = total_result.scalar() or 0
    total_pages = math.ceil(total_items / per_page) if total_items > 0 else 1
    
    page = min(page, total_pages)
    
    # 5. Cálculo do offset e adição aos parâmetros
    offset = (page - 1) * per_page
    params["offset"] = offset
    params["limit"] = per_page

    # 6. Query de busca dos itens (com paginação)
    items_query_sql = f"""
        SELECT CPF,
    NOMECOMPLETO ,
    CLASSIFICACAO_CONTABIL ,
    empresa,
    null as CPF_APROVADOR, 
   
    NULL AS NOME_APROVADOR
      FROM {base_sql} {where_sql}
        ORDER BY A.NOMECOMPLETO
        OFFSET :offset ROWS FETCH NEXT :limit ROWS ONLY
    """
    #print(items_query_sql)
    items_result = await sessiondb.execute(text(items_query_sql), params)
    colaboradores_list = items_result.fetchall()
    # --- FIM DA LÓGICA ---

    return templates.TemplateResponse("cad_prestador.html", {
        "request": request,
        
        # Dados do usuário e UI
        "user_username": email,
        "username": username_display,
        "cards": cards,
        "empresa": "Grupo New",
        "menus": menus,
        "notifications": notifications,
        "notification_count": len(notifications),
        
        # Dados da paginação
        "colaboradores": colaboradores_list,
        "page": page,
        "total_pages": total_pages,
        "search_term": search_term 
    })
    

@router.get("/logout")
async def logout():
    response = RedirectResponse(url="/", status_code=302)
    response.delete_cookie("access_token", path="/")
    return response