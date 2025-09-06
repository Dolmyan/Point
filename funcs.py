import logging
import asyncio
import os
import re
import time
from datetime import datetime, timedelta

from aiogram.enums import ParseMode, ChatMemberStatus
from aiogram.fsm import state
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, \
    KeyboardButton
from aiogram import Router, F, Bot
from aiogram.filters import CommandStart, Command
from app.generators import *
from config import *


db = BotDB('point.db')
router = Router()
bot = Bot(token=TG_TOKEN)

logger = logging.getLogger(__name__)

MAX_MSG_LEN = 4000  # безопасный лимит

async def response_generator(source, request_task, kb=None, bot=None):
    """
    Универсальная функция: принимает либо callback_query, либо message.
    Делит длинный ответ на части и добавляет клавиатуру только к последнему сообщению.
    """
    # Определяем объект message
    if hasattr(source, "message"):  # значит это callback_query
        message = source.message
    else:  # обычный message
        message = source

    # Сообщение ожидания
    waiting_msg = await message.answer("⏳ Пожалуйста, подождите", parse_mode='HTML')

    # Анимация ожидания
    await show_waiting_animation(waiting_msg, request_task)

    # Результат
    response = await request_task

    # Разбиваем на части
    messages = [response[i:i + MAX_MSG_LEN] for i in range(0, len(response), MAX_MSG_LEN)]

    # Отправляем все части
    for part in messages[:-1]:
        await message.answer(text=part, parse_mode='HTML')
    await message.answer(text=messages[-1], parse_mode='HTML', reply_markup=kb)

    # Удаляем сообщение ожидания
    if bot:
        await bot.delete_message(chat_id=message.chat.id, message_id=waiting_msg.message_id)

    return response


async def show_waiting_animation(message, request_task, delay=0.3):
    logger.info(f"Запуск анимации ожидания для сообщения {message.message_id}.")
    dots_animation = [
        "⏳ Пожалуйста, подождите.",
        "⏳ Пожалуйста, подождите..",
        "⏳ Пожалуйста, подождите...",
        "⌛ Пожалуйста, подождите...",
        "⌛ Пожалуйста, подождите..",
        "⌛ Пожалуйста, подождите."
    ]

    try:
        while not request_task.done():
            for dots in dots_animation:
                if request_task.done():
                    break
                await asyncio.sleep(delay)
                await message.edit_text(dots)
                logger.debug(f"Обновлено сообщение ожидания: {dots}")
    except asyncio.CancelledError:
        logger.warning("Анимация ожидания была отменена.")


import subprocess, io
from aiogram.types import Message

async def text_or_voice(message: Message) -> str | None:
    """
    Возвращает текст из сообщения: либо сразу текст, либо
    распознанное голосовое (с корректировкой GPT).
    """
    if message.text:  # обычный текст
        return message.text.strip()

    elif message.voice:  # голосовое сообщение
        file = await message.bot.get_file(message.voice.file_id)
        file_bytes = await message.bot.download_file(file.file_path)

        # Конвертация ogg -> wav
        ogg_data = file_bytes.read()
        process = subprocess.Popen(
            ['ffmpeg', '-i', 'pipe:0', '-f', 'wav', 'pipe:1'],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL
        )
        wav_data, _ = process.communicate(input=ogg_data)

        # Распознавание через Whisper
        audio_file = io.BytesIO(wav_data)
        audio_file.name = "voice.wav"
        transcript = openai.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file
        )
        raw_text = transcript.text

        # Доп. обработка GPT
        response = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Ты ассистент, который исправляет ошибки и улучшает читаемость текста."},
                {"role": "user", "content": f"Отредактируй текст:\n\n{raw_text}"}
            ]
        )
        print(getattr(response.choices[0].message, "content", raw_text).strip())
        return getattr(response.choices[0].message, "content", raw_text).strip()
    elif message.photo:
        return message.caption or "[Фото без подписи]"
    elif message.video:
        return message.caption or "[Видео без подписи]"

    return None
