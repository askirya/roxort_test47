from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database.db import get_session, async_session
from database.models import User, Transaction
from config import MIN_DEPOSIT, MIN_WITHDRAWAL, CRYPTO_MIN_AMOUNT, CRYPTO_CURRENCY, ADMIN_IDS
from handlers.common import get_main_keyboard, check_user_registered
import logging
from sqlalchemy import select
from datetime import datetime
import uuid
from utils.crypto import crypto_bot
from log import logger

router = Router()
logger = logging.getLogger(__name__)

class PaymentStates(StatesGroup):
    entering_deposit_amount = State()
    entering_withdrawal_amount = State()
    entering_wallet = State()
    waiting_deposit_amount = State()
    waiting_withdrawal_amount = State()

class WithdrawStates(StatesGroup):
    entering_amount = State()
    confirming = State()

def get_payment_keyboard():
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💰 Пополнить баланс", callback_data="deposit")],
            [InlineKeyboardButton(text="💸 Вывести средства", callback_data="withdraw")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_payment")]
        ]
    )
    return keyboard

@router.message(F.text == "💰 Баланс")
async def show_balance_menu(message: types.Message):
    if not await check_user_registered(message.from_user.id):
        await message.answer(
            "❌ Вы не зарегистрированы!\n"
            "Пожалуйста, пройдите регистрацию:",
            reply_markup=get_main_keyboard()
        )
        return

    async with await get_session() as session:
        user = await session.get(User, message.from_user.id)
        
        await message.answer(
            f"💰 Ваш текущий баланс: {user.balance:.2f} USDT\n\n"
            f"Минимальная сумма пополнения: {MIN_DEPOSIT} USDT\n"
            f"Минимальная сумма вывода: {MIN_WITHDRAWAL} USDT",
            reply_markup=get_payment_keyboard()
        )

@router.callback_query(lambda c: c.data == "deposit")
async def start_deposit(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(PaymentStates.entering_deposit_amount)
    await callback.message.edit_text(
        f"💰 Введите сумму пополнения (мин. {MIN_DEPOSIT} USDT):"
    )

@router.message(PaymentStates.entering_deposit_amount)
async def process_deposit_amount(message: types.Message, state: FSMContext):
    try:
        amount = float(message.text.strip())
        if amount < MIN_DEPOSIT:
            await message.answer(f"❌ Минимальная сумма пополнения: {MIN_DEPOSIT} USDT")
            return
        
        # Здесь будет интеграция с CryptoBot
        # Пока что просто имитируем пополнение
        async with await get_session() as session:
            user = await session.get(User, message.from_user.id)
            user.balance += amount
            await session.commit()
            
            await message.answer(
                f"✅ Баланс успешно пополнен на {amount} USDT\n"
                f"💰 Текущий баланс: {user.balance:.2f} USDT",
                reply_markup=get_main_keyboard(message.from_user.id)
            )
        
        await state.clear()
        
    except ValueError:
        await message.answer("❌ Введите корректную сумму")

@router.callback_query(lambda c: c.data == "withdraw")
async def start_withdrawal(callback: types.CallbackQuery, state: FSMContext):
    async with await get_session() as session:
        user = await session.get(User, callback.from_user.id)
        
        if user.balance < MIN_WITHDRAWAL:
            await callback.message.edit_text(
                f"❌ Недостаточно средств для вывода.\n"
                f"Минимальная сумма: {MIN_WITHDRAWAL} USDT\n"
                f"Ваш баланс: {user.balance:.2f} USDT",
                reply_markup=get_main_keyboard(callback.from_user.id)
            )
            return
        
        await state.set_state(PaymentStates.entering_withdrawal_amount)
        await callback.message.edit_text(
            f"💸 Введите сумму вывода (мин. {MIN_WITHDRAWAL} USDT):\n"
            f"Доступно: {user.balance:.2f} USDT"
        )

@router.message(PaymentStates.entering_withdrawal_amount)
async def process_withdrawal_amount(message: types.Message, state: FSMContext):
    try:
        amount = float(message.text.strip())
        if amount < MIN_WITHDRAWAL:
            await message.answer(f"❌ Минимальная сумма вывода: {MIN_WITHDRAWAL} USDT")
            return
        
        async with await get_session() as session:
            user = await session.get(User, message.from_user.id)
            
            if amount > user.balance:
                await message.answer(
                    "❌ Недостаточно средств на балансе\n"
                    f"Доступно: {user.balance:.2f} USDT"
                )
                return
            
            await state.update_data(amount=amount)
            await state.set_state(PaymentStates.entering_wallet)
            
            await message.answer(
                "Введите ваш USDT TRC20 кошелек для вывода средств:"
            )
            
    except ValueError:
        await message.answer("❌ Введите корректную сумму")

@router.message(PaymentStates.entering_wallet)
async def process_withdrawal_wallet(message: types.Message, state: FSMContext):
    wallet = message.text.strip()
    data = await state.get_data()
    amount = data['amount']
    
    # Здесь будет интеграция с CryptoBot
    # Пока что просто имитируем вывод
    async with await get_session() as session:
        user = await session.get(User, message.from_user.id)
        user.balance -= amount
        await session.commit()
        
        await message.answer(
            f"✅ Заявка на вывод создана!\n"
            f"💰 Сумма: {amount} USDT\n"
            f"👛 Кошелек: {wallet}\n\n"
            f"Средства поступят на ваш кошелек в течение 24 часов.",
            reply_markup=get_main_keyboard(message.from_user.id)
        )
    
    await state.clear()

@router.callback_query(lambda c: c.data == "cancel_payment")
async def cancel_payment(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "❌ Операция отменена.",
        reply_markup=get_main_keyboard(callback.from_user.id)
    )

@router.callback_query(F.data == "balance")
async def show_balance(callback: types.CallbackQuery):
    async with get_session() as session:
        query = select(User).where(User.telegram_id == callback.from_user.id)
        result = await session.execute(query)
        user = result.scalar_one_or_none()
        
        if not user:
            await callback.answer("❌ Вы не зарегистрированы", show_alert=True)
            return
        
        await callback.message.edit_text(
            f"💰 Ваш баланс: {user.balance:.2f} {CRYPTO_CURRENCY}\n\n"
            f"Минимальная сумма пополнения: {CRYPTO_MIN_AMOUNT} {CRYPTO_CURRENCY}\n"
            f"Минимальная сумма вывода: {CRYPTO_MIN_AMOUNT} {CRYPTO_CURRENCY}",
            reply_markup=get_payment_keyboard()
        )

@router.callback_query(F.data == "deposit")
async def start_deposit(callback: types.CallbackQuery, state: FSMContext):
    keyboard = [[
        types.InlineKeyboardButton(
            text="❌ Отмена",
            callback_data="cancel_payment"
        )
    ]]
    
    await state.set_state(PaymentStates.waiting_deposit_amount)
    await callback.message.edit_text(
        f"💳 Введите сумму пополнения (минимум {CRYPTO_MIN_AMOUNT} {CRYPTO_CURRENCY}):",
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=keyboard)
    )

