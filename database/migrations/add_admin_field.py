from sqlalchemy import text
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def upgrade(conn):
    """Добавляет поле is_admin в таблицу users"""
    try:
        # Проверяем, существует ли уже поле is_admin
        result = await conn.execute(text("PRAGMA table_info(users)"))
        columns = [row[1] for row in result]
        
        if 'is_admin' not in columns:
            # Добавляем поле is_admin
            await conn.execute(text("ALTER TABLE users ADD COLUMN is_admin BOOLEAN DEFAULT FALSE"))
            logger.info("Поле is_admin успешно добавлено в таблицу users")
        else:
            logger.info("Поле is_admin уже существует в таблице users")
            
    except Exception as e:
        logger.error(f"Ошибка при добавлении поля is_admin: {e}")
        raise

async def downgrade(conn):
    """Удаляет поле is_admin из таблицы users"""
    try:
        # Проверяем, существует ли поле is_admin
        result = await conn.execute(text("PRAGMA table_info(users)"))
        columns = [row[1] for row in result]
        
        if 'is_admin' in columns:
            # Удаляем поле is_admin
            await conn.execute(text("ALTER TABLE users DROP COLUMN is_admin"))
            logger.info("Поле is_admin успешно удалено из таблицы users")
        else:
            logger.info("Поле is_admin не существует в таблице users")
            
    except Exception as e:
        logger.error(f"Ошибка при удалении поля is_admin: {e}")
        raise 