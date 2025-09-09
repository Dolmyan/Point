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
from funcs import response_generator, text_or_voice

db = BotDB('point.db')
router = Router()
bot = Bot(token=TG_TOKEN)

logger = logging.getLogger(__name__)


@router.message(lambda message: message.text == "🎬 Видео идеи")
async def video_ideas(message: Message, state: FSMContext):
    user_id=message.from_user.id

    from app.subscription_funcs import SubscriptionManager
    subscription_manager = SubscriptionManager(db, bot)
    if not await subscription_manager.can_generate(user_id):
        return  # пользователь уведомлен, генерация не идёт
    await bot.send_photo(
            caption=(
                "<b>🎬 Идеи для видео</b>\n\n"
                "Я придумаю рабочие идеи для коротких видео (Reels, TikTok, Stories): цепляющие хук-начала, краткая структура, монтажные подсказки и чёткий CTA. "
                "Каждая идея будет готова к быстрой съёмке и монтажу.\n\n"),
            parse_mode="HTML",
            photo='AgACAgIAAxkBAAOlaLCltmiqSDxc66xL5IEp1aI-czwAAlIBMhulPIlJA0roZsnHnlYBAAMCAAN3AAM2BA',
            chat_id=message.chat.id
    )
    await message.answer(
            "💡 На какую тему ты хочешь генерировать?\n\n"
            "✍️ Можешь написать текстом\n"
            "🎙️ Или записать голосовое.",
            parse_mode="HTML"
    )
    await state.set_state(Form.video_ideas)


@router.message(Form.video_ideas)
async def video_ideas_handler(message: Message, state: FSMContext):
    theme = await text_or_voice(message)
    goal = f"{db.get_business(user_id=message.from_user.id)} Тема генерации: {theme}"
    content=f'''
    {goal}
    Задача: придумать 10 идей коротких видео (Reels, TikTok, Stories) для вашей ниши. Для каждой идеи укажи:

    🎯 Краткий заголовок / тема  
    📝 Суть видео в 1–2 предложениях  
    🎬 Формат и подача (говорящая голова, графика, сторителлинг, диалог и т.д.)  
    💡 Хук для первых 3 секунд, чтобы зритель зацепился  
    ✅ Призыв к действию (CTA): регистрация, заявка, подписка, лайк, комментарий  

    Каждая идея должна быть готова к съёмке и монтажу. Не добавляй вводных и заключительных фраз, не используй разделители.
    '''
    request_task = asyncio.create_task(
            generator(user_id=message.from_user.id, content=content)
    )
    response = await response_generator(message, request_task, bot=bot)
    await state.set_state(Form.clear)
