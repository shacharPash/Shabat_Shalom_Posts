# Telegram Bot Setup

This guide explains how to set up the Telegram bot for the Shabbat Poster Generator.

## Prerequisites

1. Create a Telegram bot via [@BotFather](https://t.me/BotFather)
2. Get your bot token from BotFather
3. A Vercel account with this project deployed

## Vercel Deployment

### Environment Variables

The bot requires these environment variables in Vercel:

| Variable | Description | Required |
|----------|-------------|----------|
| `TELEGRAM_BOT_TOKEN` | Your bot token from @BotFather | Yes |
| `REDIS_URL` or `KV_URL` | Redis connection URL | One of them |

> **Note:** If you're using Vercel KV integration, the `KV_URL` is automatically set. The bot will use it if `REDIS_URL` is not set.

### Setup Steps

1. Go to your Vercel project dashboard
2. Navigate to **Settings** → **Environment Variables**
3. Add `TELEGRAM_BOT_TOKEN` with your bot token
4. If using external Redis (not Vercel KV), add `REDIS_URL`
5. Redeploy the project for changes to take effect

## Set Webhook

After deployment, register the webhook URL with Telegram:

```bash
curl "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/setWebhook?url=https://<YOUR_VERCEL_DOMAIN>/api/telegram"
```

Replace:
- `<YOUR_BOT_TOKEN>` with your actual bot token
- `<YOUR_VERCEL_DOMAIN>` with your Vercel domain (e.g., `your-project.vercel.app`)

### Example

```bash
curl "https://api.telegram.org/bot123456:ABC-DEF/setWebhook?url=https://shabbat-poster.vercel.app/api/telegram"
```

## Verify Webhook

Check that the webhook is properly configured:

```bash
curl "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getWebhookInfo"
```

You should see a response like:

```json
{
  "ok": true,
  "result": {
    "url": "https://your-domain.vercel.app/api/telegram",
    "has_custom_certificate": false,
    "pending_update_count": 0
  }
}
```

## Test the Bot

1. Open your bot in Telegram (search for your bot's username)
2. Send `/start` - You should receive a welcome message
3. Send `/settings` - View your current preferences
4. Send a photo - The bot will generate a Shabbat poster

## Troubleshooting

### Bot not responding

1. Verify webhook is set: `getWebhookInfo` should show your URL
2. Check Vercel function logs for errors
3. Ensure `TELEGRAM_BOT_TOKEN` is correctly set

### Redis errors

1. Verify `REDIS_URL` or `KV_URL` is set
2. Check that your Redis instance is accessible
3. For Vercel KV, ensure the KV store is linked to your project

### Webhook errors

If `setWebhook` fails:
1. Ensure your Vercel domain uses HTTPS
2. Verify the `/api/telegram` route is accessible
3. Check that the bot token is valid

