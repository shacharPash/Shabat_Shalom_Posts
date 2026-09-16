"""Bounded GitHub Actions reminder pagination. Logs only aggregate counts/cursors."""
import json
import os
import re
import uuid
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

MAX_PAGES = 100
MAX_SECONDS = 1500


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise RuntimeError('unexpected redirect')


def main():
    base = os.environ['VERCEL_URL'].rstrip('/')
    parsed = urllib.parse.urlparse(base)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError('invalid deployment URL')
    endpoint = os.environ['REMINDER_ENDPOINT']
    if endpoint not in ('shabbat_reminder', 'omer_reminder', 'omer_morning_reminder'):
        raise ValueError('invalid endpoint')
    secret = os.environ['CRON_SECRET']
    if not secret:
        raise ValueError('missing secret')
    opener = urllib.request.build_opener(NoRedirect())
    cursor = os.environ.get('RESUME_CURSOR') or '0'
    restart = os.environ.get('RESTART_TRAVERSAL', '').lower() == 'true'
    if restart:
        if cursor != '0':
            raise ValueError('choose resume or restart, not both')
        # Generated once; all retries keep the same fresh traversal identity.
        cursor = 'r.' + uuid.uuid4().hex
    if not re.fullmatch(r'(?:0|[0-9a-f]{32}|r\.[0-9a-f]{32})', cursor):
        raise ValueError('invalid resume cursor')
    started = time.monotonic()
    for page in range(MAX_PAGES):
        url = base + '/api/' + endpoint + '?' + urllib.parse.urlencode({'cursor': cursor})
        for attempt in range(3):
            if time.monotonic() - started > MAX_SECONDS:
                raise RuntimeError('time cap reached')
            request = urllib.request.Request(url, headers={'Authorization': 'Bearer ' + secret})
            try:
                with opener.open(request, timeout=240) as response:
                    body = response.read(65537)
                    if len(body) > 65536:
                        raise RuntimeError('response too large')
                    result = json.loads(body)
                if result.get('failed', 0) or result.get('status') not in ('completed', 'skipped'):
                    raise RuntimeError('reminder page failed')
                break
            except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, RuntimeError):
                if attempt == 2:
                    print(json.dumps({'status': 'failed', 'page': page, 'resume_cursor': cursor}))
                    return 1
                time.sleep(5 * (attempt + 1))
        print(json.dumps({k: result.get(k) for k in ('status', 'reason', 'attempted', 'sent', 'failed', 'skipped', 'cursor')}))
        cursor = result['cursor']
        if not isinstance(cursor, str) or not re.fullmatch(r'(?:0|[0-9a-f]{32})', cursor):
            raise RuntimeError('invalid continuation')
        if cursor == '0':
            return 0
    print(json.dumps({'status': 'batch_cap_reached', 'resume_cursor': cursor}))
    return 1


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception:
        print('{"status":"failed","reason":"scheduler_request_failed"}')
        sys.exit(1)
