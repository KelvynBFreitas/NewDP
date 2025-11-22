# Imports existentes
from fastapi import APIRouter, Request, Form, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse # JSONResponse adicionado
from fastapi.templating import Jinja2Templates
from jose import JWTError, jwt
import os
import math
import pathlib
from typing import Optional
from pydantic import BaseModel # <<< ADICIONADO
from sqlalchemy.future import select
from sqlalchemy import func, or_, text # 'text' ainda é necessário para o Oracle
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_oracle_session, get_postgres_session
from app.core.config import SECRET_KEY
from app.schemas.colaboradores_schema import PrestadorCreate, PrestadorUpdate

# Importe seus modelos
from app.models.user import User
from app.models.funcionarios_pj_postgres import app_dp_pj_aprovador_x_prestado
from app.models.aprovadores import app_dp_pj_aprovador 

# from app.models.funcionarios_pj import ColaboradorInfo

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

# --- BLOCO DE LEITURA DO ARQUIVO (Sem alterações) ---
BASE_DIR = pathlib.Path(__file__).resolve().parent.parent
SQL_QUERY_FILE = BASE_DIR / "queries" / "colaboradores.sql"
QUERY_COLABORADORES = ""
try:
    with open(SQL_QUERY_FILE, "r", encoding="utf-8") as f:
        QUERY_COLABORADORES = f.read()
except FileNotFoundError:
    print(f"ERRO CRÍTICO: Arquivo de query não encontrado em {SQL_QUERY_FILE}")
# --- FIM DO BLOCO DE LEITURA ---



@router.get("/prestadoresdeservico", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    session: AsyncSession = Depends(get_postgres_session),
    # sessiondb é removido daqui pois não é mais usado na renderização da página principal
    # Mas será usado nos endpoints da API
    page: int = Query(1, ge=1),
    per_page: int = Query(7, ge=1, le=100),
    search: Optional[str] = Query(None)
):
    
    # --- Verificação se a query foi carregada (ainda necessária para o modal) ---
    if not QUERY_COLABORADORES:
        raise HTTPException(status_code=500, 
                            detail="Erro interno: A query SQL principal não foi carregada.")

    # ... (Token, Cards, Menus, Notificações, Lógica de Usuário - Sem alterações) ...
    token = request.cookies.get("access_token")
    if not token:
        return RedirectResponse(url="/", status_code=302)
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        username = payload.get("sub")
    except JWTError:
        return RedirectResponse(url="/", status_code=302)

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
            {"title": "E-Mail PJ", "url": "/pjemail"},
        ]}
    ]
    
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
    
    # --- LÓGICA DA TABELA PRINCIPAL (POSTGRES) ---
    
    # 1. Define as queries base
    base_query = select(app_dp_pj_aprovador_x_prestado)
    count_query = select(func.count(app_dp_pj_aprovador_x_prestado.id))
    
    search_term = search.strip() if search else None
    
    # 2. Adiciona o filtro de busca, se existir
    if search_term:
        like_term = f"%{search_term}%"
        # Assumindo os nomes das colunas no Postgres
        search_filter = or_(
            app_dp_pj_aprovador_x_prestado.nomecompleto.ilike(like_term),
            app_dp_pj_aprovador_x_prestado.cpf_prestador.ilike(like_term),
            app_dp_pj_aprovador_x_prestado.razao_social.ilike(like_term),
            app_dp_pj_aprovador_x_prestado.cnpj.ilike(like_term),
            app_dp_pj_aprovador_x_prestado.nome_aprovador.ilike(like_term),
            app_dp_pj_aprovador_x_prestado.cpf_aprovador.ilike(like_term)
        )
        base_query = base_query.where(search_filter)
        count_query = count_query.where(search_filter)

    # 3. Conta o total de itens (com o filtro aplicado)
    total_result = await session.execute(count_query)
    total_items = total_result.scalar() or 0
    total_pages = math.ceil(total_items / per_page) if total_items > 0 else 1
    
    page = min(page, total_pages)
    
    # 4. Cálculo do offset
    offset = (page - 1) * per_page

    # 5. Busca os itens paginados
    items_query = base_query.order_by(app_dp_pj_aprovador_x_prestado.razao_social).offset(offset).limit(per_page)
    items_result = await session.execute(items_query)
    colaboradores_list = items_result.scalars().all()
    # --- FIM DA LÓGICA POSTGRES ---

    # --- O BLOCO DE LÓGICA ORACLE (linhas 135-188 do seu código) FOI REMOVIDO ---

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
        
        # Dados da paginação (AGORA VINDOS DO POSTGRES)
        "colaboradores": colaboradores_list,
        "page": page,
        "total_pages": total_pages,
        "search_term": search_term 
    })

