#!/usr/bin/env python3
"""
Telegram Bot Creator for Yandex Cloud
Запускайте через ./create-bot.sh
"""

import os
import sys
import subprocess
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent

# Импорты (зависимости ставятся через create-bot.sh)
import json
import argparse
import shutil
from jinja2 import Template

import questionary
from questionary import Style
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()

# Стиль для questionary
custom_style = Style([
    ('qmark', 'fg:cyan bold'),
    ('question', 'fg:white bold'),
    ('answer', 'fg:green bold'),
    ('pointer', 'fg:cyan bold'),
    ('highlighted', 'fg:cyan bold'),
    ('selected', 'fg:green'),
    ('separator', 'fg:cyan'),
    ('instruction', 'fg:gray'),
])


def check_yc_cli():
    """Проверяет Yandex Cloud CLI"""
    try:
        result = subprocess.run(['yc', 'version'], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            console.print("[green]✓ Yandex Cloud CLI найден[/]")
            
            # Проверяем авторизацию
            result = subprocess.run(['yc', 'config', 'get', 'folder-id'], 
                                   capture_output=True, text=True, timeout=5)
            if result.returncode == 0 and result.stdout.strip():
                console.print(f"[green]✓ YC авторизован (folder: {result.stdout.strip()})[/]")
            else:
                console.print("[yellow]⚠ YC folder-id не настроен. Выполните: yc init[/]")
        return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        console.print("[yellow]⚠ Yandex Cloud CLI не найден[/]")
        console.print("[yellow]  Установите: curl -sSL https://storage.yandexcloud.net/yandexcloud-yc/install.sh | bash[/]")
        return False


def load_debug_config():
    """Загружает конфигурацию из config.local"""
    config_path = SCRIPT_DIR / "config.local"
    if not config_path.exists():
        return {}
    
    config = {}
    with open(config_path) as f:
        for line in f:
            line = line.strip()
            if line.startswith('export ') and '=' in line:
                line = line[7:]  # убираем 'export '
                key, _, value = line.partition('=')
                value = value.strip('"').strip("'")
                if value:
                    config[key] = value
    return config


class BotCreator:
    def __init__(self, base_dir: Path, debug_mode: bool = False):
        self.config = {}
        self.base_dir = base_dir
        self.debug_mode = debug_mode
        self.debug_config = load_debug_config() if debug_mode else {}
        
    def welcome(self):
        """Приветственное сообщение"""
        console.print()
        console.print(Panel.fit(
            "[bold cyan]Мастер создания Telegram бота[/]\n\n"
            "Этот инструмент поможет вам создать бота на базе:\n"
            "• [green]Yandex Cloud Functions[/] (Serverless)\n"
            "• [green]Yandex Cloud Responses API[/] (AI)\n"
            "• [green]Yandex Object Storage[/] (S3 для состояния)",
            title="🤖 Bot Creator",
            border_style="cyan"
        ))
        console.print()

    def get_action(self) -> str:
        """Выбор действия"""
        return questionary.select(
            "Что вы хотите сделать?",
            choices=[
                questionary.Choice("🆕 Создать нового бота", value="create"),
                questionary.Choice("🚀 Задеплоить существующего бота", value="deploy"),
                questionary.Choice("❌ Выход", value="exit"),
            ],
            style=custom_style
        ).ask()

    def collect_bot_info(self):
        """Сбор информации о боте"""
        console.print("\n[bold cyan]📝 Информация о боте[/]\n")
        
        self.config["project_name"] = questionary.text(
            "Название проекта (латиница, без пробелов):",
            default="my-telegram-bot",
            validate=lambda x: len(x) > 0 and " " not in x,
            style=custom_style
        ).ask()
        
        default_path = str(self.base_dir / self.config["project_name"])
        self.config["project_path"] = questionary.path(
            "Путь для создания проекта:",
            default=default_path,
            style=custom_style
        ).ask()
        
        # Telegram токен
        if self.debug_mode and self.debug_config.get("TELEGRAM_BOT_TOKEN"):
            token = self.debug_config["TELEGRAM_BOT_TOKEN"]
            console.print(f"[green]✓ Telegram Token из config.local: {token[:15]}...[/]")
            self.config["telegram_token"] = token
        else:
            console.print("[dim]  Получите токен у @BotFather в Telegram:[/]")
            console.print("[dim]  1. Откройте @BotFather → /newbot → введите имя[/]")
            console.print("[dim]  2. Скопируйте токен (формат: 123456789:ABC...)[/]")
            console.print("[dim]  📖 https://core.telegram.org/bots#botfather[/]\n")
            
            self.config["telegram_token"] = questionary.text(
                "Telegram Bot Token:",
                validate=lambda x: ":" in x and len(x) > 20,
                style=custom_style
            ).ask()

    def collect_yc_info(self):
        """Сбор информации о Yandex Cloud"""
        console.print("\n[bold cyan]☁️  Yandex Cloud настройки[/]\n")
        
        # Folder ID
        if self.debug_mode and self.debug_config.get("YANDEX_CLOUD_FOLDER"):
            folder_id = self.debug_config["YANDEX_CLOUD_FOLDER"]
            console.print(f"[green]✓ Folder ID из config.local: {folder_id}[/]")
            self.config["folder_id"] = folder_id
        else:
            default_folder = ""
            try:
                result = subprocess.run(['yc', 'config', 'get', 'folder-id'],
                                       capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    default_folder = result.stdout.strip()
            except:
                pass
            
            if not default_folder:
                console.print("[dim]  Folder ID — идентификатор каталога в Yandex Cloud[/]")
                console.print("[dim]  Найти: Консоль → Выбрать каталог → Скопировать ID[/]")
                console.print("[dim]  📖 https://yandex.cloud/ru/docs/resource-manager/operations/folder/get-id[/]\n")
            
            self.config["folder_id"] = questionary.text(
                "Yandex Cloud Folder ID:",
                default=default_folder,
                validate=lambda x: len(x) > 10,
                style=custom_style
            ).ask()
        
        # API Key
        if self.debug_mode and self.debug_config.get("YANDEX_CLOUD_API_KEY"):
            api_key = self.debug_config["YANDEX_CLOUD_API_KEY"]
            console.print(f"[green]✓ API Key из config.local: {api_key[:10]}...[/]")
            self.config["api_key"] = api_key
        else:
            console.print("[dim]  API-ключ нужен для доступа к AI API от имени сервисного аккаунта[/]")
            console.print("[dim]  Создать: Консоль → IAM → Сервисные аккаунты → Ваш SA → Создать API-ключ[/]")
            console.print("[dim]  📖 https://yandex.cloud/ru/docs/iam/operations/api-key/create[/]\n")
            
            self.config["api_key"] = questionary.text(
                "Yandex Cloud API Key:",
                validate=lambda x: len(x) > 10,
                style=custom_style
            ).ask()

    def collect_agent_info(self):
        """Сбор информации об агентах"""
        console.print("\n[bold cyan]🤖 Настройка AI агентов[/]\n")
        
        # Из debug config
        if self.debug_mode and self.debug_config.get("AGENTS_JSON"):
            try:
                agents = json.loads(self.debug_config["AGENTS_JSON"])
                if agents:
                    console.print("[green]✓ Агенты из config.local:[/]")
                    for agent_id, agent_name in agents.items():
                        console.print(f"   {agent_name} ({agent_id[:8]}...)")
                    
                    if questionary.confirm("Использовать этих агентов?", default=True, style=custom_style).ask():
                        self.config["agents"] = agents
                        self.config["use_model"] = False
                        return
            except json.JSONDecodeError:
                pass
        
        console.print("[dim]  AI Агент — это предварительно настроенный промпт в Yandex Cloud.[/]")
        console.print("[dim]  Можно использовать готового агента (нужен ID) или выбрать модель напрямую.[/]")
        console.print("[dim]  📖 https://yandex.cloud/ru/docs/foundation-models/concepts/assistant[/]\n")
        
        use_agents = questionary.confirm(
            "Использовать готовых AI агентов из консоли YC?",
            default=True,
            style=custom_style
        ).ask()
        
        self.config["agents"] = {}
        
        if use_agents:
            console.print("\n[dim]  ID агента найдёте: Консоль → Foundation Models → Промпты → Ваш агент[/]")
            console.print("[dim]  Формат ID: fvt... (начинается с fvt)[/]\n")
            
            while True:
                agent_id = questionary.text(
                    "ID агента (или Enter для завершения):",
                    default="",
                    style=custom_style
                ).ask()
                
                if not agent_id:
                    break
                
                agent_name = questionary.text(
                    f"Название агента {agent_id[:8]}...:",
                    default="🤖 Ассистент",
                    style=custom_style
                ).ask()
                
                self.config["agents"][agent_id] = agent_name
                console.print(f"[green]✓ Агент добавлен: {agent_name}[/]")
        
        if not self.config["agents"]:
            self.config["use_model"] = True
            self.config["model"] = questionary.select(
                "Выберите модель:",
                choices=[
                    questionary.Choice("YandexGPT Pro 5", value="yandexgpt/latest"),
                    questionary.Choice("YandexGPT Pro 5.1 (RC)", value="yandexgpt/rc"),
                    questionary.Choice("YandexGPT Lite", value="yandexgpt-lite"),
                ],
                style=custom_style
            ).ask()
            
            self.config["system_prompt"] = questionary.text(
                "Системный промпт для модели:",
                default="Ты дружелюбный AI-ассистент. Отвечай кратко и по делу.",
                style=custom_style
            ).ask()
        else:
            self.config["use_model"] = False

    def collect_features(self):
        """Выбор функций бота"""
        console.print("\n[bold cyan]⚙️  Функции бота[/]\n")
        
        console.print("[dim]  Выберите пробелом, подтвердите Enter[/]\n")
        
        features = questionary.checkbox(
            "Выберите функции:",
            choices=[
                questionary.Choice("💾 Память диалогов (S3)", value="memory", checked=True),
                questionary.Choice("🔄 Выбор агентов", value="agent_selection", checked=True),
                questionary.Choice("📊 Статус диалога", value="status", checked=True),
                questionary.Choice("🎨 Кастомное меню", value="custom_menu", checked=True),
            ],
            style=custom_style
        ).ask()
        
        self.config["features"] = features or []
        
        if "memory" in self.config["features"]:
            if self.debug_mode and self.debug_config.get("S3_BUCKET"):
                console.print(f"[green]✓ S3 Bucket из config.local: {self.debug_config['S3_BUCKET']}[/]")
                self.config["create_s3_bucket"] = False
                self.config["s3_bucket"] = self.debug_config["S3_BUCKET"]
                self.config["aws_access_key_id"] = self.debug_config.get("AWS_ACCESS_KEY_ID", "")
                self.config["aws_secret_access_key"] = self.debug_config.get("AWS_SECRET_ACCESS_KEY", "")
            else:
                console.print("\n[dim]  S3 (Object Storage) нужен для хранения истории диалогов.[/]")
                console.print("[dim]  Скрипт создаст бакет и настроит доступ автоматически.[/]")
                console.print("[dim]  📖 https://yandex.cloud/ru/docs/storage/quickstart[/]\n")
                
                self.config["create_s3_bucket"] = questionary.confirm(
                    "Создать S3 бакет автоматически?",
                    default=True,
                    style=custom_style
                ).ask()

    def show_summary(self):
        """Показать сводку конфигурации"""
        console.print("\n")
        
        table = Table(title="📋 Конфигурация бота", border_style="cyan")
        table.add_column("Параметр", style="cyan")
        table.add_column("Значение", style="green")
        
        table.add_row("Проект", self.config.get("project_name", "-"))
        table.add_row("Путь", self.config.get("project_path", "-"))
        table.add_row("Telegram Token", self.config.get("telegram_token", "-")[:20] + "...")
        table.add_row("Folder ID", self.config.get("folder_id", "-"))
        table.add_row("API Key", self.config.get("api_key", "-")[:15] + "...")
        
        if self.config.get("agents"):
            table.add_row("Агенты", ", ".join(self.config["agents"].values()))
        elif self.config.get("model"):
            table.add_row("Модель", self.config.get("model", "-"))
        
        table.add_row("Функции", ", ".join(self.config.get("features", [])) or "-")
        
        console.print(table)
        console.print()
        
        return questionary.confirm("Создать бота с этими настройками?", default=True, style=custom_style).ask()

    def create_project(self):
        """Создание проекта"""
        project_path = Path(self.config["project_path"])
        
        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as progress:
            
            task = progress.add_task("Создаю структуру проекта...", total=None)
            project_path.mkdir(parents=True, exist_ok=True)
            (project_path / "src").mkdir(exist_ok=True)
            progress.update(task, completed=True)
            
            task = progress.add_task("Генерирую код бота...", total=None)
            self._generate_main_py(project_path / "src" / "main.py")
            progress.update(task, completed=True)
            
            task = progress.add_task("Создаю requirements.txt...", total=None)
            self._generate_requirements(project_path / "src" / "requirements.txt")
            progress.update(task, completed=True)
            
            task = progress.add_task("Создаю .env...", total=None)
            self._generate_env(project_path / ".env")
            self._generate_env_example(project_path / ".env.example")
            progress.update(task, completed=True)
            
            task = progress.add_task("Создаю скрипт деплоя...", total=None)
            self._generate_deploy_script(project_path / "deploy.sh")
            progress.update(task, completed=True)
            
            task = progress.add_task("Создаю README.md...", total=None)
            self._generate_readme(project_path / "README.md")
            self._generate_gitignore(project_path / ".gitignore")
            progress.update(task, completed=True)
        
        console.print(f"\n[bold green]✅ Проект создан: {project_path}[/]\n")
        
        if self.config.get("create_s3_bucket") and "memory" in self.config.get("features", []):
            self._create_s3_resources(project_path)

    def _generate_main_py(self, path: Path):
        """Генерация main.py"""
        template = '''"""
Telegram Bot на Yandex Cloud Serverless Functions
"""

import json
import os
import openai
import requests
{% if "memory" in features %}
import boto3
from botocore.config import Config
{% endif %}

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
YANDEX_CLOUD_API_KEY = os.environ.get("YANDEX_CLOUD_API_KEY")
YANDEX_CLOUD_FOLDER = os.environ.get("YANDEX_CLOUD_FOLDER")
{% if "memory" in features %}
S3_BUCKET = os.environ.get("S3_BUCKET")
AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY")
{% endif %}

{% if use_model %}
MODEL = "{{ model }}"
SYSTEM_PROMPT = """{{ system_prompt }}"""
{% endif %}

{% if agents %}
AGENTS = {{ agents_json }}

def get_agents():
    env_agents = os.environ.get("AGENTS_JSON")
    return json.loads(env_agents) if env_agents else AGENTS
{% endif %}


def get_ai_client():
    return openai.OpenAI(
        api_key=YANDEX_CLOUD_API_KEY,
        base_url="https://rest-assistant.api.cloud.yandex.net/v1",
        project=YANDEX_CLOUD_FOLDER
    )

{% if "memory" in features %}
def get_s3_client():
    return boto3.client("s3", endpoint_url="https://storage.yandexcloud.net",
        aws_access_key_id=AWS_ACCESS_KEY_ID, aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        config=Config(signature_version="s3v4"), region_name="ru-central1")


def get_state(chat_id):
    try:
        s3 = get_s3_client()
        obj = s3.get_object(Bucket=S3_BUCKET, Key=f"dialogs/{chat_id}.json")
        return json.loads(obj["Body"].read().decode())
    except:
{% if agents %}
        agents = get_agents()
        return {"prev_id": None, "count": 0, "agent_id": list(agents.keys())[0] if agents else None}
{% else %}
        return {"prev_id": None, "count": 0}
{% endif %}


def save_state(chat_id, state):
    try:
        get_s3_client().put_object(Bucket=S3_BUCKET, Key=f"dialogs/{chat_id}.json",
            Body=json.dumps(state), ContentType="application/json")
    except Exception as e:
        print(f"Error: {e}")
{% endif %}


def get_ai_response(message, chat_id):
    try:
        client = get_ai_client()
{% if "memory" in features %}
        state = get_state(chat_id)
{% if agents %}
        agent_id = state.get("agent_id")
        if not agent_id:
            return "❌ Агент не выбран. /agents"
{% endif %}
{% endif %}

{% if agents %}
        response = client.responses.create(
            prompt={"id": agent_id},
            input=message,
{% if "memory" in features %}
            previous_response_id=state.get("prev_id")
{% endif %}
        )
{% else %}
        response = client.responses.create(
            model=f"gpt://{YANDEX_CLOUD_FOLDER}/{MODEL}",
            instructions=SYSTEM_PROMPT,
            input=message,
{% if "memory" in features %}
            previous_response_id=state.get("prev_id")
{% endif %}
        )
{% endif %}

{% if "memory" in features %}
        save_state(chat_id, {
            "prev_id": response.id,
            "count": state.get("count", 0) + 1,
{% if agents %}
            "agent_id": agent_id
{% endif %}
        })
{% endif %}
        return response.output_text
    except Exception as e:
        return f"❌ Ошибка: {e}"


def send_message(chat_id, text, markup=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
    if markup:
        payload["reply_markup"] = json.dumps(markup)
    return requests.post(url, json=payload).json()


def send_typing(chat_id):
    requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendChatAction",
        json={"chat_id": chat_id, "action": "typing"})

{% if "agent_selection" in features and agents %}
def answer_callback(cb_id, text=None):
    payload = {"callback_query_id": cb_id}
    if text:
        payload["text"] = text
    return requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/answerCallbackQuery", json=payload).json()


def edit_message(chat_id, msg_id, text, markup=None):
    payload = {"chat_id": chat_id, "message_id": msg_id, "text": text, "parse_mode": "Markdown"}
    if markup:
        payload["reply_markup"] = json.dumps(markup)
    return requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/editMessageText", json=payload).json()


def agents_keyboard(current=None):
    agents = get_agents()
    return {"inline_keyboard": [[{"text": f"✅ {n}" if k == current else n, "callback_data": f"agent:{k}"}] for k, n in agents.items()]}
{% endif %}

{% if "custom_menu" in features %}
def main_menu():
    return {"keyboard": [[{"text": "🆕 Новый диалог"}{% if "agent_selection" in features and agents %}, {"text": "🤖 Агенты"}{% endif %}],
        [{"text": "📊 Статус"}, {"text": "❓ Помощь"}]], "resize_keyboard": True}
{% endif %}


def handle_command(chat_id, cmd):
{% if "custom_menu" in features %}
    menu = main_menu()
{% else %}
    menu = None
{% endif %}

    if cmd == "/start":
{% if "memory" in features %}
{% if agents %}
        state = get_state(chat_id)
        agent_id = state.get("agent_id") or list(get_agents().keys())[0]
        save_state(chat_id, {"prev_id": None, "count": 0, "agent_id": agent_id})
        name = get_agents().get(agent_id, "?")
        send_message(chat_id, f"👋 *Привет!*\\n\\n🤖 Агент: {name}\\n\\nНапиши мне!", menu)
{% else %}
        save_state(chat_id, {"prev_id": None, "count": 0})
        send_message(chat_id, "👋 *Привет!* Напиши мне!", menu)
{% endif %}
{% else %}
        send_message(chat_id, "👋 *Привет!* Напиши мне!", menu)
{% endif %}
        return True

    if cmd in ["🆕 Новый диалог", "/new"]:
{% if "memory" in features %}
{% if agents %}
        state = get_state(chat_id)
        save_state(chat_id, {"prev_id": None, "count": 0, "agent_id": state.get("agent_id")})
{% else %}
        save_state(chat_id, {"prev_id": None, "count": 0})
{% endif %}
{% endif %}
        send_message(chat_id, "🆕 *Диалог сброшен!*", menu)
        return True

{% if "agent_selection" in features and agents %}
    if cmd in ["🤖 Агенты", "/agents"]:
        state = get_state(chat_id)
        send_message(chat_id, "🤖 *Выберите агента:*", agents_keyboard(state.get("agent_id")))
        return True
{% endif %}

{% if "status" in features %}
    if cmd in ["📊 Статус", "/status"]:
{% if "memory" in features %}
        state = get_state(chat_id)
        ctx = "✅" if state.get("prev_id") else "❌"
{% if agents %}
        name = get_agents().get(state.get("agent_id"), "?")
        send_message(chat_id, f"📊 *Статус*\\n🤖 {name}\\n💬 {state.get('count', 0)}\\n🧠 {ctx}", menu)
{% else %}
        send_message(chat_id, f"📊 *Статус*\\n💬 {state.get('count', 0)}\\n🧠 {ctx}", menu)
{% endif %}
{% else %}
        send_message(chat_id, "📊 *Статус*\\n✅ Бот работает", menu)
{% endif %}
        return True
{% endif %}

    if cmd in ["❓ Помощь", "/help"]:
        send_message(chat_id, "❓ *Справка*\\n/new — новый диалог\\n/status — статус\\n/help — помощь", menu)
        return True

    return False

{% if "agent_selection" in features and agents %}
def handle_callback(cb):
    cb_id = cb.get("id")
    data = cb.get("data", "")
    msg = cb.get("message", {})
    chat_id = msg.get("chat", {}).get("id")
    msg_id = msg.get("message_id")

    if data.startswith("agent:"):
        agent_id = data.split(":", 1)[1]
        agents = get_agents()
        if agent_id not in agents:
            answer_callback(cb_id, "❌ Не найден")
            return

        state = get_state(chat_id)
        if state.get("agent_id") != agent_id:
            save_state(chat_id, {"prev_id": None, "count": 0, "agent_id": agent_id})
            answer_callback(cb_id, "✅ Изменён!")
        else:
            answer_callback(cb_id, "ℹ️ Уже выбран")

        edit_message(chat_id, msg_id, f"🤖 *Агент:* {agents[agent_id]}", agents_keyboard(agent_id))
        return

    answer_callback(cb_id)
{% endif %}


def process(update):
{% if "agent_selection" in features and agents %}
    if "callback_query" in update:
        handle_callback(update["callback_query"])
        return {"ok": True}
{% endif %}

    msg = update.get("message", {})
    chat_id = msg.get("chat", {}).get("id")
    text = msg.get("text", "")

    if not chat_id or not text:
        return {"ok": True}

    if handle_command(chat_id, text):
        return {"ok": True}

    send_typing(chat_id)
    response = get_ai_response(text, chat_id)
{% if "custom_menu" in features %}
    send_message(chat_id, response, main_menu())
{% else %}
    send_message(chat_id, response)
{% endif %}
    return {"ok": True}


def handler(event, context):
    try:
        body = json.loads(event["body"]) if isinstance(event.get("body"), str) else event.get("body", {})
        return {"statusCode": 200, "body": json.dumps(process(body))}
    except Exception as e:
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}
'''
        
        rendered = Template(template).render(
            **self.config,
            agents_json=json.dumps(self.config.get("agents", {}), ensure_ascii=False)
        )
        
        with open(path, "w") as f:
            f.write(rendered)

    def _generate_requirements(self, path: Path):
        requirements = ["openai>=1.0.0", "requests>=2.28.0"]
        if "memory" in self.config.get("features", []):
            requirements.append("boto3>=1.28.0")
        with open(path, "w") as f:
            f.write("\n".join(requirements) + "\n")

    def _generate_env_example(self, path: Path):
        content = "TELEGRAM_BOT_TOKEN=\nYANDEX_CLOUD_API_KEY=\nYANDEX_CLOUD_FOLDER=\n"
        if "memory" in self.config.get("features", []):
            content += "S3_BUCKET=\nAWS_ACCESS_KEY_ID=\nAWS_SECRET_ACCESS_KEY=\n"
        with open(path, "w") as f:
            f.write(content)

    def _generate_env(self, path: Path):
        content = f"""TELEGRAM_BOT_TOKEN={self.config.get('telegram_token', '')}
YANDEX_CLOUD_API_KEY={self.config.get('api_key', '')}
YANDEX_CLOUD_FOLDER={self.config.get('folder_id', '')}
"""
        if "memory" in self.config.get("features", []):
            content += f"""S3_BUCKET={self.config.get('s3_bucket', self.config.get('project_name', 'bot') + '-state')}
AWS_ACCESS_KEY_ID={self.config.get('aws_access_key_id', '')}
AWS_SECRET_ACCESS_KEY={self.config.get('aws_secret_access_key', '')}
"""
        with open(path, "w") as f:
            f.write(content)

    def _generate_deploy_script(self, path: Path):
        name = self.config.get('project_name', 'bot')
        content = f'''#!/bin/bash
set -e
NAME="{name}"

[ -f .env ] && set -a && source .env && set +a
[ -z "$TELEGRAM_BOT_TOKEN" ] && echo "❌ TELEGRAM_BOT_TOKEN не установлен" && exit 1

echo "📦 Создаю архив..."
cd src && rm -f ../function.zip && zip -r ../function.zip . && cd ..

yc serverless function get "$NAME-handler" &>/dev/null || yc serverless function create --name "$NAME-handler"

ENV="TELEGRAM_BOT_TOKEN=$TELEGRAM_BOT_TOKEN,YANDEX_CLOUD_API_KEY=$YANDEX_CLOUD_API_KEY,YANDEX_CLOUD_FOLDER=$YANDEX_CLOUD_FOLDER"
'''
        if "memory" in self.config.get("features", []):
            content += '[ -n "$S3_BUCKET" ] && ENV="$ENV,S3_BUCKET=$S3_BUCKET,AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY_ID,AWS_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY"\n'
        
        content += '''
echo "⬆️ Деплою..."
yc serverless function version create --function-name "$NAME-handler" --runtime python312 \\
    --entrypoint main.handler --memory 128m --execution-timeout 30s \\
    --source-path function.zip --environment "$ENV"

yc serverless function allow-unauthenticated-invoke "$NAME-handler"
URL=$(yc serverless function get "$NAME-handler" --format json | grep -o '"http_invoke_url": "[^"]*"' | cut -d'"' -f4)

echo "🔗 Устанавливаю вебхук..."
curl -s -X POST "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/setWebhook?url=$URL" | grep -q '"ok":true' && echo "✅ Готово! $URL" || echo "❌ Ошибка вебхука"
'''
        with open(path, "w") as f:
            f.write(content)
        os.chmod(path, 0o755)

    def _generate_readme(self, path: Path):
        content = f"# {self.config.get('project_name', 'Bot')}\n\n```bash\n./deploy.sh\n```\n"
        with open(path, "w") as f:
            f.write(content)

    def _generate_gitignore(self, path: Path):
        with open(path, "w") as f:
            f.write(".env\n*.zip\n__pycache__/\n")

    def _create_s3_resources(self, project_path: Path):
        """Создание S3 бакета"""
        import time
        
        console.print("\n[bold cyan]☁️ Создание S3...[/]\n")
        
        name = self.config.get("project_name", "bot")
        folder_id = self.config.get("folder_id")
        bucket = f"{name}-state-{int(time.time())}"
        sa = f"{name}-s3-sa"
        
        try:
            # Бакет
            subprocess.run(["yc", "storage", "bucket", "create", "--name", bucket,
                          "--default-storage-class", "standard", "--max-size", "1073741824"],
                         capture_output=True, timeout=30, check=True)
            console.print(f"[green]✓ Бакет: {bucket}[/]")
            
            # SA
            subprocess.run(["yc", "iam", "service-account", "create", "--name", sa],
                         capture_output=True, timeout=30)
            
            result = subprocess.run(["yc", "iam", "service-account", "get", sa, "--format", "json"],
                                   capture_output=True, text=True, timeout=10)
            sa_id = json.loads(result.stdout).get("id")
            
            subprocess.run(["yc", "resource-manager", "folder", "add-access-binding", folder_id,
                          "--role", "storage.editor", "--subject", f"serviceAccount:{sa_id}"],
                         capture_output=True, timeout=30)
            
            result = subprocess.run(["yc", "iam", "access-key", "create", "--service-account-name", sa],
                                   capture_output=True, text=True, timeout=30)
            
            access_key = secret_key = ""
            for line in result.stdout.split('\n'):
                if "key_id:" in line:
                    access_key = line.split("key_id:")[1].strip()
                elif "secret:" in line:
                    secret_key = line.split("secret:")[1].strip()
            
            # Обновляем .env
            env_path = project_path / ".env"
            with open(env_path) as f:
                content = f.read()
            content = content.replace(f"S3_BUCKET={name}-state", f"S3_BUCKET={bucket}")
            content = content.replace("AWS_ACCESS_KEY_ID=", f"AWS_ACCESS_KEY_ID={access_key}")
            content = content.replace("AWS_SECRET_ACCESS_KEY=", f"AWS_SECRET_ACCESS_KEY={secret_key}")
            with open(env_path, "w") as f:
                f.write(content)
            
            console.print(f"[green]✓ S3 готов![/]")
            
        except Exception as e:
            console.print(f"[red]❌ Ошибка: {e}[/]")

    def deploy_bot(self):
        """Деплой бота"""
        console.print("\n[bold cyan]🚀 Деплой бота[/]\n")
        
        project_path = questionary.path("Путь к проекту:", default=str(Path.cwd()), style=custom_style).ask()
        deploy_script = Path(project_path) / "deploy.sh"
        
        if not deploy_script.exists():
            console.print("[red]❌ deploy.sh не найден[/]")
            return
        
        subprocess.run(["bash", str(deploy_script)], cwd=project_path)

    def run(self):
        """Основной цикл"""
        self.welcome()
        
        while True:
            action = self.get_action()
            
            if action == "exit" or action is None:
                console.print("\n[cyan]👋 До свидания![/]\n")
                break
            
            elif action == "create":
                self.collect_bot_info()
                self.collect_yc_info()
                self.collect_agent_info()
                self.collect_features()
                
                if self.show_summary():
                    self.create_project()
                    
                    if questionary.confirm("Задеплоить сейчас?", default=False, style=custom_style).ask():
                        subprocess.run(["bash", "deploy.sh"], cwd=self.config["project_path"])
            
            elif action == "deploy":
                self.deploy_bot()
            
            console.print()


def main():
    parser = argparse.ArgumentParser(description="Telegram Bot Creator for Yandex Cloud")
    parser.add_argument("--base-dir", type=str, default=None, help="Директория для ботов")
    parser.add_argument("--debug", "-d", action="store_true", help="Использовать config.local")
    args = parser.parse_args()
    
    console.print()
    console.print("[bold cyan]🤖 Telegram Bot Creator for Yandex Cloud[/]")
    console.print()
    
    # Проверяем YC CLI
    check_yc_cli()
    
    # Debug mode
    if args.debug:
        config = load_debug_config()
        if config:
            console.print("\n[yellow]🔧 DEBUG MODE[/]")
            for k, v in config.items():
                if v:
                    console.print(f"   {k}: [cyan]{v[:15]}...[/]" if len(v) > 15 else f"   {k}: [cyan]{v}[/]")
        else:
            console.print("[yellow]⚠ config.local не найден[/]")
    
    base_dir = Path(args.base_dir) if args.base_dir else SCRIPT_DIR / "bots"
    
    try:
        creator = BotCreator(base_dir=base_dir, debug_mode=args.debug)
        creator.run()
    except KeyboardInterrupt:
        console.print("\n\n[cyan]👋 Прервано[/]\n")
        sys.exit(0)


if __name__ == "__main__":
    main()
