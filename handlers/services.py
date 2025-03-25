from typing import Dict, List

# Доступные сервисы и их описания
available_services: Dict[str, str] = {
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

def get_services_keyboard():
    """Создает клавиатуру с доступными сервисами"""
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    
    keyboard = []
    for service_id, service_name in available_services.items():
        keyboard.append([
            InlineKeyboardButton(
                text=service_name,
                callback_data=f"service_{service_id}"
            )
        ])
    
    keyboard.append([
        InlineKeyboardButton(
            text="↩️ Назад",
            callback_data="back_to_main"
        )
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard) 