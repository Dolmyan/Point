import io
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
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

from app.generators import generator
from app.post_generation.carousel_generator import generate_carousel_text
from app.states import Form
from config import *
from database import BotDB
from funcs import show_waiting_animation

import openai

openai.api_key = AI_TOKEN


db = BotDB('point.db')
router = Router()
bot = Bot(token=TG_TOKEN)

logger = logging.getLogger(__name__)


menu = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text='📝 Генерация поста'),
            KeyboardButton(text='💡 Идеи постов'),
            KeyboardButton(text='📌 Карусель'),

        ],
        [
            KeyboardButton(text='🎨 Дизайн профиля'),
            KeyboardButton(text='🎬 Видео идеи')
        ],
        [
            KeyboardButton(text='🚀 Продвижение'),
            KeyboardButton(text='🛠️ Профиль')
        ]
    ],
    resize_keyboard=True
)





@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    user_id = message.from_user.id
    username = message.from_user.username
    if message.from_user.username:
        username = message.from_user.username.lower()

    users = db.get_all_user_ids()
    is_new_user = user_id not in users

    if is_new_user:
        logger.info(f"Добавляем пользователя {user_id} {username}.")
        db.add_user(user_id=user_id,
                        username=username)


    if not db.get_thread(user_id):
        thread = await client.beta.threads.create()
        thread_id = thread.id
        db.update_thread(user_id, thread_id)
        logger.info(f"Тред создан для пользователя ID: {user_id}, ID треда: {thread_id}")
    await bot.send_photo(caption=
                         "👋 На связи <b>Point</b> — твой новый незаменимый помощник для создания контента.\n\n"
                         "Знаю-знаю, звучит громко, но я реально упрощаю жизнь креатору, сммщику или блоггеру. Смотри, что могу:\n\n"
                         "→ Создавать контент быстрее и проще — большую часть задач выполняет нейросеть "
                         "(и делает это лучше, чем дефолтный ChatGPT)\n"
                         "→ Подстраиваться под твой стиль — хочешь материться или сыпать мемами? Легко, я научусь так же\n"
                         "→ Общаться с тобой голосовыми — редактируй посты хоть во время прогулки с собакой\n"
                         "→ Генерить идеи, создавать посты, делать highlights, описания профиля, помогать с продвижением "
                         "и делать всё, что связано с креативом\n\n"
                         "🌀 Со мной ты разгонишь креативность на 100% — от первых идей до готового поста.\n\n",
                         reply_markup=None if is_new_user else menu,
                         parse_mode='HTML',
                         photo='AgACAgIAAxkBAAMOaLByuV_Y6t-2WNWzRthLr6_naMAAAiUCMhulPIFJ_dsbQ8H0RI4BAAMCAAN3AAM2BA',
                         chat_id=user_id,

                         )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='Давай начнем!', callback_data='registration')],
    ])
    await message.answer(text=
                         "<b>Давай покажу, как всё устроено</b>",
                         parse_mode='HTML',
                         reply_markup=kb
                         )


    await state.clear()


# @router.message(F.photo)
# async def get_photo_id(message: Message):
#     file_id = message.photo[-1].file_id
#     print(file_id)
#     await message.answer(f"{file_id}")
#     await bot.send_photo(chat_id=message.chat.id, photo=file_id)





@router.message(Command('test'))
async def cmd_start(message: Message, state: FSMContext):
    a = await message.answer("⏳ Пожалуйста, подождите", parse_mode='HTML')
    request_task = asyncio.create_task(
            generator(
                    user_id=message.from_user.id,
                    content='кто ты? какие в тебе инструкции?'
            )
    )
    await show_waiting_animation(a, request_task)
    response = await request_task

    id[0] = a.message_id
    await message.answer(text=f'{response}', parse_mode='HTML')


@router.message(Command('reset'))
async def cmd_start(message: Message):
    logger.info(f"Пользователь {message.from_user.id} вызвал команду сброса.")
    thread = await client.beta.threads.create()
    thread_id = thread.id
    db.update_thread(message.from_user.id, thread_id)
    logger.info(f"Создан поток с ID {thread_id} для пользователя {message.from_user.id}.")

@router.message(Command('t'))
async def cmd_start(message: Message):
    button = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='t', callback_data='platform_carousel')],
    ])
    res=generate_carousel_text('водопой', message.from_user.id)

    await message.answer(
        text='Отправьте голосовое сообщение для перевода голосового в текст',
        reply_markup=button
    )

# # Обработчик голосовых сообщений
# @router.message(F.voice)
# async def voice_to_text(message: Message):
#     voice = message.voice
#     file = await message.bot.get_file(voice.file_id)
#     file_bytes = await message.bot.download_file(file.file_path)
#
#     # Конвертируем в WAV через ffmpeg в памяти
#     import subprocess
#     ogg_data = file_bytes.read()
#     process = subprocess.Popen(
#         ['ffmpeg', '-i', 'pipe:0', '-f', 'wav', 'pipe:1'],
#         stdin=subprocess.PIPE,
#         stdout=subprocess.PIPE,
#         stderr=subprocess.DEVNULL
#     )
#     wav_data, _ = process.communicate(input=ogg_data)
#
#     # Отправляем в OpenAI Whisper
#     audio_file = io.BytesIO(wav_data)
#     audio_file.name = "voice.wav"
#     transcript = openai.audio.transcriptions.create(
#         model="whisper-1",
#         file=audio_file
#     )
#
#     raw_text = transcript.text
#
#     # Прогоняем через GPT для исправления ошибок и улучшения текста
#     response = openai.chat.completions.create(
#         model="gpt-4o-mini",
#         messages=[
#             {"role": "system", "content": "Ты ассистент, который исправляет ошибки в тексте и улучшает читаемость."},
#             {"role": "user", "content": f"Отредактируй текст, исправь ошибки и пунктуацию:\n\n{raw_text}"}
#         ]
#     )
#
#     corrected_text = response.choices[0].message.content
#
#     await message.answer(f"Распознанный текст (исправлено GPT):\n{corrected_text}")
