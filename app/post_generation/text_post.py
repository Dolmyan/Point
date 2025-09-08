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
from funcs import show_waiting_animation, response_generator

db = BotDB('point.db')
router = Router()
bot = Bot(token=TG_TOKEN)

logger = logging.getLogger(__name__)


@router.callback_query(lambda c: c.data in ["platform_text"])
async def choose_platform(callback_query: CallbackQuery, state: FSMContext):
    await state.update_data(platform=callback_query.data)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Telegram", callback_data="text_telegram")],
        [InlineKeyboardButton(text="Threads", callback_data="text_threads")],
        [InlineKeyboardButton(text="Хуки", callback_data="text_hooks")],
    ])

    await callback_query.message.answer(
            "<b>Выберите тип текстового поста:</b>\n\n"
            "Telegram — пост для Telegram канала.\n"
            "Threads — короткие цепочки постов.\n"
            "Хуки — идеи для цепляющих заголовков и первых строк.\n"
            "Если хотите вернуться назад, нажмите 'Назад'.",
            parse_mode="HTML",
            reply_markup=kb
    )


@router.callback_query(lambda c: c.data in ["text_telegram", "text_threads", "text_hooks", "text_back"])
async def choose_text_type(callback_query: CallbackQuery, state: FSMContext):
    await state.update_data(text_type=callback_query.data)
    data = await state.get_data()
    content = f"""
    Ты — экспертный автор контента, который помогает создавать профессиональные посты для соцсетей. 

    === НАЧАЛО БЛОКА СТИЛЯ (используй ЕГО ДОСЛОВНО) ===
    {db.get_style(callback_query.from_user.id)}
    === КОНЕЦ БЛОКА СТИЛЯ ===

    Учитывай данные:
    Тема поста: {data['post_theme']}
    Идеи/поток мыслей пользователя: {data.get('user_theme', 'Пользователь не добавил поток мыслей — опирайся на тему поста')}
    Формат публикации: {data['text_type']}

    Правила генерации (строго):
    1. Используй стиль из блока «НАЧАЛО БЛОКА СТИЛЯ» ДОСЛОВНО: сохраняй пунктуацию, эмодзи, регистр, длину абзацев, списки и форматирование. Не замещай или не удаляй эмодзи без явной причины.
    2. Подстраивай лексику, тон и ритм под этот стиль (слова, частоту коротких/длинных предложений, «вы/ты», уровень формальности).
    3. Выбирай формат генерации по полю «Формат публикации»:

    — Если формат = "текстовый пост":  
       Пиши связный пост с обязательным хук-вступлением → развитие → вывод/инсайт. Дай 1–3 конкретных совета/факта/преимущества. Заверши лёгким CTA.

    — Если формат = "хуки":  
       Сначала выведи тему отдельной строкой.  
       Затем через разделитель («- - - ... - - - - -») выдай **несколько блоков хуков** (по 3 примера в каждом).  
       Блоки могут быть такими: провокационные/спорные, ошибки, сторителлинг, вопросы, ценность/выгода, любопытство/тизер, боль/узнаваемая ситуация, статистика, экспериментальные.  
       Каждый хук — это короткая фраза/заголовок.  
       Формат вывода строго списками.

    — Если формат = "threads":  
       Сначала выведи тему отдельной строкой.  
       Затем через разделитель («- - - ... - - - - -») оформи развернутую нить: несколько коротких абзацев (3–6), где каждый абзац — отдельная мысль или часть аргументации.  
       Используй стрелки «→» для выделения списков.  
       Заверши сильным выводом или правилом + лёгким CTA.  
       Структура должна напоминать ленту «твитов/тредов», как в примере threads.

    4. НЕ добавляй ничего сверх: никаких пояснений, инструкций или примечаний. Только сам пост.
    5. Если стиль пустой или содержит «[без подписи]» — используй нейтральный экспертный тон, кратко и уверенно.

    Выведи только результат — готовый пост, без кавычек и объяснений.
    """

    request_task = asyncio.create_task(
            generator(user_id=callback_query.from_user.id, content=content)
    )
    response = await response_generator(callback_query, request_task, bot=bot)
    await state.set_state(Form.clear)
    await state.clear()
