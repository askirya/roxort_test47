from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from database.db import get_session, async_session
from database.models import User, Transaction, Dispute, PhoneListing, Review
from datetime import datetime, timedelta
from sqlalchemy import select, and_, or_, func
from config import ADMIN_IDS
import logging
from aiogram import Dispatcher
from aiogram.filters import Command
from aiogram.types import Message

logger = logging.getLogger(__name__)

router = Router()

class AdminStates(StatesGroup):
    waiting_for_user_id = State()
    entering_balance = State()
    entering_announcement = State()

def get_admin_keyboard():
    """Создает клавиатуру администратора"""
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

async def check_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

@router.message(lambda message: message.text == "🔑 Панель администратора")
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

@router.message(lambda message: message.text == "📊 Статистика")
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
            
            response = "📊 Подробная статистика:\n\n"
            response += f"💰 Общий объем сделок: {total_volume:.2f} USDT\n"
            response += f"✅ Завершенных сделок: {completed_tx}\n"
            response += f"⭐️ Средний рейтинг: {avg_rating:.1f}\n"
            
            await message.answer(response, reply_markup=get_admin_keyboard())
    except Exception as e:
        logger.error(f"Ошибка при показе статистики: {e}")
        await message.answer(
            "Произошла ошибка при загрузке статистики.",
            reply_markup=get_admin_keyboard()
        )

@router.message(lambda message: message.text == "👥 Пользователи")
async def show_users(message: types.Message):
    """Показывает список пользователей"""
    if message.from_user.id not in ADMIN_IDS:
        return
    
    try:
        async with async_session() as session:
            # Получаем последних зарегистрированных пользователей
            users_query = select(User).order_by(User.created_at.desc()).limit(5)
            users_result = await session.execute(users_query)
            recent_users = users_result.scalars().all()
            
            response = "👥 Последние зарегистрированные пользователи:\n\n"
            for user in recent_users:
                response += f"ID: {user.telegram_id}\n"
                response += f"Username: @{user.username}\n"
                response += f"Баланс: {user.balance} USDT\n"
                response += f"Рейтинг: {user.rating:.1f}\n"
                response += f"Дата регистрации: {user.created_at.strftime('%d.%m.%Y %H:%M')}\n\n"
            
            await message.answer(response, reply_markup=get_admin_keyboard())
    except Exception as e:
        logger.error(f"Ошибка при показе пользователей: {e}")
        await message.answer(
            "Произошла ошибка при загрузке списка пользователей.",
            reply_markup=get_admin_keyboard()
        )

@router.message(lambda message: message.text == "↩️ Назад")
async def back_to_main(message: types.Message):
    """Возврат в главное меню"""
    await message.answer(
        "Главное меню:",
        reply_markup=get_main_keyboard(message.from_user.id)
    )

@router.message(lambda message: message.text == "💰 Управление балансами")
async def manage_balance_start(message: types.Message, state: FSMContext):
    if not await check_admin(message.from_user.id):
        return
    
    await state.set_state(AdminStates.waiting_for_user_id)
    await message.answer(
        "Введите ID пользователя для управления балансом:",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="❌ Отмена")]],
            resize_keyboard=True
        )
    )

@router.message(AdminStates.waiting_for_user_id)
async def process_user_id(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer(
            "Операция отменена.",
            reply_markup=get_admin_keyboard()
        )
        return
    
    try:
        user_id = int(message.text)
        async with await get_session() as session:
            user = await session.get(User, user_id)
            if not user:
                await message.answer("❌ Пользователь не найден!")
                return
            
            await state.update_data(user_id=user_id)
            await state.set_state(AdminStates.entering_balance)
            
            await message.answer(
                f"Текущий баланс пользователя: {user.balance} USDT\n"
                "Введите новый баланс:"
            )
    except:
        await message.answer("❌ Введите корректный ID пользователя!")

@router.message(AdminStates.entering_balance)
async def process_new_balance(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer(
            "Операция отменена.",
            reply_markup=get_admin_keyboard()
        )
        return
    
    try:
        new_balance = float(message.text)
        data = await state.get_data()
        user_id = data['user_id']
        
        async with await get_session() as session:
            user = await session.get(User, user_id)
            old_balance = user.balance
            user.balance = new_balance
            await session.commit()
            
            await message.answer(
                f"✅ Баланс пользователя обновлен!\n"
                f"Старый баланс: {old_balance} USDT\n"
                f"Новый баланс: {new_balance} USDT",
                reply_markup=get_admin_keyboard()
            )
            
            # Уведомляем пользователя
            await message.bot.send_message(
                user.telegram_id,
                f"💰 Ваш баланс был изменен администратором\n"
                f"Новый баланс: {new_balance} USDT"
            )
    except:
        await message.answer("❌ Введите корректную сумму!")
    
    await state.clear()

@router.message(lambda message: message.text == "⚠️ Активные споры")
async def show_active_disputes(message: types.Message):
    if not await check_admin(message.from_user.id):
        return
    
    async with await get_session() as session:
        query = select(Dispute).where(Dispute.status == "open")
        result = await session.execute(query)
        disputes = result.scalars().all()
        
        if not disputes:
            await message.answer("✅ Активных споров нет!")
            return
        
        for dispute in disputes:
            transaction = await session.get(Transaction, dispute.transaction_id)
            buyer = await session.get(User, transaction.buyer_id)
            seller = await session.get(User, transaction.seller_id)
            
            await message.answer(
                f"⚠️ Спор #{dispute.id}\n\n"
                f"Покупатель: @{buyer.username or buyer.telegram_id}\n"
                f"Продавец: @{seller.username or seller.telegram_id}\n"
                f"Сумма: {transaction.amount} USDT\n"
                f"Описание: {dispute.description}\n"
                f"Создан: {dispute.created_at.strftime('%d.%m.%Y %H:%M')}",
                reply_markup=get_admin_dispute_keyboard(dispute.id)
            )

@router.message(lambda message: message.text == "📢 Сделать объявление")
async def start_announcement(message: types.Message, state: FSMContext):
    if not await check_admin(message.from_user.id):
        return
    
    await state.set_state(AdminStates.entering_announcement)
    await message.answer(
        "Введите текст объявления для всех пользователей:",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="❌ Отмена")]],
            resize_keyboard=True
        )
    )

