"""
TaskFlow - Settings Screen
"""
import flet as ft
from core.theme import Colors, Typography, Spacing, Radius
from core.services import AuthService
from components.widgets import primary_button, primary_divider, avatar_circle, snack

AVATAR_COLORS = [
    "#F5A623","#8B5CF6","#06B6D4","#FB923C","#F43F5E",
    "#F59E0B","#3B82F6","#EC4899","#6B7280","#A855F7",
]

def build_settings_screen(page: ft.Page, user, on_navigate, on_logout):
    sel_color = {"v": user.avatar_color}

    def save_profile(_):
        new_name = tf_name.value.strip() or user.username
        AuthService.update_profile(user, new_name, sel_color["v"])
        # Update UI avatar circle color
        avatar_placeholder.content = avatar_circle(user.full_name, user.avatar_color, 80)
        snack(page, "Đã cập nhật tài khoản ✓")
        page.update()

    def change_password(_):
        old = tf_old_pwd.value.strip()
        new = tf_new_pwd.value.strip()
        cfm = tf_cfm_pwd.value.strip()
        if not old or not new:
            snack(page, "Vui lòng nhập đầy đủ!", success=False); return
        ok, msg = AuthService.change_password(user, old, new, cfm)
        if not ok:
            snack(page, msg, success=False); return
        tf_old_pwd.value = tf_new_pwd.value = tf_cfm_pwd.value = ""
        snack(page, msg)
        page.update()

    def do_logout(_):
        AuthService.logout()
        on_logout()

    avatar_placeholder = ft.Container(
        content=avatar_circle(user.full_name or user.username, user.avatar_color, 80),
        alignment=ft.Alignment.CENTER,
    )

    def color_circle(color: str) -> ft.GestureDetector:
        selected_border = ft.Ref[ft.Container]()
        c = ft.Container(
            content=ft.Container(
                width=30, height=30, border_radius=Radius.FULL, bgcolor=color, ref=selected_border,
            ),
            padding=3, border_radius=Radius.FULL,
            border=ft.Border.all(2, Colors.PRIMARY if color == sel_color["v"] else "transparent"),
        )
        def _pick(_):
            sel_color["v"] = color
            avatar_placeholder.content = avatar_circle(
                tf_name.value.strip() or user.full_name or user.username, color, 80)
            for gc in color_pickers:
                gc.content.border = ft.border.all(
                    2, Colors.PRIMARY if gc.content.content.bgcolor == color else "transparent"
                )
            page.update()
        return ft.GestureDetector(content=c, on_tap=_pick)

    color_pickers = [color_circle(c) for c in AVATAR_COLORS]

    tf_name = ft.TextField(
        label="Họ và tên", value=user.full_name, bgcolor=Colors.BG_INPUT, border_color=Colors.BORDER,
        focused_border_color=Colors.PRIMARY, text_style=ft.TextStyle(color=Colors.TEXT_PRIMARY),
        label_style=ft.TextStyle(color=Colors.TEXT_SECONDARY), border_radius=Radius.MD, cursor_color=Colors.PRIMARY,
    )

    tf_old_pwd = ft.TextField(label="Mật khẩu cũ", password=True, can_reveal_password=True,
        bgcolor=Colors.BG_INPUT, border_color=Colors.BORDER, focused_border_color=Colors.PRIMARY,
        text_style=ft.TextStyle(color=Colors.TEXT_PRIMARY), label_style=ft.TextStyle(color=Colors.TEXT_SECONDARY),
        border_radius=Radius.MD, cursor_color=Colors.PRIMARY)

    tf_new_pwd = ft.TextField(label="Mật khẩu mới", password=True, can_reveal_password=True,
        bgcolor=Colors.BG_INPUT, border_color=Colors.BORDER, focused_border_color=Colors.PRIMARY,
        text_style=ft.TextStyle(color=Colors.TEXT_PRIMARY), label_style=ft.TextStyle(color=Colors.TEXT_SECONDARY),
        border_radius=Radius.MD, cursor_color=Colors.PRIMARY)

    tf_cfm_pwd = ft.TextField(label="Xác nhận mật khẩu mới", password=True, can_reveal_password=True,
        bgcolor=Colors.BG_INPUT, border_color=Colors.BORDER, focused_border_color=Colors.PRIMARY,
        text_style=ft.TextStyle(color=Colors.TEXT_PRIMARY), label_style=ft.TextStyle(color=Colors.TEXT_SECONDARY),
        border_radius=Radius.MD, cursor_color=Colors.PRIMARY)

    def section_card(title, icon, content_widget):
        return ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Text(icon, size=16),
                    ft.Text(title, size=Typography.H4, color=Colors.TEXT_PRIMARY, weight=Typography.SEMIBOLD),
                ], spacing=Spacing.SM),
                primary_divider(0.2),
                ft.Container(height=Spacing.SM),
                content_widget,
            ], spacing=Spacing.SM, tight=True),
            padding=Spacing.MD, border_radius=Radius.LG,
            bgcolor=Colors.BG_CARD, border=ft.Border.all(1, Colors.BORDER),
            shadow=ft.BoxShadow(
                blur_radius=12,
                color="#00000018",
                offset=ft.Offset(0, 3),
            ),
        )

    def info_row(icon, label, value):
        return ft.Row([
            ft.Container(content=ft.Text(icon, size=16), width=36, height=36,
                         border_radius=Radius.MD, bgcolor=Colors.BG_SURFACE,
                         alignment=ft.Alignment.CENTER),
            ft.Column([
                ft.Text(label, size=Typography.TINY, color=Colors.TEXT_MUTED),
                ft.Text(value, size=Typography.BODY, color=Colors.TEXT_PRIMARY, weight=Typography.MEDIUM),
            ], spacing=0, tight=True, expand=True),
        ], spacing=Spacing.SM, vertical_alignment=ft.CrossAxisAlignment.CENTER)

    # HEADER
    header = ft.Container(
        content=ft.Row([
            ft.IconButton(ft.Icons.ARROW_BACK_IOS_NEW_ROUNDED, on_click=lambda _: on_navigate("profile")),
            ft.Text("Cài đặt", size=Typography.H2, color=Colors.TEXT_PRIMARY, weight=Typography.BOLD),
        ]),
        padding=ft.Padding.symmetric(horizontal=Spacing.MD, vertical=Spacing.MD),
    )

    body = ft.Column([
        header,
        ft.Container(
            content=ft.Column([
                section_card("Thông tin cơ bản", "👤",
                    ft.Column([
                        ft.Container(
                            content=ft.Column([
                                avatar_placeholder,
                                ft.Container(height=Spacing.SM),
                                ft.Row(color_pickers, alignment=ft.MainAxisAlignment.CENTER, spacing=Spacing.XS, wrap=True),
                                ft.Text("Chọn màu avatar", size=Typography.TINY, color=Colors.TEXT_MUTED, text_align=ft.TextAlign.CENTER),
                            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=Spacing.XS),
                            alignment=ft.Alignment.CENTER,
                        ),
                        ft.Container(height=Spacing.MD),
                        info_row("👤", "Tên đăng nhập", user.username),
                        ft.Container(height=Spacing.SM),
                        info_row("📧", "Email", user.email),
                        ft.Container(height=Spacing.MD),
                        tf_name,
                        ft.Container(height=Spacing.MD),
                        primary_button("Lưu thay đổi", on_click=save_profile, icon=ft.Icons.SAVE_OUTLINED, height=44),
                    ], spacing=0, tight=True)
                ),
                ft.Container(height=Spacing.SM),
                section_card("Đổi mật khẩu", "🔒",
                    ft.Column([
                        tf_old_pwd, ft.Container(height=Spacing.SM), tf_new_pwd, ft.Container(height=Spacing.SM), tf_cfm_pwd, ft.Container(height=Spacing.MD),
                        primary_button("Đổi mật khẩu", on_click=change_password, icon=ft.Icons.LOCK_RESET_OUTLINED, outlined=True, height=44),
                    ], spacing=0, tight=True)
                ),
                ft.Container(height=Spacing.SM),
                ft.Container(
                    content=ft.Row([
                        ft.Icon(ft.Icons.LOGOUT_ROUNDED, color=Colors.TEXT_MUTED, size=20),
                        ft.Text("Đăng xuất", size=Typography.BODY, color=Colors.TEXT_MUTED, weight=Typography.SEMIBOLD),
                    ], alignment=ft.MainAxisAlignment.CENTER, spacing=Spacing.SM),
                    height=48, border_radius=Radius.MD, border=ft.Border.all(1.5, Colors.BORDER),
                    bgcolor=Colors.BG_SURFACE, on_click=do_logout, ink=True,
                    shadow=ft.BoxShadow(
                        blur_radius=8,
                        color="#00000010",
                        offset=ft.Offset(0, 2),
                    ),
                ),
                ft.Container(height=Spacing.XXXL),
                ft.Container(height=Spacing.XXXL),
            ], scroll=ft.ScrollMode.AUTO, spacing=0, tight=True),
            padding=ft.padding.symmetric(horizontal=Spacing.MD),
            expand=True
        )
    ], spacing=0, tight=True, scroll=ft.ScrollMode.HIDDEN)

    return body
