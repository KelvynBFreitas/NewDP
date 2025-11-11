
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import List, Dict, Any
from fastapi import APIRouter, Request, Form, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_postgres_session,get_oracle_session
from app.core.config import SECRET_KEY
import pathlib
from typing import Optional # <<< NOVO IMPORT
from sqlalchemy.future import select
from sqlalchemy import func, or_, text # 'text' ainda é necessário para o Oracle
from app.models.funcionarios_pj_postgres import app_dp_pj_aprovador_x_prestado 
from app.models.user import User
# --- Modelos de Dados (Inalterados) ---
class ItemUpdate(BaseModel):
    id: int
    nome: str
    email: str

class FinalSubmission(BaseModel):
    ids: List[int]

# --- Configuração da Aplicação ---
router = APIRouter()
templates = Jinja2Templates(directory="app/templates")
# --- BLOCO DE LEITURA DO ARQUIVO (Sem alterações) ---
BASE_DIR = pathlib.Path(__file__).resolve().parent.parent
SQL_QUERY_FILE = BASE_DIR / "queries" / "pj_calculado.sql"
QUERY_COLABORADORES = ""
try:
    with open(SQL_QUERY_FILE, "r", encoding="utf-8") as f:
        QUERY_COLABORADORES = f.read()
except FileNotFoundError:
    print(f"ERRO CRÍTICO: Arquivo de query não encontrado em {SQL_QUERY_FILE}")

# --- Banco de Dados Falso (Inalterado) ---
db: Dict[str, Dict[int, Dict[str, Any]]] = {
    "etapa1": {
        1: {"cpf": '01415482152', "nome": "Alda Cristina Carvalho Rufino", "Cidade": "Fortaleza","Centro_Custo":"Vendas Corporativo","Descontos":0.0, "Ressarcimento":0.0, "Vale_Refeicao": 448.36,"outros":0.0, "Acao":"Adicionar na Nota >>>", "resultado": 448.36,"motivo":""},
        2: {"cpf": '61946966304', "nome": "Alice Lucas Da Rocha Oliveira", "Cidade": "Fortaleza","Centro_Custo":"Sala CRM","Descontos":0.0, "Ressarcimento":0.0, "Vale_Refeicao": 448.36,"outros":0.0, "Acao":"Adicionar na Nota >>>", "resultado": 448.36,"motivo":""},

       
    },
    "etapa2": {
        101: {"id": 101, "nome": "Produto X", "email": "Em estoque"},
        102: {"id": 102, "nome": "Produto Y", "email": "Esgotado"},
    },
    "etapa_final": {
        201: {"id": 201, "nome": "Item de Aprovação Alfa", "email": ""},
        202: {"id": 202, "nome": "Item de Aprovação Beta", "email": ""},
        203: {"id": 203, "nome": "Item de Aprovação Gama", "email": ""},
    }
}


@router.get("/pjemail", response_class=HTMLResponse)
async def get_homepage(
                       request: Request,
                        session: AsyncSession = Depends(get_postgres_session),):
    """
    Serve o "casulo" HTML. O Vue.js fará o resto.
    Note que não passamos 'filteredEtapa1', pois isso
    é controlado pelo Vue (client-side), não pelo Jinja2 (server-side).
    """
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
    return templates.TemplateResponse("pj_email.html", {
        'request': request,
         "user_username": email,
        "username": username_display,
        "cards": cards,
        "empresa": "Grupo New",
        "menus": menus,
        "notifications": notifications,
    })

# --- Endpoints de API (Inalterados) ---

@router.get("/api/dados_etapa1")
async def get_dados_etapa1(request: Request,
                           session_postgres: AsyncSession = Depends(get_postgres_session),
                            session_oracle: AsyncSession = Depends(get_oracle_session),
                            
                            ):
    search = "a"
    # 1. Validação e Token
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="Não autorizado")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    except JWTError:
        raise HTTPException(status_code=401, detail="Token inválido")

    # if not search or len(search) < 3:
    #     return []

    # 2. Buscar TODOS os CPFs já cadastrados no Postgres
    try:
        stmt_cadastrados = select(app_dp_pj_aprovador_x_prestado.cpf_prestador)
        result_cadastrados = await session_postgres.execute(stmt_cadastrados)
        cpfs_cadastrados = set(result_cadastrados.scalars().all())
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
            UPPER(A.NOME) LIKE :search_like OR
            A.CPF LIKE :search_like
        )
    """
    params["search_like"] = search_like
    
    query_sql = f"""
        SELECT CPF, NOME,CIDADE, CENTRO, PLANOS,VR, RESSARCIMENTO, OUTROS, ACAO_, RESULTADO
        FROM {base_sql}
        {where_sql}
        ORDER BY A.NOME
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
        if func["cpf"]  in cpfs_cadastrados:
            funcionarios_filtrados.append(func)


    return {"data": funcionarios_filtrados}

@router.get("/api/dados_etapa2")
async def get_dados_etapa2(request: Request,):
    token = request.cookies.get("access_token")
    if not token:
        return RedirectResponse(url="/", status_code=302)
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        username = payload.get("sub")
        
    except JWTError:
        return RedirectResponse(url="/", status_code=302)
    return {"data": list(db["etapa2"].values())}

@router.get("/api/dados_etapa_final")
async def get_dados_etapa_final():
    return {"data": list(db["etapa_final"].values())}

@router.get("/api/item/{item_id}")
async def get_item(item_id: int, etapa: int = 1):
    db_key = "etapa1" if etapa == 1 else "etapa2"
    item = db[db_key].get(item_id)
    if item:
        return item
    return {"status": "error", "message": "Item não encontrado"}

@router.put("/api/item/{item_id}")
async def update_item(item_id: int, item: ItemUpdate, etapa: int = 1):
    db_key = "etapa1" if etapa == 1 else "etapa2"
    if item_id in db[db_key]:
        db[db_key][item_id] = item.model_dump()
        print(f"[LOG] Etapa {etapa} atualizada: {db[db_key][item_id]}")
        return {"status": "success", "item": db[db_key][item_id]}
    return {"status": "error", "message": "Item não encontrado"}

@router.post("/api/enviar_final")
async def post_final_submission(submission: FinalSubmission):
    print(f"[LOG] IDs recebidos para envio final: {submission.ids}")
    return {
        "status": "recebido",
        "recebidos": len(submission.ids),
        "ids": submission.ids
    }