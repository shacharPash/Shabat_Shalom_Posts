"""Offline security and real isolated Redis regressions. No service credentials."""
import importlib
import io
import json
import os
import shutil
import socket
import subprocess
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

import pytest
import redis
# Strip service credentials even when the external audit harness is absent in CI.
for secret_name in ('TELEGRAM_BOT_TOKEN', 'TELEGRAM_WEBHOOK_SECRET', 'CRON_SECRET', 'REDIS_URL', 'KV_URL'):
    os.environ.pop(secret_name, None)
try:
    import sitecustomize as _audit_harness
except ImportError:
    _audit_harness = None
_original_socket_connect = getattr(_audit_harness, '_original_connect', socket.socket.connect)

import redis_client as storage
import telegram_bot as bot


@pytest.fixture(autouse=True)
def no_external_connections():
    def reject(sock, address):
        raise OSError('Bot tests block network connections')
    with patch.object(socket.socket, 'connect', reject):
        yield


@pytest.fixture
def isolated_redis():
    executable = shutil.which('redis-server')
    assert executable, 'redis-server is required for critical concurrency tests'
    with tempfile.TemporaryDirectory(prefix='shabat-redis-', dir=os.path.realpath('/tmp')) as folder:
        path = folder + '/redis.sock'
        process = subprocess.Popen([executable, '--port', '0', '--unixsocket', path,
                                    '--unixsocketperm', '700', '--save', '',
                                    '--appendonly', 'no', '--dir', folder],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        previous_connect = socket.socket.connect
        # Audit harness remains installed. Permit only this fixture-owned Unix socket.
        original_connect = _original_socket_connect
        def connect(sock, address):
            if sock.family == socket.AF_UNIX and address == path:
                return original_connect(sock, address)
            return previous_connect(sock, address)
        try:
            with patch.object(socket.socket, 'connect', connect):
                # Probe with an explicitly closed socket before constructing the
                # client. redis-py 5 can leak sockets on failed startup connects.
                for _ in range(100):
                    try:
                        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as probe:
                            probe.settimeout(.1)
                            probe.connect(path)
                        break
                    except OSError:
                        if process.poll() is not None:
                            pytest.fail('isolated Redis exited during startup')
                        time.sleep(.02)
                else:
                    pytest.fail('isolated Redis failed to start')
                client = redis.Redis(unix_socket_path=path, decode_responses=True,
                                     socket_timeout=2, socket_connect_timeout=2)
                try:
                    assert client.ping()
                    with patch.object(storage, '_redis_client', client):
                        yield client
                finally:
                    client.close()
        finally:
            process.terminate()
            process.wait(timeout=5)
            process.stderr.close()


def request_handler(module, path='/', headers=None, body=None):
    h = module.handler.__new__(module.handler)
    h.path = path
    h.headers = headers or {}
    h.wfile = io.BytesIO()
    h.rfile = io.BytesIO(body or b'')
    h.client_address = ('127.0.0.1', 1)
    h.send_response = Mock()
    h.send_header = Mock()
    h.end_headers = Mock()
    return h


@pytest.mark.parametrize('name', ['shabbat_reminder', 'omer_reminder', 'omer_morning_reminder', 'setup_commands'])
@pytest.mark.parametrize('secret,provided', [(None, None), ('expected', None), ('expected', 'Bearer wrong')])
def test_all_cron_handlers_fail_closed_even_test_mode(name, secret, provided):
    module = importlib.import_module('api.' + name)
    with patch.dict(os.environ, {}, clear=True), patch.object(module, 'CRON_SECRET', secret, create=True):
        h = request_handler(module, '/?test_user_id=123&omer_day=1', {'Authorization': provided})
        h.do_GET()
    assert h.send_response.call_args.args[0] in (401, 403, 503)
    assert not any(word in h.wfile.getvalue() for word in (b'123', b'expected'))


def test_defaults_and_two_user_isolation(isolated_redis):
    first = storage.get_user_prefs('1')
    first['cities'][0]['name'] = 'changed'
    assert storage.get_user_prefs('2')['cities'][0]['name'] != 'changed'
    assert storage.DEFAULT_PREFERENCES['cities'][0]['name'] != 'changed'


def test_interleaved_edits_preserve_opt_out(isolated_redis):
    storage.set_user_prefs('1', {'reminder_enabled': True, 'legacy_custom': 'preserved'})
    stale = storage.get_user_prefs('1')
    storage.update_user_prefs('1', {'reminder_enabled': False})
    storage.update_user_prefs('1', {'blessing_text': 'new'})
    assert stale['reminder_enabled'] is True
    assert storage.get_user_prefs('1')['reminder_enabled'] is False
    assert storage.get_user_prefs('1')['legacy_custom'] == 'preserved'


def test_real_concurrent_mutations_and_owned_claims(isolated_redis):
    def increment(_):
        storage.mutate_user_prefs('1', lambda p: p.update(counter=p.get('counter', 0) + 1))
    with ThreadPoolExecutor(max_workers=6) as pool:
        list(pool.map(increment, range(30)))
    assert storage.get_user_prefs('1')['counter'] == 30
    key = 'zmunah:delivery:1:evening:test'
    with ThreadPoolExecutor(max_workers=8) as pool:
        tokens = list(pool.map(lambda _: storage.acquire_claim(key), range(8)))
    assert sum(token is not None for token in tokens) == 1
    token = next(t for t in tokens if t)
    assert 0 < isolated_redis.ttl(key) <= 600
    assert not storage.release_claim(key, 'wrong-owner')
    assert not storage.complete_claim(key, 'wrong-owner')
    assert storage.release_claim(key, token)
    replacement = storage.acquire_claim(key)
    assert replacement != token
    assert not storage.release_claim(key, token)
    assert storage.complete_claim(key, replacement)
    assert storage.acquire_claim(key) is None
    assert isolated_redis.get(key + ':done') == '1'


def private_update(update_id=1, user=123, text='/settings'):
    return {'update_id': update_id, 'message': {'from': {'id': user},
            'chat': {'id': user, 'type': 'private'}, 'text': text}}


def test_private_binding_replay_and_retry(isolated_redis):
    with patch.object(bot, 'handle_settings') as action:
        update = private_update()
        bot.process_update(update)
        bot.process_update(update)
        assert action.call_count == 1
        group = private_update(2)
        group['message']['chat']['type'] = 'group'
        bot.process_update(group)
        mismatch = private_update(3)
        mismatch['message']['chat']['id'] = 456
        bot.process_update(mismatch)
        assert action.call_count == 1
    with patch.object(bot, 'handle_settings', side_effect=[RuntimeError('transient'), None]) as action:
        with pytest.raises(RuntimeError):
            bot.process_update(private_update(4))
        bot.process_update(private_update(4))
        assert action.call_count == 2


@pytest.mark.parametrize('value', [[], None, {'update_id': 'bad'}, {'update_id': 1, 'message': []}])
def test_malformed_updates_rejected(value):
    with pytest.raises(ValueError):
        bot.process_update(value)


def test_webhook_transient_is_retryable():
    module = importlib.import_module('api.telegram_webhook')
    body = json.dumps(private_update()).encode()
    with patch.object(module, 'TELEGRAM_WEBHOOK_SECRET', 'test'), patch.object(module, 'process_update', side_effect=RuntimeError('sensitive')):
        h = request_handler(module, headers={'Content-Length': str(len(body)), 'X-Telegram-Bot-Api-Secret-Token': 'test'}, body=body)
        h.do_POST()
    assert h.send_response.call_args.args[0] == 503
    assert b'sensitive' not in h.wfile.getvalue()


def test_omer_context_first_last_night_and_overnight_identity():
    import omer_utils as o
    first_day = o._find_omer_start_for_year(2026)
    for day in (1, 49):
        evening = first_day + timedelta(days=day - 2)
        nightfall = o._get_jerusalem_tzet_datetime(evening)
        assert nightfall is not None
        before = o.omer_event_context(nightfall - timedelta(seconds=1))
        after = o.omer_event_context(nightfall + timedelta(seconds=1))
        morning = o.omer_event_context(o.ISRAEL_TZ.localize(datetime.combine(evening + timedelta(days=1), datetime.min.time()).replace(hour=9)))
        assert not before['evening_eligible']
        assert after['day'] == day
        assert after['date'] == evening + timedelta(days=1)
        assert after['event_id'] == morning['event_id']
        assert after['evening_eligible']
        assert not morning['evening_eligible']
    assert o.omer_event_context(o._get_jerusalem_tzet_datetime(first_day + timedelta(days=48)) + timedelta(seconds=1))['day'] is None


def test_context_timezone_and_missing_nightfall():
    import omer_utils as o
    for moment in [datetime(2026,3,27,22), datetime(2026,10,25,22)]:
        local=o.ISRAEL_TZ.localize(moment)
        assert o.omer_event_context(local) == o.omer_event_context(local.astimezone(__import__('datetime').timezone.utc))
    with patch.object(o, '_get_jerusalem_tzet_datetime', return_value=None):
        with pytest.raises(ValueError):
            o.omer_event_context(o.ISRAEL_TZ.localize(datetime(2026,4,2,22)))


def test_delete_preserves_other_user_and_legacy_keys(isolated_redis):
    for uid in ['12', '123']:
        storage.set_user_prefs(uid, {'reminder_enabled': True})
        for key in [f'zmunah:state:{uid}', f'zmunah:omer_sent:2026-04-03:{uid}',
                    f'zmunah:omer_counted:{uid}:1', f'zmunah:delivery:{uid}:evening:x:done',
                    f'zmunah:privacy:{uid}:delete']:
            isolated_redis.set(key, '1')
    exported = storage.export_user_data('12')
    assert not any('123' in key for key in exported)
    storage.delete_user_data('12')
    assert not any(isolated_redis.exists(k) for k in storage.user_data_keys('12'))
    assert isolated_redis.exists('zmunah:user:123')
    assert isolated_redis.exists('zmunah:omer_sent:2026-04-03:123')


def callback_update(data, update_id=10, user=123):
    return {'update_id': update_id, 'callback_query': {'id':'cb', 'from':{'id':user}, 'data':data,
        'message':{'message_id':1, 'from':{'id':999}, 'chat':{'id':user,'type':'private'}}}}


def test_confirm_delete_cleans_flow_and_cannot_delete_reenrollment(isolated_redis):
    storage.update_user_prefs('123', {'reminder_enabled':True})
    with patch.object(bot, 'send_message_with_keyboard') as prompt, patch.object(bot,'answer_callback_query'), patch.object(bot,'send_message'):
        bot.process_update(private_update(1,text='/delete_my_data'))
        assert storage.get_user_prefs('123')['reminder_enabled']
        data=prompt.call_args.args[2][0][0]['callback_data']
        bot.process_update(callback_update(data))
        assert not any(isolated_redis.exists(k) for k in storage.user_data_keys('123'))
        storage.update_user_prefs('123', {'reminder_enabled':True})
        bot.process_update(callback_update(data))
        assert storage.get_user_prefs('123')['reminder_enabled']


def test_stale_or_forged_count_callback_does_not_mark_today(isolated_redis):
    import omer_utils as o
    context=o.omer_event_context(o.ISRAEL_TZ.localize(datetime(2026,4,3,22)))
    with patch.object(bot, 'omer_event_context', return_value=context), patch.object(bot,'answer_callback_query'), patch.object(bot,'send_message'):
        for i,data in enumerate(['omer:mark_counted','omer:mark_counted:2','omer:count:2026-04-01:1','omer:count:2026-04-04:49']):
            bot.process_update(callback_update(data,20+i))
        assert not storage.was_omer_counted('123', context['event_id'])
        bot.process_update(callback_update(f"omer:count:{context['event_id']}:{context['day']}",30))
        assert storage.was_omer_counted('123', context['event_id'])


def test_retry_does_not_repeat_toggle(isolated_redis):
    storage.update_user_prefs('123', {'reminder_enabled':True})
    with patch.object(bot,'send_message',side_effect=[RuntimeError('retry'), {'ok':True}]):
        with pytest.raises(RuntimeError):
            bot.process_update(private_update(72,text='/reminder'))
        assert storage.get_user_prefs('123')['reminder_enabled'] is False
        bot.process_update(private_update(72,text='/reminder'))
        assert storage.get_user_prefs('123')['reminder_enabled'] is False


def test_authenticated_batches_claim_retry_optout_and_morning_count(isolated_redis):
    import reminder_delivery as delivery
    import omer_utils as o
    module=importlib.import_module('api.omer_reminder')
    now=o.ISRAEL_TZ.localize(datetime(2026,4,3,22))
    clock=Mock();clock.now.return_value=now
    for uid in ('1','2','3'):
        storage.update_user_prefs(uid, {'reminder_enabled':True})
    with patch.object(delivery,'datetime',clock), patch.object(module,'CRON_SECRET','test'), patch.object(module,'send_omer_reminder',return_value=True) as send:
        cursor='0'
        for _ in range(10):
            h=request_handler(module,'/?cursor='+cursor,{'Authorization':'Bearer test'});h.do_GET()
            result=json.loads(h.wfile.getvalue())
            assert result['attempted'] <= 2
            cursor=result['cursor']
            if cursor=='0':break
        else:pytest.fail('batch did not terminate')
        assert send.call_count==3
        h=request_handler(module,'/?test_user_id=1',{'Authorization':'Bearer test'});h.do_GET()
        assert json.loads(h.wfile.getvalue())['skipped']==1
        assert send.call_count==3
        storage.update_user_prefs('4', {'reminder_enabled':False})
        h=request_handler(module,'/?test_user_id=4',{'Authorization':'Bearer test'});h.do_GET()
        assert send.call_count==3
        storage.update_user_prefs('5', {'reminder_enabled':True})
        send.side_effect=[False, True]
        h=request_handler(module,'/?test_user_id=5',{'Authorization':'Bearer test'});h.do_GET()
        assert h.send_response.call_args.args[0]==503
        h=request_handler(module,'/?test_user_id=5',{'Authorization':'Bearer test'});h.do_GET()
        assert json.loads(h.wfile.getvalue())['sent']==1
    morning=importlib.import_module('api.omer_morning_reminder')
    clock.now.return_value=o.ISRAEL_TZ.localize(datetime(2026,4,4,9))
    storage.mark_omer_counted('1','2026-04-04')
    with patch.object(delivery,'datetime',clock), patch.object(morning,'CRON_SECRET','test'), patch.object(morning,'send_morning_reminder',return_value=True) as send:
        h=request_handler(morning,'/?test_user_id=1',{'Authorization':'Bearer test'});h.do_GET()
        assert json.loads(h.wfile.getvalue())['skipped']==1
        send.assert_not_called()


def test_text_image_share_one_event_and_date(isolated_redis):
    import omer_utils as o
    module=importlib.import_module('api.omer_reminder')
    context=o.omer_event_context(o.ISRAEL_TZ.localize(datetime(2026,4,2,22)))
    with patch.object(module,'send_message_with_keyboard',return_value={'ok':True}) as text, patch.object(module,'send_photo_with_keyboard',return_value={'ok':True}) as photo, patch.object(module,'build_poster_from_payload',return_value=b'image') as build:
        assert module._send_text_reminder(123,'sefard',context)
        assert module._send_image_reminder(123,{},'sefard',context)
        payload=build.call_args.args[0]
        assert payload['omerDay']==context['day']==1
        assert payload['omerDate']==context['date'].isoformat()
        assert text.call_args.args[2]==photo.call_args.args[3]
        assert f"יום {context['day']}" in text.call_args.args[1]


def test_export_is_private_document_and_flow_is_removed(isolated_redis):
    storage.update_user_prefs('123', {'blessing_text':'mine'})
    storage.update_user_prefs('456', {'blessing_text':'other'})
    response=Mock();response.json.return_value={'ok':True};response.__enter__=Mock(return_value=response);response.__exit__=Mock(return_value=False)
    with patch.object(bot,'send_message_with_keyboard') as prompt, patch.object(bot.requests,'post',return_value=response) as post:
        bot.process_update(private_update(81,text='/export'))
        post.assert_not_called()
        data=prompt.call_args.args[2][0][0]['callback_data']
        bot.process_update(callback_update(data,82))
        exported=post.call_args.kwargs['files']['document'][1]
        assert b'mine' in exported and b'other' not in exported
        assert post.call_args.kwargs['data']['chat_id']==123
        assert not list(isolated_redis.scan_iter(match='zmunah:privacy:123:*'))
        assert list(isolated_redis.scan_iter(match='zmunah:delivery:123:*')) == ['zmunah:delivery:123:rate']
        assert 0 < isolated_redis.ttl('zmunah:delivery:123:rate') <= 60
        assert b':rate' not in exported


def test_download_stream_limit_and_response_cleanup():
    from media_validation import MAX_IMAGE_BYTES
    metadata=Mock();metadata.json.return_value={'ok':True,'result':{'file_path':'photos/safe.jpg'}}
    stream=Mock();stream.status_code=200;stream.headers={};stream.iter_content.return_value=iter([b'x'*MAX_IMAGE_BYTES,b'x'])
    for response in [metadata,stream]:
        response.__enter__=Mock(return_value=response);response.__exit__=Mock(return_value=False)
    with patch.object(bot.requests,'get',side_effect=[metadata,stream]):
        with pytest.raises(ValueError,match='too large'):
            bot.download_photo('test')
    metadata.__exit__.assert_called_once();stream.__exit__.assert_called_once()


def test_evening_schedule_after_nightfall_range():
    import omer_utils as o
    for year in range(2024,2031):
        first=o._find_omer_start_for_year(year)
        for index in range(49):
            evening=first+timedelta(days=index-1)
            nightfall=o._get_jerusalem_tzet_datetime(evening)
            assert nightfall is not None
            assert nightfall.hour*60+nightfall.minute < 21*60


def test_calendar_interface_midnight_identity_and_late_skip():
    import omer_utils as o
    night=o.omer_event_context(o.ISRAEL_TZ.localize(datetime(2026,4,2,23,59)))
    midnight=o.omer_event_context(o.ISRAEL_TZ.localize(datetime(2026,4,3,0)))
    assert night['event_id']==midnight['event_id']=='2026-04-03'
    assert night['day']==midnight['day']==1
    assert night['evening_eligible'] and not midnight['evening_eligible']
    with patch.object(o,'get_jerusalem_alos',side_effect=AssertionError('unsupported JewCal key')):
        assert o.omer_event_context(night['now'])['day']==1


def test_storage_outage_prevents_processing_and_delivery():
    with (patch.object(storage,'get_redis_client',side_effect=redis.ConnectionError('sensitive-url')),
          patch.object(bot,'handle_settings') as action):
        with pytest.raises(redis.ConnectionError):
            bot.process_update(private_update())
        action.assert_not_called()


def test_actual_lease_expiry_cannot_release_new_owner(isolated_redis):
    key='zmunah:delivery:1:expiry'
    old=storage.acquire_claim(key,ttl=1)
    time.sleep(1.1)
    new=storage.acquire_claim(key)
    assert new and new!=old
    assert not storage.release_claim(key,old)
    assert not storage.complete_claim(key,old)
    assert isolated_redis.get(key)==new


def test_missing_or_group_callback_cannot_reach_preferences(isolated_redis):
    with patch.object(bot,'handle_callback_query') as action:
        forged=callback_update('toggle:reminder')
        forged['callback_query']['message']['chat']['id']=456
        bot.process_update(forged)
        forged=callback_update('toggle:reminder',11)
        forged['callback_query']['message']['chat']['type']='supergroup'
        bot.process_update(forged)
        action.assert_not_called()
        assert list(isolated_redis.scan_iter())==[]


def test_two_concurrent_updates_same_user_do_not_double_dispatch(isolated_redis):
    from threading import Event
    entered, finish=Event(),Event()
    def action(update):
        entered.set()
        assert finish.wait(5)
    with patch.object(bot,'handle_settings',side_effect=action) as handler:
        with ThreadPoolExecutor(max_workers=2) as pool:
            first=pool.submit(bot.process_update,private_update())
            assert entered.wait(5)
            try:
                with pytest.raises(RuntimeError,match='busy'):
                    bot.process_update(private_update())
            finally:
                finish.set()
            first.result()
        bot.process_update(private_update())
        assert handler.call_count==1


def test_shabbat_duplicate_and_late_evening_skip(isolated_redis):
    import reminder_delivery as delivery
    import omer_utils as o
    shabbat=importlib.import_module('api.shabbat_reminder')
    storage.update_user_prefs('123',{'shabbat_reminder_enabled':True,'reminder_enabled':True})
    clock=Mock();clock.now.return_value=o.ISRAEL_TZ.localize(datetime(2026,4,3,8))
    with patch.object(delivery,'datetime',clock), patch.object(shabbat,'CRON_SECRET','test'), patch.object(shabbat,'send_shabbat_reminder',return_value=True) as send:
        for _ in range(2):
            h=request_handler(shabbat,'/?test_user_id=123',{'Authorization':'Bearer test'});h.do_GET()
            assert h.send_response.call_args.args[0]==200
        send.assert_called_once()
    evening=importlib.import_module('api.omer_reminder')
    clock.now.return_value=o.ISRAEL_TZ.localize(datetime(2026,4,4,0,30))
    with patch.object(delivery,'datetime',clock), patch.object(evening,'CRON_SECRET','test'), patch.object(evening,'send_omer_reminder') as send:
        h=request_handler(evening,'/?test_user_id=123',{'Authorization':'Bearer test'});h.do_GET()
        assert json.loads(h.wfile.getvalue())['reason']=='outside_delivery_window'
        send.assert_not_called()


def test_bot_poster_and_keyboard_share_request_timestamp(isolated_redis):
    import omer_utils as o
    import api.poster
    now=o.ISRAEL_TZ.localize(datetime(2026,4,2,22))
    clock=Mock();clock.now.return_value=now
    with patch.object(bot,'datetime',clock), patch.object(api.poster,'build_poster_from_payload',return_value=b'poster') as build, patch.object(bot,'send_message'), patch.object(bot,'send_photo_with_keyboard') as send:
        bot.process_update(private_update(200,text='/omer'))
        payload=build.call_args.args[0]
        assert payload['omerDay']==1
        assert payload['omerDate']=='2026-04-03'
        assert send.call_args.args[3][0][0]['callback_data']=='omer:count:2026-04-03:1'


def test_morning_status_honors_event_count(isolated_redis):
    import omer_utils as o
    context=o.omer_event_context(o.ISRAEL_TZ.localize(datetime(2026,4,3,9)))
    storage.mark_omer_counted('123',context['event_id'])
    with patch.object(bot,'omer_event_context',return_value=context):
        assert bot.get_omer_counting_status('123')['status']=='counted_last_night'


def test_scheduler_fails_on_unresolved_page_and_bounds_pagination():
    import importlib.util
    spec=importlib.util.spec_from_file_location('reminder_runner','.github/scripts/run_reminders.py')
    runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
    import urllib.error
    opener=Mock();opener.open.side_effect=urllib.error.HTTPError('https://example.test',503,'unavailable',{},None)
    with patch.dict(os.environ,{'VERCEL_URL':'https://example.test','CRON_SECRET':'test','REMINDER_ENDPOINT':'omer_reminder'}), patch.object(runner.urllib.request,'build_opener',return_value=opener), patch.object(runner.time,'sleep'):
        assert runner.main()==1
        assert opener.open.call_count==3
    response=Mock();response.__enter__=Mock(return_value=response);response.__exit__=Mock(return_value=False)
    response.read.return_value=json.dumps({'status':'completed','failed':0,'cursor':'a'*32}).encode()
    opener.open.side_effect=None;opener.open.return_value=response
    with patch.dict(os.environ,{'VERCEL_URL':'https://example.test','CRON_SECRET':'test','REMINDER_ENDPOINT':'omer_reminder'}), patch.object(runner.urllib.request,'build_opener',return_value=opener), patch.object(runner,'MAX_PAGES',2):
        assert runner.main()==1


def test_download_stops_slow_stream_and_closes():
    metadata=Mock();metadata.json.return_value={'ok':True,'result':{'file_path':'photos/safe.jpg'}}
    stream=Mock();stream.status_code=200;stream.headers={};stream.iter_content.return_value=iter([b'x', b'y'])
    for response in [metadata,stream]:
        response.__enter__=Mock(return_value=response);response.__exit__=Mock(return_value=False)
    with patch.object(bot.requests,'get',side_effect=[metadata,stream]), patch('time.monotonic',side_effect=[0,31]):
        with pytest.raises(bot.TelegramDeliveryError, match='download'):
            bot.download_photo('test')
    stream.__exit__.assert_called_once()


def test_sparse_subscribers_have_bounded_scan_work(isolated_redis):
    keys=[f'zmunah:user:{i}' for i in range(100)]
    with patch.object(isolated_redis,'scan',return_value=(0,keys)), patch.object(storage,'get_user_prefs',return_value={}) as get:
        users,cursor=storage.reminder_user_batch('reminder_enabled')
        assert users==[] and len(cursor)==32
        assert get.call_count<=2


def test_partial_failure_preserves_success_receipt(isolated_redis):
    import reminder_delivery as delivery
    import omer_utils as o
    module=importlib.import_module('api.omer_reminder')
    clock=Mock();clock.now.return_value=o.ISRAEL_TZ.localize(datetime(2026,4,3,22))
    for uid in ['1','2']:
        storage.update_user_prefs(uid,{'reminder_enabled':True})
    with patch.object(delivery,'datetime',clock), patch.object(module,'CRON_SECRET','test'), patch.object(module,'send_omer_reminder',side_effect=[True,False]) as send, patch.object(delivery,'reminder_user_batch',return_value=(['1','2'],'0')):
        h=request_handler(module,headers={'Authorization':'Bearer test'});h.do_GET()
        result=json.loads(h.wfile.getvalue())
        assert h.send_response.call_args.args[0]==503
        assert result['sent']==result['failed']==1 and result['attempted']==2
        assert isolated_redis.ttl('zmunah:delivery:1:evening:2026-04-04:done') in range(storage.EVENT_TTL-5,storage.EVENT_TTL+1)
        send.side_effect=[True]
        h=request_handler(module,headers={'Authorization':'Bearer test'});h.do_GET()
        result=json.loads(h.wfile.getvalue())
        assert result['sent']==result['skipped']==1
        assert send.call_count==3


@pytest.mark.parametrize('field', ['blessing','dedication'])
def test_bot_rejects_new_oversize_text_preserves_legacy_and_edit_state(isolated_redis,field):
    legacy='א'*501
    storage.update_user_prefs('123',{field+'_text':legacy})
    bot._set_user_state('123','editing_'+field)
    with patch.object(bot,'send_message') as message, patch.object(bot,'send_message_with_keyboard'):
        bot.process_update(private_update(300,text='ב'*501))
        assert storage.get_user_prefs('123')[field+'_text']==legacy
        assert bot._get_user_state('123')=='editing_'+field
        assert '500' in message.call_args.args[1]
        bot.process_update(private_update(301,text='ב'*500))
        assert storage.get_user_prefs('123')[field+'_text']=='ב'*500


def test_bot_rejects_thirteenth_city_and_can_repair_legacy_list(isolated_redis):
    names=list(bot.CITY_BY_NAME)[:14]
    cities=[{'name':name,'candle_offset':20} for name in names[:12]]
    storage.update_user_prefs('123',{'cities':cities})
    with patch.object(bot,'send_message') as message, patch.object(bot,'edit_message_keyboard_only'):
        bot.handle_city_toggle(123,1,'123',names[12])
        assert len(storage.get_user_prefs('123')['cities'])==12
        assert '12' in message.call_args.args[1]
        storage.update_user_prefs('123',{'cities':cities+[{'name':names[12],'candle_offset':20}]})
        bot.handle_city_toggle(123,1,'123',names[12])
        assert len(storage.get_user_prefs('123')['cities'])==12


def test_legacy_invalid_record_generation_explains_correction(isolated_redis):
    storage.update_user_prefs('123',{'blessing_text':'א'*501})
    with patch.object(bot,'send_message') as message, patch.object(bot,'send_photo_with_keyboard') as send:
        bot.process_update(private_update(305,text='/poster'))
        assert '500' in message.call_args.args[1] and '12' in message.call_args.args[1]
        assert storage.get_user_prefs('123')['blessing_text']=='א'*501
        send.assert_not_called()


def test_two_users_sharing_webhook_ip_have_separate_budget(isolated_redis):
    module=importlib.import_module('api.telegram_webhook')
    with patch.object(module,'TELEGRAM_WEBHOOK_SECRET','test'), patch.object(bot,'handle_settings') as action:
        def invoke(uid,index):
            body=json.dumps(private_update(index,uid)).encode()
            h=request_handler(module,headers={'X-Forwarded-For':'203.0.113.9','Content-Length':str(len(body)), 'X-Telegram-Bot-Api-Secret-Token':'test'},body=body)
            h.do_POST()
            return h.send_response.call_args.args[0]
        for index in range(30):
            assert invoke(123,400+index)==200
        assert invoke(123,430)==429
        assert invoke(456,431)==200
        assert invoke(123,400)==200  # Already completed replays consume no quota.
        assert action.call_count==31
    storage.delete_user_data('123')
    assert not any(isolated_redis.exists(key) for key in storage.user_data_keys('123'))


def test_predeletion_successful_update_replay_cannot_reenroll(isolated_redis):
    old=private_update(700,text='/reminder on')
    with patch.object(bot,'send_message') as send, patch.object(bot,'send_message_with_keyboard') as prompt:
        bot.process_update(old)
        assert storage.get_user_prefs('123')['reminder_enabled']
        bot.process_update(private_update(701,text='/delete_my_data'))
        confirmation=prompt.call_args.args[2][0][0]['callback_data']
        bot.process_update(callback_update(confirmation,702))
        assert not isolated_redis.exists('zmunah:user:123')
        count=send.call_count
        bot.process_update(old)
        assert not isolated_redis.exists('zmunah:user:123')
        assert not storage.get_user_prefs('123')['reminder_enabled']
        assert send.call_count==count


def test_whitespace_message_is_safely_ignored(isolated_redis):
    with patch.object(bot,'send_message') as send, patch.object(bot,'send_message_with_keyboard') as keyboard:
        bot.process_update(private_update(900,text='   '))
        send.assert_not_called()
        keyboard.assert_not_called()


def test_fixed_subscriber_traversal_survives_delivery_key_churn(isolated_redis):
    """Deterministically move live SCAN page boundaries as bookkeeping grows."""
    for uid in range(1, 7):
        storage.update_user_prefs(str(uid), {'reminder_enabled': True})
    calls = {0: 0, 7: 0}
    def scan(cursor, **kwargs):
        cursor = int(cursor)
        calls[cursor] += 1
        if cursor == 0:
            # The initial response overflows the two-recipient invocation limit.
            # Re-reading it under churn no longer includes its third candidate.
            names = ['1', '2', '3', '4'] if calls[0] == 1 else ['1', '2', '4']
            return 7, ['zmunah:user:' + uid for uid in names]
        return 0, ['zmunah:user:5', 'zmunah:user:6']
    seen = set()
    cursor = '0'
    with patch.object(isolated_redis, 'scan', side_effect=scan):
        for _ in range(12):
            users, cursor = storage.reminder_user_batch('reminder_enabled', cursor)
            for uid in users:
                key = f'zmunah:delivery:{uid}:evening:churn'
                token = storage.acquire_claim(key)
                if token:
                    storage.complete_claim(key, token, storage.EVENT_TTL)
                    seen.add(uid)
            if cursor == '0':
                break
    assert seen == {str(uid) for uid in range(1, 7)}
    assert calls[0] == calls[7] == 1


def test_failed_page_retries_same_recipients_under_scan_churn(isolated_redis):
    import reminder_delivery as delivery
    import omer_utils as o
    module = importlib.import_module('api.omer_reminder')
    for uid in ('1', '2', '3'):
        storage.update_user_prefs(uid, {'reminder_enabled': True})
    clock = Mock(); clock.now.return_value = o.ISRAEL_TZ.localize(datetime(2026, 4, 3, 22))
    responses = [(0, ['zmunah:user:1', 'zmunah:user:2']),
                 (0, ['zmunah:user:1', 'zmunah:user:3'])]
    delivered = []
    failed = False
    def send(uid, context):
        nonlocal failed
        if uid == '2' and not failed:
            failed = True
            return False
        delivered.append(uid)
        return True
    with patch.object(delivery, 'datetime', clock), patch.object(module, 'CRON_SECRET', 'test'), patch.object(module, 'send_omer_reminder', side_effect=send), patch.object(isolated_redis, 'scan', side_effect=responses):
        h = request_handler(module, headers={'Authorization': 'Bearer test'}); h.do_GET()
        assert h.send_response.call_args.args[0] == 503
        h = request_handler(module, headers={'Authorization': 'Bearer test'}); h.do_GET()
        assert h.send_response.call_args.args[0] == 200
    assert delivered == ['1', '2']


def test_confirmed_deletion_resumes_after_partial_failure_and_nonce_expiry(isolated_redis):
    for uid in ('12', '123'):
        storage.update_user_prefs(uid, {'reminder_enabled': True, 'blessing_text': 'preserve-until-deleted'})
        isolated_redis.set(f'zmunah:state:{uid}', 'private state')
    for index in range(130):
        isolated_redis.set(f'zmunah:omer_counted:123:history{index:03}', '1')
    with patch.object(bot, 'send_message') as notice, patch.object(bot, 'send_message_with_keyboard') as prompt:
        bot.process_update(private_update(1000, text='/delete_my_data'))
        data = prompt.call_args.args[2][0][0]['callback_data']
        update = callback_update(data, 1001)
        original_delete = isolated_redis.delete
        chunk_calls = 0
        def fail_second_chunk(*keys):
            nonlocal chunk_calls
            if len(keys) > 1:
                chunk_calls += 1
                if chunk_calls == 2:
                    raise redis.ConnectionError('transient chunk failure')
            return original_delete(*keys)
        with patch.object(isolated_redis, 'delete', side_effect=fail_second_chunk):
            with pytest.raises(redis.ConnectionError):
                bot.process_update(update)
        assert chunk_calls == 2
        notice.assert_not_called()
        assert isolated_redis.ttl('zmunah:privacy:123:delete_pending') > 600
        # The original authorization window has elapsed before Telegram retries.
        isolated_redis.pexpire('zmunah:privacy:123:delete', 1)
        time.sleep(.02)
        assert not isolated_redis.exists('zmunah:privacy:123:delete')
        bot.process_update(update)
    assert not any(isolated_redis.exists(key) for key in storage.user_data_keys('123'))
    assert isolated_redis.exists('zmunah:user:12')
    assert isolated_redis.exists('zmunah:state:12')


def test_stale_callback_ack_does_not_gate_deduplicated_action(isolated_redis):
    response = Mock()
    response.json.return_value = {'ok': False, 'error_code': 400,
        'description': 'Bad Request: query is too old and response timeout expired or query ID is invalid'}
    with patch.object(bot.requests, 'post', return_value=response), patch.object(bot, 'handle_new_omer_settings'):
        update = callback_update('toggle:reminder', 1100)
        bot.process_update(update)
        bot.process_update(update)
    assert storage.get_user_prefs('123')['reminder_enabled'] is True


def test_saved_pages_expire_fail_closed_and_explicit_restart_is_stable(isolated_redis):
    for uid in ('12', '123', '456', '789'):
        storage.update_user_prefs(uid, {'reminder_enabled': True})
    users, cursor = storage.reminder_user_batch('reminder_enabled')
    assert cursor != '0' and len(cursor) == 32
    isolated_redis.delete(storage.REMINDER_PAGE_PREFIX + cursor)
    with pytest.raises(ValueError, match='expired'):
        storage.reminder_user_batch('reminder_enabled', cursor)
    with pytest.raises(ValueError, match='expired'):
        storage.reminder_user_batch('reminder_enabled', '0')
    restart = 'r.' + 'a' * 32
    first = storage.reminder_user_batch('reminder_enabled', restart)
    second = storage.reminder_user_batch('reminder_enabled', restart)
    assert first == second
    assert first[0]


def test_deletion_scrubs_saved_memberships_and_notice_follows_cleanup(isolated_redis):
    for uid in ('12', '123'):
        storage.update_user_prefs(uid, {'reminder_enabled': True})
    storage.reminder_user_batch('reminder_enabled')
    with patch.object(bot, 'send_message_with_keyboard') as prompt:
        bot.process_update(private_update(1200, text='/delete_my_data'))
    confirmation = prompt.call_args.args[2][0][0]['callback_data']
    def notice(*args, **kwargs):
        assert not isolated_redis.exists('zmunah:user:123')
        for key in isolated_redis.scan_iter(match=storage.REMINDER_PAGE_PREFIX + '*'):
            assert '123' not in json.loads(isolated_redis.get(key)).get('users', [])
        raise bot.TelegramDeliveryError('transient notice failure')
    with patch.object(bot, 'send_message', side_effect=notice):
        with pytest.raises(bot.TelegramDeliveryError):
            bot.process_update(callback_update(confirmation, 1201))
    pending = 'zmunah:privacy:123:delete_pending'
    assert isolated_redis.ttl(pending) > 600
    assert isolated_redis.exists('zmunah:user:12')
    with patch.object(bot, 'send_message'):
        bot.process_update(callback_update(confirmation, 1201))
    assert not any(isolated_redis.exists(key) for key in storage.user_data_keys('123'))
    assert isolated_redis.exists('zmunah:user:12')


def test_real_fixed_population_complete_with_bookkeeping_churn(isolated_redis):
    for uid in range(1, 101):
        storage.update_user_prefs(str(uid), {'reminder_enabled': True})
    cursor = '0'
    seen = set()
    for _ in range(500):
        users, cursor = storage.reminder_user_batch('reminder_enabled', cursor)
        assert len(users) <= 2
        for uid in users:
            key = f'zmunah:delivery:{uid}:evening:2026-04-04'
            token = storage.acquire_claim(key)
            if token:
                storage.complete_claim(key, token, storage.EVENT_TTL)
                seen.add(uid)
        if cursor == '0':
            break
    else:
        pytest.fail('bounded traversal did not finish')
    assert seen == {str(uid) for uid in range(1, 101)}


def test_stale_ack_does_not_hide_action_delivery_failure(isolated_redis):
    response = Mock(); response.json.return_value = {'ok': False, 'error_code': 400, 'description': 'query ID is invalid'}
    update = callback_update('toggle:reminder', 1300)
    with patch.object(bot.requests, 'post', return_value=response), patch.object(bot, 'handle_new_omer_settings', side_effect=[bot.TelegramDeliveryError('transient action delivery'), None]) as action:
        with pytest.raises(bot.TelegramDeliveryError):
            bot.process_update(update)
        assert storage.get_user_prefs('123')['reminder_enabled']
        bot.process_update(update)
        assert storage.get_user_prefs('123')['reminder_enabled']
        assert action.call_count == 2


def test_workflow_driver_resume_and_restart_keep_opaque_retry_identity():
    import importlib.util
    import urllib.error
    spec = importlib.util.spec_from_file_location('reminder_resume_runner', '.github/scripts/run_reminders.py')
    runner = importlib.util.module_from_spec(spec); spec.loader.exec_module(runner)
    opener = Mock(); opener.open.side_effect = urllib.error.HTTPError('https://example.test', 503, 'unavailable', {}, None)
    values = {'VERCEL_URL': 'https://example.test', 'CRON_SECRET': 'test', 'REMINDER_ENDPOINT': 'omer_reminder'}
    for options in ({'RESUME_CURSOR': 'b' * 32}, {'RESTART_TRAVERSAL': 'true'}):
        opener.reset_mock()
        with patch.dict(os.environ, {**values, **options}, clear=True), patch.object(runner.urllib.request, 'build_opener', return_value=opener), patch.object(runner.time, 'sleep'):
            assert runner.main() == 1
        urls = [call.args[0].full_url for call in opener.open.call_args_list]
        assert len(urls) == 3 and len(set(urls)) == 1
        cursor = runner.urllib.parse.parse_qs(runner.urllib.parse.urlparse(urls[0]).query)['cursor'][0]
        if 'RESUME_CURSOR' in options:
            assert cursor == 'b' * 32
        else:
            assert cursor.startswith('r.') and len(cursor) == 34


def test_pending_deletion_survives_completion_write_failure(isolated_redis):
    storage.update_user_prefs('123', {'reminder_enabled': True})
    with patch.object(bot, 'send_message_with_keyboard') as prompt:
        bot.process_update(private_update(1400, text='/delete_my_data'))
    data = prompt.call_args.args[2][0][0]['callback_data']
    update = callback_update(data, 1401)
    with patch.object(bot, 'send_message'), patch.object(bot, 'complete_claim', side_effect=redis.ConnectionError('completion unavailable')):
        with pytest.raises(redis.ConnectionError):
            bot.process_update(update)
    assert storage.get_pending_deletion('123') is not None
    with pytest.raises(RuntimeError, match='deletion is pending'):
        bot.process_update(private_update(1402, text='/reminder on'))
    assert not isolated_redis.exists('zmunah:user:123')
    with patch.object(bot, 'send_message'):
        bot.process_update(update)
    assert storage.get_pending_deletion('123') is None
    assert not any(isolated_redis.exists(key) for key in storage.user_data_keys('123'))


def test_snapshot_contention_does_not_deadlock_deletion(isolated_redis):
    with patch.object(bot, 'send_message_with_keyboard') as prompt:
        bot.process_update(private_update(1500, text='/delete_my_data'))
    update = callback_update(prompt.call_args.args[2][0][0]['callback_data'], 1501)
    with storage.reminder_snapshot_lock(), patch.object(bot, 'send_message') as send:
        with ThreadPoolExecutor(max_workers=1) as pool:
            attempt = pool.submit(bot.process_update, update)
            with pytest.raises(RuntimeError, match='snapshot busy'):
                attempt.result(timeout=2)
        send.assert_not_called()
    with patch.object(bot, 'send_message'):
        bot.process_update(update)
    assert not any(isolated_redis.exists(key) for key in storage.user_data_keys('123'))


def test_saved_page_metadata_is_bounded_and_has_expected_ttls(isolated_redis):
    for uid in range(1, 8):
        storage.update_user_prefs(str(uid), {'reminder_enabled': True})
    _, cursor = storage.reminder_user_batch('reminder_enabled')
    assert len(cursor) == 32
    for key in isolated_redis.scan_iter(match=storage.REMINDER_PAGE_PREFIX + '*'):
        page = json.loads(isolated_redis.get(key))
        assert len(page.get('users', [])) <= 2
        assert 0 < isolated_redis.ttl(key) <= 3600
    for key in isolated_redis.scan_iter(match='zmunah:reminder_root:*'):
        assert len(isolated_redis.get(key)) == 32
        assert 3600 < isolated_redis.ttl(key) <= 72 * 3600
    key = storage.REMINDER_PAGE_PREFIX + cursor
    page = json.loads(isolated_redis.get(key))
    page['users'] = ['1', '2', '3']
    page.pop('scan', None); page['next'] = '0'
    isolated_redis.set(key, json.dumps(page))
    with pytest.raises(ValueError, match='invalid reminder page'):
        storage.reminder_user_batch('reminder_enabled', cursor)


NOT_MODIFIED = ('Bad Request: message is not modified: specified new message content and reply markup '
                'are exactly the same as a current content and reply markup of the message')


def telegram_error(status, payload):
    response = bot.requests.Response()
    response.status_code = status
    response._content = json.dumps(payload).encode()
    return response


@pytest.mark.parametrize('callback,method', [
    ('city:ירושלים:0', 'editMessageReplyMarkup'),
    ('omer:toggle_reminder', 'editMessageText'),
])
def test_webhook_lost_edit_response_converges_once(isolated_redis, callback, method):
    import hashlib
    module = importlib.import_module('api.telegram_webhook')
    body = json.dumps(callback_update(callback, 910)).encode()
    headers = {'Content-Length': str(len(body)), 'X-Telegram-Bot-Api-Secret-Token': 'test'}
    success_key = 'zmunah:update_receipt:' + hashlib.sha256(b'910').hexdigest()
    applied = []

    def post(url, *, json, timeout):
        assert url.endswith('/' + method)
        if not applied:
            applied.append(json)
            raise bot.requests.Timeout('lost response after applied edit')
        assert json == applied[0]
        return telegram_error(400, {'ok': False, 'error_code': 400, 'description': NOT_MODIFIED})

    with (patch.object(module, 'TELEGRAM_WEBHOOK_SECRET', 'test'),
          patch.object(bot, 'answer_callback_query'),
          patch.object(bot.requests, 'post', side_effect=post) as transport):
        statuses = []
        for _ in range(3):
            h = request_handler(module, headers=headers, body=body)
            h.do_POST()
            statuses.append(h.send_response.call_args.args[0])
        assert statuses == [503, 200, 200]
        assert transport.call_count == 2
    prefs = storage.get_user_prefs('123')
    if method == 'editMessageReplyMarkup':
        assert [city['name'] for city in prefs['cities']] == ['תל אביב -יפו', 'חיפה']
    else:
        assert prefs['reminder_enabled'] is True
    assert len(list(isolated_redis.scan_iter(match='zmunah:delivery:123:update:910:mutation:*'))) == 1
    assert isolated_redis.get(success_key) == '1'


@pytest.mark.parametrize('helper,args', [
    (bot.edit_message_with_keyboard, (123, 1, 'text', [])),
    (bot.edit_message_keyboard_only, (123, 1, [])),
])
@pytest.mark.parametrize('status,payload', [
    (400, {'ok': False, 'error_code': 400, 'description': 'Bad Request: message to edit not found'}),
    (401, {'ok': False, 'error_code': 401, 'description': NOT_MODIFIED}),
    (400, {'ok': False, 'error_code': 401, 'description': NOT_MODIFIED}),
    (400, {'ok': True, 'error_code': 400, 'description': NOT_MODIFIED}),
    (400, {'ok': False, 'error_code': 400, 'description': 'Other error: message is not modified'}),
    (400, []),
])
def test_edit_helpers_reject_genuine_or_malformed_errors(helper, args, status, payload):
    with patch.object(bot.requests, 'post', return_value=telegram_error(status, payload)):
        with pytest.raises(bot.TelegramDeliveryError, match='Telegram request failed'):
            helper(*args)


def test_send_message_does_not_accept_edit_noop():
    response = telegram_error(400, {'ok': False, 'error_code': 400, 'description': NOT_MODIFIED})
    with patch.object(bot.requests, 'post', return_value=response):
        with pytest.raises(bot.TelegramDeliveryError):
            bot.send_message(123, 'text')
