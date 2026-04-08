# Telegram Bot Builder for Yandex AI Studio

An interactive CLI tool for creating and deploying AI-powered Telegram bots on Yandex Cloud serverless infrastructure.

## Features

- **Interactive Setup Wizard** — step-by-step bot creation with guided prompts
- **Yandex AI Studio Integration** — use AI Agents from AI Studio or YandexGPT models directly
- **Conversation Memory** — persistent dialog context via Yandex Object Storage (S3)
- **Serverless Deployment** — runs on Yandex Cloud Functions with automatic scaling
- **Zero Infrastructure Management** — automated resource creation (S3 buckets, service accounts, IAM roles)
- **Debug Mode** — use pre-configured credentials for development and testing

## Architecture

```
Telegram → API Gateway → Cloud Function → YandexGPT Responses API
                              ↓
                         Object Storage (conversation memory)
```

## Быстрый старт

```bash
# Клонируем репозиторий
git clone https://github.com/goluntsov/bot-creator
cd bot-creator

# Запускаем мастер настройки
./run.sh
```

Мастер настройки проведет вас через все шаги:
1. Выберите пункт **1) 🚀 Начальная настройка (YC CLI + сервисный аккаунт)**
   - Скрипт сам установит Yandex Cloud CLI (если его нет)
   - Попросит перейти по ссылке и скопировать OAuth-токен
   - Предложит выбрать облако и каталог (обычно нужно просто нажимать Enter)
   - Автоматически создаст сервисный аккаунт и выдаст ему нужные права
2. Выберите пункт **2) 🆕 Создать нового бота**
   - Введите токен от Telegram (получите у @BotFather)
   - Введите API-ключ Yandex Cloud (ссылка на создание будет в терминале)
   - Выберите нужные функции (память диалогов, меню и т.д.)
3. Бот будет автоматически развернут в Yandex Cloud Functions!

## Интерактивное меню

```
1) 🚀 Начальная настройка (YC CLI + сервисный аккаунт)
2) 🆕 Создать нового бота
3) 📋 Справка по получению ключей
4) ⚙️  Перенастроить YC аккаунт
5) 🔧 Режим разработчика (debug)
6) ❌ Выход
```

## Требования

### Аккаунт Yandex Cloud

