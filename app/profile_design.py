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
from app.generators import *
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

from app.handlers import menu
from app.states import Form
from config import *
from database import BotDB
from funcs import response_generator

db = BotDB('point.db')
router = Router()
bot = Bot(token=TG_TOKEN)

logger = logging.getLogger(__name__)


@router.message(lambda message: message.text == "🎨 Дизайн профиля")
async def profile_design(message: Message, state: FSMContext):
    user_id=message.from_user.id

    from app.subscription_funcs import SubscriptionManager
    subscription_manager = SubscriptionManager(db, bot)
    if not await subscription_manager.can_generate(user_id):
        return  # пользователь уведомлен, генерация не идёт
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✨ Набор эмодзи", callback_data="emoji_set")],
        [InlineKeyboardButton(text="📄 Описание профиля IG", callback_data="ig_bio")],
        [InlineKeyboardButton(text="🌟 Идеи для Highlights IG", callback_data="ig_highlights")]
    ])
    await bot.send_photo(
            caption="""
            💡 Что будем создавать?\n
            Выбери одну из кнопок ниже, чтобы приступить к работе ⬇  
            """,
            parse_mode="HTML",
            photo='AgACAgIAAxkBAAOoaLCncUpTj5yVmb99qKnWCzCzWdwAAloBMhulPIlJa-XdYhMiqGgBAAMCAAN3AAM2BA',
            chat_id=message.chat.id,
            reply_markup=kb
    )

PROMPTS_INLINE = {
    "emoji_set": (
        "Задача: подготовить 10 вариантов строк эмодзи (4–7 эмодзи) для профиля и постов в указанной нише.\n"
        "Для каждого варианта в одну строку: EMOJI_STRING — коротко, где использовать (1 предложение).\n"
        "Пиши просто и по делу, без вступлений и разделителей."
    ),
    "ig_bio": (
        "Задача: написать 5 коротких вариантов bio для профиля (каждый 1–2 строки, до ~140 символов).\n"
        "Для каждого варианта укажи: BIO — EMOJI (1–2 эмодзи) — CTA (одно краткое действие).\n"
        "Пиши живо и продающе, без вступлений и разделителей."
    ),
    "ig_highlights": (
        "Задача: придумать 8 идей для Highlights IG. Для каждой идеии дай: Название (1–2 слова) — Описание (1 предложение) — Рекомендованная иконка/эмодзи.\n"
        "Вывод — пронумерованный список из 8 пунктов. Пиши коротко и по делу."
    ),
}

@router.callback_query(lambda c: c.data in ["emoji_set", "ig_bio", "ig_highlights"])
async def inline_choice(callback_query: CallbackQuery, state: FSMContext):
    selected = callback_query.data
    # Сохраняем выбранный вариант в FSM
    await state.update_data(selected_callback=selected)

    data = await state.get_data()
    selected = data["selected_callback"]


    goal = db.get_business(user_id=callback_query.from_user.id)

    # Формируем контент для генератора
    prompt = PROMPTS_INLINE[selected]
    content = f'''
{goal}
{prompt}
'''
    request_task = asyncio.create_task(
            generator(user_id=callback_query.from_user.id, content=content)
    )
    response = await response_generator(callback_query, request_task, bot=bot)
