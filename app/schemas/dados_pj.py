import re
from pydantic import BaseModel, constr, validator
from typing import Optional
from datetime import date, datetime
# --- MODELO PYDANTIC para o POST do Modal ---
# class dados(BaseModel):
#     nomecompleto: Optional[str] = None
#     cpf_prestador: str
#     razao_social: str
#     cnpj: Optional[str] = None
#     classificacao_contabil: Optional[str] = None
#     nome_aprovador: Optional[str] = None
#     cpf_aprovador: Optional[str] = None

class PrestadorNotasUpdate(BaseModel):
    id: Optional[int] = None
    cpf: str
    nome: Optional[str] = None
    cidade: Optional[str] = None
    centro: Optional[str] = None
    
    # O JavaScript também envia estes campos (mesmo sendo read-only),
    # então o modelo precisa recebê-los.
    planos: Optional[float] = None
    vr: Optional[float] = None
    resultado: Optional[float] = None
    motivo: Optional[str] = None
    datareferencia: Optional[datetime] = None
    data_ajuste:  Optional[datetime] = None
    ultima_alteracao: Optional[str] = None
    acao_: Optional[str] = None
    dataadmissao:  Optional[datetime] = None
    email_colaborador: Optional[str] = None
    outros: Optional[float] = None
    justificativa: Optional[str] = None
    ressarcimento: Optional[float] = None


    