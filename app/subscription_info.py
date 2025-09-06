import logging
import asyncio
import os
import re
import time
from datetime import datetime, timedelta

from aiogram.enums import ParseMode, ChatMemberStatus
from aiogram.fsm import state
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, \
    KeyboardButton, user
from aiogram import Router, F, Bot
from aiogram.filters import CommandStart, Command
# from app.generators import *
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

from app.handlers import menu
from app.states import Form
from config import *
from database import BotDB

db = BotDB('point.db')
router = Router()
bot = Bot(token=TG_TOKEN)

logger = logging.getLogger(__name__)

from app.subscription_funcs import SubscriptionManager

subscription_manager = SubscriptionManager(db, bot)
@router.message(lambda message: message.text == "🛠️ Профиль")
async def subscription_info(message: Message):
    user_id = message.from_user.id

    # Получаем данные о подписке
    sub = subscription_manager.db.get_subscription(user_id)
    profile = subscription_manager.db.get_business(user_id)

    status_map = {
        0: "❌ Нет подписки",
        1: "🟦 Базовый тариф",
        2: "🟩 Продвинутый тариф"
    }
    status_text = status_map.get(sub["status"], "❌ Нет подписки")

    free_gen = sub["free_generations"]
    end_date = sub["subscription_end"] or "—"

    text = (
        f"<b>Уровень подписки:</b> {status_text}\n"
        f"<b>Бесплатные генерации:</b> {free_gen}\n"
        f"<b>Дата окончания подписки:</b> {end_date}\n\n"
        f"👤 <b>Ваш профиль:</b> <i>{profile}</i>"
    )

    # Инлайн-кнопки
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Перейти к оплате", callback_data="go_to_payment")],
        [InlineKeyboardButton(text="📝 Изменить профиль", callback_data="registration")],
    ])

    await message.answer(
        f"🌟 <b>Информация о подписке</b>:\n\n{text}",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
