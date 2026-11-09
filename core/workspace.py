"""Transactional local workspace operations; no cloud or billing simulation."""
from dataclasses import asdict, fields
from datetime import date, datetime, timedelta
import csv
import io
import json
import uuid
import hashlib

from core.models import Task
from core.orm import (SessionLocal, TaskModel, AIMemoryModel, ChatSessionModel,
                      ChatMessageModel, ScheduleBlockModel, TaskTrashModel, UserModel)


def _id(user_id, kind, original):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"taskflow-restore:{user_id}:{kind}:{original}"))


def validate_task(task):
    if not isinstance(task.title, str) or not task.title.strip() or len(task.title) > 500:
        raise ValueError("Tên công việc cần từ 1 đến 500 ký tự.")
    if task.status not in ("todo", "in_progress", "done", "cancelled"):
        raise ValueError("Trạng thái công việc không hợp lệ.")
    if task.priority not in ("low", "medium", "high"):
        raise ValueError("Mức ưu tiên không hợp lệ.")
    for value in (task.due_date, task.start_date):
        if value:
            date.fromisoformat(value)
    if task.due_time:
        datetime.strptime(task.due_time, "%H:%M")
    if type(task.estimated_minutes) is not int or not 1 <= task.estimated_minutes <= 10080:
        raise ValueError("Thời lượng cần từ 1 đến 10080 phút.")
    if type(task.reminder_minutes) is not int or task.reminder_minutes < 0:
        raise ValueError("Thời gian nhắc việc không hợp lệ.")
    if not isinstance(task.tags, list) or len(task.tags) > 100 or any(not isinstance(tag, str) for tag in task.tags):
        raise ValueError("Nhãn công việc không hợp lệ.")
    if not isinstance(task.subtasks, list) or len(task.subtasks) > 200 or any(not isinstance(item, dict) or not isinstance(item.get("title"), str) for item in task.subtasks):
        raise ValueError("Danh sách việc con không hợp lệ.")
    if task.is_recurring and task.recur_pattern not in ("daily", "weekly", "monthly"):
        raise ValueError("Chu kỳ lặp không hợp lệ.")