# ===========================================
# === NOVOS ENDPOINTS PARA O MODAL
# ===========================================

@router.get("/api/search-funcionarios")
async def search_funcionarios(
    request: Request,
    session_postgres: AsyncSession = Depends(get_postgres_session),
    session_oracle: AsyncSession = Depends(get_oracle_session),
    search: Optional[str] = Query(None)
):
    # 1. Validação e Token
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="Não autorizado")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    except JWTError:
        raise HTTPException(status_code=401, detail="Token inválido")

    if not search or len(search) < 3:
        return []

    # 2. Buscar TODOS os CPFs já cadastrados no Postgres
    try:
        stmt_cadastrados = select(app_dp_pj_aprovador_x_prestado.cpf_prestador)
        result_cadastrados = await session_postgres.execute(stmt_cadastrados)
        cpfs_cadastrados = set(result_cadastrados.scalars().all())
        print(f"CPFs já cadastrados: {cpfs_cadastrados}")
    except Exception as e:
        print(f"Erro ao buscar CPFs no Postgres: {e}")
        raise HTTPException(status_code=500, detail="Erro ao verificar CPFs existentes.")

    # 3. Buscar no Oracle (usando a QUERY_COLABORADORES)
    if not QUERY_COLABORADORES:
        raise HTTPException(status_code=500, detail="Query de colaboradores não carregada")

    base_sql = f"({QUERY_COLABORADORES}) A"
    params = {}
    
    search_like = f"%{search.strip().upper()}%"
    where_sql = """
        WHERE (
            UPPER(A.NOMECOMPLETO) LIKE :search_like OR
            A.CPF LIKE :search_like
        )
    """
    params["search_like"] = search_like
    
    query_sql = f"""
        SELECT CPF, NOMECOMPLETO, CLASSIFICACAO_CONTABIL, EMPRESA
        FROM {base_sql}
        {where_sql}
        ORDER BY A.NOMECOMPLETO
        FETCH NEXT 50 ROWS ONLY
    """ # Limita a 50 resultados para performance
    
    try:
        oracle_result = await session_oracle.execute(text(query_sql), params)
        funcionarios_oracle = oracle_result.mappings().all() # Retorna como dict
    except Exception as e:
        print(f"Erro na query Oracle: {e}")
        raise HTTPException(status_code=500, detail="Erro ao consultar banco de dados de funcionários")

    # 4. Filtrar resultados (excluir CPFs já cadastrados)
    funcionarios_filtrados = []
    for func in funcionarios_oracle:
        if func["cpf"] not in cpfs_cadastrados:
            funcionarios_filtrados.append(func)
            
    return funcionarios_filtrados


@router.post("/api/add-prestador")
async def add_prestador(
    request: Request,
    prestador_data: PrestadorCreate,
    session_postgres: AsyncSession = Depends(get_postgres_session)
):
    # 1. Validação e Token
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="Não autorizado")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    except JWTError:
        raise HTTPException(status_code=401, detail="Token inválido")

    # 2. Verificar se já existe
    stmt_exists = select(app_dp_pj_aprovador_x_prestado).where(
        app_dp_pj_aprovador_x_prestado.cpf_prestador == prestador_data.cpf_prestador
    )
    result_exists = await session_postgres.execute(stmt_exists)
    if result_exists.scalar_one_or_none() is not None:
        raise HTTPException(status_code=400, detail="Este CPF de prestador já está cadastrado.")

    # 3. Criar e Salvar
    try:
        # Assumindo que seu model Postgres tem estas colunas
        novo_prestador = app_dp_pj_aprovador_x_prestado(
            nomecompleto =prestador_data.nomecompleto,
            cpf_prestador=prestador_data.cpf_prestador,
            razao_social=prestador_data.razao_social,
            cnpj=prestador_data.cnpj,
            classificacao_contabil=prestador_data.classificacao_contabil,
            nome_aprovador=prestador_data.nome_aprovador,
            cpf_aprovador=prestador_data.cpf_aprovador
        )
        
        session_postgres.add(novo_prestador)
        await session_postgres.commit()
        await session_postgres.refresh(novo_prestador)
        
        return JSONResponse(content={"message": "Prestador adicionado com sucesso!", "id": novo_prestador.id}, status_code=201)

    except Exception as e:
        await session_postgres.rollback()
        print(f"Erro ao salvar: {e}")
        raise HTTPException(status_code=500, detail=f"Erro interno ao salvar no banco de dados: {e}")
