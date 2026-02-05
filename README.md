# Telegram Bot Builder for Yandex Cloud

An interactive CLI tool for creating and deploying AI-powered Telegram bots on Yandex Cloud serverless infrastructure.

## Features

- **Interactive Setup Wizard** — step-by-step bot creation with guided prompts
- **YandexGPT Integration** — use AI Agents from AI Studio or YandexGPT models directly
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

## Quick Start

```bash
# Clone the repository
git clone <repo-url>
cd blueprints-agent-deploy

# Run the setup wizard
./run.sh
```

The wizard will guide you through:
1. Python environment setup (virtual environment + dependencies)
2. Yandex Cloud CLI installation and authentication
3. Service account creation with required IAM roles
4. Bot configuration (Telegram token, AI agent/model, features)
5. Deployment to Yandex Cloud Functions

## Interactive Menu

```
1) 🚀 Initial Setup (YC CLI + service account)
2) 🆕 Create a new bot
3) 📋 Help: how to get API keys
4) ⚙️  Reconfigure YC account
5) 🔧 Developer mode (debug)
6) ❌ Exit
```

## Prerequisites

### Yandex Cloud Account

1. Create an account at [console.yandex.cloud](https://console.yandex.cloud)
2. Set up a billing account (free trial available with grants)

### Telegram Bot Token

1. Open [@BotFather](https://t.me/BotFather) in Telegram
2. Send `/newbot` and follow the instructions
3. Copy the token (format: `123456789:ABC...`)

### Python 3.8+

```bash
python3 --version
```

## Project Structure

```
blueprints-agent-deploy/
├── run.sh               # 👈 Entry point — run this
├── create-bot.py        # Interactive bot creator (Python)
├── config.local.example # Debug credentials template
├── bots/                # Generated bot projects (created on first run)
├── src/                 # Bot code template
│   └── main.py
├── terraform/           # IaC for deployment (alternative method)
│   └── main.tf
└── .cursor/
    └── mcp.json         # MCP integration for YC documentation
```

## What Gets Created

When you create a bot, the wizard generates a complete project:

```
bots/my-telegram-bot/
├── src/
│   └── main.py          # Bot code (customized based on your choices)
│   └── requirements.txt # Python dependencies
├── deploy.sh            # One-click deployment script
├── .env                 # Environment variables (your secrets)
├── .env.example         # Template for sharing
├── .gitignore
└── README.md
```

## Bot Features

Choose features during creation:

| Feature | Description |
|---------|-------------|
| 💾 **Dialog Memory** | Persist conversation context across messages using S3 |
| 🔄 **Agent Selection** | Allow users to switch between multiple AI agents |
| 📊 **Status Command** | Show dialog statistics and current agent |
| 🎨 **Custom Menu** | Interactive keyboard with quick actions |

## AI Configuration

### Option 1: AI Agents (Recommended)

Create agents in [Yandex AI Studio](https://console.yandex.cloud/folders/<folder>/ai-studio/prompts):
- Configure system prompts, temperature, and tools
- Get the agent ID (format: `fvt...`)
- The bot will use the Responses API for stateful conversations

### Option 2: Direct Model Access

Use YandexGPT models directly:
- YandexGPT Pro 5
- YandexGPT Pro 5.1 (RC)
- YandexGPT Lite

## Manual Deployment

If you prefer manual setup over the wizard:

### 1. Install Yandex Cloud CLI

```bash
curl -sSL https://storage.yandexcloud.net/yandexcloud-yc/install.sh | bash
yc init
```

### 2. Create Service Account

```bash
# Get folder ID
yc config get folder-id

# Create service account
yc iam service-account create --name telegram-bot-sa

# Assign roles
SA_ID=$(yc iam service-account get telegram-bot-sa --format json | jq -r '.id')
FOLDER_ID=$(yc config get folder-id)

yc resource-manager folder add-access-binding $FOLDER_ID \
    --role ai.languageModels.user --subject serviceAccount:$SA_ID
yc resource-manager folder add-access-binding $FOLDER_ID \
    --role ai.assistants.editor --subject serviceAccount:$SA_ID
yc resource-manager folder add-access-binding $FOLDER_ID \
    --role storage.editor --subject serviceAccount:$SA_ID

# Create API key
yc iam api-key create --service-account-name telegram-bot-sa
```

### 3. Configure Terraform

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with your values
```

### 4. Deploy

```bash
terraform init
terraform apply
```

### 5. Set Webhook

```bash
curl -X POST "https://api.telegram.org/bot<TOKEN>/setWebhook?url=<FUNCTION_URL>"
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `TELEGRAM_BOT_TOKEN` | Bot token from @BotFather |
| `YANDEX_CLOUD_API_KEY` | API key for AI services |
| `YANDEX_CLOUD_FOLDER` | Yandex Cloud folder ID |
| `S3_BUCKET` | Object Storage bucket for dialog state |
| `AWS_ACCESS_KEY_ID` | S3 static access key |
| `AWS_SECRET_ACCESS_KEY` | S3 secret key |
| `AGENTS_JSON` | JSON map of agents: `{"agent_id": "Agent Name"}` |

## Debug Mode

For development, use pre-configured credentials:

```bash
# Create config from template
cp config.local.example config.local

# Edit with your test credentials
nano config.local

# Run in debug mode (menu option 5)
./run.sh
```

The `config.local` file is git-ignored and contains your personal API keys for testing.

## Useful Commands

```bash
# View function logs
yc serverless function logs <function-name> --follow

# Check webhook status
curl "https://api.telegram.org/bot<TOKEN>/getWebhookInfo"

# Remove webhook
curl "https://api.telegram.org/bot<TOKEN>/deleteWebhook"

# List functions
yc serverless function list
```

## Troubleshooting

### Bot not responding

1. Check webhook: `curl "https://api.telegram.org/bot<TOKEN>/getWebhookInfo"`
2. View logs: `yc serverless function logs <function-name>`
3. Verify environment variables in function settings

### AI errors

1. Verify `YANDEX_CLOUD_API_KEY` is valid
2. Check that the AI agent exists in the console
3. Review quotas in Yandex Cloud

### S3 errors

1. Verify bucket exists: `yc storage bucket list`
2. Check `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY`
3. Ensure service account has `storage.editor` role

## Security Notes

- Never commit `.env` or `config.local` files
- Rotate API keys periodically
- Use separate service accounts for production and development
- The `.gitignore` is pre-configured to exclude sensitive files

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

MIT
