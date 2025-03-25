from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from database.db import async_session
from database.models import User, PhoneListing
from sqlalchemy import select
from handlers.common import get_main_keyboard
from .services import available_services, get_services_keyboard
from log import logger
import logging
from aiogram import Dispatcher
from aiogram.filters import Command
from aiogram.types import Message

router = Router()
logger = logging.getLogger(__name__)

class SellingStates(StatesGroup):
    choosing_service = State()
    entering_phone = State()
    entering_period = State()
    entering_price = State()
    confirming = State()
    selecting_service = State()

@router.message(F.text == "📱 Продать номер")
async def start_selling(message: types.Message, state: FSMContext):
    """Начинает процесс продажи номера"""
    try:
        async with async_session() as session:
            user = await session.get(User, message.from_user.id)
            if not user:
                await message.answer(
                    "❌ Пожалуйста, сначала зарегистрируйтесь.",
                    reply_markup=get_main_keyboard()
                )
                return
            
            # Проверяем минимальный баланс
            if user.balance < 0.1:
                await message.answer(
                    "❌ Недостаточно средств на балансе для создания объявления.\n"
                    f"Минимальная стоимость: 0.1 ROXY\n"
                    f"Ваш баланс: {user.balance:.2f} ROXY",
                    reply_markup=get_main_keyboard()
                )
                return
            
            # Показываем список доступных сервисов
            keyboard = []
            for service in SERVICES:
                keyboard.append([InlineKeyboardButton(
                    text=service,
                    callback_data=f"select_service:{service}"
                )])
            
            keyboard.append([InlineKeyboardButton(
                text="❌ Отмена",
                callback_data="cancel_selling"
            )])
            
            await state.set_state(SellingStates.selecting_service)
            await message.answer(
                "Выберите сервис для продажи номера:",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
            )
    except Exception as e:
        logger.error(f"Error in start_selling: {e}")
        await message.answer(
            "❌ Произошла ошибка при начале процесса продажи.",
            reply_markup=get_main_keyboard()
        )

@router.callback_query(lambda c: c.data.startswith("select_service:"))
async def process_service_selection(callback: types.CallbackQuery, state: FSMContext):
    """Обрабатывает выбор сервиса"""
    service = callback.data.split(":")[1]
    await state.update_data(service=service)
    
    await callback.message.edit_text(
        f"Вы выбрали сервис: {service}\n\n"
        "Введите цену в ROXY (минимум 0.1 ROXY):",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(
            text="❌ Отмена",
            callback_data="cancel_selling"
        )]])
    )

@router.message(SellingStates.entering_phone)
async def process_phone(message: types.Message, state: FSMContext):
    phone = message.text.strip()
    
    # Проверяем формат номера
    if not (phone.startswith("+7") and len(phone) == 12 and phone[1:].isdigit()):
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_sell")
        ]])
        await message.answer(
            "❌ Неверный формат номера.\n"
            "Введите номер в формате: +7XXXXXXXXXX",
            reply_markup=keyboard
        )
        return
    
    await state.update_data(phone=phone)
    await state.set_state(SellingStates.entering_period)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_sell")
    ]])
    
    await message.answer(
        "⏰ Введите срок аренды в часах (от 1 до 168):",
        reply_markup=keyboard
    )

@router.message(SellingStates.entering_period)
async def process_period(message: types.Message, state: FSMContext):
    try:
        period = int(message.text.strip())
        if not 1 <= period <= 168:
            raise ValueError
    except ValueError:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_sell")
        ]])
        await message.answer(
            "❌ Неверный формат.\n"
            "Введите число от 1 до 168",
            reply_markup=keyboard
        )
        return
    
    await state.update_data(period=period)
    await state.set_state(SellingStates.entering_price)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_sell")
    ]])
    
    await message.answer(
        "💰 Введите цену в рублях (минимум 0.1 ROXY):",
        reply_markup=keyboard
    )

@router.message(SellingStates.entering_price)
async def process_price(message: types.Message, state: FSMContext):
    """Обрабатывает ввод цены"""
    try:
        price = float(message.text)
        if price < 0.1:
            await message.answer(
                "❌ Минимальная цена: 0.1 ROXY",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(
                    text="❌ Отмена",
                    callback_data="cancel_selling"
                )]])
            )
            return
        
        data = await state.get_data()
        service = data['service']
        
        # Создаем объявление
        async with async_session() as session:
            user = await session.get(User, message.from_user.id)
            if user.balance < 0.1:
                await message.answer(
                    "❌ Недостаточно средств на балансе для создания объявления.\n"
                    f"Минимальная стоимость: 0.1 ROXY\n"
                    f"Ваш баланс: {user.balance:.2f} ROXY",
                    reply_markup=get_main_keyboard()
                )
                return
            
            # Списываем комиссию
            user.balance -= 0.1
            await session.commit()
            
            # Создаем объявление
            listing = PhoneListing(
                seller_id=message.from_user.id,
                service=service,
                phone_number=data['phone'],
                rental_period=data['period'],
                price=price,
                is_active=True
            )
            session.add(listing)
            await session.commit()
            
            # Показываем подтверждение
            keyboard = [
                [InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"confirm_listing:{listing.id}")],
                [InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_selling")]
            ]
            
            await message.answer(
                f"📱 Создание объявления:\n\n"
                f"Сервис: {service}\n"
                f"Номер: {data['phone']}\n"
                f"Срок аренды: {data['period']} часов\n"
                f"Цена: {price:.2f} ROXY\n"
                f"Комиссия: 0.1 ROXY\n\n"
                f"Подтвердите создание объявления:",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
            )
            
    except ValueError:
        await message.answer(
            "❌ Пожалуйста, введите корректное число.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(
                text="❌ Отмена",
                callback_data="cancel_selling"
            )]])
        )
    except Exception as e:
        logger.error(f"Error in process_price: {e}")
        await message.answer(
            "❌ Произошла ошибка при обработке цены.",
            reply_markup=get_main_keyboard()
        )

@router.callback_query(lambda c: c.data == "confirm_sell")
async def confirm_listing(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    
    async with async_session() as session:
        try:
            # Создаем объявление
            listing = PhoneListing(
                seller_id=callback.from_user.id,
                service=data['service'],
                phone_number=data['phone'],
                rental_period=data['period'],
                price=data['price'],
                is_active=True
            )
            session.add(listing)
            await session.commit()
            
            await callback.message.edit_text(
                "✅ Объявление успешно создано!\n\n"
                f"Сервис: {available_services[data['service']]}\n"
                f"Номер: {data['phone']}\n"
                f"Срок аренды: {data['period']} часов\n"
                f"Цена: {data['price']}₽\n\n"
                "Ожидайте покупателя! 🎉"
            )
            
            await callback.message.answer(
                "Вернуться в главное меню:",
                reply_markup=get_main_keyboard(callback.from_user.id)
            )
            
            await state.clear()
            
        except Exception as e:
            await session.rollback()
            logger.error(f"Error creating listing: {e}")
            await callback.answer("❌ Произошла ошибка при создании объявления", show_alert=True)

async def cmd_sell(message: Message, state: FSMContext):
    """Обработчик команды /sell"""
    await start_selling(message, state)

def register_selling_handlers(dp: Dispatcher):
    """Регистрация обработчиков для продажи"""
    dp.include_router(router)
    dp.message.register(cmd_sell, Command("sell")) 