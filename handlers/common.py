from aiogram import Router, types, Dispatcher
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, Message
from aiogram.fsm.context import FSMContext
from database.db import async_session
from database.models import User, Transaction, Review
from sqlalchemy import select, or_
from config import ADMIN_IDS
from sqlalchemy.ext.asyncio import AsyncSession
import logging
from aiogram.filters import Command
from datetime import datetime

router = Router()
logger = logging.getLogger(__name__)

def get_main_keyboard(user_id: int = None):
    keyboard = [
        [
            KeyboardButton(text="👤 Профиль")
        ],
        [
            KeyboardButton(text="📱 Купить номер"),
            KeyboardButton(text="📱 Продать номер")
        ],
        [
            KeyboardButton(text="💰 Баланс"),
            KeyboardButton(text="💸 Вывести средства")
        ],
        [
            KeyboardButton(text="⚠️ Споры"),
            KeyboardButton(text="⭐️ Отзывы")
        ]
    ]
    
    if isinstance(user_id, int) and user_id in ADMIN_IDS:
        keyboard.append([KeyboardButton(text="🔑 Панель администратора")])
    
    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True
    )

def get_start_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="🔄 Начать регистрацию")]],
        resize_keyboard=True
    )

def get_admin_keyboard():
    keyboard = [
        [
            KeyboardButton(text="📊 Статистика"),
            KeyboardButton(text="👥 Пользователи")
        ],
        [
            KeyboardButton(text="⚙️ Настройки"),
            KeyboardButton(text="↩️ Назад")
        ]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

async def check_user_registered(user_id: int) -> bool:
    async with async_session() as session:
        query = select(User).where(User.telegram_id == user_id)
        result = await session.execute(query)
        user = result.scalar_one_or_none()
        return user is not None

@router.message(Command("start"))
async def cmd_start(message: Message):
    """Обработчик команды /start"""
    try:
        async with async_session() as session:
            user = await session.get(User, message.from_user.id)
            
            if not user:
                user = User(
                    telegram_id=message.from_user.id,
                    username=message.from_user.username,
                    created_at=datetime.utcnow(),
                    balance=0.0,
                    rating=5.0,
                    is_blocked=False
                )
                session.add(user)
                await session.commit()
                
                await message.answer(
                    "👋 Добро пожаловать в ROXORT!\n\n"
                    "Я помогу вам купить или продать номер телефона.\n"
                    "Используйте меню ниже для навигации:",
                    reply_markup=get_main_keyboard(message.from_user.id)
                )
            else:
                await message.answer(
                    "👋 С возвращением в ROXORT!\n"
                    "Выберите действие в меню:",
                    reply_markup=get_main_keyboard(message.from_user.id)
                )
    except Exception as e:
        logger.error(f"Ошибка при обработке команды /start: {e}")
        await message.answer("Произошла ошибка. Пожалуйста, попробуйте позже.")

@router.message(Command("help"))
async def cmd_help(message: Message):
    """Обработчик команды /help"""
    help_text = (
        "🤖 ROXORT - Бот для покупки и продажи номеров телефонов\n\n"
        "📱 Основные команды:\n"
        "/start - Начать работу с ботом\n"
        "/help - Показать это сообщение\n"
        "/buy - Купить номер\n"
        "/sell - Продать номер\n"
        "/balance - Проверить баланс\n"
        "/dispute - Открыть спор\n"
        "/ratings - Просмотр отзывов\n\n"
        "❓ Как пользоваться:\n"
        "1. Зарегистрируйтесь через /start\n"
        "2. Пополните баланс\n"
        "3. Выберите нужное действие в меню\n\n"
        "⚠️ Важно:\n"
        "- Все сделки защищены\n"
        "При возникновении проблем используйте систему споров\n"
        "- Рейтинг влияет на доверие пользователей\n"
        "- Администрация всегда готова помочь"
    )
    await message.answer(help_text)

@router.message(lambda message: message.text == "👤 Профиль")
async def show_profile(message: Message):
    async with async_session() as session:
        user = await session.get(User, message.from_user.id)
        
        if not user:
            await message.answer(
                "❌ Вы не зарегистрированы!\n"
                "Пожалуйста, пройдите регистрацию:",
                reply_markup=get_start_keyboard()
            )
            return
        
        tx_query = select(Transaction).where(
            or_(
                Transaction.buyer_id == user.telegram_id,
                Transaction.seller_id == user.telegram_id
            )
        )
        tx_result = await session.execute(tx_query)
        transactions = tx_result.scalars().all()
        
        sold_count = len([tx for tx in transactions if tx.seller_id == user.telegram_id and tx.status == "completed"])
        bought_count = len([tx for tx in transactions if tx.buyer_id == user.telegram_id and tx.status == "completed"])
        
        reviews_query = select(Review).where(Review.reviewed_id == user.telegram_id)
        reviews_result = await session.execute(reviews_query)
        reviews_count = len(reviews_result.scalars().all())
        
        await message.answer(
            f"📊 Ваш профиль:\n"
            f"ID: {user.telegram_id}\n"
            f"Телефон: {user.phone_number}\n"
            f"Рейтинг: {'⭐️' * round(user.rating)} ({user.rating:.1f})\n"
            f"Количество отзывов: {reviews_count}\n"
            f"Баланс: {user.balance} USDT\n"
            f"Продано номеров: {sold_count}\n"
            f"Куплено номеров: {bought_count}\n"
            f"Дата регистрации: {user.created_at.strftime('%d.%m.%Y')}",
            reply_markup=get_main_keyboard(message.from_user.id)
        )

@router.message(lambda message: message.text == "💰 Баланс")
async def show_balance(message: Message):
    async with async_session() as session:
        user = await session.get(User, message.from_user.id)
        
        if not user:
            await message.answer(
                "❌ Вы не зарегистрированы!\n"
                "Пожалуйста, пройдите регистрацию:",
                reply_markup=get_start_keyboard()
            )
            return
        
        await message.answer(
            f"💰 Ваш текущий баланс: {user.balance} USDT",
            reply_markup=get_main_keyboard(message.from_user.id)
        )

@router.message(lambda message: message.text == "📱 Купить номер")
async def start_buying(message: Message, state: FSMContext):
    if not await check_user_registered(message.from_user.id):
        await message.answer(
            "❌ Вы не зарегистрированы!\n"
            "Пожалуйста, пройдите регистрацию сначала.",
            reply_markup=get_start_keyboard()
        )
        return
    
    from handlers.buying import show_services_message
    await show_services_message(message, state)

@router.message(lambda message: message.text == "📱 Продать номер")
async def handle_sell(message: Message, state: FSMContext):
    if not await check_user_registered(message.from_user.id):
        await message.answer(
            "❌ Вы не зарегистрированы!\n"
            "Пожалуйста, пройдите регистрацию сначала.",
            reply_markup=get_start_keyboard()
        )
        return
    
    from handlers.selling import start_selling
    await start_selling(message, state)

@router.message(lambda message: message.text == "💸 Вывести средства")
async def handle_withdraw(message: Message, state: FSMContext):
    if not await check_user_registered(message.from_user.id):
        await message.answer(
            "❌ Вы не зарегистрированы!\n"
            "Пожалуйста, пройдите регистрацию сначала.",
            reply_markup=get_start_keyboard()
        )
        return
    
    async with async_session() as session:
        user = await session.get(User, message.from_user.id)
        if user.balance < 10:
            await message.answer(
                "❌ Недостаточно средств для вывода.\n"
                "Минимальная сумма вывода: 10 USDT",
                reply_markup=get_main_keyboard(message.from_user.id)
            )
            return
    
    await state.set_state("withdraw_amount")
    await message.answer(
        "💸 Введите сумму для вывода (минимум 10 USDT):",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="❌ Отмена")]],
            resize_keyboard=True
        )
    )

