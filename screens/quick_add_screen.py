"""Small standalone desktop window invoked from the system tray or shortcut."""
import asyncio
from datetime import datetime, timedelta
import flet as ft
from components.desktop_style import desktop_theme
from core.services import AuthService
from core.workspace import Workspace


def quick_add_main(page):
    page.title = 'TaskFlow · Thêm lịch nhanh'
    page.window.width, page.window.height = 480, 560
    page.window.min_width, page.window.min_height = 420, 500
    page.padding = 24
    page.bgcolor = '#FFFFFF'
    page.theme, page.theme_mode = desktop_theme(), ft.ThemeMode.LIGHT
    user = AuthService.get_current_user()
    if not user:
        from core.tray import open_window
        page.add(ft.Column([ft.Text('Đăng nhập để thêm lịch', size=24, weight=ft.FontWeight.W_600),
            ft.Text('Mở TaskFlow và đăng nhập tài khoản trên máy này trước.', color='#666666'),
            ft.OutlinedButton('Mở TaskFlow', on_click=lambda e: open_window())], spacing=18))
        return
    soon = (datetime.now() + timedelta(minutes=15)).replace(second=0, microsecond=0)
    title = ft.TextField(label='Tên công việc / lịch', autofocus=True, text_size=14)
    day = ft.TextField(label='Ngày · YYYY-MM-DD', value=soon.date().isoformat(), expand=True)
    time = ft.TextField(label='Giờ · HH:MM', value=soon.strftime('%H:%M'), width=120)
    duration = ft.TextField(label='Thời lượng (phút)', value='30', expand=True)
    reminder = ft.TextField(label='Nhắc trước (phút)', value='15', expand=True)
    message = ft.Text(size=13, color='#666666')
    async def save(_):
        if button.disabled:
            return
        button.disabled = True
        message.value = 'Đang lưu…'
        page.update()
        closed = False
        try:
            await asyncio.to_thread(Workspace.quick_add, user.id, title.value or '',
                (day.value or '').strip() + 'T' + (time.value or '').strip(), int(duration.value), int(reminder.value))
            message.value = 'Đã lưu trên máy. Sẽ đồng bộ khi tiến trình nền đã kết nối tài khoản.'
            page.update()
            await page.window.destroy()
            closed = True
        except ValueError as exc:
            message.value = str(exc) if not str(exc).startswith(('Invalid', 'invalid')) else 'Kiểm tra ngày, giờ và số phút rồi thử lại.'
        except Exception:
            message.value = 'Chưa lưu được. Nội dung vẫn được giữ; hãy thử lại.'
        finally:
            button.disabled = False
            if not closed:
                page.update()
    button = ft.OutlinedButton('Thêm lịch và đóng', icon=ft.Icons.ADD, on_click=save)
    from core.tray import open_window
    title.on_submit = save
    page.add(ft.Column([ft.Text('Thêm lịch nhanh', size=26, weight=ft.FontWeight.W_600),
        ft.Text(user.full_name or user.username, size=13, color='#666666'), title,
        ft.Row([day, time]), ft.Row([duration, reminder]), message, ft.Row([button, ft.TextButton('Mở TaskFlow', on_click=lambda e: open_window())]),
        ft.Text('Lưu được khi mất mạng. Để nhận thông báo sau khi đóng cửa sổ, bật nhắc nền trong Cài đặt.', size=13, color='#666666')], spacing=18, scroll=ft.ScrollMode.AUTO, expand=True, horizontal_alignment=ft.CrossAxisAlignment.STRETCH))
