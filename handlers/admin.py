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
from aiogram.filters import Command, StateFilter
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

@router.message(F.text == "👑 Админ панель")
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
            response = "👑 Панель администратора\n\n"
            response += f"📊 Статистика:\n"
            response += f"👥 Всего пользователей: {users_count}\n"
            response += f"📱 Активных объявлений: {active_listings}\n"
            response += f"⚠️ Открытых споров: {open_disputes}\n\n"
            
            if recent_transactions:
                response += "💳 Последние транзакции:\n"
                for tx in recent_transactions:
                    response += f"ID: {tx.id}\n"
                    response += f"Сумма: {tx.amount:.2f} ROXY\n"
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
                response += f"Баланс: {user.balance:.2f} ROXY\n"
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
                    text=f"👤 @{user.username or 'Пользователь'} | 💰 {user.balance:.2f} ROXY",
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
        "Введите сумму в ROXY:",
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
                f"✅ Баланс пользователя успешно {'пополнен' if action == 'add' else 'списан'} на {amount:.2f} ROXY\n"
                f"Текущий баланс: {user.balance:.2f} ROXY",
                reply_markup=get_admin_keyboard()
            )
            
            # Уведомляем пользователя
            try:
                await message.bot.send_message(
                    user_id,
                    f"💰 Ваш баланс был {'пополнен' if action == 'add' else 'списан'} на {amount:.2f} ROXY\n"
                    f"Текущий баланс: {user.balance:.2f} ROXY"
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

@router.message(F.text == "🎁 Управление промокодами")
async def show_promo_menu(message: types.Message):
    """Показывает меню управления промокодами"""
    if message.from_user.id not in ADMIN_IDS:
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Создать промокод", callback_data="create_promo")],
        [InlineKeyboardButton(text="📋 Список промокодов", callback_data="list_promos")],
        [InlineKeyboardButton(text="↩️ Назад", callback_data="back_to_admin")]
    ])
    
    await message.answer(
        "🎁 Управление промокодами\n\n"
        "Выберите действие:",
        reply_markup=keyboard
    )

@router.callback_query(lambda c: c.data == "back_to_admin")
async def back_to_admin(callback: types.CallbackQuery):
    """Возврат в главное меню админ-панели"""
    await callback.message.edit_text(
        "👑 Панель администратора\n\n"
        "Выберите действие:",
        reply_markup=get_admin_keyboard()
    )

@router.callback_query(lambda c: c.data == "create_promo")
async def create_promo(callback: types.CallbackQuery, state: FSMContext):
    """Начинает процесс создания промокода"""
    if not await check_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа к этой функции", show_alert=True)
        return
    
    await state.set_state("entering_promo_amount")
    await callback.message.edit_text(
        "Введите сумму промокода в ROXY:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_promo_creation")
        ]])
    )

@router.message(StateFilter("entering_promo_amount"))
async def process_promo_amount(message: types.Message, state: FSMContext):
    """Обрабатывает ввод суммы промокода"""
    try:
        amount = float(message.text)
        if amount <= 0:
            await message.answer(
                "❌ Сумма должна быть больше 0. Попробуйте еще раз:",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_promo_creation")
                ]])
            )
            return
        
        await state.update_data(promo_amount=amount)
        await state.set_state("entering_promo_uses")
        
        await message.answer(
            "Введите максимальное количество использований (1-1000):",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_promo_creation")
            ]])
        )
    except ValueError:
        await message.answer(
            "❌ Пожалуйста, введите корректное число. Попробуйте еще раз:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_promo_creation")
            ]])
        )

@router.message(StateFilter("entering_promo_uses"))
async def process_promo_uses(message: types.Message, state: FSMContext):
    """Обрабатывает ввод количества использований"""
    try:
        max_uses = int(message.text)
        if max_uses < 1 or max_uses > 1000:
            await message.answer(
                "❌ Количество использований должно быть от 1 до 1000. Попробуйте еще раз:",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_promo_creation")
                ]])
            )
            return
        
        await state.update_data(promo_uses=max_uses)
        await state.set_state("entering_promo_codes")
        
        await message.answer(
            "Введите промокоды (по одному в строке):\n"
            "Например:\n"
            "PROMO1\n"
            "PROMO2\n"
            "PROMO3",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_promo_creation")
            ]])
        )
    except ValueError:
        await message.answer(
            "❌ Пожалуйста, введите корректное число. Попробуйте еще раз:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_promo_creation")
            ]])
        )

