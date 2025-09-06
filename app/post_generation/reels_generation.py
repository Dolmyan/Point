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





@router.callback_query(lambda c: c.data == "platform_reels")
async def platform_reels_handler(callback_query: CallbackQuery):
    platform_reels_kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="Экспертный", callback_data="reels_expert"),
                    InlineKeyboardButton(text="Сторителлинг", callback_data="reels_story")
                ],
                [
                    InlineKeyboardButton(text="Диалоговый", callback_data="reels_dialog"),
                    InlineKeyboardButton(text="Хуки", callback_data="reels_hooks")
                ],

            ]
    )
    await callback_query.message.answer(
        "Выберите тип Reels:",
        reply_markup=platform_reels_kb
    )

@router.callback_query(lambda c: c.data in ["reels_expert", "reels_story", "reels_dialog", "reels_hooks"])
async def process_reels_callbacks(callback_query: CallbackQuery, state: FSMContext):
    await state.update_data(reels_type=callback_query.data)
    a = await callback_query.message.answer("⏳ Пожалуйста, подождите", parse_mode='HTML')

    data=await state.get_data()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Вернуться назад", callback_data="post_topic_next")]
    ])
    style = db.get_style(callback_query.from_user.id)

    content = f"""
    Ты — креативный сценарист для Reels/TikTok. Твоя задача — ПРЕВРАТИТЬ тему в цепляющий динамичный сценарий, строго следуя переданному стилю.

    === НАЧАЛО БЛОКА СТИЛЯ (используй ЕГО ДОСЛОВНО) ===
    {style}
    === КОНЕЦ БЛОКА СТИЛЯ ===

    Учитывай данные:
    Тема Reels: {data['post_theme']}
    Идеи/поток мыслей пользователя: {data.get('user_theme', 'Пользователь не добавил поток мыслей — опирайся на тему Reels')}
    Тип Reels: {data['reels_type']}

    Правила генерации (строго):
    1. Используй текст из блока «НАЧАЛО БЛОКА СТИЛЯ» ДОСЛОВНО — сохраняй эмодзи, пунктуацию, регистр, размеры абзацев и форматирование (тоном, риторикой). Не добавляй объяснений о стиле.
    2. Хук: первые 3 секунды — обязателен (вопрос / шок-факт / провокация). Сделай 1 выразительную строку/реплику как начало.
    3. Структура: хук → раскрытие (ключевая идея/доказательство/действие) → вывод/призыв к действию.
    4. Реплики: короткие, удобные для озвучки — 1–2 предложения; отдельные строки для каждой реплики/кадра.
    5. Вставь конкретные подсказки для визуала: кадры, жесты, смена плана, текст на экране, тайминги (примерно 0–3s, 3–8s, 8–15s и т.д.).
    6. Учитывай {data['reels_type']}: 
       - «Экспертный» — фокус на 1–3 ценных совета/факта;  
       - «Сторителлинг» — мини-нарратив с эмоциональным крючком и моралью;  
       - «Диалоговый» — форматируй как диалог (2 персонажа), чёткие реплики;  
       - «Хуки» — сгенерируй 5–7 коротких вариантов зацепок (каждый на новой строке).
    7. Тон: экспертный, дружелюбный, динамичный, но придерживайся манеры из блока стиля (если в стиле «ты/сленг» — используй его).
    8. Не добавляй альтернативных версий, разъяснений или мета-комментариев. Только готовый сценарий (скрипт/лэйаут) — ничего лишнего.
    9. Если стиль пуст или содержит «[без подписи]» — используй нейтральный экспертный динамичный тон, короткие реплики и чёткие визуальные подсказки.
    10. При конфликте между дословностью стиля и требованиями формата ищи компромисс: сохраняй ключевые элементы стиля (эмодзи/тона/фразы) и адаптируй длину под озвучку.

    Выведи только готовый сценарий, без кавычек и комментариев.
    """

    request_task = asyncio.create_task(
            generator(user_id=callback_query.from_user.id, content=content)
    )
    response = await response_generator(callback_query, request_task, bot=bot)
    await state.clear()

