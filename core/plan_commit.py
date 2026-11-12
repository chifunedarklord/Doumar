"""Confirm AI suggestions atomically; never move an existing calendar entry."""
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import uuid

from core.models import Task
from core.orm import SessionLocal, TaskModel, ScheduleBlockModel, UserModel
from core.workspace import validate_task


def _work_slot(item, default_minutes, title):
    start, end = item.get('start_at'), item.get('end_at')
    if end and not start:
        raise ValueError('Thiếu giờ bắt đầu. Hãy yêu cầu AI sửa kế hoạch.')
    if not start:
        return None
    begin = datetime.fromisoformat(start)
    minutes = item.get('estimated_minutes') or default_minutes
    finish = datetime.fromisoformat(end) if end else begin + timedelta(minutes=minutes)
    if begin.tzinfo or finish.tzinfo or finish <= begin or finish.date() != begin.date():
        raise ValueError('Giờ thực hiện cần hợp lệ và nằm trong cùng một ngày.')
    return begin, finish, title


def save_suggestion(user_id, item, suggestion_id):
    task_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f'doumar-plan:{user_id}:{suggestion_id}'))
    minutes = item.get('estimated_minutes') or 30
    task = Task(id=task_id, user_id=user_id, title=item.get('title') or '',
                description=item.get('description') or '', category=item.get('category') or 'personal',
                priority=item.get('priority') or 'medium', due_date=item.get('due_date'),
                due_time=item.get('due_time'), estimated_minutes=minutes,
                subtasks=deepcopy(item.get('subtasks') or []))
    for sub in task.subtasks:
        sub['id'] = str(uuid.uuid4())
        sub['status'] = 'todo'
        sub.pop('done', None)
    validate_task(task)
    slots = []
    parent_slot = _work_slot(item, minutes, task.title)
    if parent_slot:
        slots.append(parent_slot)
    for sub in task.subtasks:
        slot = _work_slot(sub, 30, task.title + ' · ' + sub['title'])
        if slot:
            if parent_slot:
                raise ValueError('Chỉ xếp giờ cho công việc cha hoặc các việc nhỏ để tránh chiếm lịch hai lần.')
            child_day = sub.get('due_date') or task.due_date
            child_time = sub.get('due_time') or (task.due_time if not sub.get('due_date') else None)
            if child_day and slot[1] > datetime.fromisoformat(child_day + 'T' + (child_time or '23:59:59')):
                raise ValueError('Giờ thực hiện việc nhỏ vượt hạn. Hãy điều chỉnh trước khi lưu.')
            slots.append(slot)
    slots.sort(key=lambda slot: slot[0])
    for before, after in zip(slots, slots[1:]):
        if before[1] > after[0]:
            raise ValueError('Các việc nhỏ trùng giờ. Hãy yêu cầu AI điều chỉnh.')
    for begin, finish, title in slots:
        if task.due_date and finish > datetime.fromisoformat(task.due_date + 'T' + (task.due_time or '23:59:59')):
            raise ValueError('Giờ thực hiện vượt hạn chót. Hãy điều chỉnh trước khi lưu.')
    if slots:
        task.start_date = slots[0][0].date().isoformat()
    with SessionLocal.begin() as db:
        if db.bind.dialect.name == 'sqlite':
            from sqlalchemy import text
            db.execute(text('BEGIN IMMEDIATE'))
        # Serialize confirmations for the same account on SQL databases as well.
        account = db.query(UserModel).filter_by(id=user_id).with_for_update().first()
        if account is None:
            raise ValueError('Không tìm thấy tài khoản hiện tại.')
        previous = db.get(TaskModel, task_id)
        if previous:
            if previous.user_id != user_id:
                raise ValueError('Công việc không thuộc tài khoản hiện tại.')
            return False
        now = datetime.now(ZoneInfo(account.timezone or 'Asia/Ho_Chi_Minh')).replace(tzinfo=None)
        blocks = db.query(ScheduleBlockModel).filter_by(user_id=user_id).all()
        for begin, finish, title in slots:
            if begin < now.replace(second=0, microsecond=0):
                raise ValueError('Giờ bắt đầu đã qua. Hãy yêu cầu AI cập nhật kế hoạch.')
            if any(begin < datetime.fromisoformat(row.end_at) and datetime.fromisoformat(row.start_at) < finish for row in blocks):
                raise ValueError('Giờ này trùng lịch đã lưu. Hãy yêu cầu AI chọn giờ trống khác.')
        db.add(TaskModel(**asdict(task)))
        for index, (begin, finish, title) in enumerate(slots):
            db.add(ScheduleBlockModel(id=str(uuid.uuid5(uuid.NAMESPACE_URL, task_id + f':calendar:{index}')),
                user_id=user_id, task_id=task_id, title=title,
                start_at=begin.isoformat(), end_at=finish.isoformat(), source='manual'))
    # A post-commit analytics/cache failure must never be reported as a failed save.
    try:
        from utils.ai_helper import invalidate_context_cache
        from core.services import BehaviorService, AnalyticsService
        invalidate_context_cache(user_id)
        AnalyticsService.invalidate_cache(user_id)
        BehaviorService.log(user_id, 'plan_save_tasks', {'task_id': task_id, 'scheduled': bool(slots)})
    except Exception:
        import logging
        logging.getLogger(__name__).exception('Saved plan; analytics refresh failed')
    return True
