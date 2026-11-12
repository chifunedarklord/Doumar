"""Folder-style task browsing and a persistent, explicit focus target."""
import asyncio
from datetime import datetime
import flet as ft

from core.task_focus import TaskFocus
from core.task_rules import subtask_done
from screens.desktop_screen import palette


class FocusClock(ft.Text):
    def __init__(self, started_at):
        super().__init__(size=32, weight=ft.FontWeight.W_600, color='#111111')
        self._started_at = started_at
        self._running = False
        self._future = None
        self._elapsed()

    def _elapsed(self):
        seconds = max(0, int((datetime.now()-datetime.fromisoformat(self._started_at)).total_seconds()))
        hours, remainder = divmod(seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        self.value = f'{hours:02}:{minutes:02}:{seconds:02}' if hours else f'{minutes:02}:{seconds:02}'

    def did_mount(self):
        self._running = True
        self._future = self.page.run_task(self._tick)

    def will_unmount(self):
        self._running = False
        if self._future:
            self._future.cancel()

    async def _tick(self):
        while self._running:
            self._elapsed()
            self.update()
            await asyncio.sleep(1)


def build_focus_panel(page, user, navigate, on_changed, compact=False):
    active = TaskFocus.current(user.id)
    if not active:
        return ft.Container(visible=False)
    error = ft.Text('', color='#111111', size=13)

    def stop(_):
        try:
            TaskFocus.stop(user.id, active['session_id'])
            on_changed()
        except Exception as exc:
            error.value = str(exc) if isinstance(exc, ValueError) else 'Chưa kết thúc được phiên. Hãy thử lại.'
            page.update()

    def complete(_):
        try:
            if active['subtask_id']:
                TaskFocus.set_done(user.id, active['task_id'], active['subtask_id'], True)
            else:
                TaskFocus.set_task_done(user.id, active['task_id'], True)
            on_changed()
        except Exception as exc:
            error.value = str(exc) if isinstance(exc, ValueError) else 'Chưa lưu được thay đổi. Hãy thử lại.'
            page.update()

    if compact:
        clock = FocusClock(active['started_at'])
        clock.size = 23
        return ft.Container(ft.Column([
            ft.Row([
                ft.Icon(ft.Icons.MY_LOCATION, size=20),
                ft.Column([ft.Text('Đang tập trung', size=12, color='#666666'),
                           ft.Text(active['title'], size=16, weight=ft.FontWeight.W_600, max_lines=2)], expand=True, spacing=3),
                clock,
                ft.IconButton(icon=ft.Icons.CHECK, tooltip='Hoàn thành việc đang tập trung', on_click=complete),
                ft.IconButton(icon=ft.Icons.STOP_CIRCLE_OUTLINED, tooltip='Kết thúc tập trung', on_click=stop),
                ft.IconButton(icon=ft.Icons.OPEN_IN_NEW, tooltip='Mở mục tiêu tập trung',
                              on_click=lambda e: navigate('task_folder', task_id=active['task_id'])),
            ], spacing=12), error,
        ], spacing=0), padding=14, bgcolor='#FAFAFA', border_radius=8)

    return ft.Container(content=ft.Column([
        ft.Row([ft.Icon(ft.Icons.MY_LOCATION, size=18), ft.Text('Đang tập trung', size=14, weight=ft.FontWeight.W_600)], spacing=8),
        ft.Text(active['title'], size=22, weight=ft.FontWeight.W_600, selectable=True),
        ft.Text(active['parent_title'], size=13, color='#666666'),
        FocusClock(active['started_at']),
        ft.Row([
            ft.OutlinedButton('Hoàn thành việc này', icon=ft.Icons.CHECK, on_click=complete),
            ft.TextButton('Kết thúc tập trung', on_click=stop),
            ft.TextButton('Mở công việc', on_click=lambda e: navigate('task_folder', task_id=active['task_id'])),
        ], wrap=True), error,
    ], spacing=8), bgcolor='#FAFAFA', padding=20, border_radius=8)


def build_task_folder(page, user, navigate, task_id):
    c = palette(page)
    content = ft.Column(spacing=18, expand=True)
    state = {'selected': None}
    message = ft.Text('', size=13, color=c['text'])
    entry = ft.TextField(hint_text='Thêm công việc nhỏ rồi nhấn Enter', expand=True, text_size=14, max_length=500, counter='')

    def show_error(exc):
        message.value = str(exc) if isinstance(exc, ValueError) else 'Chưa lưu được thay đổi. Hãy thử lại.'
        page.update()

    def finish(child_id, done):
        try:
            TaskFocus.set_done(user.id, task_id, child_id, done)
            message.value = ''
            render()
        except Exception as exc:
            show_error(exc)

    def finish_empty(done):
        try:
            TaskFocus.set_task_done(user.id, task_id, done)
            message.value = ''
            render()
        except Exception as exc:
            show_error(exc)

    def focus(child_id=None):
        try:
            TaskFocus.start(user.id, task_id, child_id)
            state['selected'] = child_id
            message.value = ''
            render()
        except Exception as exc:
            show_error(exc)

    def select(child_id):
        state['selected'] = None if state['selected'] == child_id else child_id
        render()

    def add(_):
        try:
            TaskFocus.add_child(user.id, task_id, entry.value or '')
            entry.value = ''
            message.value = 'Đã thêm công việc nhỏ.'
            render()
        except Exception as exc:
            show_error(exc)
    entry.on_submit = add

    def render(update=True):
        try:
            task = TaskFocus.ensure_ids(user.id, task_id)
        except Exception as exc:
            content.controls = [ft.TextButton('Về Công việc', icon=ft.Icons.ARROW_BACK, on_click=lambda e: navigate('tasks')),
                                ft.Text(str(exc), color=c['text'])]
            if update:
                page.update()
            return
        active = TaskFocus.current(user.id)
        entry.disabled = task.status == 'cancelled'
        done, total = task.subtask_progress
        status = 'Đã hoàn thành' if task.status == 'done' else 'Đã hủy' if task.status == 'cancelled' else 'Quá hạn' if task.is_overdue else 'Đang thực hiện'
        controls = [
            ft.Row([ft.TextButton('Công việc', icon=ft.Icons.ARROW_BACK, on_click=lambda e: navigate('tasks', project_id=task.project_id)),
                    ft.Icon(ft.Icons.CHEVRON_RIGHT, size=16, color=c['muted']), ft.Text('Thư mục', color=c['muted'], size=13)]),
            ft.Row([ft.Icon(ft.Icons.FOLDER_OPEN_OUTLINED, size=32, color=c['text']),
                    ft.Text(task.title, size=28, weight=ft.FontWeight.W_600, expand=True, selectable=True),
                    ft.TextButton('Sửa thư mục', icon=ft.Icons.EDIT_OUTLINED, on_click=lambda e: navigate('task_edit', task=task))], spacing=12),
            ft.Text(f'{done}/{total} công việc hoàn thành · {status}' if total else status, size=14, color=c['muted']),
        ]
        if task.description:
            controls.append(ft.Text(task.description, size=15, color=c['muted'], selectable=True))
        controls.append(build_focus_panel(page, user, navigate, render))
        controls.extend([ft.Row([entry, ft.IconButton(icon=ft.Icons.ADD, tooltip='Thêm công việc nhỏ', disabled=task.status == 'cancelled', on_click=add)]), message,
                         ft.Text('Công việc trong thư mục', size=17, weight=ft.FontWeight.W_600),
                         ft.Text('Bấm tên để xem chi tiết. Chọn Tập trung để làm một việc tại một thời điểm.', size=13, color=c['muted'])])
        for index, child in enumerate(task.subtasks):
            child_id = child['id']
            completed = subtask_done(child)
            targeted = bool(active and active['task_id'] == task_id and active['subtask_id'] == child_id)
            selected = state['selected'] == child_id
            due_day = child.get('due_date') or task.due_date
            due_clock = child.get('due_time') or (task.due_time if not child.get('due_date') else None)
            info = [f'Ưu tiên thứ {index+1}']
            if child.get('estimated_minutes'):
                info.append(f"{child['estimated_minutes']} phút dự kiến")
            if completed:
                info.append('Đã hoàn thành')
            elif due_day:
                info.append('Hạn ' + due_day + (' ' + due_clock if due_clock else ''))
            if targeted:
                info.append('Đang tập trung')
            file_row = ft.Row([
                ft.Checkbox(value=completed, disabled=task.status == 'cancelled', tooltip='Bỏ hoàn thành' if completed else 'Hoàn thành công việc nhỏ',
                            on_change=lambda e, key=child_id: finish(key, bool(e.control.value))),
                ft.Container(content=ft.Row([
                    ft.Icon(ft.Icons.TASK_ALT if completed else ft.Icons.INSERT_DRIVE_FILE_OUTLINED, size=21, color=c['muted']),
                    ft.Column([ft.Text(child['title'], size=16, color=c['muted'] if completed else c['text'],
                                       style=ft.TextStyle(decoration=ft.TextDecoration.LINE_THROUGH if completed else None)),
                               ft.Text(' · '.join(info), size=12, color=c['muted'])], spacing=4, expand=True),
                ], spacing=12), expand=True, padding=ft.Padding.symmetric(vertical=14), on_click=lambda e, key=child_id: select(key)),
                ft.TextButton('Đang tập trung' if targeted else 'Tập trung', icon=ft.Icons.MY_LOCATION,
                              disabled=completed or targeted or task.status == 'cancelled', on_click=lambda e, key=child_id: focus(key)),
            ], spacing=8)
            parts = [file_row]
            if selected:
                detail = [ft.Text(child['title'], size=18, weight=ft.FontWeight.W_600)]
                if child.get('description'):
                    detail.append(ft.Text(child['description'], size=15, selectable=True))
                if child.get('start_at'):
                    detail.append(ft.Text('Lịch thực hiện: ' + str(child['start_at']) + ' → ' + str(child.get('end_at') or 'theo thời lượng'), size=13))
                if completed and child.get('completed_at'):
                    detail.append(ft.Text('Hoàn thành lúc ' + child['completed_at'][:16].replace('T',' '), size=13, color=c['muted']))
                detail.append(ft.Row([
                    ft.OutlinedButton('Bỏ hoàn thành' if completed else 'Đánh dấu hoàn thành', icon=ft.Icons.CHECK,
                                      disabled=task.status == 'cancelled', on_click=lambda e, key=child_id, value=not completed: finish(key,value)),
                    ft.TextButton('Tập trung vào việc này', icon=ft.Icons.MY_LOCATION,
                                  disabled=completed or targeted or task.status == 'cancelled', on_click=lambda e, key=child_id: focus(key)),
                ], wrap=True))
                parts.append(ft.Container(ft.Column(detail, spacing=12), padding=ft.Padding.only(left=52, right=16, bottom=18)))
            controls.append(ft.Container(ft.Column(parts, spacing=0), bgcolor=c['selected'] if selected or targeted else None,
                                         border=ft.Border(bottom=ft.BorderSide(1,c['line'])), padding=ft.Padding.symmetric(horizontal=4)))
        if not task.subtasks:
            controls.extend([ft.Text('Thư mục chưa có việc nhỏ. Thêm bước đầu tiên ở ô phía trên.', size=15, color=c['muted']),
                             ft.TextButton('Tập trung vào công việc này', icon=ft.Icons.MY_LOCATION,
                                           disabled=task.status in ('done','cancelled'), on_click=lambda e: focus()),
                             ft.TextButton('Bỏ hoàn thành' if task.status == 'done' else 'Đánh dấu hoàn thành công việc', icon=ft.Icons.CHECK,
                                           disabled=task.status == 'cancelled', on_click=lambda e: finish_empty(task.status != 'done'))])
        content.controls = controls
        if update:
            page.update()
    render(update=False)
    return ft.Column([ft.ListView(controls=[content], expand=True, spacing=0)], expand=True)
