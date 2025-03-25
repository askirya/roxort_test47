from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from database.db import async_session
from database.models import User, Transaction, Dispute, PhoneListing, Review, PromoCode
from datetime import datetime, timedelta
from sqlalchemy import select, func, and_, or_
import logging
from config import ADMIN_IDS
from handlers.common import get_main_keyboard
from aiogram import Dispatcher
from aiogram.filters import Command
from aiogram.types import Message

logger = logging.getLogger(__name__)

router = Router()

class AdminStates(StatesGroup):
    selecting_user = State()
    entering_amount = State()
    entering_message = State()
    selecting_listing = State()
    creating_promo = State()
    entering_promo_code = State()

def get_admin_keyboard():
    """Создает клавиатуру администратора"""
    keyboard = [
        [
            KeyboardButton(text="📊 Статистика"),
            KeyboardButton(text="👥 Пользователи")
        ],
        [
            KeyboardButton(text="💰 Управление балансами"),
            KeyboardButton(text="⚠️ Активные споры")
        ],
        [
            KeyboardButton(text="📢 Сделать объявление"),
            KeyboardButton(text="🔒 Заблокировать пользователя")
        ],
        [
            KeyboardButton(text="🎁 Управление промокодами"),
            KeyboardButton(text="❌ Выйти из панели админа")
        ]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

async def check_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

@router.message(F.text == "🔑 Панель администратора")
async def show_admin_panel(message: types.Message):
    """Показывает панель администратора"""
    if message.from_user.id not in ADMIN_IDS:
        await message.answer(
            "❌ У вас нет доступа к панели администратора.",
            reply_markup=get_main_keyboard(message.from_user.id)
        )
        return
    
    try:
        async with async_session() as session:
            # Получаем статистику
            users_count = await session.scalar(select(func.count(User.telegram_id)))
            active_listings = await session.scalar(select(func.count(PhoneListing.id)).where(PhoneListing.is_active == True))
            open_disputes = await session.scalar(select(func.count(Dispute.id)).where(Dispute.status == "open"))
            
            # Получаем последние транзакции
            transactions_query = select(Transaction).order_by(Transaction.created_at.desc()).limit(5)
            transactions_result = await session.execute(transactions_query)
            recent_transactions = transactions_result.scalars().all()
            
            # Формируем сообщение
            response = "🔑 Панель администратора\n\n"
            response += f"📊 Статистика:\n"
            response += f"👥 Всего пользователей: {users_count}\n"
            response += f"📱 Активных объявлений: {active_listings}\n"
            response += f"⚠️ Открытых споров: {open_disputes}\n\n"
            
            if recent_transactions:
                response += "💳 Последние транзакции:\n"
                for tx in recent_transactions:
                    response += f"ID: {tx.id}\n"
                    response += f"Сумма: {tx.amount} USDT\n"
                    response += f"Статус: {tx.status}\n"
                    response += f"Дата: {tx.created_at.strftime('%d.%m.%Y %H:%M')}\n\n"
            
            await message.answer(
                response,
                reply_markup=get_admin_keyboard()
            )
    except Exception as e:
        logger.error(f"Ошибка при показе панели администратора: {e}")
        await message.answer(
            "Произошла ошибка при загрузке панели администратора.",
            reply_markup=get_main_keyboard(message.from_user.id)
        )

@router.message(F.text == "📊 Статистика")
async def show_statistics(message: types.Message):
    """Показывает подробную статистику"""
    if message.from_user.id not in ADMIN_IDS:
        return
    
    try:
        async with async_session() as session:
            # Получаем расширенную статистику
            total_volume = await session.scalar(
                select(func.sum(Transaction.amount)).where(Transaction.status == "completed")
            ) or 0
            
            completed_tx = await session.scalar(
                select(func.count(Transaction.id)).where(Transaction.status == "completed")
            ) or 0
            
            avg_rating = await session.scalar(
                select(func.avg(User.rating))
            ) or 0
            
            # Статистика за последние 24 часа
            day_ago = datetime.utcnow() - timedelta(days=1)
            new_users = await session.scalar(
                select(func.count(User.telegram_id)).where(User.created_at >= day_ago)
            ) or 0
            
            new_transactions = await session.scalar(
                select(func.count(Transaction.id)).where(Transaction.created_at >= day_ago)
            ) or 0
            
            platform_earnings = total_volume * (5 / 100) if total_volume else 0
            
            response = "📊 Подробная статистика:\n\n"
            response += f"💰 Общий объем сделок: {total_volume:.2f} USDT\n"
            response += f"✅ Завершенных сделок: {completed_tx}\n"
            response += f"⭐️ Средний рейтинг: {avg_rating:.1f}\n"
            response += f"🆕 Новых пользователей за 24ч: {new_users}\n"
            response += f"💳 Новых сделок за 24ч: {new_transactions}\n"
            response += f"📈 Заработок платформы: {platform_earnings:.2f} USDT"
            
            await message.answer(response, reply_markup=get_admin_keyboard())
    except Exception as e:
        logger.error(f"Ошибка при показе статистики: {e}")
        await message.answer(
            "Произошла ошибка при загрузке статистики.",
            reply_markup=get_admin_keyboard()
        )

@router.message(F.text == "👥 Пользователи")
async def show_users(message: types.Message):
    """Показывает список пользователей"""
    if message.from_user.id not in ADMIN_IDS:
        return
    
    try:
        async with async_session() as session:
            # Получаем последних зарегистрированных пользователей
            users_query = select(User).order_by(User.created_at.desc()).limit(10)
            users_result = await session.execute(users_query)
            recent_users = users_result.scalars().all()
            
            response = "👥 Последние 10 пользователей:\n\n"
            for user in recent_users:
                response += f"ID: {user.telegram_id}\n"
                response += f"Username: @{user.username or 'Нет'}\n"
                response += f"Баланс: {user.balance} USDT\n"
                response += f"Рейтинг: ⭐️ {user.rating:.1f}\n"
                response += f"Регистрация: {user.created_at.strftime('%d.%m.%Y %H:%M')}\n"
                response += "➖➖➖➖➖➖➖➖➖➖\n"
            
            await message.answer(response, reply_markup=get_admin_keyboard())
    except Exception as e:
        logger.error(f"Ошибка при показе пользователей: {e}")
        await message.answer(
            "Произошла ошибка при загрузке списка пользователей.",
            reply_markup=get_admin_keyboard()
        )

@router.message(F.text == "💰 Управление балансами")
async def manage_balances(message: types.Message, state: FSMContext):
    """Начинает процесс управления балансами"""
    if message.from_user.id not in ADMIN_IDS:
        return
    
    try:
        async with async_session() as session:
            # Получаем список пользователей с их балансами
            users_query = select(User).order_by(User.balance.desc()).limit(10)
            users_result = await session.execute(users_query)
            users = users_result.scalars().all()
            
            keyboard = []
            for user in users:
                keyboard.append([InlineKeyboardButton(
                    text=f"👤 @{user.username or 'Пользователь'} | 💰 {user.balance} USDT",
                    callback_data=f"manage_balance:{user.telegram_id}"
                )])
            
            keyboard.append([InlineKeyboardButton(
                text="❌ Отмена",
                callback_data="cancel_admin_action"
            )])
            
            await state.set_state(AdminStates.selecting_user)
            await message.answer(
                "Выберите пользователя для управления балансом:",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
            )
    except Exception as e:
        logger.error(f"Ошибка при показе списка пользователей для управления балансом: {e}")
        await message.answer(
            "Произошла ошибка при загрузке списка пользователей.",
            reply_markup=get_admin_keyboard()
        )

@router.callback_query(lambda c: c.data.startswith("manage_balance:"))
async def process_user_selection(callback: types.CallbackQuery, state: FSMContext):
    """Обрабатывает выбор пользователя для управления балансом"""
    user_id = int(callback.data.split(":")[1])
    await state.update_data(user_id=user_id)
    await state.set_state(AdminStates.entering_amount)
    
    keyboard = [
        [InlineKeyboardButton(text="➕ Пополнить", callback_data="balance_action:add")],
        [InlineKeyboardButton(text="➖ Списать", callback_data="balance_action:subtract")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_admin_action")]
    ]
    
    await callback.message.edit_text(
        "Выберите действие:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )

@router.callback_query(lambda c: c.data.startswith("balance_action:"))
async def process_balance_action(callback: types.CallbackQuery, state: FSMContext):
    """Обрабатывает выбор действия с балансом"""
    action = callback.data.split(":")[1]
    await state.update_data(action=action)
    
    await callback.message.edit_text(
        "Введите сумму в USDT:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(
            text="❌ Отмена",
            callback_data="cancel_admin_action"
        )]])
    )

