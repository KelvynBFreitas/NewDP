
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
import asyncio
from typing import Optional # <<< NOVO IMPORT
from sqlalchemy.future import select
from sqlalchemy import func, or_, text,and_ # 'text' ainda é necessário para o Oracle
from app.models.app_dp_ajustes_valores_pj_postgres import AppDpAjustesValoresPj 
from app.schemas.dados_pj import PrestadorNotasUpdate
from app.models.user import User
from sqlalchemy.sql.expression import literal_column
from datetime import date, timedelta,datetime
from app.models.funcionarios_pj_postgres import app_dp_pj_aprovador_x_prestado
from fastapi.responses import JSONResponse
from fastapi import BackgroundTasks
# --- Modelos Pydantic ---
class FiltrosModel(BaseModel):
    search: Optional[str] = ""
    aprovador: Optional[str] = ""

class EnvioFinalRequest(BaseModel):
    ids: List[str] = []          # Pode vir vazio se enviar_tudo=True
    enviar_tudo: bool = False    # Nova flag
    filtros: Optional[FiltrosModel] = None
    data_emissao: str
    data_pagamento: str
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

@router.get("/api/dados_etapa1")
async def get_dados_etapa1(
    request: Request,
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1),
    search: str = Query(""),
    status: str = Query(""),
    kw: str = Query(None),
    session_postgres: AsyncSession = Depends(get_postgres_session),
    session_oracle: AsyncSession = Depends(get_oracle_session),
):
    """
    Busca dados de funcionários no Oracle (excluindo cadastrados) e concatena com Postgres.
    Faz o merge com a tabela de prestadores para trazer CNPJ e Razão Social.
    """
    # 1. Configuração de Datas e Filtros
    hoje = date.today()
    primeiro_dia_mes_atual = hoje.replace(day=1)
    ultimo_dia_mes_anterior = primeiro_dia_mes_atual - timedelta(days=1)
    
    search_term = search.strip()
    filtro_data_ref = AppDpAjustesValoresPj.datareferencia == ultimo_dia_mes_anterior

    # ==============================================================================
    # 🛠️ FUNÇÃO AUXILIAR: MERGE COM DADOS DO PRESTADOR (POSTGRES)
    # ==============================================================================
    async def enrich_with_prestador_data(lista_colaboradores: List[Dict[str, Any]]):
        """
        Recebe lista do Oracle, busca CNPJ/Razão na tabela app_dp_pj_aprovador_x_prestado
        e enriquece os dicionários.
        """
        if not lista_colaboradores:
            return

        # A. Coletar CPFs da página atual (limpa espaços e converte para string)
        cpfs_para_buscar = {
            str(row.get("cpf")).strip() 
            for row in lista_colaboradores 
            if row.get("cpf")
        }

        if not cpfs_para_buscar:
            return

        try:
            # B. Buscar no Postgres apenas os CPFs desta página
            stmt = select(
                app_dp_pj_aprovador_x_prestado.cpf_prestador,
                app_dp_pj_aprovador_x_prestado.cnpj,
                app_dp_pj_aprovador_x_prestado.razao_social
            ).where(
                app_dp_pj_aprovador_x_prestado.cpf_prestador.in_(cpfs_para_buscar)
            )

            result = await session_postgres.execute(stmt)
            prestadores = result.all()
           
            # C. Criar Mapa para acesso rápido: {'12345678900': {'cnpj': '...', 'razao': '...'}}
            mapa_prestadores = {
                str(p.cpf_prestador).strip(): {"cnpj": p.cnpj, "razao_social": p.razao_social}
                for p in prestadores
            }

            # D. Injetar os dados na lista original
            for colab in lista_colaboradores:
                cpf_key = str(colab.get("cpf")).strip()
                dados_extra = mapa_prestadores.get(cpf_key)
                
                if dados_extra:
                    colab["cnpj"] = dados_extra["cnpj"]
                    colab["razao_social"] = dados_extra["razao_social"]
                else:
                    colab["cnpj"] = None
                    colab["razao_social"] = None

        except Exception as e:
            print(f"Erro ao fazer merge com prestadores: {e}")
            # Fallback: garante as chaves nulas para não quebrar o front
            for colab in lista_colaboradores:
                colab.setdefault("cnpj", None)
                colab.setdefault("razao_social", None)

    # ==========================================================
    # LÓGICA DE FILTRO POR STATUS
    # ==========================================================

    # --- CASO A: STATUS 0 (JÁ AJUSTADOS / APENAS POSTGRES) ---
    if status == "0":
        try:
            count_stmt_ajustes = select(func.count()).select_from(AppDpAjustesValoresPj)
            conditions = [filtro_data_ref]

            if search_term:
                conditions.append(
                    (AppDpAjustesValoresPj.nome.ilike(f"%{search_term}%")) | 
                    (AppDpAjustesValoresPj.cpf.ilike(f"%{search_term}%"))
                )

            count_stmt_ajustes = count_stmt_ajustes.where(and_(*conditions))
            total_registros = await session_postgres.scalar(count_stmt_ajustes) or 0
            
            dados_combinados = []
            if total_registros > 0:
                offset = (page - 1) * limit
                
                stmt_ajustes = select(
                    AppDpAjustesValoresPj.cpf.label("cpf"),
                    AppDpAjustesValoresPj.nome.label("nome"),
                    AppDpAjustesValoresPj.cidade.label("cidade"),
                    AppDpAjustesValoresPj.centro_de_custo.label("centro"),
                    AppDpAjustesValoresPj.desconto_plano.label("planos"),
                    AppDpAjustesValoresPj.vr.label("vr"),
                    AppDpAjustesValoresPj.ressarcimento.label("ressarcimento"),
                    AppDpAjustesValoresPj.outros.label("outros"),
                    AppDpAjustesValoresPj.acao.label("acao_"),
                    AppDpAjustesValoresPj.resultado.label("resultado"),
                    AppDpAjustesValoresPj.motivo_tab.label("motivo"),
                    AppDpAjustesValoresPj.justificativa.label("justificativa"),
                    AppDpAjustesValoresPj.dataadmissao.label("dataadmissao"),
                    AppDpAjustesValoresPj.email_colaborador.label("email_colaborador"),
                    AppDpAjustesValoresPj.cnpj.label("cnpj"),
                    AppDpAjustesValoresPj.razao_social.label("razao_social"),
                    literal_column("0").label("status")
                    
                ).select_from(AppDpAjustesValoresPj)

                stmt_ajustes = stmt_ajustes.where(and_(*conditions))
                stmt_ajustes = stmt_ajustes.order_by(AppDpAjustesValoresPj.nome).offset(offset).limit(limit)
                
                result_ajustes = await session_postgres.execute(stmt_ajustes)
                dados_combinados = [dict(r) for r in result_ajustes.mappings().all()]
            
            return {"data": dados_combinados, "total": total_registros, "page": page, "limit": limit}
            
        except Exception as e:
            print(f"Erro Status 0: {e}")
            raise HTTPException(status_code=500, detail="Erro no banco Postgres")

    # --- CASO B: STATUS 1 (PENDENTES / ORACLE) ---
    elif status == "1":
        try:
            # 1. Buscar CPFs já cadastrados no Postgres (Exclusão)
            stmt_cadastrados = select(AppDpAjustesValoresPj.cpf).where(filtro_data_ref)
            result_cadastrados = await session_postgres.execute(stmt_cadastrados)
            cpfs_cadastrados = {str(cpf).strip() for cpf in result_cadastrados.scalars().all()} 

            # 2. Query Oracle
            if not QUERY_COLABORADORES: raise HTTPException(status_code=500, detail="Query vazia")
            
            base_sql = f"({QUERY_COLABORADORES}) A"
            params = {}
            search_like = f"%{search_term.upper()}%"
            where_parts = ["(UPPER(A.NOME) LIKE :search_like OR A.CPF LIKE :search_like)"]
            params["search_like"] = search_like

            if cpfs_cadastrados:
                cpfs_clean = [c for c in cpfs_cadastrados if c.isalnum()]
                if cpfs_clean:
                    # Formata lista para o NOT IN do SQL
                    cpfs_formatted = ", ".join([f"'{c}'" for c in cpfs_clean])
                    where_parts.append(f"A.CPF NOT IN ({cpfs_formatted})")
            
            where_sql = "WHERE " + " AND ".join(where_parts)

            # 3. Count Oracle
            count_sql = f"SELECT COUNT(*) FROM {base_sql} {where_sql}"
            total_registros = (await session_oracle.execute(text(count_sql), params)).scalar() or 0
            
            dados_combinados = []
            if total_registros > 0:
                offset = (page - 1) * limit
                params["offset_val"] = offset
                params["limit_val"] = limit
                
                query_sql = f"""
                    SELECT CPF, NOME, CIDADE, CENTRO, PLANOS, VR, RESSARCIMENTO, OUTROS, 
                           ACAO_, RESULTADO, DATAADMISSAO, EMAIL_COLABORADOR, MOTIVO, JUSTIFICATIVA,
                           1 AS STATUS 
                    FROM {base_sql} {where_sql}
                    ORDER BY A.NOME
                    OFFSET :offset_val ROWS FETCH NEXT :limit_val ROWS ONLY
                """
                
                oracle_result = await session_oracle.execute(text(query_sql), params)
                dados_combinados = [dict(r) for r in oracle_result.mappings().all()]

                # >>> AQUI: Injeta CNPJ e Razão Social <<<
                await enrich_with_prestador_data(dados_combinados)

            return {"data": dados_combinados, "total": total_registros, "page": page, "limit": limit}
            
        except Exception as e:
            print(f"Erro Status 1: {e}")
            raise HTTPException(status_code=500, detail="Erro no Oracle ou processamento")

    # --- CASO C: STATUS VAZIO (MISTO / TODOS) ---
    else:
        # 1. Preparar filtros e CPFs cadastrados
        cpfs_cadastrados = set()
        try:
            stmt_cadastrados = select(AppDpAjustesValoresPj.cpf).where(filtro_data_ref)
            result_cadastrados = await session_postgres.execute(stmt_cadastrados)
            cpfs_cadastrados = {str(cpf).strip() for cpf in result_cadastrados.scalars().all()} 
        except Exception as e:
            print(f"Erro CPFs cadastrados: {e}")
        
        # 2. Configurar Oracle Query
        if not QUERY_COLABORADORES: raise HTTPException(status_code=500, detail="Query vazia")
        base_sql = f"({QUERY_COLABORADORES}) A"
        params = {}
        search_like = f"%{search_term.upper()}%"
        where_parts = ["(UPPER(A.NOME) LIKE :search_like OR A.CPF LIKE :search_like)"]
        params["search_like"] = search_like

        if cpfs_cadastrados:
            cpfs_clean = [c for c in cpfs_cadastrados if c.isalnum()]
            if cpfs_clean:
                cpfs_formatted = ", ".join([f"'{c}'" for c in cpfs_clean])
                where_parts.append(f"A.CPF NOT IN ({cpfs_formatted})")

        where_sql = "WHERE " + " AND ".join(where_parts)

        # 3. Contagens (Oracle Pendentes + Postgres Ajustados)
        total_oracle_pendentes = 0
        try:
            count_sql = f"SELECT COUNT(*) FROM {base_sql} {where_sql}"
            total_oracle_pendentes = (await session_oracle.execute(text(count_sql), params)).scalar() or 0
        except Exception as e:
            print(f"Erro Count Oracle: {e}")

        total_postgres_ajustados = 0
        try:
            count_pg = select(func.count()).select_from(AppDpAjustesValoresPj).where(filtro_data_ref)
            if search_term:
                count_pg = count_pg.where(
                    (AppDpAjustesValoresPj.nome.ilike(f"%{search_term}%")) | 
                    (AppDpAjustesValoresPj.cpf.ilike(f"%{search_term}%"))
                )
            total_postgres_ajustados = await session_postgres.scalar(count_pg) or 0
        except Exception as e:
            print(f"Erro Count Postgres: {e}")

        total_registros_geral = total_oracle_pendentes + total_postgres_ajustados

        # 4. Busca e Paginação Unificada
        funcionarios_oracle = []
        ajustes_postgres = []
        start_index = (page - 1) * limit

        # 4.1 Busca Oracle
        if start_index < total_oracle_pendentes:
            offset_oracle = start_index
            limit_oracle = min(limit, total_oracle_pendentes - offset_oracle)
            
            if limit_oracle > 0:
                params["offset_val"] = offset_oracle
                params["limit_val"] = limit_oracle
                query_sql = f"""
                    SELECT CPF, NOME, CIDADE, CENTRO, PLANOS, VR, RESSARCIMENTO, OUTROS, 
                           ACAO_, RESULTADO, DATAADMISSAO, EMAIL_COLABORADOR, MOTIVO, JUSTIFICATIVA,
                           1 AS STATUS 
                    FROM {base_sql} {where_sql}
                    ORDER BY A.NOME
                    OFFSET :offset_val ROWS FETCH NEXT :limit_val ROWS ONLY
                """
                try:
                    oracle_result = await session_oracle.execute(text(query_sql), params)
                    funcionarios_oracle = [dict(r) for r in oracle_result.mappings().all()]
                    
                    # >>> AQUI: Injeta CNPJ e Razão Social no Oracle <<<
                    await enrich_with_prestador_data(funcionarios_oracle)

                except Exception as e:
                    print(f"Erro Fetch Oracle: {e}")

        # 4.2 Busca Postgres
        slots_restantes = limit - len(funcionarios_oracle)
        if slots_restantes > 0 and start_index < total_registros_geral:
            offset_postgres = 0
            if start_index >= total_oracle_pendentes:
                offset_postgres = start_index - total_oracle_pendentes
            
            limit_postgres = min(slots_restantes, total_postgres_ajustados - offset_postgres)

            if limit_postgres > 0:
                try:
                    stmt_pg = select(
                        AppDpAjustesValoresPj.cpf.label("cpf"),
                        AppDpAjustesValoresPj.nome.label("nome"),
                        AppDpAjustesValoresPj.cidade.label("cidade"),
                        AppDpAjustesValoresPj.centro_de_custo.label("centro"),
                        AppDpAjustesValoresPj.desconto_plano.label("planos"),
                        AppDpAjustesValoresPj.vr.label("vr"),
                        AppDpAjustesValoresPj.ressarcimento.label("ressarcimento"),
                        AppDpAjustesValoresPj.outros.label("outros"),
                        AppDpAjustesValoresPj.acao.label("acao_"),
                        AppDpAjustesValoresPj.resultado.label("resultado"),
                        AppDpAjustesValoresPj.motivo_tab.label("motivo"),
                        AppDpAjustesValoresPj.justificativa.label("justificativa"),
                        AppDpAjustesValoresPj.dataadmissao.label("dataadmissao"),
                        AppDpAjustesValoresPj.email_colaborador.label("email_colaborador"),
                        AppDpAjustesValoresPj.cnpj.label("cnpj"),
                        AppDpAjustesValoresPj.razao_social.label("razao_social"),
                        literal_column("0").label("status")
                    ).select_from(AppDpAjustesValoresPj).where(filtro_data_ref)
                    
                    if search_term:
                        stmt_pg = stmt_pg.where(
                            (AppDpAjustesValoresPj.nome.ilike(f"%{search_term}%")) | 
                            (AppDpAjustesValoresPj.cpf.ilike(f"%{search_term}%"))
                        )

                    stmt_pg = stmt_pg.order_by(AppDpAjustesValoresPj.nome).offset(offset_postgres).limit(limit_postgres)
                    result_pg = await session_postgres.execute(stmt_pg)
                    ajustes_postgres = [dict(r) for r in result_pg.mappings().all()]
                    
                except Exception as e:
                    print(f"Erro Fetch Postgres: {e}")

        # 5. Retorno
        dados_combinados = funcionarios_oracle + ajustes_postgres
        
        return {
            "data": dados_combinados,
            "total": total_registros_geral,
            "page": page,
            "limit": limit
        }


