"""Opt-in two-way synchronization of a dedicated app-created Google calendar.

All OAuth secrets and refresh tokens stay on the server. External calls happen
outside workspace transactions; revision checks protect concurrent desktop edits.
"""
import hashlib
import json
import os
import secrets
import time
import uuid
from copy import deepcopy
from datetime import datetime, date, timedelta, timezone
from urllib.parse import urlencode, quote
from urllib.request import Request, build_opener
from urllib.error import HTTPError, URLError
from zoneinfo import ZoneInfo
from core.billing import NoRedirect, https_url
from core.models import Task
from dataclasses import asdict
from core.snapshot import validate_snapshot
from server.store import digest

SCOPE = 'https://www.googleapis.com/auth/calendar.app.created'


class GoogleError(ValueError):
    def __init__(self, message, status=0):
        self.status = status
        super().__init__(message)


def configured():
    return all(os.getenv(key) for key in ('GOOGLE_CLIENT_ID', 'GOOGLE_CLIENT_SECRET', 'GOOGLE_REDIRECT_URI', 'TASKFLOW_TOKEN_ENCRYPTION_KEY'))


def cipher():
    from cryptography.fernet import Fernet
    try:
        return Fernet(os.environ['TASKFLOW_TOKEN_ENCRYPTION_KEY'].encode())
    except (KeyError, ValueError):
        raise GoogleError('Chưa cấu hình khóa mã hóa OAuth trên máy chủ.')


def http(method, url, data=None, token=None, etag=None, form=False):
    https_url(url)
    headers = {'Accept': 'application/json'}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    if etag:
        headers['If-Match'] = etag
    body = None
    if data is not None:
        body = urlencode(data).encode() if form else json.dumps(data).encode()
        headers['Content-Type'] = 'application/x-www-form-urlencoded' if form else 'application/json'
    try:
        with build_opener(NoRedirect()).open(Request(url, method=method, data=body, headers=headers), timeout=20) as response:
            raw = response.read(8 * 1024 * 1024 + 1)
            if len(raw) > 8 * 1024 * 1024:
                raise GoogleError('Phản hồi Google quá lớn.')
            return json.loads(raw) if raw else {}
    except HTTPError as exc:
        raise GoogleError('Google chưa chấp nhận yêu cầu. Hãy kiểm tra liên kết hoặc thử lại.', exc.code) from exc
    except (URLError, OSError, ValueError) as exc:
        if isinstance(exc, GoogleError):
            raise
        raise GoogleError('Chưa kết nối được Google Calendar. Dữ liệu hiện có vẫn được giữ.') from exc


