"""Quiet desktop workspace backed by the existing task services."""
from datetime import date, datetime, timedelta
from dataclasses import replace
import uuid

import flet as ft
from core.models import Task
from core.services import TaskService, ProjectService


def palette(page):
    return {
        "bg": "#FFFFFF",
        "side": "#FAFAFA",
        "text": "#111111",
        "muted": "#666666",
        "line": "#E8E8E8",
        "selected": "#EEEEEE",
    }


def build_tasks(page, user, navigate, register_refresh=None, project_id=None):
    c = palette(page)
    rows = ft.Column(spacing=0)
    state = {"filter": "active", "query": "", "priority": "all", "sort": "due", "project": project_id or "all"}
    count = ft.Text(color=c["muted"], size=13)
    error = ft.Text(color=c["text"], size=13, visible=False)
    focus_area = ft.Column(spacing=0)

    def remove(task):
        def confirm(_):
            try:
                TaskService.delete_task(task.id, user_id=user.id)
                dialog.open = False
                refresh()
                def undo(_):
                    try:
                        from core.workspace import Workspace
                        Workspace.restore_task(user.id, task.id)
                        refresh()
                        notice.open = False
                    except Exception:
                        error.value, error.visible = 'Không hoàn tác được. Hãy mở Thùng rác để khôi phục.', True
                    page.update()
                notice = ft.SnackBar(content=ft.Text('Đã chuyển vào Thùng rác'), action='Hoàn tác', on_action=undo, duration=8000)
                page.overlay.append(notice)
                notice.open = True
                page.update()
            except Exception:
                dialog.content = ft.Text("Không thể xóa. Vui lòng thử lại.")
                page.update()

        def cancel(_):
            dialog.open = False
            page.update()

        dialog = ft.AlertDialog(
            title=ft.Text("Xóa công việc?"),
            content=ft.Text(task.title + "\n\nCông việc sẽ chuyển vào Thùng rác và có thể khôi phục."),
            actions=[ft.TextButton("Hủy", on_click=cancel),
                     ft.TextButton("Xóa", on_click=confirm)],
        )
        page.overlay.append(dialog)
        dialog.open = True
        page.update()

    def refresh(update=True):
        tasks = TaskService.get_tasks(user.id)
        from screens.task_folder_screen import build_focus_panel
        focus_area.controls = [build_focus_panel(page, user, navigate, refresh, compact=True)]
        q = state["query"].casefold()
        today = date.today().isoformat()
        tasks = [task for task in tasks if q in (task.title + " " + (task.description or "") + " " + " ".join(task.tags) + " " + " ".join(child.get('title','') for child in task.subtasks)).casefold()]
        selected = state["filter"]
        if selected == "active":
            tasks = [task for task in tasks if task.status not in ("done", "cancelled")]
        elif selected == "today":
            from core.workspace import Workspace
            scheduled = {item['task_id'] for item in Workspace.blocks(user.id, today)}
            tasks = [task for task in tasks if task.status not in ('done', 'cancelled') and
                     (task.id in scheduled or (task.due_date and task.due_date <= today))]
        elif selected == "done":
            tasks = [task for task in tasks if task.status == "done"]
        elif selected == "overdue":
            tasks = [task for task in tasks if task.is_overdue]
        if state["priority"] != "all":
            tasks = [task for task in tasks if task.priority == state["priority"]]
        if state["project"] != "all":
            tasks = [task for task in tasks if task.project_id == state["project"]]
        priorities = {"high": 0, "medium": 1, "low": 2}
        key = (lambda task: (task.status == "done", priorities.get(task.priority, 1), task.due_date or "9999")) if state["sort"] == "priority" else (lambda task: (task.status == "done", task.due_date or "9999", task.due_time or '23:59', priorities.get(task.priority, 1), task.title.casefold()))
        tasks.sort(key=key)
        count.value = f"{len(tasks)} thư mục"
        rows.controls.clear()
        for task in tasks:
            label = {"high": "Cao", "medium": "Vừa", "low": "Thấp"}.get(task.priority, task.priority)
            rows.controls.append(ft.Container(
                padding=ft.Padding.symmetric(vertical=3),
                border=ft.Border(bottom=ft.BorderSide(1, c["line"])),
                content=ft.Row([
                    ft.IconButton(icon=ft.Icons.FOLDER_OUTLINED, tooltip="Mở thư mục công việc", on_click=lambda e, task=task: navigate('task_folder', task_id=task.id)),
                    ft.Container(expand=True, on_click=lambda e, task=task: navigate("task_folder", task_id=task.id),
                                 content=ft.Text(task.title + (f" · {task.subtask_progress[0]}/{task.subtask_progress[1]}" if task.subtasks else ""), color=c["muted"] if task.status == "done" else c["text"],
                                                 style=ft.TextStyle(decoration=ft.TextDecoration.LINE_THROUGH if task.status == "done" else None),
                                                 size=14, max_lines=2, tooltip=task.title, overflow=ft.TextOverflow.ELLIPSIS)),
                    ft.Text(("Quá hạn · " + date.fromisoformat(task.due_date).strftime("%d/%m" if date.fromisoformat(task.due_date).year == date.today().year else "%d/%m/%Y") if task.is_overdue else task.due_date_display) if task.due_date or task.status == "done" else "—", width=108, size=12,
                            weight=ft.FontWeight.W_600 if task.is_overdue else ft.FontWeight.W_400,
                            color=c["text"] if task.is_overdue else c["muted"]),
                    ft.Text(label, width=70, size=12, color=c["muted"]),
                    ft.PopupMenuButton(tooltip="Thao tác công việc", items=[
                        ft.PopupMenuItem(content=ft.Text("Sửa"), on_click=lambda e, task=task: navigate("task_edit", task=task)),
                        ft.PopupMenuItem(content=ft.Text("Xóa"), on_click=lambda e, task=task: remove(task)),
                        ft.PopupMenuItem(content=ft.Text("Nhân bản"), on_click=lambda e, task=task: duplicate(task)),
                    ]),
                ], spacing=8),
            ))
        if not tasks:
            rows.controls.append(ft.Container(padding=ft.Padding.symmetric(vertical=48, horizontal=16), content=ft.Column([
                ft.Text("Không có công việc phù hợp" if q else "Một khoảng trống cho việc tiếp theo", size=18, color=c["text"]),
                ft.Text("Thử bộ lọc khác hoặc thêm công việc mới.", color=c["muted"]),
                ft.TextButton("Thêm thư mục", on_click=lambda e: navigate("task_edit")),
            ], spacing=12)))
        if update:
            page.update()

    def search(e):
        state["query"] = e.control.value
        refresh()

    def duplicate(task):
        now = datetime.now().isoformat()
        from copy import deepcopy
        children = deepcopy(task.subtasks)
        for child in children:
            child['status'] = 'todo'
            child['done'] = False
            child['id'] = str(uuid.uuid4())
            child.pop('start_at', None)
            child.pop('end_at', None)
        navigate("task_edit", task=replace(task, id=str(uuid.uuid4()), title=task.title + " (bản sao)", subtasks=children,
                  status="todo", completed_at=None, created_at=now, updated_at=now))

    def change_option(e, name):
        state[name] = e.control.value
        refresh()

    def select(e):
        state["filter"] = e.control.value
        refresh()

    quick = ft.TextField(hint_text='Thêm thư mục công việc rồi nhấn Enter', text_size=14, expand=True, tooltip='Ctrl+K: thêm nhanh · Ctrl+N: mở trang thêm công việc')
    def quick_add(_):
        if not quick.value or not quick.value.strip():
            return
        if len(quick.value.strip()) > 500:
            error.value, error.visible = 'Tên công việc tối đa 500 ký tự.', True
            page.update()
            return
        try:
            TaskService.save_task(Task(id=str(uuid.uuid4()), user_id=user.id, title=quick.value.strip()))
            quick.value = ''
            quick_button.disabled = True
            error.value, error.visible = 'Đã thêm thư mục. Bấm tên thư mục để thêm các việc nhỏ.', True
            refresh()
        except Exception:
            error.value, error.visible = 'Không lưu được. Nội dung vẫn được giữ để thử lại.', True
            page.update()
    quick_button = ft.OutlinedButton('Thêm nhanh', icon=ft.Icons.ADD, disabled=True, on_click=quick_add)
    def quick_changed(e):
        quick_button.disabled = not bool((e.control.value or '').strip())
        page.update()
    quick.on_change = quick_changed
    quick.on_submit = quick_add
    async def keyboard(e):
        if e.ctrl and str(e.key).lower() == 'n':
            navigate('task_edit')
        elif e.ctrl and str(e.key).lower() == 'k':
            await quick.focus()
    page.on_keyboard_event = keyboard

    if register_refresh:
        register_refresh(refresh)
    refresh(update=False)
    projects = ProjectService.get_projects(user.id)
    return ft.ListView([
        ft.Text("Công việc", size=30, weight=ft.FontWeight.W_600, color=c["text"]),
        ft.Text("Mở một thư mục để xem các việc nhỏ, hoàn thành hoặc chọn mục tiêu tập trung.", size=14, color=c['muted']),
        count,
        focus_area,
        ft.Row([
            ft.FilledButton("Thêm thư mục", icon=ft.Icons.CREATE_NEW_FOLDER_OUTLINED,
                            on_click=lambda e: navigate("task_edit"),
                            style=ft.ButtonStyle(bgcolor=c['text'], color=c['bg'])),
            ft.TextButton("Lịch", icon=ft.Icons.CALENDAR_TODAY_OUTLINED, on_click=lambda e: navigate("calendar")),
            ft.TextButton("Dự án", icon=ft.Icons.FOLDER_SPECIAL_OUTLINED, on_click=lambda e: navigate("projects")),
            ft.TextButton("Thùng rác", icon=ft.Icons.DELETE_OUTLINE, on_click=lambda e: navigate("trash")),
            ft.TextButton("Làm mới", icon=ft.Icons.REFRESH, on_click=lambda e: refresh()),
        ], spacing=8, run_spacing=8, wrap=True),
        ft.Row([quick, quick_button], spacing=10),
        ft.Row([
            ft.Dropdown(value=state['filter'], width=200, text_size=13, dense=True, border_color=c["line"], border_radius=6, on_select=select, options=[
                ft.DropdownOption("active", "Đang thực hiện"), ft.DropdownOption("today", "Hôm nay"),
                ft.DropdownOption("all", "Tất cả"), ft.DropdownOption("done", "Đã hoàn thành"), ft.DropdownOption("overdue", "Quá hạn")]),
            ft.TextField(hint_text="Tìm công việc…", prefix_icon=ft.Icons.SEARCH, expand=True,
                         text_size=13, dense=True, border_color=c["line"], border_radius=6,
                         content_padding=ft.Padding.symmetric(horizontal=12, vertical=12), on_change=search),
        ]),
        ft.Row([
            ft.Dropdown(value=state["project"], width=190, dense=True, text_size=13, border_color=c["line"],
                options=[ft.DropdownOption("all", "Mọi dự án")] + [ft.DropdownOption(project.id, project.name) for project in projects],
                on_select=lambda e: change_option(e, "project")),
            ft.Dropdown(value="all", width=220, dense=True, text_size=13, border_color=c["line"],
                options=[ft.DropdownOption(key, label) for key, label in [("all", "Mọi mức ưu tiên"), ("high", "Ưu tiên cao"), ("medium", "Ưu tiên vừa"), ("low", "Ưu tiên thấp")]],
                on_select=lambda e: change_option(e, "priority")),
            ft.Dropdown(value="due", width=220, dense=True, text_size=13, border_color=c["line"],
                options=[ft.DropdownOption("due", "Sắp theo hạn"), ft.DropdownOption("priority", "Sắp theo ưu tiên")],
                on_select=lambda e: change_option(e, "sort")),
        ], wrap=True),
        ft.Container(height=4),
        ft.Row([ft.Container(width=48), ft.Text("Thư mục công việc", expand=True, size=12, color=c["muted"]),
                ft.Text("Hạn", width=108, size=12, color=c["muted"]),
                ft.Text("Ưu tiên", width=70, size=12, color=c["muted"]), ft.Container(width=48)], spacing=8),
        ft.Divider(height=1, color=c["line"]),
        rows,
        error,
    ], expand=True, spacing=12)


