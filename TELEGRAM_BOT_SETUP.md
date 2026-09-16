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
| `TELEGRAM_WEBHOOK_SECRET` | A random secret also passed to Telegram as `secret_token` | Yes |
| `CRON_SECRET` | Shared authentication for reminder and command setup routes | Yes |
| `REDIS_URL` or `KV_URL` | Redis connection URL | One of them |

> **Note:** If you're using Vercel KV integration, the `KV_URL` is automatically set. The bot will use it if `REDIS_URL` is not set.

### Setup Steps

1. Go to your Vercel project dashboard
2. Navigate to **Settings** → **Environment Variables**
3. Add `TELEGRAM_BOT_TOKEN` with your bot token
4. Generate a secret, for example with `openssl rand -hex 32`, and add it as `TELEGRAM_WEBHOOK_SECRET`
5. If using external Redis (not Vercel KV), add `REDIS_URL`
6. Redeploy the project for changes to take effect

## Set Webhook

After deployment, register the webhook URL with Telegram:

```bash
curl --get "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/setWebhook" \
  --data-urlencode "url=https://<YOUR_VERCEL_DOMAIN>/api/telegram" \
  --data-urlencode "secret_token=<YOUR_RANDOM_WEBHOOK_SECRET>"
```

Replace:
- `<YOUR_BOT_TOKEN>` with your actual bot token
- `<YOUR_VERCEL_DOMAIN>` with your Vercel domain (e.g., `your-project.vercel.app`)
- `<YOUR_RANDOM_WEBHOOK_SECRET>` with the exact value stored in `TELEGRAM_WEBHOOK_SECRET`

### Example

