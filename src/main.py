"""
Telegram Bot на Yandex Cloud Serverless Functions
Использует Yandex Cloud Responses API с выбором агента и памятью диалогов
"""

import json
import os
import openai
import requests
import boto3
from botocore.config import Config


# Конфигурация из переменных окружения
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
YANDEX_CLOUD_API_KEY = os.environ.get("YANDEX_CLOUD_API_KEY")
YANDEX_CLOUD_FOLDER = os.environ.get("YANDEX_CLOUD_FOLDER")
S3_BUCKET = os.environ.get("S3_BUCKET")
AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY")

# Доступные агенты (ID -> название)
# Задайте через переменную окружения AGENTS_JSON или укажите здесь
# Пример: {"agent_id": "🤖 Название агента"}
DEFAULT_AGENTS = {}

def get_agents() -> dict:
    """Получает список агентов из переменной окружения или дефолтный"""
    agents_json = os.environ.get("AGENTS_JSON")
    if agents_json:
        try:
            return json.loads(agents_json)
        except:
            pass
    return DEFAULT_AGENTS


def get_ai_client():
    """Создаёт клиент для Yandex Cloud Responses API"""
    return openai.OpenAI(
        api_key=YANDEX_CLOUD_API_KEY,
        base_url="https://rest-assistant.api.cloud.yandex.net/v1",
        project=YANDEX_CLOUD_FOLDER
    )


def get_s3_client():
    """Создаёт клиент для Yandex Object Storage"""
    return boto3.client(
        "s3",
        endpoint_url="https://storage.yandexcloud.net",
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        config=Config(signature_version="s3v4"),
        region_name="ru-central1"
    )


def get_dialog_state(chat_id: int) -> dict:
    """Получает состояние диалога из S3"""
    try:
        s3 = get_s3_client()
        response = s3.get_object(Bucket=S3_BUCKET, Key=f"dialogs/{chat_id}.json")
        return json.loads(response["Body"].read().decode("utf-8"))
    except Exception:
        agents = get_agents()
        default_agent = list(agents.keys())[0] if agents else None
        return {"previous_response_id": None, "message_count": 0, "agent_id": default_agent}


def save_dialog_state(chat_id: int, state: dict) -> None:
    """Сохраняет состояние диалога в S3"""
    try:
        s3 = get_s3_client()
        s3.put_object(
            Bucket=S3_BUCKET,
            Key=f"dialogs/{chat_id}.json",
            Body=json.dumps(state),
            ContentType="application/json"
        )
    except Exception as e:
        print(f"Error saving state: {e}")


def delete_dialog_state(chat_id: int) -> None:
    """Удаляет состояние диалога (сброс контекста)"""
    try:
        s3 = get_s3_client()
        s3.delete_object(Bucket=S3_BUCKET, Key=f"dialogs/{chat_id}.json")
    except Exception:
        pass


def get_ai_response(message: str, chat_id: int) -> str:
    """Получает ответ от агента через Responses API с учётом контекста"""
    try:
        client = get_ai_client()
        state = get_dialog_state(chat_id)
        agent_id = state.get("agent_id")
        
        if not agent_id:
            return "❌ Агент не выбран. Используйте /agents для выбора агента."
        
        # Вызов Responses API с выбранным агентом
        response = client.responses.create(
            prompt={"id": agent_id},
            input=message,
            previous_response_id=state.get("previous_response_id")
        )
        
        # Сохраняем состояние для следующего сообщения
        save_dialog_state(chat_id, {
            "previous_response_id": response.id,
            "message_count": state.get("message_count", 0) + 1,
            "agent_id": agent_id
        })
        
        return response.output_text
        
    except Exception as e:
        return f"❌ Ошибка: {str(e)}"


def send_telegram_message(chat_id: int, text: str, reply_markup: dict = None) -> dict:
    """Отправляет сообщение в Telegram"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown"
    }
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)
    
    response = requests.post(url, json=payload)
    return response.json()


def answer_callback_query(callback_query_id: str, text: str = None) -> dict:
    """Отвечает на callback query"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/answerCallbackQuery"
    payload = {"callback_query_id": callback_query_id}
    if text:
        payload["text"] = text
    return requests.post(url, json=payload).json()


