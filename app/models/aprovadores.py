from sqlalchemy import Column, Integer, String, Boolean
from app.core.database import Base

class app_dp_pj_aprovador(Base):
    __tablename__ = "app_dp_pj_aprovadores"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    cpf = Column(String)
    situacao = Column(Boolean, default=True)
