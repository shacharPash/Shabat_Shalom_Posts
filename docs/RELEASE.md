# Personal beta release and operations

This is a reviewable procedure, not a record of production changes. Complete checks with synthetic data first. Nothing here grants asset rights or legal compliance.

## Pre-release gates

- The owner has authorized hardening pull requests to the existing public repository. That authorization does not grant a new code-reuse license. Choose the code license and copyright wording before a wider public beta or any claim that reuse is permitted.
- Confirm permission for every bundled photograph, background, icon and watermark in THIRD_PARTY_NOTICES.md. A digest proves file identity, not rights.
- Configure a direct private contact/reporting channel and update the privacy/security pages. Never solicit private details in public GitHub issues.
- Verify hosting and database regions, backup locations, access controls, actual logging/retention, processor terms/DPAs and any relevant international transfer terms for the intended audience. Current verified function region is iad1; database and contractual retention are unverified.
- Review potentially sensitive religious preferences and free text against the intended audience and jurisdiction. No additional consent banner is assumed by this code.
- Restrict actual Telegram, Redis, webhook and cron credentials to production. The current verified configuration includes production, preview and development; isolation is not already complete. Changes affect future deployments. Retire old credential-bearing previews and verify fork/preview protection. Use dummy/absent secrets and disposable Redis for preview/development.
- Set the canonical `WEB_APP_URL`. Check webhook registration `secret_token` against `TELEGRAM_WEBHOOK_SECRET`, and GitHub/production `CRON_SECRET` equality without logging values. Existing secret names alone do not establish a match.
- Run Python 3.12 / Node 22 full tests, Ruff, mypy, dependency consistency and both dependency audits. Review CI on the exact release revision, then a Linux/Vercel build. Local macOS results do not prove that build.
- Exercise a synthetic poster with keyboard city selection/reorder and crop, plus square/portrait Shabbat/Omer and bounded GIF output. Check Hebcal credit and watermark at full size, public legal pages, local fonts and no analytics network scripts.
- Record a successful isolated backup/restore rehearsal. Confirm deletion handling and provider backup expiry policy before real data backups are relied upon.

## Backup and restore rehearsal

Use a new empty local Redis instance in a temporary directory, bound to loopback or a Unix socket. Confirm the target is disposable and never read a production URL from the shell by default. The test suite's Unix-socket Redis fixture is an example of isolated configuration.

1. Write synthetic preference and counted-event keys, including one key with a short TTL and one synthetic deleted user. Save an RDB snapshot with Redis SAVE to that instance's own directory. Record the Redis version and key counts without real content.
2. Stop the disposable process cleanly. Copy only that synthetic `dump.rdb` into a second empty temporary Redis directory, then start an isolated restore instance using that file. Do not restore over a running or shared database.
3. Compare synthetic values and counts. Confirm remaining TTLs are bounded and not reset to full retention, persistent preferences remain persistent, and deleted users remain absent. Exercise export/delete with mocked Telegram transport against restored synthetic state.
4. Stop both local processes and remove their synthetic files. Record commands, expected/actual results and cleanup in private release evidence.

For the real provider, obtain its supported snapshot/restore procedure and access policy separately. Encrypt and limit access to backups, define retention and deletion handling, and test a restore into a separate protected database with outbound delivery disabled. Restoring a pre-deletion backup can recreate removed users, opt-ins or files: reconcile subsequent deletions before enabling traffic. A generic RDB rehearsal is not proof of a managed provider's recovery guarantees.

## Deployment sequence

1. Record the reviewed commit and the current approved deployment identifier in private release records. Confirm backup readiness, production-only secret scopes and the platform runtime configuration. The reviewed current function limit is 300 seconds with 2048 MiB; processing leases are 600 seconds and depend on that runtime being shorter.
2. Build the reviewed source with the runtime hash lock selected through `requirements.txt` (tool settings live in dedicated configuration files). Validate an isolated preview without real bot/storage credentials. Verify normal poster quota rejection returns 429 and a simulated configured Redis failure returns 503 without rendering; absent storage configuration uses the bounded per-process fallback, not a shared quota. Verify `/`, `/poster`, `/omer-info`, `/upcoming-events`, `/privacy.html`, `/terms.html`, fonts and image assets.
3. Apply the approved production deployment and webhook/command configuration. Run an authorized private smoke check without logging personal content. Avoid live actions until this step is approved.
4. Ensure GitHub Actions is the sole reminder scheduler. Source removes Vercel cron jobs, but the currently deployed Vercel schedule stays until rollout. Do not leave both active. Confirm the three workflows' shared secret/origin and runtime guards. Schedules can be delayed, skipped or retried; Telegram ambiguous timeouts cannot promise exactly-once delivery.
5. Verify export/delete confirmation and opt-out behavior using a dedicated consenting test account, then delete that account's test data. Retain only redacted health and validation evidence.

## Rollback

Pause GitHub reminder workflows first and prevent duplicate scheduling. Revert traffic to the last reviewed compatible deployment using the provider's deployment rollback facility. Do not blindly restore an older revision with the removed media/authentication defects. If no safe compatible revision exists, keep the affected route unavailable while preparing a fix.

Keep existing Redis state intact unless data recovery is specifically required. Do not flush Redis or restore a backup merely to roll back code. Verify compatibility with pending deletion proofs, anti-replay receipts, preferences and event IDs before resuming. Preserve deletion requests when recovery is required. Secrets may need rotation independently of rollback, and rolling back code does not undo provider configuration changes. Recheck webhook authentication, private synthetic poster generation, legal assets and one scheduler, then resume only after review.
