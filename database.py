import json
import logging
import sqlite3
from datetime import datetime


class BotDB:
    def __init__(self, database_file):
        self.connection = sqlite3.connect(database_file)
        self.cursor = self.connection.cursor()
        self.create_table()

    def create_table(self):
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER UNIQUE ON CONFLICT REPLACE,
                username TEXT,
                created_at TIMESTAMP,
                status INTEGER DEFAULT 1,
                thread_id TEXT
            );
        ''')

        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_requests (
                user_id INTEGER UNIQUE ON CONFLICT REPLACE,
                count INTEGER DEFAULT 0,
                request_limit INTEGER DEFAULT 5
            );
        ''')

        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_settings (
                user_id INTEGER UNIQUE ON CONFLICT REPLACE,
                style TEXT,
                business TEXT

            );
        ''')

        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS subscriptions (
                user_id INTEGER UNIQUE ON CONFLICT REPLACE,
                status INTEGER NOT NULL DEFAULT 0,           -- 0: нет подписки, 1: базовый/бесплатный, 2: продвинутый
                free_generations INTEGER NOT NULL DEFAULT 5, -- Кол-во бесплатных генераций
                carousel_count INTEGER NOT NULL DEFAULT 0,   -- количество сгенерированных каруселей

                subscription_end TEXT,                       -- Дата окончания подписки в формате ISO
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
        ''')

        self.connection.commit()

    def add_user(self, user_id, username):
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # таблица users
        self.cursor.execute('''
            INSERT INTO users (user_id, username, created_at)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET username=excluded.username
        ''', (user_id, username, now))

        # таблица user_requests
        self.cursor.execute('''
            INSERT INTO user_requests (user_id, count, request_limit)
            VALUES (?, 0, 5)
            ON CONFLICT(user_id) DO NOTHING
        ''', (user_id,))

        # таблица user_settings
        self.cursor.execute('''
            INSERT INTO user_settings (user_id, style)
            VALUES (?, "default")
            ON CONFLICT(user_id) DO NOTHING
        ''', (user_id,))

        self.cursor.execute('''
            INSERT INTO subscriptions (user_id, status, free_generations, carousel_count, carousel_count_last_reset, subscription_end)
            VALUES (?, 0, 5, 0, date('now'), NULL)
            ON CONFLICT(user_id) DO NOTHING
        ''', (user_id,))

        self.connection.commit()

    def update_business(self, user_id, business):
        self.cursor.execute(
                "UPDATE user_settings SET business = ? WHERE user_id = ?",
                (business, user_id)
        )
        return self.connection.commit()

    def update_style(self, user_id, style):
        self.cursor.execute(
                "UPDATE user_settings SET style = ? WHERE user_id = ?",
                (style, user_id)
        )
        return self.connection.commit()

    def update_thread(self, user_id, thread):
        self.cursor.execute(
            "UPDATE users SET thread_id = ? WHERE user_id = ?",
            (thread, user_id)
        )
        return self.connection.commit()
    def get_thread(self, user_id):
        # Пример SQL-запроса для получения user_id по username
        self.cursor.execute("SELECT thread_id FROM users WHERE user_id = ?", (user_id,))
        result = self.cursor.fetchone()

        if result:
            return result[0]
        else:
            return None

    def get_user_status(self, user_id):
        """
        Возвращает словарь с информацией о подписке и генерациях:
        status: 0, 1, 2
        count: использованные генерации
        limit: максимальное количество генераций
        """
        self.cursor.execute(
            "SELECT count, request_limit FROM user_requests WHERE user_id = ?",
            (user_id,)
        )
        row = self.cursor.fetchone()
        if not row:
            return {"status": 0, "count": 0, "limit": 5}  # если нет данных, считаем, что всё закончилось
        count, limit = row
        # Получаем статус из таблицы users
        self.cursor.execute(
            "SELECT status FROM users WHERE user_id = ?",
            (user_id,)
        )
        status_row = self.cursor.fetchone()
        if status_row:
            status = status_row[0]
        else:
            status = 1  # по умолчанию бесплатная подписка
        return {"status": status, "count": count, "limit": limit}

    def get_subscription(self, user_id):
        self.cursor.execute(
                'SELECT status, free_generations, subscription_end, carousel_count FROM subscriptions WHERE user_id = ?',
                (user_id,)
        )
        row = self.cursor.fetchone()
        if row:
            return {
                "status": row[0],
                "free_generations": row[1],
                "subscription_end": row[2],
                "carousel_count": row[3] or 0  # если None, ставим 0
            }
        # Если пользователя нет, создаём дефолтную запись
        self.cursor.execute(
                'INSERT INTO subscriptions (user_id) VALUES (?)',
                (user_id,)
        )
        self.connection.commit()
        return {"status": 0, "free_generations": 5, "subscription_end": None, "carousel_count": 0}

    def update_subscription(self, user_id, status=None, free_generations=None, subscription_end=None,
                            carousel_count=None, carousel_count_last_reset=None):
        updates = []
        params = []

        if status is not None:
            updates.append("status = ?")
            params.append(status)
        if free_generations is not None:
            updates.append("free_generations = ?")
            params.append(free_generations)
        if subscription_end is not None:
            updates.append("subscription_end = ?")
            params.append(subscription_end)
        if carousel_count is not None:
            updates.append("carousel_count = ?")
            params.append(carousel_count)
        if carousel_count_last_reset is not None:
            updates.append("carousel_count_last_reset = ?")
            params.append(carousel_count_last_reset)

        if updates:
            params.append(user_id)
            self.cursor.execute(
                f"UPDATE subscriptions SET {', '.join(updates)}, updated_at = datetime('now') WHERE user_id = ?",
                tuple(params)
            )
            self.connection.commit()

    def get_all_user_ids(self):
        self.cursor.execute('SELECT user_id FROM users')
        rows = self.cursor.fetchall()
        user_ids = [row[0] for row in rows]
        return user_ids

    def get_all_users(self):
        # Получает всех пользователей и их дату окончания подписки
        self.cursor.execute("SELECT user_id FROM users")
        return self.cursor.fetchall()

    def get_business(self, user_id):
        self.cursor.execute('SELECT business FROM user_settings WHERE user_id = ?', (user_id,))
        row = self.cursor.fetchone()
        if row:
            return row[0]
        return 'none'

    def get_style(self, user_id):
        self.cursor.execute('SELECT style FROM user_settings WHERE user_id = ?', (user_id,))
        row = self.cursor.fetchone()
        if row:
            return row[0]
        return 'none'


    def get_user_id_by_username(self, username):
        # Пример SQL-запроса для получения user_id по username
        self.cursor.execute("SELECT user_id FROM users WHERE username = ?", (username,))
        result = self.cursor.fetchone()

        # Если пользователь найден, возвращаем его ID, иначе None
        if result:
            return result[0]  # user_id
        return None





