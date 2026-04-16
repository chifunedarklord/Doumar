"""
TaskFlow - Profile / Account Screen
"""
import flet as ft
from core.theme import Colors, Typography, Spacing, Radius
from core.services import TaskService
from components.widgets import avatar_circle

def build_profile_screen(page: ft.Page, user, on_navigate, on_logout=None):
    avatar_area = ft.Container(
        content=avatar_circle(user.full_name or user.username,
                               user.avatar_color, 80),
        alignment=ft.Alignment.CENTER,
    )
    profile_name_text = ft.Text(user.full_name or user.username, size=Typography.H2, color=Colors.TEXT_PRIMARY, weight=Typography.BOLD)

    # ── Stats summary ─────────────────────────────────────────
    all_tasks   = TaskService.get_tasks(user.id)
    total       = len(all_tasks)
    done        = sum(1 for t in all_tasks if t.status == "done")
    in_prog     = sum(1 for t in all_tasks if t.status == "in_progress")
    overdue_cnt = sum(1 for t in all_tasks if t.is_overdue)

    def _small_stat(val, lbl, color):
        return ft.Column([
            ft.Text(val, size=Typography.H2, color=color, weight=Typography.EXTRABOLD),
            ft.Text(lbl, size=Typography.TINY, color=Colors.TEXT_MUTED),
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=0, tight=True)

    def _divider_v():
        return ft.Container(width=1, height=40, bgcolor=Colors.BORDER)

    stats_row = ft.Container(
        content=ft.Column([
            ft.Row([
                _small_stat(str(total),        "Tổng CT",    Colors.VIOLET),
                _divider_v(),
                _small_stat(str(done),         "Xong",       Colors.SUCCESS),
                _divider_v(),
                _small_stat(str(in_prog),      "Đang làm",   Colors.CYAN),
                _divider_v(),
                _small_stat(str(overdue_cnt),  "Quá hạn",    Colors.ERROR),
                _divider_v(),
                _small_stat(f"{int(done/total*100) if total else 0}%", "Tỷ lệ", Colors.PRIMARY),
            ], alignment=ft.MainAxisAlignment.SPACE_AROUND, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ft.Container(height=Spacing.SM),
            ft.Container(
                content=ft.Row([
                    ft.Icon(ft.Icons.BAR_CHART_ROUNDED, color=Colors.TEXT_MUTED, size=16),
                    ft.Text("Xem báo cáo chi tiết", size=Typography.TINY, color=Colors.TEXT_MUTED),
                    ft.Icon(ft.Icons.CHEVRON_RIGHT, color=Colors.TEXT_MUTED, size=16),
                ], alignment=ft.MainAxisAlignment.CENTER, spacing=4, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                on_click=lambda _: on_navigate("report"),
                ink=True, border_radius=Radius.SM, padding=ft.Padding.symmetric(vertical=Spacing.XS),
            ),
        ], spacing=0, tight=True),
        padding=ft.Padding.symmetric(vertical=Spacing.MD, horizontal=Spacing.MD),
        border_radius=Radius.LG, bgcolor=Colors.BG_CARD, border=ft.border.all(1, Colors.BORDER),
        shadow=ft.BoxShadow(
            blur_radius=12,
            color="#00000018",
            offset=ft.Offset(0, 3),
        ),
    )

    # ── Achievements ──────────────────────────────────────────
    def _achieve_card(icon, title, desc, unlocked):
        return ft.Container(
            content=ft.Row([
                ft.Container(
                    content=ft.Text(icon, size=24), width=48, height=48, border_radius=24,
                    bgcolor=Colors.PRIMARY_BG if unlocked else Colors.BG_SURFACE, alignment=ft.Alignment.CENTER,
                    border=ft.Border.all(1, Colors.PRIMARY_BORDER if unlocked else "transparent")
                ),
                ft.Column([
                    ft.Text(title, size=Typography.BODY, color=Colors.TEXT_PRIMARY if unlocked else Colors.TEXT_MUTED, weight=Typography.SEMIBOLD),
                    ft.Text(desc, size=Typography.TINY, color=Colors.TEXT_MUTED),
                ], spacing=2, tight=True, expand=True),
                ft.Icon(ft.Icons.CHECK_CIRCLE, color=Colors.SUCCESS if unlocked else "transparent", size=16),
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
            padding=Spacing.MD, border_radius=Radius.MD, bgcolor=Colors.BG_SURFACE,
            border=ft.Border.all(1, Colors.BORDER), opacity=1.0 if unlocked else 0.4,
            shadow=ft.BoxShadow(
                blur_radius=8,
                color="#00000014",
                offset=ft.Offset(0, 2),
            ) if unlocked else None,
        )

    achievements = ft.Column([
        _achieve_card("🏆", "Người khởi đầu", "Hoàn thành 1 công việc đầu tiên", done >= 1),
        _achieve_card("🔥", "Khởi động tốt", "Hoàn thành 5 công việc", done >= 5),
        _achieve_card("🌟", "Chuyên gia", "Thực hiện xong 20 công việc", done >= 20),
        _achieve_card("🚀", "Không cản nổi", "Tích lũy 50 công việc hoàn thiện", done >= 50),
    ], spacing=Spacing.SM)


    # ── Main Body ─────────────────────────────────────────────
    btn_settings = ft.IconButton(
        icon=ft.Icons.SETTINGS_OUTLINED,
        icon_color=Colors.TEXT_PRIMARY,
        on_click=lambda _: on_navigate("settings")
    )

    simple_profile = ft.Container(
        content=ft.Column([
            avatar_area,
            ft.Container(height=Spacing.XS),
            profile_name_text,
            ft.Text(f"{user.email} • {user.username}", size=Typography.SMALL, color=Colors.TEXT_MUTED),
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=0),
        alignment=ft.Alignment.CENTER,
        padding=Spacing.MD
    )

    body = ft.Column([
        ft.Container(
            content=ft.Row([
                ft.Text("Hồ sơ", size=Typography.H2, color=Colors.TEXT_PRIMARY, weight=Typography.BOLD),
                ft.Container(expand=True),
                btn_settings
            ]),
            padding=ft.Padding.symmetric(horizontal=Spacing.MD, vertical=Spacing.MD),
        ),
        ft.Container(
            content=ft.Column([
                simple_profile,
                ft.Container(height=Spacing.MD),
                ft.Text("Báo cáo", size=Typography.H4, color=Colors.TEXT_PRIMARY, weight=Typography.BOLD),
                stats_row,
                ft.Container(height=Spacing.MD),
                ft.Text("Thành tích", size=Typography.H4, color=Colors.TEXT_PRIMARY, weight=Typography.BOLD),
                achievements,
                ft.Container(height=Spacing.XXXL),
                ft.Container(height=Spacing.XXXL),
            ], spacing=Spacing.SM),
            padding=ft.Padding.symmetric(horizontal=Spacing.MD),
        )
    ], spacing=0, tight=True, scroll=ft.ScrollMode.AUTO, expand=True)

    return body
