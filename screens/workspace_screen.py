"""Local schedule, data portability and commercial plan presentation."""
from datetime import date, datetime, timedelta
from pathlib import Path
import json
import flet as ft

from core.services import TaskService
from core.workspace import Workspace
from core.plans import PLANS, format_vnd
from screens.desktop_screen import palette


def build_projects(page, user, navigate):
    from core.models import Project, Task
    from core.services import ProjectService
    import uuid
    name = ft.TextField(label="Tên dự án", text_size=14)
    description = ft.TextField(label="Mô tả", text_size=14)
    rows, message = ft.Column(spacing=12), ft.Text()
    state = {"editing": None}

    def edit(project):
        state["editing"] = project.id
        name.value, description.value = project.name, project.description
        page.update()

    def remove(project):
        def confirm(_):
            try:
                ProjectService.delete_project(project.id, user.id)
                dialog.open = False
                render()
            except Exception:
                message.value = "Không xóa được dự án."
            page.update()
        def cancel(_):
            dialog.open = False
            page.update()
        dialog = ft.AlertDialog(title=ft.Text("Xóa dự án?"), content=ft.Text("Các công việc vẫn được giữ, chỉ gỡ liên kết với dự án."),
            actions=[ft.TextButton("Hủy", on_click=cancel), ft.TextButton("Xóa", on_click=confirm)])
        page.overlay.append(dialog)
        dialog.open = True
        page.update()

    def render():
        tasks = TaskService.get_tasks(user.id)
        rows.controls.clear()
        for project in ProjectService.get_projects(user.id):
            related = [task for task in tasks if task.project_id == project.id]
            rows.controls.append(ft.Row([
                ft.Column([ft.Text(project.name, size=17, weight=ft.FontWeight.W_600),
                           ft.Text(f"{sum(task.status == 'done' for task in related)}/{len(related)} công việc hoàn thành", size=12, color="#666666")], expand=True),
                ft.TextButton("Mở", on_click=lambda e, project=project: navigate("tasks", project_id=project.id)),
                ft.IconButton(icon=ft.Icons.EDIT_OUTLINED, tooltip="Sửa dự án", on_click=lambda e, project=project: edit(project)),
                ft.IconButton(icon=ft.Icons.DELETE_OUTLINE, tooltip="Xóa dự án", on_click=lambda e, project=project: remove(project)),
            ]))
        if not rows.controls:
            rows.controls = [ft.Text("Chưa có dự án. Thêm dự án học tập hoặc công việc đầu tiên.", color="#666666")]

    def save(_):
        try:
            ProjectService.save_project(Project(id=state["editing"] or str(uuid.uuid4()), user_id=user.id,
                                                name=name.value.strip(), description=description.value or ""))
            state["editing"] = None
            name.value = description.value = ""
            message.value = "Đã lưu dự án."
            render()
        except Exception as exc:
            message.value = str(exc) if isinstance(exc, ValueError) else "Không lưu được dự án. Hãy thử lại."
        page.update()
    render()
    return ft.Column([ft.Text("Dự án", size=30, weight=ft.FontWeight.W_600), rows, ft.Divider(),
                      name, description, ft.OutlinedButton("Lưu dự án", icon=ft.Icons.ADD, on_click=save), message],
                      spacing=18, expand=True, scroll=ft.ScrollMode.AUTO)


