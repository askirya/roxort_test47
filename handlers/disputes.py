from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from database.db import get_session, async_session
from database.models import User, Transaction, Dispute
from datetime import datetime
from sqlalchemy import select, and_, or_
from config import ADMIN_IDS
from handlers.common import get_main_keyboard, check_user_registered
from log import logger
import logging
from aiogram import Dispatcher
from aiogram.filters import Command
from aiogram.types import Message

router = Router()

logger = logging.getLogger(__name__)

class DisputeStates(StatesGroup):
    entering_description = State()
    selecting_transaction = State()
    confirming = State()

def get_dispute_keyboard(transaction_id: int):
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="📝 Открыть спор",
                callback_data=f"open_dispute:{transaction_id}"
            )],
            [InlineKeyboardButton(
                text="❌ Отмена",
                callback_data="cancel_dispute"
            )]
        ]
    )
    return keyboard

def get_admin_dispute_keyboard(dispute_id: int):
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Вернуть средства покупателю", 
                                   callback_data=f"resolve_buyer_{dispute_id}"),
                InlineKeyboardButton(text="💰 Передать средства продавцу", 
                                   callback_data=f"resolve_seller_{dispute_id}")
            ],
            [
                InlineKeyboardButton(text="❌ Закрыть спор", 
                                   callback_data=f"close_dispute_{dispute_id}")
            ]
        ]
    )
    return keyboard

@router.message(lambda message: message.text == "⚠️ Споры")
async def show_disputes_menu(message: types.Message):
    async with async_session() as session:
        try:
            # Проверяем регистрацию пользователя
            query = select(User).where(User.telegram_id == message.from_user.id)
            result = await session.execute(query)
            user = result.scalar_one_or_none()
            
            if not user:
                await message.answer(
                    "❌ Вы не зарегистрированы!\n"
                    "Пожалуйста, пройдите регистрацию сначала.",
                    reply_markup=get_main_keyboard()
                )
                return

            # Получаем активные споры пользователя
            disputes_query = select(Dispute).where(
                and_(
                    Dispute.user_id == message.from_user.id,
                    Dispute.status == "open"
                )
            )
            disputes_result = await session.execute(disputes_query)
            disputes = disputes_result.scalars().all()

            if not disputes:
                await message.answer(
                    "✅ У вас нет активных споров.\n\n"
                    "Если у вас возникли проблемы с транзакцией:\n"
                    "1. Перейдите в раздел 'Мои объявления'\n"
                    "2. Выберите проблемную транзакцию\n"
                    "3. Нажмите кнопку 'Открыть спор'\n"
                    "4. Опишите возникшую проблему\n\n"
                    "Администрация рассмотрит ваше обращение в течение 24 часов.",
                    reply_markup=get_main_keyboard(message.from_user.id)
                )
                return

            # Формируем список активных споров
            disputes_text = "🚨 Ваши активные споры:\n\n"
            for dispute in disputes:
                # Получаем информацию о транзакции
                tx_query = select(Transaction).where(Transaction.id == dispute.transaction_id)
                tx_result = await session.execute(tx_query)
                transaction = tx_result.scalar_one_or_none()

                if transaction:
                    disputes_text += (
                        f"ID спора: #{dispute.id}\n"
                        f"Транзакция: #{transaction.id}\n"
                        f"Статус: ⏳ На рассмотрении\n"
                        f"Описание: {dispute.description}\n"
                        f"Создан: {dispute.created_at.strftime('%d.%m.%Y %H:%M')}\n"
                        f"Сумма: {transaction.amount} USDT\n\n"
                    )

            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Обновить", callback_data="refresh_disputes")]
            ])

            await message.answer(
                disputes_text,
                reply_markup=keyboard
            )

        except Exception as e:
            logger.error(f"Error in disputes menu: {e}")
            await message.answer(
                "❌ Произошла ошибка при загрузке споров.\n"
                "Пожалуйста, попробуйте позже.",
                reply_markup=get_main_keyboard(message.from_user.id)
            )
        finally:
            await session.close()

