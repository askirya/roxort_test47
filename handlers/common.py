from aiogram import Router, types, Dispatcher, F
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.fsm.context import FSMContext
from database.db import async_session
from database.models import User, Transaction, Review, PromoCode, Dispute, PhoneListing
from sqlalchemy import select, or_, func
from config import ADMIN_IDS
from sqlalchemy.ext.asyncio import AsyncSession
import logging
from aiogram.filters import Command
from datetime import datetime, timedelta
from aiogram.fsm.state import StatesGroup, State

router = Router()
logger = logging.getLogger(__name__)

class UserStates(StatesGroup):
    entering_promo = State()
    entering_withdrawal_amount = State()
    entering_usdt_address = State()

def get_main_keyboard(user_id: int = None):
    keyboard = [
        [
            KeyboardButton(text="📱 Купить номер"),
            KeyboardButton(text="📱 Продать номер")
        ],
        [
            KeyboardButton(text="💳 Баланс"),
            KeyboardButton(text="💳 Вывод в USDT")
        ],
        [
            KeyboardButton(text="🎁 Активировать промокод"),
            KeyboardButton(text="⭐️ Отзывы")
        ],
        [
            KeyboardButton(text="⚖️ Споры"),
            KeyboardButton(text="👤 Профиль")
        ]
    ]
    
    if user_id in ADMIN_IDS:
        keyboard.append([KeyboardButton(text="👑 Админ панель")])
    
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

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

@router.message(F.text == "💳 Баланс")
async def show_balance(message: types.Message):
    """Показывает баланс пользователя"""
    try:
        async with async_session() as session:
            user = await session.get(User, message.from_user.id)
            if not user:
                await message.answer(
                    "❌ Пожалуйста, сначала зарегистрируйтесь.",
                    reply_markup=get_main_keyboard()
                )
                return
            
            # Получаем статистику транзакций
            transactions_query = select(Transaction).where(
                or_(
                    Transaction.buyer_id == user.telegram_id,
                    Transaction.seller_id == user.telegram_id
                )
            )
            transactions_result = await session.execute(transactions_query)
            transactions = transactions_result.scalars().all()
            
            total_bought = sum(t.amount for t in transactions if t.buyer_id == user.telegram_id)
            total_sold = sum(t.amount for t in transactions if t.seller_id == user.telegram_id)
            
            response = f"💰 Ваш баланс: {user.balance:.2f} ROXY\n\n"
            response += f"📊 Статистика:\n"
            response += f"Куплено на: {total_bought:.2f} ROXY\n"
            response += f"Продано на: {total_sold:.2f} ROXY\n"
            
            if user.balance >= 100:
                response += "\n💡 Вы можете вывести средства в USDT (минимум 100 ROXY)"
            
            await message.answer(response, reply_markup=get_main_keyboard())
    except Exception as e:
        logger.error(f"Error in show_balance: {e}")
        await message.answer(
            "❌ Произошла ошибка при получении баланса.",
            reply_markup=get_main_keyboard()
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

@router.message(F.text == "⚖️ Споры")
async def show_disputes(message: types.Message):
    """Показывает список активных споров"""
    try:
        async with async_session() as session:
            # Получаем споры, где пользователь является участником
            disputes = await session.scalars(
                select(Dispute).where(
                    or_(
                        Dispute.buyer_id == message.from_user.id,
                        Dispute.seller_id == message.from_user.id
                    )
                ).order_by(Dispute.created_at.desc())
            )
            disputes = disputes.all()
            
            if not disputes:
                await message.answer(
                    "📋 У вас нет активных споров.",
                    reply_markup=get_main_keyboard()
                )
                return
            
            # Формируем список споров
            text = "📋 Ваши споры:\n\n"
            for dispute in disputes:
                # Определяем роль пользователя в споре
                role = "Покупатель" if dispute.buyer_id == message.from_user.id else "Продавец"
                
                # Получаем информацию о транзакции
                transaction = await session.get(Transaction, dispute.transaction_id)
                if not transaction:
                    continue
                
                # Получаем информацию о листинге
                listing = await session.get(PhoneListing, transaction.listing_id)
                if not listing:
                    continue
                
                # Получаем информацию о второй стороне
                other_party_id = dispute.seller_id if role == "Покупатель" else dispute.buyer_id
                other_party = await session.get(User, other_party_id)
                
                text += (
                    f"ID спора: {dispute.id}\n"
                    f"Роль: {role}\n"
                    f"Сервис: {available_services[listing.service]}\n"
                    f"Сумма: {transaction.amount:.2f} ROXY\n"
                    f"Оппонент: @{other_party.username or 'Пользователь'}\n"
                    f"Статус: {dispute.status}\n\n"
                )
            
            # Добавляем кнопку для создания нового спора
            keyboard = [
                [InlineKeyboardButton(text="⚖️ Открыть спор", callback_data="open_dispute")],
                [InlineKeyboardButton(text="↩️ Назад", callback_data="back_to_main")]
            ]
            
            await message.answer(
                text,
                reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
            )
            
    except Exception as e:
        logger.error(f"Error in show_disputes: {e}")
        await message.answer(
            "❌ Произошла ошибка при получении списка споров.",
            reply_markup=get_main_keyboard()
        )

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

@router.message(F.text == "🎁 Активировать промокод")
async def activate_promo(message: types.Message, state: FSMContext):
    if not await check_user_registered(message.from_user.id):
        await message.answer(
            "❌ Вы не зарегистрированы!\n"
            "Пожалуйста, пройдите регистрацию:",
            reply_markup=get_main_keyboard()
        )
        return
    
    await message.answer(
        "Введите промокод:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_promo")
        ]])
    )
    await state.set_state(UserStates.entering_promo)