def _hash(value):
    return digest(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')))


def event_hash(event):
    def instant(value):
        if value.get('dateTime'):
            moment = datetime.fromisoformat(value['dateTime'].replace('Z', '+00:00'))
            if moment.tzinfo is None:
                moment = moment.replace(tzinfo=ZoneInfo(value.get('timeZone', 'UTC')))
            return moment.astimezone(timezone.utc).isoformat()
        return value.get('date')
    reminders = event.get('reminders', {})
    return _hash({'title': event.get('summary', ''), 'description': event.get('description', ''),
        'start': instant(event.get('start', {})), 'end': instant(event.get('end', {})),
        'recurrence': event.get('recurrence', []), 'status': 'cancelled' if event.get('status') == 'cancelled' else 'active',
        'reminders': {'useDefault': bool(reminders.get('useDefault', False)),
                      'overrides': sorted(reminders.get('overrides', []), key=lambda item: (item.get('method', ''), item.get('minutes', 0)))}})


def desired_events(payload):
    tz = payload.get('profile', {}).get('timezone', 'Asia/Ho_Chi_Minh')
    zone = ZoneInfo(tz)
    tasks = {item['id']: item for item in payload.get('tasks', [])}
    scheduled = set()
    result = {}
    def timed(title, description, begin, end, lead, local_id):
        return {'summary': title, 'description': description or '',
            'start': {'dateTime': begin.replace(tzinfo=zone).isoformat(), 'timeZone': tz},
            'end': {'dateTime': end.replace(tzinfo=zone).isoformat(), 'timeZone': tz},
            'reminders': {'useDefault': False, 'overrides': [{'method': 'popup', 'minutes': min(40320, max(0, lead))}]},
            'extendedProperties': {'private': {'taskflow_id': local_id}}}
    for block in payload.get('blocks', []):
        task = tasks.get(block.get('task_id'))
        if task and task['status'] in ('done', 'cancelled'):
            continue
        if task:
            scheduled.add(task['id'])
        key = 'block:' + block['id']
        result[key] = timed(task['title'] if task else block['title'], task.get('notes', '') if task else '', datetime.fromisoformat(block['start_at']),
            datetime.fromisoformat(block['end_at']), int(task.get('reminder_minutes', 0)) if task else 0, key)
    for task in tasks.values():
        if task['id'] in scheduled or task['status'] in ('done', 'cancelled') or not task.get('due_date'):
            continue
        key = 'task:' + task['id']
        if task.get('due_time'):
            begin = datetime.fromisoformat(task['due_date'] + 'T' + task['due_time'])
            result[key] = timed(task['title'], task.get('notes', ''), begin, begin + timedelta(minutes=task['estimated_minutes']), task.get('reminder_minutes', 0), key)
        else:
            result[key] = {'summary': task['title'], 'description': task.get('notes', ''),
                'start': {'date': task['due_date']}, 'end': {'date': (date.fromisoformat(task['due_date']) + timedelta(days=1)).isoformat()},
                'reminders': {'useDefault': False, 'overrides': []}, 'extendedProperties': {'private': {'taskflow_id': key}}}
    return result


def import_event(payload, uid, event, local_id=None):
    """Google events become tasks; timed events also get a linked work slot."""
    task_id = str(uuid.uuid5(uuid.NAMESPACE_URL, 'taskflow-google-task:' + uid + ':' + event['id']))
    block_id = str(uuid.uuid5(uuid.NAMESPACE_URL, 'taskflow-google-block:' + uid + ':' + event['id']))
    kind, identifier = local_id.split(':', 1) if local_id else ('block' if event.get('start', {}).get('dateTime') else 'task', block_id if event.get('start', {}).get('dateTime') else task_id)
    existing_block = next((item for item in payload['blocks'] if item['id'] == identifier), None) if kind == 'block' else None
    existing_task = next((item for item in payload['tasks'] if item['id'] == (existing_block.get('task_id') if existing_block else identifier if kind == 'task' else task_id)), None)
    if event.get('status') == 'cancelled':
        if kind == 'block':
            payload['blocks'] = [item for item in payload['blocks'] if item['id'] != identifier]
        if existing_task and (kind == 'task' or existing_task['id'] == task_id):
            payload['tasks'] = [item for item in payload['tasks'] if item['id'] != existing_task['id']]
            payload['blocks'] = [item for item in payload['blocks'] if item.get('task_id') != existing_task['id']]
            payload['trash'] = [item for item in payload.get('trash', []) if item['id'] != existing_task['id']]
            payload['trash'].append({'id': existing_task['id'], 'payload': existing_task, 'deleted_at': datetime.now().isoformat()})
        return kind + ':' + identifier
    if event.get('recurrence') or event.get('recurringEventId'):
        raise GoogleError('Lịch Google lặp lại cần được xử lý riêng; sự kiện này chưa được nhập hoặc ghi đè.')
    title = str(event.get('summary') or 'Lịch Google')[:500]
    zone = ZoneInfo(payload.get('profile', {}).get('timezone', 'Asia/Ho_Chi_Minh'))
    start, end = event['start'], event['end']
    if start.get('dateTime'):
        def local(value):
            moment = datetime.fromisoformat(value['dateTime'].replace('Z', '+00:00'))
            if moment.tzinfo is None:
                moment = moment.replace(tzinfo=ZoneInfo(value.get('timeZone', str(zone))))
            return moment.astimezone(zone).replace(tzinfo=None)
        begin, finish = local(start), local(end)
        if finish <= begin or (finish - begin).total_seconds() > 10080 * 60:
            raise GoogleError('Sự kiện Google có thời lượng không được hỗ trợ.')
        minutes = max(1, int((finish - begin).total_seconds() // 60))
    else:
        begin, finish, minutes = datetime.fromisoformat(start['date']), datetime.fromisoformat(end['date']), 30
        if finish.date() != begin.date() + timedelta(days=1):
            raise GoogleError('Lịch cả ngày nhiều ngày cần kiểm tra thủ công; chưa nhập sự kiện này.')
    lead = next((int(item['minutes']) for item in event.get('reminders', {}).get('overrides', []) if item.get('method') == 'popup'), 0)
    if existing_task:
        existing_task['title'] = title
        existing_task['updated_at'] = datetime.now().isoformat()
        if existing_task['id'] == task_id or kind == 'task':
            existing_task.update(due_date=begin.date().isoformat(), due_time=begin.strftime('%H:%M') if start.get('dateTime') else None,
                estimated_minutes=minutes, reminder_minutes=lead, notes=str(event.get('description', ''))[:60000])
        task_id = existing_task['id']
    else:
        if kind == 'task':
            task_id = identifier
        payload['tasks'].append(asdict(Task(id=task_id, user_id=uid, title=title, due_date=begin.date().isoformat(),
            due_time=begin.strftime('%H:%M') if start.get('dateTime') else None, estimated_minutes=minutes,
            reminder_minutes=lead, notes=str(event.get('description', ''))[:60000])))
    if kind == 'block':
        if not start.get('dateTime'):
            raise GoogleError('Đổi lịch theo giờ thành cả ngày cần kiểm tra thủ công; bản cũ được giữ.')
        block = {'id': identifier, 'task_id': task_id, 'title': title, 'start_at': begin.isoformat(), 'end_at': finish.isoformat(), 'source': 'manual'}
        if existing_block:
            existing_block.update(block)
        else:
            payload['blocks'].append(block)
    return kind + ':' + identifier


class GoogleCalendar:
    def __init__(self, store):
        self.store = store

    def status(self, uid):
        with self.store.connect() as db:
            link = db.execute('SELECT * FROM google_links WHERE account=?', (uid,)).fetchone()
            rows = db.execute('SELECT local_id,conflict FROM google_maps WHERE account=?', (uid,)).fetchall()
        return {'configured': configured(), 'connected': bool(link), 'last_sync': link['last_sync'] if link else None,
                'error': link['error'] if link else '', 'conflicts': [{'local_id': row['local_id'], 'title': json.loads(row['conflict']).get('event', {}).get('summary', 'Sự kiện đã thay đổi')} for row in rows if row['conflict'] and not json.loads(row['conflict']).get('unsupported')]}

    def start(self, uid):
        if not configured():
            raise GoogleError('Dịch vụ liên kết Google Calendar chưa được nhà phát hành thiết lập.')
        cipher()
        redirect = os.environ['GOOGLE_REDIRECT_URI']
        from urllib.parse import urlsplit
        parts = urlsplit(redirect)
        if parts.scheme != 'https' and not (parts.scheme == 'http' and parts.hostname in ('127.0.0.1', 'localhost')):
            raise GoogleError('OAuth callback cần HTTPS; chỉ localhost được dùng HTTP khi phát triển.')
        if self.status(uid)['connected']:
            raise GoogleError('Tài khoản này đã liên kết. Ngắt liên kết trước khi đổi tài khoản Google.')
        state = secrets.token_urlsafe(32)
        with self.store.connect() as db:
            db.execute('DELETE FROM google_states WHERE expires<?', (time.time(),))
            db.execute('INSERT INTO google_states VALUES (?,?,?)', (digest(state), uid, time.time() + 600))
        return {'authorization_url': 'https://accounts.google.com/o/oauth2/v2/auth?' + urlencode({
            'client_id': os.environ['GOOGLE_CLIENT_ID'], 'redirect_uri': redirect, 'response_type': 'code',
            'scope': SCOPE, 'state': state, 'access_type': 'offline', 'prompt': 'consent'})}

    def callback(self, state, code):
        with self.store.connect(lock='google-oauth') as db:
            row = db.execute('SELECT * FROM google_states WHERE hash=? AND expires>?', (digest(state), time.time())).fetchone()
            if not row:
                raise GoogleError('Yêu cầu liên kết hết hạn hoặc đã sử dụng.')
            uid = row['account']
            db.execute('DELETE FROM google_states WHERE hash=?', (digest(state),))
        tokens = http('POST', 'https://oauth2.googleapis.com/token', {'code': code,
            'client_id': os.environ['GOOGLE_CLIENT_ID'], 'client_secret': os.environ['GOOGLE_CLIENT_SECRET'],
            'redirect_uri': os.environ['GOOGLE_REDIRECT_URI'], 'grant_type': 'authorization_code'}, form=True)
        if not tokens.get('refresh_token') or not tokens.get('access_token'):
            raise GoogleError('Google chưa cấp quyền truy cập nền. Hãy liên kết lại và cho phép truy cập.')
        calendar = http('POST', 'https://www.googleapis.com/calendar/v3/calendars', {'summary': 'TaskFlow', 'timeZone': 'Asia/Ho_Chi_Minh'}, tokens['access_token'])
        tokens['expires_at'] = time.time() + tokens.get('expires_in', 3600)
        with self.store.connect(lock='google-oauth') as db:
            if db.execute('SELECT 1 FROM google_links WHERE account=?', (uid,)).fetchone():
                raise GoogleError('Tài khoản đã có liên kết; không thay thế lịch đang dùng.')
            db.execute('INSERT INTO google_links VALUES (?,?,?,?,?,?)', (uid, calendar['id'], cipher().encrypt(json.dumps(tokens).encode()).decode(), None, 0, ''))
        return {'message': 'Đã liên kết lịch Google TaskFlow. Quay lại ứng dụng để kiểm tra.'}

    def disconnect(self, uid):
        with self.store.connect(lock='google:' + uid) as db:
            link = db.execute('SELECT credentials FROM google_links WHERE account=?', (uid,)).fetchone()
            for table in ('google_maps', 'google_jobs', 'google_states', 'google_links'):
                db.execute('DELETE FROM ' + table + ' WHERE account=?', (uid,))
        if link:
            try:
                token = json.loads(cipher().decrypt(link['credentials'].encode()))['refresh_token']
                http('POST', 'https://oauth2.googleapis.com/revoke', {'token': token}, form=True)
            except Exception:
                pass
        return {'message': 'Đã ngắt liên kết trong TaskFlow. Lịch Google hiện có được giữ lại.'}

    def resolve(self, uid, local_id, choice):
        if choice not in ('google', 'taskflow'):
            raise GoogleError('Lựa chọn xung đột không hợp lệ.')
        with self.store.connect(lock='google:' + uid) as db:
            running = db.execute('SELECT 1 FROM google_jobs WHERE account=? AND expires>?', (uid, time.time())).fetchone()
            if running:
                raise GoogleError('Google đang đồng bộ. Chờ kết thúc rồi chọn cách xử lý xung đột.')
            row = db.execute('SELECT * FROM google_maps WHERE account=? AND local_id=?', (uid, local_id)).fetchone()
            if not row or not row['conflict']:
                raise GoogleError('Xung đột đã thay đổi. Hãy kiểm tra lại.')
            conflict = json.loads(row['conflict'])
            if conflict.get('unsupported'):
                raise GoogleError('Kiểu sự kiện này chưa hỗ trợ. Hãy chỉnh sự kiện trong Google Calendar trước.')
            if choice == 'taskflow' and conflict['event'].get('status') == 'cancelled':
                db.execute('UPDATE google_maps SET event_id=?,local_hash=?,remote_hash=?,etag=?,conflict=? WHERE account=? AND local_id=?',
                    (uuid.uuid4().hex, '', '', None, None, uid, local_id))
                return {'message': 'Đã chọn tạo lại sự kiện từ TaskFlow. Chọn Đồng bộ Google để áp dụng.'}
            conflict['choice'] = choice
            db.execute('UPDATE google_maps SET conflict=? WHERE account=? AND local_id=?', (json.dumps(conflict), uid, local_id))
        return {'message': 'Đã ghi lựa chọn. Chọn Đồng bộ Google để áp dụng.'}

    def token(self, link):
        tokens = json.loads(cipher().decrypt(link['credentials'].encode()))
        if tokens.get('expires_at', 0) < time.time() + 120:
            refreshed = http('POST', 'https://oauth2.googleapis.com/token', {'client_id': os.environ['GOOGLE_CLIENT_ID'],
                'client_secret': os.environ['GOOGLE_CLIENT_SECRET'], 'refresh_token': tokens['refresh_token'], 'grant_type': 'refresh_token'}, form=True)
            tokens.update(refreshed, expires_at=time.time() + refreshed.get('expires_in', 3600))
            with self.store.connect() as db:
                db.execute('UPDATE google_links SET credentials=? WHERE account=? AND calendar_id=?', (cipher().encrypt(json.dumps(tokens).encode()).decode(), link['account'], link['calendar_id']))
        return tokens['access_token']

    def pull(self, calendar_url, token, sync_token):
        params = {'maxResults': 250, 'showDeleted': 'true', 'singleEvents': 'false'}
        if sync_token:
            params['syncToken'] = sync_token
        events = []
        for _ in range(100):
            try:
                response = http('GET', calendar_url + '/events?' + urlencode(params), token=token)
            except GoogleError as exc:
                if exc.status == 410 and sync_token:
                    return self.pull(calendar_url, token, None)
                raise
            events.extend(response.get('items', []))
            if len(events) > 10000:
                raise GoogleError('Lịch Google vượt giới hạn 10.000 sự kiện.')
            if not response.get('nextPageToken'):
                return events, response.get('nextSyncToken'), not bool(sync_token)
            params['pageToken'] = response['nextPageToken']
        raise GoogleError('Lịch Google có quá nhiều trang dữ liệu.')

    def sync(self, uid):
        owner = str(uuid.uuid4())
        with self.store.connect(lock='google:' + uid) as db:
            job = db.execute('SELECT * FROM google_jobs WHERE account=?', (uid,)).fetchone()
            if job and job['expires'] > time.time():
                return {'message': 'Google Calendar đang được đồng bộ.'}
            link = db.execute('SELECT * FROM google_links WHERE account=?', (uid,)).fetchone()
            if not link:
                raise GoogleError('Tài khoản chưa liên kết Google Calendar.')
            db.upsert('google_jobs', ('account',), {'account': uid, 'owner': owner, 'expires': time.time() + 3600})
        try:
            return self._sync(uid, dict(link), owner)
        except Exception as exc:
            message = str(exc) if isinstance(exc, GoogleError) else 'Chưa đồng bộ Google được. Dữ liệu hiện có được giữ; hãy thử lại.'
            with self.store.connect() as db:
                db.execute('UPDATE google_links SET error=? WHERE account=?', (message[:500], uid))
            raise GoogleError(message) from exc
        finally:
            with self.store.connect() as db:
                db.execute('DELETE FROM google_jobs WHERE account=? AND owner=?', (uid, owner))

    def lease(self, db, uid, owner):
        job = db.execute('SELECT 1 FROM google_jobs WHERE account=? AND owner=? AND expires>?', (uid, owner, time.time())).fetchone()
        if not job or not db.execute('SELECT 1 FROM google_links WHERE account=?', (uid,)).fetchone():
            raise GoogleError('Liên kết hoặc phiên đồng bộ đã thay đổi. Hãy thử lại.')

    def _sync(self, uid, link, owner):
        from server.app import empty_workspace
        token = self.token(link)
        url = 'https://www.googleapis.com/calendar/v3/calendars/' + quote(link['calendar_id'], safe='')
        with self.store.connect() as db:
            workspace = db.execute('SELECT * FROM workspaces WHERE account=?', (uid,)).fetchone()
            maps = {row['local_id']: dict(row) for row in db.execute('SELECT * FROM google_maps WHERE account=?', (uid,)).fetchall()}
        revision = workspace['revision'] if workspace else 0
        payload = json.loads(workspace['payload']) if workspace else empty_workspace()
        payload.setdefault('trash', [])
        before = _hash(payload)
        desired = desired_events(payload)
        changes, sync_token, full = self.pull(url, token, link['sync_token'])
        seen = {item['id'] for item in changes}
        if full:
            changes.extend({'id': item['event_id'], 'status': 'cancelled'} for item in maps.values() if item['remote_hash'] and item['event_id'] not in seen)
        changes_by_id = {item['id']: item for item in changes}
        for mapping in maps.values():
            if mapping.get('conflict'):
                pending = json.loads(mapping['conflict'])
                changes_by_id.setdefault(mapping['event_id'], pending['event'])
        errors = []
        def unsupported(event, mapping, message):
            errors.append(message)
            key = mapping['local_id'] if mapping else 'unsupported:' + digest(event['id'])
            maps[key] = dict(mapping or {'account': uid, 'local_id': key, 'event_id': event['id'],
                'local_hash': '', 'remote_hash': '', 'etag': event.get('etag')},
                conflict=json.dumps({'event': event, 'unsupported': True}))
        for event in changes_by_id.values():
            mapping = next((item for item in maps.values() if item['event_id'] == event['id']), None)
            if event.get('status') == 'cancelled' and mapping is None:
                continue
            if event.get('recurrence') or event.get('recurringEventId'):
                unsupported(event, mapping, 'Lịch Google lặp lại chưa được nhập: ' + str(event.get('summary', 'Sự kiện'))[:80])
                continue
            if mapping and mapping['local_id'].startswith('unsupported:'):
                maps.pop(mapping['local_id'], None)
                mapping = None
            local_id = mapping['local_id'] if mapping else event.get('extendedProperties', {}).get('private', {}).get('taskflow_id')
            local = desired.get(local_id)
            if not mapping and local_id and not local:
                errors.append('Sự kiện TaskFlow không còn bản tương ứng trong app; giữ lịch Google để kiểm tra thủ công.')
                continue
            remote_hash = event_hash(event)
            local_hash = event_hash(local) if local else ''
            if mapping and not local and event.get('status') == 'cancelled':
                maps.pop(mapping['local_id'], None)
                continue
            if mapping:
                pending = json.loads(mapping['conflict']) if mapping.get('conflict') else {}
                if pending.get('choice') == 'taskflow':
                    mapping.update(remote_hash=remote_hash, etag=event.get('etag'), conflict=None)
                    continue
                remote_changed = remote_hash != mapping['remote_hash']
                local_changed = local_hash != mapping['local_hash']
                if remote_changed and local_changed and local_hash != remote_hash and pending.get('choice') != 'google':
                    mapping['conflict'] = json.dumps({'event': event})
                    continue
                if not remote_changed and pending.get('choice') != 'google':
                    mapping['etag'] = event.get('etag', mapping['etag'])
                    continue
            elif local_id and local and local_hash != remote_hash:
                maps[local_id] = {'account': uid, 'local_id': local_id, 'event_id': event['id'], 'local_hash': local_hash,
                    'remote_hash': '', 'etag': event.get('etag'), 'conflict': json.dumps({'event': event})}
                continue
            elif event.get('status') == 'cancelled':
                continue
            candidate = deepcopy(payload)
            try:
                local_id = import_event(candidate, uid, event, local_id if local_id in desired else mapping['local_id'] if mapping else None)
            except GoogleError as exc:
                unsupported(event, mapping, str(exc))
                continue
            payload = candidate
            if event.get('status') == 'cancelled':
                maps.pop(local_id, None)
            else:
                updated = desired_events(payload).get(local_id)
                maps[local_id] = {'account': uid, 'local_id': local_id, 'event_id': event['id'],
                    'local_hash': event_hash(updated) if updated else '', 'remote_hash': remote_hash, 'etag': event.get('etag'), 'conflict': None}
        validate_snapshot(payload)
        with self.store.connect(lock=['google:' + uid, 'workspace:' + uid]) as db:
            self.lease(db, uid, owner)
            current = db.execute('SELECT revision FROM workspaces WHERE account=?', (uid,)).fetchone()
            if (current['revision'] if current else 0) != revision:
                raise GoogleError('Dữ liệu TaskFlow vừa thay đổi. Sẽ thử đồng bộ Google lại, chưa ghi đè dữ liệu.')
            if _hash(payload) != before:
                db.upsert('workspaces', ('account',), {'account': uid, 'revision': revision + 1, 'payload': json.dumps(payload, ensure_ascii=False)})
            db.execute('DELETE FROM google_maps WHERE account=?', (uid,))
            for mapping in maps.values():
                db.upsert('google_maps', ('account', 'local_id'), mapping)
            db.execute('UPDATE google_links SET sync_token=?,last_sync=?,error=? WHERE account=?', (sync_token, time.time(), '; '.join(errors)[:500], uid))
        desired = desired_events(payload)
        processed = 0
        for local_id in list(dict.fromkeys(list(desired) + list(maps))):
            mapping, local = maps.get(local_id), desired.get(local_id)
            if mapping and mapping.get('conflict'):
                continue
            local_hash = event_hash(local) if local else ''
            if mapping and local_hash == mapping['local_hash']:
                continue
            if processed >= 500:
                break
            processed += 1
            with self.store.connect() as db:
                self.lease(db, uid, owner)
            try:
                if not local and mapping:
                    try:
                        http('DELETE', url + '/events/' + quote(mapping['event_id'], safe=''), token=token, etag=mapping['etag'])
                    except GoogleError as exc:
                        if exc.status not in (404, 410):
                            raise
                    with self.store.connect() as db:
                        db.execute('DELETE FROM google_maps WHERE account=? AND local_id=?', (uid, local_id))
                    continue
                if mapping and mapping['remote_hash']:
                    result = http('PATCH', url + '/events/' + quote(mapping['event_id'], safe=''), local, token, mapping['etag'])
                else:
                    event_id = mapping['event_id'] if mapping else hashlib.sha256((uid + ':' + local_id).encode()).hexdigest()
                    try:
                        result = http('POST', url + '/events', dict(local, id=event_id), token)
                    except GoogleError as exc:
                        if exc.status != 409:
                            raise
                        result = http('GET', url + '/events/' + event_id, token=token)
                        if result.get('extendedProperties', {}).get('private', {}).get('taskflow_id') != local_id:
                            raise GoogleError('Mã sự kiện Google bị trùng. Không ghi đè sự kiện khác.')
                        if event_hash(result) != local_hash:
                            with self.store.connect() as db:
                                db.upsert('google_maps', ('account', 'local_id'), {'account': uid, 'local_id': local_id, 'event_id': result['id'],
                                    'local_hash': local_hash, 'remote_hash': '', 'etag': result.get('etag'), 'conflict': json.dumps({'event': result})})
                            continue
                with self.store.connect() as db:
                    self.lease(db, uid, owner)
                    db.upsert('google_maps', ('account', 'local_id'), {'account': uid, 'local_id': local_id, 'event_id': result['id'],
                        'local_hash': local_hash, 'remote_hash': event_hash(result), 'etag': result.get('etag'), 'conflict': None})
            except GoogleError as exc:
                if exc.status in (404, 410, 412) and mapping:
                    try:
                        event = http('GET', url + '/events/' + quote(mapping['event_id'], safe=''), token=token)
                    except GoogleError as missing:
                        if missing.status not in (404, 410):
                            raise
                        event = {'id': mapping['event_id'], 'status': 'cancelled'}
                    with self.store.connect() as db:
                        db.execute('UPDATE google_maps SET conflict=? WHERE account=? AND local_id=?', (json.dumps({'event': event}), uid, local_id))
                else:
                    raise
        return {'message': 'Đã đồng bộ lịch Google TaskFlow.', **self.status(uid)}
