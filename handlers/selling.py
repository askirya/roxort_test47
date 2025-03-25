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

@router.message(F.text == "📱 Продать номер")
async def start_selling(message: types.Message, state: FSMContext):
    """Начать процесс продажи номера"""
    async with async_session() as session:
        try:
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
            
            await state.set_state(SellingStates.choosing_service)
            await message.answer(
                "📱 Выберите сервис для продажи номера:",
                reply_markup=get_services_keyboard()
            )
        except Exception as e:
            logger.error(f"Error in start_selling: {e}")
            await message.answer(
                "❌ Произошла ошибка при начале продажи.\n"
                "Пожалуйста, попробуйте позже.",
                reply_markup=get_main_keyboard()
            )

@router.callback_query(lambda c: c.data == "cancel_sell")
async def cancel_selling(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    try:
        await callback.message.delete()
        await callback.message.answer(
            "❌ Создание объявления отменено.",
            reply_markup=get_main_keyboard(callback.from_user.id)
        )
    except Exception as e:
        logger.error(f"Error in cancel_selling: {e}")
        await callback.message.edit_text(
            "❌ Создание объявления отменено.",
            reply_markup=get_main_keyboard(callback.from_user.id)
        )

@router.callback_query(lambda c: c.data.startswith("service_"))
async def process_service_choice(callback: types.CallbackQuery, state: FSMContext):
    service = callback.data.split("_")[1]
    if service not in available_services:
        await callback.answer("❌ Неверный сервис", show_alert=True)
        return
    
    await state.update_data(service=service)
    await state.set_state(SellingStates.entering_phone)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_sell")
    ]])
    
    await callback.message.edit_text(
        f"📱 Введите номер телефона для {available_services[service]}:\n"
        "Формат: +7XXXXXXXXXX",
        reply_markup=keyboard
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
        "💰 Введите цену в рублях (минимум 10₽):",
        reply_markup=keyboard
    )

@router.message(SellingStates.entering_price)
async def process_price(message: Message, state: FSMContext):
    """Обработка введенной цены"""
    try:
        price = float(message.text)
        
        # Проверяем минимальную цену (0.1 ROXY)
        if price < 0.1:
            await message.answer(
                "❌ Минимальная цена: 0.1 ROXY\n"
                "Пожалуйста, введите корректную цену:",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="↩️ Отмена", callback_data="cancel_selling")
                ]])
            )
            return
            
        # Сохраняем цену
        await state.update_data(price=price)
        
        # Получаем данные о номере
        data = await state.get_data()
        service = data.get('service')
        phone_number = data.get('phone')
        
        # Формируем сообщение для подтверждения
        text = (
            f"📱 Подтвердите создание объявления:\n\n"
            f"Сервис: {service}\n"
            f"Номер: {phone_number}\n"
            f"Цена: {price:.2f} ROXY\n\n"
            f"💱 Курс: 10 ROXY = 1 USDT"
        )
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Подтвердить", callback_data="confirm_listing")],
            [InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_selling")]
        ])
        
        await message.answer(text, reply_markup=keyboard)
        await state.set_state(SellingStates.confirming)
        
    except ValueError:
        await message.answer(
            "❌ Пожалуйста, введите корректное число",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="↩️ Отмена", callback_data="cancel_selling")
            ]])
        )
    except Exception as e:
        logger.error(f"Ошибка при обработке цены: {e}")
        await message.answer(
            "Произошла ошибка. Попробуйте еще раз или отмените создание объявления.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="↩️ Отмена", callback_data="cancel_selling")
            ]])
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