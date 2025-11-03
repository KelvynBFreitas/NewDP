from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import DATABASE_URL

# Criação do engine assíncrono
engine = create_async_engine(DATABASE_URL, echo=True)

# Sessão assíncrona
AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)

# Base declarativa para os modelos
Base = declarative_base()

# Dependência para injeção de sessão
async def get_session():
    async with AsyncSessionLocal() as session:
        yield session
