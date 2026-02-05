#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════════
# Telegram Bot Creator for Yandex Cloud
# ═══════════════════════════════════════════════════════════════════════════════
#
# Использование:
#   ./run.sh           # Обычный режим
#   ./run.sh --debug   # Использовать config.local (для разработчиков)
#   ./run.sh --setup   # Повторная настройка YC аккаунта
#
# ═══════════════════════════════════════════════════════════════════════════════

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"
CONFIG_FILE="$SCRIPT_DIR/.yc-config"
CONFIG_LOCAL="$SCRIPT_DIR/config.local"

# ─────────────────────────────────────────────────────────────────────────────
# Цвета и форматирование
# ─────────────────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BLUE='\033[0;34m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m'

print_header() {
    echo ""
    echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${CYAN}  🤖 Telegram Bot Creator for Yandex Cloud${NC}"
    echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
    echo ""
}

print_step() {
    echo -e "${BLUE}▶${NC} ${BOLD}$1${NC}"
}

print_ok() {
    echo -e "${GREEN}✓${NC} $1"
}

print_warn() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_info() {
    echo -e "${DIM}  $1${NC}"
}

print_link() {
    echo -e "${DIM}  📖 $1${NC}"
}

# ─────────────────────────────────────────────────────────────────────────────
# Проверка Python и создание venv
# ─────────────────────────────────────────────────────────────────────────────
setup_python() {
    print_step "Проверка Python..."
    
    if ! command -v python3 &>/dev/null; then
        print_error "Python3 не найден"
        echo ""
        echo "  Установите Python:"
        echo "    macOS:  brew install python3"
        echo "    Ubuntu: sudo apt install python3 python3-venv"
        exit 1
    fi
    print_ok "Python3 найден"
    
    # Создание/проверка venv
    if [ -d "$VENV_DIR" ] && [ -f "$VENV_DIR/bin/activate" ]; then
        print_ok "Virtual environment найден"
    else
        print_info "Создаю virtual environment..."
        python3 -m venv "$VENV_DIR"
        print_ok "Virtual environment создан"
    fi
    
    source "$VENV_DIR/bin/activate"
    
    # Установка зависимостей
    if ! python3 -c "import rich, questionary, jinja2" 2>/dev/null; then
        print_info "Устанавливаю зависимости..."
        pip install --quiet --upgrade pip
        pip install --quiet rich questionary jinja2
        print_ok "Зависимости установлены"
    else
        print_ok "Зависимости в порядке"
    fi
}

# ─────────────────────────────────────────────────────────────────────────────
# Настройка Yandex Cloud CLI (один раз)
# ─────────────────────────────────────────────────────────────────────────────
setup_yc_cli() {
    print_step "Проверка Yandex Cloud CLI..."
    
    if ! command -v yc &>/dev/null; then
        print_warn "Yandex Cloud CLI не установлен"
        echo ""
        echo -e "  ${BOLD}Yandex Cloud CLI${NC} — инструмент для управления облачными ресурсами"
        echo ""
        print_link "https://yandex.cloud/ru/docs/cli/quickstart"
        echo ""
        echo "  Установка:"
        echo -e "    ${CYAN}curl -sSL https://storage.yandexcloud.net/yandexcloud-yc/install.sh | bash${NC}"
        echo ""
        read -p "  Нажмите Enter после установки (или Ctrl+C для выхода)..."
        
        # Перезагрузка PATH
        export PATH="$HOME/yandex-cloud/bin:$PATH"
        
        if ! command -v yc &>/dev/null; then
            print_error "YC CLI всё ещё не найден. Перезапустите терминал и попробуйте снова."
            exit 1
        fi
    fi
    print_ok "Yandex Cloud CLI найден"
    
    # Проверка авторизации
    if ! yc config get folder-id &>/dev/null 2>&1; then
        print_warn "YC CLI не настроен"
        echo ""
        echo -e "  ${BOLD}Первоначальная настройка Yandex Cloud${NC}"
        echo ""
        echo "  Вам понадобится:"
        echo "    1. Аккаунт Yandex (yandex.ru)"
        echo "    2. Платёжный аккаунт в Yandex Cloud (есть бесплатный грант)"
        echo ""
        print_link "https://yandex.cloud/ru/docs/cli/quickstart#initialize"
        echo ""
        echo "  Запускаю настройку..."
        echo ""
        yc init
        echo ""
    fi
    
    FOLDER_ID=$(yc config get folder-id 2>/dev/null || echo "")
    if [ -n "$FOLDER_ID" ]; then
        print_ok "YC авторизован (folder: $FOLDER_ID)"
    fi
}

