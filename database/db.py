import os
from pathlib import Path

# Определяем путь к базе данных
DB_PATH = Path(__file__).parent / "roxort.db"

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import NullPool
from typing import AsyncGenerator
from config import DATABASE_URL

class Base(DeclarativeBase):
    pass

# Создаем движок базы данных
engine = create_async_engine(
    f"sqlite+aiosqlite:///{DB_PATH}",
    echo=True
)

# Создаем фабрику сессий
async_session = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)

# Функция для получения сессии как контекстного менеджера
async def get_session() -> AsyncSession:
    """Получение сессии для работы с базой данных"""
    session = async_session()
    try:
        yield session
    finally:
        await session.close()

async def init_db() -> bool:
    """Инициализация подключения к базе данных"""
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        return True
    except Exception as e:
        print(f"Ошибка при инициализации БД: {e}")
        return False

async def create_tables() -> None:
    """Создание всех таблиц в базе данных"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def drop_tables() -> None:
    """Удаление всех таблиц из базы данных"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all) 