@router.callback_query(lambda c: c.data == "refresh_disputes")
async def refresh_disputes(callback: types.CallbackQuery):
    async with async_session() as session:
        try:
            # Получаем активные споры пользователя
            disputes_query = select(Dispute).where(
                and_(
                    Dispute.user_id == callback.from_user.id,
                    Dispute.status == "open"
                )
            )
            disputes_result = await session.execute(disputes_query)
            disputes = disputes_result.scalars().all()

            if not disputes:
                await callback.message.edit_text(
                    "✅ У вас нет активных споров.",
                    reply_markup=None
                )
                return

            # Формируем обновленный список споров
            disputes_text = "🚨 Ваши активные споры:\n\n"
            for dispute in disputes:
                tx_query = select(Transaction).where(Transaction.id == dispute.transaction_id)
                tx_result = await session.execute(tx_query)
                transaction = tx_result.scalar_one_or_none()

                if transaction:
                    disputes_text += (
                        f"ID спора: #{dispute.id}\n"
                        f"Транзакция: #{transaction.id}\n"
                        f"Статус: ⏳ На рассмотрении\n"
                        f"Описание: {dispute.description}\n"
                        f"Создан: {dispute.created_at.strftime('%d.%m.%Y %H:%M')}\n"
                        f"Сумма: {transaction.amount} USDT\n\n"
                    )

            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Обновить", callback_data="refresh_disputes")]
            ])

            await callback.message.edit_text(
                disputes_text,
                reply_markup=keyboard
            )

        except Exception as e:
            logger.error(f"Error refreshing disputes: {e}")
            await callback.answer("❌ Ошибка при обновлении списка споров", show_alert=True)
        finally:
            await session.close()

@router.callback_query(lambda c: c.data.startswith("select_transaction:"))
async def process_transaction_selection(callback: types.CallbackQuery, state: FSMContext):
    transaction_id = int(callback.data.split(":")[1])
    await state.update_data(transaction_id=transaction_id)
    await state.set_state(DisputeStates.entering_description)
    
    await callback.message.edit_text(
        "Опишите причину спора:\n"
        "Будьте максимально конкретны и предоставьте все необходимые детали."
    )

@router.message(DisputeStates.entering_description)
async def process_dispute_description(message: types.Message, state: FSMContext):
    description = message.text.strip()
    if len(description) < 10:
        await message.answer(
            "❌ Описание слишком короткое.\n"
            "Пожалуйста, предоставьте более подробное описание проблемы."
        )
        return
    
    data = await state.get_data()
    transaction_id = data['transaction_id']
    
    async with await get_session() as session:
        # Создаем спор
        dispute = Dispute(
            transaction_id=transaction_id,
            description=description,
            status="open",
            created_at=datetime.utcnow()
        )
        session.add(dispute)
        
        # Обновляем статус транзакции
        transaction = await session.get(Transaction, transaction_id)
        transaction.status = "disputed"
        
        await session.commit()
        
        # Уведомляем администраторов
        for admin_id in ADMIN_IDS:
            try:
                await message.bot.send_message(
                    admin_id,
                    f"⚠️ Новый спор #{dispute.id}\n"
                    f"Транзакция: #{transaction_id}\n"
                    f"Сумма: {transaction.amount} USDT\n"
                    f"Описание: {description}"
                )
            except Exception as e:
                logger.error(f"Failed to notify admin {admin_id}: {e}")
        
        await message.answer(
            "✅ Спор успешно открыт!\n"
            "Администрация рассмотрит ваше обращение в ближайшее время.",
            reply_markup=get_main_keyboard(message.from_user.id)
        )
    
    await state.clear()

@router.callback_query(lambda c: c.data == "cancel_dispute")
async def cancel_dispute(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "❌ Открытие спора отменено.",
        reply_markup=get_main_keyboard(callback.from_user.id)
    )

@router.message(F.text == "📋 Мои споры")
async def show_my_disputes(message: types.Message):
    async with await get_session() as session:
        # Получаем все споры пользователя
        query = select(Dispute).where(
            Dispute.initiator_id == message.from_user.id
        ).order_by(Dispute.created_at.desc())
        
        result = await session.execute(query)
        disputes = result.scalars().all()
        
        if not disputes:
            await message.answer("У вас нет открытых споров.")
            return
        
        for dispute in disputes:
            transaction = await session.get(Transaction, dispute.transaction_id)
            listing = await session.get(PhoneListing, transaction.listing_id)
            
            status_emoji = {
                "open": "🔴",
                "resolved": "✅",
                "closed": "⚫️"
            }
            
            await message.answer(
                f"{status_emoji.get(dispute.status, '❓')} Спор #{dispute.id}\n\n"
                f"📱 Сервис: {listing.service}\n"
                f"💰 Сумма: {transaction.amount} USDT\n"
                f"📅 Создан: {dispute.created_at.strftime('%d.%m.%Y %H:%M')}\n"
                f"📝 Статус: {dispute.status}\n"
                f"ℹ️ Описание: {dispute.description}"
            )

