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


@router.message(lambda message: message.text == "🚀 Продвижение")
async def promotion_info(message: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[

        [
            InlineKeyboardButton(text="Прогрев в сторис", callback_data="stories_warmup"),
            InlineKeyboardButton(text="Недельный прогрев", callback_data="weekly_warmup")
        ],
        [
            InlineKeyboardButton(text="Идеи вебинаров", callback_data="webinar_ideas"),
            InlineKeyboardButton(text="Сценарий вебинара", callback_data="webinar_script"),
        ],
        [
            InlineKeyboardButton(text="Идеи рассылок", callback_data="newsletter_ideas"),
            InlineKeyboardButton(text="Анализ трендов", callback_data="trand_analysis")

        ]
    ])
    await bot.send_photo(caption=
            "<b>🚀 Продвижение:</b>\n\n"
            "Здесь ты можешь найти советы, идеи и стратегии для роста твоего аккаунта, "
            "увеличения охвата и вовлеченности аудитории.",
            reply_markup=kb,
            parse_mode="HTML",
                         photo='AgACAgIAAxkBAAM9aLCKu0bZMjqxQhFwntDM3hANGjUAAjQDMhulPIFJu0WpiQnK3OMBAAMCAAN3AAM2BA',
                         chat_id=message.chat.id
    )

