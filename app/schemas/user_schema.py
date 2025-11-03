import re
from pydantic import BaseModel, constr, validator

class UserCreate(BaseModel):
    username: constr(min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9]+$")
    password: constr(min_length=8)
    perfil: str
    ativo: bool

    @validator("password")
    def strong_password(cls, v):
        errors = []
        if not re.search(r"[A-Z]", v):
            errors.append("uma letra maiúscula")
        if not re.search(r"[a-z]", v):
            errors.append("uma letra minúscula")
        if not re.search(r"\d", v):
            errors.append("um número")
        if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", v):
            errors.append("um símbolo especial (!@#$%^&*(),.?\":{}|<>)")
        if errors:
            raise ValueError(f"A senha deve conter pelo menos: {', '.join(errors)}.")
        return v
    
    # O validador 'block_common_sql_patterns' foi removido 
    # pois o regex no 'constr' de 'username' já faz esse trabalho.

    class Config:
        orm_mode = True

# --- E O MODELO DE LOGIN CORRIGIDO ---

class UserLogin(BaseModel):
    # Corrigido para aceitar o mesmo formato do UserCreate
    username: constr(min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9]+$") 
    password: constr(min_length=6, max_length=100)
    perfil:str