@router.message(StateFilter("entering_promo_codes"))
async def process_promo_codes(message: types.Message, state: FSMContext):
    """Обрабатывает ввод промокодов"""
    try:
        data = await state.get_data()
        amount = data['promo_amount']
        max_uses = data['promo_uses']
        
        # Разбиваем текст на строки и очищаем от пробелов
        codes = [code.strip().upper() for code in message.text.split('\n') if code.strip()]
        
        if not codes:
            await message.answer(
                "❌ Пожалуйста, введите хотя бы один промокод. Попробуйте еще раз:",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_promo_creation")
                ]])
            )
            return
        
        async with async_session() as session:
            created_count = 0
            failed_codes = []
            
            for code in codes:
                try:
                    promo = PromoCode(
                        code=code,
                        amount=amount,
                        max_uses=max_uses,
                        current_uses=0,
                        is_active=True,
                        created_by=message.from_user.id,
                        created_at=datetime.utcnow()
                    )
                    session.add(promo)
                    created_count += 1
                except Exception as e:
                    logger.error(f"Failed to create promo code {code}: {e}")
                    failed_codes.append(code)
            
            await session.commit()
            
            response = f"✅ Создано промокодов: {created_count}\n"
            response += f"Сумма: {amount} ROXY\n"
            response += f"Использований: {max_uses}\n\n"
            
            if failed_codes:
                response += "❌ Не удалось создать следующие промокоды:\n"
                response += "\n".join(failed_codes)
            
            await message.answer(
                response,
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="↩️ Назад", callback_data="back_to_admin")
                ]])
            )
            await state.clear()
            
    except Exception as e:
        logger.error(f"Error in process_promo_codes: {e}")
        await message.answer(
            "❌ Произошла ошибка при создании промокодов.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="↩️ Назад", callback_data="back_to_admin")
            ]])
        )
        await state.clear()

@router.callback_query(lambda c: c.data == "list_promos")
async def show_promos(callback: types.CallbackQuery):
    """Показывает список всех промокодов"""
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

@router.callback_query(lambda c: c.data == "cancel_promo_creation")
async def cancel_promo_creation(callback: types.CallbackQuery, state: FSMContext):
    """Отменяет создание промокода"""
    await state.clear()
    await callback.message.edit_text(
        "❌ Создание промокода отменено.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="↩️ Назад", callback_data="back_to_admin")
        ]])
    )

@router.callback_query(lambda c: c.data == "manage_disputes")
async def manage_disputes(callback: types.CallbackQuery):
    """Показывает список активных споров"""
    if not await check_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа к этой функции", show_alert=True)
        return
    
    try:
        async with async_session() as session:
            # Получаем активные споры
            disputes = await session.scalars(
                select(Dispute)
                .where(Dispute.status == "active")
                .order_by(Dispute.created_at.desc())
            )
            disputes = disputes.all()
            
            if not disputes:
                await callback.message.edit_text(
                    "📋 Активных споров нет.",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                        InlineKeyboardButton(text="↩️ Назад", callback_data="back_to_admin")
                    ]])
                )
                return
            
            # Формируем список споров
            text = "📋 Активные споры:\n\n"
            keyboard = []
            
            for dispute in disputes:
                transaction = await session.get(Transaction, dispute.transaction_id)
                if not transaction:
                    continue
                
                buyer = await session.get(User, dispute.buyer_id)
                seller = await session.get(User, dispute.seller_id)
                
                if not buyer or not seller:
                    continue
                
                text += (
                    f"ID спора: {dispute.id}\n"
                    f"Сумма: {transaction.amount:.2f} ROXY\n"
                    f"Покупатель: @{buyer.username or 'Пользователь'}\n"
                    f"Продавец: @{seller.username or 'Пользователь'}\n"
                    f"Дата: {dispute.created_at.strftime('%d.%m.%Y %H:%M')}\n\n"
                )
                
                keyboard.append([InlineKeyboardButton(
                    text=f"⚖️ Решить спор #{dispute.id}",
                    callback_data=f"resolve_dispute:{dispute.id}"
                )])
            
            keyboard.append([InlineKeyboardButton(
                text="↩️ Назад",
                callback_data="back_to_admin"
            )])
            
            await callback.message.edit_text(
                text,
                reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
            )
            
    except Exception as e:
        logger.error(f"Error in manage_disputes: {e}")
        await callback.answer("❌ Произошла ошибка при загрузке споров", show_alert=True)