# ... (depois do endpoint /api/search-funcionarios)

@router.get("/api/search-aprovadores")
async def search_aprovadores(
    request: Request,
    session_postgres: AsyncSession = Depends(get_postgres_session),
    search: Optional[str] = Query(None)
):
    """
    Busca por NOMES ou CPFs de APROVADORES distintos na tabela
    principal do Postgres (app_dp_pj_aprovador).
    """
    
    # 1. Validação e Token
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="Não autorizado")
    try:
        jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    except JWTError:
        raise HTTPException(status_code=401, detail="Token inválido")

    if not search or len(search) < 3:
        return []

    # 2. Buscar no Postgres (na tabela principal, buscando aprovadores distintos)
    try:
        search_like = f"%{search.strip().upper()}%"
        
        # Filtro de busca
        search_filter = or_(
            app_dp_pj_aprovador.nome.ilike(search_like),
            app_dp_pj_aprovador.cpf.ilike(search_like)
        )
        
        # Seleciona distintamente e filtra nulos/vazios
        stmt = select(
            app_dp_pj_aprovador.nome, 
            app_dp_pj_aprovador.cpf
        ).where(
            search_filter,
            app_dp_pj_aprovador.nome.isnot(None),
            app_dp_pj_aprovador.nome != ''
        ).distinct().limit(20) # Limita a 20 resultados
        
        result = await session_postgres.execute(stmt)
        
        # Converte o resultado (que é uma tupla) em um dicionário
        aprovadores_list = [
            {"nome_aprovador": nome, "cpf_aprovador": cpf} 
            for nome, cpf in result.all()
        ]
        
        return aprovadores_list
        
    except Exception as e:
        print(f"Erro ao buscar aprovadores no Postgres: {e}")
        raise HTTPException(status_code=500, detail="Erro ao consultar banco de dados de aprovadores.")


# ... (depois da rota /api/search-aprovadores)

# ===========================================
# === ROTA DE ATUALIZAÇÃO CORRIGIDA (PARA JSON)
# ===========================================
@router.post("/api/update-prestador")
async def update_prestador_api(
    request: Request,
    payload: PrestadorUpdate, # <<< MUDANÇA 1: Recebe o Pydantic Model (JSON)
    session: AsyncSession = Depends(get_postgres_session)
):
    # 1. Validação e Token
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="Não autorizado")
    try:
        jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    except JWTError:
        raise HTTPException(status_code=401, detail="Token inválido")

    try:
        # 2. Busca o colaborador pelo ID
        result = await session.execute(
            select(app_dp_pj_aprovador_x_prestado).where(app_dp_pj_aprovador_x_prestado.id == payload.id)
        )
        colaborador = result.scalar()
        
        if not colaborador:
            raise HTTPException(status_code=404, detail="Colaborador não encontrado.")
        
        # 3. Atualiza os campos com os dados do payload
        colaborador.razao_social = payload.razao_social
        colaborador.cnpj = payload.cnpj
        colaborador.nome_aprovador = payload.nome_aprovador
        colaborador.cpf_aprovador = payload.cpf_aprovador
        
        # A lógica original também atualizava estes campos.
        # Como o JS os envia (mesmo sendo read-only), mantemos a lógica.
        colaborador.cpf_prestador = payload.cpf_prestador 
        colaborador.nomecompleto = payload.nomecompleto
        
        # Nota: 'classificacao_contabil' não está no formulário de alteração,
        # por isso não é atualizado aqui.

        await session.commit()
        await session.refresh(colaborador)
        
        # 4. Retorna JSONResponse, como o JavaScript espera
        return JSONResponse(content={"message": "Prestador atualizado com sucesso!", "id": colaborador.id}, status_code=200)

    except Exception as e:
        await session.rollback()
        print(f"Erro ao atualizar via API: {e}")
        raise HTTPException(status_code=500, detail=f"Erro interno ao atualizar no banco de dados: {e}")


# ===========================================
# === ROTA DE LOGOUT (Sem alterações)
# ===========================================
@router.get("/logout")
async def logout():
    response = RedirectResponse(url="/", status_code=302)
    response.delete_cookie("access_token", path="/")
    return response

@router.get("/logout")
async def logout():
    response = RedirectResponse(url="/", status_code=302)
    response.delete_cookie("access_token", path="/")
    return response