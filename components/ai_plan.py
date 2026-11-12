"""Readable, selectable AI suggestions. Nothing is saved without an action."""
import uuid
import flet as ft
from core.plan_commit import save_suggestion
from core.theme import Colors


def build_plan(plan, page, user_id, on_changed, on_refine):
    raw_tasks = plan.get('suggested_tasks') or []
    malformed = not isinstance(raw_tasks, list) or any(not isinstance(item, dict) for item in raw_tasks)
    tasks = [item for item in raw_tasks if isinstance(item, dict)] if isinstance(raw_tasks, list) else []
    saved = set(plan.get('_saved_indices') or [])
    plan.setdefault('_save_id', str(uuid.uuid4()))
    ready = not malformed and plan.get('ready_to_save') is True and not plan.get('missing_information') and not plan.get('assumptions')
    checks = []
    buttons = []
    message = ft.Text('', size=16, color=Colors.TEXT_SECONDARY)
    bulk = ft.OutlinedButton('Xác nhận lưu (0)', disabled=True)

    def refresh():
        count = sum(bool(box.value) for i, box in enumerate(checks) if i not in saved)
        bulk.content = f'Xác nhận lưu ({count})'
        bulk.disabled = count == 0 or not ready
        if page:
            page.update()

    def save(indices):
        if not ready:
            return
        count = 0
        errors = 0
        for i in indices:
            if i in saved:
                continue
            item = tasks[i]
            try:
                save_suggestion(user_id, item, f"{plan['_save_id']}:{i}")
                saved.add(i)
                checks[i].value = False
                checks[i].disabled = True
                buttons[i].content = 'Đã lưu'
                buttons[i].disabled = True
                count += 1
            except Exception as exc:
                errors += 1
                message.value = str(exc)
        # Preserve stable suggestion positions and IDs across re-renders.
        plan['_saved_indices'] = sorted(saved)
        message.value = f'Đã lưu {count} công việc.' + (f' {errors} việc chưa lưu được: ' + message.value if errors else '')
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
            if step.get('time_or_step'):
                title = str(step['time_or_step']) + ' · ' + title
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
        box = ft.Checkbox(value=False, disabled=not ready or i in saved, on_change=lambda _: refresh(),
                          tooltip='Chọn công việc để lưu',
                          fill_color={ft.ControlState.SELECTED: '#111111', ft.ControlState.DEFAULT: '#FFFFFF'},
                          check_color='#FFFFFF', border_side=ft.BorderSide(1.2, '#777777'))
        button = ft.TextButton('Đã lưu' if i in saved else 'Xác nhận lưu', disabled=not ready or i in saved, on_click=lambda _, index=i: save([index]))
        checks.append(box)
        buttons.append(button)
        sections.append(ft.Row([box, ft.Column([
            ft.Text(item.get('title', ''), size=17),
            ft.Text(f"{item.get('estimated_minutes') or 30} phút dự kiến · " +
                    (f"{item['start_at']} → {item.get('end_at') or 'theo thời lượng'}" if item.get('start_at') else ('Theo lịch các việc nhỏ' if any(sub.get('start_at') for sub in item.get('subtasks') or []) else 'Chưa xếp giờ · chỉ vào công việc')) +
                    (f" · Hạn: {item['due_date']} {item.get('due_time') or ''}" if item.get('due_date') else ''), size=14, color=Colors.TEXT_SECONDARY),
            *[ft.Text(f"{j+1}. {sub.get('title', '')}" + (f" · {sub['start_at']} → {sub.get('end_at') or 'theo thời lượng'}" if sub.get('start_at') else ''), size=14, color=Colors.TEXT_SECONDARY)
              for j, sub in enumerate(item.get('subtasks') or [])],
        ], spacing=3, expand=True), button], spacing=8))
    if tasks:
        def select_all(e):
            for i, box in enumerate(checks):
                if ready and i not in saved:
                    box.value = e.control.value
            refresh()
        sections.extend([ft.Checkbox(label='Chọn tất cả', disabled=not ready, on_change=select_all), bulk, message])
    if not ready:
        sections.append(ft.Text('Bản sơ bộ — hãy trả lời câu hỏi hoặc yêu cầu điều chỉnh trước khi xác nhận lưu.', size=15, color=Colors.TEXT_SECONDARY))
    for missing in plan.get('missing_information') or []:
        sections.append(ft.Text('Cần làm rõ: ' + str(missing), size=15))
    if plan.get('follow_up_question'):
        sections.append(ft.Text(plan['follow_up_question'], size=16, color=Colors.TEXT_SECONDARY))
    options = plan.get('refine_options') or []
    if options:
        sections.append(ft.Row([ft.TextButton(str(option), on_click=lambda _, text=option: on_refine(text))
                                for option in options], wrap=True))
    return ft.Container(ft.Column(sections, spacing=14, tight=True),
                        bgcolor=Colors.BG_CARD, padding=24, border_radius=10,
                        border=ft.Border.all(1, Colors.BORDER))
