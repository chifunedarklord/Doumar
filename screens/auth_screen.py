"""
TaskFlow - Login / Register Screen (Redesign)
Luxury dark theme - Clean & balanced
"""
import flet as ft
from core.theme import Colors, Typography, Spacing, Radius
from core.services import AuthService

login    = AuthService.login
register = AuthService.register
from components.widgets import (
    text_input, snack, primary_button
)


def build_auth_screen(page: ft.Page, on_login_success):

    page.bgcolor = Colors.BG_DARKEST
    page.padding = 0

    # ── STATE ─────────────────────────────
    state = {"is_login": True}

    # ── INPUTS ────────────────────────────
    tf_username = text_input("Tên đăng nhập", "Nhập username...",
                            prefix_icon=ft.Icons.PERSON_OUTLINE, value="admin")

    tf_email = text_input("Email", "Nhập email...",
                         prefix_icon=ft.Icons.EMAIL_OUTLINED,
                         value="admin@taskflow.com")

    tf_fullname = text_input("Họ và tên", "Nhập họ tên...",
                            prefix_icon=ft.Icons.BADGE_OUTLINED,
                            value="Admin Test")

    tf_password = text_input("Mật khẩu", "Nhập mật khẩu...",
                            password=True,
                            prefix_icon=ft.Icons.LOCK_OUTLINE,
                            value="123456")

    tf_confirm = text_input("Xác nhận mật khẩu", "Nhập lại...",
                           password=True,
                           prefix_icon=ft.Icons.LOCK_RESET_OUTLINED,
                           value="123456")

    err_text = ft.Text("", color=Colors.ERROR,
                       size=Typography.SMALL,
                       text_align=ft.TextAlign.CENTER)

    # ── REFS ──────────────────────────────
    extra_ref = ft.Ref[ft.Column]()
    confirm_ref = ft.Ref[ft.Container]()
    title_ref = ft.Ref[ft.Text]()
    sub_ref = ft.Ref[ft.Text]()
    toggle_prompt_ref = ft.Ref[ft.Text]()
    toggle_btn_ref = ft.Ref[ft.TextButton]()

    # ── EVENTS ────────────────────────────
    def clear_err(_=None):
        err_text.value = ""
        page.update()

    tf_username.on_change = clear_err
    tf_password.on_change = clear_err

    def handle_submit(_=None):
        err_text.value = ""

        uname = tf_username.value.strip()
        pwd = tf_password.value.strip()

        if state["is_login"]:
            if not uname or not pwd:
                err_text.value = "Vui lòng nhập đầy đủ"
                page.update()
                return

            ok, msg, user = login(uname, pwd)

            if ok:
                snack(page, msg, success=True)
                on_login_success(user)
            else:
                err_text.value = msg
                page.update()

        else:
            email = tf_email.value.strip()
            fname = tf_fullname.value.strip()
            confirm = tf_confirm.value.strip()

            if not uname or not email or not pwd:
                err_text.value = "Vui lòng nhập đầy đủ"
                page.update()
                return

            if pwd != confirm:
                err_text.value = "Mật khẩu không khớp"
                page.update()
                return

            ok, msg = register(uname, email, pwd, fname)

            if ok:
                snack(page, "Đăng ký thành công!", success=True)
                switch_mode(None)
            else:
                err_text.value = msg
                page.update()

    def switch_mode(_):
        state["is_login"] = not state["is_login"]
        mode = state["is_login"]

        extra_ref.current.visible = not mode
        confirm_ref.current.visible = not mode

        title_ref.current.value = "Chào mừng trở lại" if mode else "Tạo tài khoản"
        sub_ref.current.value = "Đăng nhập để tiếp tục" if mode else "Tạo tài khoản mới"

        toggle_prompt_ref.current.value = "Chưa có tài khoản?" if mode else "Đã có tài khoản?"
        toggle_btn_ref.current.text = "Đăng ký" if mode else "Đăng nhập"

        err_text.value = ""
        page.update()

    # ── HEADER ────────────────────────────
    header = ft.Column([
    ft.Image(
        src="doumar1.png",
        width=320,
        height=120,
        fit="contain"
    ),

    ft.Text("Smart Task Manager",
            size=12,
            color=Colors.TEXT_MUTED)
    ],
    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    spacing=6)

    # ── TITLE ─────────────────────────────
    title_section = ft.Column([
        ft.Text("Chào mừng trở lại",
                ref=title_ref,
                size=22,
                weight=Typography.BOLD,
                color=Colors.TEXT_PRIMARY),

        ft.Text("Đăng nhập để tiếp tục",
                ref=sub_ref,
                size=13,
                color=Colors.TEXT_MUTED)
    ], spacing=4)

    # ── FORM ──────────────────────────────
    extra_fields = ft.Column([
        tf_fullname,
        tf_email
    ], spacing=12, visible=False, ref=extra_ref)

    confirm_field = ft.Container(
        content=tf_confirm,
        visible=False,
        ref=confirm_ref
    )

    form = ft.Column([
        tf_username,
        extra_fields,
        tf_password,
        confirm_field,
        err_text
    ], spacing=12)

    # ── BUTTON ────────────────────────────
    submit_btn = primary_button(
        "Xác nhận",
        on_click=handle_submit,
        width=200,
        height=48
    )

    # ── TOGGLE ────────────────────────────
    toggle = ft.Row([
        ft.Text("Chưa có tài khoản?",
                ref=toggle_prompt_ref,
                size=12,
                color=Colors.TEXT_MUTED),

        ft.TextButton("Đăng ký",
                      ref=toggle_btn_ref,
                      on_click=switch_mode,
                      style=ft.ButtonStyle(
                          color=Colors.PRIMARY
                      ))
    ], alignment=ft.MainAxisAlignment.CENTER)

    # ── CARD ──────────────────────────────
    card = ft.Container(
        content=ft.Column([
            header,
            ft.Divider(height=20, color="transparent"),
            title_section,
            ft.Divider(height=10, color="transparent"),
            form,
            ft.Divider(height=10, color="transparent"),
            ft.Container(submit_btn, alignment=ft.Alignment.CENTER),
            toggle
        ], spacing=8),

        width=360,
        padding=24,
        border_radius=16,
        bgcolor=Colors.BG_CARD,
        border=ft.border.all(1, Colors.BORDER),
        shadow=ft.BoxShadow(
            blur_radius=30,
            color="#10000000",
            offset=ft.Offset(0, 6)
        )
    )

    # ── BACKGROUND ────────────────────────
    bg = ft.Stack([
        ft.Container(bgcolor=Colors.BG_DARKEST, expand=True),

        ft.Container(
            width=260,
            height=260,
            border_radius=200,
            gradient=ft.RadialGradient(
                colors=["#222563EB", "transparent"]
            ),
            left=-80,
            top=-80
        ),

        ft.Container(
            width=220,
            height=220,
            border_radius=200,
            gradient=ft.RadialGradient(
                colors=["#228B5CF6", "transparent"]
            ),
            right=-60,
            bottom=80
        ),

        ft.Container(
            content=ft.Column([
                ft.Container(expand=True),
                card,
                ft.Container(expand=True)
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            expand=True
        )
    ])

    return ft.Container(content=bg, expand=True)