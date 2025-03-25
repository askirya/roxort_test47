from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from database.db import get_session, async_session
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
    
    async with await get_session() as session:
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
                reply_markup=get_main_keyboard(callback.from_user.id)
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
                reply_markup=get_main_keyboard(callback.from_user.id)
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
        "Опишите ваш опыт работы с продавцом/покупателем"
    )

@router.message(ReviewStates.entering_comment)
async def process_comment(message: types.Message, state: FSMContext):
    comment = message.text.strip()
    
    # Валидация комментария
    if len(comment) < 5:
        await message.answer("❌ Комментарий слишком короткий. Напишите более подробный отзыв (минимум 5 символов).")
        return
    
    if len(comment) > 500:
        await message.answer("❌ Комментарий слишком длинный. Максимальная длина - 500 символов.")
        return
    
    data = await state.get_data()
    transaction_id = data['transaction_id']
    rating = data['rating']
    
    async with await get_session() as session:
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
                # Продолжаем выполнение, даже если уведомление не удалось
                
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
    async with await get_session() as session:
        # Получаем отзывы о пользователе
        reviews_query = select(Review).where(
            Review.reviewed_id == callback.from_user.id
        ).order_by(Review.created_at.desc())
        
        result = await session.execute(reviews_query)
        reviews = result.scalars().all()
        
        if not reviews:
            await callback.message.edit_text(
                "У вас пока нет отзывов.",
                reply_markup=get_main_keyboard(callback.from_user.id)
            )
            return
        
        for review in reviews:
            reviewer = await session.get(User, review.reviewer_id)
            transaction = await session.get(Transaction, review.transaction_id)
            
            await callback.message.answer(
                f"⭐️ Отзыв от {'покупателя' if reviewer.telegram_id == transaction.buyer_id else 'продавца'}\n"
                f"Оценка: {'⭐' * review.rating}\n"
                f"Комментарий: {review.comment}\n"
                f"Сумма сделки: {transaction.amount} USDT\n"
                f"Дата: {review.created_at.strftime('%d.%m.%Y %H:%M')}"
            )

@router.callback_query(lambda c: c.data == "cancel_review")
async def cancel_review(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "❌ Отзыв отменен.",
        reply_markup=get_main_keyboard(callback.from_user.id)
    )

async def show_reviews(message: types.Message):
    """Показывает отзывы пользователя"""
    try:
        async with async_session() as session:
            user = await session.get(User, message.from_user.id)
            
            # Получаем отзывы о пользователе
            reviews_query = select(Review).where(Review.reviewed_id == user.telegram_id)
            reviews_result = await session.execute(reviews_query)
            reviews = reviews_result.scalars().all()
            
            if not reviews:
                await message.answer(
                    "У вас пока нет отзывов.",
                    reply_markup=get_main_keyboard(message.from_user.id)
                )
                return
            
            # Формируем сообщение с отзывами
            response = f"⭐️ Ваш рейтинг: {user.rating:.1f}\n"
            response += f"Количество отзывов: {len(reviews)}\n\n"
            response += "📝 Отзывы:\n\n"
            
            for review in reviews:
                reviewer = await session.get(User, review.reviewer_id)
                transaction = await session.get(Transaction, review.transaction_id)
                
                response += f"От: @{reviewer.username if reviewer else 'Пользователь'}\n"
                response += f"Оценка: {'⭐️' * review.rating}\n"
                response += f"Комментарий: {review.comment}\n"
                if transaction:
                    response += f"Сумма сделки: {transaction.amount} USDT\n"
                response += f"Дата: {review.created_at.strftime('%d.%m.%Y %H:%M')}\n\n"
            
            await message.answer(
                response,
                reply_markup=get_main_keyboard(message.from_user.id)
            )
    except Exception as e:
        logger.error(f"Ошибка при показе отзывов: {e}")
        await message.answer(
            "Произошла ошибка при получении списка отзывов.",
            reply_markup=get_main_keyboard(message.from_user.id)
        )

def register_rating_handlers(dp: Dispatcher):
    """Регистрация обработчиков для рейтингов"""
    dp.include_router(router) 