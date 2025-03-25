import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import BotCommand, Message
from aiogram.filters import Command
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from config import BOT_TOKEN
from handlers import register_all_handlers
from database.backup import backup_database
from database.migrations.init_db import init_database
from database.migrations.run_migrations import run_migrations

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Глобальные объекты
bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()

async def setup_database():
    """Инициализация и обновление базы данных"""
    try:
        logger.info("Начинаем инициализацию базы данных...")
        await init_database()
        logger.info("База данных инициализирована")
        
        logger.info("Запускаем миграции...")
        await run_migrations()
        logger.info("Миграции выполнены успешно")
        
        # Создаем первую резервную копию
        await backup_database()
        logger.info("Создана первая резервная копия базы данных")
        
    except Exception as e:
        logger.error(f"Ошибка при инициализации базы данных: {e}")
        raise

async def run_backup_service():
    """Сервис автоматического резервного копирования"""
    while True:
        try:
            await backup_database()
            logger.info("Создана резервная копия базы данных")
        except Exception as e:
            logger.error(f"Ошибка при создании резервной копии: {e}")
        await asyncio.sleep(3600)  # Каждый час

@dp.startup()
async def on_startup():
    """Действия при запуске бота"""
    # Инициализируем базу данных
    await setup_database()
    
    # Регистрируем все обработчики
    register_all_handlers(dp)
    
    # Запускаем сервис резервного копирования
    asyncio.create_task(run_backup_service())
    
    logger.info("Бот успешно запущен")

@dp.shutdown()
async def on_shutdown():
    """Действия при выключении бота"""
    # Создаем финальную резервную копию
    try:
        await backup_database()
        logger.info("Создана финальная резервная копия базы данных")
    except Exception as e:
        logger.error(f"Ошибка при создании финальной резервной копии: {e}")
    
    logger.info("Бот остановлен")

async def main():
    """Основная функция запуска бота"""
    try:
        # Запускаем бота
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main()) 