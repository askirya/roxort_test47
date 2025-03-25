from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from database.db import async_session
from database.models import User, Transaction, Review, PhoneListing
from datetime import datetime, timedelta
from sqlalchemy import select, and_, or_
from handlers.common import get_main_keyboard, check_user_registered
import logging
from aiogram import Dispatcher
from aiogram.filters import Command
from aiogram.types import Message

router = Router()
logger = logging.getLogger(__name__)

class ReviewStates(StatesGroup):
    selecting_transaction = State()
    entering_rating = State()
    entering_comment = State()

def get_rating_keyboard():
    keyboard = []
    for rating in range(1, 6):
        keyboard.append([InlineKeyboardButton(
            text="⭐" * rating,
            callback_data=f"rate:{rating}"
        )])
    keyboard.append([InlineKeyboardButton(
        text="❌ Отмена",
        callback_data="cancel_review"
    )])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

@router.message(F.text == "⭐️ Отзывы")
async def show_rating_menu(message: types.Message, state: FSMContext):
    if not await check_user_registered(message.from_user.id):
        await message.answer(
            "❌ Вы не зарегистрированы!\n"
            "Пожалуйста, пройдите регистрацию:",
            reply_markup=get_main_keyboard()
        )
        return

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📝 Оставить отзыв", callback_data="leave_review")],
            [InlineKeyboardButton(text="👤 Мои отзывы", callback_data="my_reviews")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_review")]
        ]
    )
    
    await message.answer(
        "⭐️ Меню отзывов:\n"
        "Выберите действие:",
        reply_markup=keyboard
    )

@router.callback_query(lambda c: c.data == "leave_review")
async def start_review(callback: types.CallbackQuery, state: FSMContext):
    week_ago = datetime.utcnow() - timedelta(days=7)
    
    async with async_session() as session:
        # Получаем завершенные транзакции за последние 7 дней
        query = select(Transaction).where(
            and_(
                or_(
                    Transaction.buyer_id == callback.from_user.id,
                    Transaction.seller_id == callback.from_user.id
                ),
                Transaction.status == "completed",
                Transaction.completed_at >= week_ago
            )
        )
        result = await session.execute(query)
        transactions = result.scalars().all()
        
        if not transactions:
            await callback.message.edit_text(
                "У вас нет завершенных сделок за последние 7 дней.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(
                    text="↩️ Назад",
                    callback_data="cancel_review"
                )]])
            )
            return
        
        # Создаем клавиатуру с транзакциями
        keyboard = []
        for tx in transactions:
            # Проверяем, не оставлен ли уже отзыв
            review_exists = await session.scalar(
                select(Review).where(Review.transaction_id == tx.id)
            )
            if not review_exists:
                listing = await session.get(PhoneListing, tx.listing_id)
                keyboard.append([InlineKeyboardButton(
                    text=f"📱 {listing.service} | 💰 {tx.amount} USDT",
                    callback_data=f"review_tx:{tx.id}"
                )])
        
        if not keyboard:
            await callback.message.edit_text(
                "Вы уже оставили отзывы по всем недавним сделкам.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(
                    text="↩️ Назад",
                    callback_data="cancel_review"
                )]])
            )
            return
        
        keyboard.append([InlineKeyboardButton(
            text="❌ Отмена",
            callback_data="cancel_review"
        )])
        
        await state.set_state(ReviewStates.selecting_transaction)
        await callback.message.edit_text(
            "Выберите сделку для отзыва:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
        )

@router.callback_query(lambda c: c.data.startswith("review_tx:"))
async def process_transaction_selection(callback: types.CallbackQuery, state: FSMContext):
    tx_id = int(callback.data.split(":")[1])
    await state.update_data(transaction_id=tx_id)
    await state.set_state(ReviewStates.entering_rating)
    
    await callback.message.edit_text(
        "Оцените сделку:",
        reply_markup=get_rating_keyboard()
    )

@router.callback_query(lambda c: c.data.startswith("rate:"))
async def process_rating(callback: types.CallbackQuery, state: FSMContext):
    rating = int(callback.data.split(":")[1])
    await state.update_data(rating=rating)
    await state.set_state(ReviewStates.entering_comment)
    
    await callback.message.edit_text(
        "Напишите комментарий к отзыву:\n"
        "Опишите ваш опыт работы с продавцом/покупателем",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(
            text="❌ Отмена",
            callback_data="cancel_review"
        )]])
    )