class Workspace:
    @staticmethod
    def quick_add(user_id, title, start_at, minutes=30, reminder=15):
        """Add one task and its work slot atomically from the tray window."""
        try:
            begin = datetime.strptime(start_at, '%Y-%m-%dT%H:%M')
        except (ValueError, TypeError) as exc:
            raise ValueError('Nhập ngày YYYY-MM-DD và giờ HH:MM hợp lệ.') from exc
        if begin.tzinfo or begin < datetime.now().replace(second=0, microsecond=0):
            raise ValueError('Chọn một giờ bắt đầu sắp tới.')
        if type(minutes) is not int or not 1 <= minutes <= 1440 or type(reminder) is not int or not 0 <= reminder <= 1440:
            raise ValueError('Thời lượng cần 1–1440 phút; nhắc trước cần 0–1440 phút.')
        end = begin + timedelta(minutes=minutes)
        if begin.date() != end.date():
            raise ValueError('Lịch thêm nhanh cần kết thúc trong cùng ngày.')
        task = Task(id=str(uuid.uuid4()), user_id=user_id, title=title.strip(), due_date=begin.date().isoformat(),
                    due_time=begin.strftime('%H:%M'), estimated_minutes=minutes, reminder_minutes=reminder)
        validate_task(task)
        with SessionLocal.begin() as db:
            from core.orm import SessionModel
            session = db.query(SessionModel).first()
            if not session or session.user_id != user_id:
                raise ValueError('Tài khoản đã thay đổi. Hãy mở lại ô thêm nhanh.')
            existing = db.query(ScheduleBlockModel).filter_by(user_id=user_id).all()
            if any(begin.isoformat() < item.end_at and item.start_at < end.isoformat() for item in existing):
                raise ValueError('Giờ này đang trùng một lịch đã lưu. Chọn giờ khác.')
            db.add(TaskModel(**asdict(task)))
            db.add(ScheduleBlockModel(id=str(uuid.uuid4()), user_id=user_id, task_id=task.id, title=task.title,
                start_at=begin.isoformat(), end_at=end.isoformat(), source='manual'))
        return task

    @staticmethod
    def sync_snapshot(user_id):
        with SessionLocal() as db:
            if db.bind.dialect.name == 'sqlite':
                from sqlalchemy import text
                db.execute(text('BEGIN'))
            return Workspace._sync_snapshot(db, user_id)

    @staticmethod
    def _sync_snapshot(db, user_id):
        from core.repositories import Storage
        user = db.get(UserModel, user_id)
        return {'format': 'taskflow-workspace', 'version': 1,
            'profile': {key: getattr(user, key) for key in ('full_name', 'work_start', 'work_end', 'timezone')} if user else {},
            'tasks': [asdict(Storage._orm_to_task(r)) for r in db.query(TaskModel).filter_by(user_id=user_id)],
            'memories': [{k: getattr(r, k) for k in ('memory_type', 'key', 'value', 'confidence', 'updated_at')}
                for r in db.query(AIMemoryModel).filter(AIMemoryModel.user_id == user_id, AIMemoryModel.memory_type.in_(('project', 'recurrence', 'preference', 'habit', 'goal', 'state', 'performance')))],
            'sessions': [{k: getattr(r, k) for k in ('id', 'title', 'created_at', 'updated_at')} for r in db.query(ChatSessionModel).filter_by(user_id=user_id)],
            'messages': [{k: getattr(r, k) for k in ('session_id', 'role', 'text', 'timestamp')} for r in db.query(ChatMessageModel).filter_by(user_id=user_id).order_by(ChatMessageModel.id)],
            'blocks': [{k: getattr(r, k) for k in ('id', 'task_id', 'title', 'start_at', 'end_at', 'source')} for r in db.query(ScheduleBlockModel).filter_by(user_id=user_id)],
            'trash': [{'id': r.id, 'payload': r.payload, 'deleted_at': r.deleted_at} for r in db.query(TaskTrashModel).filter_by(user_id=user_id)]}

    @staticmethod
    def apply_sync_snapshot(user_id, payload, expected_hash):
        """Replace only this account, atomically, preserving stable cross-device IDs."""
        from core.sync import fingerprint
        from core.repositories import Storage
        from core.snapshot import validate_snapshot
        validate_snapshot(payload)
        if payload.get('format') != 'taskflow-workspace' or payload.get('version') != 1:
            raise ValueError('Dữ liệu đồng bộ không đúng định dạng.')
        task_rows, sessions, blocks, trash = [], [], [], []
        for raw in payload.get('tasks', []):
            task = Task(**dict(raw, user_id=user_id))
            validate_task(task)
            task_rows.append(TaskModel(**asdict(task)))
        task_ids = {row.id for row in task_rows}
        if len(task_ids) != len(task_rows):
            raise ValueError('Công việc đồng bộ trùng mã.')
        for raw in payload.get('sessions', []):
            sessions.append(ChatSessionModel(user_id=user_id, **{k: raw[k] for k in ('id', 'title', 'created_at', 'updated_at')}))
        session_ids = {row.id for row in sessions}
        for raw in payload.get('blocks', []):
            start, end = datetime.fromisoformat(raw['start_at']), datetime.fromisoformat(raw['end_at'])
            if end <= start or start.tzinfo or end.tzinfo or (raw.get('task_id') and raw['task_id'] not in task_ids):
                raise ValueError('Khoảng lịch đồng bộ không hợp lệ.')
            blocks.append(ScheduleBlockModel(user_id=user_id, **{k: raw.get(k) for k in ('id', 'task_id', 'title', 'start_at', 'end_at', 'source')}))
        for raw in payload.get('trash', []):
            task = Task(**dict(raw['payload'], user_id=user_id))
            validate_task(task)
            if raw['id'] != task.id:
                raise ValueError('Công việc trong thùng rác không hợp lệ.')
            trash.append(TaskTrashModel(id=task.id, user_id=user_id, payload=asdict(task), deleted_at=raw['deleted_at']))
        # SQLite's write lock prevents a background edit racing the comparison
        # and replacement. Reject other DB engines rather than pretend atomicity.
        with SessionLocal() as db:
            if db.bind.dialect.name != 'sqlite':
                raise ValueError('Đồng bộ desktop hiện cần cơ sở dữ liệu SQLite.')
            from sqlalchemy import text
            db.execute(text('BEGIN IMMEDIATE'))
            try:
                # Build the current snapshot on the same transaction/connection.
                current = Workspace._sync_snapshot(db, user_id)
                if fingerprint(current) != expected_hash:
                    raise ValueError('Dữ liệu trên máy vừa thay đổi. Hãy đồng bộ lại.')
                for model, entries in ((TaskModel, task_rows), (ChatSessionModel, sessions), (ScheduleBlockModel, blocks), (TaskTrashModel, trash)):
                    for row in entries:
                        owner = db.get(model, row.id)
                        if owner and owner.user_id != user_id:
                            raise ValueError('Mã dữ liệu xung đột với tài khoản khác.')
                db.expunge_all()
                for model in (ChatMessageModel, ScheduleBlockModel, ChatSessionModel, TaskTrashModel, TaskModel):
                    db.query(model).filter_by(user_id=user_id).delete(synchronize_session=False)
                db.query(AIMemoryModel).filter(AIMemoryModel.user_id == user_id, AIMemoryModel.memory_type.in_(('project', 'recurrence', 'preference', 'habit', 'goal', 'state', 'performance'))).delete(synchronize_session=False)
                db.add_all(task_rows + sessions)
                account = db.get(UserModel, user_id)
                if account and payload.get('profile'):
                    for key in ('full_name', 'work_start', 'work_end', 'timezone'):
                        setattr(account, key, payload['profile'][key])
                db.flush()
                db.add_all(blocks + trash)
                for raw in payload.get('messages', []):
                    if raw['session_id'] not in session_ids or raw['role'] not in ('user', 'model', 'assistant'):
                        raise ValueError('Lịch sử chat đồng bộ không hợp lệ.')
                    db.add(ChatMessageModel(user_id=user_id, **{k: raw[k] for k in ('session_id', 'role', 'text', 'timestamp')}))
                for raw in payload.get('memories', []):
                    if raw['memory_type'] in ('project', 'recurrence', 'preference', 'habit', 'goal', 'state', 'performance'):
                        db.add(AIMemoryModel(user_id=user_id, **{k: raw[k] for k in ('memory_type', 'key', 'value', 'confidence', 'updated_at')}))
                db.commit()
            except Exception:
                db.rollback()
                raise

    @staticmethod
    def delete_project(user_id, project_id):
        with SessionLocal.begin() as db:
            db.query(AIMemoryModel).filter_by(user_id=user_id, memory_type="project", key="project:" + project_id).delete()
            db.query(TaskModel).filter_by(user_id=user_id, project_id=project_id).update({TaskModel.project_id: None})

    @staticmethod
    def pending_reminders(user_id, now=None, catchup_seconds=300):
        """Return due reminders in a five-minute delivery window, including work slots."""
        now = now or datetime.now()
        candidates = []
        with SessionLocal() as db:
            tasks = {row.id: row for row in db.query(TaskModel).filter_by(user_id=user_id).all()}
            for task in tasks.values():
                if task.status in ("done", "cancelled") or task.reminder_minutes <= 0 or not task.due_date or not task.due_time:
                    continue
                when = datetime.fromisoformat(task.due_date + "T" + task.due_time) - timedelta(minutes=task.reminder_minutes)
                candidates.append(("task:" + task.id + ":" + when.isoformat(), task.title, when))
            for block in db.query(ScheduleBlockModel).filter_by(user_id=user_id).all():
                task = tasks.get(block.task_id)
                if block.task_id and (task is None or task.status in ("done", "cancelled")):
                    continue
                lead = task.reminder_minutes if task else 0
                when = datetime.fromisoformat(block.start_at) - timedelta(minutes=lead)
                identity = "task:" + block.task_id if block.task_id else "event:" + block.title.strip().casefold()
                candidates.append((identity + ":" + when.isoformat(), block.title, when))
            result, seen = [], set()
            for identifier, title, when in candidates:
                if not 0 <= (now - when).total_seconds() <= catchup_seconds:
                    continue
                key = hashlib.sha256(identifier.encode()).hexdigest()
                if key in seen:
                    continue
                seen.add(key)
                if db.query(AIMemoryModel.id).filter_by(user_id=user_id, memory_type="reminder_sent", key=key).first() is None:
                    result.append({"key": key, "title": title, "when": when.isoformat()})
            return result

    @staticmethod
    def mark_reminded(user_id, key):
        from core.repositories import Storage
        Storage.set_memory(user_id, "reminder_sent", key, datetime.now().isoformat(), 1.0)

    @staticmethod
    def blocks(user_id, day=None):
        with SessionLocal() as db:
            query = db.query(ScheduleBlockModel).filter_by(user_id=user_id)
            if day:
                query = query.filter(ScheduleBlockModel.start_at >= day + "T00:00",
                                     ScheduleBlockModel.start_at < (date.fromisoformat(day) + timedelta(days=1)).isoformat() + "T00:00")
            return [{key: getattr(row, key) for key in ("id", "task_id", "title", "start_at", "end_at", "source")}
                    for row in query.order_by(ScheduleBlockModel.start_at).all()]

    @staticmethod
    def save_blocks(user_id, blocks, replace_day=None):
        validated = []
        for block in blocks:
            start, end = datetime.fromisoformat(block["start_at"]), datetime.fromisoformat(block["end_at"])
            if start.tzinfo or end.tzinfo or end <= start or start.date() != end.date():
                raise ValueError("Khoảng thời gian phải hợp lệ và trong cùng một ngày.")
            if replace_day and start.date().isoformat() != replace_day:
                raise ValueError("Lịch đề xuất chứa ngày không phù hợp.")
            if replace_day and start < datetime.now():
                raise ValueError("Lịch đề xuất đã qua giờ bắt đầu. Hãy tạo lại đề xuất.")
            if not str(block.get("title", "")).strip():
                raise ValueError("Hãy nhập tên lịch.")
            validated.append(dict(block, start_at=start.isoformat(), end_at=end.isoformat()))
        validated.sort(key=lambda item: item["start_at"])
        for first, following in zip(validated, validated[1:]):
            if first["end_at"] > following["start_at"]:
                raise ValueError("Các khoảng thời gian bị trùng nhau.")
        with SessionLocal.begin() as db:
            existing = db.query(ScheduleBlockModel).filter_by(user_id=user_id).all()
            if replace_day:
                existing = [row for row in existing if not (row.start_at[:10] == replace_day and row.source == "proposal" and datetime.fromisoformat(row.start_at) >= datetime.now())]
            for block in validated:
                task_id = block.get("task_id")
                if task_id:
                    task = db.query(TaskModel).filter_by(id=task_id, user_id=user_id).first()
                    if task is None or task.status in ("done", "cancelled") or (block.get("task_revision") and task.updated_at != block["task_revision"]):
                        raise ValueError("Công việc đã thay đổi. Hãy tạo lại lịch đề xuất.")
                if any(block["start_at"] < row.end_at and row.start_at < block["end_at"] for row in existing):
                    raise ValueError("Lịch trùng với một khoảng thời gian đã lưu. Hãy điều chỉnh trước khi áp dụng.")
            if replace_day:
                db.query(ScheduleBlockModel).filter_by(user_id=user_id, source="proposal").filter(
                    ScheduleBlockModel.start_at >= max(replace_day + "T00:00", datetime.now().isoformat()),
                    ScheduleBlockModel.start_at < (date.fromisoformat(replace_day) + timedelta(days=1)).isoformat() + "T00:00",
                ).delete(synchronize_session=False)
            for block in validated:
                db.add(ScheduleBlockModel(id=str(uuid.uuid4()), user_id=user_id,
                    task_id=block.get("task_id"), title=str(block["title"])[:500],
                    start_at=block["start_at"], end_at=block["end_at"],
                    source="proposal" if replace_day else "manual"))

    @staticmethod
    def delete_block(user_id, block_id):
        with SessionLocal.begin() as db:
            db.query(ScheduleBlockModel).filter_by(user_id=user_id, id=block_id).delete()

    @staticmethod
    def trash_task(user_id, task_id):
        from core.repositories import Storage
        with SessionLocal.begin() as db:
            row = db.query(TaskModel).filter_by(id=task_id, user_id=user_id).first()
            if row is None:
                raise ValueError("Không tìm thấy công việc của tài khoản này.")
            old = db.get(TaskTrashModel, task_id)
            if old and old.user_id != user_id:
                raise ValueError("Công việc không thuộc tài khoản hiện tại.")
            if old:
                db.delete(old)
                db.flush()
            db.add(TaskTrashModel(id=task_id, user_id=user_id,
                                 payload=asdict(Storage._orm_to_task(row)), deleted_at=datetime.now().isoformat()))
            db.query(ScheduleBlockModel).filter_by(user_id=user_id, task_id=task_id).delete()
            db.delete(row)

    @staticmethod
    def trash(user_id):
        with SessionLocal() as db:
            return [{"id": row.id, "title": row.payload.get("title", ""), "deleted_at": row.deleted_at}
                    for row in db.query(TaskTrashModel).filter_by(user_id=user_id).order_by(TaskTrashModel.deleted_at.desc()).all()]

    @staticmethod
    def restore_task(user_id, task_id):
        with SessionLocal.begin() as db:
            row = db.query(TaskTrashModel).filter_by(id=task_id, user_id=user_id).first()
            if row is None or db.get(TaskModel, task_id):
                raise ValueError("Không thể khôi phục công việc này.")
            task = Task(**row.payload)
            task.user_id = user_id
            validate_task(task)
            db.add(TaskModel(**asdict(task)))
            db.delete(row)

    @staticmethod
    def backup(user_id):
        from core.repositories import Storage
        with SessionLocal() as db:
            tasks = [asdict(Storage._orm_to_task(row)) for row in db.query(TaskModel).filter_by(user_id=user_id).all()]
            memories = [{"memory_type": row.memory_type, "key": row.key, "value": row.value,
                         "confidence": row.confidence, "updated_at": row.updated_at}
                        for row in db.query(AIMemoryModel).filter(AIMemoryModel.user_id == user_id,
                            AIMemoryModel.memory_type.in_(('project', 'recurrence', 'preference', 'habit', 'goal', 'state', 'performance'))).all()]
            sessions = [{key: getattr(row, key) for key in ("id", "title", "created_at", "updated_at")}
                        for row in db.query(ChatSessionModel).filter_by(user_id=user_id).all()]
            messages = [{key: getattr(row, key) for key in ("session_id", "role", "text", "timestamp")}
                        for row in db.query(ChatMessageModel).filter_by(user_id=user_id).order_by(ChatMessageModel.id).all()]
            blocks = [{key: getattr(row, key) for key in ("id", "task_id", "title", "start_at", "end_at", "source")}
                      for row in db.query(ScheduleBlockModel).filter_by(user_id=user_id).all()]
        return {"format": "taskflow-workspace", "version": 1, "exported_at": datetime.now().isoformat(),
                "tasks": tasks, "memories": memories, "sessions": sessions, "messages": messages, "blocks": blocks}

    @staticmethod
    def restore(user_id, payload):
        """Additive, transactional import; repeat imports of one file are idempotent.

        IDs are namespaced to the signed-in local account; no account/password or
        entitlement data is imported. Existing account items are not deleted.
        """
        if not isinstance(payload, dict) or payload.get("format") != "taskflow-workspace" or payload.get("version") != 1:
            raise ValueError("Tệp sao lưu không đúng định dạng TaskFlow phiên bản 1.")
        for key in ("tasks", "memories", "sessions", "messages", "blocks"):
            if not isinstance(payload.get(key, []), list) or len(payload.get(key, [])) > 50000:
                raise ValueError("Tệp sao lưu có dữ liệu không hợp lệ hoặc quá lớn.")
        task_keys = {field.name for field in fields(Task)}
        tasks = []
        project_map = {item["key"][8:]: _id(user_id, "project", item["key"][8:])
                       for item in payload.get("memories", []) if item.get("memory_type") == "project" and item.get("key", "").startswith("project:")}
        for raw in payload.get("tasks", []):
            if not isinstance(raw, dict):
                raise ValueError("Công việc trong tệp sao lưu không hợp lệ.")
            data = {key: value for key, value in raw.items() if key in task_keys}
            data.update(id=_id(user_id, "task", raw["id"]), user_id=user_id)
            data["dependencies"] = [_id(user_id, "task", value) for value in raw.get("dependencies", [])]
            if data.get("project_id"):
                data["project_id"] = project_map.get(data["project_id"])
            task = Task(**data)
            validate_task(task)
            tasks.append(task)
        session_ids = {item["id"] for item in payload.get("sessions", [])}
        with SessionLocal.begin() as db:
            for task in tasks:
                existing = db.get(TaskModel, task.id)
                if existing and existing.user_id != user_id:
                    raise ValueError("Tệp sao lưu xung đột dữ liệu tài khoản.")
                db.merge(TaskModel(**asdict(task)))
            for item in payload.get("memories", []):
                kind, key = item["memory_type"], item["key"]
                if kind == "project" and key.startswith("project:"):
                    key = "project:" + project_map[key[8:]]
                if kind == "recurrence" and key.startswith("next:"):
                    key = "next:" + _id(user_id, "task", key[5:])
                    item = dict(item, value=_id(user_id, "task", item["value"]))
                if kind not in ("project", "recurrence", "preference", "habit", "goal", "state", "performance"):
                    continue
                row = db.query(AIMemoryModel).filter_by(user_id=user_id, memory_type=kind, key=key).first()
                if row is None:
                    row = AIMemoryModel(user_id=user_id, memory_type=kind, key=key)
                    db.add(row)
                row.value = item["value"] if isinstance(item["value"], str) else json.dumps(item["value"], ensure_ascii=False)
                row.confidence = float(item.get("confidence", .5))
                row.updated_at = datetime.now().isoformat()
            for item in payload.get("sessions", []):
                sid = _id(user_id, "chat", item["id"])
                existing = db.get(ChatSessionModel, sid)
                if existing and existing.user_id != user_id:
                    raise ValueError("Lịch sử chat xung đột tài khoản.")
                db.merge(ChatSessionModel(id=sid, user_id=user_id, title=item["title"], created_at=item["created_at"], updated_at=item["updated_at"]))
                db.query(ChatMessageModel).filter_by(user_id=user_id, session_id=sid).delete()
            db.flush()
            for item in payload.get("messages", []):
                if item["session_id"] not in session_ids or item["role"] not in ("user", "model", "assistant"):
                    raise ValueError("Lịch sử trò chuyện trong tệp không hợp lệ.")
                db.add(ChatMessageModel(user_id=user_id, session_id=_id(user_id, "chat", item["session_id"]),
                                        role=item["role"], text=item["text"], timestamp=item["timestamp"]))
            for item in payload.get("blocks", []):
                start, end = datetime.fromisoformat(item["start_at"]), datetime.fromisoformat(item["end_at"])
                if end <= start or start.tzinfo or end.tzinfo:
                    raise ValueError("Lịch trong tệp không hợp lệ.")
                bid = _id(user_id, "block", item["id"])
                existing = db.get(ScheduleBlockModel, bid)
                if existing and existing.user_id != user_id:
                    raise ValueError("Lịch xung đột tài khoản.")
                db.merge(ScheduleBlockModel(id=bid, user_id=user_id, title=item["title"],
                    task_id=_id(user_id, "task", item["task_id"]) if item.get("task_id") else None,
                    start_at=start.isoformat(), end_at=end.isoformat(), source=item.get("source", "manual")))
        return {"tasks": len(tasks), "conversations": len(session_ids)}

    @staticmethod
    def export_csv(user_id):
        from core.services import TaskService
        output = io.StringIO(newline="")
        writer = csv.writer(output)
        writer.writerow(["Tên công việc", "Trạng thái", "Ưu tiên", "Ngày hạn", "Giờ hạn", "Thời lượng (phút)", "Nhãn"])
        for task in TaskService.get_tasks(user_id):
            values = [task.title, task.status, task.priority, task.due_date or "", task.due_time or "", task.estimated_minutes, ", ".join(task.tags)]
            writer.writerow(["'" + value if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")) else value for value in values])
        return output.getvalue().encode("utf-8-sig")
