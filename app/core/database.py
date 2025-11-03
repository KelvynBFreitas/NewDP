# database.py
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import ORACLE_DATABASE_URL, POSTGRES_DATABASE_URL

# --- Base Declarativa (Pode ser compartilhada) ---
Base = declarative_base()


# --- Configuração do Oracle (Async) ---
oracle_engine = create_async_engine(
    ORACLE_DATABASE_URL, 
    echo=True
)
OracleAsyncSessionLocal = sessionmaker(
    bind=oracle_engine,
    class_=AsyncSession,
    expire_on_commit=False
)

# Dependência para o Oracle
async def get_oracle_session():
    async with OracleAsyncSessionLocal() as session:
        yield session


# --- Configuração do Postgres (Async) ---
postgres_engine = create_async_engine(
    POSTGRES_DATABASE_URL, 
    echo=True
)
PostgresAsyncSessionLocal = sessionmaker(
    bind=postgres_engine,
    class_=AsyncSession,
    expire_on_commit=False
)

# Dependência para o Postgres
async def get_postgres_session():
    async with PostgresAsyncSessionLocal() as session:
        yield session