@router.message(ReviewStates.entering_comment)
async def process_comment(message: types.Message, state: FSMContext):
    comment = message.text.strip()
    
    # Валидация комментария
    if len(comment) < 5:
        await message.answer(
            "❌ Комментарий слишком короткий. Напишите более подробный отзыв (минимум 5 символов).",
            reply_markup=get_main_keyboard(message.from_user.id)
        )
        return
    
    if len(comment) > 500:
        await message.answer(
            "❌ Комментарий слишком длинный. Максимальная длина - 500 символов.",
            reply_markup=get_main_keyboard(message.from_user.id)
        )
        return
    
    data = await state.get_data()
    transaction_id = data['transaction_id']
    rating = data['rating']
    
    async with async_session() as session:
        try:
            # Проверяем существование транзакции
            transaction = await session.get(Transaction, transaction_id)
            if not transaction:
                await message.answer(
                    "❌ Ошибка: транзакция не найдена.",
                    reply_markup=get_main_keyboard(message.from_user.id)
                )
                return
            
            # Проверяем, не оставлен ли уже отзыв
            existing_review = await session.scalar(
                select(Review).where(Review.transaction_id == transaction_id)
            )
            if existing_review:
                await message.answer(
                    "❌ Отзыв для этой транзакции уже оставлен.",
                    reply_markup=get_main_keyboard(message.from_user.id)
                )
                return
            
            # Определяем, кто оставляет отзыв и кому
            if message.from_user.id == transaction.buyer_id:
                reviewer_id = transaction.buyer_id
                reviewed_id = transaction.seller_id
            else:
                reviewer_id = transaction.seller_id
                reviewed_id = transaction.buyer_id
            
            # Создаем отзыв
            review = Review(
                transaction_id=transaction_id,
                reviewer_id=reviewer_id,
                reviewed_id=reviewed_id,
                rating=rating,
                comment=comment,
                created_at=datetime.utcnow()
            )
            session.add(review)
            
            # Обновляем рейтинг пользователя
            reviewed_user = await session.get(User, reviewed_id)
            if not reviewed_user:
                await message.answer(
                    "❌ Ошибка: пользователь не найден.",
                    reply_markup=get_main_keyboard(message.from_user.id)
                )
                return
            
            reviews_query = select(Review).where(Review.reviewed_id == reviewed_id)
            reviews_result = await session.execute(reviews_query)
            reviews = reviews_result.scalars().all()
            
            total_rating = sum(r.rating for r in reviews) + rating
            reviewed_user.rating = total_rating / (len(reviews) + 1)
            
            await session.commit()
            
            await message.answer(
                "✅ Спасибо за отзыв!\n"
                f"Вы поставили оценку: {'⭐' * rating}",
                reply_markup=get_main_keyboard(message.from_user.id)
            )
            
            # Уведомляем пользователя о новом отзыве
            try:
                await message.bot.send_message(
                    reviewed_id,
                    f"📝 Новый отзыв!\n"
                    f"Оценка: {'⭐' * rating}\n"
                    f"Комментарий: {comment}"
                )
            except Exception as e:
                logger.error(f"Failed to notify user {reviewed_id} about new review: {e}")
                
        except Exception as e:
            logger.error(f"Error in process_comment: {e}")
            await session.rollback()
            await message.answer(
                "❌ Произошла ошибка при создании отзыва. Пожалуйста, попробуйте позже.",
                reply_markup=get_main_keyboard(message.from_user.id)
            )
    
    await state.clear()

@router.callback_query(lambda c: c.data == "my_reviews")
async def show_my_reviews(callback: types.CallbackQuery):
    async with async_session() as session:
        # Получаем отзывы о пользователе
        reviews_query = select(Review).where(
            Review.reviewed_id == callback.from_user.id
        ).order_by(Review.created_at.desc())
        
        result = await session.execute(reviews_query)
        reviews = result.scalars().all()
        
        if not reviews:
            await callback.message.edit_text(
                "У вас пока нет отзывов.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(
                    text="↩️ Назад",
                    callback_data="cancel_review"
                )]])
            )
            return
        
        # Отправляем первый отзыв с кнопкой "Следующий"
        if len(reviews) > 1:
            keyboard = [[InlineKeyboardButton(
                text="➡️ Следующий",
                callback_data="next_review:1"
            )]]
        else:
            keyboard = [[InlineKeyboardButton(
                text="↩️ Назад",
                callback_data="cancel_review"
            )]]
        
        review = reviews[0]
        reviewer = await session.get(User, review.reviewer_id)
        transaction = await session.get(Transaction, review.transaction_id)
        
        await callback.message.edit_text(
            f"⭐️ Отзыв от {'покупателя' if reviewer.telegram_id == transaction.buyer_id else 'продавца'}\n"
            f"Оценка: {'⭐' * review.rating}\n"
            f"Комментарий: {review.comment}\n"
            f"Сумма сделки: {transaction.amount} USDT\n"
            f"Дата: {review.created_at.strftime('%d.%m.%Y %H:%M')}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
        )

@router.callback_query(lambda c: c.data.startswith("next_review:"))
async def show_next_review(callback: types.CallbackQuery):
    current_index = int(callback.data.split(":")[1])
    
    async with async_session() as session:
        reviews_query = select(Review).where(
            Review.reviewed_id == callback.from_user.id
        ).order_by(Review.created_at.desc())
        
        result = await session.execute(reviews_query)
        reviews = result.scalars().all()
        
        if current_index + 1 >= len(reviews):
            await callback.message.edit_text(
                "Это был последний отзыв.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(
                    text="↩️ Назад",
                    callback_data="cancel_review"
                )]])
            )
            return
        
        review = reviews[current_index + 1]
        reviewer = await session.get(User, review.reviewer_id)
        transaction = await session.get(Transaction, review.transaction_id)
        
        keyboard = []
        if current_index + 1 > 0:
            keyboard.append([InlineKeyboardButton(
                text="⬅️ Предыдущий",
                callback_data=f"next_review:{current_index}"
            )])
        if current_index + 1 < len(reviews) - 1:
            keyboard.append([InlineKeyboardButton(
                text="➡️ Следующий",
                callback_data=f"next_review:{current_index + 1}"
            )])
        keyboard.append([InlineKeyboardButton(
            text="↩️ Назад",
            callback_data="cancel_review"
        )])
        
        await callback.message.edit_text(
            f"⭐️ Отзыв от {'покупателя' if reviewer.telegram_id == transaction.buyer_id else 'продавца'}\n"
            f"Оценка: {'⭐' * review.rating}\n"
            f"Комментарий: {review.comment}\n"
            f"Сумма сделки: {transaction.amount} USDT\n"
            f"Дата: {review.created_at.strftime('%d.%m.%Y %H:%M')}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
        )

@router.callback_query(lambda c: c.data == "cancel_review")
async def cancel_review(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "❌ Отзыв отменен.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(
            text="↩️ В главное меню",
            callback_data="back_to_main"
        )]])
    )

def register_rating_handlers(dp: Dispatcher):
    """Регистрация обработчиков для рейтингов"""
    dp.include_router(router) 