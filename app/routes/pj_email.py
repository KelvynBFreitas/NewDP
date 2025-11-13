
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
from app.models.app_dp_ajustes_valores_pj_postgres import AppDpAjustesValoresPj 
from app.schemas.dados_pj import PrestadorNotasUpdate
from app.models.user import User
from datetime  import datetime,date
from sqlalchemy.sql.expression import literal_column
# --- Modelos de Dados (Inalterados) ---


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


# Defina a variável global SECRET_KEY, QUERY_COLABORADORES, get_postgres_session, get_oracle_session e AppDpAjustesValoresPj
# Exemplo (se não estiverem em outro arquivo):
# router = APIRouter()
# SECRET_KEY = "sua_chave_secreta"
# QUERY_COLABORADORES = "SELECT * FROM colaboradores_oracle"
# class AppDpAjustesValoresPj: ... # Seu modelo
# async def get_postgres_session(): ...
# async def get_oracle_session(): ...

@router.get("/api/dados_etapa1")
async def get_dados_etapa1(
    request: Request,
    page: int = Query(1, ge=1),      # Recebe a página da URL (padrão 1)
    limit: int = Query(10, ge=1),    # Recebe o limite por página (padrão 10)
    search: str = Query(""),         # Recebe a busca da URL
    # Mantemos o 'kw' para satisfazer dependências internas obrigatórias (se aplicável)
    kw: str = Query(None), 
    session_postgres: AsyncSession = Depends(get_postgres_session), 
    session_oracle: AsyncSession = Depends(get_oracle_session),   
):
    """
    Busca dados de funcionários no Oracle (excluindo cadastrados) com paginação,
    e concatena com os dados já ajustados do Postgres, com contagem total unificada.
    """
    # 1. Validação e Token (Mantido)
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="Não autorizado")
    try:
        # Lembre-se de usar sua SECRET_KEY real
        jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    except JWTError:
        raise HTTPException(status_code=401, detail="Token inválido")

    # 2. Buscar CPFs já cadastrados no Postgres
    cpfs_cadastrados = set()
    try:
        stmt_cadastrados = select(AppDpAjustesValoresPj.cpf) 
        result_cadastrados = await session_postgres.execute(stmt_cadastrados)
        # Garante que CPF seja string e removido espaços
        cpfs_cadastrados = {str(cpf).strip() for cpf in result_cadastrados.scalars().all()} 
    except Exception as e:
        print(f"Erro Postgres ao buscar CPFs cadastrados: {e}")
    
    # 3. Montar Query Oracle Dinâmica (para dados pendentes)
    if not QUERY_COLABORADORES:
        raise HTTPException(status_code=500, detail="Query não carregada")

    base_sql = f"({QUERY_COLABORADORES}) A"
    params = {}
    
    # Filtro de Busca
    search_like = f"%{search.strip().upper()}%"
    where_parts = ["(UPPER(A.NOME) LIKE :search_like OR A.CPF LIKE :search_like)"]
    params["search_like"] = search_like

    # Filtro de Exclusão (NOT IN)
    if cpfs_cadastrados:
        # Apenas CPFs alfanuméricos para evitar injeção e erro de sintaxe
        cpfs_formatted = ", ".join([f"'{c}'" for c in cpfs_cadastrados if c.isalnum()]) 
        if cpfs_formatted:
            where_parts.append(f"A.CPF NOT IN ({cpfs_formatted})")

    where_sql = "WHERE " + " AND ".join(where_parts)

    # 4. Contagens e Total Geral (Mantido)
    
    # 4. Contagem do Oracle (PENDENTES)
    count_sql = f"SELECT COUNT(*) FROM {base_sql} {where_sql}"
    total_oracle_pendentes = 0
    try:
        count_result = await session_oracle.execute(text(count_sql), params)
        total_oracle_pendentes = count_result.scalar() or 0
    except Exception as e:
        print(f"Erro Count Oracle: {e}")


    # 4.5. Contagem do Postgres (AJUSTADOS)
    total_postgres_ajustados = 0
    try:
        count_stmt_ajustes = select(func.count()).select_from(AppDpAjustesValoresPj)
        
        search_term = search.strip()
        if search_term:
            count_stmt_ajustes = count_stmt_ajustes.where(
                (AppDpAjustesValoresPj.nome.ilike(f"%{search_term}%")) | 
                (AppDpAjustesValoresPj.cpf.ilike(f"%{search_term}%"))
            )
        
        total_postgres_ajustados = await session_postgres.scalar(count_stmt_ajustes) or 0
          
    except Exception as e:
        print(f"Erro Count Postgres: {e}")
        total_postgres_ajustados = 0

    # 4.6. Cálculo do Total Geral (Para a Paginação do Frontend)
    total_registros_geral = total_oracle_pendentes + total_postgres_ajustados


    # 5. Lógica de Busca e Paginação Unificada
    funcionarios_oracle = []
    ajustes_postgres = []
    
    # Índice onde a página atual começa no dataset combinado
    start_index = (page - 1) * limit

    # --- 5.1 Busca no Oracle (Bloco 1: Registros Pendentes) ---
    # Só busca no Oracle se a página começar antes do total de pendentes
    if start_index < total_oracle_pendentes:
        
        # Calcula o OFFSET e LIMIT para o Oracle
        offset_oracle = start_index
        # O limite é o menor entre o 'limit' da página e quantos registros restam no Oracle
        limit_oracle = min(limit, total_oracle_pendentes - offset_oracle) 
        
        if limit_oracle > 0:
            query_sql = f"""
                SELECT 
                    CPF, NOME, CIDADE, CENTRO, PLANOS, VR, RESSARCIMENTO, OUTROS, 
                    ACAO_, RESULTADO, DATAADMISSAO, EMAIL_COLABORADOR, MOTIVO, JUSTIFICATIVA,
                    1 AS STATUS 
                FROM {base_sql}
                {where_sql}
                ORDER BY A.NOME
                OFFSET :offset_val ROWS FETCH NEXT :limit_val ROWS ONLY
            """
            params["offset_val"] = offset_oracle
            params["limit_val"] = limit_oracle

            try:
                oracle_result = await session_oracle.execute(text(query_sql), params)
                # Converte para dict() para garantir modificabilidade (embora não mais necessário para o status)
                funcionarios_oracle = [dict(r) for r in oracle_result.mappings().all()] 
            except Exception as e:
                print(f"Erro Query Oracle: {e}")
                raise HTTPException(status_code=500, detail="Erro no banco Oracle")


    # --- 5.2 Busca no Postgres (Bloco 2: Registros Ajustados) ---

    # Calcula quantos slots (registros) faltam para completar a página
    slots_restantes = limit - len(funcionarios_oracle)
    
    # Se há slots restantes E a página não está além do total geral
    if slots_restantes > 0 and start_index < total_registros_geral:
        
        # O bloco do Postgres começa no índice 'total_oracle_pendentes'.
        offset_postgres = 0

        # Se a página atual está totalmente dentro ou começou no bloco do Postgres (ex: P6, P7...)
        if start_index >= total_oracle_pendentes:
            # Calcula o OFFSET do Postgres relativo ao total de registros ajustados
            offset_postgres = start_index - total_oracle_pendentes
        
        # O limite real a buscar no Postgres é o menor entre slots_restantes e o que resta no Postgres
        limit_postgres = min(slots_restantes, total_postgres_ajustados - offset_postgres)

        if limit_postgres > 0:
            try:
                # Seleciona as colunas do modelo Postgres, garantindo nomes em MAIÚSCULO
                stmt_ajustes = select(
                    AppDpAjustesValoresPj.cpf.label("cpf"),
                    AppDpAjustesValoresPj.nome.label("nome"),
                    AppDpAjustesValoresPj.cidade.label("cidade"),
                    AppDpAjustesValoresPj.centro_de_custo.label("centro"),
                    AppDpAjustesValoresPj.desconto_plano.label("planos"),
                    AppDpAjustesValoresPj.vr.label("vr"),
                    AppDpAjustesValoresPj.ressarcimento.label("ressarcimento"),
                    AppDpAjustesValoresPj.outros.label("outros"),
                    # Assumindo que 'acao_anterior' é o campo que mapeia para 'ACAO_'
                    AppDpAjustesValoresPj.acao.label("acao_"),
                    AppDpAjustesValoresPj.resultado.label("resultado"),
                    AppDpAjustesValoresPj.motivo_tab.label("motivo"),
                    AppDpAjustesValoresPj.justificativa.label("justificativa"),
                    AppDpAjustesValoresPj.dataadmissao.label("dataadmissao"),
                    AppDpAjustesValoresPj.email_colaborador.label("email_colaborador"),
                    # 🟢 BOLA VERDE PARA POSTGRES (AJUSTADOS)
                    literal_column("0").label("status")
                )
                
                # Aplica o filtro de busca ('search')
                search_term = search.strip()
                if search_term:
                    stmt_ajustes = stmt_ajustes.where(
                        (AppDpAjustesValoresPj.nome.ilike(f"%{search_term}%")) | 
                        (AppDpAjustesValoresPj.cpf.ilike(f"%{search_term}%"))
                    )
                
                # Aplica OFFSET e LIMIT para buscar o bloco exato de registros ajustados
                stmt_ajustes = stmt_ajustes.order_by(AppDpAjustesValoresPj.nome).offset(offset_postgres).limit(limit_postgres)
        
                result_ajustes = await session_postgres.execute(stmt_ajustes)
                # Converte para dict() para garantir compatibilidade e modificabilidade (se precisar)
                ajustes_postgres = [dict(r) for r in result_ajustes.mappings().all()]
                
            except Exception as e:
                print(f"Erro ao buscar ajustes Postgres: {e}")
                ajustes_postgres = [] 

    
    # 6. CONCATENAR os resultados
    dados_combinados = funcionarios_oracle + ajustes_postgres
    dados_combinados.sort(key=lambda item: item.get('NOME', '').upper())

    # Retorna estrutura pronta para o Frontend
    return {
        "data": dados_combinados,
        # NOVO TOTAL: Total geral (Oracle Pendentes + Postgres Ajustados)
        "total": total_registros_geral, 
        "page": page,
        "limit": limit
    }
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
async def get_item(item_id: str, etapa: int = 1):
    db_key = "etapa1" if etapa == 1 else "etapa2"
    item = db[db_key].get(item_id)
    if item:
        return item
    return {"status": "error", "message": "Item não encontrado"}

