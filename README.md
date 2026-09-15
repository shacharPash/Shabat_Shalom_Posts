# Zmunah: personal Shabbat and Omer posters

A personal Hebrew poster generator maintained by [shacharPash](https://github.com/shacharPash). Python renders uploaded images and text; the browser downloads or shares the result. The private Telegram bot stores preferences in Redis and sends opted-in reminders. There is no AI service or automatic social publishing.

## Current release scope

Israel parsha readings, with validated local fallback data for 2024-2040. Omer event identity and reminders use Asia/Jerusalem and the existing Jerusalem 8.5 degree nightfall calculation. An evening run after local midnight is skipped; morning recovery uses the prior evening's event. Custom poster cities and manually entered times remain available. Worldwide reminder localization is not implemented.

This is a personal beta candidate. Public release is pending the owner decisions and provider checks in [the release guide](docs/RELEASE.md). No code license has been granted by this change. See [the proposal](docs/LICENSE_PROPOSAL.md), [asset and dependency notices](THIRD_PARTY_NOTICES.md), [privacy](public/privacy.html), and [terms](public/terms.html).

## Setup

Supported runtime: Python 3.12. Development also needs Node 22 and a local `redis-server` binary for isolated tests. Install Redis with your OS package manager. Production needs only the runtime lock, not Node or development tools.

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install --require-hashes -r requirements-dev.txt
.venv/bin/python -m pip check
.venv/bin/python -m uvicorn service:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000/`. Both `service:app` and `api.index:app` expose `/`, `POST /poster`, `/omer-info`, `/upcoming-events` and public assets. Public pages are `/privacy.html` and `/terms.html`. Local poster work does not need Telegram or Redis secrets. The calendar service can request Hebcal over the network; use an explicit offline harness or mocked HTTP for offline work. Tests reject unmocked network access and remove service secrets before application imports.

Production installation:

```sh
python3.12 -m pip install --require-hashes -r requirements.txt
```

## Configuration

Use `.env.example` as a names/reference guide. Do not commit `.env` or secret values. The local server does not automatically load that file; pass only the needed variables explicitly in your own environment. Use disposable Redis state and absent or dummy service secrets for development and previews.

Service variable names: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_WEBHOOK_SECRET`, `CRON_SECRET`, `REDIS_URL` (legacy fallback `KV_URL`), `WEB_APP_URL`. GitHub reminder workflows need `CRON_SECRET` and `VERCEL_URL`. Image, time, watermark and calendar configuration names are described in `.env.example`. Configure the canonical personal site origin before using bot privacy links.

The webhook registration's `secret_token` must equal `TELEGRAM_WEBHOOK_SECRET`; reminder workflow and production `CRON_SECRET` must match. Do not print either value while comparing. Registration and command setup are explicit release operations documented in [bot setup](TELEGRAM_BOT_SETUP.md).

## Media and settings links

Public input accepts base64 JPEG, PNG, static WebP or bounded GIF. URL/path inputs and videos are disabled. Each decoded upload is at most 3 MiB (3,145,728 bytes), 20 million source pixels and 12,000 pixels per dimension. Omer output is a static PNG even with GIF input; Shabbat GIF output preserves its frames. GIF permits at most 30 frames and 40 million aggregate canvas pixels. HTTP request and response bodies are capped at 4,400,000 bytes. Errors use 400/413/415 with actionable Hebrew text. The browser rejects unsupported or over-size files before preview, and may compress ordinary images. The server validates actual image bytes independently.

Links save mode, ordinary city selection/order in Shabbat mode and Omer nusach. Personal blessing/dedication text is excluded unless the unchecked include-text option is selected. Images, crop, dates, custom cities, offsets and styling are not included. Older links still load, including literal percent signs and Hebrew text. Anyone with an optional-text URL can read its contents.

## Validation

Run from the repository root with Python 3.12, Node 22 and `redis-server` on PATH:

```sh
.venv/bin/python run_tests.py -q
.venv/bin/python -m ruff check .
.venv/bin/python -m mypy
.venv/bin/python -m pip check
.venv/bin/python -m pip_audit --require-hashes --disable-pip -r requirements.txt
.venv/bin/python -m pip_audit --require-hashes --disable-pip -r requirements-dev.txt
```

The tests launch their own disposable Redis process, use synthetic images and reject unmocked HTTP/DNS. The frontend regression runs Node through pytest without a new frontend framework. Warnings fail the suite. Ruff checks core correctness; mypy covers six maintained modules, not the whole legacy application. Audit commands query public vulnerability services and require network access.

For dependency updates, regenerate `requirements.txt` first and `requirements-dev.txt` second using the locked pip-tools and `--generate-hashes --strip-extras --allow-unsafe --index-url https://pypi.org/simple`. Inspect the diff, install in a clean environment, rerun the gates and update notices. `anyio==4.14.2` avoids the deprecated alias used by the locked Starlette TestClient; revisit that pin when upstream compatibility changes.

Regenerate local parsha data with `scripts/update_parsha_data.py`, inspect the diff and validate Israel reading coverage. The scheduled workflow produces a reviewable artifact; it does not auto-commit data. See its command-line help for year range and cached-source options.

## Operations

Follow [release, backup/restore rehearsal and rollback](docs/RELEASE.md). GitHub Actions is the only intended reminder scheduler after rollout. Existing Vercel cron configuration must be retired during release. Redis holds personal data; never use production storage for local tests. Bot users can confirm `/export` or `/delete_my_data` privately; provider, Telegram, browser and recipient copies have separate lifetimes.
