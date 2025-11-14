
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
from sqlalchemy import func, or_, text,and_ # 'text' ainda é necessário para o Oracle
from app.models.app_dp_ajustes_valores_pj_postgres import AppDpAjustesValoresPj 
from app.schemas.dados_pj import PrestadorNotasUpdate
from app.models.user import User
from datetime  import datetime,date
from sqlalchemy.sql.expression import literal_column
from datetime import date, timedelta
from app.models.funcionarios_pj_postgres import app_dp_pj_aprovador_x_prestado
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
async def post_final_submission(submission: FinalSubmission):
    print(f"[LOG] IDs recebidos para envio final: {submission.ids}")
    return {
        "status": "recebido",
        "recebidos": len(submission.ids),
        "ids": submission.ids
    }