@router.get("/api/etapa_final")
async def get_etapa_final(
    request: Request,
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1),
    search: str = Query(""),
    status: str = Query(""),
    aprovador: str = "",
    kw: str = Query(None),
    session_postgres: AsyncSession = Depends(get_postgres_session),
    session_oracle: AsyncSession = Depends(get_oracle_session),
):
    """
    Busca dados filtrando corretamente pelo APROVADOR direto no banco de dados.
    """
    # 1. Configuração de Datas
    hoje = date.today()
    primeiro_dia_mes_atual = hoje.replace(day=1)
    ultimo_dia_mes_anterior = primeiro_dia_mes_atual - timedelta(days=1)
    
    search_term = search.strip()
    filtro_data_ref = AppDpAjustesValoresPj.datareferencia == ultimo_dia_mes_anterior

    # ==============================================================================
    # 🚀 CORREÇÃO CRÍTICA: PRÉ-CARREGAR CPFS DO APROVADOR
    # ==============================================================================
    # Se houver filtro de aprovador, buscamos QUAIS CPFs pertencem a ele antes de tudo.
    cpfs_do_aprovador_filtro = None
    
    if aprovador and aprovador.strip():
        aprovador_limpo = aprovador.strip()

        try:
            # Prepara o select base
            stmt_aprov = select(app_dp_pj_aprovador_x_prestado.cpf_prestador)

            # --- LÓGICA AJUSTADA ---
            if aprovador_limpo == "Sem Aprovador":
                # Se selecionou "Sem Aprovador", busca quem tem campo Nulo ou Vazio
                stmt_aprov = stmt_aprov.where(
                    or_(
                        app_dp_pj_aprovador_x_prestado.nome_aprovador.is_(None),
                        app_dp_pj_aprovador_x_prestado.nome_aprovador == ''
                    )
                )
            else:
                # Se tem nome, busca pelo nome exato
                stmt_aprov = stmt_aprov.where(
                    app_dp_pj_aprovador_x_prestado.nome_aprovador == aprovador_limpo
                )
            # -----------------------

            result_aprov = await session_postgres.execute(stmt_aprov)
            
            # Cria um SET de strings para busca rápida e remoção de duplicatas
            cpfs_do_aprovador_filtro = {str(c).strip() for c in result_aprov.scalars().all()}
            
            # Se filtrou (seja por nome ou por 'sem aprovador') e não achou ninguém, retorna vazio
            if not cpfs_do_aprovador_filtro:
                return {"data": [], "total": 0, "page": page, "limit": limit}
                
        except Exception as e:
            print(f"Erro ao buscar CPFs do aprovador: {e}")
            return {"data": [], "total": 0, "page": page, "limit": limit}

    # ==============================================================================
    # 🛠️ FUNÇÃO AUXILIAR: ENRICH (Mantida para preencher os dados visuais)
    # ==============================================================================
    async def enrich_with_prestador_data(lista_colaboradores: List[Dict[str, Any]]):
        if not lista_colaboradores: return

        cpfs_para_buscar = {str(row.get("cpf")).strip() for row in lista_colaboradores if row.get("cpf")}
        if not cpfs_para_buscar: return

        try:
            stmt = select(
                app_dp_pj_aprovador_x_prestado.cpf_prestador,
                app_dp_pj_aprovador_x_prestado.cnpj,
                app_dp_pj_aprovador_x_prestado.razao_social,
                app_dp_pj_aprovador_x_prestado.nome_aprovador
            ).where(app_dp_pj_aprovador_x_prestado.cpf_prestador.in_(cpfs_para_buscar))

            result = await session_postgres.execute(stmt)
            prestadores = result.all()
            
            mapa_prestadores = {
                str(p.cpf_prestador).strip(): {
                    "cnpj": p.cnpj, "razao_social": p.razao_social, "aprovador": p.nome_aprovador
                } for p in prestadores
            }

            for colab in lista_colaboradores:
                cpf_key = str(colab.get("cpf")).strip()
                dados = mapa_prestadores.get(cpf_key)
                if dados:
                    colab["cnpj"] = dados["cnpj"]
                    colab["razao_social"] = dados["razao_social"]
                    colab["aprovador"] = dados["aprovador"]
                else:
                    colab.setdefault("cnpj", None)
                    colab.setdefault("razao_social", None)
                    colab.setdefault("aprovador", None)
        except Exception as e:
            print(f"Erro enrich: {e}")

    # ==========================================================
    # LÓGICA DE FILTRO POR STATUS
    # ==========================================================

    # --- CASO A: STATUS 0 (JÁ AJUSTADOS / APENAS POSTGRES) ---
    if status == "0":
        try:
            # Montar condições base
            conditions = [filtro_data_ref]

            if search_term:
                conditions.append(
                    (AppDpAjustesValoresPj.nome.ilike(f"%{search_term}%")) | 
                    (AppDpAjustesValoresPj.cpf.ilike(f"%{search_term}%"))
                )
            
            # 🚀 APLICA O FILTRO DE APROVADOR AQUI
            if cpfs_do_aprovador_filtro:
                conditions.append(AppDpAjustesValoresPj.cpf.in_(cpfs_do_aprovador_filtro))

            # Query de Contagem
            count_stmt_ajustes = select(func.count()).select_from(AppDpAjustesValoresPj).where(and_(*conditions))
            total_registros = await session_postgres.scalar(count_stmt_ajustes) or 0
            
            dados_combinados = []
            if total_registros > 0:
                offset = (page - 1) * limit
                stmt_ajustes = select(
                    AppDpAjustesValoresPj.cpf.label("cpf"),
                    AppDpAjustesValoresPj.nome.label("nome"),
                    AppDpAjustesValoresPj.cidade.label("cidade"),
                    AppDpAjustesValoresPj.centro_de_custo.label("centro"),
                    AppDpAjustesValoresPj.desconto_plano.label("planos"),
                    AppDpAjustesValoresPj.vr.label("vr"),
                    AppDpAjustesValoresPj.ressarcimento.label("ressarcimento"),
                    AppDpAjustesValoresPj.outros.label("outros"),
                    AppDpAjustesValoresPj.acao.label("acao_"),
                    AppDpAjustesValoresPj.resultado.label("resultado"),
                    AppDpAjustesValoresPj.motivo_tab.label("motivo"),
                    AppDpAjustesValoresPj.justificativa.label("justificativa"),
                    AppDpAjustesValoresPj.dataadmissao.label("dataadmissao"),
                    AppDpAjustesValoresPj.email_colaborador.label("email_colaborador"),
                    AppDpAjustesValoresPj.cnpj.label("cnpj"),
                    AppDpAjustesValoresPj.razao_social.label("razao_social"),
                    AppDpAjustesValoresPj.status_envio.label("status_envio"),
                    literal_column("0").label("status")
                ).select_from(AppDpAjustesValoresPj).where(and_(*conditions))

                stmt_ajustes = stmt_ajustes.order_by(AppDpAjustesValoresPj.nome).offset(offset).limit(limit)
                result_ajustes = await session_postgres.execute(stmt_ajustes)
                dados_combinados = [dict(r) for r in result_ajustes.mappings().all()]

                await enrich_with_prestador_data(dados_combinados)
            
            return {"data": dados_combinados, "total": total_registros, "page": page, "limit": limit}
            
        except Exception as e:
            print(f"Erro Status 0: {e}")
            raise HTTPException(status_code=500, detail="Erro no banco Postgres")

    # --- CASO B: STATUS 1 (PENDENTES / ORACLE) ---
    elif status == "1":
        try:
            stmt_cadastrados = select(AppDpAjustesValoresPj.cpf).where(filtro_data_ref)
            result_cadastrados = await session_postgres.execute(stmt_cadastrados)
            cpfs_cadastrados = {str(cpf).strip() for cpf in result_cadastrados.scalars().all()} 

            if not QUERY_COLABORADORES: raise HTTPException(status_code=500, detail="Query vazia")
            
            base_sql = f"({QUERY_COLABORADORES}) A"
            params = {}
            search_like = f"%{search_term.upper()}%"
            where_parts = ["(UPPER(A.NOME) LIKE :search_like OR A.CPF LIKE :search_like)"]
            params["search_like"] = search_like

            if cpfs_cadastrados:
                cpfs_clean = [c for c in cpfs_cadastrados if c.isalnum()]
                if cpfs_clean:
                    cpfs_formatted = ", ".join([f"'{c}'" for c in cpfs_clean])
                    where_parts.append(f"A.CPF NOT IN ({cpfs_formatted})")
            
            # 🚀 APLICA O FILTRO DE APROVADOR AQUI (ORACLE)
            if cpfs_do_aprovador_filtro:
                # Oracle tem limite de 1000 itens no IN. Se for muito grande, precisaria de chunk.
                # Assumindo volume razoável por aprovador para este contexto.
                cpfs_aprov_list = [f"'{c}'" for c in cpfs_do_aprovador_filtro if c.isalnum()]
                if cpfs_aprov_list:
                    cpfs_aprov_formatted = ", ".join(cpfs_aprov_list)
                    where_parts.append(f"A.CPF IN ({cpfs_aprov_formatted})")
                else:
                    # Aprovador tem CPFs, mas nenhum alfanumérico válido? Bloqueia.
                    where_parts.append("1=0")

            where_sql = "WHERE " + " AND ".join(where_parts)

            count_sql = f"SELECT COUNT(*) FROM {base_sql} {where_sql}"
            total_registros = (await session_oracle.execute(text(count_sql), params)).scalar() or 0
            
            dados_combinados = []
            if total_registros > 0:
                offset = (page - 1) * limit
                params["offset_val"] = offset
                params["limit_val"] = limit
                
                query_sql = f"""
                    SELECT CPF, NOME, CIDADE, CENTRO, PLANOS, VR, RESSARCIMENTO, OUTROS, 
                           ACAO_, RESULTADO, DATAADMISSAO, EMAIL_COLABORADOR, MOTIVO, JUSTIFICATIVA,
                           1 AS STATUS , 0 STATUS_ENVIO
                    FROM {base_sql} {where_sql}
                    ORDER BY A.NOME
                    OFFSET :offset_val ROWS FETCH NEXT :limit_val ROWS ONLY
                """
                oracle_result = await session_oracle.execute(text(query_sql), params)
                dados_combinados = [dict(r) for r in oracle_result.mappings().all()]
                await enrich_with_prestador_data(dados_combinados)

            return {"data": dados_combinados, "total": total_registros, "page": page, "limit": limit}
            
        except Exception as e:
            print(f"Erro Status 1: {e}")
            raise HTTPException(status_code=500, detail="Erro no Oracle")

    # --- CASO C: MISTO (TODOS) ---
    else:
        # 1. Prepara CPFs cadastrados
        cpfs_cadastrados = set()
        try:
            stmt_cadastrados = select(AppDpAjustesValoresPj.cpf).where(filtro_data_ref)
            result_cadastrados = await session_postgres.execute(stmt_cadastrados)
            cpfs_cadastrados = {str(cpf).strip() for cpf in result_cadastrados.scalars().all()} 
        except Exception as e:
            print(f"Erro CPFs cadastrados: {e}")
        
        # 2. Configura Oracle (Com Filtro de Aprovador)
        if not QUERY_COLABORADORES: raise HTTPException(status_code=500, detail="Query vazia")
        base_sql = f"({QUERY_COLABORADORES}) A"
        params = {}
        search_like = f"%{search_term.upper()}%"
        where_parts = ["(UPPER(A.NOME) LIKE :search_like OR A.CPF LIKE :search_like)"]
        params["search_like"] = search_like

        if cpfs_cadastrados:
            cpfs_clean = [c for c in cpfs_cadastrados if c.isalnum()]
            if cpfs_clean:
                cpfs_formatted = ", ".join([f"'{c}'" for c in cpfs_clean])
                where_parts.append(f"A.CPF NOT IN ({cpfs_formatted})")

        # 🚀 APLICA FILTRO APROVADOR (ORACLE MISTO)
        if cpfs_do_aprovador_filtro:
            cpfs_aprov_list = [f"'{c}'" for c in cpfs_do_aprovador_filtro if c.isalnum()]
            if cpfs_aprov_list:
                cpfs_aprov_formatted = ", ".join(cpfs_aprov_list)
                where_parts.append(f"A.CPF IN ({cpfs_aprov_formatted})")
            else:
                where_parts.append("1=0")

        where_sql = "WHERE " + " AND ".join(where_parts)

        # 3. Contagens
        total_oracle_pendentes = 0
        try:
            count_sql = f"SELECT COUNT(*) FROM {base_sql} {where_sql}"
            total_oracle_pendentes = (await session_oracle.execute(text(count_sql), params)).scalar() or 0
        except Exception as e:
            print(f"Erro Count Oracle: {e}")

        total_postgres_ajustados = 0
        try:
            count_pg = select(func.count()).select_from(AppDpAjustesValoresPj).where(filtro_data_ref)
            if search_term:
                count_pg = count_pg.where(
                    (AppDpAjustesValoresPj.nome.ilike(f"%{search_term}%")) | 
                    (AppDpAjustesValoresPj.cpf.ilike(f"%{search_term}%"))
                )
            # 🚀 APLICA FILTRO APROVADOR (POSTGRES MISTO)
            if cpfs_do_aprovador_filtro:
                count_pg = count_pg.where(AppDpAjustesValoresPj.cpf.in_(cpfs_do_aprovador_filtro))

            total_postgres_ajustados = await session_postgres.scalar(count_pg) or 0
        except Exception as e:
            print(f"Erro Count Postgres: {e}")

        total_registros_geral = total_oracle_pendentes + total_postgres_ajustados

        # 4. Busca Unificada
        funcionarios_oracle = []
        ajustes_postgres = []
        start_index = (page - 1) * limit

        # 4.1 Fetch Oracle
        if start_index < total_oracle_pendentes:
            offset_oracle = start_index
            limit_oracle = min(limit, total_oracle_pendentes - offset_oracle)
            
            if limit_oracle > 0:
                params["offset_val"] = offset_oracle
                params["limit_val"] = limit_oracle
                query_sql = f"""
                    SELECT CPF, NOME, CIDADE, CENTRO, PLANOS, VR, RESSARCIMENTO, OUTROS, 
                           ACAO_, RESULTADO, DATAADMISSAO, EMAIL_COLABORADOR, MOTIVO, JUSTIFICATIVA,
                           1 AS STATUS, 0 STATUS_ENVIO
                    FROM {base_sql} {where_sql}
                    ORDER BY A.NOME
                    OFFSET :offset_val ROWS FETCH NEXT :limit_val ROWS ONLY
                """
                try:
                    oracle_result = await session_oracle.execute(text(query_sql), params)
                    funcionarios_oracle = [dict(r) for r in oracle_result.mappings().all()]
                    await enrich_with_prestador_data(funcionarios_oracle)
                except Exception as e:
                    print(f"Erro Fetch Oracle: {e}")

        # 4.2 Fetch Postgres
        slots_restantes = limit - len(funcionarios_oracle)
        # Ajuste offset para Postgres
        # Se o start_index já passou do total do Oracle, o offset é (start_index - total_oracle)
        # Se estamos pegando uma parte do Oracle e uma parte do PG, o offset do PG é 0
        offset_postgres = max(0, start_index - total_oracle_pendentes)
        
        if slots_restantes > 0 and offset_postgres < total_postgres_ajustados:
            limit_postgres = min(slots_restantes, total_postgres_ajustados - offset_postgres)

            if limit_postgres > 0:
                try:
                    stmt_pg = select(
                        AppDpAjustesValoresPj.cpf.label("cpf"),
                        AppDpAjustesValoresPj.nome.label("nome"),
                        AppDpAjustesValoresPj.cidade.label("cidade"),
                        AppDpAjustesValoresPj.centro_de_custo.label("centro"),
                        AppDpAjustesValoresPj.desconto_plano.label("planos"),
                        AppDpAjustesValoresPj.vr.label("vr"),
                        AppDpAjustesValoresPj.ressarcimento.label("ressarcimento"),
                        AppDpAjustesValoresPj.outros.label("outros"),
                        AppDpAjustesValoresPj.acao.label("acao_"),
                        AppDpAjustesValoresPj.resultado.label("resultado"),
                        AppDpAjustesValoresPj.motivo_tab.label("motivo"),
                        AppDpAjustesValoresPj.justificativa.label("justificativa"),
                        AppDpAjustesValoresPj.dataadmissao.label("dataadmissao"),
                        AppDpAjustesValoresPj.email_colaborador.label("email_colaborador"),
                        AppDpAjustesValoresPj.cnpj.label("cnpj"),
                        AppDpAjustesValoresPj.razao_social.label("razao_social"),
                        AppDpAjustesValoresPj.status_envio.label("status_envio"),
                        literal_column("0").label("status")
                    ).select_from(AppDpAjustesValoresPj).where(filtro_data_ref)
                    
                    if search_term:
                        stmt_pg = stmt_pg.where(
                            (AppDpAjustesValoresPj.nome.ilike(f"%{search_term}%")) | 
                            (AppDpAjustesValoresPj.cpf.ilike(f"%{search_term}%"))
                        )

                    # 🚀 APLICA FILTRO APROVADOR (POSTGRES MISTO FETCH)
                    if cpfs_do_aprovador_filtro:
                         stmt_pg = stmt_pg.where(AppDpAjustesValoresPj.cpf.in_(cpfs_do_aprovador_filtro))

                    stmt_pg = stmt_pg.order_by(AppDpAjustesValoresPj.nome).offset(offset_postgres).limit(limit_postgres)
                    result_pg = await session_postgres.execute(stmt_pg)
                    ajustes_postgres = [dict(r) for r in result_pg.mappings().all()]
                    await enrich_with_prestador_data(ajustes_postgres)
                    
                except Exception as e:
                    print(f"Erro Fetch Postgres: {e}")

        dados_combinados = funcionarios_oracle + ajustes_postgres
        
        return {
            "data": dados_combinados,
            "total": total_registros_geral,
            "page": page,
            "limit": limit
        }


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
    hoje = date.today()
    primeiro_dia_mes_atual = hoje.replace(day=1)
    ultimo_dia_mes_anterior = primeiro_dia_mes_atual - timedelta(days=1)
    if etapa == 1:
        pass  # Lógica específica da etapa 1, se necessário
    result = await session.execute(
        select(AppDpAjustesValoresPj).where(
            (AppDpAjustesValoresPj.cpf == item.cpf) & 
            (AppDpAjustesValoresPj.datareferencia == ultimo_dia_mes_anterior)
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
        #Pegar o último dia do mês anterior
        
        novo_registro = AppDpAjustesValoresPj(
            cpf=item.cpf,
            nome=item.nome,
            cidade=item.cidade,
            centro_de_custo=item.centro,
            desconto_plano=item.planos,
            vr=item.vr,
            resultado=item.resultado,
            motivo_tab=item.motivo,
            datareferencia= ultimo_dia_mes_anterior,
            data_ajuste=datetime.now(),
            ultima_alteracao=username,
            acao=item.acao_,
            dataadmissao=item.dataadmissao,
            email_colaborador=item.email_colaborador,
            outros=item.outros,
            justificativa=item.justificativa,
            ressarcimento=item.ressarcimento,
            cnpj=item.cnpj,
            razao_social=item.razao_social
        )
        session.add(novo_registro)
        await session.commit()
        return {"status": "success", "message": "Registro cadastrado com sucesso."}
    
@router.post("/api/enviar_final")
async def post_enviar_final(
    payload: EnvioFinalRequest,
    background_tasks: BackgroundTasks, # <--- INJEÇÃO DA BACKGROUND TASK
    session_postgres: AsyncSession = Depends(get_postgres_session),
    session_oracle: AsyncSession = Depends(get_oracle_session)
):
    try:
        # ==========================================================================
        # 1. RESOLUÇÃO DOS CPFS (Global ou Manual)
        # ==========================================================================
        cpfs_selecionados = []

        # CASO A: Selecionar Tudo (Busca no banco baseada nos filtros)
        if payload.enviar_tudo:
            # Configura datas para filtrar a query
            hoje = date.today()
            primeiro_dia_mes_atual = hoje.replace(day=1)
            ultimo_dia_mes_anterior = primeiro_dia_mes_atual - timedelta(days=1)
            filtro_data_ref = AppDpAjustesValoresPj.datareferencia == ultimo_dia_mes_anterior

            # Recupera filtros
            search_term = payload.filtros.search.strip() if payload.filtros and payload.filtros.search else ""
            filtro_aprovador = payload.filtros.aprovador.strip() if payload.filtros and payload.filtros.aprovador else ""

            # A.1 Filtro de Aprovador
            cpfs_aprovador = set()
            if filtro_aprovador:
                stmt_aprov = select(app_dp_pj_aprovador_x_prestado.cpf_prestador).where(
                    app_dp_pj_aprovador_x_prestado.nome_aprovador == filtro_aprovador
                )
                res_aprov = await session_postgres.execute(stmt_aprov)
                cpfs_aprovador = {str(c).strip() for c in res_aprov.scalars().all()}
                if not cpfs_aprovador:
                    return JSONResponse(content={"message": "Nenhum item para este aprovador"}, status_code=400)

            # A.2 Busca Postgres (Status 0)
            conditions = [filtro_data_ref]
            if search_term:
                conditions.append((AppDpAjustesValoresPj.nome.ilike(f"%{search_term}%")) | (AppDpAjustesValoresPj.cpf.ilike(f"%{search_term}%")))
            if cpfs_aprovador:
                conditions.append(AppDpAjustesValoresPj.cpf.in_(cpfs_aprovador))

            stmt_pg_ids = select(AppDpAjustesValoresPj.cpf).where(and_(*conditions))
            res_pg_ids = await session_postgres.execute(stmt_pg_ids)
            ids_pg = [str(c).strip() for c in res_pg_ids.scalars().all()]

            # A.3 Busca Oracle (Status 1)
            # Excluir quem já está no PG
            stmt_cad = select(AppDpAjustesValoresPj.cpf).where(filtro_data_ref)
            res_cad = await session_postgres.execute(stmt_cad)
            cpfs_ignorar = {str(c).strip() for c in res_cad.scalars().all()}

            base_sql = f"({QUERY_COLABORADORES}) A"
            where_parts = []
            params = {}
            if search_term:
                params["search_like"] = f"%{search_term.upper()}%"
                where_parts.append("(UPPER(A.NOME) LIKE :search_like OR A.CPF LIKE :search_like)")
            if cpfs_ignorar:
                clean = [c for c in cpfs_ignorar if c.isalnum()]
                if clean: where_parts.append(f"A.CPF NOT IN ({', '.join([f"'{c}'" for c in clean])})")
            if cpfs_aprovador:
                clean_aprov = [c for c in cpfs_aprovador if c.isalnum()]
                if clean_aprov: where_parts.append(f"A.CPF IN ({', '.join([f"'{c}'" for c in clean_aprov])})")
                else: where_parts.append("1=0")

            where_sql = "WHERE " + " AND ".join(where_parts) if where_parts else ""
            sql_oracle = f"SELECT CPF FROM {base_sql} {where_sql}"
            try:
                res_ora = await session_oracle.execute(text(sql_oracle), params)
                ids_oracle = [str(row.cpf).strip() for row in res_ora.all()]
            except:
                ids_oracle = []

            cpfs_selecionados = list(set(ids_pg + ids_oracle))

        # CASO B: Seleção Manual
        else:
            cpfs_selecionados = [cpf.strip() for cpf in payload.ids]

        # Validação Final
        if not cpfs_selecionados:
            return JSONResponse(content={"message": "Nenhum item selecionado"}, status_code=400)

        # ==========================================================================
        # 2. SUA LÓGICA ORIGINAL (Processamento)
        # ==========================================================================
        
        # Conversão de Datas
        try:
            dt_emissao = datetime.strptime(payload.data_emissao, "%Y-%m-%d").date()
            dt_pagamento = datetime.strptime(payload.data_pagamento, "%Y-%m-%d").date()
        except ValueError:
            return JSONResponse(content={"detail": "Formato de data inválido"}, status_code=400)

        processed_count = 0
        
        # Datas de referência para o update/insert
        hoje = date.today()
        primeiro_dia_mes_atual = hoje.replace(day=1)
        ultimo_dia_mes_anterior = primeiro_dia_mes_atual - timedelta(days=1)

        # --- Função Enrich (Mantida igual) ---
        async def enrich_with_prestador_data(lista_colaboradores: List[Dict[str, Any]]):
            if not lista_colaboradores: return
            cpfs_para_buscar = {str(row.get("cpf")).strip() for row in lista_colaboradores if row.get("cpf")}
            if not cpfs_para_buscar: return

            try:
                stmt = select(
                    app_dp_pj_aprovador_x_prestado.cpf_prestador,
                    app_dp_pj_aprovador_x_prestado.cnpj,
                    app_dp_pj_aprovador_x_prestado.razao_social,
                    app_dp_pj_aprovador_x_prestado.nome_aprovador
                ).where(app_dp_pj_aprovador_x_prestado.cpf_prestador.in_(cpfs_para_buscar))

                result = await session_postgres.execute(stmt)
                prestadores = result.all()
                
                mapa_prestadores = {
                    str(p.cpf_prestador).strip(): {
                        "cnpj": p.cnpj, "razao_social": p.razao_social, "aprovador": p.nome_aprovador
                    } for p in prestadores
                }

                for colab in lista_colaboradores:
                    cpf_key = str(colab.get("cpf")).strip()
                    dados_extra = mapa_prestadores.get(cpf_key)
                    if dados_extra:
                        colab["cnpj"] = dados_extra["cnpj"]
                        colab["razao_social"] = dados_extra["razao_social"]
                        colab["aprovador"] = dados_extra["aprovador"]
                    else:
                        colab.setdefault("cnpj", None)
                        colab.setdefault("razao_social", None)
                        colab.setdefault("aprovador", None)
            except Exception as e:
                print(f"Erro enrich: {e}")
                for colab in lista_colaboradores:
                    colab.setdefault("cnpj", None)
                    colab.setdefault("razao_social", None)
                    colab.setdefault("aprovador", None)

        # --- Lógica Principal de Upsert ---

        # 1. Buscar dados já existentes no Postgres (Histórico/Editados)
        #    Agora usamos chunking para evitar estouro no IN clause se a lista for enorme
        registros_existentes = []
        chunk_size = 1000
        for i in range(0, len(cpfs_selecionados), chunk_size):
            chunk = cpfs_selecionados[i:i + chunk_size]
            stmt_pg = select(AppDpAjustesValoresPj).where(AppDpAjustesValoresPj.cpf.in_(chunk))
            result_pg = await session_postgres.execute(stmt_pg)
            registros_existentes.extend(result_pg.scalars().all())
        
        mapa_postgres = {r.cpf: r for r in registros_existentes}
        cpfs_encontrados_pg = set(mapa_postgres.keys())
        
        # 2. Identificar Novos (Só existem no Oracle)
        cpfs_pendentes_oracle = list(set(cpfs_selecionados) - cpfs_encontrados_pg)
        
        dados_novos_oracle = []
        if cpfs_pendentes_oracle:
            # Chunking para Query Oracle também
            for i in range(0, len(cpfs_pendentes_oracle), chunk_size):
                chunk = cpfs_pendentes_oracle[i:i + chunk_size]
                cpfs_sql = ", ".join([f"'{c}'" for c in chunk])
                
                query_oracle = f"""
                    SELECT CPF, NOME, CIDADE, CENTRO, PLANOS, VR, RESSARCIMENTO, OUTROS, 
                           ACAO_, RESULTADO, DATAADMISSAO, EMAIL_COLABORADOR, MOTIVO, JUSTIFICATIVA
                    FROM ({QUERY_COLABORADORES}) A
                    WHERE A.CPF IN ({cpfs_sql})
                """
                res_oracle = await session_oracle.execute(text(query_oracle))
                dados_novos_oracle.extend([dict(r) for r in res_oracle.mappings().all()])

            if dados_novos_oracle:
                await enrich_with_prestador_data(dados_novos_oracle)

        # 3. Processamento (Upsert)
        
        # A. UPDATE: Atualizar os existentes
        for cpf, registro in mapa_postgres.items():
            registro.data_emissao_nota = dt_emissao
            registro.data_pagamento = dt_pagamento
            registro.status_envio = 1 
            processed_count += 1

        # B. INSERT: Inserir os novos (Enriquecidos)
        for row in dados_novos_oracle:
            novo_registro = AppDpAjustesValoresPj(
                cpf=str(row.get("cpf")).strip(),
                nome=row.get("nome"),
                cidade=row.get("cidade"),
                centro_de_custo=row.get("centro"),
                cnpj=row.get("cnpj"),                
                razao_social=row.get("razao_social"), 
                # aprovador=row.get("aprovador"), # Descomente se tiver coluna no modelo
                desconto_plano=row.get("planos") or 0.0,
                vr=row.get("vr") or 0.0,
                ressarcimento=row.get("ressarcimento") or 0.0,
                outros=row.get("outros") or 0.0,
                acao=row.get("acao_"),
                resultado=row.get("resultado") or 0.0,
                motivo_tab=row.get("motivo"),
                justificativa=row.get("justificativa"),
                dataadmissao=row.get("dataadmissao"),
                email_colaborador=row.get("email_colaborador"),
                data_emissao_nota=dt_emissao,
                data_pagamento=dt_pagamento,
                datareferencia=ultimo_dia_mes_anterior,
                status_envio=1 
            )
            session_postgres.add(novo_registro)
            processed_count += 1

        await session_postgres.commit()
        # ==========================================================================
        # 3. INICIA TAREFA DE ENVIO DE E-MAILS EM BACKGROUND
        await simular_envio_email_sincrono(cpfs_selecionados)
        return {
            "message": "Dados processados e envio de e-mails.",
            "recebidos": processed_count
        }

    except Exception as e:
        await session_postgres.rollback()
        print(f"Erro no envio final: {e}")
        raise HTTPException(status_code=500, detail=f"Erro interno: {str(e)}")

@router.get("/api/lista_aprovadores")
async def get_lista_aprovadores(
    session_postgres: AsyncSession = Depends(get_postgres_session)
):
    """
    Retorna a lista de todos os aprovadores + opção 'Sem Aprovador'.
    """
    try:
        # Busca nomes distintos e ordena alfabeticamente
        # Mantemos o filtro != None para não vir 'None' do banco,
        # pois vamos inserir nossa própria string personalizada.
        stmt = select(app_dp_pj_aprovador_x_prestado.nome_aprovador)\
            .where(app_dp_pj_aprovador_x_prestado.nome_aprovador != None)\
            .distinct()\
            .order_by(app_dp_pj_aprovador_x_prestado.nome_aprovador)
        
        result = await session_postgres.execute(stmt)
        
        # Cria a lista com os resultados do banco
        lista = [row for row in result.scalars().all() if row]
        
        # --- ADIÇÃO AQUI ---
        # Insere "Sem Aprovador" na primeira posição (índice 0)
        lista.insert(0, "Sem Aprovador")
        
        return lista
        
    except Exception as e:
        print(f"Erro ao buscar lista de aprovadores: {e}")
        return ["Sem Aprovador"] # Retorna pelo menos essa opção em caso de erro, se fizer sentido
    
# async def simular_envio_email_background(cpfs: List[str]):
#     """
#     Simula o envio de e-mail assíncrono. 
#     Na vida real, aqui entraria a conexão SMTP.
#     """
#     print(f"--- INICIANDO ENVIO EM LOTE DE {len(cpfs)} E-MAILS ---")
#     total = len(cpfs)
#     for index, cpf in enumerate(cpfs):
#         # Simula um delay de envio (ex: 0.5s por email)
#         await asyncio.sleep(5) 
#         print(f"[{index + 1}/{total}] Enviando e-mail simulado para CPF: {cpf}...")
#         await asyncio.sleep(5) 

#     print("--- ENVIO EM LOTE FINALIZADO ---")

async def simular_envio_email_sincrono(cpfs: List[str]):
    """
    Simula o envio travando a resposta até terminar.
    """
    print(f"--- INICIANDO ENVIO DE {len(cpfs)} E-MAILS ---")
    for index, cpf in enumerate(cpfs):
        # Tempo de espera simulado por e-mail (0.5 segundos)
        # Se tiver 10 itens, vai demorar 5 segundos na tela do usuário
        await asyncio.sleep(0.5) 
        print(f"[{index + 1}/{len(cpfs)}] Enviando e-mail simulado para CPF: {cpf}...")
    print("--- ENVIO FINALIZADO ---")