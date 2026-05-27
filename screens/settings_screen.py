"""
TaskFlow - Settings Screen
"""
import flet as ft
from core.theme import Colors, Typography, Spacing, Radius
from core.services import AuthService
from components.widgets import primary_button, primary_divider, avatar_circle, snack
from core.i18n import t, get_lang, set_lang

AVATAR_COLORS = [
    "#F5A623","#8B5CF6","#06B6D4","#FB923C","#F43F5E",
    "#F59E0B","#3B82F6","#EC4899","#6B7280","#A855F7",
]

def build_settings_screen(page: ft.Page, user, on_navigate, on_logout):
    sel_color = {"v": user.avatar_color}

    def save_profile(_):
        new_name = tf_name.value.strip() or user.username
        AuthService.update_profile(user, new_name, sel_color["v"])
        if tf_work_start.value and ":" in tf_work_start.value:
            user.work_start = tf_work_start.value.strip()
        if tf_work_end.value and ":" in tf_work_end.value:
            user.work_end = tf_work_end.value.strip()
        from core.database import Storage
        Storage.save_user(user)
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
                gc.content.border = ft.Border.all(
                    2, Colors.PRIMARY if gc.content.content.bgcolor == color else "transparent"
                )
            page.update()
        return ft.GestureDetector(content=c, on_tap=_pick)

    color_pickers = [color_circle(c) for c in AVATAR_COLORS]

    tf_name = ft.TextField(
        label=t("full_name"), value=user.full_name, bgcolor=Colors.BG_INPUT, border_color=Colors.BORDER,
        focused_border_color=Colors.PRIMARY, text_style=ft.TextStyle(color=Colors.TEXT_PRIMARY),
        label_style=ft.TextStyle(color=Colors.TEXT_SECONDARY), border_radius=Radius.MD, cursor_color=Colors.PRIMARY,
    )
    tf_work_start = ft.TextField(
        label=t("work_start"), hint_text="08:00",
        value=getattr(user, "work_start", "08:00"),
        width=150, text_size=Typography.SMALL,
        bgcolor=Colors.BG_INPUT, border_color=Colors.BORDER,
        focused_border_color=Colors.PRIMARY,
        text_style=ft.TextStyle(color=Colors.TEXT_PRIMARY),
        label_style=ft.TextStyle(color=Colors.TEXT_SECONDARY),
        border_radius=Radius.MD, cursor_color=Colors.PRIMARY,
    )
    tf_work_end = ft.TextField(
        label=t("work_end"), hint_text="18:00",
        value=getattr(user, "work_end", "18:00"),
        width=150, text_size=Typography.SMALL,
        bgcolor=Colors.BG_INPUT, border_color=Colors.BORDER,
        focused_border_color=Colors.PRIMARY,
        text_style=ft.TextStyle(color=Colors.TEXT_PRIMARY),
        label_style=ft.TextStyle(color=Colors.TEXT_SECONDARY),
        border_radius=Radius.MD, cursor_color=Colors.PRIMARY,
    )

    tf_old_pwd = ft.TextField(label=t("old_password"), password=True, can_reveal_password=True,
        bgcolor=Colors.BG_INPUT, border_color=Colors.BORDER, focused_border_color=Colors.PRIMARY,
        text_style=ft.TextStyle(color=Colors.TEXT_PRIMARY), label_style=ft.TextStyle(color=Colors.TEXT_SECONDARY),
        border_radius=Radius.MD, cursor_color=Colors.PRIMARY)

    tf_new_pwd = ft.TextField(label=t("new_password"), password=True, can_reveal_password=True,
        bgcolor=Colors.BG_INPUT, border_color=Colors.BORDER, focused_border_color=Colors.PRIMARY,
        text_style=ft.TextStyle(color=Colors.TEXT_PRIMARY), label_style=ft.TextStyle(color=Colors.TEXT_SECONDARY),
        border_radius=Radius.MD, cursor_color=Colors.PRIMARY)

    tf_cfm_pwd = ft.TextField(label=t("confirm_password"), password=True, can_reveal_password=True,
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

    # ── Language selector ──────────────────────────────────────
    _cur_lang = {"v": get_lang()}
    lang_btn_refs = {}

    def _lang_option(code: str, flag: str, label: str) -> ft.Container:
        ref = ft.Ref[ft.Container]()
        lang_btn_refs[code] = ref

        def _select(_):
            old = _cur_lang["v"]
            if old == code:
                return
            _cur_lang["v"] = code
            set_lang(code)
            try:
                from core.services import AIMemoryService
                AIMemoryService.remember(user.id, "system", "app_language", code, 1.0)
            except Exception:
                pass
            # Update button borders
            for c2, r2 in lang_btn_refs.items():
                if r2.current:
                    r2.current.border = ft.Border.all(
                        2, Colors.PRIMARY if c2 == code else Colors.BORDER)
                    r2.current.bgcolor = Colors.PRIMARY_BG if c2 == code else Colors.BG_SURFACE
            page.update()
            # Rebuild settings with new language
            on_navigate("settings")

        is_active = (_cur_lang["v"] == code)
        return ft.Container(
            ref=ref,
            content=ft.Row([
                ft.Text(flag, size=22),
                ft.Column([
                    ft.Text(label, size=Typography.BODY, color=Colors.TEXT_PRIMARY,
                            weight=Typography.SEMIBOLD if is_active else Typography.REGULAR),
                ], spacing=0, tight=True, expand=True),
                ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED if is_active else ft.Icons.RADIO_BUTTON_UNCHECKED,
                        size=18, color=Colors.PRIMARY if is_active else Colors.TEXT_MUTED),
            ], spacing=Spacing.MD, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            padding=ft.padding.symmetric(horizontal=Spacing.MD, vertical=12),
            border_radius=Radius.MD,
            bgcolor=Colors.PRIMARY_BG if is_active else Colors.BG_SURFACE,
            border=ft.Border.all(2, Colors.PRIMARY if is_active else Colors.BORDER),
            on_click=_select, ink=True,
            margin=ft.margin.only(bottom=Spacing.XS),
        )

    lang_section = section_card(t("language"), "🌐",
        ft.Column([
            ft.Text(t("language_hint"), size=Typography.TINY, color=Colors.TEXT_MUTED),
            ft.Container(height=Spacing.SM),
            _lang_option("vi", "🇻🇳", t("language_vi")),
            _lang_option("en", "🇬🇧", t("language_en")),
            _lang_option("zh", "🇨🇳", t("language_zh")),
        ], spacing=0, tight=True)
    )

    # HEADER
    header = ft.Container(
        content=ft.Row([
            ft.IconButton(ft.Icons.ARROW_BACK_IOS_NEW_ROUNDED, on_click=lambda _: on_navigate("profile")),
            ft.Text(t("settings_title"), size=Typography.H2, color=Colors.TEXT_PRIMARY, weight=Typography.BOLD),
        ]),
        padding=ft.Padding.symmetric(horizontal=Spacing.MD, vertical=Spacing.MD),
    )

    body = ft.Column([
        header,
        ft.Container(
            content=ft.Column([
                section_card(t("account_info"), "👤",
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
                        ft.Container(height=Spacing.SM),
                        ft.Row([
                            tf_work_start,
                            ft.Text("—", color=Colors.TEXT_MUTED),
                            tf_work_end,
                        ], spacing=Spacing.SM, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                        ft.Container(height=Spacing.MD),
                        primary_button(t("save_changes"), on_click=save_profile, icon=ft.Icons.SAVE_OUTLINED, height=44),
                    ], spacing=0, tight=True)
                ),
                ft.Container(height=Spacing.SM),
                section_card(t("change_password"), "🔒",
                    ft.Column([
                        tf_old_pwd, ft.Container(height=Spacing.SM), tf_new_pwd, ft.Container(height=Spacing.SM), tf_cfm_pwd, ft.Container(height=Spacing.MD),
                        primary_button(t("change_password"), on_click=change_password, icon=ft.Icons.LOCK_RESET_OUTLINED, outlined=True, height=44),
                    ], spacing=0, tight=True)
                ),
                ft.Container(height=Spacing.SM),
                lang_section,
                ft.Container(height=Spacing.SM),
                ft.Container(
                    content=ft.Row([
                        ft.Icon(ft.Icons.LOGOUT_ROUNDED, color=Colors.TEXT_MUTED, size=20),
                        ft.Text(t("logout"), size=Typography.BODY, color=Colors.TEXT_MUTED, weight=Typography.SEMIBOLD),
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
