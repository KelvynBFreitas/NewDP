from sqlalchemy import Column, Integer, String, Float, Boolean, Date,DateTime
from app.core.database import Base

class AppDpAjustesValoresPj(Base):
    __tablename__ = "app_dp_ajustes_valores_pj"

    id = Column(Integer, primary_key=True, index=True)
    cpf = Column(String, index=True)
    nome = Column(String)
    cidade = Column(String)
    centro_de_custo = Column(String)
    desconto_plano = Column(Float)
    vr = Column(Float)
    resultado = Column(Float)
    motivo_tab = Column(String)
    datareferencia = Column(Date,index=True)
    data_ajuste = Column(DateTime)
    ultima_alteracao = Column(String)
    acao = Column(String)
    dataadmissao = Column(Date)
    email_colaborador = Column(String)
    outros = Column(Float)
    justificativa = Column(String)
    ressarcimento = Column(Float)
    cnpj = Column(String)
    razao_social = Column(String,)
    data_emissao_nota = Column(Date)
    data_pagamento = Column(Date)
    status_envio = Column(Integer, index=True)
