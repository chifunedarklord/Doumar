"""Readable, selectable AI suggestions. Nothing is saved without an action."""
from datetime import datetime
import uuid
import flet as ft
from core.models import Task
from core.services import TaskService
from core.theme import Colors


def build_plan(plan, page, user_id, on_changed, on_refine):
    tasks = list(plan.get('suggested_tasks') or [])
    saved = set()
    checks = []
    buttons = []
    message = ft.Text('', size=16, color=Colors.TEXT_SECONDARY)
    bulk = ft.OutlinedButton('Lưu việc đã chọn (0)', disabled=True)

    def refresh():
        count = sum(bool(box.value) for i, box in enumerate(checks) if i not in saved)
        bulk.content = f'Lưu việc đã chọn ({count})'
        bulk.disabled = count == 0
        if page:
            page.update()

    def save(indices):
        count = 0
        errors = 0
        for i in indices:
            if i in saved:
                continue
            item = tasks[i]
            try:
                now = datetime.now().isoformat()
                TaskService.save_task(Task(
                    id=str(uuid.uuid4()), user_id=user_id,
                    title=item.get('title') or 'Công việc mới',
                    description=item.get('description', ''),
                    category=item.get('category', 'personal'),
                    priority=item.get('priority', 'medium'), status='todo',
                    due_date=item.get('due_date'), due_time=item.get('due_time'),
                    estimated_minutes=int(item.get('estimated_minutes') or 30),
                    created_at=now, updated_at=now))
                saved.add(i)
                checks[i].value = False
                checks[i].disabled = True
                buttons[i].content = 'Đã lưu'
                buttons[i].disabled = True
                count += 1
            except Exception:
                errors += 1
        plan['suggested_tasks'] = [item for i, item in enumerate(tasks) if i not in saved]
        message.value = f'Đã lưu {count} công việc.' + (f' {errors} việc chưa lưu được; hãy thử lại.' if errors else '')
        if count and on_changed:
            on_changed()
        refresh()

    bulk.on_click = lambda _: save([i for i, box in enumerate(checks) if box.value])
    sections = [ft.Text(plan.get('title') or 'Kế hoạch của bạn', size=24, weight=ft.FontWeight.W_600)]
    if plan.get('summary'):
        sections.append(ft.Text(plan['summary'], size=17, selectable=True))
    assumptions = plan.get('assumptions') or []
    if assumptions:
        sections.append(ft.Text('Thông tin đang giả định', size=16, weight=ft.FontWeight.W_600))
        sections.extend(ft.Text('• ' + str(value), size=16, color=Colors.TEXT_SECONDARY) for value in assumptions)
    for index, step in enumerate(plan.get('plan') or []):
        if isinstance(step, dict):
            title = step.get('title') or step.get('name') or f'Bước {index + 1}'
            details = step.get('details') or step.get('actions') or step.get('description') or []
            if isinstance(details, str):
                details = [details]
        else:
            title, details = str(step), []
        sections.append(ft.Container(ft.Row([
            ft.Text(f'{index + 1:02}', size=16, color=Colors.TEXT_MUTED, width=32, tooltip=step.get('time_or_step') if isinstance(step, dict) else None),
            ft.Column([ft.Text(title, size=18, weight=ft.FontWeight.W_500)] +
                      [ft.Text(str(value), size=17, selectable=True) for value in details],
                      spacing=6, expand=True),
        ], vertical_alignment=ft.CrossAxisAlignment.START), padding=ft.Padding.symmetric(vertical=8)))
    if tasks:
        sections.extend([ft.Divider(color=Colors.BORDER), ft.Text('Công việc đề xuất', size=18, weight=ft.FontWeight.W_600)])
    for i, item in enumerate(tasks):
        box = ft.Checkbox(value=False, on_change=lambda _: refresh(),
                          tooltip='Chọn công việc để lưu',
                          fill_color={ft.ControlState.SELECTED: '#111111', ft.ControlState.DEFAULT: '#FFFFFF'},
                          check_color='#FFFFFF', border_side=ft.BorderSide(1.2, '#777777'))
        button = ft.TextButton('Lưu', on_click=lambda _, index=i: save([index]))
        checks.append(box)
        buttons.append(button)
        sections.append(ft.Row([box, ft.Column([
            ft.Text(item.get('title', ''), size=17),
            ft.Text(f"{item.get('estimated_minutes') or 30} phút", size=14, color=Colors.TEXT_SECONDARY),
        ], spacing=3, expand=True), button], spacing=8))
    if tasks:
        sections.extend([bulk, message])
    if plan.get('follow_up_question'):
        sections.append(ft.Text(plan['follow_up_question'], size=16, color=Colors.TEXT_SECONDARY))
    options = plan.get('refine_options') or []
    if options:
        sections.append(ft.Row([ft.TextButton(str(option), on_click=lambda _, text=option: on_refine(text))
                                for option in options], wrap=True))
    return ft.Container(ft.Column(sections, spacing=14, tight=True),
                        bgcolor=Colors.BG_CARD, padding=24, border_radius=10,
                        border=ft.Border.all(1, Colors.BORDER))