@router.message(AdminStates.entering_amount)
async def process_amount(message: types.Message, state: FSMContext):
    """Обрабатывает ввод суммы для изменения баланса"""
    try:
        amount = float(message.text)
        if amount <= 0:
            raise ValueError("Amount must be positive")
        
        data = await state.get_data()
        user_id = data['user_id']
        action = data['action']
        
        async with async_session() as session:
            user = await session.get(User, user_id)
            if not user:
                await message.answer(
                    "❌ Пользователь не найден.",
                    reply_markup=get_admin_keyboard()
                )
                return
            
            if action == "subtract" and user.balance < amount:
                await message.answer(
                    "❌ Недостаточно средств на балансе пользователя.",
                    reply_markup=get_admin_keyboard()
                )
                return
            
            # Изменяем баланс
            if action == "add":
                user.balance += amount
            else:
                user.balance -= amount
            
            await session.commit()
            
            await message.answer(
                f"✅ Баланс пользователя успешно {'пополнен' if action == 'add' else 'списан'} на {amount} USDT\n"
                f"Текущий баланс: {user.balance} USDT",
                reply_markup=get_admin_keyboard()
            )
            
            # Уведомляем пользователя
            try:
                await message.bot.send_message(
                    user_id,
                    f"💰 Ваш баланс был {'пополнен' if action == 'add' else 'списан'} на {amount} USDT\n"
                    f"Текущий баланс: {user.balance} USDT"
                )
            except Exception as e:
                logger.error(f"Failed to notify user {user_id} about balance change: {e}")
                
    except ValueError:
        await message.answer(
            "❌ Пожалуйста, введите корректное число.",
            reply_markup=get_admin_keyboard()
        )
    except Exception as e:
        logger.error(f"Error in process_amount: {e}")
        await message.answer(
            "❌ Произошла ошибка при изменении баланса.",
            reply_markup=get_admin_keyboard()
        )
    
    await state.clear()

