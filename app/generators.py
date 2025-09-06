import re
import time

import openai
import httpx
from openai import AssistantEventHandler, AsyncOpenAI
from typing_extensions import override
import asyncio

from config import AI_TOKEN, MAX_MSG_LEN  # , PROXY
import logging

from database import BotDB

# Логирование для диагностики
logging.basicConfig(level=logging.INFO)

cached_assistant_id = None

db = BotDB('point.db')


# Прокси-сервер
def res(response):
    response = re.sub(r'###(.*?)###', r'<b>\1</b>', response)
    response = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', response)
    response = re.sub(r'####(.*?)', r'*\1*', response)
    response = re.sub(r'###(.*?)', r'\1', response)
    return response



import httpx
from openai import AsyncOpenAI




client = AsyncOpenAI(
    api_key=AI_TOKEN,
    http_client=httpx.AsyncClient(


    )
)




async def get_assistant():
    global cached_assistant_id
    if cached_assistant_id:
        return cached_assistant_id

    try:
        # Попытка получить список ассистентов
        assistants_list = await client.beta.assistants.list()
        for existing_assistant in assistants_list.data:
            if existing_assistant.name == "Point":
                cached_assistant_id = existing_assistant.id
                logging.info(f"Используется существующий ассистент с ID: {cached_assistant_id}")
                return cached_assistant_id

        return cached_assistant_id
    except openai.APIConnectionError as e:
        logging.error(f"Ошибка подключения к API OpenAI: {e}")
        raise e




async def get_thread_content(thread_id):
    # Получаем все сообщения из потока
    messages_response = await client.beta.threads.messages.list(thread_id=thread_id)

    extracted_messages = []
    # Проходим по каждому сообщению
    for message in messages_response.data:
        # Проверяем наличие контента
        if hasattr(message, 'content') and message.content:
            for block in message.content:
                # Проверяем, содержит ли блок текст
                if hasattr(block, 'text') and hasattr(block.text, 'value'):
                    extracted_messages.append({
                        'role': message.role,  # Роль: 'user' или 'assistant'
                        'text': block.text.value  # Текст сообщения
                    })

    return extracted_messages



async def generator(user_id, content, max_retries=15):
    # Получаем assistant_id
    try:
        assistant_id = await get_assistant()
    except Exception as e:
        logging.error(f"❌ Ошибка при получении assistant_id: {e}")
        return

    # Получаем thread_id из БД
    thread_id = db.get_thread(user_id)

    if not thread_id:
        logging.info(f"📭 Поток не найден, создаю новый...")
        try:
            thread = await client.beta.threads.create()
            thread_id = thread.id
            db.update_thread(user_id, thread_id)
        except Exception as e:
            logging.error(f"❌ Ошибка при создании нового потока: {e}")
            return

    for attempt in range(max_retries):
        try:
            # Отправка сообщения пользователю
            response = await client.beta.threads.messages.create(
                thread_id=thread_id,
                role="user",
                content=content,
            )

            logging.info(f"🚀 Создаю запуск для обработки (попытка {attempt + 1})...")
            run_response = await client.beta.threads.runs.create(
                thread_id=thread_id,
                assistant_id=assistant_id,
            )

            while True:
                run_status = await client.beta.threads.runs.retrieve(
                        run_id=run_response.id,
                        thread_id=thread_id
                )

                if run_status.status == 'completed':
                    break
                elif run_status.status == 'failed':
                    logging.warning("❌ Запуск завершился с ошибкой, пересоздаю поток и пробую снова...")
                    # Создаем новый поток
                    thread = await client.beta.threads.create()
                    thread_id = thread.id
                    db.update_thread(user_id, thread_id)
                    # Прерываем текущую попытку и сразу переходим к следующей итерации for
                    continue  # <--- важно, чтобы цикл for сделал следующую попытку

                await asyncio.sleep(5)
            else:
                continue  # если цикл while завершился без break, идем к следующей попытке

            # Если run завершился успешно, получаем сообщения
            messages_response = await client.beta.threads.messages.list(thread_id=thread_id)
            if messages_response.data:
                text = res(messages_response.data[0].content[0].text.value)
                return text
            else:
                logging.warning("⚠️ Сообщений нет.")
                return None

        except openai.APIConnectionError as e:
            logging.warning(f"🌐 Ошибка подключения (попытка {attempt + 1} из {max_retries}): {e}")
            await asyncio.sleep(2 ** attempt)
            if attempt == max_retries - 1:
                logging.error("🚫 Превышено максимальное количество попыток подключения.")
                raise e

        except Exception as e:
            logging.error(f"❗ Неожиданная ошибка: {e}")
            raise e



async def generator_nothread(user_id, content, max_retries=10):
    assistant_id = await get_assistant()
    thread_id = db.get_thread(user_id)

    threadik = await client.beta.threads.create()
    threadik_id = threadik.id

    response = await client.beta.threads.messages.create(
        thread_id=thread_id,
        role="user",
        content=content,
    )

    for attempt in range(max_retries):
        try:
            run_response = await client.beta.threads.runs.create(
                thread_id=threadik_id,
                assistant_id=assistant_id,
            )
            while True:
                run_status = await client.beta.threads.runs.retrieve(run_id=run_response.id, thread_id=threadik_id)
                if run_status.status == 'completed':
                    break
                elif run_status.status == 'failed':
                    logging.error("Запуск завершился с ошибкой")

                    return

                await asyncio.sleep(5)

            messages_response = await client.beta.threads.messages.list(thread_id=threadik_id)
            if messages_response.data:
                text = res(messages_response.data[0].content[0].text.value)
                return text
            else:
                logging.info("Сообщений нет.")
                return None
        except openai.APIConnectionError as e:
            logging.warning(f"Ошибка подключения (попытка {attempt + 1} из {max_retries}): {e}")
            await asyncio.sleep(2 ** attempt)  # Экспоненциальная задержка
            if attempt == max_retries - 1:
                logging.error("Превышено максимальное количество попыток подключения.")
                raise e


async def generate_test(question, max_retries=5, thread_id=None):
    assistant_id = await get_assistant()

    content = f'{question}'

    if not thread_id:
        thread = await client.beta.threads.create()
        thread_id = thread.id

    response = await client.beta.threads.messages.create(
        thread_id=thread_id,
        role="user",
        content=content,
    )

    for attempt in range(max_retries):
        try:
            run_response = await client.beta.threads.runs.create(
                thread_id=thread_id,
                assistant_id=assistant_id,
            )
            while True:
                run_status = await client.beta.threads.runs.retrieve(run_id=run_response.id, thread_id=thread_id)
                if run_status.status == 'completed':
                    break
                elif run_status.status == 'failed':
                    logging.error("Запуск завершился с ошибкой")
                    return

                await asyncio.sleep(5)

            messages_response = await client.beta.threads.messages.list(thread_id=thread_id)
            if messages_response.data:
                text = res(messages_response.data[0].content[0].text.value)
                return text
            else:
                logging.info("Сообщений нет.")
                return None
        except openai.APIConnectionError as e:
            logging.warning(f"Ошибка подключения (попытка {attempt + 1} из {max_retries}): {e}")
            await asyncio.sleep(2 ** attempt)  # Экспоненциальная задержка
            if attempt == max_retries - 1:
                logging.error("Превышено максимальное количество попыток подключения.")
                raise e