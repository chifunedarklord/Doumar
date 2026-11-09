"""Account connection, recoverable synchronization and desktop reminder settings."""
import asyncio
from dataclasses import replace
import flet as ft
from core.cloud import CloudClient, CloudError, session_for


def build_sync_panel(page, user, on_download=None):
    from core.sync import synchronize, status
    saved = status(user.id)
    connected = bool(session_for(user.id))
    persisted = bool(session_for(user.id).get('persistent'))
    initial = ('Đồng bộ gần nhất: ' + saved['last_synced'][:16].replace('T', ' ')) if saved.get('last_synced') else 'Dữ liệu đã lưu trên máy; chưa đồng bộ.'
    message = ft.Text(initial, size=13, color='#666666', selectable=True)
    choices = ft.Row(visible=False, wrap=True)
    state = {'busy': False}
    async def run(_, choice=None):
        if state['busy']:
            return
        state['busy'], button.disabled = True, True
        for control in choices.controls:
            control.disabled = True
        message.value = 'Đang đồng bộ…'
        page.update()
        try:
            result = await asyncio.to_thread(synchronize, user.id, choice)
            message.value = result['message']
            choices.visible = result['state'] == 'conflict'
            if result['state'] in ('downloaded', 'merged') and on_download:
                on_download()
            if result['state'] in ('downloaded', 'merged'):
                from core.repositories import Storage
                fresh = next((item for item in Storage.get_users() if item.id == user.id), None)
                if fresh:
                    for key in ('full_name', 'work_start', 'work_end', 'timezone'):
                        setattr(user, key, getattr(fresh, key))
                message.value += ' · Mở lại trang để cập nhật nội dung đang xem.'
        except (ValueError, CloudError) as exc:
            message.value = str(exc)
        except Exception:
            message.value = 'Chưa đồng bộ được. Dữ liệu trên máy vẫn được giữ; hãy thử lại.'
        finally:
            state['busy'], button.disabled = False, not connected
            for control in choices.controls:
                control.disabled = False
            page.update()
    def choose(choice):
        def confirm(_):
            dialog.open = False
            page.run_task(run, None, choice)
        def cancel(_):
            dialog.open = False
            page.update()
        dialog = ft.AlertDialog(title=ft.Text('Giữ bản trên máy?' if choice == 'local' else 'Giữ bản máy chủ?'),
            content=ft.Text('Bản còn lại sẽ được lưu vào thư mục recovery cạnh cơ sở dữ liệu trước khi thay thế. Đây là lựa chọn cho toàn bộ không gian làm việc.'),
            actions=[ft.TextButton('Hủy', on_click=cancel), ft.TextButton('Xác nhận', on_click=confirm)])
        page.overlay.append(dialog)
        dialog.open = True
        page.update()
    choices.controls = [ft.OutlinedButton('Giữ bản trên máy', on_click=lambda e: choose('local')),
                        ft.OutlinedButton('Giữ bản máy chủ', on_click=lambda e: choose('remote'))]
    button = ft.OutlinedButton('Đồng bộ ngay', icon=ft.Icons.SYNC, on_click=run, disabled=not connected)
    return ft.Column([
        ft.Text('Đồng bộ tài khoản', size=20, weight=ft.FontWeight.W_600),
        ft.Text('Tự đồng bộ mỗi phút khi đang mở trang công việc, lịch hoặc báo cáo.' if connected else
                'Chưa kết nối máy chủ.' if not CloudClient().configured else 'Hãy đăng xuất và đăng nhập lại để kết nối máy chủ.', size=13, color='#666666'),
        ft.Text('Chưa lưu được phiên đăng nhập trong kho khóa hệ điều hành. Đồng bộ sẽ dừng khi đóng cửa sổ.' if connected and not persisted else 'Phiên đăng nhập được giữ trong kho khóa hệ điều hành để tiếp tục đồng bộ khi đóng cửa sổ.' if connected else '', size=13, color='#666666', visible=connected),
        message, ft.Row([button]), choices,
    ], spacing=12)


def build_reminder_settings(page, user):
    from core.repositories import Storage
    from core.reminders import start_agent, set_autostart, autostart_enabled
    message = ft.Text(size=13, color='#666666')
    enabled = ft.Switch(label='Thông báo nhắc việc trên desktop', value=user.settings.get('desktop_reminders', True))
    background = ft.Switch(label='Tiếp tục nhắc khi đóng cửa sổ', value=user.settings.get('background_reminders', False))
    startup = ft.Switch(label='Khởi động nhắc nền khi đăng nhập Windows / Linux', value=autostart_enabled())
    async def save(_):
        previous = dict(user.settings)
        try:
            if startup.value and not background.value:
                background.value = True
            if background.value:
                enabled.value = True
            await asyncio.to_thread(set_autostart, bool(startup.value))
            current = next(u for u in Storage.get_users() if u.id == user.id)
            settings = dict(current.settings, desktop_reminders=bool(enabled.value), background_reminders=bool(background.value))
            Storage.save_user(replace(current, settings=settings))
            user.settings = settings
            if background.value:
                start_agent()
            message.value = 'Đã lưu nhắc việc.'
        except Exception:
            message.value = 'Không lưu được. Kiểm tra quyền cài tự khởi động rồi thử lại.'
            user.settings = previous
        page.update()
    async def test(_):
        from core.reminders import send_notification
        sent = await asyncio.to_thread(send_notification, 'TaskFlow', 'Thông báo nhắc việc đang hoạt động.')
        message.value = 'Đã gửi thông báo thử. Kiểm tra trung tâm thông báo của hệ điều hành.' if sent else 'Chưa gửi được. Kiểm tra quyền thông báo và dịch vụ thông báo của hệ điều hành.'
        page.update()
    return ft.Column([ft.Text('Nhắc việc', size=20, weight=ft.FontWeight.W_600), enabled, background, startup,
        ft.Text('Sau khi máy bật lại, app nhắc bù lịch trong 24 giờ gần nhất. Máy tắt hoặc đang ngủ không thể phát thông báo. Đăng xuất sẽ dừng nhắc cho tài khoản đó.', size=13, color='#666666'),
        ft.Row([ft.OutlinedButton('Lưu nhắc việc', on_click=save), ft.TextButton('Gửi thông báo thử', on_click=test)], wrap=True), message], spacing=12)
