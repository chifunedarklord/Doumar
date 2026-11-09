"""Compact monochrome authentication with real browser-based social sign-in."""
import asyncio
import base64
import re
from pathlib import Path
from urllib.parse import urlsplit
import flet as ft
from core.services import AuthService
from core.cloud import CloudClient

INK, MUTED, LINE = '#111111', '#666666', '#E5E5E5'


def build_auth_screen(page, on_login_success):
    state = {'mode': 'login', 'busy': False, 'epoch': 0, 'ticket': None}
    client = CloudClient()
    launcher = ft.UrlLauncher()
    page.services.append(launcher)
    heading = ft.Text('Chào mừng trở lại', size=27, weight=ft.FontWeight.W_600, color=INK)
    subtitle = ft.Text('Tiếp tục với lịch học và công việc của bạn.', size=16, color=MUTED)
    message = ft.Text('', size=16, color=INK, selectable=True, visible=False)
    footnote = ft.Text('Tài khoản chỉ lưu trên máy này.' if not client.configured else 'Đăng nhập mạng xã hội sẽ tạo tài khoản nếu bạn chưa có.',
        size=14, color=MUTED, text_align=ft.TextAlign.CENTER)

    def field(label, icon, **kwargs):
        return ft.TextField(label=label, prefix_icon=icon, text_size=17, dense=True,
            border_color=LINE, focused_border_color=INK, border_radius=6,
            content_padding=ft.Padding.symmetric(horizontal=12, vertical=12), **kwargs)
    username = field('Tên đăng nhập', ft.Icons.PERSON_OUTLINE, autofocus=True, max_length=40, counter='')
    email = field('Email', ft.Icons.MAIL_OUTLINE, max_length=254, counter='', visible=False)
    password = field('Mật khẩu', ft.Icons.LOCK_OUTLINE, password=True, can_reveal_password=True)
    confirm = field('Nhập lại mật khẩu', ft.Icons.LOCK_OUTLINE, password=True, can_reveal_password=True, visible=False)
    token = field('Mã khôi phục trong email', ft.Icons.KEY_OUTLINED, visible=False)
    fields = [username, email, password, confirm, token]

    def inform(value):
        message.value, message.visible = value, bool(value)

    def busy(value):
        state['busy'] = value
        for control in [*fields, *social_buttons, login_tab, register_tab, submit, forgot, have_code, back]:
            control.disabled = value
        page.update()

    def mode(value):
        if state['busy']:
            return
        state['mode'] = value
        regular = value in ('login', 'register')
        footnote.visible = regular
        tabs.visible = social.visible = divider.visible = regular
        username.visible = regular
        email.visible = value in ('register', 'forgot')
        password.visible = value != 'forgot'
        confirm.visible = value in ('register', 'reset')
        token.visible = value == 'reset'
        password.value = confirm.value = token.value = ''
        heading.value = {'login': 'Chào mừng trở lại', 'register': 'Tạo tài khoản TaskFlow',
                         'forgot': 'Quên mật khẩu?', 'reset': 'Đặt lại mật khẩu'}[value]
        subtitle.value = {'login': 'Tiếp tục với lịch học và công việc của bạn.',
            'register': 'Một nơi gọn gàng cho kế hoạch mỗi ngày.',
            'forgot': 'Nhận mã khôi phục qua email của bạn.', 'reset': 'Nhập mã trong email và chọn mật khẩu mới.'}[value]
        submit.content = {'login': 'Đăng nhập', 'register': 'Tạo tài khoản', 'forgot': 'Gửi mã khôi phục', 'reset': 'Lưu mật khẩu mới'}[value]
        forgot.visible = value == 'login' and client.configured
        forgot_row.visible = forgot.visible
        have_code.visible = value == 'forgot'
        back.visible = not regular
        password.label = ('Mật khẩu · tối thiểu 10 ký tự' if client.configured else 'Mật khẩu · tối thiểu 6 ký tự') if value in ('register', 'reset') else 'Mật khẩu'
        for button, selected in ((login_tab, value == 'login'), (register_tab, value == 'register')):
            button.style = ft.ButtonStyle(bgcolor='#F1F1F1' if selected else '#FFFFFF', color=INK if selected else MUTED,
                shape=ft.RoundedRectangleBorder(radius=5), padding=8)
        inform('')
        page.update()

    async def handle(_=None):
        if state['busy']:
            return
        busy(True)
        inform('Đang xử lý…')
        page.update()
        try:
            current = state['mode']
            if current in ('register', 'reset') and password.value != confirm.value:
                raise ValueError('Mật khẩu nhập lại chưa khớp.')
            if current == 'login':
                if not (username.value or '').strip() or not password.value:
                    raise ValueError('Nhập tên đăng nhập và mật khẩu để tiếp tục.')
                ok, text, user = await asyncio.to_thread(AuthService.login, username.value.strip(), password.value)
                if not ok:
                    raise ValueError(text)
                on_login_success(user)
            elif current == 'register':
                if not (username.value or '').strip() or not (email.value or '').strip() or not password.value:
                    raise ValueError('Nhập tên đăng nhập, email và mật khẩu để tạo tài khoản.')
                if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email.value.strip()):
                    raise ValueError('Nhập địa chỉ email hợp lệ, ví dụ ban@example.com.')
                ok, text = await asyncio.to_thread(AuthService.register, username.value.strip(), email.value.strip(), password.value, '')
                if not ok:
                    raise ValueError(text)
                busy(False)
                mode('login')
                inform('Đã tạo tài khoản. Đăng nhập để bắt đầu.')
            else:
                data = {'email': (email.value or '').strip()} if current == 'forgot' else {'token': (token.value or '').strip(), 'password': password.value or ''}
                endpoint = '/v1/auth/forgot-password' if current == 'forgot' else '/v1/auth/reset-password'
                result = await asyncio.to_thread(client.request, 'POST', endpoint, data, False)
                inform(result['message'])
        except ValueError as exc:
            inform(str(exc))
        except Exception:
            inform('Chưa thực hiện được. Nội dung vẫn được giữ; hãy thử lại.')
        finally:
            busy(False)

    async def cancel_social(_=None):
        if cancel.disabled:
            return
        state['epoch'] += 1
        ticket = state['ticket']
        state['ticket'] = None
        cancel.visible = False
        inform('Đã hủy. Bạn có thể chọn cách đăng nhập khác.')
        busy(False)
        if ticket:
            try:
                await asyncio.to_thread(client.request, 'POST', '/v1/auth/social/cancel', {'ticket': ticket}, False)
            except ValueError:
                pass

    async def social_login(provider):
        if state['busy']:
            return
        state['epoch'] += 1
        attempt = state['epoch']
        name = 'Google' if provider == 'google' else 'Facebook'
        busy(True)
        cancel.disabled = False
        cancel.visible = True
        inform('Đang mở ' + name + '…')
        page.update()
        ticket = None
        try:
            result = await asyncio.to_thread(client.request, 'POST', '/v1/auth/social/start', {'provider': provider}, False)
            ticket = result['ticket']
            if attempt != state['epoch']:
                await asyncio.to_thread(client.request, 'POST', '/v1/auth/social/cancel', {'ticket': ticket}, False)
                return
            state['ticket'] = ticket
            url = result['authorization_url']
            parts = urlsplit(url)
            expected = 'accounts.google.com' if provider == 'google' else 'www.facebook.com'
            if parts.scheme != 'https' or parts.hostname != expected or parts.username or parts.password or parts.port not in (None, 443):
                raise ValueError('Địa chỉ đăng nhập không hợp lệ. Hãy thử lại.')
            await launcher.launch_url(url)
            inform('Hoàn tất đăng nhập ' + name + ' trên trình duyệt. TaskFlow đang chờ bạn quay lại…')
            page.update()
            deadline = asyncio.get_running_loop().time() + min(600, int(result.get('expires_in', 600)))
            while attempt == state['epoch'] and asyncio.get_running_loop().time() < deadline:
                status = await asyncio.to_thread(client.request, 'POST', '/v1/auth/social/status', {'ticket': ticket}, False)
                if attempt != state['epoch']:
                    return
                if status.get('status') == 'ready':
                    cancel.disabled = True
                    inform('Đang hoàn tất đăng nhập…')
                    page.update()
                    response = await asyncio.to_thread(client.request, 'POST', '/v1/auth/social/finish', {'ticket': ticket}, False)
                    if response.get('account', {}).get('id') != status.get('account', {}).get('id'):
                        raise ValueError('Tài khoản xác thực không khớp. Hãy thử lại.')
                    user = await asyncio.to_thread(AuthService.finish_social_login, response)
                    inform('Đã đăng nhập.')
                    on_login_success(user)
                    return
                await asyncio.sleep(2)
            if attempt == state['epoch']:
                raise ValueError('Đã hết thời gian chờ. Chọn ' + name + ' để đăng nhập lại.')
        except ValueError as exc:
            if attempt == state['epoch']:
                inform(str(exc))
        except Exception:
            if attempt == state['epoch']:
                inform('Chưa đăng nhập được bằng ' + name + '. Hãy thử lại hoặc dùng tài khoản TaskFlow.')
        finally:
            if attempt == state['epoch']:
                state['ticket'] = None
                cancel.visible = False
                cancel.disabled = False
                busy(False)

    google_image = base64.b64encode((Path(__file__).resolve().parents[1] / 'assets/google_g.png').read_bytes()).decode()
    def provider_button(label, icon, provider):
        return ft.OutlinedButton(content=ft.Row([icon, ft.Text(label, size=16, color=INK)], alignment=ft.MainAxisAlignment.CENTER, spacing=10),
            height=46, style=ft.ButtonStyle(side=ft.BorderSide(1, LINE), bgcolor='#FFFFFF',
                shape=ft.RoundedRectangleBorder(radius=6), padding=12),
            on_click=lambda e: page.run_task(social_login, provider))
    social_buttons = [provider_button('Tiếp tục với Google', ft.Image(src=google_image, width=19, height=19, fit=ft.BoxFit.CONTAIN, color=INK), 'google'),
                      provider_button('Tiếp tục với Facebook', ft.Icon(ft.Icons.FACEBOOK, size=22, color=INK), 'facebook')]
    social = ft.Column(social_buttons, spacing=8, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)
    divider = ft.Row([ft.Container(height=1, bgcolor=LINE, expand=True), ft.Text('hoặc dùng tài khoản', size=14, color=MUTED),
                      ft.Container(height=1, bgcolor=LINE, expand=True)], spacing=12)
    login_tab = ft.TextButton('Đăng nhập', expand=True, on_click=lambda e: mode('login'))
    register_tab = ft.TextButton('Tạo tài khoản', expand=True, on_click=lambda e: mode('register'))
    tabs = ft.Row([login_tab, register_tab], spacing=4)
    submit = ft.FilledButton('Đăng nhập', height=44, style=ft.ButtonStyle(
        bgcolor={ft.ControlState.DEFAULT: INK, ft.ControlState.HOVERED: '#333333', ft.ControlState.DISABLED: '#777777'},
        color='#FFFFFF', elevation=0, shape=ft.RoundedRectangleBorder(radius=6)), on_click=handle)
    forgot = ft.TextButton('Quên mật khẩu?', visible=client.configured, on_click=lambda e: mode('forgot'))
    have_code = ft.TextButton('Tôi đã có mã khôi phục', visible=False, on_click=lambda e: mode('reset'))
    back = ft.TextButton('Quay lại đăng nhập', icon=ft.Icons.ARROW_BACK, visible=False, on_click=lambda e: mode('login'))
    cancel = ft.TextButton('Hủy đăng nhập bằng trình duyệt', visible=False, on_click=cancel_social)
    forgot_row = ft.Row([forgot], alignment=ft.MainAxisAlignment.END, visible=client.configured)
    password.on_submit = confirm.on_submit = handle
    login_tab.style = ft.ButtonStyle(bgcolor='#F1F1F1', color=INK, shape=ft.RoundedRectangleBorder(radius=5), padding=8)
    register_tab.style = ft.ButtonStyle(color=MUTED, padding=8)
    return ft.Column([
        ft.Row([ft.Icon(ft.Icons.CHECK_BOX_OUTLINED, size=23, color=INK), ft.Text('TaskFlow', size=17, weight=ft.FontWeight.W_600, color=INK)], spacing=8),
        ft.Column([heading, subtitle], spacing=6), tabs,
        social, divider, ft.Column(fields, spacing=10, horizontal_alignment=ft.CrossAxisAlignment.STRETCH),
        forgot_row,
        message, submit, cancel, have_code, back,
        footnote,
    ], spacing=12, tight=True, scroll=ft.ScrollMode.AUTO, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)
