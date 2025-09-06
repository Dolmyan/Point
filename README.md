[Читать русскую версию → README_ru.md] (README_ru.md)

# 🚀 Point — Content Bot for Creators

**Point** is an assistant for authors and creators: it generates posts, video ideas, carousels, helps with profile design and audience warm-ups.  
Built with `aiogram` + `FastAPI`. Purpose — produce high-quality content tailored to your style.

GitHub: https://github.com/Dolmyan/Point · Telegram: @BigBoyAndroid

---

## 📌 Quick Summary
- Core: **Python 3.12**
- Frameworks: `aiogram` (bot), `FastAPI` (webhooks / web services)
- Database: `sqlite` (`point.db`)
- Payments: **YooKassa**
- Production mode: **webhook** (ngrok for local dev; VPS for production)
- Dependencies: see `requirements.txt` in the repo

---

## 📚 Table of Contents
1. [Features](#features)  
2. [Tech & Dependencies](#tech--dependencies)  
3. [Project Structure](#project-structure)  
4. [Install & Quick Start](#install--quick-start)  
5. [`.env` — template & variables](#env---template--variables)  
6. [Webhook: setup & production notes (VPS)](#webhook-setup--production-notes-vps)  
7. [Nginx + systemd: VPS deployment examples](#nginx--systemd-vps-deployment-examples)  
8. [Database & Backups](#database--backups)  
9. [Security Recommendations](#security-recommendations)  
10. [Commands & Keyboards — examples](#commands--keyboards---examples)  
11. [CI / tests / Docker](#ci--tests--docker)  
12. [Roadmap / TODO / Known issues](#roadmap--todo--known-issues)  
13. [Contacts, Contributing, Thanks](#contacts-contributing-thanks)

---

## ✨ Features
Point is aimed at creators and includes:
- Registration: gathers information about user activity and style (user sends **one example** post for style adaptation).  
- Content generation:
  - `💡 Post ideas`
  - `📌 Carousel` — generate carousels for Instagram / Telegram
  - `🎨 Profile design` — emojis, bio, style
  - `🎬 Video ideas`
- Promotion:
  - Warm-ups (stories_warmup, weekly_warmup)
  - Webinar ideas and scripts
  - Newsletter ideas, trend analysis
- Subscriptions / Payments: YooKassa integration and subscription management via `SubscriptionManager`.
- Admin / profile: check subscription status, edit profile, generation limits, etc.

---

## 🛠 Tech & Dependencies
Main dependencies (full list in `requirements.txt` in repo):

```
aiofiles==24.1.0
aiogram==3.22.0
aiohttp==3.12.15
aiosqlite==0.21.0
fastapi==0.116.1
uvicorn==0.35.0
openai==1.102.0
pillow==11.3.0
yookassa==3.7.0
... (see requirements.txt)
```

> Install dependencies:
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

## 📁 Project Structure (root `Point/`)
```
Point
├── .venv
├── app/                      # main logic (routers, handlers)
├── post_generation/          # post, carousel, reels generation
├── promotion/                # promotion & warmup modules
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

Short descriptions:
- `run.py` — entry point: initializes `Bot`, `Dispatcher`, and `FastAPI`. (Currently starts polling — see Webhook section.)  
- `database.py` — `BotDB` class (sqlite) with tables `users`, `user_requests`, `user_settings`, `subscriptions`.  
- `subscription_funcs.py` — `SubscriptionManager` for activating/deactivating subscriptions.  
- `post_generation/`, `promotion/`, `video_ideas.py`, `profile_design.py` — content-generation logic.  
- `payment.py` — router for payment handling and YooKassa callbacks (there is a `/yookassa/webhook` endpoint in `run.py`).

---

## ▶️ Install & Quick Start
1. Clone the repo:
```bash
git clone https://github.com/Dolmyan/Point.git
cd Point
```

2. Create venv and install:
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

3. Create `.env` (see template below) and fill tokens.

4. Run locally (dev, polling/ngrok):
```bash
# if using polling (as in current run.py)
python run.py

# or run FastAPI via uvicorn
uvicorn run:app --host 0.0.0.0 --port 8000 --reload
```

> For local webhook testing use `ngrok`:
```bash
ngrok http 8000
# then set Telegram webhook to the ngrok URL
```

---

## 🔐 `.env.example` — template (copy as `.env`)
```env
# Telegram
TG_TOKEN=your_telegram_bot_token_here

# OpenAI (if used)
AI_TOKEN=your_openai_api_key_here

# YooKassa
SHOP_ID=your_yookassa_shop_id
YK_TOKEN=your_yookassa_secret_key

# App settings
WEBHOOK_URL=https://your-domain-or-ngrok-url/telegram/webhook
DB_PATH=point.db
LOG_LEVEL=INFO
```

**IMPORTANT:** do not commit `.env`. Keep it in `.gitignore`.

---

## 🔁 Webhook: setup & production notes (VPS)
`run.py` contains `FastAPI` and a YooKassa endpoint (`/yookassa/webhook`). To handle Telegram webhooks in production:

1. Register HTTPS URL with Telegram:
```bash
curl -F "url=https://<your-domain>/telegram/webhook" "https://api.telegram.org/bot$TG_TOKEN/setWebhook"
```

2. Ensure HTTPS (Let's Encrypt / certbot) or proxy via nginx with SSL to uvicorn.

3. Webhook receiver implementation:
- Add `/telegram/webhook` route in `FastAPI` to receive Telegram updates and forward them to the `Dispatcher`.
- In production mode replace `dp.start_polling()` with webhook setup and cleanup on startup/shutdown.

> Example pseudo-logic:
```py
from aiogram import types

@app.post("/telegram/webhook")
async def telegram_webhook(request: Request):
    data = await request.json()
    update = types.Update(**data)
    await dp.process_update(update)
    return {"ok": True}
```

Note: aiogram Dispatcher helpers differ between versions — check docs for `dp.process_update` / `dp.feed_update`. Keep polling for dev and create a separate prod mode for webhook.

---

## 🧰 Nginx + systemd — VPS deployment examples
Assume `uvicorn` listens on `127.0.0.1:8000`. Nginx is an HTTPS reverse proxy.

### Example Nginx config `/etc/nginx/sites-available/point`:
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

### Example systemd unit `/etc/systemd/system/point.service`:
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

Then:
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now point.service
sudo nginx -t && sudo systemctl restart nginx
```

Set Telegram webhook to your domain URL afterwards.

---

## 💾 Database & Backups
`BotDB` uses sqlite `point.db`. Tables:
- `users(user_id, username, created_at, status, thread_id)`
- `user_requests(user_id, count, request_limit)`
- `user_settings(user_id, style, business)`
- `subscriptions(user_id, status, free_generations, carousel_count, subscription_end, created_at, updated_at)`

Backup recommendations:
- Regularly copy the DB file (rsync / cron):
```bash
0 3 * * * cp /home/someuser/Point/point.db /home/someuser/backups/point_$(date +\%F).db
```
- Use `sqlite3` backup:
```bash
sqlite3 point.db ".backup 'backup.db'"
```
- Keep migration scripts for schema changes (manual ALTER / CREATE).

---

## 🔒 Security Recommendations
- Never commit `.env` or secrets to git.
- Use HTTPS for webhooks (Let's Encrypt).
- Store tokens securely and rotate on compromise.
- Harden VPS: firewall, SSH keys, 2FA for accounts.
- Use webhook URL with a secret path: `/telegram/webhook/<random_secret>`.
- Rotate YooKassa keys between dev and prod.

---

## ⌨️ Commands & Keyboards — examples
Main keyboard (example):
```
💡 Post ideas
📌 Carousel
🎨 Profile design
🎬 Video ideas
🚀 Promotion
🛠️ Profile
```

Promotion inline menu includes:
- stories_warmup
- weekly_warmup
- webinar_ideas
- webinar_script
- newsletter_ideas
- trand_analysis

Registration prompt:
> 💪 **Show your style!**  
> Send **one example** of your post or a Telegram-format script — use your own material.  
> 📝 This will help adapt content generation to your unique style.

---

## 📦 CI / tests / Docker
- No Docker for now (per request).  
- No tests yet; recommend adding unit tests for `database.py` and core generators before enabling CI.  
- If desired, I can prepare a GitHub Actions workflow for linting/testing.

---

## 🧭 Roadmap / TODO
- ✅ Basic content generation (posts, carousels, reels)  
- ✅ YooKassa integration (webhook exists)  
- 🔲 Switch polling → webhook mode for production  
- 🔲 DB migrations / schema versioning  
- 🔲 Unit/integration tests  
- 🔲 Optional Dockerfile

---

## 📬 Contacts & Contributing
- Repo: https://github.com/Dolmyan/Point  
- Author: @BigBoyAndroid (Telegram)  
- Contributions: PRs welcome — include short description in PR.

---

## 📝 Useful commands
```bash
git clone https://github.com/Dolmyan/Point.git
cd Point

python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# dev run
python run.py
# or
uvicorn run:app --host 0.0.0.0 --port 8000 --reload

# set webhook example
curl -F "url=https://example.com/telegram/webhook" "https://api.telegram.org/bot$TG_TOKEN/setWebhook"
```

---


