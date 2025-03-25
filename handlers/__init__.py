from aiogram import Dispatcher
from .admin import register_admin_handlers
from .buying import register_buying_handlers
from .ratings import register_rating_handlers
from .disputes import register_dispute_handlers
from .common import register_common_handlers

def register_all_handlers(dp: Dispatcher):
    """Регистрация всех обработчиков"""
    # Регистрируем обработчики в порядке приоритета
    register_admin_handlers(dp)  # Админские команды должны быть первыми
    register_buying_handlers(dp)
    register_rating_handlers(dp)
    register_dispute_handlers(dp)
    register_common_handlers(dp)  # Общие команды должны быть последними 