@router.message(UserStates.entering_promo)
async def process_promo(message: types.Message, state: FSMContext):
    code = message.text.upper()
    
    async with async_session() as session:
        # Проверяем промокод
        promo = await session.scalar(
            select(PromoCode).where(PromoCode.code == code)
        )
        
        if not promo:
            await message.answer(
                "❌ Промокод не найден. Попробуйте еще раз:",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_promo")
                ]])
            )
            return
        
        if promo.is_used:
            await message.answer(
                "❌ Этот промокод уже использован.",
                reply_markup=get_main_keyboard(message.from_user.id)
            )
            await state.clear()
            return
        
        if promo.expires_at and promo.expires_at < datetime.utcnow():
            await message.answer(
                "❌ Срок действия промокода истек.",
                reply_markup=get_main_keyboard(message.from_user.id)
            )
            await state.clear()
            return
        
        # Активируем промокод
        user = await session.get(User, message.from_user.id)
        user.balance += promo.amount
        promo.is_used = True
        promo.used_by = message.from_user.id
        
        await session.commit()
        
        await message.answer(
            f"✅ Промокод успешно активирован!\n"
            f"На ваш баланс начислено {promo.amount} ROXY",
            reply_markup=get_main_keyboard(message.from_user.id)
        )
        await state.clear()

@router.callback_query(lambda c: c.data == "cancel_promo")
async def cancel_promo(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "❌ Активация промокода отменена.",
        reply_markup=get_main_keyboard(callback.from_user.id)
    )

@router.message(F.text == "💳 Вывод в USDT")
async def start_withdraw(message: types.Message, state: FSMContext):
    if not await check_user_registered(message.from_user.id):
        await message.answer(
            "❌ Вы не зарегистрированы!\n"
            "Пожалуйста, пройдите регистрацию:",
            reply_markup=get_main_keyboard()
        )
        return
    
    async with async_session() as session:
        user = await session.get(User, message.from_user.id)
        if user.balance < 100:
            await message.answer(
                "❌ Минимальная сумма для вывода: 100 ROXY\n"
                f"Ваш баланс: {user.balance} ROXY",
                reply_markup=get_main_keyboard(message.from_user.id)
            )
            return
    
    await message.answer(
        "Введите сумму для вывода в ROXY (минимум 100):",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_withdraw")
        ]])
    )
    await state.set_state(UserStates.entering_withdrawal_amount)