def edit_message_text(chat_id: int, message_id: int, text: str, reply_markup: dict = None) -> dict:
    """Редактирует сообщение"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/editMessageText"
    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
        "parse_mode": "Markdown"
    }
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)
    return requests.post(url, json=payload).json()


def send_typing_action(chat_id: int) -> None:
    """Отправляет индикатор набора текста"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendChatAction"
    requests.post(url, json={"chat_id": chat_id, "action": "typing"})


def get_main_menu():
    """Возвращает главное меню бота"""
    return {
        "keyboard": [
            [{"text": "🆕 Новый диалог"}, {"text": "🤖 Агенты"}],
            [{"text": "📊 Статус"}, {"text": "❓ Помощь"}]
        ],
        "resize_keyboard": True,
        "one_time_keyboard": False
    }


def get_agents_inline_keyboard(current_agent_id: str = None):
    """Возвращает inline клавиатуру для выбора агента"""
    agents = get_agents()
    buttons = []
    
    for agent_id, agent_name in agents.items():
        # Отмечаем текущего агента галочкой
        if agent_id == current_agent_id:
            display_name = f"✅ {agent_name}"
        else:
            display_name = agent_name
        
        buttons.append([{
            "text": display_name,
            "callback_data": f"agent:{agent_id}"
        }])
    
    return {"inline_keyboard": buttons}


def handle_command(chat_id: int, command: str) -> dict:
    """Обрабатывает команды бота"""
    
    if command in ["/start"]:
        # При старте не сбрасываем агента, только контекст
        state = get_dialog_state(chat_id)
        agent_id = state.get("agent_id")
        agents = get_agents()
        if not agent_id and agents:
            agent_id = list(agents.keys())[0]
        
        save_dialog_state(chat_id, {
            "previous_response_id": None,
            "message_count": 0,
            "agent_id": agent_id
        })
        
        agent_name = agents.get(agent_id, "Не выбран") if agent_id else "Не выбран"
        
        text = (
            "👋 *Привет!* Я AI-ассистент на базе YandexGPT.\n\n"
            "🧠 Я запоминаю контекст нашего разговора.\n\n"
            f"🤖 *Текущий агент:* {agent_name}\n\n"
            "*Доступные команды:*\n"
            "🆕 *Новый диалог* — сбросить контекст\n"
            "🤖 *Агенты* — выбрать агента\n"
            "📊 *Статус* — информация о диалоге\n"
            "❓ *Помощь* — справка\n\n"
            "Просто напиши мне сообщение! 💬"
        )
        
        send_telegram_message(chat_id, text, get_main_menu())
        return {"ok": True, "action": "start"}
    
    elif command in ["🆕 Новый диалог", "/new"]:
        state = get_dialog_state(chat_id)
        agent_id = state.get("agent_id")
        
        # Сбрасываем контекст, но сохраняем агента
        save_dialog_state(chat_id, {
            "previous_response_id": None,
            "message_count": 0,
            "agent_id": agent_id
        })
        
        text = "🆕 *Диалог сброшен!*\n\nКонтекст очищен. Начинаем новый разговор."
        send_telegram_message(chat_id, text, get_main_menu())
        return {"ok": True, "action": "new"}
    
    elif command in ["🤖 Агенты", "/agents"]:
        state = get_dialog_state(chat_id)
        current_agent = state.get("agent_id")
        
        text = "🤖 *Выберите агента:*\n\nКаждый агент имеет свои настройки, промпт и инструменты."
        send_telegram_message(chat_id, text, get_agents_inline_keyboard(current_agent))
        return {"ok": True, "action": "agents"}
    
    elif command in ["/status", "📊 Статус"]:
        state = get_dialog_state(chat_id)
        msg_count = state.get("message_count", 0)
        has_context = "✅ Да" if state.get("previous_response_id") else "❌ Нет"
        agent_id = state.get("agent_id")
        agents = get_agents()
        agent_name = agents.get(agent_id, "Не выбран") if agent_id else "Не выбран"
        
        text = (
            f"📊 *Статус диалога*\n\n"
            f"🤖 Агент: {agent_name}\n"
            f"💬 Сообщений: {msg_count}\n"
            f"🧠 Контекст сохранён: {has_context}"
        )
        send_telegram_message(chat_id, text, get_main_menu())
        return {"ok": True, "action": "status"}
    
    elif command in ["/help", "❓ Помощь"]:
        text = (
            "❓ *Справка*\n\n"
            "Я — AI-ассистент с памятью. Я помню наш разговор "
            "и могу отвечать с учётом контекста.\n\n"
            "*Команды:*\n"
            "• /new — начать новый диалог\n"
            "• /agents — выбрать агента\n"
            "• /status — статус диалога\n"
            "• /help — эта справка\n\n"
            "*Агенты:*\n"
            "Вы можете переключаться между разными агентами. "
            "Каждый агент имеет свой промпт и инструменты.\n\n"
            "💡 *Совет:* При смене агента контекст диалога сохраняется!"
        )
        send_telegram_message(chat_id, text, get_main_menu())
        return {"ok": True, "action": "help"}
    
    return None


