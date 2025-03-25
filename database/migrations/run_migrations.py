import asyncio
import logging
from pathlib import Path
import sys
import importlib.util
import inspect

# Добавляем корневую директорию проекта в PYTHONPATH
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from database.db import engine

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def load_migration_module(file_path: Path):
    """Загружает модуль миграции из файла"""
    spec = importlib.util.spec_from_file_location(file_path.stem, file_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

async def run_migrations():
    """Запуск всех миграций"""
    try:
        migrations_dir = Path(__file__).parent
        migration_files = sorted(migrations_dir.glob("*.py"))
        
        for file_path in migration_files:
            if file_path.name == "__init__.py" or file_path.name == "run_migrations.py":
                continue
                
            logger.info(f"Применяем миграцию: {file_path.name}")
            module = load_migration_module(file_path)
            
            if hasattr(module, 'upgrade'):
                async with engine.begin() as conn:
                    await module.upgrade(conn)
                logger.info(f"Миграция {file_path.name} успешно применена")
            else:
                logger.warning(f"Миграция {file_path.name} не содержит функции upgrade")
                
        logger.info("Все миграции успешно применены")
    except Exception as e:
        logger.error(f"Ошибка при выполнении миграций: {e}")
        raise

async def rollback_migrations():
    """Откат всех миграций"""
    try:
        migrations_dir = Path(__file__).parent
        migration_files = sorted(migrations_dir.glob("*.py"), reverse=True)
        
        for file_path in migration_files:
            if file_path.name == "__init__.py" or file_path.name == "run_migrations.py":
                continue
                
            logger.info(f"Откатываем миграцию: {file_path.name}")
            module = load_migration_module(file_path)
            
            if hasattr(module, 'downgrade'):
                async with engine.begin() as conn:
                    await module.downgrade(conn)
                logger.info(f"Миграция {file_path.name} успешно откачена")
            else:
                logger.warning(f"Миграция {file_path.name} не содержит функции downgrade")
                
        logger.info("Все миграции успешно откачены")
    except Exception as e:
        logger.error(f"Ошибка при откате миграций: {e}")
        raise

if __name__ == "__main__":
    # Запускаем миграции
    asyncio.run(run_migrations()) 