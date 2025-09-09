import logging
from aiogram import Router, Bot
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from yookassa import Configuration, Payment

from config import TG_TOKEN, SHOP_ID, YK_TOKEN

# Настройка YooKassa
Configuration.account_id = SHOP_ID
Configuration.secret_key = YK_TOKEN

router = Router()
bot = Bot(token=TG_TOKEN)
logger = logging.getLogger(__name__)


@router.callback_query(lambda c: c.data in ["go_to_payment"])
async def show_tariffs(callback_query: CallbackQuery, state: FSMContext):
    """Показ тарифов с кнопками оплаты"""
    text = """✨ <b>Базовый тариф</b> ✨
<u>Что входит:</u>
🟦 1 профиль
🟦 12 каруселей в месяц
🟦 Генерация постов
🟦 Идеи для постов
🟦 Дизайн и оформление профиля
🟦 Прогрев в сторис
🟦 Недельный прогрев
💰 Цена: 790₽

🚀 <b>Продвинутый тариф</b> 🚀
<u>Что входит:</u>
🟩 4 профиля
🟩 Бесконечное количество каруселей 
🟩 Идеи для постов
🟩 Дизайн и оформление профиля
🟩 Прогрев в сторис
🟩 Недельный прогрев
🟩 Идеи для вебинаров 
🟩 Сценарий для вебинаров 
🟩 Идеи для рассылок 
🟩 Анализ трендов в твоей нише 
🟩 Идеи для твоих видео
💎 Цена: 1600₽
"""

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Базовый тариф", callback_data="pay_basic")],
        [InlineKeyboardButton(text="💳 Продвинутый тариф", callback_data="pay_advanced")]
    ])

    await callback_query.message.answer(text, parse_mode="HTML", reply_markup=keyboard)


@router.callback_query(lambda c: c.data in ["pay_basic", "pay_advanced"])
async def process_payment(callback_query: CallbackQuery):
    """Создание платежа в YooKassa"""
    if callback_query.data == "pay_basic":
        amount = 790
        plan_name = "Базовый тариф"
    else:
        amount = 1600
        plan_name = "Продвинутый тариф"

    # Создание платежа с metadata (user_id, план)
    payment = Payment.create({
        "amount": {
            "value": str(amount),
            "currency": "RUB"
        },
        "confirmation": {
            "type": "redirect",
            "return_url": "https://example.com/success"  # просто заглушка
        },
        "capture": True,
        "description": f"Оплата {plan_name}",
        "metadata": {
            "user_id": callback_query.from_user.id,
            "plan": plan_name
        },
        "test": False  # тестовый режим
    })

    # Отправляем пользователю ссылку на оплату
    await callback_query.message.answer(
        f"Вы выбрали <b>{plan_name}</b>.\n"
        f"Сумма к оплате: <b>{amount}₽</b>\n"
        f"👉 <a href='{payment.confirmation.confirmation_url}'>Оплатить</a>\n\n",
        parse_mode="HTML",
        disable_web_page_preview=True
    )
