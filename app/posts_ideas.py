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

kb_topics = InlineKeyboardMarkup(row_width=2, inline_keyboard=[
        [
            InlineKeyboardButton(text="🌲 Вечно зеленые темы", callback_data="evergreen"),
            InlineKeyboardButton(text="☀️ Утренние stories", callback_data="morning_stories")
        ],
        [
            InlineKeyboardButton(text="🤫 Редко обсуждают", callback_data="rarely_discussed"),
            InlineKeyboardButton(text="🔥 Хайповые темы", callback_data="hype_topics")
        ],
        [
            InlineKeyboardButton(text="🙈 Никто не пишет", callback_data="nobody_writes"),
            InlineKeyboardButton(text="🚫 Запретные", callback_data="forbidden")
        ],
        [
            InlineKeyboardButton(text="💥 Скандальные", callback_data="scandalous"),
            InlineKeyboardButton(text="❓ Популярные вопросы", callback_data="popular_questions")
        ],
        [
            InlineKeyboardButton(text="🧐 Мифы о работе", callback_data="work_myths"),
            InlineKeyboardButton(text="🧪 Экспериментальные", callback_data="experimental")
        ],
        [
            InlineKeyboardButton(text="😨 Страхи перед походом к", callback_data="fears")
        ]
    ])

@router.message(lambda message: message.text == "💡 Идеи постов")
async def posts_ideas(message: Message, state: FSMContext):
    user_id = message.from_user.id

    from app.subscription_funcs import SubscriptionManager
    subscription_manager = SubscriptionManager(db, bot)
    if not await subscription_manager.can_generate(user_id):
        return  # пользователь уведомлен, генерация не идёт
    await bot.send_photo(
            caption=(
                "<b>📝 Идеи постов</b>\n\n"
                "Я придумаю 10 рабочих идей для постов в соцсетях (Instagram, TikTok, Telegram): "
                "цепляющий заголовок, короткое описание контента, призыв к действию (лайк, комментарий, подписка). "
                "Каждая идея будет готова к публикации и легко реализуема.\n\n"),
            parse_mode="HTML",
            photo='AgACAgIAAxkBAAPEaLCrKvsasGL7Hoh0gjXJ6ctaMD0AAmwBMhulPIlJecqv0uAfDxoBAAMCAAN3AAM2BA',
            chat_id=message.chat.id
    )
    await message.answer(
            text="💡 Выберите интересные темы для контента:",
            reply_markup=kb_topics
    )

@router.callback_query(lambda c: c.data in ["posts_ideas"])
async def posts_ideas(callback_query: CallbackQuery, state: FSMContext):
    await bot.send_photo(
            caption=(
                "<b>📝 Идеи постов</b>\n\n"
                "Я придумаю 10 рабочих идей для постов в соцсетях (Instagram, TikTok, Telegram): "
                "цепляющий заголовок, короткое описание контента, призыв к действию (лайк, комментарий, подписка). "
                "Каждая идея будет готова к публикации и легко реализуема.\n\n"),
            parse_mode="HTML",
            photo='AgACAgIAAxkBAAPEaLCrKvsasGL7Hoh0gjXJ6ctaMD0AAmwBMhulPIlJecqv0uAfDxoBAAMCAAN3AAM2BA',
            chat_id=callback_query.message.chat.id
    )


    # Отправка пользователю с текстом
    await callback_query.message.answer(
            text="💡 Выберите интересные темы для контента:",
            reply_markup=kb_topics
    )


TOPIC_CALLBACKS = [
    "evergreen", "morning_stories", "rarely_discussed", "hype_topics",
    "nobody_writes", "forbidden", "scandalous", "popular_questions",
    "work_myths", "experimental", "fears"
]