def build_editor(page, user, navigate, task=None, register_guard=None):
    c = palette(page)
    original = task or Task(id=str(uuid.uuid4()), user_id=user.id, title="", due_date=date.today().isoformat())
    original_exists = any(item.id == original.id for item in TaskService.get_tasks(user.id))
    title = ft.TextField(label="Tên công việc", value=original.title, autofocus=True, text_size=14)
    description = ft.TextField(label="Mô tả", value=original.description, multiline=True, min_lines=4, max_lines=8, text_size=14)
    due = ft.TextField(label="Hạn hoàn thành", hint_text="YYYY-MM-DD", value=original.due_date or "")
    due_time = ft.TextField(label="Giờ", hint_text="HH:MM", value=original.due_time or "")
    priority = ft.Dropdown(label="Ưu tiên", width=375, value=original.priority, options=[ft.DropdownOption(k, v) for k, v in [("low", "Thấp"), ("medium", "Vừa"), ("high", "Cao")]])
    status = ft.Dropdown(label="Trạng thái", width=375, value=original.status, options=[ft.DropdownOption(k, v) for k, v in [("todo", "Chưa làm"), ("in_progress", "Đang làm"), ("done", "Hoàn thành"), ("cancelled", "Đã hủy")]])
    projects = ProjectService.get_projects(user.id)
    project_options = [ft.DropdownOption("", "Không thuộc dự án")]
    project_options.extend(ft.DropdownOption(project.id, project.name) for project in projects)
    if original.project_id and original.project_id not in {project.id for project in projects}:
        project_options.append(ft.DropdownOption(original.project_id, "Dự án đã lưu trước đó"))
    project = ft.Dropdown(label="Dự án", width=375, value=original.project_id or "", options=project_options)
    category = ft.Dropdown(label="Danh mục", width=375, value=original.category, options=[
        ft.DropdownOption(key, label) for key, label in [
            ("work", "Công việc"), ("personal", "Cá nhân"), ("education", "Học tập"),
            ("finance", "Tài chính"), ("health", "Sức khỏe"),
        ]])
    minutes = ft.TextField(label="Thời lượng dự kiến (phút)", value=str(original.estimated_minutes),
                           keyboard_type=ft.KeyboardType.NUMBER, text_size=14)
    reminder = ft.Dropdown(label="Nhắc trước hạn", width=375, value=str(original.reminder_minutes), options=[
        ft.DropdownOption(str(value), label) for value, label in [
            (0, "Không nhắc"), (5, "5 phút"), (15, "15 phút"), (30, "30 phút"),
            (60, "1 giờ"), (1440, "1 ngày"),
        ]])
    if original.reminder_minutes not in (0, 5, 15, 30, 60, 1440):
        reminder.options.append(ft.DropdownOption(str(original.reminder_minutes), f"{original.reminder_minutes} phút"))
    tags = ft.TextField(label="Nhãn", hint_text="Ví dụ: khách hàng, tuần này", value=", ".join(original.tags), text_size=14)
    repeat = ft.Dropdown(label="Lặp lại sau khi hoàn thành", value=original.recur_pattern if original.is_recurring else "none", options=[
        ft.DropdownOption(key, label) for key, label in [("none", "Không lặp"), ("daily", "Hằng ngày"), ("weekly", "Hằng tuần"), ("monthly", "Hằng tháng")]])
    from core.access import access_for
    if not access_for(user.id).allows("recurrence"):
        repeat.label = "Lặp lại · Plus / Pro"
        for option in repeat.options[1:]:
            option.disabled = True
    if not access_for(user.id).allows("projects"):
        project.disabled = True
    from copy import deepcopy
    subtask_data = deepcopy(original.subtasks)
    subtask_view = ft.Column(spacing=6)
    new_subtask = ft.TextField(label="Thêm việc con", expand=True, text_size=13)

    def render_subtasks():
        subtask_view.controls = []
        from core.task_rules import subtask_done
        for index, item in enumerate(subtask_data):
            def move(e, item=item, offset=0):
                position = subtask_data.index(item)
                target = position + offset
                if 0 <= target < len(subtask_data):
                    subtask_data[position], subtask_data[target] = subtask_data[target], subtask_data[position]
                    render_subtasks()
                    page.update()
            def edit(e, item=item, key="title"):
                item[key] = e.control.value.strip() or None
            def number(e, item=item):
                value = e.control.value.strip()
                item['estimated_minutes'] = int(value) if value.isdigit() else value or None
            def toggle(e, item=item):
                item["status"] = "done" if e.control.value else "todo"
                if "done" in item:
                    item["done"] = e.control.value
            def remove(e, item=item):
                subtask_data.remove(item)
                render_subtasks()
                page.update()
            def dropped(e, item=item):
                source = e.src.data
                if source is item or source not in subtask_data:
                    return
                target = subtask_data.index(item)
                subtask_data.remove(source)
                subtask_data.insert(target, source)
                render_subtasks()
                page.update()
            row = ft.Row([
                ft.Draggable(content=ft.Icon(ft.Icons.DRAG_HANDLE, size=18, color=c['muted']),
                             group='subtask-priority', data=item, tooltip='Kéo để đổi thứ tự ưu tiên'),
                ft.Checkbox(value=subtask_done(item), on_change=toggle),
                ft.Column([
                    *([ft.Text("Lịch thực hiện: " + str(item.get('start_at')) + " → " + str(item.get('end_at') or 'theo thời lượng'), size=12, color=c['muted'])] if item.get('start_at') else []),
                    ft.TextField(value=item.get("title", ""), label="Việc nhỏ", on_change=lambda e, item=item: edit(e, item), text_size=13),
                    ft.Row([
                        ft.TextField(value=str(item.get("estimated_minutes") or ""), label="Phút dự kiến", expand=True, on_change=lambda e, item=item: number(e, item), text_size=12),
                        ft.TextField(value=item.get("due_date") or "", label="Hạn riêng", hint_text="YYYY-MM-DD", expand=True,
                                     on_change=lambda e, item=item: edit(e, item, 'due_date'), text_size=12),
                        ft.TextField(value=item.get("due_time") or "", label="Giờ hạn", hint_text="HH:MM", width=115,
                                     on_change=lambda e, item=item: edit(e, item, 'due_time'), text_size=12),
                    ]),
                ], expand=True, spacing=4, horizontal_alignment=ft.CrossAxisAlignment.STRETCH),
                ft.IconButton(icon=ft.Icons.ARROW_UPWARD, tooltip="Ưu tiên trước", disabled=index == 0,
                              on_click=lambda e, item=item: move(e, item, -1)),
                ft.IconButton(icon=ft.Icons.ARROW_DOWNWARD, tooltip="Ưu tiên sau", disabled=index == len(subtask_data)-1,
                              on_click=lambda e, item=item: move(e, item, 1)),
                ft.IconButton(icon=ft.Icons.CLOSE, tooltip="Bỏ việc con", on_click=remove),
            ])
            subtask_view.controls.append(ft.DragTarget(content=row, group='subtask-priority', on_accept=dropped))

    def add_subtask(_):
        if new_subtask.value and new_subtask.value.strip():
            subtask_data.append({"id": str(uuid.uuid4()), "title": new_subtask.value.strip(), "status": "todo"})
            new_subtask.value = ""
            render_subtasks()
            page.update()
    new_subtask.on_submit = add_subtask
    render_subtasks()
    notes = ft.TextField(label="Ghi chú", value=original.notes, multiline=True, min_lines=2)
    error = ft.Text(color=c["text"], weight=ft.FontWeight.W_600)

    def draft():
        import json
        return json.dumps([control.value for control in (title, description, due, due_time, priority, status, project, category, minutes, reminder, tags, repeat, notes)] + [subtask_data], ensure_ascii=False, sort_keys=True)
    initial_draft = draft()
    def guard(continue_navigation):
        if draft() == initial_draft:
            continue_navigation()
            return
        def stay(_):
            dialog.open = False
            page.update()
        def leave(_):
            dialog.open = False
            continue_navigation()
        dialog = ft.AlertDialog(title=ft.Text('Rời trang khi chưa lưu?'), content=ft.Text('Thay đổi của bạn chưa được lưu.'),
            actions=[ft.TextButton('Tiếp tục sửa', on_click=stay), ft.TextButton('Bỏ thay đổi', on_click=leave)])
        page.overlay.append(dialog)
        dialog.open = True
        page.update()
    if register_guard:
        register_guard(guard)

    def save(_):
        try:
            if not title.value.strip():
                raise ValueError("Hãy nhập tên công việc.")
            estimated = int(minutes.value.strip())
            if estimated < 1 or estimated > 10080:
                raise ValueError("Thời lượng dự kiến cần từ 1 đến 10080 phút.")
            if due.value.strip():
                date.fromisoformat(due.value.strip())
            if due_time.value.strip():
                datetime.strptime(due_time.value.strip(), "%H:%M")
            if due_time.value.strip() and not due.value.strip():
                raise ValueError("Hãy chọn ngày cho giờ hoàn thành.")
            if int(reminder.value or "0") > 0 and (not due.value.strip() or not due_time.value.strip()):
                raise ValueError("Nhắc việc cần đủ ngày và giờ hoàn thành.")
        except ValueError as exc:
            error.value = str(exc) if str(exc).startswith(("Hãy", "Thời", "Nhắc")) else "Kiểm tra thời lượng, ngày YYYY-MM-DD và giờ HH:MM."
            page.update()
            return
        updated = replace(original, title=title.value.strip(), description=description.value or "",
                          due_date=due.value.strip() or None, due_time=due_time.value.strip() or None,
                          priority=priority.value, status=status.value, notes=notes.value or "",
                          project_id=project.value or None, category=category.value,
                          estimated_minutes=estimated, reminder_minutes=int(reminder.value or "0"),
                          tags=list(dict.fromkeys(tag.strip() for tag in tags.value.split(",") if tag.strip())),
                          is_recurring=repeat.value != "none", recur_pattern=repeat.value if repeat.value != "none" else "",
                          subtasks=deepcopy(subtask_data),
                          updated_at=datetime.now().isoformat())
        if status.value == "done" and original.status != "done":
            updated.completed_at = datetime.now().isoformat()
        elif status.value != "done":
            updated.completed_at = None
        try:
            TaskService.save_task(updated, expected_revision=original.updated_at if original_exists else None)
        except Exception as exc:
            error.value = str(exc) if isinstance(exc, ValueError) else "Không lưu được công việc. Vui lòng thử lại."
            page.update()
            return
        if register_guard:
            register_guard(None)
        navigate("tasks")

    async def keyboard(e):
        if e.ctrl and str(e.key).lower() == 's':
            save(None)
    page.on_keyboard_event = keyboard

    editor = ft.Column([
        ft.Row([ft.TextButton("Công việc", icon=ft.Icons.ARROW_BACK, on_click=lambda e: navigate("tasks"))]),
        ft.Text("Sửa công việc" if task else "Thêm công việc", size=30, color=c["text"], weight=ft.FontWeight.W_600),
        ft.Container(height=12), title, description,
        ft.Text("Việc nhỏ · theo thứ tự ưu tiên", size=18, weight=ft.FontWeight.W_600),
        ft.Text("Kéo tay nắm hoặc dùng mũi tên để đổi thứ tự. Để trống hạn riêng để dùng hạn công việc cha. Hoàn thành hết các bước sẽ tự hoàn thành công việc.", size=12, color=c['muted']),
        subtask_view, ft.Row([new_subtask, ft.IconButton(icon=ft.Icons.ADD, tooltip="Thêm việc con", on_click=add_subtask)]),
        ft.ResponsiveRow([ft.Container(due, col=8), ft.Container(due_time, col=4)]),
        ft.ResponsiveRow([ft.Container(ft.Column([priority], horizontal_alignment=ft.CrossAxisAlignment.STRETCH), col=6), ft.Container(ft.Column([status], horizontal_alignment=ft.CrossAxisAlignment.STRETCH), col=6)]),
        ft.ResponsiveRow([ft.Container(project, col=6), ft.Container(category, col=6)]),
        ft.ResponsiveRow([ft.Container(minutes, col=6), ft.Container(reminder, col=6)]),
        ft.Text("Bật nhắc nền trong Cài đặt để nhận nhắc việc sau khi đóng cửa sổ.", size=12, color=c["muted"]),
        tags,
        repeat,
        notes, error,
        ft.Row([ft.OutlinedButton("Lưu công việc", icon=ft.Icons.CHECK, on_click=save), ft.TextButton("Hủy", on_click=lambda e: navigate("tasks"))]),
    ], spacing=18, scroll=ft.ScrollMode.AUTO, expand=True, width=760,
       horizontal_alignment=ft.CrossAxisAlignment.STRETCH)
    actions = editor.controls.pop()
    body = ft.Column([editor, ft.Divider(height=1, color=c["line"]), actions], expand=True, spacing=12)
    return ft.Row([ft.Container(body, width=760)], expand=True,
                  vertical_alignment=ft.CrossAxisAlignment.STRETCH)


