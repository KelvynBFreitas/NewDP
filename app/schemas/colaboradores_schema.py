import re
from pydantic import BaseModel, constr, validator
from typing import Optional
# --- MODELO PYDANTIC para o POST do Modal ---
class PrestadorCreate(BaseModel):
    nomecompleto: Optional[str] = None
    cpf_prestador: str
    razao_social: str
    cnpj: Optional[str] = None
    classificacao_contabil: Optional[str] = None
    nome_aprovador: Optional[str] = None
    cpf_aprovador: Optional[str] = None

class PrestadorUpdate(BaseModel):
    id: int
    razao_social: str
    cnpj: Optional[str] = None
    nome_aprovador: Optional[str] = None
    cpf_aprovador: Optional[str] = None
    
    # O JavaScript também envia estes campos (mesmo sendo read-only),
    # então o modelo precisa recebê-los.
    cpf_prestador: Optional[str] = None
    nomecompleto: Optional[str] = None