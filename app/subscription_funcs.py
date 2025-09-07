from datetime import datetime, timedelta

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# today_date=datetime.now()
today_date = datetime(2025, 11, 2, 12, 0, 0)  # 1 января 2030, 12:00
class SubscriptionManager:
    def __init__(self, db, bot):
        """
        db: экземпляр BotDB
        bot: экземпляр aiogram.Bot
        """
        self.db = db
        self.bot = bot

    # ------------------- Основная логика -------------------
    def use_free_generation(self, user_id):
        """Списывает одну бесплатную генерацию, возвращает True если генерация использована, False если нет."""
        sub = self.db.get_subscription(user_id)
        if sub["free_generations"] > 0:
            new_free = sub["free_generations"] - 1
            # Не трогаем status — списание free_generations не должно менять статус подписки
            self.db.update_subscription(user_id, free_generations=new_free)
            return True
        return False

    def activate_subscription(self, user_id, plan_type, days=30):
        """
        plan_type: 1 = Базовый, 2 = Продвинутый
        Подписка активна days дней
        """
        end_date = datetime.now() + timedelta(days=days)
        self.db.update_subscription(
            user_id,
            status=plan_type,
            subscription_end=end_date.strftime("%Y-%m-%d %H:%M:%S")
        )

    def is_subscription_active(self, user_id):
        """Проверяет, активна ли подписка у пользователя"""
        sub = self.db.get_subscription(user_id)
        # статус 0 = нет подписки
        if sub["status"] == 0:
            return False

        # Если даты окончания нет — считаем подписку неактивной (чёткая политика)
        if not sub.get("subscription_end"):
            return False

        try:
            end = datetime.strptime(sub["subscription_end"], "%Y-%m-%d %H:%M:%S")
        except Exception:
            # если формат сломан, считаем подписку неактивной и обнуляем статус
            self.db.update_subscription(user_id, status=0, subscription_end=None)
            return False

        if datetime.now() > end:
            # подписка закончилась — сбрасываем статус
            self.db.update_subscription(user_id, status=0, subscription_end=None)
            return False

        return True

    def remaining_free_generations(self, user_id):
        """Возвращает количество оставшихся бесплатных генераций"""
        sub = self.db.get_subscription(user_id)
        return sub["free_generations"]

    # ------------------- Уведомления пользователя -------------------
    async def notify_if_no_access(self, user_id):
        """Отправляет сообщение пользователю, если у него нет доступа к генерации"""
        sub = self.db.get_subscription(user_id)
        payment_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 Перейти к оплате", callback_data="go_to_payment")],
        ])
        if sub["status"] == 0 and sub["free_generations"] == 0:
            await self.bot.send_message(chat_id=user_id,
                                        text="❌ У вас закончились бесплатные генерации и нет активной подписки. Оплатите тариф.",
                                        reply_markup=payment_kb)
            return False
        return True

    async def notify_subscription_active(self, user_id):
        """Отправляет пользователю информацию о его подписке"""
        sub = self.db.get_subscription(user_id)
        if sub["status"] == 0 and sub["free_generations"] == 0:
            msg = "❌ У вас нет активной подписки и закончились бесплатные генерации. Оплатите тариф."
        elif sub["status"] == 0 and sub["free_generations"] > 0:
            msg = f"У вас осталось {sub['free_generations']} бесплатных генераций."
        else:
            msg = f"У вас активна подписка (статус {sub['status']}) до {sub['subscription_end']}."
        await self.bot.send_message(user_id, msg)

    # ------------------- Генерация с проверкой доступа -------------------
    async def can_generate(self, user_id):
        """
        Проверка перед генерацией:
        - Если подписка активна → True
        - Если нет, но есть бесплатные генерации → списываем одну → True
        - Если нет и бесплатных генераций нет → False
        """
        if self.is_subscription_active(user_id):
            return True
        if self.use_free_generation(user_id):
            return True
        await self.notify_if_no_access(user_id)
        return False