# ─────────────────────────────────────────────────────────────────────────────
# Проверка/создание сервисного аккаунта
# ─────────────────────────────────────────────────────────────────────────────
check_service_account() {
    print_step "Проверка сервисного аккаунта..."
    
    # Загружаем сохранённую конфигурацию
    if [ -f "$CONFIG_FILE" ]; then
        source "$CONFIG_FILE"
    fi
    
    # Если есть сохранённый SA — проверяем его
    if [ -n "$YC_SERVICE_ACCOUNT" ]; then
        if yc iam service-account get "$YC_SERVICE_ACCOUNT" &>/dev/null 2>&1; then
            print_ok "Сервисный аккаунт: $YC_SERVICE_ACCOUNT"
            return 0
        fi
    fi
    
    # Нет сохранённого SA — предлагаем выбрать или создать
    echo ""
    echo -e "  ${BOLD}Сервисный аккаунт${NC} — это аккаунт для автоматизации,"
    echo "  от имени которого бот будет обращаться к API Yandex Cloud."
    echo ""
    print_link "https://yandex.cloud/ru/docs/iam/concepts/users/service-accounts"
    echo ""
    
    # Получаем список существующих SA
    SA_JSON=$(yc iam service-account list --format json 2>/dev/null || echo "[]")
    
    # Парсим в массивы
    SA_NAMES=()
    SA_IDS=()
    while IFS= read -r line; do
        SA_NAMES+=("$line")
    done < <(echo "$SA_JSON" | python3 -c "import sys,json; [print(sa['name']) for sa in json.load(sys.stdin)]" 2>/dev/null)
    
    while IFS= read -r line; do
        SA_IDS+=("$line")
    done < <(echo "$SA_JSON" | python3 -c "import sys,json; [print(sa['id']) for sa in json.load(sys.stdin)]" 2>/dev/null)
    
    SA_COUNT=${#SA_NAMES[@]}
    
    echo "  Выберите сервисный аккаунт:"
    echo ""
    echo -e "    ${CYAN}0)${NC} ➕ Создать новый (telegram-bot-sa)"
    
    for i in "${!SA_NAMES[@]}"; do
        num=$((i + 1))
        echo -e "    ${CYAN}${num})${NC} ${SA_NAMES[$i]}"
    done
    
    echo ""
    read -p "  Ваш выбор [0-$SA_COUNT]: " SA_CHOICE
    
    # Обработка выбора
    if [ -z "$SA_CHOICE" ] || [ "$SA_CHOICE" = "0" ]; then
        SA_NAME="telegram-bot-sa"
        
        # Проверяем не существует ли уже
        if yc iam service-account get "$SA_NAME" &>/dev/null 2>&1; then
            print_ok "Используем существующий: $SA_NAME"
        else
            print_info "Создаю сервисный аккаунт: $SA_NAME..."
            yc iam service-account create --name "$SA_NAME" --description "Telegram bot service account"
            print_ok "Сервисный аккаунт создан"
            
            # Назначаем роли
            assign_sa_roles "$SA_NAME"
        fi
    elif [ "$SA_CHOICE" -ge 1 ] && [ "$SA_CHOICE" -le "$SA_COUNT" ] 2>/dev/null; then
        idx=$((SA_CHOICE - 1))
        SA_NAME="${SA_NAMES[$idx]}"
        print_ok "Выбран: $SA_NAME"
    else
        print_warn "Неверный выбор, использую telegram-bot-sa"
        SA_NAME="telegram-bot-sa"
        
        if ! yc iam service-account get "$SA_NAME" &>/dev/null 2>&1; then
            print_info "Создаю сервисный аккаунт: $SA_NAME..."
            yc iam service-account create --name "$SA_NAME" --description "Telegram bot service account"
            assign_sa_roles "$SA_NAME"
        fi
    fi
    
    # Сохраняем
    echo "YC_SERVICE_ACCOUNT=\"$SA_NAME\"" > "$CONFIG_FILE"
    YC_SERVICE_ACCOUNT="$SA_NAME"
}

# Назначение ролей сервисному аккаунту
assign_sa_roles() {
    local sa_name=$1
    
    FOLDER_ID=$(yc config get folder-id)
    print_info "Назначаю роли..."
    
    SA_ID=$(yc iam service-account get "$sa_name" --format json | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
    
    # Роли для AI и S3
    yc resource-manager folder add-access-binding "$FOLDER_ID" \
        --role ai.languageModels.user \
        --subject "serviceAccount:$SA_ID" 2>/dev/null || true
    
    yc resource-manager folder add-access-binding "$FOLDER_ID" \
        --role ai.assistants.editor \
        --subject "serviceAccount:$SA_ID" 2>/dev/null || true
        
    yc resource-manager folder add-access-binding "$FOLDER_ID" \
        --role storage.editor \
        --subject "serviceAccount:$SA_ID" 2>/dev/null || true
    
    print_ok "Роли назначены: ai.languageModels.user, ai.assistants.editor, storage.editor"
}

# ─────────────────────────────────────────────────────────────────────────────
# Загрузка debug конфигурации
# ─────────────────────────────────────────────────────────────────────────────
load_debug_config() {
    if [ "$DEBUG_MODE" = true ] && [ -f "$CONFIG_LOCAL" ]; then
        echo ""
        print_step "DEBUG MODE — загружаю config.local"
        set -a
        source "$CONFIG_LOCAL"
        set +a
        
        [ -n "$TELEGRAM_BOT_TOKEN" ] && print_info "TELEGRAM_BOT_TOKEN: ${TELEGRAM_BOT_TOKEN:0:15}..."
        [ -n "$YANDEX_CLOUD_FOLDER" ] && print_info "YANDEX_CLOUD_FOLDER: $YANDEX_CLOUD_FOLDER"
        [ -n "$YANDEX_CLOUD_API_KEY" ] && print_info "YANDEX_CLOUD_API_KEY: ${YANDEX_CLOUD_API_KEY:0:10}..."
        [ -n "$S3_BUCKET" ] && print_info "S3_BUCKET: $S3_BUCKET"
        [ -n "$AGENTS_JSON" ] && print_info "AGENTS_JSON: $AGENTS_JSON"
    fi
}

# ─────────────────────────────────────────────────────────────────────────────
# Показать справку по получению ключей
# ─────────────────────────────────────────────────────────────────────────────
show_credentials_help() {
    echo ""
    echo -e "${CYAN}───────────────────────────────────────────────────────────────${NC}"
    echo -e "${BOLD}  📋 Справка: как получить ключи и токены${NC}"
    echo -e "${CYAN}───────────────────────────────────────────────────────────────${NC}"
    echo ""
    echo -e "  ${BOLD}1. Telegram Bot Token${NC}"
    echo "     Создайте бота через @BotFather в Telegram:"
    echo "     • Напишите /newbot"
    echo "     • Задайте имя и username"
    echo "     • Скопируйте токен вида: 123456789:ABCdef..."
    print_link "https://t.me/BotFather"
    echo ""
    echo -e "  ${BOLD}2. Yandex Cloud API Key${NC}"
    echo "     Консоль → IAM → Сервисные аккаунты → Ваш SA →"
    echo "     → Создать новый ключ → Создать API-ключ"
    echo "     Область: yc.ai.foundationModels.execute"
    print_link "https://yandex.cloud/ru/docs/ai-studio/operations/get-api-key"
    echo ""
    echo -e "  ${BOLD}3. S3 Static Keys (для памяти диалогов)${NC}"
    echo "     Консоль → IAM → Сервисные аккаунты → Ваш SA →"
    echo "     → Создать новый ключ → Создать статический ключ доступа"
    print_link "https://yandex.cloud/ru/docs/storage/s3/s3-api-quickstart"
    echo ""
    echo -e "  ${BOLD}4. S3 Bucket${NC}"
    echo "     Консоль → Object Storage → Создать бакет"
    echo "     Имя: любое уникальное, например my-bot-state-12345"
    print_link "https://yandex.cloud/ru/docs/storage/operations/buckets/create"
    echo ""
    echo -e "  ${BOLD}5. AI Agent ID${NC}"
    echo "     Консоль → AI Studio → Агенты → Создать агента"
    echo "     Или используйте модель напрямую без агента"
    print_link "https://yandex.cloud/ru/docs/ai-studio/operations/agents/create"
    echo ""
    echo -e "${CYAN}───────────────────────────────────────────────────────────────${NC}"
}

# ─────────────────────────────────────────────────────────────────────────────
# Интерактивное меню
# ─────────────────────────────────────────────────────────────────────────────
show_menu() {
    echo ""
    echo -e "${CYAN}───────────────────────────────────────────────────────────────${NC}"
    echo -e "${BOLD}  Выберите действие:${NC}"
    echo -e "${CYAN}───────────────────────────────────────────────────────────────${NC}"
    echo ""
    echo "  1) 🚀 Начальная настройка (YC CLI + сервисный аккаунт)"
    echo "  2) 🆕 Создать нового бота"
    echo "  3) 📋 Справка по получению ключей"
    echo "  4) ⚙️  Перенастроить YC аккаунт"
    echo "  5) 🔧 Режим разработчика (debug)"
    echo "  6) ❌ Выход"
    echo ""
    read -p "  Ваш выбор [1-6]: " choice
    
    case $choice in
        1)
            run_initial_setup
            ;;
        2)
            run_creator false false
            ;;
        3)
            show_credentials_help
            echo ""
            read -p "  Нажмите Enter для возврата в меню..."
            show_menu
            ;;
        4)
            rm -f "$CONFIG_FILE" 2>/dev/null
            echo ""
            print_info "Настройки сброшены. Перезапускаю..."
            sleep 1
            run_initial_setup
            ;;
        5)
            if [ -f "$CONFIG_LOCAL" ]; then
                run_creator true false
            else
                echo ""
                print_warn "Файл config.local не найден!"
                echo ""
                echo "  Создайте его из примера:"
                echo -e "    ${CYAN}cp config.local.example config.local${NC}"
                echo "  Заполните своими ключами и запустите снова."
                echo ""
                read -p "  Нажмите Enter для возврата в меню..."
                show_menu
            fi
            ;;
        6|q|Q)
            echo ""
            echo -e "  ${CYAN}👋 До свидания!${NC}"
            echo ""
            exit 0
            ;;
        *)
            echo ""
            print_warn "Неверный выбор. Попробуйте снова."
            show_menu
            ;;
    esac
}

