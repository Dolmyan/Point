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


@router.message(lambda message: message.text == "📝 Генерация поста")
async def post_generation(message: Message, state: FSMContext):
    user_id = message.from_user.id

    from app.subscription_funcs import SubscriptionManager
    subscription_manager = SubscriptionManager(db, bot)
    if not await subscription_manager.can_generate(user_id):
        return  # пользователь уведомлен, генерация не идёт
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Далее", callback_data="post_topic_next")]
    ])

    caption = (
        "<b>Итак, как это всё работает? 🌀</b>\n\n"
        "Начинаем с темы. Тема — это не готовый пост и не сценарий на миллион знаков. "
        "Это просто мысль, инсайт или вайб, который ты хочешь донести до своей аудитории. "
        "Пиши в максимально свободной форме.\n\n"
        "<b>Например:</b> «Как я успеваю постить крутые рилсы каждый день и трачу на это 10 минут?»\n\n"
        "У тебя таких тем наверняка миллион, просто они пока живут где-то в заметках или в голове. "
        "Вот их мы и будем превращать в крутые посты.\n\n"
        "Нажми кнопку ниже, чтобы продолжить."
    )

    await bot.send_photo(
            caption=caption,
            reply_markup=kb,
            parse_mode="HTML",
            photo='AgACAgIAAxkBAAPpaLCwBye_8JsHum2cRnyEM0_RWiwAApYBMhulPIlJcWv4BwbzMWQBAAMCAAN3AAM2BA',
            chat_id=message.chat.id
    )

@router.callback_query(lambda c: c.data == "post_topic_next")
async def post_topic_next(callback_query: CallbackQuery, state: FSMContext):


    caption = (
        "И знаешь, тему даже не нужно как-то красиво называть. Просто скидываешь свои мысли — выгружаешь всё из головы, как есть.\n\n"
        "Можно текстом. Но по-честному, самый удобный формат — голосовое 🎤\n"
        "Буквально 3–5 минут наговорил всё, что думаешь по теме, и готово.\n\n"
        "Дальше уже подключаем нейросеть: она аккуратно разберёт весь твой поток сознания и превратит его в структурированную основу. "
        "Следующий шаг — делаем из этого полноценные посты под разные платформы."
    )

    # отправляем фото с подписью и кнопкой
    await bot.send_photo(
        caption=caption,
        parse_mode="HTML",
        photo='AgACAgIAAxkBAAPsaLCwxfvFH8c0dMjlbEwcKKfkhlMAAp0BMhulPIlJO-GdbcHY0g0BAAMCAAN3AAM2BA',
        chat_id=callback_query.message.chat.id
    )

    # переводим FSM в состояние ожидания ввода темы/голоса от пользователя
    await state.set_state(Form.post_generation_theme)

@router.message(Form.post_generation_theme)
async def receive_theme(message: Message, state: FSMContext):
    user_theme = await text_or_voice(message)  # или голосовое сообщение, если обрабатывается отдельно
    await state.update_data(user_theme=user_theme)  # сохраняем в FSM

    # Переходим к финальному шагу
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Погнали", callback_data="start_content_generation")]
    ])

    caption = (
        "<b>Финальный шаг — делаем контент ✨</b>\n\n"
        "Ты выбираешь, куда нужен контент:\n"
        "→ текстовый пост (например, в Telegram),\n"
        "→ сценарий для видео (Reels, TikTok — что угодно),\n"
        "→ ветку коротких постов (типа Threads)."
    )

    await bot.send_photo(
        caption=caption,
        reply_markup=kb,
        parse_mode="HTML",
        photo='AgACAgIAAxkBAAPvaLCx0NTlUc8Wyng8yPW6QjB7JrcAAs8BMhulPIlJ4YdqB-0eOtYBAAMCAAN3AAM2BA',
        chat_id=message.chat.id
    )

@router.callback_query(lambda c: c.data == "start_content_generation")
async def start_content_generation(callback_query: CallbackQuery, state: FSMContext):
    post_theme = "none"
    await state.update_data(post_theme=post_theme)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Текстовый пост", callback_data="platform_text")],
        [InlineKeyboardButton(text="Рилс", callback_data="platform_reels")],
    ])

    await callback_query.message.answer(
        "<b>Выберите платформу для генерации контента:</b>\n\n"
        "Текстовый пост — например, для Telegram или соцсетей.\n"
        "Рилс — короткие видео для Instagram Reels/TikTok.\n",
        parse_mode="HTML",
        reply_markup=kb
    )