@router.message(lambda message: message.text == "⚠️ Споры")
async def handle_disputes(message: Message):
    if not await check_user_registered(message.from_user.id):
        await message.answer(
            "❌ Вы не зарегистрированы!\n"
            "Пожалуйста, пройдите регистрацию сначала.",
            reply_markup=get_start_keyboard()
        )
        return
    
    from handlers.disputes import show_disputes
    await show_disputes(message)

@router.message(lambda message: message.text == "⭐️ Отзывы")
async def handle_reviews(message: Message):
    if not await check_user_registered(message.from_user.id):
        await message.answer(
            "❌ Вы не зарегистрированы!\n"
            "Пожалуйста, пройдите регистрацию сначала.",
            reply_markup=get_start_keyboard()
        )
        return
    
    from handlers.ratings import show_reviews
    await show_reviews(message)

@router.message(lambda message: message.text == "🔑 Панель администратора")
async def handle_admin_panel(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer(
            "❌ У вас нет доступа к панели администратора.",
            reply_markup=get_main_keyboard(message.from_user.id)
        )
        return
    
    from handlers.admin import show_admin_panel
    await show_admin_panel(message)

@router.message(lambda message: message.text == "❌ Отмена")
async def handle_cancel(message: Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state:
        await state.clear()
    
    await message.answer(
        "Действие отменено.",
        reply_markup=get_main_keyboard(message.from_user.id)
    )

@router.message(lambda message: message.text and message.text.startswith("💸"))
async def handle_withdraw_amount(message: Message, state: FSMContext):
    try:
        amount = float(message.text.replace("💸", "").strip())
        if amount < 10:
            await message.answer(
                "❌ Минимальная сумма вывода: 10 USDT\n"
                "Попробуйте еще раз:",
                reply_markup=ReplyKeyboardMarkup(
                    keyboard=[[KeyboardButton(text="❌ Отмена")]],
                    resize_keyboard=True
                )
            )
            return
        
        async with async_session() as session:
            user = await session.get(User, message.from_user.id)
            if user.balance < amount:
                await message.answer(
                    "❌ Недостаточно средств на балансе.\n"
                    "Попробуйте другую сумму:",
                    reply_markup=ReplyKeyboardMarkup(
                        keyboard=[[KeyboardButton(text="❌ Отмена")]],
                        resize_keyboard=True
                    )
                )
                return
            
            user.balance -= amount
            await session.commit()
        
        await state.clear()
        await message.answer(
            f"✅ Заявка на вывод {amount} USDT создана.\n"
            "Администратор проверит и обработает её в ближайшее время.",
            reply_markup=get_main_keyboard(message.from_user.id)
        )
    except ValueError:
        await message.answer(
            "❌ Неверный формат суммы.\n"
            "Попробуйте еще раз:",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text="❌ Отмена")]],
                resize_keyboard=True
            )
        )

def register_common_handlers(dp: Dispatcher):
    """Регистрация обработчиков общих команд"""
    dp.include_router(router) 