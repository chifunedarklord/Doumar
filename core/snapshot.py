"""Validation of the account workspace wire format, independent of the database."""
from datetime import date, datetime
from core.models import Task

MEMORY_TYPES = ('project', 'recurrence', 'preference', 'habit', 'goal', 'state', 'performance')


def string(value, limit=500, empty=False):
    if not isinstance(value, str) or len(value) > limit or (not empty and not value.strip()):
        raise ValueError('Dữ liệu văn bản đồng bộ không hợp lệ.')
    return value


def validate_snapshot(payload):
    if not isinstance(payload, dict) or payload.get('format') != 'taskflow-workspace' or payload.get('version') != 1:
        raise ValueError('Dữ liệu đồng bộ không đúng định dạng.')
    profile = payload.get('profile', {})
    if profile:
        if not isinstance(profile, dict) or set(profile) != {'full_name', 'work_start', 'work_end', 'timezone'}:
            raise ValueError('Thông tin tài khoản đồng bộ không hợp lệ.')
        string(profile['full_name'], 200, True)
        string(profile['timezone'], 50)
        begin, finish = (datetime.strptime(profile[key], '%H:%M') for key in ('work_start', 'work_end'))
        if finish <= begin:
            raise ValueError('Giờ làm việc đồng bộ không hợp lệ.')
    for key in ('tasks', 'memories', 'sessions', 'messages', 'blocks', 'trash'):
        items = payload.get(key, [])
        if not isinstance(items, list) or len(items) > 10000 or any(not isinstance(item, dict) for item in items):
            raise ValueError('Dữ liệu đồng bộ vượt giới hạn hoặc sai định dạng.')
    identities = {}
    for key in ('tasks', 'sessions', 'blocks', 'trash'):
        ids = [string(item.get('id'), 128) for item in payload.get(key, [])]
        if len(ids) != len(set(ids)):
            raise ValueError('Dữ liệu đồng bộ trùng mã định danh.')
        identities[key] = set(ids)
    for raw in payload.get('tasks', []) + [row.get('payload', {}) for row in payload.get('trash', [])]:
        task = Task(**raw)
        string(task.id, 128)
        string(task.title)
        for field in ('description', 'notes'):
            string(getattr(task, field), 60000, True)
        if task.status not in ('todo', 'in_progress', 'done', 'cancelled') or task.priority not in ('low', 'medium', 'high'):
            raise ValueError('Công việc đồng bộ có trạng thái không hợp lệ.')
        if type(task.estimated_minutes) is not int or not 1 <= task.estimated_minutes <= 10080 or type(task.reminder_minutes) is not int or not 0 <= task.reminder_minutes <= 525600:
            raise ValueError('Thời lượng công việc đồng bộ không hợp lệ.')
        for value in (task.due_date, task.start_date):
            if value:
                date.fromisoformat(value)
        if task.due_time:
            datetime.strptime(task.due_time, '%H:%M')
        for value in (task.created_at, task.updated_at):
            datetime.fromisoformat(value)
        if not isinstance(task.tags, list) or len(task.tags) > 100 or any(not isinstance(tag, str) or len(tag) > 200 for tag in task.tags):
            raise ValueError('Nhãn công việc không hợp lệ.')
        if not isinstance(task.dependencies, list) or any(not isinstance(item, str) for item in task.dependencies):
            raise ValueError('Phụ thuộc công việc không hợp lệ.')
        if not isinstance(task.subtasks, list) or len(task.subtasks) > 200 or any(not isinstance(item, dict) or not isinstance(item.get('title'), str) for item in task.subtasks):
            raise ValueError('Việc con không hợp lệ.')
        if task.is_recurring and task.recur_pattern not in ('daily', 'weekly', 'monthly'):
            raise ValueError('Chu kỳ lặp không hợp lệ.')
    if identities['tasks'] & identities['trash']:
        raise ValueError('Công việc vừa tồn tại vừa nằm trong Thùng rác.')
    for raw in payload.get('trash', []):
        if raw['id'] != raw['payload']['id']:
            raise ValueError('Mã công việc trong Thùng rác không khớp.')
        datetime.fromisoformat(raw['deleted_at'])
    for raw in payload.get('blocks', []):
        begin, end = datetime.fromisoformat(raw['start_at']), datetime.fromisoformat(raw['end_at'])
        if begin.tzinfo or end.tzinfo or end <= begin or raw.get('source') not in ('proposal', 'manual') or (raw.get('task_id') and raw['task_id'] not in identities['tasks']):
            raise ValueError('Khoảng lịch đồng bộ không hợp lệ.')
        string(raw['title'])
    for raw in payload.get('sessions', []):
        string(raw['title'], 500, True)
        datetime.fromisoformat(raw['created_at'])
        datetime.fromisoformat(raw['updated_at'])
    for raw in payload.get('messages', []):
        if raw.get('session_id') not in identities['sessions'] or raw.get('role') not in ('user', 'model', 'assistant'):
            raise ValueError('Tin nhắn đồng bộ không hợp lệ.')
        string(raw['text'], 100000, True)
        datetime.fromisoformat(raw['timestamp'])
    memory_keys = set()
    for raw in payload.get('memories', []):
        if raw.get('memory_type') not in MEMORY_TYPES:
            raise ValueError('Dữ liệu quyền hoặc cấu hình nội bộ không được đồng bộ.')
        key = (raw['memory_type'], string(raw.get('key'), 500))
        if key in memory_keys:
            raise ValueError('Dữ liệu ghi nhớ trùng khóa.')
        memory_keys.add(key)
        string(raw.get('value'), 100000, True)
        if type(raw.get('confidence')) not in (float, int) or not 0 <= raw['confidence'] <= 1:
            raise ValueError('Dữ liệu ghi nhớ không hợp lệ.')
        datetime.fromisoformat(raw['updated_at'])
    return payload
