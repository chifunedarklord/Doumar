"""Offline-first snapshot synchronization with compare-and-swap revisions.

Conflicting snapshots require an explicit choice; each replacement first writes
an account-scoped recovery file. Passwords and entitlements never synchronize.
"""
from datetime import datetime
import hashlib
import json
import threading
from pathlib import Path
from core.cloud import CloudClient, CloudError
from core.workspace import Workspace
from core.repositories import Storage

_locks = {}
_guard = threading.Lock()


def fingerprint(payload):
    data = dict(payload)
    data.pop('exported_at', None)
    data.setdefault('profile', {})
    for key in ('tasks', 'memories', 'sessions', 'messages', 'blocks', 'trash'):
        data[key] = sorted(data.get(key, []), key=lambda item: json.dumps(item, ensure_ascii=False, sort_keys=True))
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def status(user_id):
    value = next((item['value'] for item in Storage.get_memory(user_id, 'cloud_sync') if item['key'] == 'state'), None)
    try:
        if isinstance(value, dict):
            return value
        return json.loads(value) if value else {}
    except (TypeError, ValueError):
        return {}


def baseline(user_id):
    value = Storage.get_memory_value(user_id, 'cloud_sync', 'baseline')
    return value if isinstance(value, dict) else None


def recovery_copy(user_id, payload):
    from core.orm import engine
    base = Path(engine.url.database).resolve().parent if engine.url.get_backend_name() == 'sqlite' else Path.home() / '.taskflow'
    folder = base / 'recovery' / hashlib.sha256(user_id.encode()).hexdigest()[:24]
    folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    name = folder / (datetime.now().strftime('%Y%m%d-%H%M%S-%f') + '.json')
    import os
    fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as stream:
        json.dump(payload, stream, ensure_ascii=False)
    return str(name)


def synchronize(user_id, choice=None, can_download=None):
    with _guard:
        lock = _locks.setdefault(user_id, threading.Lock())
    if not lock.acquire(blocking=False):
        return {'state': 'busy', 'message': 'Đang đồng bộ…'}
    try:
        client = CloudClient(user_id)
        local = Workspace.sync_snapshot(user_id)
        local_hash = fingerprint(local)
        previous = status(user_id)
        if previous.get('server') != client.url:
            previous = {}
        remote = client.request('GET', '/v1/sync')
        if remote.get('account_id') != user_id:
            raise CloudError('Dữ liệu đồng bộ không thuộc tài khoản này.')
        remote_hash = fingerprint(remote['workspace'])
        if local_hash == remote_hash:
            result, baseline_hash, baseline_payload = 'synced', local_hash, local
        else:
            local_changed = local_hash != previous.get('hash')
            remote_changed = remote['revision'] != previous.get('revision', 0)
            empty = not any(local.get(k) for k in ('tasks', 'memories', 'sessions', 'blocks', 'trash'))
            if choice is None and local_changed and remote_changed and not empty:
                from core.sync_merge import merge_snapshots
                before = baseline(user_id)
                merged = merge_snapshots(before, local, remote['workspace']) if before and fingerprint(before) == previous.get('hash') else None
                if merged is None:
                    return {'state': 'conflict', 'message': 'Cùng một mục đã thay đổi ở hai nơi. Chọn bản trên máy hoặc bản máy chủ; bản bị thay thế sẽ được sao lưu.'}
                if can_download is not None and not can_download():
                    return {'state': 'deferred', 'message': 'Đã lưu trên máy · Sẽ gộp dữ liệu sau khi bạn rời trang sửa'}
                remote = client.request('PUT', '/v1/sync', {'revision': remote['revision'], 'workspace': merged})
                recovery_copy(user_id, local)
                Workspace.apply_sync_snapshot(user_id, merged, expected_hash=local_hash)
                result, baseline_payload = 'merged', Workspace.sync_snapshot(user_id)
                baseline_hash = fingerprint(baseline_payload)
            elif choice == 'local' or (choice is None and local_changed and not remote_changed):
                if choice == 'local':
                    recovery_copy(user_id, remote['workspace'])
                # CAS on server: stale revisions can never overwrite a newer edit.
                remote = client.request('PUT', '/v1/sync', {'revision': remote['revision'], 'workspace': local})
                baseline_hash, result, baseline_payload = local_hash, 'uploaded', local
            else:
                if can_download is not None and not can_download():
                    return {'state': 'deferred', 'message': 'Đã lưu trên máy · Sẽ đồng bộ sau khi bạn rời trang đang sửa'}
                recovery_copy(user_id, local)
                Workspace.apply_sync_snapshot(user_id, remote['workspace'], expected_hash=local_hash)
                baseline_payload = Workspace.sync_snapshot(user_id)
                baseline_hash, result = fingerprint(baseline_payload), 'downloaded'
        state = {'revision': remote['revision'], 'hash': baseline_hash, 'server': client.url,
                 'last_synced': datetime.now().isoformat()}
        Storage.set_memory(user_id, 'cloud_sync', 'baseline', json.dumps(baseline_payload, ensure_ascii=False), 1.0)
        Storage.set_memory(user_id, 'cloud_sync', 'state', json.dumps(state), 1.0)
        return {'state': result, 'message': 'Đã đồng bộ lúc ' + datetime.now().strftime('%H:%M'), **state}
    except CloudError as exc:
        if exc.status == 409:
            return {'state': 'conflict', 'message': str(exc)}
        raise
    finally:
        lock.release()