# ─────────────────────────────────────────────────────────────────────────────
# Начальная настройка
# ─────────────────────────────────────────────────────────────────────────────
run_initial_setup() {
    echo ""
    echo -e "${CYAN}───────────────────────────────────────────────────────────────${NC}"
    echo -e "${BOLD}  🚀 Начальная настройка Yandex Cloud${NC}"
    echo -e "${CYAN}───────────────────────────────────────────────────────────────${NC}"
    echo ""
    echo "  Эта настройка выполняется один раз и включает:"
    echo "    • Установка Python зависимостей"
    echo "    • Настройка Yandex Cloud CLI"
    echo "    • Создание сервисного аккаунта с нужными ролями"
    echo ""
    
    # 1. Python и зависимости
    setup_python
    echo ""
    
    # 2. Yandex Cloud CLI
    setup_yc_cli
    echo ""
    
    # 3. Сервисный аккаунт
    check_service_account
    echo ""
    
    echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}  ✅ Начальная настройка завершена!${NC}"
    echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
    echo ""
    echo "  Теперь вы можете создать бота (пункт 2 в меню)."
    echo ""
    read -p "  Нажмите Enter для возврата в меню..."
    show_menu
}

# ─────────────────────────────────────────────────────────────────────────────
# Запуск создателя ботов
# ─────────────────────────────────────────────────────────────────────────────
run_creator() {
    local debug_mode=$1
    local force_setup=$2
    
    echo ""
    
    # 1. Python и зависимости
    setup_python
    echo ""
    
    # 2. Yandex Cloud CLI
    setup_yc_cli
    echo ""
    
    # 3. Сервисный аккаунт (если не debug mode или force_setup)
    if [ "$debug_mode" = false ] || [ "$force_setup" = true ]; then
        check_service_account
        echo ""
    fi
    
    # 4. Debug config (если включён)
    if [ "$debug_mode" = true ]; then
        DEBUG_MODE=true
        load_debug_config
    fi
    
    echo ""
    
    # 5. Запуск Python скрипта
    ARGS=""
    [ "$debug_mode" = true ] && ARGS="--debug"
    
    # Экспортируем SA для Python
    export YC_SERVICE_ACCOUNT
    
    python3 "$SCRIPT_DIR/create-bot.py" $ARGS
    
    # После завершения — возврат в меню
    echo ""
    read -p "  Нажмите Enter для возврата в меню..."
    show_menu
}

# ─────────────────────────────────────────────────────────────────────────────
# Главная функция
# ─────────────────────────────────────────────────────────────────────────────
main() {
    print_header
    show_menu
}

main
