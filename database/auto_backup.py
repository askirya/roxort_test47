import asyncio
import time
from database.backup import backup_database

async def run_auto_backup():
    """Запускает автоматическое резервное копирование каждый час"""
    print("🔄 Запущен сервис автоматического резервного копирования")
    while True:
        await backup_database()
        # Ждем 1 час (3600 секунд)
        await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(run_auto_backup()) 