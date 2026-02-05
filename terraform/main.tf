# Terraform конфигурация для Telegram бота на Yandex Cloud Serverless

terraform {
  required_providers {
    yandex = {
      source  = "yandex-cloud/yandex"
      version = ">= 0.100"
    }
    archive = {
      source  = "hashicorp/archive"
      version = ">= 2.0"
    }
  }
  required_version = ">= 1.0"
}

provider "yandex" {
  # Можно задать через переменные окружения:
  # YC_TOKEN, YC_CLOUD_ID, YC_FOLDER_ID
  # или через переменные Terraform
  folder_id = var.folder_id
}

# ==================== Переменные ====================

variable "folder_id" {
  description = "Yandex Cloud Folder ID"
  type        = string
}

variable "telegram_bot_token" {
  description = "Telegram Bot Token"
  type        = string
  sensitive   = true
}

variable "yandex_cloud_api_key" {
  description = "Yandex Cloud API Key для AI Assistant"
  type        = string
  sensitive   = true
}

variable "yandex_cloud_project_id" {
  description = "Yandex Cloud Project ID (обычно совпадает с folder_id)"
  type        = string
  default     = ""
}

variable "assistant_prompt_id" {
  description = "AI Assistant Prompt ID (ID агента из консоли YC)"
  type        = string
  default     = ""
}

# ==================== Service Account ====================

resource "yandex_iam_service_account" "bot_sa" {
  name        = "telegram-bot-sa"
  description = "Service account для Telegram бота"
}

resource "yandex_resourcemanager_folder_iam_member" "bot_sa_invoker" {
  folder_id = var.folder_id
  role      = "serverless.functions.invoker"
  member    = "serviceAccount:${yandex_iam_service_account.bot_sa.id}"
}

resource "yandex_resourcemanager_folder_iam_member" "bot_sa_editor" {
  folder_id = var.folder_id
  role      = "editor"
  member    = "serviceAccount:${yandex_iam_service_account.bot_sa.id}"
}

# ==================== Cloud Function ====================

# Архивируем исходный код
data "archive_file" "function_zip" {
  type        = "zip"
  source_dir  = "${path.module}/../src"
  output_path = "${path.module}/function.zip"
}

resource "yandex_function" "telegram_bot" {
  name               = "telegram-bot-handler"
  description        = "Обработчик вебхуков Telegram бота"
  user_hash          = data.archive_file.function_zip.output_sha256
  runtime            = "python312"
  entrypoint         = "main.handler"
  memory             = 128
  execution_timeout  = 30
  service_account_id = yandex_iam_service_account.bot_sa.id

  environment = {
    TELEGRAM_BOT_TOKEN    = var.telegram_bot_token
    YANDEX_CLOUD_API_KEY  = var.yandex_cloud_api_key
    YANDEX_CLOUD_PROJECT_ID = var.yandex_cloud_project_id
    ASSISTANT_PROMPT_ID   = var.assistant_prompt_id
  }

  content {
    zip_filename = data.archive_file.function_zip.output_path
  }
}

# Делаем функцию публично доступной для вебхуков
resource "yandex_function_iam_binding" "function_public" {
  function_id = yandex_function.telegram_bot.id
  role        = "functions.functionInvoker"
  members     = ["system:allUsers"]
}

# ==================== API Gateway ====================

resource "yandex_api_gateway" "bot_gateway" {
  name        = "telegram-bot-gateway"
  description = "API Gateway для Telegram бота"

  spec = <<-EOF
    openapi: 3.0.0
    info:
      title: Telegram Bot API
      version: 1.0.0
    paths:
      /webhook:
        post:
          summary: Telegram Webhook
          operationId: telegramWebhook
          x-yc-apigateway-integration:
            type: cloud_functions
            function_id: ${yandex_function.telegram_bot.id}
            service_account_id: ${yandex_iam_service_account.bot_sa.id}
          responses:
            '200':
              description: Success
      /health:
        get:
          summary: Health Check
          operationId: healthCheck
          responses:
            '200':
              description: OK
              content:
                application/json:
                  schema:
                    type: object
                    properties:
                      status:
                        type: string
          x-yc-apigateway-integration:
            type: dummy
            content:
              application/json: '{"status": "ok"}'
            http_code: 200
  EOF
}

# ==================== Outputs ====================

output "webhook_url" {
  description = "URL для регистрации вебхука в Telegram"
  value       = "https://${yandex_api_gateway.bot_gateway.domain}/webhook"
}

output "function_id" {
  description = "ID Cloud Function"
  value       = yandex_function.telegram_bot.id
}

output "api_gateway_domain" {
  description = "Домен API Gateway"
  value       = yandex_api_gateway.bot_gateway.domain
}

output "set_webhook_command" {
  description = "Команда для установки вебхука"
  value       = "curl -X POST 'https://api.telegram.org/bot<YOUR_TOKEN>/setWebhook?url=https://${yandex_api_gateway.bot_gateway.domain}/webhook'"
  sensitive   = false
}

