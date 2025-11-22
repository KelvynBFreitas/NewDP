from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from jose import JWTError, jwt
from sqlalchemy import select, and_, or_, func
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime

# Seus imports de configuração e banco
from app.core.database import get_postgres_session
from app.core.config import SECRET_KEY
from app.models.user import User
from app.models.funcionarios_pj_postgres import app_dp_pj_aprovador_x_prestado
from app.models.app_dp_ajustes_valores_pj_postgres import AppDpAjustesValoresPj

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

# --- FUNÇÃO HELPER DE FORMATAÇÃO (Opcional, pois o Vue fará isso no front) ---
def format_currency(value):
    if value is None or value == "":
        return "R$ 0,00"
    try:
        val = float(value)
        return f"R$ {val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (ValueError, TypeError):
        return str(value)

templates.env.filters["formatCurrency"] = format_currency

@router.get("/relatoriopj", response_class=HTMLResponse)
async def get_homepage(request: Request, session: AsyncSession = Depends(get_postgres_session)):
    token = request.cookies.get("access_token")
    if not token:
        return RedirectResponse(url="/", status_code=302)
    
    username_display = ""
    email = ""

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        username = payload.get("sub")
        
        # Busca dados do usuário apenas se o token for válido
        result_user = await session.execute(select(User).where(User.username == username))
        user = result_user.scalar()
        
        if user:
            email = user.email
            nomes = user.username.title().split()
            username_display = f"{nomes[0]} {nomes[-1]}" if len(nomes) >= 2 else user.username.title()

    except JWTError:
        return RedirectResponse(url="/", status_code=302)

    # Menus e Cards (Simplificado para o exemplo)
    
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
             {"title": "Relatorios PJ", "url": "/relatoriopj"},
        ]}
    ]
    
    return templates.TemplateResponse("relatorioPJ.html", {
        'request': request,
        "user_username": email,
        "username": username_display,
        "menus": menus,
        # Placeholders não são estritamente necessários se o Vue carrega tudo,
        # mas evitam erro se você tentar renderizar algo via Jinja
    })

@router.get("/api/relatorio")
async def get_relatorio_pj(
    data_inicio: str,
    data_fim: str,
    search: str = "",
    session_postgres: AsyncSession = Depends(get_postgres_session)
):
    try:
        # Conversão de strings para datas
        dt_ini = datetime.strptime(data_inicio, "%Y-%m-%d").date()
        dt_fim = datetime.strptime(data_fim, "%Y-%m-%d").date()

        # Query
        stmt = (
            select(
                AppDpAjustesValoresPj.cpf.label("cpf_prestador"),
                AppDpAjustesValoresPj.nome,
                AppDpAjustesValoresPj.razao_social,
                AppDpAjustesValoresPj.cidade,
                AppDpAjustesValoresPj.centro_de_custo.label("classificacao_contabil"),
                AppDpAjustesValoresPj.desconto_plano.label("planos"),
                AppDpAjustesValoresPj.vr,
                AppDpAjustesValoresPj.ressarcimento,
                AppDpAjustesValoresPj.outros,
                AppDpAjustesValoresPj.acao,
                AppDpAjustesValoresPj.resultado.label("total"),
                AppDpAjustesValoresPj.datareferencia.label("data_referencia"),
                app_dp_pj_aprovador_x_prestado.nome_aprovador.label("aprovador")
            )
            .outerjoin(
                app_dp_pj_aprovador_x_prestado, 
                AppDpAjustesValoresPj.cpf == app_dp_pj_aprovador_x_prestado.cpf_prestador
            )
            .where(
                and_(
                    AppDpAjustesValoresPj.datareferencia >= dt_ini,
                    AppDpAjustesValoresPj.datareferencia <= dt_fim
                )
            )
            .order_by(AppDpAjustesValoresPj.nome)
        )

        if search:
            term = f"%{search.upper()}%"
            stmt = stmt.where(
                or_(
                    AppDpAjustesValoresPj.nome.ilike(term),
                    AppDpAjustesValoresPj.cpf.ilike(term),
                    AppDpAjustesValoresPj.razao_social.ilike(term)
                )
            )

        result = await session_postgres.execute(stmt)
        # .mappings().all() converte corretamente as linhas do SQLAlchemy em dicts baseados nos labels
        dados = [dict(row) for row in result.mappings().all()]

        # Totais calculados no Python
        total_valor = sum((d['total'] or 0) for d in dados)
        total_plano = sum((d['planos'] or 0) for d in dados)
        total_vr = sum((d['vr'] or 0) for d in dados)
        total_ressarcimento = sum((d['ressarcimento'] or 0) for d in dados)
        total_outros = sum((d['outros'] or 0) for d in dados)
        total_registros = len(dados)

        return {
            "data": dados,
            "resumo": {
                "total_valor": total_valor,
                "total_plano": total_plano,
                "total_vr":total_vr,
                "total_ressarcimento":total_ressarcimento,
                "total_outros":total_outros,
                "total_registros": total_registros
            }
        }

    except Exception as e:
        print(f"Erro no relatório: {e}")
        raise HTTPException(status_code=500, detail=str(e))