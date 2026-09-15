"""Fail-closed authentication shared by administrative HTTP handlers."""
import hmac
import json


def send_json(handler, status, payload):
    body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
    handler.send_response(status)
    handler.send_header('Content-Type', 'application/json; charset=utf-8')
    handler.send_header('Cache-Control', 'no-store')
    handler.send_header('Content-Length', str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def authenticate_cron(handler, secret):
    provided = handler.headers.get('Authorization')
    if not secret or not isinstance(provided, str) or not hmac.compare_digest(
            provided.encode(), ('Bearer ' + secret).encode()):
        send_json(handler, 503 if not secret else 403, {'error': 'unavailable' if not secret else 'forbidden'})
        return False
    return True