def build_account_settings(page, user, navigate, on_logout):
    from screens.cloud_screen import build_sync_panel, build_reminder_settings
    from screens.google_calendar_screen import build_google_panel
    from core.database import Storage
    from core.services import AuthService
    from dataclasses import replace
    name = ft.TextField(label="Tên hiển thị", value=user.full_name, text_size=14)
    start = ft.TextField(label="Bắt đầu làm việc / học", value=user.work_start, width=230)
    end = ft.TextField(label="Kết thúc", value=user.work_end, width=230)
    old = ft.TextField(label="Mật khẩu hiện tại", password=True, can_reveal_password=True)
    password = ft.TextField(label="Mật khẩu mới", password=True, can_reveal_password=True)
    confirm_password = ft.TextField(label="Nhập lại mật khẩu mới", password=True, can_reveal_password=True)
    message = ft.Text()

    def save(_):
        try:
            begin = datetime.strptime(start.value.strip(), "%H:%M")
            finish = datetime.strptime(end.value.strip(), "%H:%M")
            if begin >= finish:
                raise ValueError("Giờ kết thúc cần sau giờ bắt đầu.")
            profile = dict((user.settings or {}).get('planning_profile', {}))
            profile['work_hours'] = [begin.strftime('%H:%M'), finish.strftime('%H:%M')]
            updated = replace(user, full_name=name.value.strip() or user.username,
                              work_start=begin.strftime("%H:%M"), work_end=finish.strftime("%H:%M"),
                              settings=dict(user.settings or {}, planning_profile=profile))
            Storage.save_user(updated)
            user.full_name, user.work_start, user.work_end = updated.full_name, updated.work_start, updated.work_end
            user.settings = updated.settings
            from core.services import AIMemoryService
            AIMemoryService.remember(user.id, 'preference', 'planning_profile', profile, 1.0)
            from utils.ai_helper import invalidate_context_cache
            invalidate_context_cache(user.id)
            message.value = "Đã lưu cài đặt."
        except ValueError:
            message.value = "Nhập giờ HH:MM hợp lệ; giờ kết thúc phải sau giờ bắt đầu."
        except Exception:
            message.value = "Không lưu được cài đặt. Vui lòng thử lại."
        page.update()

    def change_password(_):
        try:
            ok, text = AuthService.change_password(user, old.value or "", password.value or "", confirm_password.value or "")
            message.value = text
            if ok:
                old.value = password.value = confirm_password.value = ""
        except Exception:
            message.value = "Không đổi được mật khẩu. Vui lòng thử lại."
        page.update()

    return ft.Column([
        ft.Text("Cài đặt tài khoản", size=30, weight=ft.FontWeight.W_600),
        ft.Text(' · '.join(value for value in (user.settings.get('cloud_username', user.username), user.settings.get('cloud_email', user.email)) if value), color="#666666"),
        build_sync_panel(page, user),
        name, ft.Row([start, end], wrap=True), ft.Row([ft.OutlinedButton("Lưu cài đặt", on_click=save)]),
        ft.TextButton("Cập nhật hồ sơ và thói quen cho AI", on_click=lambda e: navigate('planning_profile')),
        ft.Divider(), build_reminder_settings(page, user),
        ft.Divider(), build_google_panel(page, user),
        ft.Divider(), ft.Text("Đổi mật khẩu", size=20, weight=ft.FontWeight.W_600), old, password, confirm_password,
        ft.Row([ft.OutlinedButton("Đổi mật khẩu", on_click=change_password)]), message,
        ft.Row([ft.TextButton("Đăng xuất", icon=ft.Icons.LOGOUT, on_click=lambda e: on_logout())]),
    ], spacing=18, scroll=ft.ScrollMode.AUTO, expand=True, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)


def build_plans(page, user, navigate):
    from screens.upgrade_screen import build_upgrade
    return build_upgrade(page, user, navigate)