@router.message(PaymentStates.waiting_deposit_amount)
async def process_deposit_amount(message: types.Message, state: FSMContext):
    try:
        amount = float(message.text.replace(",", "."))
        if amount < CRYPTO_MIN_AMOUNT:
            await message.answer(
                f"❌ Минимальная сумма пополнения: {CRYPTO_MIN_AMOUNT} {CRYPTO_CURRENCY}"
            )
            return
        
        # Создаем инвойс
        invoice = await crypto_bot.create_invoice(
            amount=amount,
            description=f"Пополнение баланса в ROXORT SMS",
            paid_btn_name="Вернуться в бот",
            paid_btn_url=f"https://t.me/{(await message.bot.me()).username}",
            payload=f"deposit_{message.from_user.id}_{uuid.uuid4()}"
        )
        
        if "error" in invoice:
            await message.answer("❌ Ошибка при создании платежа")
            return
        
        pay_url = invoice["result"]["pay_url"]
        keyboard = [
            [
                types.InlineKeyboardButton(
                    text="💳 Оплатить",
                    url=pay_url
                )
            ],
            [
                types.InlineKeyboardButton(
                    text="❌ Отмена",
                    callback_data="cancel_payment"
                )
            ]
        ]
        
        await message.answer(
            f"💳 Счет на оплату создан\n\n"
            f"Сумма: {amount} {CRYPTO_CURRENCY}\n"
            "Нажмите кнопку ниже для оплаты:",
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=keyboard)
        )
        
        await state.clear()
        
    except ValueError:
        await message.answer("❌ Неверный формат суммы")

@router.callback_query(F.data == "withdraw")
async def start_withdrawal(callback: types.CallbackQuery, state: FSMContext):
    async with get_session() as session:
        query = select(User).where(User.telegram_id == callback.from_user.id)
        result = await session.execute(query)
        user = result.scalar_one_or_none()
        
        if not user:
            await callback.answer("❌ Вы не зарегистрированы", show_alert=True)
            return
        
        if user.balance < CRYPTO_MIN_AMOUNT:
            await callback.answer(
                f"❌ Недостаточно средств. Минимальная сумма: {CRYPTO_MIN_AMOUNT} {CRYPTO_CURRENCY}",
                show_alert=True
            )
            return
        
        keyboard = [[
            types.InlineKeyboardButton(
                text="❌ Отмена",
                callback_data="cancel_payment"
            )
        ]]
        
        await state.set_state(PaymentStates.waiting_withdrawal_amount)
        await callback.message.edit_text(
            f"💸 Введите сумму вывода (минимум {CRYPTO_MIN_AMOUNT} {CRYPTO_CURRENCY}):\n"
            f"Доступно: {user.balance:.2f} {CRYPTO_CURRENCY}",
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=keyboard)
        )

