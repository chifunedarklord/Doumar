"""Pure recurrence rules shared by creation, editing and completion."""
import calendar
from datetime import date, timedelta, datetime
from dataclasses import replace
from copy import deepcopy
import uuid


def next_occurrence(task, today=None):
    if not task.is_recurring or task.status != "done":
        return None
    if task.recur_pattern not in ("daily", "weekly", "monthly"):
        raise ValueError("Chu kỳ lặp lại không hợp lệ.")
    today = today or date.today()
    base = date.fromisoformat(task.due_date) if task.due_date else today
    if task.recur_pattern in ("daily", "weekly"):
        step = 1 if task.recur_pattern == "daily" else 7
        jumps = max(1, (today - base).days // step + 1)
        following = base + timedelta(days=jumps * step)
    else:
        months = max(1, (today.year - base.year) * 12 + today.month - base.month)
        while True:
            month_index = base.year * 12 + base.month - 1 + months
            year, month = divmod(month_index, 12)
            month += 1
            following = date(year, month, min(base.day, calendar.monthrange(year, month)[1]))
            if following > today:
                break
            months += 1
    now = datetime.now().isoformat()
    subtasks = deepcopy(task.subtasks)
    for subtask in subtasks:
        subtask["status"] = "todo"
        if "done" in subtask:
            subtask["done"] = False
    return replace(task,
        id=str(uuid.uuid5(uuid.NAMESPACE_URL, f"taskflow-next:{task.user_id}:{task.id}")),
        due_date=following.isoformat(), status="todo", completed_at=None,
        created_at=now, updated_at=now, subtasks=subtasks, actual_minutes=0,
        postpone_count=0, interruption_count=0, focus_score=0,
    )
