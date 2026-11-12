"""Pure validation shared by desktop, backup and server sync; no database imports."""
from datetime import date, datetime


def validate_task(task):
    if not isinstance(task.title, str) or not task.title.strip() or len(task.title) > 500:
        raise ValueError("Tên công việc cần từ 1 đến 500 ký tự.")
    if task.status not in ("todo", "in_progress", "done", "cancelled"):
        raise ValueError("Trạng thái công việc không hợp lệ.")
    if task.priority not in ("low", "medium", "high"):
        raise ValueError("Mức ưu tiên không hợp lệ.")
    for value in (task.due_date, task.start_date):
        if value:
            if not isinstance(value, str) or date.fromisoformat(value).isoformat() != value:
                raise ValueError("Ngày cần đúng định dạng YYYY-MM-DD.")
    if task.due_time:
        if not task.due_date:
            raise ValueError("Hãy chọn ngày cho giờ hạn hoàn thành.")
        if datetime.strptime(task.due_time, "%H:%M").strftime('%H:%M') != task.due_time:
            raise ValueError("Giờ cần đúng định dạng HH:MM.")
    if type(task.estimated_minutes) is not int or not 1 <= task.estimated_minutes <= 10080:
        raise ValueError("Thời lượng cần từ 1 đến 10080 phút.")
    if type(task.reminder_minutes) is not int or task.reminder_minutes < 0:
        raise ValueError("Thời gian nhắc việc không hợp lệ.")
    if not isinstance(task.tags, list) or len(task.tags) > 100 or any(not isinstance(tag, str) for tag in task.tags):
        raise ValueError("Nhãn công việc không hợp lệ.")
    if not isinstance(task.subtasks, list) or len(task.subtasks) > 200 or any(not isinstance(item, dict) or not isinstance(item.get("title"), str) for item in task.subtasks):
        raise ValueError("Danh sách việc con không hợp lệ.")
    for item in task.subtasks:
        if item.get('status', 'todo') not in ('todo', 'in_progress', 'done'):
            raise ValueError("Trạng thái việc nhỏ không hợp lệ.")
        if not item['title'].strip() or len(item['title']) > 500:
            raise ValueError("Tên việc nhỏ cần từ 1 đến 500 ký tự.")
        if item.get('estimated_minutes') is not None and (type(item['estimated_minutes']) is not int or not 1 <= item['estimated_minutes'] <= 10080):
            raise ValueError("Thời lượng việc nhỏ cần từ 1 đến 10080 phút hoặc để trống.")
        if item.get('due_date'):
            if date.fromisoformat(item['due_date']).isoformat() != item['due_date']:
                raise ValueError('Hạn việc nhỏ cần đúng định dạng YYYY-MM-DD.')
            if task.due_date and item['due_date'] > task.due_date:
                raise ValueError("Hạn việc nhỏ không được sau hạn công việc cha.")
        if item.get('due_time'):
            if datetime.strptime(item['due_time'], '%H:%M').strftime('%H:%M') != item['due_time']:
                raise ValueError('Giờ việc nhỏ cần đúng định dạng HH:MM.')
            if not (item.get('due_date') or task.due_date):
                raise ValueError("Hãy chọn ngày cho hạn việc nhỏ.")
            child_day = item.get('due_date') or task.due_date
            if task.due_date and child_day == task.due_date and task.due_time and item['due_time'] > task.due_time:
                raise ValueError("Giờ hạn việc nhỏ không được sau hạn công việc cha.")
    if task.is_recurring and task.recur_pattern not in ("daily", "weekly", "monthly"):
        raise ValueError("Chu kỳ lặp không hợp lệ.")
