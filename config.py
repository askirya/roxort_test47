from typing import List

# Основные настройки бота
BOT_TOKEN = "8129643535:AAEN6aiJ6R-dE-BXA76CgewnpEVbSys597o"

# ID администраторов
ADMIN_IDS = [1396514552]

# Настройки CryptoBot
CRYPTO_BOT_TOKEN = "354326:AAvvU1GhSq3Eajzz2ApK2jlGaYvHoXWewkY"
CRYPTO_BOT_API_URL = "https://pay.crypt.bot/api"
CRYPTO_MIN_AMOUNT = 0.1  # Минимальная сумма в USDT
CRYPTO_CURRENCY = "USDT"
CRYPTO_NETWORK = "TRC20"  # Сеть для USDT

# Настройки базы данных
DATABASE_URL = "sqlite+aiosqlite:///database.db"

# Доступные сервисы
AVAILABLE_SERVICES = {
    "whatsapp": "WhatsApp",
    "telegram": "Telegram",
    "viber": "Viber",
    "vkontakte": "VKontakte",
    "facebook": "Facebook",
    "instagram": "Instagram",
    "twitter": "Twitter",
    "snapchat": "Snapchat",
    "tiktok": "TikTok",
    "google": "Google",
}

# Настройки времени аренды (в часах)
RENTAL_PERIODS = [1, 4, 12, 24]

# Комиссия платформы (5%)
PLATFORM_FEE = 0.05

# Минимальные суммы для операций
MIN_DEPOSIT = CRYPTO_MIN_AMOUNT
MIN_WITHDRAWAL = CRYPTO_MIN_AMOUNT

# Настройки веб-хука
WEBHOOK_HOST = ""  # Например: https://your-domain.com
WEBHOOK_PATH = "/crypto-pay-webhook"
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}" if WEBHOOK_HOST else ""

# Настройки веб-сервера
WEBAPP_HOST = "localhost"
WEBAPP_PORT = 8080

# Настройки CryptoBot
CRYPTO_BOT_TOKEN = ""
CRYPTO_BOT_WEBHOOK_URL = "" 