def handle_callback_query(callback_query: dict) -> dict:
    """Обрабатывает callback query (нажатие inline кнопок)"""
    callback_id = callback_query.get("id")
    data = callback_query.get("data", "")
    message = callback_query.get("message", {})
    chat_id = message.get("chat", {}).get("id")
    message_id = message.get("message_id")
    
    if not chat_id or not data:
        return {"ok": True, "message": "Invalid callback"}
    
    # Обработка выбора агента
    if data.startswith("agent:"):
        agent_id = data.split(":", 1)[1]
        agents = get_agents()
        
        if agent_id not in agents:
            answer_callback_query(callback_id, "❌ Агент не найден")
            return {"ok": False, "message": "Agent not found"}
        
        state = get_dialog_state(chat_id)
        old_agent = state.get("agent_id")
        
        # Сохраняем нового агента (контекст сохраняем, если агент тот же)
        if old_agent != agent_id:
            # При смене агента сбрасываем контекст
            save_dialog_state(chat_id, {
                "previous_response_id": None,
                "message_count": 0,
                "agent_id": agent_id
            })
            answer_callback_query(callback_id, f"✅ Агент изменён! Контекст сброшен.")
        else:
            answer_callback_query(callback_id, f"ℹ️ Этот агент уже выбран")
        
        agent_name = agents[agent_id]
        
        # Обновляем сообщение
        text = f"🤖 *Выбран агент:* {agent_name}\n\nТеперь можете начать диалог!"
        edit_message_text(chat_id, message_id, text, get_agents_inline_keyboard(agent_id))
        
        return {"ok": True, "action": "agent_selected", "agent_id": agent_id}
    
    answer_callback_query(callback_id)
    return {"ok": True, "message": "Unknown callback"}


def process_message(update: dict) -> dict:
    """Обрабатывает входящее сообщение от Telegram"""
    
    # Обработка callback query (inline кнопки)
    if "callback_query" in update:
        return handle_callback_query(update["callback_query"])
    
    message = update.get("message", {})
    chat_id = message.get("chat", {}).get("id")
    text = message.get("text", "")
    
    if not chat_id or not text:
        return {"ok": True, "message": "No message to process"}
    
    # Проверяем команды
    command_result = handle_command(chat_id, text)
    if command_result:
        return command_result
    
    # Показываем индикатор набора
    send_typing_action(chat_id)
    
    # Получаем ответ от агента с контекстом
    ai_response = get_ai_response(text, chat_id)
    
    # Отправляем ответ
    send_telegram_message(chat_id, ai_response, get_main_menu())
    
    return {"ok": True, "message": "Response sent"}


def handler(event, context):
    """
    Точка входа для Yandex Cloud Function
    Обрабатывает вебхуки от Telegram
    """
    try:
        if isinstance(event.get("body"), str):
            body = json.loads(event["body"])
        else:
            body = event.get("body", {})
        
        result = process_message(body)
        
        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(result)
        }
        
    except Exception as e:
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"ok": False, "error": str(e)})
        }