@router.message(UserStates.entering_withdrawal_amount)
async def process_withdraw_amount(message: types.Message, state: FSMContext):
    try:
        amount = float(message.text)
        if amount < 100:
            await message.answer(
                "❌ Минимальная сумма для вывода: 100 ROXY\n"
                "Попробуйте еще раз:",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_withdraw")
                ]])
            )
            return
        
        async with async_session() as session:
            user = await session.get(User, message.from_user.id)
            if user.balance < amount:
                await message.answer(
                    "❌ Недостаточно средств на балансе.\n"
                    f"Ваш баланс: {user.balance} ROXY\n"
                    "Попробуйте еще раз:",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                        InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_withdraw")
                    ]])
                )
                return
        
        await state.update_data(withdraw_amount=amount)
        await state.set_state(UserStates.entering_usdt_address)
        
        await message.answer(
            "Введите ваш USDT (TRC20) адрес:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_withdraw")
            ]])
        )
    except ValueError:
        await message.answer(
            "❌ Пожалуйста, введите корректную сумму (например: 100):",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_withdraw")
            ]])
        )

@router.message(UserStates.entering_usdt_address)
async def process_withdraw_address(message: types.Message, state: FSMContext):
    data = await state.get_data()
    amount = data['withdraw_amount']
    usdt_amount = amount / 10  # Конвертация ROXY в USDT (10:1)
    
    async with async_session() as session:
        user = await session.get(User, message.from_user.id)
        
        # Списываем средства
        user.balance -= amount
        
        # Создаем транзакцию
        transaction = Transaction(
            user_id=user.telegram_id,
            amount=amount,
            type="withdraw",
            status="pending",
            created_at=datetime.utcnow(),
            details={
                "usdt_address": message.text,
                "usdt_amount": usdt_amount
            }
        )
        
        session.add(transaction)
        await session.commit()
        
        # Уведомляем админов
        for admin_id in ADMIN_IDS:
            try:
                await message.bot.send_message(
                    admin_id,
                    f"💰 Новая заявка на вывод!\n\n"
                    f"Пользователь: @{user.username or 'Пользователь'}\n"
                    f"Сумма: {amount} ROXY ({usdt_amount} USDT)\n"
                    f"Адрес: {message.text}\n\n"
                    "Пожалуйста, обработайте заявку в личных сообщениях с пользователем.",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                        InlineKeyboardButton(
                            text="💬 Написать пользователю",
                            url=f"tg://user?id={user.telegram_id}"
                        )
                    ]])
                )
            except Exception as e:
                logger.error(f"Failed to notify admin {admin_id}: {e}")
        
        await message.answer(
            f"✅ Заявка на вывод создана!\n\n"
            f"Сумма: {amount} ROXY ({usdt_amount} USDT)\n"
            f"Адрес: {message.text}\n\n"
            "Администратор свяжется с вами для подтверждения вывода.",
            reply_markup=get_main_keyboard(message.from_user.id)
        )
        await state.clear()

@router.callback_query(lambda c: c.data == "cancel_withdraw")
async def cancel_withdraw(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "❌ Вывод средств отменен.",
        reply_markup=get_main_keyboard(callback.from_user.id)
    )

