from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database.db import async_session
from database.models import User
from sqlalchemy import select
from handlers.common import get_main_keyboard
from log import logger

router = Router()

class RegistrationStates(StatesGroup):
    waiting_for_phone = State()

@router.message(lambda message: message.text == "🔄 Начать регистрацию")
async def start_registration(message: types.Message, state: FSMContext):
    keyboard = types.ReplyKeyboardMarkup(
        keyboard=[[
            types.KeyboardButton(text="📱 Поделиться номером", request_contact=True)
        ]],
        resize_keyboard=True
    )
    await message.answer(
        "📱 Для регистрации поделитесь своим номером телефона:",
        reply_markup=keyboard
    )
    await state.set_state(RegistrationStates.waiting_for_phone)

@router.message(RegistrationStates.waiting_for_phone, F.contact)
async def process_phone_number(message: types.Message, state: FSMContext):
    if not message.contact or not message.contact.phone_number:
        await message.answer("❌ Пожалуйста, поделитесь номером телефона через кнопку.")
        return

    phone_number = message.contact.phone_number
    telegram_id = message.from_user.id
    username = message.from_user.username

    async with async_session() as session:
        try:
            # Проверяем, не зарегистрирован ли уже пользователь
            query = select(User).where(User.telegram_id == telegram_id)
            result = await session.execute(query)
            existing_user = result.scalar_one_or_none()

            if existing_user:
                await message.answer(
                    "❌ Вы уже зарегистрированы!",
                    reply_markup=get_main_keyboard(telegram_id)
                )
                await state.clear()
                return

            # Создаем нового пользователя
            new_user = User(
                telegram_id=telegram_id,
                username=username,
                phone_number=phone_number
            )
            session.add(new_user)
            await session.commit()

            await message.answer(
                "✅ Регистрация успешно завершена!\n"
                "Теперь вы можете использовать все функции бота:",
                reply_markup=get_main_keyboard(telegram_id)
            )
            await state.clear()

        except Exception as e:
            await session.rollback()
            logger.error(f"Error during registration: {e}")
            await message.answer(
                "❌ Произошла ошибка при регистрации.\n"
                "Пожалуйста, попробуйте позже или обратитесь к администратору."
            )
            await state.clear()
        finally:
            await session.close()

@router.message(RegistrationStates.waiting_for_phone)
async def process_invalid_phone(message: types.Message):
    await message.answer(
        "❌ Пожалуйста, поделитесь номером телефона через специальную кнопку ниже."
    ) 