@router.callback_query(lambda c: c.data.startswith("resolve_dispute:"))
async def resolve_dispute(callback: types.CallbackQuery):
    """Показывает меню для решения спора"""
    if not await check_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа к этой функции", show_alert=True)
        return
    
    try:
        dispute_id = int(callback.data.split(":")[1])
        
        async with async_session() as session:
            dispute = await session.get(Dispute, dispute_id)
            if not dispute or dispute.status != "active":
                await callback.answer("❌ Спор не найден или уже решен", show_alert=True)
                return
            
            transaction = await session.get(Transaction, dispute.transaction_id)
            buyer = await session.get(User, dispute.buyer_id)
            seller = await session.get(User, dispute.seller_id)
            
            if not all([transaction, buyer, seller]):
                await callback.answer("❌ Ошибка: данные не найдены", show_alert=True)
                return
            
            keyboard = [
                [
                    InlineKeyboardButton(
                        text="👤 Покупатель",
                        callback_data=f"dispute_winner:{dispute_id}:buyer"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="👤 Продавец",
                        callback_data=f"dispute_winner:{dispute_id}:seller"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="↩️ Назад",
                        callback_data="manage_disputes"
                    )
                ]
            ]
            
            await callback.message.edit_text(
                f"⚖️ Решение спора #{dispute.id}\n\n"
                f"Сумма: {transaction.amount:.2f} ROXY\n"
                f"Покупатель: @{buyer.username or 'Пользователь'}\n"
                f"Продавец: @{seller.username or 'Пользователь'}\n\n"
                "Выберите победителя спора:",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
            )
            
    except Exception as e:
        logger.error(f"Error in resolve_dispute: {e}")
        await callback.answer("❌ Произошла ошибка при решении спора", show_alert=True)

@router.callback_query(lambda c: c.data.startswith("dispute_winner:"))
async def process_dispute_winner(callback: types.CallbackQuery):
    """Обрабатывает выбор победителя спора"""
    if not await check_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа к этой функции", show_alert=True)
        return
    
    try:
        _, dispute_id, winner = callback.data.split(":")
        dispute_id = int(dispute_id)
        
        async with async_session() as session:
            dispute = await session.get(Dispute, dispute_id)
            if not dispute or dispute.status != "active":
                await callback.answer("❌ Спор не найден или уже решен", show_alert=True)
                return
            
            transaction = await session.get(Transaction, dispute.transaction_id)
            buyer = await session.get(User, dispute.buyer_id)
            seller = await session.get(User, dispute.seller_id)
            
            if not all([transaction, buyer, seller]):
                await callback.answer("❌ Ошибка: данные не найдены", show_alert=True)
                return
            
            # Определяем победителя
            winner_id = buyer.telegram_id if winner == "buyer" else seller.telegram_id
            winner_user = buyer if winner == "buyer" else seller
            
            # Переводим средства победителю
            winner_user.balance += transaction.amount
            
            # Обновляем статусы
            dispute.status = "resolved"
            dispute.winner_id = winner_id
            transaction.status = "completed"
            
            await session.commit()
            
            # Уведомляем участников
            await callback.bot.send_message(
                buyer.telegram_id,
                f"⚖️ Спор #{dispute.id} решен!\n\n"
                f"Победитель: @{winner_user.username or 'Пользователь'}\n"
                f"Сумма: {transaction.amount:.2f} ROXY"
            )
            
            await callback.bot.send_message(
                seller.telegram_id,
                f"⚖️ Спор #{dispute.id} решен!\n\n"
                f"Победитель: @{winner_user.username or 'Пользователь'}\n"
                f"Сумма: {transaction.amount:.2f} ROXY"
            )
            
            # Возвращаемся к списку споров
            await callback.message.edit_text(
                f"✅ Спор #{dispute.id} успешно решен!\n\n"
                f"Победитель: @{winner_user.username or 'Пользователь'}\n"
                f"Сумма: {transaction.amount:.2f} ROXY",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="↩️ Назад к спорам", callback_data="manage_disputes")
                ]])
            )
            
    except Exception as e:
        logger.error(f"Error in process_dispute_winner: {e}")
        await callback.answer("❌ Произошла ошибка при обработке решения спора", show_alert=True)

@router.callback_query(lambda c: c.data.startswith("delete_promo:"))
async def delete_promo(callback: types.CallbackQuery):
    """Удаляет промокод"""
    if not await check_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа к этой функции", show_alert=True)
        return
    
    try:
        promo_id = int(callback.data.split(":")[1])
        
        async with async_session() as session:
            promo = await session.get(PromoCode, promo_id)
            if not promo:
                await callback.answer("❌ Промокод не найден", show_alert=True)
                return
            
            # Удаляем промокод
            await session.delete(promo)
            await session.commit()
            
            await callback.message.edit_text(
                f"✅ Промокод {promo.code} успешно удален!",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="↩️ Назад", callback_data="back_to_admin")
                ]])
            )
            
    except Exception as e:
        logger.error(f"Error in delete_promo: {e}")
        await callback.answer("❌ Произошла ошибка при удалении промокода", show_alert=True)

def register_admin_handlers(dp: Dispatcher):
    """Регистрация обработчиков для администраторов"""
    dp.include_router(router)
    
    # Регистрируем все обработчики промокодов
    dp.callback_query.register(show_promo_menu, F.data == "promo_codes")
    dp.callback_query.register(create_promo, F.data == "create_promo")
    dp.callback_query.register(show_promos, F.data == "list_promos")
    dp.callback_query.register(cancel_promo_creation, F.data == "cancel_promo_creation")
    dp.callback_query.register(back_to_admin, F.data == "back_to_admin")

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