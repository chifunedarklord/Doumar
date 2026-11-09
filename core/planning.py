"""Local scheduling proposals with fixed-event conflict avoidance."""
from datetime import date, datetime, timedelta


def propose_day(tasks, fixed_blocks, selected_day, work_start="08:00", work_end="18:00", now=None):
    target = date.fromisoformat(selected_day)
    now = now or datetime.now()
    if target < now.date():
        raise ValueError("Hãy chọn hôm nay hoặc một ngày sắp tới.")
    start = datetime.fromisoformat(selected_day + "T" + work_start)
    finish = datetime.fromisoformat(selected_day + "T" + work_end)
    if finish <= start:
        raise ValueError("Giờ kết thúc cần sau giờ bắt đầu trong cùng ngày.")
    cursor = max(start, now.replace(second=0, microsecond=0) + timedelta(minutes=int(bool(now.second or now.microsecond)))) if target == now.date() else start
    occupied = sorted((datetime.fromisoformat(item["start_at"]) - timedelta(minutes=10),
                       datetime.fromisoformat(item["end_at"]) + timedelta(minutes=10)) for item in fixed_blocks)
    gaps = []
    free_start = start
    for begin, end in occupied:
        if end <= start or begin >= finish:
            continue
        begin, end = max(start, begin), min(finish, end)
        if begin > free_start:
            gaps.append((free_start, begin))
        free_start = max(free_start, end)
    if free_start < finish:
        gaps.append((free_start, finish))
    priorities = {"high": 0, "medium": 1, "low": 2}
    active = [task for task in tasks if task.status not in ("done", "cancelled")]
    active.sort(key=lambda task: (
        0 if task.due_date and task.due_date < selected_day else 1 if task.due_date == selected_day else 2,
        priorities.get(task.priority, 1), task.due_date or "9999", task.estimated_minutes,
    ))
    blocks, unscheduled = [], []
    completed = {task.id for task in tasks if task.status == 'done'}
    queue = list(active)
    ordered = []
    while queue:
        ready = next((task for task in queue if all(dep in completed or dep in {item.id for item in ordered} for dep in task.dependencies)), None)
        if ready is None:
            unscheduled.extend(task.title for task in queue)
            break
        ordered.append(ready)
        queue.remove(ready)
    placed = set(completed)
    for task in ordered:
        if any(dep not in placed for dep in task.dependencies):
            unscheduled.append(task.title)
            continue
        if task.start_date and task.start_date > selected_day:
            unscheduled.append(task.title)
            continue
        remaining = max(1, int(task.estimated_minutes))
        pending, candidate = [], cursor
        for gap_start, gap_end in gaps:
            if task.deadline_type == 'hard' and task.due_date:
                deadline = datetime.fromisoformat(task.due_date + 'T' + (task.due_time or '23:59'))
                gap_end = min(gap_end, deadline)
            candidate = max(candidate, gap_start)
            while remaining and candidate < gap_end:
                length = min(90, remaining, int((gap_end - candidate).total_seconds() // 60))
                if length <= 0:
                    break
                end = candidate + timedelta(minutes=length)
                pending.append({"task_id": task.id, "task_revision": getattr(task, "updated_at", None),
                                "title": task.title, "start_at": candidate.isoformat(), "end_at": end.isoformat()})
                remaining -= length
                candidate = end + timedelta(minutes=10)
            if not remaining:
                break
        if remaining:
            unscheduled.append(task.title)
        else:
            blocks.extend(pending)
            placed.add(task.id)
            cursor = candidate
    return {"blocks": blocks, "unscheduled": unscheduled}
