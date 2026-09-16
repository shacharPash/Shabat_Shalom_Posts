"""Exercise the deployed poster quota boundary without external connections."""
import io
from unittest.mock import Mock

import pytest

from api import poster
import rate_limiter as limits
import redis_client as storage


@pytest.fixture(autouse=True)
def clean_quota(monkeypatch):
    limits._memory_store.clear()
    monkeypatch.setattr(storage, '_redis_client', None)
    monkeypatch.setattr(poster, '_rate_limiter', limits.RateLimiter(10, 60))
    yield
    limits._memory_store.clear()


def invoke(ip='203.0.113.9'):
    handler = poster.handler.__new__(poster.handler)
    handler.headers = {'Content-Length': '2', 'X-Forwarded-For': ip}
    handler.client_address = ('127.0.0.1', 1)
    handler.rfile = io.BytesIO(b'{}')
    handler.wfile = io.BytesIO()
    handler.send_response = Mock()
    handler.send_header = Mock()
    handler.end_headers = Mock()
    handler.do_POST()
    return handler.send_response.call_args.args[0], handler.wfile.getvalue()


def test_configured_pipeline_outage_never_renders_and_recovers(monkeypatch):
    client = Mock()
    client.pipeline.return_value.execute.side_effect = RuntimeError('sensitive-url')
    monkeypatch.setattr(poster._rate_limiter, '_get_client', lambda: client)
    render = Mock(return_value=b'poster')
    monkeypatch.setattr(poster, 'build_poster_from_payload', render)
    results = [invoke() for _ in range(11)]
    assert [status for status, _ in results] == [503] * 11
    assert all(b'sensitive-url' not in body and b'203.0.113.9' not in body for _, body in results)
    render.assert_not_called()
    client.pipeline.return_value.execute.side_effect = None
    client.pipeline.return_value.execute.return_value = [1, True]
    assert invoke()[0] == 200
    assert render.call_count == 1


def test_configured_client_creation_error_is_not_local_mode(monkeypatch):
    monkeypatch.setenv('REDIS_URL', 'redis://synthetic.invalid')
    monkeypatch.setattr(storage, 'get_redis_client', Mock(side_effect=ValueError('sensitive-url')))
    render = Mock(return_value=b'poster')
    monkeypatch.setattr(poster, 'build_poster_from_payload', render)
    assert invoke()[0] == 503
    render.assert_not_called()
    assert not limits._memory_store


def test_healthy_redis_enforces_quota_before_render(monkeypatch):
    client = Mock()
    client.pipeline.return_value.execute.side_effect = [[count, True] for count in range(1, 12)]
    monkeypatch.setattr(poster._rate_limiter, '_get_client', lambda: client)
    render = Mock(return_value=b'poster')
    monkeypatch.setattr(poster, 'build_poster_from_payload', render)
    assert [invoke()[0] for _ in range(11)] == [200] * 10 + [429]
    assert render.call_count == 10


def test_absent_configuration_keeps_local_quota(monkeypatch):
    render = Mock(return_value=b'poster')
    monkeypatch.setattr(poster, 'build_poster_from_payload', render)
    assert [invoke()[0] for _ in range(11)] == [200] * 10 + [429]
    assert render.call_count == 10


def test_local_capacity_does_not_evict_active_quota_and_reclaims_expired(monkeypatch):
    monkeypatch.setattr(limits, 'MAX_MEMORY_IDENTIFIERS', 2, raising=False)
    monkeypatch.setattr(limits.time, 'time', lambda: 1000)
    monkeypatch.setattr(poster, 'build_poster_from_payload', Mock(return_value=b'poster'))
    assert [invoke('203.0.113.1')[0] for _ in range(10)] == [200] * 10
    assert invoke('203.0.113.2')[0] == 200
    assert [invoke(f'198.51.100.{i}')[0] for i in range(100)] == [503] * 100
    assert len(limits._memory_store) == 2
    assert invoke('203.0.113.1')[0] == 429
    monkeypatch.setattr(limits.time, 'time', lambda: 1060)
    assert invoke('203.0.113.3')[0] == 200
    assert len(limits._memory_store) == 1