@router.message(F.text == "⚠️ Активные споры")
async def show_active_disputes(message: types.Message):
    """Показывает активные споры"""
    if message.from_user.id not in ADMIN_IDS:
        return
    
    try:
        async with async_session() as session:
            # Получаем активные споры
            disputes_query = select(Dispute).where(
                Dispute.status == "open"
            ).order_by(Dispute.created_at.desc())
            
            result = await session.execute(disputes_query)
            disputes = result.scalars().all()
            
            if not disputes:
                await message.answer(
                    "В данный момент нет активных споров.",
                    reply_markup=get_admin_keyboard()
                )
                return
            
            response = "⚠️ Активные споры:\n\n"
            for dispute in disputes:
                transaction = await session.get(Transaction, dispute.transaction_id)
                buyer = await session.get(User, transaction.buyer_id)
                seller = await session.get(User, transaction.seller_id)
                
                response += f"ID спора: {dispute.id}\n"
                response += f"Сумма: {transaction.amount} USDT\n"
                response += f"Покупатель: @{buyer.username or 'Пользователь'}\n"
                response += f"Продавец: @{seller.username or 'Пользователь'}\n"
                response += f"Дата создания: {dispute.created_at.strftime('%d.%m.%Y %H:%M')}\n"
                response += "➖➖➖➖➖➖➖➖➖➖\n"
            
            await message.answer(response, reply_markup=get_admin_keyboard())
    except Exception as e:
        logger.error(f"Ошибка при показе активных споров: {e}")
        await message.answer(
            "Произошла ошибка при загрузке списка споров.",
            reply_markup=get_admin_keyboard()
        )

@router.message(F.text == "📢 Сделать объявление")
async def start_announcement(message: types.Message, state: FSMContext):
    """Начинает процесс создания объявления"""
    if message.from_user.id not in ADMIN_IDS:
        return
    
    await state.set_state(AdminStates.entering_message)
    await message.answer(
        "Введите текст объявления:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(
            text="❌ Отмена",
            callback_data="cancel_admin_action"
        )]])
    )