@router.put("/api/item/{item_id}")
async def update_item(item_id: str,
                      item: PrestadorNotasUpdate,
                      request: Request, # <-- MOVIDO PARA CIMA (obrigatório)
                      etapa: int = 1,
                      session: AsyncSession = Depends(get_postgres_session)):
    token = request.cookies.get("access_token")
    if not token:
        return RedirectResponse(url="/", status_code=302)
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        username = payload.get("sub")
        
    except JWTError:
        return RedirectResponse(url="/", status_code=302)
    result = await session.execute(
        select(AppDpAjustesValoresPj).where(
            (AppDpAjustesValoresPj.cpf == item.cpf )            
        )
    )
    atualiza_registro = result.scalar()
    if atualiza_registro:
        
        atualiza_registro.cpf=item.cpf
        atualiza_registro.nome=item.nome
        atualiza_registro.cidade=item.cidade
        atualiza_registro.centro_de_custo=item.centro
        atualiza_registro.desconto_plano=item.planos
        atualiza_registro.vr=item.vr
        atualiza_registro.resultado=item.resultado
        atualiza_registro.motivo_tab=item.motivo
        #datareferencia= date.today(),
        atualiza_registro.data_ajuste=datetime.now()
        atualiza_registro.ultima_alteracao=username
        atualiza_registro.acao=item.acao_
        atualiza_registro.dataadmissao=item.dataadmissao
        atualiza_registro.email_colaborador=item.email_colaborador
        atualiza_registro.outros=item.outros
        atualiza_registro.justificativa=item.justificativa
        atualiza_registro.ressarcimento=item.ressarcimento
        
        await session.commit()
        print(f"[LOG] Registro já existe para CPF {item.cpf} e Data Referência {item.datareferencia}.")
        return {"status": "error", "message": "Atualização efetuada com sucesso."}
    else:
        novo_registro = AppDpAjustesValoresPj(
            cpf=item.cpf,
            nome=item.nome,
            cidade=item.cidade,
            centro_de_custo=item.centro,
            desconto_plano=item.planos,
            vr=item.vr,
            resultado=item.resultado,
            motivo_tab=item.motivo,
            datareferencia= date.today(),
            data_ajuste=datetime.now(),
            ultima_alteracao=username,
            acao=item.acao_,
            dataadmissao=item.dataadmissao,
            email_colaborador=item.email_colaborador,
            outros=item.outros,
            justificativa=item.justificativa,
            ressarcimento=item.ressarcimento
        )
        session.add(novo_registro)
        await session.commit()
        return {"status": "success", "message": "Registro cadastrado com sucesso."}
    #
    # db_key = "etapa1" if etapa == 1 else "etapa2"
    # if item_id in db[db_key]:
    #     db[db_key][item_id] = item.model_dump()
    #     print(f"[LOG] Etapa {etapa} atualizada: {db[db_key][item_id]}")
    print(item.cpf)
    print(item.nome)
    print(item.cidade)
    if item:
        #print(f"[LOG] Etapa 1 atualizada: {item}")
        return {"status": "success", "item": item_id}
    return {"status": "error", "message": "Item não encontrado"}

@router.post("/api/enviar_final")
async def post_final_submission(submission: FinalSubmission):
    print(f"[LOG] IDs recebidos para envio final: {submission.ids}")
    return {
        "status": "recebido",
        "recebidos": len(submission.ids),
        "ids": submission.ids
    }