1. Создайте аккаунт на [console.yandex.cloud](https://console.yandex.cloud)
2. Настройте платежный аккаунт (доступен бесплатный грант для новых пользователей)

### Токен Telegram Бота

1. Откройте [@BotFather](https://t.me/BotFather) в Telegram
2. Отправьте `/newbot` и следуйте инструкциям
3. Скопируйте токен (формат: `123456789:ABC...`)

### Python 3.8+ и утилита zip

```bash
python3 --version
zip --version
```

На системах Debian/Ubuntu может потребоваться установить пакеты `venv` и `zip`:
```bash
sudo apt update
sudo apt install python3-venv zip
```

## Структура проекта

```
bot-creator/
├── run.sh               # 👈 Точка входа — запускайте этот файл
├── create-bot.py        # Интерактивный скрипт на Python
├── config.local.example # Шаблон для локальных ключей (debug)
├── bots/                # Сгенерированные проекты ботов
├── src/                 # Шаблон кода бота
│   └── main.py
├── terraform/           # IaC для развертывания (альтернативный метод)
│   └── main.tf
└── .cursor/
    └── mcp.json         # MCP интеграция для документации YC
```

## Что создается

При создании бота скрипт генерирует готовый проект:

```
bots/my-telegram-bot/
├── src/
│   └── main.py          # Код бота (настроенный под ваш выбор)
│   └── requirements.txt # Python зависимости
├── deploy.sh            # Скрипт для деплоя в один клик
├── .env                 # Переменные окружения (ваши секреты)
├── .env.example         # Шаблон для передачи проекта
├── .gitignore
└── README.md
```

## Функции бота

Выбираются во время создания:

| Функция | Описание |
|---------|-------------|
| 💾 **Память диалогов** | Сохранение контекста беседы с помощью S3 Object Storage |
| 🔄 **Выбор агента** | Возможность переключаться между разными AI агентами |
| 📊 **Статус** | Отображение статистики диалога и текущего агента |
| 🎨 **Кастомное меню** | Интерактивная клавиатура с быстрыми действиями |

## Настройка AI

### Вариант 1: AI Агенты (Рекомендуется)

Создайте агентов в [Yandex AI Studio](https://console.yandex.cloud/folders/<folder>/ai-studio/prompts):
- Настройте системный промпт, температуру и инструменты
- Получите ID агента (формат: `fvt...`)
- Бот будет использовать Responses API для сохранения контекста
- Подробнее: [Текстовые агенты в AI Studio](https://aistudio.yandex.ru/docs/ru/ai-studio/concepts/agents/text-agents.html)

### Вариант 2: Прямой доступ к моделям

Используйте модели YandexGPT напрямую:
- YandexGPT Pro 5
- YandexGPT Pro 5.1 (RC)
- YandexGPT Lite

## Ручное развертывание

Если вы предпочитаете ручную настройку вместо мастера:

### 1. Установка Yandex Cloud CLI

```bash
curl -sSL https://storage.yandexcloud.net/yandexcloud-yc/install.sh | bash
yc init
```

### 2. Создание сервисного аккаунта

```bash
# Получить ID каталога
yc config get folder-id

# Создать сервисный аккаунт
yc iam service-account create --name telegram-bot-sa

# Назначить роли
SA_ID=$(yc iam service-account get telegram-bot-sa --format json | jq -r '.id')
FOLDER_ID=$(yc config get folder-id)

yc resource-manager folder add-access-binding $FOLDER_ID \
    --role ai.languageModels.user --subject serviceAccount:$SA_ID
yc resource-manager folder add-access-binding $FOLDER_ID \
    --role ai.assistants.editor --subject serviceAccount:$SA_ID
yc resource-manager folder add-access-binding $FOLDER_ID \
    --role storage.editor --subject serviceAccount:$SA_ID
yc resource-manager folder add-access-binding $FOLDER_ID \
    --role serverless.functions.invoker --subject serviceAccount:$SA_ID

# Создать API-ключ
yc iam api-key create --service-account-name telegram-bot-sa
```

### 3. Настройка Terraform

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars
# Отредактируйте terraform.tfvars, добавив свои значения
```

### 4. Развертывание

```bash
terraform init
terraform apply
```

### 5. Установка Webhook

```bash
curl -X POST "https://api.telegram.org/bot<TOKEN>/setWebhook?url=<FUNCTION_URL>"
```

## Переменные окружения

| Переменная | Описание |
|----------|-------------|
| `TELEGRAM_BOT_TOKEN` | Токен бота от @BotFather |
| `YANDEX_CLOUD_API_KEY` | API-ключ для AI сервисов |
| `YANDEX_CLOUD_FOLDER` | ID каталога Yandex Cloud |
| `S3_BUCKET` | Бакет Object Storage для состояния диалогов |
| `AWS_ACCESS_KEY_ID` | Статический ключ доступа S3 |
| `AWS_SECRET_ACCESS_KEY` | Секретный ключ S3 |
| `AGENTS_JSON` | JSON словарь агентов: `{"agent_id": "Имя Агента"}` |

## Режим разработчика (Debug)

Для разработки используйте заранее настроенные ключи:

```bash
# Создайте конфиг из шаблона
cp config.local.example config.local

# Впишите свои тестовые ключи
nano config.local

# Запустите в режиме отладки (пункт меню 5)
./run.sh
```

Файл `config.local` добавлен в gitignore и содержит ваши личные API-ключи для тестирования.

## Полезные команды

```bash
# Просмотр логов функции
yc serverless function logs <function-name> --follow

# Проверка статуса вебхука
curl "https://api.telegram.org/bot<TOKEN>/getWebhookInfo"

# Удаление вебхука
curl "https://api.telegram.org/bot<TOKEN>/deleteWebhook"

# Список функций
yc serverless function list
```

## Решение проблем

### Бот не отвечает

1. Проверьте вебхук: `curl "https://api.telegram.org/bot<TOKEN>/getWebhookInfo"`
2. Посмотрите логи: `yc serverless function logs <function-name>`
3. Проверьте переменные окружения в настройках функции

### Ошибки AI

1. Убедитесь, что `YANDEX_CLOUD_API_KEY` валиден
2. Проверьте, существует ли AI агент в консоли
3. Проверьте квоты в Yandex Cloud

### Ошибки S3

1. Проверьте существование бакета: `yc storage bucket list`
2. Проверьте `AWS_ACCESS_KEY_ID` и `AWS_SECRET_ACCESS_KEY`
3. Убедитесь, что у сервисного аккаунта есть роль `storage.editor`

## Безопасность

- Никогда не коммитьте файлы `.env` или `config.local`
- Периодически меняйте (ротируйте) API-ключи
- Используйте разные сервисные аккаунты для продакшена и разработки
- Файл `.gitignore` уже настроен на исключение конфиденциальных файлов

## Участие в разработке

1. Сделайте форк репозитория
2. Создайте ветку для фичи
3. Внесите изменения
4. Отправьте pull request

## Лицензия

MIT.
