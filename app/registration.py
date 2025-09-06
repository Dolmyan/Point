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
from funcs import text_or_voice

db = BotDB('point.db')
router = Router()
bot = Bot(token=TG_TOKEN)

logger = logging.getLogger(__name__)


@router.callback_query(lambda c: c.data in ['registration'])
async def registration(callback_query: CallbackQuery, state: FSMContext):
    await callback_query.message.answer(
            "Расскажи немного о своём бизнесе или о том, чем ты занимаешься — "
            "так я смогу точнее понимать твои задачи и делать контент, который реально будет работать на тебя, а не в пустоту.\n\n"
            "→ В какой сфере ты создаёшь контент?\n"
            "→ Кто твоя аудитория, с кем нравится работать?\n"
            "→ Какой у тебя подход, в чём отличия?\n"
            "Всё, что отражает тебя и твоё дело.\n\n"
            "💡 Можешь накатать текстом, но <b>голосовое — будет круче</b>. "
            "Так получится передать больше деталей и эмоций, а мне проще поймать твой вайб. 🎤",
            parse_mode="HTML"
    )
    await state.set_state(Form.business)

@router.message(Form.business)
async def business(message: Message, state: FSMContext):
    business = await text_or_voice(message)

    db.update_business(user_id=message.from_user.id, business=business)
    await message.answer(
            "💪 <b>Покажи свой стиль!</b>\n\n"
            "Чтобы я понял твой подход, отправь <b>один пример</b> твоего поста или сценария для формата <b>«Telegram»</b> — "
            "можно использовать пример только из твоих собственных материалов.\n\n"
            "📝 Это поможет мне адаптировать генерацию контента под твой уникальный стиль и формат.",
            parse_mode="HTML"
    )
    await state.set_state(Form.reg_style)

processed_media_groups = set()


@router.message(Form.reg_style)
async def reg_style(message: Message, state: FSMContext):
    if message.media_group_id:
        if message.media_group_id in processed_media_groups:
            return  # игнорируем остальные фото из альбома
        processed_media_groups.add(message.media_group_id)
    reg_style=await text_or_voice(message)
    db.update_style(user_id=message.from_user.id, style=reg_style)
    await message.answer(
            "✨ <b>Готово!</b> Настройка пройдена.\n"
            "Теперь я заряжен помогать тебе пилить контент под твой стиль и задачи.\n\n"
            "Выбери нужную функцию из меню ниже ⬇️",
            parse_mode="HTML",
            reply_markup=menu
    )
    await state.clear()