@router.callback_query(lambda c: c.data.startswith('resolve_'))
async def resolve_dispute(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ У вас нет прав администратора!")
        return
    
    action, dispute_id = callback.data.split('_')[1:]
    dispute_id = int(dispute_id)
    
    async with await get_session() as session:
        dispute = await session.get(Dispute, dispute_id)
        if not dispute or dispute.status != "open":
            await callback.answer("❌ Спор уже закрыт или не существует!")
            return
        
        transaction = await session.get(Transaction, dispute.transaction_id)
        buyer = await session.get(User, transaction.buyer_id)
        seller = await session.get(User, transaction.seller_id)
        
        if action == "buyer":
            # Возвращаем средства покупателю
            buyer.balance += transaction.amount
            transaction.status = "refunded"
            dispute.status = "resolved"
            
            await callback.message.edit_text(
                f"✅ Спор #{dispute_id} разрешен в пользу покупателя\n"
                f"💰 Сумма {transaction.amount} USDT возвращена покупателю."
            )
            
            # Уведомляем покупателя
            await callback.bot.send_message(
                buyer.telegram_id,
                f"✅ Ваш спор #{dispute_id} разрешен!\n"
                f"💰 Сумма {transaction.amount} USDT возвращена на ваш баланс."
            )
            
        elif action == "seller":
            # Передаем средства продавцу
            seller.balance += transaction.amount
            transaction.status = "completed"
            dispute.status = "resolved"
            
            await callback.message.edit_text(
                f"✅ Спор #{dispute_id} разрешен в пользу продавца\n"
                f"💰 Сумма {transaction.amount} USDT передана продавцу."
            )
            
            # Уведомляем продавца
            await callback.bot.send_message(
                seller.telegram_id,
                f"✅ Спор по сделке разрешен в вашу пользу!\n"
                f"💰 Сумма {transaction.amount} USDT зачислена на ваш баланс."
            )
        
        await session.commit()

@router.callback_query(lambda c: c.data.startswith('close_dispute_'))
async def close_dispute(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ У вас нет прав администратора!")
        return
    
    dispute_id = int(callback.data.split('_')[2])
    
    async with await get_session() as session:
        dispute = await session.get(Dispute, dispute_id)
        if not dispute or dispute.status != "open":
            await callback.answer("❌ Спор уже закрыт или не существует!")
            return
        
        dispute.status = "closed"
        await session.commit()
        
        await callback.message.edit_text(
            f"⚫️ Спор #{dispute_id} закрыт администратором."
        )

async def cmd_dispute(message: Message):
    """Обработчик команды /dispute"""
    try:
        async with async_session() as session:
            user = await session.get(User, message.from_user.id)
            if not user:
                await message.answer("Пожалуйста, сначала зарегистрируйтесь с помощью команды /start")
                return
            
            # Получаем активные споры пользователя
            disputes = await session.query(Dispute).filter(
                Dispute.user_id == user.id,
                Dispute.status == "open"
            ).all()
            
            if not disputes:
                await message.answer("У вас нет активных споров.")
                return
            
            # Формируем сообщение со спорами
            response = "⚠️ Ваши активные споры:\n\n"
            for dispute in disputes:
                response += f"ID спора: {dispute.id}\n"
                response += f"Статус: {dispute.status}\n"
                response += f"Дата создания: {dispute.created_at.strftime('%d.%m.%Y %H:%M')}\n"
                response += f"Описание: {dispute.description}\n\n"
            
            await message.answer(response)
    except Exception as e:
        logger.error(f"Ошибка при обработке команды /dispute: {e}")
        await message.answer("Произошла ошибка. Пожалуйста, попробуйте позже.")

def register_dispute_handlers(dp: Dispatcher):
    """Регистрация обработчиков для споров"""
    dp.message.register(cmd_dispute, Command("dispute"))
    dp.include_router(router) 