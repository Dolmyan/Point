import logging
import asyncio
from logging.handlers import RotatingFileHandler

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from fastapi import FastAPI, Request

from config import TG_TOKEN
from app.handlers import router
from app.registration import router as registration_router
from app.subscription_info import router as subscription_info_router
from app.promotion.promotion import router as promotion_router
from app.promotion.universal import router as universal_router
from app.video_ideas import router as video_ideas_router
from app.profile_design import router as profile_design_router
from app.posts_ideas import router as posts_ideas_router
from app.post_generation.post_generation import router as post_generation_router
from app.post_generation.text_post import router as post_generation_text_post_router
from app.post_generation.reels_generation import router as reels_generation_router
from app.post_generation.carousel import router as carousel_router
from app.payment import router as payment_router
from database import BotDB

# ===================
# Логирование
# ===================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

file_handler = RotatingFileHandler("app.log", maxBytes=10**6, backupCount=3)
file_handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
root_logger = logging.getLogger()
root_logger.addHandler(file_handler)


# ===================
# Инициализация бота
# ===================
bot = Bot(token=TG_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
db = BotDB("point.db")

from app.subscription_funcs import SubscriptionManager
subscription_manager = SubscriptionManager(db=db, bot=bot)


# Подключение всех роутеров
dp.include_router(router)
dp.include_router(registration_router)
dp.include_router(subscription_info_router)
dp.include_router(promotion_router)
dp.include_router(universal_router)
dp.include_router(video_ideas_router)
dp.include_router(profile_design_router)
dp.include_router(posts_ideas_router)
dp.include_router(post_generation_router)
dp.include_router(post_generation_text_post_router)
dp.include_router(reels_generation_router)
dp.include_router(carousel_router)
dp.include_router(payment_router)


# ===================
# FastAPI
# ===================
app = FastAPI()


@app.on_event("startup")
async def on_startup():
    """Запуск aiogram вместе с FastAPI"""
    asyncio.create_task(dp.start_polling(bot))


@app.post("/yookassa/webhook")
async def yookassa_webhook(request: Request):
    data = await request.json()
    event = data.get("event")
    obj = data.get("object", {})

    user_id = obj.get("metadata", {}).get("user_id")
    plan_name = obj.get("metadata", {}).get("plan")

    if event == "payment.succeeded" and user_id:
        # Определяем тип плана
        plan_type = 1 if "Базовый" in plan_name else 2
        # Активируем подписку через SubscriptionManager
        subscription_manager.activate_subscription(user_id=user_id, plan_type=plan_type, days=30)

        await bot.send_message(
            user_id,
            f"✅ Оплата прошла успешно!\nВы получили доступ к тарифу <b>{plan_name}</b> на 30 дней",
            parse_mode="HTML"
        )

    elif event == "payment.canceled" and user_id:
        await bot.send_message(user_id, "❌ Оплата отменена.", parse_mode="HTML")

    elif event == "payment.waiting_for_capture":
        logging.info(f"Платеж ожидает подтверждения: {obj}")

    return {"status": "ok"}