@router.message(PaymentStates.waiting_withdrawal_amount)
async def process_withdrawal_amount(message: types.Message, state: FSMContext):
    try:
        amount = float(message.text.replace(",", "."))
        
        async with get_session() as session:
            query = select(User).where(User.telegram_id == message.from_user.id)
            result = await session.execute(query)
            user = result.scalar_one_or_none()
            
            if not user:
                await message.answer("❌ Вы не зарегистрированы")
                return
            
            if amount < CRYPTO_MIN_AMOUNT:
                await message.answer(
                    f"❌ Минимальная сумма вывода: {CRYPTO_MIN_AMOUNT} {CRYPTO_CURRENCY}"
                )
                return
            
            if amount > user.balance:
                await message.answer("❌ Недостаточно средств")
                return
            
            # Создаем уникальный ID для транзакции
            spend_id = str(uuid.uuid4())
            
            # Выполняем перевод
            transfer = await crypto_bot.transfer(
                user_id=message.from_user.id,
                amount=amount,
                spend_id=spend_id,
                comment="Вывод средств из ROXORT SMS"
            )
            
            if "error" in transfer:
                await message.answer("❌ Ошибка при выводе средств")
                return
            
            # Обновляем баланс пользователя
            user.balance -= amount
            
            # Создаем запись о транзакции
            transaction = Transaction(
                user_id=user.telegram_id,
                type="withdrawal",
                amount=amount,
                status="completed",
                created_at=datetime.utcnow()
            )
            
            session.add(transaction)
            await session.commit()
            
            await message.answer(
                f"✅ Средства успешно выведены!\n"
                f"Сумма: {amount} {CRYPTO_CURRENCY}"
            )
            
            await state.clear()
            
    except ValueError:
        await message.answer("❌ Неверный формат суммы")

@router.callback_query(F.data == "cancel_payment")
async def cancel_payment(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await show_balance(callback)

# Обработчик уведомлений от CryptoBot
async def process_crypto_payment(data: dict, headers: dict):
    try:
        # Проверяем подпись
        signature = headers.get("X-Crypto-Pay-Signature")
        if not signature or not crypto_bot.verify_signature(data, signature):
            logger.warning("Invalid payment signature")
            return False
        
        # Получаем данные платежа
        payload = data.get("payload", "")
        if not payload.startswith("deposit_"):
            logger.warning("Invalid payment payload")
            return False
        
        # Извлекаем ID пользователя
        _, user_id, _ = payload.split("_")
        user_id = int(user_id)
        
        # Получаем сумму
        amount = float(data["amount"])
        
        async with get_session() as session:
            # Обновляем баланс пользователя
            query = select(User).where(User.telegram_id == user_id)
            result = await session.execute(query)
            user = result.scalar_one_or_none()
            
            if not user:
                logger.error(f"User {user_id} not found")
                return False
            
            user.balance += amount
            
            # Создаем запись о транзакции
            transaction = Transaction(
                user_id=user_id,
                type="deposit",
                amount=amount,
                status="completed",
                created_at=datetime.utcnow()
            )
            
            session.add(transaction)
            await session.commit()
            
            # Отправляем уведомление пользователю
            bot = await get_bot()  # Функция для получения объекта бота
            await bot.send_message(
                user_id,
                f"✅ Баланс пополнен!\n"
                f"Сумма: {amount} {CRYPTO_CURRENCY}"
            )
            
            return True
            
    except Exception as e:
        logger.error(f"Error processing crypto payment: {e}")
        return False

@router.message(lambda message: message.text == "💸 Вывести средства")
async def withdraw_funds(message: types.Message):
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

            # Проверяем баланс
            if user.balance <= 0:
                await message.answer(
                    "❌ На вашем балансе нет средств для вывода.\n"
                    f"Текущий баланс: {user.balance} USDT",
                    reply_markup=get_main_keyboard(message.from_user.id)
                )
                return

            # Создаем транзакцию вывода
            withdrawal = Transaction(
                buyer_id=user.telegram_id,
                seller_id=user.telegram_id,  # в случае вывода отправитель и получатель совпадают
                amount=user.balance,
                status="withdrawal_requested"
            )
            session.add(withdrawal)

            # Обнуляем баланс пользователя
            old_balance = user.balance
            user.balance = 0
            
            await session.commit()

            # Отправляем сообщение пользователю
            await message.answer(
                "✅ Запрос на вывод средств создан!\n\n"
                f"Сумма: {old_balance} USDT\n\n"
                "📝 Напишите администратору для получения средств:\n"
                f"ID транзакции: #{withdrawal.id}",
                reply_markup=get_main_keyboard(message.from_user.id)
            )

            # Уведомляем администраторов
            for admin_id in ADMIN_IDS:
                try:
                    await message.bot.send_message(
                        admin_id,
                        f"💸 Новый запрос на вывод средств!\n\n"
                        f"От: {user.username or user.telegram_id}\n"
                        f"Сумма: {old_balance} USDT\n"
                        f"ID транзакции: #{withdrawal.id}"
                    )
                except Exception as e:
                    logger.error(f"Failed to notify admin {admin_id}: {e}")

        except Exception as e:
            logger.error(f"Error in withdraw_funds: {e}")
            await session.rollback()
            await message.answer(
                "❌ Произошла ошибка при создании запроса на вывод средств.\n"
                "Пожалуйста, попробуйте позже или обратитесь к администратору.",
                reply_markup=get_main_keyboard(message.from_user.id)
            )
        finally:
            await session.close() 