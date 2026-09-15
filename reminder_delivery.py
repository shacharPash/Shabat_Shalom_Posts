"""Shared bounded, authenticated reminder execution with owned delivery claims."""
import json
from datetime import datetime
from urllib.parse import parse_qs, urlparse
from bot_auth import authenticate_cron, send_json
from omer_utils import ISRAEL_TZ, omer_event_context
from redis_client import (acquire_claim, release_claim, complete_claim, claim_completed,
                          get_user_prefs, reminder_user_batch, was_omer_counted, EVENT_TTL)
from telegram_bot import user_processing


def run_reminders(handler, secret, kind, send, eligible=None):
    if not authenticate_cron(handler, secret):
        return
    counts = {'attempted': 0, 'sent': 0, 'failed': 0, 'skipped': 0}
    try:
        query = parse_qs(urlparse(handler.path).query)
        # A manually targeted request uses the same auth, consent and time guards.
        target = query.get('test_user_id', [None])[0]
        if target is not None and (not target.isdigit() or int(target) <= 0):
            send_json(handler, 400, {'error': 'invalid request'})
            return
        now = datetime.now(ISRAEL_TZ)
        context = omer_event_context(now) if kind != 'shabbat' else {'now': now, 'event_id': now.date().isoformat()}
        is_eligible = eligible(now) if kind == 'shabbat' else context['day'] is not None
        if kind == 'evening':
            is_eligible = is_eligible and context['evening_eligible']
        if kind == 'morning':
            is_eligible = is_eligible and 6 <= now.hour < 12
        if not is_eligible:
            response = {'status': 'skipped', 'reason': 'outside_delivery_window', 'cursor': '0', **counts}
        else:
            field = 'shabbat_reminder_enabled' if kind == 'shabbat' else 'reminder_enabled'
            users, cursor = ([target], '0') if target else reminder_user_batch(field, query.get('cursor', ['0'])[0])
            for user_id in users:
                key = f"zmunah:delivery:{user_id}:{kind}:{context['event_id']}"
                token = None
                try:
                    with user_processing(user_id):
                        # Re-read after acquiring the lock, including for test mode.
                        if get_user_prefs(user_id).get(field) is not True:
                            counts['skipped'] += 1
                            continue
                        if kind == 'morning' and (was_omer_counted(user_id, context['event_id']) or was_omer_counted(user_id, context['day'])):
                            counts['skipped'] += 1
                            continue
                        token = acquire_claim(key)
                        if token is None:
                            if not claim_completed(key):
                                raise RuntimeError('delivery busy')
                            counts['skipped'] += 1
                            continue
                        counts['attempted'] += 1
                        if not send(user_id, context):
                            raise RuntimeError('delivery failed')
                        if not complete_claim(key, token, EVENT_TTL):
                            raise RuntimeError('delivery lease expired')
                        counts['sent'] += 1
                except Exception:
                    counts['failed'] += 1
                    if token:
                        release_claim(key, token)
            response = {'status': 'partial_failure' if counts['failed'] else 'completed', 'cursor': cursor, **counts}
        print(json.dumps({'event': 'reminder_summary', 'kind': kind, **response}))
        send_json(handler, 503 if counts['failed'] else 200, response)
    except Exception:
        print(json.dumps({'event': 'reminder_summary', 'kind': kind, 'status': 'failed', **counts}))
        send_json(handler, 503, {'error': 'unavailable', **counts})