PROMPTS_TOPICS = {
    "evergreen": (
        "Задача: придумать 10 evergreen-идей для постов — тем, которые всегда релевантны и работают долго.\n"
        "Для каждой идеи кратко укажи:\n"
        "🔹 Заголовок/тема\n"
        "🪝 Хук для первой строки\n"
        "📝 Краткая структура/что написать (1–2 пункта)\n"
        "👉 CTA (что просим в конце: комментарий/подписка/ссылка)\n\n"
        "Пиши просто, полезно и без вводных/заключительных фраз."
    ),

    "morning_stories": (
        "Задача: придумать 10 идей для утренних Stories — быстрые форматы, которые включают людей в день.\n"
        "Для каждой идеи укажи:\n"
        "🔹 Короткое описание (1 предложение)\n"
        "🕒 Формат/длительность (сек.)\n"
        "🪝 Хук/вопрос для вовлечения\n"
        "👉 CTA (реакция/ответ в сторис/свайп)\n\n"
        "Пиши емко и без лишних слов."
    ),

    "rarely_discussed": (
        "Задача: придумать 10 тем, которые редко обсуждают в вашей нише (уникальный контент).\n"
        "Для каждой идеи: Заголовок — Почему это важно (1 предложение) — Как подать в посте/сторис (конкретный пример).\n\n"
        "Будь смелым, но профессиональным. Без вводных/заключительных фраз."
    ),

    "hype_topics": (
        "Задача: придумать 10 актуальных, хайповых тем/рецептов контента, которые легко адаптировать под тренды.\n"
        "Для каждой идеи: Тема — Как подогнать под тренд (пример звука/формата) — Быстрый сценарий (3 шага).\n\n"
        "Фокус на скорость реализации и virality."
    ),

    "nobody_writes": (
        "Задача: придумать 10 тем, о которых почти никто не пишет в вашей нише (низкая конкуренция).\n"
        "Для каждой: Тема — Короткое объяснение почему мало кто пишет — Идея подачи (формат/первые строки).\n\n"
        "Пиши ясно и конкретно."
    ),

    "forbidden": (
        "Задача: придумать 10 «запретных» тем (провокационные, но профессиональные и этичные). "
        "Для каждой: Тема — Риск/ограничение — Как безопасно подать (тон, слова, disclaimer) — CTA.\n\n"
        "Важно: не предлагай незаконные или опасные действия, только этичные провокации."
    ),

    "scandalous": (
        "Задача: 10 скандальных/провокационных заголовков и концептов (для повышения охвата), с указанием безопасной подачи.\n"
        "Для каждого: Заголовок — Краткий сценарий — Как смягчить негатив (одна фраза) — CTA.\n\n"
        "Не выходить за правила платформ и не оскорблять людей."
    ),

    "popular_questions": (
        "Задача: собрать 10 популярных вопросов в нише и превратить каждый в идею поста.\n"
        "Для каждого: Вопрос — Краткий ответ (2–3 предложения) — Идея подачи (карусель/пост/видео) — CTA.\n\n"
        "Пиши просто и полезно."
    ),

    "work_myths": (
        "Задача: придумать 10 мифов о работе/профессии и развенчать их в формате поста.\n"
        "Для каждого: Миф — Короткий refutation (факт/пример) — Идея визуала/факта — CTA.\n\n"
        "Формат: образовательный и убедительный."
    ),

    "experimental": (
        "Задача: предложить 10 экспериментальных форматов контента (необычные форматы и подходы).\n"
        "Для каждого: Название формата — Коротко как реализовать — Почему может сработать — Призыв к тесту.\n\n"
        "Пиши креативно, но применимо."
    ),

    "fears": (
        "Задача: придумать 10 идей постов/сторис про страхи и возражения целевой аудитории (например: страх перед первым уроком, перед ценой и т.д.).\n"
        "Для каждой: Страх/возражение — Короткая эмпатичная фраза (как откликнуться) — Контраргумент/решение — CTA.\n\n"
        "Тон: эмпатичный, поддерживающий, мотивирующий."
    ),
}



# 1) Универсальный callback handler: сохраняем тему и просим нишу/пример
@router.callback_query(lambda c: c.data in TOPIC_CALLBACKS)
async def topic_chosen(callback_query: CallbackQuery, state: FSMContext):
    selected = callback_query.data
    await state.update_data(selected_topic=selected)
    await callback_query.message.answer(
            "💡 На какую тему ты хочешь сгенерировать текст?\n\n"
            "✍️ Можешь написать текстом\n"
            "🎙️ Или записать голосовое.",
            parse_mode="HTML"
    )
    await state.set_state(Form.posts_idea)

@router.message(Form.posts_idea)
async def posts_idea(message: Message, state: FSMContext):
    theme=await text_or_voice(message)
    data = await state.get_data()
    selected = data["selected_topic"]
    goal = f"{db.get_business(user_id=message.from_user.id)} Тема генерации: {theme}"
    prompt = PROMPTS_TOPICS[selected]
    content = f'''
    {goal}
    {prompt}
    '''
    request_task = asyncio.create_task(
            generator(user_id=message.from_user.id, content=content)
    )
    response = await response_generator(message, request_task, bot=bot)

