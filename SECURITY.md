# Security and private reports

Maintainer: [personal GitHub profile](https://github.com/shacharPash). A direct private reporting channel is a release prerequisite and has not yet been selected. Do not put vulnerabilities, secrets, user identifiers, images or exported data in public issues. General contact can use the profile; request a private channel before providing details. No guaranteed response time is promised for this personal beta.

## Boundaries

Public media routes reject external URLs, local paths, unsupported formats, oversized bodies and unsafe image geometry. Upload temporary files are removed in `finally`; abrupt runtime termination depends on the hosting platform's cleanup. Generated responses request private/no-store caching. The private Telegram webhook requires a matching registration secret; reminder/setup endpoints require their separate bearer secret. Redis is retained as the bot preference store.

Keep production credentials out of local tests and previews. Use a disposable Redis instance for tests. Never paste secret values into logs, reports, commands shared with others or source control. Deployment configuration is not inferred from source: verify production-only secret scopes, old preview retirement, webhook secret match, actual Redis security/backups and the region before release.

## Incident response

Pause the single reminder scheduler if deliveries or data integrity are affected. Restrict public access when needed, preserve minimal access-controlled evidence without copying user content into tickets, and revoke or rotate the affected credential through its provider. Updating webhook secrets also requires updating webhook registration. Coordinate any notification through the confirmed private contact channel and applicable provider process. Restore only into isolated state first; account for deletion requests since a backup and do not automatically replay old opt-ins. See [the operations guide](docs/RELEASE.md).

Local automated validation is not a certification of security or legal compliance.