@router.message(AdminStates.entering_announcement)
async def process_announcement(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer(
            "Операция отменена.",
            reply_markup=get_admin_keyboard()
        )
        return
    
    async with await get_session() as session:
        try:
            query = select(User)
            result = await session.execute(query)
            users = result.scalars().all()
            
            sent_count = 0
            failed_count = 0
            
            for user in users:
                try:
                    await message.bot.send_message(
                        user.telegram_id,
                        f"📢 Объявление от администрации:\n\n{message.text}"
                    )
                    sent_count += 1
                except Exception as e:
                    logger.error(f"Failed to send announcement to user {user.telegram_id}: {e}")
                    failed_count += 1
            
            await message.answer(
                f"✅ Объявление отправлено!\n"
                f"Успешно: {sent_count}\n"
                f"Ошибок: {failed_count}",
                reply_markup=get_admin_keyboard()
            )
            
        except Exception as e:
            logger.error(f"Error sending announcement: {e}")
            await message.answer(
                "❌ Произошла ошибка при отправке объявления.",
                reply_markup=get_admin_keyboard()
            )
    
    await state.clear()

@router.message(lambda message: message.text == "🔒 Заблокировать пользователя")
async def block_user_start(message: types.Message, state: FSMContext):
    if not await check_admin(message.from_user.id):
        return
    
    await state.set_state(AdminStates.waiting_for_user_id)
    await message.answer(
        "Введите ID пользователя для блокировки/разблокировки:",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="❌ Отмена")]],
            resize_keyboard=True
        )
    )

@router.message(AdminStates.waiting_for_user_id)
async def process_block_user(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer(
            "Операция отменена.",
            reply_markup=get_admin_keyboard()
        )
        return
    
    try:
        user_id = int(message.text)
        async with await get_session() as session:
            user = await session.get(User, user_id)
            if not user:
                await message.answer("❌ Пользователь не найден!")
                return
            
            # Инвертируем статус блокировки
            user.is_blocked = not user.is_blocked
            await session.commit()
            
            status = "заблокирован" if user.is_blocked else "разблокирован"
            await message.answer(
                f"✅ Пользователь {status}!\n"
                f"ID: {user.telegram_id}\n"
                f"Username: @{user.username or 'Нет'}",
                reply_markup=get_admin_keyboard()
            )
            
            # Уведомляем пользователя
            await message.bot.send_message(
                user.telegram_id,
                f"⚠️ Ваш аккаунт был {status} администратором."
            )
            
    except Exception as e:
        logger.error(f"Error blocking user: {e}")
        await message.answer("❌ Произошла ошибка при блокировке пользователя.")
    
    await state.clear()

@router.callback_query(lambda c: c.data.startswith("resolve_dispute_"))
async def resolve_dispute(callback: types.CallbackQuery):
    if not await check_admin(callback.from_user.id):
        return
    
    try:
        _, _, winner, dispute_id = callback.data.split("_")
        dispute_id = int(dispute_id)
        
        async with await get_session() as session:
            dispute = await session.get(Dispute, dispute_id)
            if not dispute or dispute.status != "open":
                await callback.message.edit_text("❌ Спор не найден или уже закрыт.")
                return
            
            transaction = await session.get(Transaction, dispute.transaction_id)
            buyer = await session.get(User, transaction.buyer_id)
            seller = await session.get(User, transaction.seller_id)
            
            if winner == "buyer":
                # Возвращаем деньги покупателю
                buyer.balance += transaction.amount
                seller.balance -= transaction.amount
                resolution_text = "в пользу покупателя"
            else:
                # Оставляем деньги продавцу
                resolution_text = "в пользу продавца"
            
            # Закрываем спор
            dispute.status = "resolved"
            dispute.resolved_at = datetime.utcnow()
            dispute.resolved_by = callback.from_user.id
            dispute.resolution = resolution_text
            
            await session.commit()
            
            # Уведомляем участников
            await callback.message.edit_text(
                f"✅ Спор #{dispute_id} закрыт {resolution_text}.\n"
                f"Решение принято администратором @{callback.from_user.username or callback.from_user.id}"
            )
            
            # Уведомляем покупателя
            await callback.bot.send_message(
                buyer.telegram_id,
                f"✅ Спор по транзакции #{transaction.id} закрыт {resolution_text}."
            )
            
            # Уведомляем продавца
            await callback.bot.send_message(
                seller.telegram_id,
                f"✅ Спор по транзакции #{transaction.id} закрыт {resolution_text}."
            )
            
    except Exception as e:
        logger.error(f"Error resolving dispute: {e}")
        await callback.message.edit_text("❌ Произошла ошибка при закрытии спора.")

@router.message(lambda message: message.text == "❌ Выйти из панели админа")
async def exit_admin_panel(message: types.Message):
    if not await check_admin(message.from_user.id):
        return
    
    from handlers.common import get_main_keyboard
    await message.answer(
        "👋 Вы вышли из панели администратора",
        reply_markup=get_main_keyboard()
    )

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

def register_admin_handlers(dp: Dispatcher):
    """Регистрация обработчиков для администраторов"""
    dp.message.register(cmd_admin, Command("admin"))
    dp.include_router(router) 