@router.message(AdminStates.entering_message)
async def process_announcement(message: types.Message, state: FSMContext):
    """Обрабатывает создание объявления"""
    try:
        announcement_text = message.text.strip()
        
        async with async_session() as session:
            # Получаем всех пользователей
            users_query = select(User.telegram_id)
            users_result = await session.execute(users_query)
            users = users_result.scalars().all()
            
            # Отправляем объявление всем пользователям
            success_count = 0
            fail_count = 0
            
            for user_id in users:
                try:
                    await message.bot.send_message(
                        user_id,
                        f"📢 Объявление от администратора:\n\n{announcement_text}"
                    )
                    success_count += 1
                except Exception as e:
                    logger.error(f"Failed to send announcement to user {user_id}: {e}")
                    fail_count += 1
            
            await message.answer(
                f"✅ Объявление отправлено!\n"
                f"Успешно: {success_count}\n"
                f"Ошибок: {fail_count}",
                reply_markup=get_admin_keyboard()
            )
            
    except Exception as e:
        logger.error(f"Error in process_announcement: {e}")
        await message.answer(
            "❌ Произошла ошибка при отправке объявления.",
            reply_markup=get_admin_keyboard()
        )
    
    await state.clear()

@router.message(F.text == "🔒 Заблокировать пользователя")
async def start_user_block(message: types.Message, state: FSMContext):
    """Начинает процесс блокировки пользователя"""
    if message.from_user.id not in ADMIN_IDS:
        return
    
    try:
        async with async_session() as session:
            # Получаем список пользователей
            users_query = select(User).order_by(User.created_at.desc()).limit(10)
            users_result = await session.execute(users_query)
            users = users_result.scalars().all()
            
            keyboard = []
            for user in users:
                status = "🔒" if user.is_blocked else "✅"
                keyboard.append([InlineKeyboardButton(
                    text=f"{status} @{user.username or 'Пользователь'} | ID: {user.telegram_id}",
                    callback_data=f"block_user:{user.telegram_id}"
                )])
            
            keyboard.append([InlineKeyboardButton(
                text="❌ Отмена",
                callback_data="cancel_admin_action"
            )])
            
            await state.set_state(AdminStates.selecting_user)
            await message.answer(
                "Выберите пользователя для блокировки/разблокировки:",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
            )
    except Exception as e:
        logger.error(f"Ошибка при показе списка пользователей для блокировки: {e}")
        await message.answer(
            "Произошла ошибка при загрузке списка пользователей.",
            reply_markup=get_admin_keyboard()
        )

@router.callback_query(lambda c: c.data.startswith("block_user:"))
async def process_user_block(callback: types.CallbackQuery):
    """Обрабатывает блокировку/разблокировку пользователя"""
    try:
        user_id = int(callback.data.split(":")[1])
        
        async with async_session() as session:
            user = await session.get(User, user_id)
            if not user:
                await callback.message.edit_text(
                    "❌ Пользователь не найден.",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(
                        text="↩️ Назад",
                        callback_data="cancel_admin_action"
                    )]])
                )
                return
            
            # Меняем статус блокировки
            user.is_blocked = not user.is_blocked
            await session.commit()
            
            # Уведомляем пользователя
            try:
                await callback.message.bot.send_message(
                    user_id,
                    f"🔒 Ваш аккаунт был {'заблокирован' if user.is_blocked else 'разблокирован'} администратором."
                )
            except Exception as e:
                logger.error(f"Failed to notify user {user_id} about block status: {e}")
            
            await callback.message.edit_text(
                f"✅ Пользователь успешно {'заблокирован' if user.is_blocked else 'разблокирован'}.",
                reply_markup=get_admin_keyboard()
            )
            
    except Exception as e:
        logger.error(f"Error in process_user_block: {e}")
        await callback.message.edit_text(
            "❌ Произошла ошибка при изменении статуса блокировки.",
            reply_markup=get_admin_keyboard()
        )

@router.message(F.text == "❌ Выйти из панели админа")
async def exit_admin_panel(message: types.Message):
    """Выход из панели администратора"""
    if message.from_user.id not in ADMIN_IDS:
        return
    
    await message.answer(
        "Вы вышли из панели администратора.",
        reply_markup=get_main_keyboard(message.from_user.id)
    )

