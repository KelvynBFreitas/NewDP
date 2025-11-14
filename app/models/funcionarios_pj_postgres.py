
from sqlalchemy import Column, Integer, String, Boolean
from app.core.database import Base

class app_dp_pj_aprovador_x_prestado(Base):
 
    __tablename__ = "app_dp_pj_aprovador_x_prestador" 
    
    id = Column(Integer, primary_key=True, index=True)
    cpf_aprovador = Column(String, unique=True, index=True)
    nomecompleto = Column(String, unique=True, index=True)
    nome_aprovador = Column(String, unique=True, index=True)
    classificacao_contabil = Column(String)
    cpf_prestador = Column(String, unique=True, index=True)
    cnpj = Column(String)
    razao_social = Column(String,)

