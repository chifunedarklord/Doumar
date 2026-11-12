"""Account-scoped focus targets bound to stable child IDs and real work sessions."""
from copy import deepcopy
from datetime import datetime
import json
import uuid

from core.database import Storage
from core.orm import SessionLocal, UserModel, TaskModel, WorkSessionModel
from core.task_rules import subtask_done


def _changed(user_id, event, data):
    try:
        from core.services import BehaviorService, AnalyticsService
        from utils.ai_helper import invalidate_context_cache
        invalidate_context_cache(user_id)
        AnalyticsService.invalidate_cache(user_id)
        BehaviorService.log(user_id, event, data)
    except Exception:
        import logging
        logging.getLogger(__name__).exception('Focus saved; analytics refresh failed')


def _lock(db, user_id):
    if db.bind.dialect.name == 'sqlite':
        from sqlalchemy import text
        db.execute(text('BEGIN IMMEDIATE'))
    if db.query(UserModel).filter_by(id=user_id).with_for_update().first() is None:
        raise ValueError('Không tìm thấy tài khoản hiện tại.')


def _describe(row):
    try:
        metadata = json.loads(row.notes or '{}')
        if not isinstance(metadata, dict):
            metadata = {}
    except (ValueError, TypeError):
        metadata = {}
    return dict(session_id=row.id, task_id=row.task_id, started_at=row.started_at,
                subtask_id=metadata.get('subtask_id'), title=metadata.get('title') or 'Phiên tập trung',
                parent_title=metadata.get('parent_title') or '')


