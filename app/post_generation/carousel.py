from datetime import datetime, timedelta

from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto
from aiogram import Router
from aiogram.fsm.context import FSMContext
import asyncio
import logging

from database import BotDB
from config import TG_TOKEN
from app.states import Form
from app.post_generation.carousel_generator import generate_carousel
from funcs import text_or_voice
from app.subscription_funcs import SubscriptionManager
from aiogram import Bot

db = BotDB('point.db')
router = Router()
bot = Bot(token=TG_TOKEN)
logger = logging.getLogger(__name__)

subscription_manager = SubscriptionManager(db=db, bot=bot)

# -------------------- Выбор платформы --------------------
@router.message(lambda message: message.text == "📌 Карусель")
async def platform_carousel(message: Message, state: FSMContext):
    # УБРАЛИ can_generate() — навигация не должна списывать генерации
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='Instagram', callback_data='instagram'),
         InlineKeyboardButton(text='Telegram', callback_data='telegram')],
    ])
    await message.answer(
        text="<b>Выберите платформу</b>\nдля генерации карусели ⬇️",
        reply_markup=kb,
        parse_mode="HTML"
    )



@router.callback_query(lambda c: c.data in ["instagram", "telegram"])
async def platform_chosen(callback_query: CallbackQuery, state: FSMContext):
    # УБРАЛИ can_generate()
    platform = callback_query.data
    await state.update_data(platform=platform)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=str(i), callback_data=f"{i}_carousel") for i in range(1, 5)],
        [InlineKeyboardButton(text=str(i), callback_data=f"{i}_carousel") for i in range(5, 8)],
    ])
    await callback_query.message.answer_photo(caption='Выберите одну из цветовых схем', reply_markup=kb,
                                              photo="AgACAgIAAxkBAAIIvWi68J0jDjFwss0jx6k8UXDtwX2IAAIE-jEbXwbZSRhDnbZXbs0MAQADAgADdwADNgQ")


@router.callback_query(lambda c: c.data.endswith("_carousel"))
async def scheme_chosen(callback_query: CallbackQuery, state: FSMContext):
    await state.update_data(scheme_number=int(callback_query.data.split("_")[0]))
    await callback_query.message.answer(
        "🎡 Вы выбрали схему\n\n✨ Давай персонализируем карусель!\n✍️ Введи ник, который укажем на карусели.\n\nНапример:\n👉 <b>@point_content</b>",
        parse_mode="HTML"
    )
    await state.set_state(Form.signature)


@router.message(Form.signature)
async def signature(message: Message, state: FSMContext):
    await state.update_data(signature=message.text)
    await message.answer(
        "💡 <i>Выбери тему для генерации:</i>\n\n✍️ Можешь <b>написать текстом</b>\n🎙️ Или <b>отправить голосовое</b> — я сам переведу его в текст.",
        parse_mode="HTML"
    )
    await state.set_state(Form.carousel_theme)


@router.message(Form.carousel_theme)
async def carousel_generation(message: Message, state: FSMContext):
    user_id = message.from_user.id
    sub = db.get_subscription(user_id)

    # --- Инициализация last_reset, если None ---
    if not sub.get("carousel_count_last_reset"):
        today_str = datetime.now().strftime("%Y-%m-%d")
        db.update_subscription(user_id, carousel_count_last_reset=today_str)
        sub["carousel_count_last_reset"] = today_str

    # --- Проверка и сброс счётчика каждые 30 дней ---
    try:
        last_reset = datetime.strptime(sub["carousel_count_last_reset"], "%Y-%m-%d")
    except Exception:
        # если формат неожиданный — перезаписываем текущей датой
        last_reset = datetime.now()
        db.update_subscription(user_id, carousel_count_last_reset=datetime.now().strftime("%Y-%m-%d"))
        sub["carousel_count_last_reset"] = datetime.now().strftime("%Y-%m-%d")

    if datetime.now() - last_reset >= timedelta(days=30):
        # Сбрасываем счётчик и обновляем дату сброса
        db.update_subscription(
            user_id,
            carousel_count=0,
            carousel_count_last_reset=datetime.now().strftime("%Y-%m-%d")
        )
        sub["carousel_count"] = 0
        sub["carousel_count_last_reset"] = datetime.now().strftime("%Y-%m-%d")

    # --- Проверка лимита для базовой подписки ---
    if sub["status"] == 1 and sub.get("carousel_count", 0) >= 12:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 Перейти к оплате", callback_data="go_to_payment")],
        ])
        await message.answer(
            text="⚠️ На базовой подписке доступно только 12 каруселей в месяц. Обновите тариф для безлимита.",
            reply_markup=keyboard
        )
        return

    # ---------------- Проверка доступа (единственный момент списания бесплатной генерации) ----------------
    # can_generate() вернёт True и, при необходимости, сам списывает free_generation.
    if not await subscription_manager.can_generate(user_id):
        return  # notify_if_no_access уже отправил сообщение пользователю

    # Обновим данные подписки после возможного списания free_generation
    sub = db.get_subscription(user_id)

    # --- Всё готово, запускаем генерацию ---
    theme = await text_or_voice(message)
    waiting_msg = await message.answer("⏳ Пожалуйста, подождите", parse_mode='HTML')

    data = await state.get_data()
    prompt = f"{db.get_business(user_id=user_id)} Тема генерации: {theme}"
    platform = data.get("platform")
    scheme_number = int(data.get("scheme_number"))
    sig = data.get("signature")
    style = db.get_style(user_id)

    if scheme_number > 1 and platform == "instagram":
        scheme_number = scheme_number * 2 - 1
    if platform == "telegram":
        scheme_number = scheme_number * 2

    loop = asyncio.get_event_loop()
    request_task = loop.run_in_executor(None, generate_carousel, prompt, scheme_number, sig, style)

    # анимация ожидания
    dots_animation = [
        "⏳ Пожалуйста, подождите.",
        "⏳ Пожалуйста, подождите..",
        "⏳ Пожалуйста, подождите...",
        "⌛ Пожалуйста, подождите...",
        "⌛ Пожалуйста, подождите..",
        "⌛ Пожалуйста, подождите."
    ]
    delay = 0.5
    try:
        while not request_task.done():
            for dots in dots_animation:
                if request_task.done():
                    break
                await asyncio.sleep(delay)
                await waiting_msg.edit_text(dots)
    except asyncio.CancelledError:
        logger.warning("Анимация ожидания была отменена.")

    # результат
    files = await request_task
    await bot.delete_message(chat_id=message.chat.id, message_id=waiting_msg.message_id)

    media_group = []
    for i, file in enumerate(files):
        if i == 0:
            media_group.append(InputMediaPhoto(media=file, caption="📌 Карусель"))
        else:
            media_group.append(InputMediaPhoto(media=file))
    await message.answer_media_group(media_group)

    # --- После успешной генерации: увеличиваем счётчик для базовой подписки ---
    if sub["status"] == 1:
        new_count = sub.get("carousel_count", 0) + 1
        db.update_subscription(user_id, carousel_count=new_count)
