import logging
import sys
from logging.handlers import RotatingFileHandler

# Настраиваем базовый логгер
logger = logging.getLogger('roxort_bot')
logger.setLevel(logging.INFO)

# Форматирование логов
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Хендлер для записи в файл
file_handler = RotatingFileHandler(
    'bot.log',
    maxBytes=5242880,  # 5MB
    backupCount=3,
    encoding='utf-8'
)
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# Хендлер для вывода в консоль
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(formatter)
logger.addHandler(console_handler) 