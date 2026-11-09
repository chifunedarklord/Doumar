"""Three-way merge of independent workspace items; overlapping edits conflict."""
from collections import Counter
from copy import deepcopy
import json
from core.snapshot import validate_snapshot

MISSING = object()


def encoded(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'))


def choose(base, local, remote):
    if local == remote:
        return local
    if local == base:
        return remote
    if remote == base:
        return local
    raise ValueError('Cùng một mục đã thay đổi trên hai thiết bị.')


def merge_snapshots(base, local, remote):
    result = {'format': 'taskflow-workspace', 'version': 1}
    try:
        for group in ('tasks', 'blocks', 'sessions', 'trash', 'memories'):
            def index(snapshot):
                return {(item['memory_type'], item['key']) if group == 'memories' else item['id']: item
                        for item in snapshot.get(group, [])}
            before, left, right = index(base), index(local), index(remote)
            result[group] = []
            for key in sorted(set(before) | set(left) | set(right)):
                item = choose(before.get(key, MISSING), left.get(key, MISSING), right.get(key, MISSING))
                if item is not MISSING:
                    result[group].append(deepcopy(item))
        profiles = [snapshot.get('profile', {}) for snapshot in (base, local, remote)]
        result['profile'] = {}
        for key in set().union(*(profile.keys() for profile in profiles)):
            value = choose(*(profile.get(key, MISSING) for profile in profiles))
            if value is not MISSING:
                result['profile'][key] = value
        counts = [Counter(encoded(item) for item in snapshot.get('messages', [])) for snapshot in (base, local, remote)]
        result['messages'] = []
        for key in sorted(set().union(*counts)):
            number = choose(*(count.get(key, 0) for count in counts))
            result['messages'].extend(json.loads(key) for _ in range(number))
        result['messages'].sort(key=lambda item: (item['timestamp'], item['session_id']))
        validate_snapshot(result)
        return result
    except (ValueError, TypeError, KeyError):
        return None