def build_data(page, user, navigate, on_restored=None):
    from screens.cloud_screen import build_sync_panel
    c = palette(page)
    message = ft.Text(color=c["text"], selectable=True)
    picker = ft.FilePicker()
    page.services.append(picker)
    buttons = []
    busy = {"value": False}

    def set_busy(value):
        busy["value"] = value
        for button in buttons:
            button.disabled = value
        page.update()

    async def export(e, csv=False):
        if busy["value"]:
            return
        set_busy(True)
        try:
            content = Workspace.export_csv(user.id) if csv else json.dumps(Workspace.backup(user.id), ensure_ascii=False, indent=2).encode("utf-8")
            path = await picker.save_file(dialog_title="Lưu dữ liệu TaskFlow", file_name=f"taskflow-{date.today().isoformat()}.{'csv' if csv else 'json'}", src_bytes=content)
            message.value = "Đã xuất dữ liệu." if path else "Đã hủy xuất dữ liệu."
        except Exception:
            message.value = "Không xuất được dữ liệu. Kiểm tra quyền ghi và thử lại."
        finally:
            set_busy(False)

    async def restore(e):
        if busy["value"]:
            return
        set_busy(True)
        try:
            files = await picker.pick_files(dialog_title="Chọn bản sao lưu TaskFlow", allowed_extensions=["json"], file_type=ft.FilePickerFileType.CUSTOM)
            if not files:
                return
            file_path = Path(files[0].path)
            if file_path.stat().st_size > 20 * 1024 * 1024:
                raise ValueError("Tệp vượt giới hạn 20 MB.")
            payload = json.loads(file_path.read_text(encoding="utf-8-sig"))
            if not isinstance(payload, dict) or payload.get("format") != "taskflow-workspace" or payload.get("version") != 1:
                raise ValueError("Tệp không phải bản sao lưu TaskFlow phiên bản 1.")

            def cancel(_):
                dialog.open = False
                page.update()

            def confirm(_):
                dialog.open = False
                try:
                    result = Workspace.restore(user.id, payload)
                    if on_restored:
                        on_restored()
                    message.value = f"Đã khôi phục {result['tasks']} công việc và {result['conversations']} cuộc trò chuyện."
                except Exception:
                    message.value = "Không khôi phục được tệp. Dữ liệu hiện có không bị thay đổi."
                page.update()

            dialog = ft.AlertDialog(title=ft.Text("Khôi phục bản sao lưu?"),
                content=ft.Text("Dữ liệu từ tệp sẽ được thêm vào tài khoản này. Công việc hiện có không bị xóa. Nhập lại cùng một tệp sẽ cập nhật dữ liệu đã nhập trước đó."),
                actions=[ft.TextButton("Hủy", on_click=cancel), ft.TextButton("Khôi phục", on_click=confirm)])
            page.overlay.append(dialog)
            dialog.open = True
        except (ValueError, OSError, TypeError):
            message.value = "Không đọc được tệp. Hãy chọn bản sao lưu TaskFlow hợp lệ, tối đa 20 MB."
        finally:
            set_busy(False)

    backup = ft.OutlinedButton("Sao lưu JSON", icon=ft.Icons.SAVE_ALT, on_click=export)
    csv_button = ft.OutlinedButton("Xuất CSV", icon=ft.Icons.TABLE_VIEW_OUTLINED, on_click=lambda e: page.run_task(export, e, True))
    restore_button = ft.OutlinedButton("Khôi phục từ tệp", icon=ft.Icons.RESTORE, on_click=restore)
    buttons.extend([backup, csv_button, restore_button])
    return ft.Column([
        ft.Text("Dữ liệu", size=30, weight=ft.FontWeight.W_600),
        build_sync_panel(page, user, on_download=on_restored),
        ft.Divider(color=c["line"]),
        ft.Text("Sao lưu và xuất dữ liệu", size=20, weight=ft.FontWeight.W_600),
        ft.Text("JSON gồm công việc, dự án, lịch và lịch sử chat của tài khoản hiện tại. CSV dùng để xem danh sách công việc trong bảng tính.", color=c["muted"]),
        ft.Row([backup, csv_button], wrap=True),
        ft.Text("Khôi phục", size=20, weight=ft.FontWeight.W_600), restore_button,
        ft.TextButton("Mở Thùng rác", icon=ft.Icons.DELETE_OUTLINE, on_click=lambda e: navigate("trash")), message,
    ], spacing=20, scroll=ft.ScrollMode.AUTO, expand=True)


