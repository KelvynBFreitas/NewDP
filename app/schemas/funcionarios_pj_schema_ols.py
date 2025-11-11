from pydantic import BaseModel
from datetime import date
from typing import Optional

class ColaboradorInfo(BaseModel):
    """
    Este é o seu "model" de resposta (Schema Pydantic).
    Ele define o formato do JSON que sua API vai retornar.
    Os nomes dos atributos aqui devem ser IDÊNTICOS (maiúsculas/minúsculas)
    aos nomes das colunas retornadas pela sua query SQL.
    """
    
    nomecompleto: str
    cpf: str
    unidade: str
    empresa: str
    salariocontratual: Optional[float] = None
    setor: str
    funcao: str
    estabelecimento: str
    estabelecimentocontrata: str
    classificacao_contabil: str
    dataadmissao: str
    email_colaborador: Optional[str] = None

    # Configuração para permitir que o Pydantic leia
    # os resultados do SQLAlchemy (objetos Row) diretamente
    class Config:
        orm_mode = True