@router.callback_query(lambda c: c.data.startswith("open_dispute:"))
async def open_dispute(callback: types.CallbackQuery):
    """Открывает спор по транзакции"""
    try:
        transaction_id = int(callback.data.split(":")[1])
        
        async with async_session() as session:
            transaction = await session.get(Transaction, transaction_id)
            if not transaction:
                await callback.answer("❌ Транзакция не найдена", show_alert=True)
                return
            
            # Проверяем, что пользователь является участником сделки
            if callback.from_user.id not in [transaction.buyer_id, transaction.seller_id]:
                await callback.answer("❌ У вас нет доступа к этой сделке", show_alert=True)
                return
            
            # Создаем спор
            dispute = Dispute(
                transaction_id=transaction_id,
                initiator_id=callback.from_user.id,
                status="active",
                created_at=datetime.utcnow()
            )
            session.add(dispute)
            
            # Замораживаем средства
            transaction.status = "disputed"
            
            await session.commit()
            
            # Уведомляем участников
            await callback.message.edit_text(
                "⚖️ Спор успешно открыт!\n\n"
                "Администратор рассмотрит спор и примет решение.\n"
                "Средства заморожены до решения спора."
            )
            
            # Уведомляем второго участника
            other_party_id = transaction.seller_id if callback.from_user.id == transaction.buyer_id else transaction.buyer_id
            await callback.bot.send_message(
                other_party_id,
                "⚖️ По вашей сделке открыт спор!\n\n"
                "Администратор рассмотрит спор и примет решение.\n"
                "Средства заморожены до решения спора."
            )
            
    except Exception as e:
        logger.error(f"Error in open_dispute: {e}")
        await callback.answer("❌ Произошла ошибка при открытии спора", show_alert=True)

@router.callback_query(lambda c: c.data.startswith("leave_review:"))
async def leave_review(callback: types.CallbackQuery, state: FSMContext):
    """Начинает процесс оставления отзыва"""
    try:
        transaction_id = int(callback.data.split(":")[1])
        
        async with async_session() as session:
            transaction = await session.get(Transaction, transaction_id)
            if not transaction:
                await callback.answer("❌ Транзакция не найдена", show_alert=True)
                return
            
            # Проверяем, что пользователь является участником сделки
            if callback.from_user.id not in [transaction.buyer_id, transaction.seller_id]:
                await callback.answer("❌ У вас нет доступа к этой сделке", show_alert=True)
                return
            
            # Определяем, кому оставляем отзыв
            target_user_id = transaction.seller_id if callback.from_user.id == transaction.buyer_id else transaction.buyer_id
            
            # Создаем клавиатуру с кнопками лайка и дизлайка
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="👍 Лайк", callback_data=f"review:like:{transaction_id}:{target_user_id}"),
                    InlineKeyboardButton(text="👎 Дизлайк", callback_data=f"review:dislike:{transaction_id}:{target_user_id}")
                ]
            ])
            
            await callback.message.edit_text(
                "⭐️ Оставьте отзыв о пользователе:",
                reply_markup=keyboard
            )
            
    except Exception as e:
        logger.error(f"Error in leave_review: {e}")
        await callback.answer("❌ Произошла ошибка при создании отзыва", show_alert=True)

@router.callback_query(lambda c: c.data.startswith("review:"))
async def process_review(callback: types.CallbackQuery):
    """Обрабатывает отзыв (лайк/дизлайк)"""
    try:
        _, action, transaction_id, target_user_id = callback.data.split(":")
        transaction_id = int(transaction_id)
        target_user_id = int(target_user_id)
        
        async with async_session() as session:
            # Проверяем, что пользователь является участником сделки
            transaction = await session.get(Transaction, transaction_id)
            if not transaction or callback.from_user.id not in [transaction.buyer_id, transaction.seller_id]:
                await callback.answer("❌ У вас нет доступа к этой сделке", show_alert=True)
                return
            
            # Получаем пользователя, которому оставляем отзыв
            target_user = await session.get(User, target_user_id)
            if not target_user:
                await callback.answer("❌ Пользователь не найден", show_alert=True)
                return
            
            # Обновляем рейтинг
            if action == "like":
                target_user.rating += 1
                await callback.answer("👍 Вы поставили лайк!")
            else:
                target_user.rating -= 1
                await callback.answer("👎 Вы поставили дизлайк!")
            
            await session.commit()
            
            # Обновляем сообщение
            await callback.message.edit_text(
                "✅ Спасибо за отзыв!\n\n"
                f"Текущий рейтинг пользователя: {target_user.rating:.1f}"
            )
            
    except Exception as e:
        logger.error(f"Error in process_review: {e}")
        await callback.answer("❌ Произошла ошибка при обработке отзыва", show_alert=True)

def register_common_handlers(dp: Dispatcher):
    """Регистрация обработчиков общих команд"""
    dp.include_router(router) 