```bash
curl --get "https://api.telegram.org/bot123456:ABC-DEF/setWebhook" \
  --data-urlencode "url=https://shabbat-poster.vercel.app/api/telegram" \
  --data-urlencode "secret_token=<YOUR_RANDOM_WEBHOOK_SECRET>"
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
4. Ensure `TELEGRAM_WEBHOOK_SECRET` matches the `secret_token` used with `setWebhook`

### Redis errors

1. Verify `REDIS_URL` or `KV_URL` is set
2. Check that your Redis instance is accessible
3. For Vercel KV, ensure the KV store is linked to your project

### Webhook errors

If `setWebhook` fails:
1. Ensure your Vercel domain uses HTTPS
2. Verify the `/api/telegram` route is accessible
3. Check that the bot token is valid

## Authenticated administration and reminders

Set a separate random `CRON_SECRET` in Vercel and the GitHub Actions secret with
that same name. Set the Actions `VERCEL_URL` secret to the canonical HTTPS origin
without a trailing redirect. Register commands with an authenticated request to
`/api/setup_commands`, using `Authorization: Bearer <CRON_SECRET>`.
Missing configuration fails closed with 503; a missing or wrong supplied secret
fails with 403. Targeted `test_user_id` requests require the same secret, an active
opt-in and the normal calendar/time guards. They cannot force delivery outside
those guards. No endpoint returns Telegram error descriptions or user IDs.

GitHub Actions is the sole reminder scheduler. Vercel cron entries are removed.
The daily schedules in UTC are:

| Reminder | UTC schedule | Israel local time |
| --- | --- | --- |
| Shabbat/holiday eve check | 05:00 | 07:00 winter or 08:00 summer |
| Omer evening | 18:00 | 20:00 winter or 21:00 summer |
| Omer morning | 06:00 | 08:00 winter or 09:00 summer |

There is one Friday check, from the daily Shabbat schedule. Evening Omer sends
require the current time to be after Jerusalem nightfall (the existing JewCal
8.5-degree calculation) and before local midnight. The supported 2024-2030 Omer
nightfall dates are regression-tested before 21:00 Israel summer time. Scheduler
lateness is not assumed: a run outside its window reports `outside_delivery_window`
and sends nothing. The morning window is 06:00-12:00 local time and uses the prior
evening's event identity. Morning reminders can cover missed evening runs but do
not send the missed evening poster or its blessing text.

Each request inspects at most two saved candidates and attempts at most two
recipients. Candidate identities are saved in linked Redis pages before sending;
retries of an input page reuse exactly those identities. SCAN advances at page
boundaries, never through a positional offset into a newly fetched response.
Each SCAN response is capped at 1000 candidates and divided into two-candidate
pages. Each page expires after one hour. Root pointers contain only event scope
and an opaque token, no recipient IDs, and remain for 72 hours so expired runs
fail explicitly rather than silently reseeding. The traversal is not a complete
subscription snapshot; enrollment changes during traversal can wait for another
run, but delivery bookkeeping does not cause unchanged subscribers to be omitted.

The workflow follows at most 100 pages, retries a failed page up to three times,
and fails on unresolved recipient failures, pagination caps or transport errors.
The script has a 25-minute budget and the job a 30-minute timeout. For a failed
run, dispatch the workflow with its logged `resume_cursor` in the `resume_cursor`
input. This value is an opaque random page token, never a recipient ID.

If a page expired, use the explicit `restart_traversal` checkbox and leave
`resume_cursor` empty. The driver generates one fresh `r.<128-bit-token>` cursor
and keeps it unchanged across retries. Existing event success receipts still
suppress completed sends. For a manual authenticated request, pass the saved
`cursor` value to the same reminder route. To explicitly restart, generate a new
32-character lowercase hexadecimal random token and use `cursor=r.<token>`;
retry that exact value if the initial fresh page fails. Missing, invalid or
expired ordinary continuation tokens fail closed. Starting with `cursor=0`
reuses the existing event root; it does not implicitly replace an expired run.
Completed runs also require explicit restart after their saved pages expire.
Resume/restart remains subject to the same active event and delivery time guards.
No manual Redis editing is needed.

The response and logs contain `attempted`, `sent`, `failed`, `skipped`, `status`
and `cursor`. Partial delivery failures return HTTP 503, allowing both Actions and
manual callers to notice and retry them. Counts describe each invocation, not
cumulative totals across retries. Failed partial pages are retried from their
input cursor so failed recipients are not silently passed over.

## Private data controls

All preference-bearing bot messages and buttons require a private chat whose
chat ID equals the sender's ID. Use `/privacy` for the policy link, `/export` for
an explicitly confirmed private JSON document, and `/delete_my_data` for an
explicitly confirmed deletion. Confirmation tokens expire after ten minutes.
The JSON document is assembled in memory and contains only that user's stored
preferences, state and reminder/count records. Privacy-flow and webhook-processing
metadata is excluded. Export confirmation metadata is removed after success.

Deletion first persists proof of the already-confirmed operation for up to seven
days. This record survives the initial ten-minute nonce expiry, partial cleanup,
and failed delivery of the completion notice. While it is pending, reminders are
suppressed and unrelated bot actions wait for the deletion to finish. Retrying
the confirmed callback, including clicking its same confirmation button again,
resumes cleanup without requiring the expired initial nonce.

Cleanup removes the user's preferences, conversation state, legacy sent/count
records, delivery/mutation records, privacy tokens, and membership in all live
recipient pages. Exact ownership keeps other users' data. Page creation and
deletion share an owned snapshot lock, so a new saved page cannot retain the user's
ID after cleanup. This lock is released before any reminder takes a user lock;
contention fails retryably instead of waiting in an unsafe lock order.

The deletion success notice is sent only after owned data and page membership
cleanup succeeds. The pending proof and active update processing claim are removed
atomically with the global successful-update receipt after the notice succeeds.
The user processing lock is then released. Failures retain proof for retry and do
not claim deletion completed. Telegram's copies of messages, photos and exported
documents are not deleted. `/reset` remains a settings reset.

Every successfully processed webhook update retains a pseudonymous anti-replay receipt for seven days:
a SHA-256 digest of the Telegram update ID with the constant value `1`. It contains
no user/chat ID, payload, timestamp or reverse index. The digest is not a secret
and is not a claim of mathematical anonymity. The receipt prevents a retried
confirmation from deleting a later re-enrollment and prevents an old successful opt-in from recreating deleted preferences. New user activity can recreate
preferences with reminders disabled by default.

## Storage, retries and limits

Existing preference JSON remains readable, including legacy image fields and
unknown fields. Independent edits merge fields atomically. List and toggle
mutations use WATCH/MULTI retries. Per-update mutation receipts keep a retried
toggle from applying twice after a transient delivery failure.

Owned processing leases expire after 600 seconds, longer than the 300-second
function limit. Global update success and user-owned mutation receipts expire after seven days;
scheduled event success receipts after 72 hours. Existing sent/count markers
expire after 48 hours; new count keys use the event date instead of only a day
number. Pending conversation state expires after one hour. Redis connection and
read timeouts are three and five seconds. Storage failure prevents delivery.

Failed work releases only its own lease. A successful Telegram send followed by
a crash or failed Redis success write can still produce a duplicate on retry:
Telegram and Redis do not share an atomic transaction. Some multi-message bot
responses can likewise partially arrive before a retry. Claims suppress completed
replays and overlapping sends while their leases remain valid; they do not promise
exactly-once external delivery. Do not increase the function lifetime beyond the
lease without revisiting this assumption.

Telegram downloads stream into bounded memory, stop at the common 3 MiB image
limit, reject redirects, and close responses. They do not create temporary files.
Poster validation still runs through the safe shared builder.

## Offline verification

The bot hardening tests require Python 3.12 and a local `redis-server` binary.
They start a fresh nonpersistent server with `--port 0` and an owned Unix socket,
strip real service credentials and block every external connection. No critical
Redis test is skipped if the binary or socket permission is missing. On a
restricted host, grant only the test invocation permission needed to bind its
owned socket. Run `python -m pytest tests/test_bot_hardening.py -q`.

## Bot input limits and per-user request budget

Bot text setters use the shared 500-character limit. City selection uses the shared
12-city limit. Oversized new edits are rejected with a correction message; existing
legacy values are preserved. Removing cities from an oversized legacy list is
allowed. If existing settings cannot render, the bot points to `/settings` and
explains the limits instead of truncating or deleting the settings.

The webhook allows 30 distinct authenticated private updates per actor in a
60-second window. Users sharing Telegram's source IP have separate budgets.
Completed duplicate updates do not consume quota. A failed update's short-lived
processing metadata remembers that it already consumed quota; the budget receipt
is removed atomically on success. Exceeding quota returns 429 with
`Retry-After: 60`. The ordinary per-actor quota counter can remain for at most
60 seconds after export, is excluded from exported JSON, and is removed by
confirmed deletion. Retaining it prevents privacy commands from resetting quota.
Global seven-day success receipts contain no actor mapping and survive deletion;
user-owned processing and mutation records remain deletable.

## Callback acknowledgements and recovery metadata

Telegram's terminal expired/invalid callback-query acknowledgement response does
not prevent an authenticated, deduplicated action from proceeding. Genuine action
storage or message/photo delivery errors remain retryable.

Saved candidate pages live at `zmunah:reminder_page:<opaque-token>` for one hour,
with at most two candidate IDs per page. Their memberships are removed on user
deletion and excluded from the private data export as transient processing data.
Root pointers at `zmunah:reminder_root:<scope>` (or with a fresh-run suffix) contain
no recipient IDs and expire after 72 hours. The snapshot lock is token-owned and
expires after 600 seconds. Confirmed-but-pending deletion proof is stored at
`zmunah:privacy:<user_id>:delete_pending` for at most seven days, is excluded from
export, and is removed on completed deletion. These are operational lifetimes,
not promises about copies retained by Telegram or infrastructure backups.