@router.callback_query(lambda c: c.data == "cancel_admin_action")
async def cancel_admin_action(callback: types.CallbackQuery, state: FSMContext):
    """Отмена действия администратора"""
    await state.clear()
    await callback.message.edit_text(
        "❌ Действие отменено.",
        reply_markup=get_admin_keyboard()
    )

@router.callback_query(lambda c: c.data == "promo_codes")
async def show_promo_menu(callback: types.CallbackQuery):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Создать промокод", callback_data="create_promo")],
        [InlineKeyboardButton(text="📋 Список промокодов", callback_data="list_promos")],
        [InlineKeyboardButton(text="↩️ Назад", callback_data="back_to_admin")]
    ])
    
    await callback.message.edit_text(
        "🎁 Управление промокодами\n\n"
        "Выберите действие:",
        reply_markup=keyboard
    )

@router.callback_query(lambda c: c.data == "create_promo")
async def start_create_promo(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.creating_promo)
    await callback.message.edit_text(
        "Введите сумму промокода в ROXY:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_promo")
        ]])
    )

@router.message(AdminStates.creating_promo)
async def process_promo_amount(message: types.Message, state: FSMContext):
    try:
        amount = float(message.text)
        if amount <= 0:
            raise ValueError
        
        await state.update_data(promo_amount=amount)
        await state.set_state(AdminStates.entering_promo_code)
        
        await message.answer(
            "Введите код промокода (например: SUMMER2024):",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_promo")
            ]])
        )
    except ValueError:
        await message.answer(
            "❌ Пожалуйста, введите корректную сумму (например: 10.5):",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_promo")
            ]])
        )

@router.message(AdminStates.entering_promo_code)
async def process_promo_code(message: types.Message, state: FSMContext):
    code = message.text.upper()
    
    async with async_session() as session:
        # Проверяем, не существует ли уже такой промокод
        existing = await session.scalar(
            select(PromoCode).where(PromoCode.code == code)
        )
        
        if existing:
            await message.answer(
                "❌ Такой промокод уже существует. Введите другой код:",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_promo")
                ]])
            )
            return
    
    data = await state.get_data()
    amount = data['promo_amount']
    
    # Создаем промокод
    promo = PromoCode(
        code=code,
        amount=amount,
        created_by=message.from_user.id
    )
    
    async with async_session() as session:
        session.add(promo)
        await session.commit()
    
    await state.clear()
    await message.answer(
        f"✅ Промокод успешно создан!\n\n"
        f"Код: {code}\n"
        f"Сумма: {amount} ROXY",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="↩️ Назад", callback_data="promo_codes")
        ]])
    )

@router.callback_query(lambda c: c.data == "list_promos")
async def show_promos(callback: types.CallbackQuery):
    async with async_session() as session:
        promos = await session.scalars(
            select(PromoCode).order_by(PromoCode.created_at.desc())
        )
        promos = promos.all()
        
        if not promos:
            await callback.message.edit_text(
                "📋 Список промокодов пуст.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="↩️ Назад", callback_data="promo_codes")
                ]])
            )
            return
        
        text = "📋 Список промокодов:\n\n"
        for promo in promos:
            status = "✅ Использован" if promo.is_used else "🆕 Активен"
            used_by = f"\nИспользован: @{promo.used_by}" if promo.used_by else ""
            text += f"Код: {promo.code}\nСумма: {promo.amount} ROXY\n{status}{used_by}\n\n"
        
        await callback.message.edit_text(
            text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="↩️ Назад", callback_data="promo_codes")
            ]])
        )

@router.callback_query(lambda c: c.data == "cancel_promo")
async def cancel_promo(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await show_promo_menu(callback)

def register_admin_handlers(dp: Dispatcher):
    """Регистрация обработчиков для администраторов"""
    dp.include_router(router)

async def cmd_admin(message: Message):
    """Обработчик команды /admin"""
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("У вас нет доступа к панели администратора.")
        return
    
    await message.answer(
        "🔑 Панель администратора\n\n"
        "Доступные команды:\n"
        "/stats - Статистика\n"
        "/users - Управление пользователями\n"
        "/announce - Отправить объявление\n"
        "/block - Заблокировать пользователя\n"
        "/unblock - Разблокировать пользователя"
    )

    dp.message.register(cmd_admin, Command("admin")) 