class TaskFocus:
    @staticmethod
    def task(user_id, task_id):
        task = next((t for t in Storage.get_tasks(user_id) if t.id == task_id), None)
        if task is None:
            raise ValueError('Công việc không còn tồn tại hoặc không thuộc tài khoản này.')
        return task

    @staticmethod
    def ensure_ids(user_id, task_id):
        task = TaskFocus.task(user_id, task_id)
        seen = set()
        changed = False
        for child in task.subtasks:
            if not child.get('id') or child['id'] in seen:
                child['id'] = str(uuid.uuid4())
                changed = True
            seen.add(child['id'])
        if changed:
            from core.services import TaskService
            TaskService.save_task(task, expected_revision=task.updated_at)
        return task

    @staticmethod
    def set_done(user_id, task_id, child_id, done):
        from core.services import TaskService
        task = TaskFocus.task(user_id, task_id)
        child = next((s for s in task.subtasks if s.get('id') == child_id), None)
        if child is None:
            raise ValueError('Việc nhỏ đã thay đổi. Hãy mở lại thư mục.')
        if task.status == 'cancelled':
            raise ValueError('Công việc đã hủy. Hãy khôi phục trước khi cập nhật.')
        child['status'], child['done'] = ('done' if done else 'todo'), bool(done)
        child['completed_at'] = (child.get('completed_at') or datetime.now().isoformat()) if done else None
        TaskService.save_task(task, expected_revision=task.updated_at)
        active = TaskFocus.current(user_id)
        if done and active and active['task_id'] == task_id and active['subtask_id'] == child_id:
            TaskFocus.stop(user_id, active['session_id'])
        _changed(user_id, 'subtask_complete' if done else 'subtask_reopen', {'task_id':task_id, 'subtask_id':child_id})
        return TaskFocus.task(user_id, task_id)

    @staticmethod
    def set_task_done(user_id, task_id, done):
        from core.services import TaskService
        task = TaskFocus.task(user_id, task_id)
        if task.subtasks:
            raise ValueError('Hãy hoàn thành từng việc nhỏ trong thư mục.')
        if task.status == 'cancelled':
            raise ValueError('Công việc đã hủy. Hãy khôi phục trước khi cập nhật.')
        if (task.status == 'done') != bool(done):
            TaskService.toggle_done(task)
        active = TaskFocus.current(user_id)
        if done and active and active['task_id'] == task_id:
            TaskFocus.stop(user_id, active['session_id'])
        return TaskFocus.task(user_id, task_id)

    @staticmethod
    def add_child(user_id, task_id, title):
        from core.services import TaskService
        if not isinstance(title, str) or not title.strip() or len(title.strip()) > 500:
            raise ValueError('Tên việc nhỏ cần từ 1 đến 500 ký tự.')
        task = TaskFocus.task(user_id, task_id)
        if task.status == 'cancelled':
            raise ValueError('Công việc đã hủy. Hãy khôi phục trước khi thêm việc nhỏ.')
        task.subtasks = deepcopy(task.subtasks) + [dict(id=str(uuid.uuid4()), title=title.strip(), status='todo')]
        TaskService.save_task(task, expected_revision=task.updated_at)
        return task

    @staticmethod
    def current(user_id):
        with SessionLocal() as db:
            row = db.query(WorkSessionModel).filter_by(user_id=user_id, ended_at=None).order_by(WorkSessionModel.started_at.desc()).first()
            return _describe(row) if row else None

    @staticmethod
    def start(user_id, task_id, child_id=None):
        with SessionLocal.begin() as db:
            _lock(db, user_id)
            task = db.query(TaskModel).filter_by(user_id=user_id, id=task_id).first()
            if task is None or task.status in ('done','cancelled'):
                raise ValueError('Chọn một công việc chưa hoàn thành để tập trung.')
            child = next((s for s in task.subtasks or [] if s.get('id') == child_id), None) if child_id else None
            if child_id and (child is None or subtask_done(child)):
                raise ValueError('Việc nhỏ không còn tồn tại hoặc đã hoàn thành.')
            if task.subtasks and not child_id:
                raise ValueError('Hãy chọn một việc nhỏ trong thư mục để tập trung.')
            active = db.query(WorkSessionModel).filter_by(user_id=user_id, ended_at=None).first()
            if active:
                info = _describe(active)
                if info['task_id'] == task_id and info['subtask_id'] == child_id:
                    return info
                raise ValueError('Bạn đang tập trung vào việc khác. Hãy kết thúc phiên đó trước khi đổi mục tiêu.')
            metadata = dict(subtask_id=child_id, title=child['title'] if child else task.title, parent_title=task.title)
            row = WorkSessionModel(id=str(uuid.uuid4()), user_id=user_id, task_id=task_id,
                                   started_at=datetime.now().isoformat(), notes=json.dumps(metadata, ensure_ascii=False))
            db.add(row)
            db.flush()
            result = _describe(row)
        _changed(user_id, 'session_start', dict(task_id=task_id, subtask_id=child_id))
        return result

    @staticmethod
    def stop(user_id, session_id):
        with SessionLocal.begin() as db:
            _lock(db, user_id)
            row = db.query(WorkSessionModel).filter_by(user_id=user_id, id=session_id).first()
            if row is None:
                raise ValueError('Không tìm thấy phiên tập trung của tài khoản này.')
            if row.ended_at:
                return row.duration_minutes
            now = datetime.now()
            row.ended_at = now.isoformat()
            row.duration_minutes = max(0, int((now-datetime.fromisoformat(row.started_at)).total_seconds()//60))
            minutes = row.duration_minutes
            info = _describe(row)
            task = db.query(TaskModel).filter_by(user_id=user_id, id=row.task_id).first()
            if task:
                task.actual_minutes = (task.actual_minutes or 0) + minutes
                children = deepcopy(task.subtasks or [])
                for child in children:
                    if child.get('id') == info['subtask_id']:
                        child['actual_minutes'] = (child.get('actual_minutes') or 0) + minutes
                task.subtasks = children
                task.updated_at = now.isoformat()
        _changed(user_id, 'session_end', dict(task_id=info['task_id'], subtask_id=info['subtask_id'], duration_minutes=minutes, focus_quality=5))
        return minutes
