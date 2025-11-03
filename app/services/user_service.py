from sqlalchemy.future import select
from app.models.user import User

async def get_all_users(session):
    result = await session.execute(select(User))
    return result.scalars().all()

async def get_user_by_id(session, user_id: int):
    result = await session.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()

async def toggle_user_status(session, user_id: int):
    user = await get_user_by_id(session, user_id)
    if user:
        user.ativo = not user.ativo
        await session.commit()
    return user

async def update_user(session, user_id: int, data: dict):
    user = await get_user_by_id(session, user_id)
    if user:
        for key, value in data.items():
            setattr(user, key, value)
        await session.commit()
    return user

async def get_users_paginated(session, limit: int = 20, offset: int = 0):
    result = await session.execute(
        select(User).offset(offset).limit(limit)
    )
    return result.scalars().all()

from sqlalchemy import func
from sqlalchemy.future import select
from app.models.user import User

async def count_users(session):
    result = await session.execute(select(func.count()).select_from(User))
    return result.scalar()
from sqlalchemy import or_
from sqlalchemy.future import select
from app.models.user import User

async def search_users(session, query: str, limit: int = 20, offset: int = 0):
    result = await session.execute(
        select(User).where(
            or_(
                User.username.ilike(f"%{query}%"),
                User.email.ilike(f"%{query}%")
            )
        ).offset(offset).limit(limit)
    )
    return result.scalars().all()

async def count_users_filtered(session, query: str):
    from sqlalchemy import func
    result = await session.execute(
        select(func.count()).select_from(User).where(
            or_(
                User.username.ilike(f"%{query}%"),
                User.email.ilike(f"%{query}%")
            )
        )
    )
    return result.scalar()
