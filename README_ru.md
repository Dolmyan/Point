# 🚀 Point — контент-бот для креаторов

**Point** — помощник для авторов и креаторов: генерирует посты, идеи для видео, карусели, помогает с дизайном профиля и прогревом аудитории.  
Написан на `aiogram` + `FastAPI`. Цель — создавать качественный контент, адаптированный под ваш стиль.

[Репозиторий на GitHub](https://github.com/Dolmyan/Point) · Telegram: [@BigBoyAndroid](https://t.me/BigBoyAndroid)

---

## 📌 Быстрая сводка
- Ядро: **Python 3.12**
- Фреймворки: `aiogram` (бот), `FastAPI` (веб-сервисы / вебхуки)
- База: `sqlite` (`point.db`)
- Платежи: **YooKassa**
- Режим продакшн: **webhook** (ngrok для локальной разработки, VPS — в проде)
- Dependencies: полный список в `requirements.txt` (в репо)

---

## 🧭 Содержание
1. [Функциональность](#функциональность)  
2. [Технологии и зависимости](#технологии-и-зависимости)  
3. [Структура проекта](#структура-проекта)  
4. [Установка и локальный запуск (быстрый старт)](#установка-и-локальный-запуск-быстрый-старт)  
5. [Файл `.env` — шаблон и описание переменных](#файл-env---шаблон-и-описание-переменных)  
6. [Webhook: настройка и пример для продакшена (VPS)](#webhook-настройка-и-пример-для-продакшена-vps)  
7. [Nginx + systemd: примеры конфигураций для VPS](#nginx--systemd-примеры-конфигураций-для-vps)  
8. [База данных и бэкапы](#база-данных-и-бэкапы)  
9. [Безопасность и рекомендации](#безопасность-и-рекомендации)  
10. [Команды и клавиатуры (UI) — примеры взаимодействия](#команды-и-клавиатуры-ui---примеры-взаимодействия)  
11. [CI / тесты / Docker](#ci--тесты--docker)  
12. [Roadmap / TODO / известных проблем](#roadmap--todo--известных-проблем)  
13. [Контакты, вклад, благодарности](#контакты-вклад-благодарности)

---

## ✨ Функциональность
Point ориентирован на креаторов и включает:
- Регистрация: сбор информации о деятельности и стиле (пользователь отправляет **1 пример** своего поста для адаптации генерации).  
- Генерация контента:
  - `💡 Идеи постов`
  - `📌 Карусель` — генерация карусели для Instagram / Telegram
  - `🎨 Дизайн профиля` — эмоджи, био и стиль
  - `🎬 Видео идеи`
- Продвижение:
  - Прогревы (stories warmup, weekly warmup)
  - Идеи и сценарии вебинаров
  - Идеи рассылок, анализ трендов
- Подписки / Платежи: интеграция с YooKassa, управление подписками (через `SubscriptionManager`).
- Админ/профиль: просмотр статуса подписки, изменение профиля, лимиты генераций и т.д.

---

## 🛠 Технологии и зависимости
Основные зависимости (полный список в `requirements.txt` в корне репо):

```
aiofiles==24.1.0
aiogram==3.22.0
aiohappyeyeballs==2.6.1
aiohttp==3.12.15
aiosqlite==0.21.0
fastapi==0.116.1
uvicorn==0.35.0
openai==1.102.0
pillow==11.3.0
yookassa==3.7.0
... (и др. — см. requirements.txt)
```

> Команда для установки зависимостей:
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

## 📁 Структура проекта (корень `Point/`)
```
Point
├── .venv
├── app/                      # основная логика (роутеры, хэндлеры)
├── post_generation/          # генерация постов, каруселей, рилсов
├── promotion/                # модули продвижения и прогрева
├── generators.py
├── handlers.py
├── payment.py
├── posts_ideas.py
├── profile_design.py
├── registration.py
├── states.py
├── subscription_funcs.py
├── subscription_info.py
├── video_ideas.py
├── .env
├── app.log
├── config.py
├── database.py               # BotDB (sqlite)
├── funcs.py
├── point.db
├── run.py                    # FastAPI + aiogram
└── requirements.txt
```

Коротко по файлам/модулям:
- `run.py` — точка входа: инициализация `Bot`, `Dispatcher`, `FastAPI`. (В текущем варианте стартует polling — см. раздел Webhook ниже.)  
- `database.py` — класс `BotDB` (sqlite) с таблицами `users`, `user_requests`, `user_settings`, `subscriptions`.  
- `subscription_funcs.py` — `SubscriptionManager` для активации/деактивации подписок.  
- `post_generation/`, `promotion/`, `video_ideas.py`, `profile_design.py` — логика генерации контента.  
- `payment.py` — роутер для обработки платежей и callback/интеграции с YooKassa (в `run.py` есть endpoint `/yookassa/webhook`).

---

## ▶️ Установка и локальный запуск (быстрый старт)
1. Клонируем репозиторий:
```bash
git clone https://github.com/Dolmyan/Point.git
cd Point
```

2. Создаём виртуальное окружение и ставим зависимости:
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

3. Создаём файл `.env` (см. шаблон ниже) и заполняем токены.

4. Запускаем локально (разработка, polling/ngrok):
```bash
# если использовать polling (как сейчас в run.py)
python run.py

# или запуск FastAPI через uvicorn (если want to run web part)
uvicorn run:app --host 0.0.0.0 --port 8000 --reload
```

> Для локального теста webhooks удобно использовать `ngrok`:
```bash
ngrok http 8000
# затем выставить setWebhook на Telegram (см. раздел Webhook ниже)
```

---

## 🔐 `.env.example` — шаблон (копировать как `.env` и заполнить)
```env
# Telegram
TG_TOKEN=your_telegram_bot_token_here

# OpenAI (если используется)
AI_TOKEN=your_openai_api_key_here

# YooKassa
SHOP_ID=your_yookassa_shop_id
YK_TOKEN=your_yookassa_secret_key

# Настройки приложения
WEBHOOK_URL=https://your-domain-or-ngrok-url/telegram/webhook  # пример
DB_PATH=point.db
LOG_LEVEL=INFO
```


---

## 🔁 Webhook: настройка и рекомендации (локально → VPS)
В `run.py` сейчас есть `FastAPI` и endpoint для YooKassa (`/yookassa/webhook`). Для обработки webhook-обновлений от Telegram на проде рекомендуется:

1. Зарегистрировать HTTPS URL у Telegram:
```bash
curl -F "url=https://<your-domain>/telegram/webhook" "https://api.telegram.org/bot$TG_TOKEN/setWebhook"
```

2. Обеспечить HTTPS (Let's Encrypt / certbot) или проксирование через nginx (HTTPS) на ваш uvicorn.

3. Реализация webhook-приёма:
- В простом варианте вы добавляете роут `/telegram/webhook` в `FastAPI`, который принимает JSON от Telegram и передаёт обновление в `Dispatcher` (dp) для обработки.
- В `run.py` на production: вместо `dp.start_polling()` делаем установку webhook в startup и удаление при shutdown.

> Пример логики (схема — адаптируй под код):
```py
# в run.py (псевдо-код):
from aiogram import types

@app.post("/telegram/webhook")
async def telegram_webhook(request: Request):
    data = await request.json()
    update = types.Update(**data)
    await dp.process_update(update)   # или подходящий метод Dispatcher в aiogram v3
    return {"ok": True}
```

> Установка webhook (пример):
```bash
curl -F "url=https://example.com/telegram/webhook" "https://api.telegram.org/bot$TG_TOKEN/setWebhook"
```

**Примечание:** API aiogram/Dispatcher имеет разные helper-методы в разных версиях — проверь `aiogram` доки для `dp.process_update` / `dp.feed_update`. Если не уверены — оставьте `dp.start_polling()` для локальной разработки и делайте отдельный файл/режим для продакшна.

---

## 🧰 Nginx + systemd — пример деплоя на VPS (Timeweb / любой VPS)
Предположим: `uvicorn` слушает `127.0.0.1:8000`. Nginx — публичный HTTPS-прокси.

### Nginx конфиг (пример)
`/etc/nginx/sites-available/point`:
```nginx
server {
    listen 80;
    server_name example.com;

    location / {
        return 301 https://$host$request_uri;
    }
}

server {
    listen 443 ssl;
    server_name example.com;

    ssl_certificate /etc/letsencrypt/live/example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/example.com/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_buffering off;
    }
}
```

### systemd unit (пример)
`/etc/systemd/system/point.service`:
```ini
[Unit]
Description=Point bot (uvicorn)
After=network.target

[Service]
User=someuser
Group=somegroup
WorkingDirectory=/home/someuser/Point
Environment="PATH=/home/someuser/Point/.venv/bin"
ExecStart=/home/someuser/Point/.venv/bin/uvicorn run:app --host 127.0.0.1 --port 8000
Restart=on-failure
RestartSec=5s

[Install]
WantedBy=multi-user.target
```

Команды:
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now point.service
sudo nginx -t && sudo systemctl restart nginx
```

После этого вызови `setWebhook` с `https://example.com/telegram/webhook`.

---

## 💾 База данных и бэкапы
`BotDB` использует sqlite: `point.db`. Таблицы:
- `users(user_id, username, created_at, status, thread_id)`
- `user_requests(user_id, count, request_limit)`
- `user_settings(user_id, style, business)`
- `subscriptions(user_id, status, free_generations, carousel_count, subscription_end, created_at, updated_at)`

Рекомендации по бэкапу:
- Регулярно копировать файл `point.db` (rsync / cron):
```bash
# ежедневный бэкап (пример в crontab)
0 3 * * * cp /home/someuser/Point/point.db /home/someuser/backups/point_$(date +\%F).db
```
- При обновлении схемы — держать миграции или скрипты schema-upgrade (ручные ALTER/CREATE).
- Для экспорта можно использовать `sqlite3`:
```bash
sqlite3 point.db ".backup 'backup.db'"
```

---

## 🔒 Безопасность и рекомендации
- **Никогда** не коммитить `.env` или секреты в репозиторий. `.gitignore` уже должен содержать `.env`.
- Используй HTTPS для webhook (Let's Encrypt).
- Храни токены в безопасном месте и ротацируй ключи при утечке.
- На VPS — добавь брандмауэр (ufw/iptables) и ограничь доступ по SSH (ключи, 2FA).
- Дай webhook URL с секретным префиксом: `/telegram/webhook/<random_secret>` — чтобы усложнить подбор.
- Логи: ротируй (`RotatingFileHandler` уже используется в `run.py`).
- Для YooKassa используй тестовые ключи в dev, реальные — в prod.

---

## ⌨️ Команды и клавиатуры — примеры UI
Главное меню (пример клавиатуры):
```
💡 Идеи постов
📌 Карусель
🎨 Дизайн профиля
🎬 Видео идеи
🚀 Продвижение
🛠️ Профиль
```

Inline-меню продвижения:
- Прогрев в сторис (`stories_warmup`)
- Недельный прогрев (`weekly_warmup`)
- Идеи вебинаров (`webinar_ideas`)
- Сценарий вебинара (`webinar_script`)
- Идеи рассылок (`newsletter_ideas`)
- Анализ трендов (`trand_analysis`)

Пример сообщения при регистрации (в `registration`):
> 💪 **Покажи свой стиль!**  
> Чтобы я понял твой подход, отправь **один пример** твоего поста или сценария для формата **«Telegram»** — можно использовать пример только из твоих собственных материалов.  
> 📝 Это поможет адаптировать генерацию контента под твой уникальный стиль.

---

## 📦 CI / тесты / Docker
- Докера в проекте не будет (по твоему запросу).  
- Если позже захочешь — можно добавить `Dockerfile` и `docker-compose` для упрощённого деплоя.  
- Тестов нет; рекомендую добавить базовые unit-тесты для `database.py` и ключевых функций генерации перед включением CI.  
- Если потребуется — подготовлю `GitHub Actions` workflow для линтинга и тестирования.

---

## 🧭 Roadmap / TODO
- ✅ Базовая генерация постов, каруселей и рилсов  
- ✅ Интеграция YooKassa (webhook уже есть)  
- 🔲 Webhook-ready production mode (сменить polling → webhook) — в README описано как настроить  
- 🔲 Миграции БД / версия схемы  
- 🔲 Юнит/интеграционные тесты  
- 🔲 Dockerfile (опционально)

---

## 📬 Контакты, вклад, благодарности
- Репо: https://github.com/Dolmyan/Point  
- Автор / контакт: @BigBoyAndroid (Telegram)  
- Вклад: PR принимаются. Пулл-реквесты — описывайте коротко в комментарии.

---

## 📝 Полезные команды (коротко)
```bash
git clone https://github.com/Dolmyan/Point.git
cd Point

python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# запуск (dev)
python run.py
# или
uvicorn run:app --host 0.0.0.0 --port 8000 --reload

# set webhook (пример)
curl -F "url=https://example.com/telegram/webhook" "https://api.telegram.org/bot$TG_TOKEN/setWebhook"
```

---