def build_trash(page, user, navigate):
    content = ft.Column(spacing=8)
    message = ft.Text()

    def restore(task_id):
        try:
            Workspace.restore_task(user.id, task_id)
            message.value = "Đã khôi phục công việc. Các khoảng lịch đã xóa cần được xếp lại."
            render()
        except Exception:
            message.value = "Không khôi phục được công việc. Hãy thử lại."
        page.update()

    def render():
        content.controls = [ft.Row([
            ft.Text(item["title"], expand=True, max_lines=2),
            ft.Text(item["deleted_at"][:10], size=12, color="#666666"),
            ft.TextButton("Khôi phục", on_click=lambda e, task_id=item["id"]: restore(task_id)),
        ]) for item in Workspace.trash(user.id)]
        if not content.controls:
            content.controls = [ft.Text("Thùng rác đang trống.", color="#666666")]
    render()
    return ft.Column([ft.Text("Thùng rác", size=30, weight=ft.FontWeight.W_600),
                      ft.Text("Công việc đã xóa có thể được khôi phục."), message, content], spacing=20, expand=True, scroll=ft.ScrollMode.AUTO)


def build_schedule(page, user, navigate):
    c = palette(page)
    day = ft.TextField(label="Ngày", value=date.today().isoformat(), width=160, text_size=13)
    title = ft.TextField(label="Tên lịch cố định", expand=True, text_size=13)
    start = ft.TextField(label="Bắt đầu", value="09:00", width=110, text_size=13)
    end = ft.TextField(label="Kết thúc", value="10:00", width=110, text_size=13)
    message = ft.Text()
    saved = ft.Column(spacing=8)
    proposal_view = ft.Column(spacing=8)
    state = {"proposal": None, "day": None}
    apply_button = ft.OutlinedButton("Áp dụng lịch đề xuất", disabled=True)

    def read_day():
        return date.fromisoformat(day.value.strip()).isoformat()

    def render():
        try:
            blocks = Workspace.blocks(user.id, read_day())
            saved.controls = [ft.Row([
                ft.Text(item["start_at"][11:16] + "–" + item["end_at"][11:16], width=115, size=13),
                ft.Text(item["title"], expand=True, max_lines=2),
                ft.IconButton(icon=ft.Icons.DELETE_OUTLINE, tooltip="Xóa khoảng lịch", on_click=lambda e, item=item: remove(item["id"])),
            ]) for item in blocks] or [ft.Text("Chưa có lịch trong ngày này.", color=c["muted"])]
        except ValueError:
            message.value = "Nhập ngày theo YYYY-MM-DD."

    def remove(block_id):
        try:
            Workspace.delete_block(user.id, block_id)
            render()
        except Exception:
            message.value = "Không xóa được khoảng lịch."
        page.update()

    def add(_):
        try:
            current_day = read_day()
            Workspace.save_blocks(user.id, [{"title": title.value.strip(), "start_at": current_day + "T" + start.value.strip(), "end_at": current_day + "T" + end.value.strip()}])
            title.value = ""
            message.value = "Đã lưu lịch cố định."
            render()
        except (ValueError, TypeError) as exc:
            message.value = str(exc)
        except Exception:
            message.value = "Không lưu được lịch. Hãy thử lại."
        page.update()

    def propose(_):
        from core.planning import propose_day
        from core.access import require_feature
        try:
            require_feature(user.id, "smart_schedule")
            selected_day = read_day()
            now = datetime.now()
            fixed = [item for item in Workspace.blocks(user.id, selected_day) if item["source"] != "proposal" or datetime.fromisoformat(item['start_at']) < now]
            tasks = TaskService.get_tasks(user.id)
            ongoing_ids = {item['task_id'] for item in fixed if item.get('task_id')}
            tasks = [task for task in tasks if task.id not in ongoing_ids]
            result = propose_day(tasks, fixed, selected_day, user.work_start, user.work_end)
            accepted, rejected = result["blocks"], result["unscheduled"]
            state.update(proposal=accepted, day=selected_day)
            proposal_view.controls = []
            for item in accepted:
                begin = ft.TextField(value=item['start_at'][11:16], label='Bắt đầu', width=110, text_size=13)
                finish = ft.TextField(value=item['end_at'][11:16], label='Kết thúc', width=110, text_size=13)
                item['_begin'], item['_finish'] = begin, finish
                proposal_view.controls.append(ft.Row([begin, finish, ft.Text(item['title'], expand=True)], spacing=12))
            if rejected:
                proposal_view.controls.append(ft.Text("Chưa xếp đủ: " + "; ".join(dict.fromkeys(rejected)), color=c["muted"]))
            apply_button.disabled = not accepted
            message.value = "Đề xuất theo ưu tiên, phụ thuộc và giờ trống. Lịch đã bắt đầu được giữ. Bạn có thể sửa giờ trước khi áp dụng; chưa thay đổi dữ liệu."
        except Exception as exc:
            message.value = str(exc) if isinstance(exc, ValueError) else "Không tạo được lịch đề xuất."
        page.update()

    def apply(_):
        try:
            from core.access import require_feature
            require_feature(user.id, 'smart_schedule')
            if not state["proposal"] or read_day() != state["day"]:
                raise ValueError("Ngày đã thay đổi. Hãy tạo lại đề xuất.")
            edited = []
            for item in state['proposal']:
                begin = datetime.fromisoformat(state['day'] + 'T' + item['_begin'].value.strip())
                finish = datetime.fromisoformat(state['day'] + 'T' + item['_finish'].value.strip())
                original_minutes = (datetime.fromisoformat(item['end_at']) - datetime.fromisoformat(item['start_at'])).total_seconds()
                if (finish - begin).total_seconds() != original_minutes:
                    raise ValueError('Giữ nguyên thời lượng từng phiên khi dời giờ; sửa thời lượng công việc rồi đề xuất lại nếu cần.')
                edited.append({key: value for key, value in dict(item, start_at=begin.isoformat(), end_at=finish.isoformat()).items() if not key.startswith('_')})
            Workspace.save_blocks(user.id, edited, replace_day=state["day"])
            state["proposal"] = None
            apply_button.disabled = True
            proposal_view.controls.clear()
            message.value = "Đã áp dụng lịch. Hạn hoàn thành công việc được giữ nguyên."
            render()
        except Exception as exc:
            message.value = str(exc) if isinstance(exc, ValueError) else "Không áp dụng được lịch; hãy thử lại."
        page.update()
    apply_button.on_click = apply
    def change_day(_):
        state["proposal"] = None
        apply_button.disabled = True
        proposal_view.controls.clear()
        render()
        page.update()
    day.on_submit = change_day
    render()
    return ft.Column([
        ft.Text("Lịch làm việc", size=30, weight=ft.FontWeight.W_600),
        ft.Row([day, ft.OutlinedButton("Xem ngày", on_click=change_day), ft.TextButton("Sắp xếp lại phần còn lại", icon=ft.Icons.EVENT_REPEAT, on_click=propose)], wrap=True),
        ft.Row([title, start, end, ft.IconButton(icon=ft.Icons.ADD, tooltip="Thêm lịch cố định", on_click=add)]),
        message, saved, ft.Divider(color=c["line"]), proposal_view, apply_button,
        ft.Text("Lịch đề xuất dùng giờ làm việc trong Cài đặt. Lịch cố định nhắc lúc bắt đầu. Bật nhắc nền trong Cài đặt để nhận thông báo khi đóng cửa sổ.", size=12, color=c["muted"]),
    ], spacing=18, expand=True, scroll=ft.ScrollMode.AUTO)
