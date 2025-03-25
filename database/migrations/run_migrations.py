import asyncio
import logging
from pathlib import Path
import sys

# Добавляем корневую директорию проекта в PYTHONPATH
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from database.db import engine
from database.migrations.add_dispute_resolution_fields import upgrade, downgrade

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def run_migrations():
    """Запуск всех миграций"""
    try:
        async with engine.begin() as conn:
            # Запускаем миграции
            await upgrade(conn)
            logger.info("Миграции успешно применены")
    except Exception as e:
        logger.error(f"Ошибка при выполнении миграций: {e}")
        raise

async def rollback_migrations():
    """Откат всех миграций"""
    try:
        async with engine.begin() as conn:
            # Откатываем миграции
            await downgrade(conn)
            logger.info("Миграции успешно откачены")
    except Exception as e:
        logger.error(f"Ошибка при откате миграций: {e}")
        raise

if __name__ == "__main__":
    # Запускаем миграции
    asyncio.run(run_migrations()) 