def build_report(page, user, navigate):
    c = palette(page)
    content = ft.Column(spacing=22)

    def render(days, update=True):
        from core.access import access_for
        if days > 7 and not access_for(user.id).allows("advanced_reports"):
            navigate("plans")
            return
        tasks = TaskService.get_tasks(user.id)
        today = date.today()
        start = today - timedelta(days=days - 1)
        completed = [task for task in tasks if task.status == "done" and task.completed_at and start.isoformat() <= task.completed_at[:10] <= today.isoformat()]
        overdue = sum(task.is_overdue for task in tasks)
        due_tasks = [task for task in tasks if task.due_date and start.isoformat() <= task.due_date <= today.isoformat()]
        on_time_done = sum(task.status == "done" for task in due_tasks)
        rate = round(on_time_done / len(due_tasks) * 100) if due_tasks else 0
        content.controls = [
            ft.Text(f"{start.strftime('%d/%m')} — {today.strftime('%d/%m/%Y')}", color=c["muted"]),
            ft.Text(f"{len(completed)} công việc hoàn thành trong kỳ · {overdue} việc đang quá hạn", size=18, color=c["text"]),
            ft.Text(f"Hoàn thành {rate}% công việc có hạn trong kỳ ({on_time_done}/{len(due_tasks)}).", color=c["muted"]),
            ft.Divider(color=c["line"]),
            ft.Text("Số công việc hoàn thành theo ngày", size=18, color=c["text"]),
        ]
        counts = {start + timedelta(days=i): 0 for i in range(days)}
        for task in completed:
            counts[date.fromisoformat(task.completed_at[:10])] += 1
        maximum = max(counts.values(), default=0) or 1
        for day, amount in counts.items():
            content.controls.append(ft.Row([
                ft.Text(day.strftime("%d/%m"), width=50, size=12, color=c["muted"]),
                ft.ProgressBar(value=amount / maximum, expand=True, color=c["text"], bgcolor=c["line"], height=8),
                ft.Text(str(amount), width=30, color=c["muted"]),
            ], spacing=16))
        if update:
            page.update()

    period = ft.Dropdown(value="7", width=170, on_select=lambda e: render(int(e.control.value)), options=[
        ft.DropdownOption("1", "Hôm nay"), ft.DropdownOption("7", "7 ngày qua"), ft.DropdownOption("30", "30 ngày qua")])
    render(7, update=False)
    return ft.Column([
        ft.Row([ft.Text("Báo cáo", size=30, weight=ft.FontWeight.W_600, color=c["text"], expand=True), period]),
        ft.Text("Tiến độ công việc của bạn", color=c["muted"]),
        ft.Container(height=12), content,
    ], spacing=16, scroll=ft.ScrollMode.AUTO, expand=True)
