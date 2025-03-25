import asyncio
import shutil
from datetime import datetime
from pathlib import Path
from database.db import DB_PATH

async def backup_database():
    """Создает резервную копию базы данных"""
    try:
        # Создаем директорию для бэкапов, если её нет
        backup_dir = Path("database/backups")
        backup_dir.mkdir(exist_ok=True)
        
        # Формируем имя файла бэкапа с текущей датой и временем
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = backup_dir / f"roxort_backup_{timestamp}.db"
        
        # Копируем файл базы данных
        shutil.copy2(DB_PATH, backup_path)
        
        print(f"✅ Резервная копия создана: {backup_path}")
        
        # Удаляем старые бэкапы (оставляем только последние 24)
        backups = sorted(backup_dir.glob("roxort_backup_*.db"))
        if len(backups) > 24:
            for old_backup in backups[:-24]:
                old_backup.unlink()
                print(f"🗑️ Удален старый бэкап: {old_backup}")
        
    except Exception as e:
        print(f"❌ Ошибка при создании резервной копии: {e}")

if __name__ == "__main__":
    asyncio.run(backup_database()) 