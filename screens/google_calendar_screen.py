"""Explicit account consent and per-event conflict choices for Google Calendar."""
import asyncio
from datetime import datetime
import flet as ft
from core.cloud import CloudClient


def build_google_panel(page, user):
    client = CloudClient(user.id)
    message = ft.Text('Kiểm tra kết nối để liên kết một lịch Google riêng tên TaskFlow.', size=13, color='#666666')
    conflicts = ft.Column(spacing=8)
    launcher = ft.UrlLauncher()
    page.services.append(launcher)
    state = {'busy': False, 'connected': False}
    async def run(action, payload=None):
        if state['busy']:
            return
        state['busy'] = True
        for button in buttons:
            button.disabled = True
        message.value = 'Đang xử lý Google Calendar…'
        page.update()
        try:
            result = await asyncio.to_thread(client.request, 'GET' if action == 'status' else 'POST', '/v1/google/' + action, payload)
            if action == 'connect':
                from urllib.parse import urlsplit
                url = result['authorization_url']
                parts = urlsplit(url)
                if parts.scheme != 'https' or parts.hostname != 'accounts.google.com':
                    raise ValueError('Địa chỉ cấp quyền Google không hợp lệ.')
                await launcher.launch_url(url)
                message.value = 'Hoàn tất cấp quyền trên trình duyệt, sau đó chọn Kiểm tra kết nối.'
            elif action in ('status', 'sync'):
                if 'connected' not in result:
                    message.value = result.get('message', 'Google đang đồng bộ.')
                    return
                state['connected'] = result['connected']
                message.value = ('Đã liên kết lịch TaskFlow. ' + ('Đồng bộ gần nhất: ' + datetime.fromtimestamp(result['last_sync']).strftime('%d/%m %H:%M') if result.get('last_sync') else 'Chưa đồng bộ.')) if result['connected'] else 'Google Calendar chưa được nhà phát hành kết nối.' if not result.get('configured') else 'Chưa liên kết Google Calendar.'
                if result.get('error'):
                    message.value += ' ' + result['error']
                conflicts.controls = [ft.Row([ft.Text(item['title'], expand=True, max_lines=2),
                    ft.TextButton('Giữ TaskFlow', on_click=lambda e, key=item['local_id']: page.run_task(run, 'resolve', {'local_id': key, 'choice': 'taskflow'})),
                    ft.TextButton('Dùng Google', on_click=lambda e, key=item['local_id']: page.run_task(run, 'resolve', {'local_id': key, 'choice': 'google'}))], wrap=True) for item in result.get('conflicts', [])]
            else:
                message.value = result['message']
        except ValueError as exc:
            message.value = str(exc)
        except Exception:
            message.value = 'Chưa xử lý được. Hãy thử lại; lịch hiện có vẫn được giữ.'
        finally:
            state['busy'] = False
            for button in buttons:
                button.disabled = False
            page.update()
    def disconnect(_):
        def confirm(_):
            dialog.open = False
            page.run_task(run, 'disconnect')
        def cancel(_):
            dialog.open = False
            page.update()
        dialog = ft.AlertDialog(title=ft.Text('Ngắt liên kết Google?'), content=ft.Text('Dừng đồng bộ với Google. Lịch trên Google và dữ liệu TaskFlow hiện có vẫn được giữ.'),
            actions=[ft.TextButton('Hủy', on_click=cancel), ft.TextButton('Ngắt liên kết', on_click=confirm)])
        page.overlay.append(dialog)
        dialog.open = True
        page.update()
    buttons = [ft.OutlinedButton('Liên kết Google', on_click=lambda e: page.run_task(run, 'connect')),
               ft.TextButton('Kiểm tra kết nối', on_click=lambda e: page.run_task(run, 'status')),
               ft.TextButton('Đồng bộ Google', on_click=lambda e: page.run_task(run, 'sync')),
               ft.TextButton('Ngắt liên kết', on_click=disconnect)]
    return ft.Column([ft.Text('Google Calendar', size=20, weight=ft.FontWeight.W_600),
        ft.Text('Một lịch riêng tên TaskFlow, đồng bộ hai chiều. Bạn có thể thêm lịch từ Google Calendar trên điện thoại mà không mở app desktop.', size=13, color='#666666'),
        ft.Row(buttons, wrap=True), message, conflicts,
        ft.Text('Thông báo trên điện thoại do Google Calendar và quyền thông báo của thiết bị quản lý. Đồng bộ khi desktop đóng cần API và calendar worker đang chạy trên máy chủ.', size=13, color='#666666')], spacing=12)
