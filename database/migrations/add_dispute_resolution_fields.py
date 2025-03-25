import logging
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy import text
from database.db import engine

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def upgrade(conn: AsyncConnection):
    """Добавление новых полей в таблицу disputes"""
    try:
        # Проверяем существование колонки resolved_by
        result = await conn.execute(text("""
            SELECT name FROM pragma_table_info('disputes') 
            WHERE name = 'resolved_by'
        """))
        if not result.fetchone():
            await conn.execute(text("""
                ALTER TABLE disputes 
                ADD COLUMN resolved_by INTEGER 
                REFERENCES users(id) 
                ON DELETE SET NULL
            """))
            logger.info("Добавлена колонка resolved_by")

        # Проверяем существование колонки resolution
        result = await conn.execute(text("""
            SELECT name FROM pragma_table_info('disputes') 
            WHERE name = 'resolution'
        """))
        if not result.fetchone():
            await conn.execute(text("""
                ALTER TABLE disputes 
                ADD COLUMN resolution TEXT
            """))
            logger.info("Добавлена колонка resolution")

        await conn.commit()
        logger.info("Миграция успешно завершена")
    except Exception as e:
        logger.error(f"Ошибка при выполнении миграции: {e}")
        await conn.rollback()
        raise

async def downgrade(conn: AsyncConnection):
    """Удаление добавленных полей из таблицы disputes"""
    try:
        # Проверяем существование колонки resolution
        result = await conn.execute(text("""
            SELECT name FROM pragma_table_info('disputes') 
            WHERE name = 'resolution'
        """))
        if result.fetchone():
            await conn.execute(text("""
                ALTER TABLE disputes 
                DROP COLUMN resolution
            """))
            logger.info("Удалена колонка resolution")

        # Проверяем существование колонки resolved_by
        result = await conn.execute(text("""
            SELECT name FROM pragma_table_info('disputes') 
            WHERE name = 'resolved_by'
        """))
        if result.fetchone():
            await conn.execute(text("""
                ALTER TABLE disputes 
                DROP COLUMN resolved_by
            """))
            logger.info("Удалена колонка resolved_by")

        await conn.commit()
        logger.info("Откат миграции успешно завершен")
    except Exception as e:
        logger.error(f"Ошибка при откате миграции: {e}")
        await conn.rollback()
        raise

if __name__ == "__main__":
    import asyncio
    async def main():
        async with engine.begin() as conn:
            await upgrade(conn)
    asyncio.run(main()) 