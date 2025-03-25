import asyncio
import sys
from pathlib import Path

# Добавляем корневую директорию проекта в PYTHONPATH
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from database.db import engine
from database.models import Base
from sqlalchemy import text

async def init_database():
    """Инициализирует базу данных и создает все необходимые таблицы"""
    try:
        print("Начинаем инициализацию базы данных...")
        
        # Создаем все таблицы
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            
            # Проверяем существование таблицы disputes
            result = await conn.execute(text("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='disputes'
            """))
            if not result.scalar():
                print("Создаем таблицу disputes...")
                await conn.execute(text("""
                    CREATE TABLE disputes (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        transaction_id INTEGER REFERENCES transactions(id) ON DELETE CASCADE,
                        user_id INTEGER REFERENCES users(telegram_id) ON DELETE CASCADE,
                        description TEXT NOT NULL,
                        status TEXT DEFAULT 'open',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        resolved_at TIMESTAMP,
                        resolved_by INTEGER REFERENCES users(telegram_id) ON DELETE SET NULL,
                        resolution TEXT
                    )
                """))
                
                # Создаем индексы для disputes
                await conn.execute(text("""
                    CREATE INDEX idx_dispute_status ON disputes(status)
                """))
                await conn.execute(text("""
                    CREATE INDEX idx_dispute_transaction ON disputes(transaction_id)
                """))
            
            # Проверяем существование таблицы reviews
            result = await conn.execute(text("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='reviews'
            """))
            if not result.scalar():
                print("Создаем таблицу reviews...")
                await conn.execute(text("""
                    CREATE TABLE reviews (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        transaction_id INTEGER REFERENCES transactions(id) ON DELETE CASCADE,
                        reviewer_id INTEGER REFERENCES users(telegram_id) ON DELETE CASCADE,
                        reviewed_id INTEGER REFERENCES users(telegram_id) ON DELETE CASCADE,
                        rating INTEGER NOT NULL,
                        comment TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """))
                
                # Создаем индексы для reviews
                await conn.execute(text("""
                    CREATE INDEX idx_review_transaction ON reviews(transaction_id)
                """))
                await conn.execute(text("""
                    CREATE INDEX idx_review_reviewer ON reviews(reviewer_id)
                """))
                await conn.execute(text("""
                    CREATE INDEX idx_review_reviewed ON reviews(reviewed_id)
                """))
            
            # Проверяем существование таблицы transactions
            result = await conn.execute(text("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='transactions'
            """))
            if not result.scalar():
                print("Создаем таблицу transactions...")
                await conn.execute(text("""
                    CREATE TABLE transactions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        listing_id INTEGER REFERENCES phone_listings(id) ON DELETE CASCADE,
                        buyer_id INTEGER REFERENCES users(telegram_id) ON DELETE CASCADE,
                        seller_id INTEGER REFERENCES users(telegram_id) ON DELETE CASCADE,
                        amount FLOAT NOT NULL,
                        status TEXT DEFAULT 'pending',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        completed_at TIMESTAMP
                    )
                """))
                
                # Создаем индексы для transactions
                await conn.execute(text("""
                    CREATE INDEX idx_transaction_status ON transactions(status)
                """))
                await conn.execute(text("""
                    CREATE INDEX idx_transaction_buyer ON transactions(buyer_id)
                """))
                await conn.execute(text("""
                    CREATE INDEX idx_transaction_seller ON transactions(seller_id)
                """))
                await conn.execute(text("""
                    CREATE INDEX idx_transaction_listing ON transactions(listing_id)
                """))
            
            # Проверяем существование таблицы phone_listings
            result = await conn.execute(text("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='phone_listings'
            """))
            if not result.scalar():
                print("Создаем таблицу phone_listings...")
                await conn.execute(text("""
                    CREATE TABLE phone_listings (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        seller_id INTEGER REFERENCES users(telegram_id) ON DELETE CASCADE,
                        service TEXT NOT NULL,
                        phone_number TEXT NOT NULL,
                        rental_period INTEGER NOT NULL,
                        price FLOAT NOT NULL,
                        is_active BOOLEAN DEFAULT TRUE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """))
                
                # Создаем индексы для phone_listings
                await conn.execute(text("""
                    CREATE INDEX idx_listing_service ON phone_listings(service)
                """))
                await conn.execute(text("""
                    CREATE INDEX idx_listing_active ON phone_listings(is_active)
                """))
                await conn.execute(text("""
                    CREATE INDEX idx_listing_seller ON phone_listings(seller_id)
                """))
            
            # Проверяем существование таблицы users
            result = await conn.execute(text("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='users'
            """))
            if not result.scalar():
                print("Создаем таблицу users...")
                await conn.execute(text("""
                    CREATE TABLE users (
                        telegram_id INTEGER PRIMARY KEY,
                        username TEXT,
                        phone_number TEXT,
                        balance FLOAT DEFAULT 0.0,
                        rating FLOAT DEFAULT 5.0,
                        total_reviews INTEGER DEFAULT 0,
                        is_blocked BOOLEAN DEFAULT FALSE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """))
        
        print("✅ База данных успешно инициализирована!")
        
    except Exception as e:
        print(f"❌ Ошибка при инициализации базы данных: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(init_database()) 