"""
TaskFlow - Reusable UI Components
"""
import flet as ft
from core.theme import Colors, Typography, Spacing, Radius


def glow_text(text: str, size: int = Typography.H3, color: str = Colors.PRIMARY,
              weight: str = Typography.BOLD) -> ft.Text:
    return ft.Text(text, size=size, color=color, weight=weight,
                   style=ft.TextStyle(shadow=ft.BoxShadow(
                       blur_radius=12, color=color + "66",
                       offset=ft.Offset(0, 0), spread_radius=1
                   )))


def gold_divider(opacity: float = 0.3) -> ft.Container:
    return ft.Container(
        height=1,
        gradient=ft.LinearGradient(
            colors=["#00000000", Colors.PRIMARY, "#00000000"],
            begin=ft.Alignment.CENTER_LEFT,
            end=ft.Alignment.CENTER_RIGHT,
        ),
        opacity=opacity,
        margin=ft.Margin.symmetric(vertical=Spacing.SM),
    )


def glass_card(content, padding: int = Spacing.MD, radius: int = Radius.MD,
               border_color: str = Colors.BORDER, glow: bool = False,
               on_click=None, expand=False) -> ft.Container:
    shadow_color = "#00000066" if glow else "#00000044"
    return ft.Container(
        content=content,
        padding=padding,
        border_radius=radius,
        bgcolor=Colors.BG_CARD,
        border=ft.Border.all(1, border_color),
        shadow=ft.BoxShadow(blur_radius=20, color=shadow_color, offset=ft.Offset(0, 4)),
        on_click=on_click,
        animate=ft.Animation(200, ft.AnimationCurve.EASE_OUT),
        expand=expand,
    )


def gold_button(text: str, on_click=None, icon: str = None,
                width: int = None, height: int = 48,
                outlined: bool = False) -> ft.Container:
    content_row = []
    if icon:
        content_row.append(ft.Icon(icon, size=18,
                                   color=Colors.BG_DARKEST if not outlined else Colors.PRIMARY))
    content_row.append(ft.Text(text, size=Typography.BODY, weight=Typography.SEMIBOLD,
                                color=Colors.BG_DARKEST if not outlined else Colors.PRIMARY))

    return ft.Container(
        content=ft.Row(content_row, alignment=ft.MainAxisAlignment.CENTER,
                       spacing=Spacing.SM, tight=True),
        height=height,
        width=width,
        border_radius=Radius.MD,
        gradient=None if outlined else ft.LinearGradient(
            colors=[Colors.PRIMARY_LIGHT, Colors.PRIMARY],
            begin=ft.Alignment.CENTER_LEFT,
            end=ft.Alignment.CENTER_RIGHT,
        ),
        border=ft.Border.all(1.5, Colors.PRIMARY) if outlined else None,
        on_click=on_click,
        animate=ft.Animation(150, ft.AnimationCurve.EASE_OUT),
        ink=True,
    )


def text_input(label: str, hint: str = "", password: bool = False,
               on_change=None, on_submit=None, value: str = "",
               prefix_icon: str = None) -> ft.TextField:
    return ft.TextField(
        label=label,
        hint_text=hint,
        value=value,
        password=password,
        can_reveal_password=password,
        on_change=on_change,
        on_submit=on_submit,
        bgcolor=Colors.BG_INPUT,
        border_color=Colors.BORDER,
        focused_border_color=Colors.PRIMARY,
        label_style=ft.TextStyle(color=Colors.TEXT_SECONDARY, size=Typography.SMALL),
        text_style=ft.TextStyle(color=Colors.TEXT_PRIMARY, size=Typography.BODY),
        hint_style=ft.TextStyle(color=Colors.TEXT_MUTED, size=Typography.SMALL),
        border_radius=Radius.MD,
        prefix_icon=prefix_icon,
        cursor_color=Colors.PRIMARY,
    )


def priority_badge(priority: str) -> ft.Container:
    from core.theme import PRIORITY_MAP
    info = PRIORITY_MAP.get(priority, PRIORITY_MAP["medium"])
    return ft.Container(
        content=ft.Row([
            ft.Text(info["icon"], size=10),
            ft.Text(info["label"], size=Typography.TINY, color=Colors.TEXT_SECONDARY,
                    weight=Typography.SEMIBOLD),
        ], spacing=3, tight=True),
        padding=ft.Padding.symmetric(horizontal=8, vertical=3),
        border_radius=Radius.FULL,
        border=ft.Border.all(1, Colors.BORDER),
        bgcolor=Colors.BG_SURFACE,
    )


def category_badge(category: str) -> ft.Container:
    from core.theme import CATEGORY_MAP
    info = CATEGORY_MAP.get(category, CATEGORY_MAP["personal"])
    return ft.Container(
        content=ft.Row([
            ft.Text(info["icon"], size=10),
            ft.Text(info["label"], size=Typography.TINY, color=Colors.TEXT_SECONDARY,
                    weight=Typography.MEDIUM),
        ], spacing=3, tight=True),
        padding=ft.Padding.symmetric(horizontal=8, vertical=3),
        border_radius=Radius.FULL,
        border=ft.Border.all(1, Colors.BORDER),
        bgcolor=Colors.BG_SURFACE,
    )


def status_chip(status: str) -> ft.Container:
    from core.theme import STATUS_MAP
    info = STATUS_MAP.get(status, STATUS_MAP["todo"])
    return ft.Container(
        content=ft.Row([
            ft.Text(info["icon"], size=10),
            ft.Text(info["label"], size=Typography.TINY, color=Colors.TEXT_SECONDARY,
                    weight=Typography.MEDIUM),
        ], spacing=3, tight=True),
        padding=ft.Padding.symmetric(horizontal=8, vertical=3),
        border_radius=Radius.FULL,
        bgcolor=Colors.BG_SURFACE,
    )


def avatar_circle(name: str, color: str = Colors.PRIMARY, size: int = 40) -> ft.Container:
    initials = "".join(p[0].upper() for p in name.split()[:2]) if name else "?"
    return ft.Container(
        content=ft.Text(initials, size=size // 2.8, color=Colors.BG_DARKEST,
                        weight=Typography.BOLD),
        width=size, height=size,
        border_radius=Radius.FULL,
        gradient=ft.LinearGradient(
            colors=[color, Colors.PRIMARY_DARK],
            begin=ft.Alignment.TOP_LEFT,
            end=ft.Alignment.BOTTOM_RIGHT,
        ),
        alignment=ft.Alignment.CENTER,
    )


def loading_ring() -> ft.Container:
    return ft.Container(
        content=ft.ProgressRing(color=Colors.PRIMARY, width=32, height=32, stroke_width=3),
        alignment=ft.Alignment.CENTER,
        expand=True,
    )


def snack(page: ft.Page, message: str, success: bool = True):
    color = Colors.SUCCESS if success else Colors.ERROR
    icon = "✅" if success else "❌"
    page.snack_bar = ft.SnackBar(
        content=ft.Row([
            ft.Text(icon, size=16),
            ft.Text(message, color=Colors.TEXT_PRIMARY, size=Typography.BODY),
        ], spacing=Spacing.SM),
        bgcolor=Colors.BG_CARD,
        behavior=ft.SnackBarBehavior.FLOATING,
        shape=ft.RoundedRectangleBorder(radius=Radius.MD),
        duration=3000,
    )
    page.snack_bar.open = True
    page.update()


def section_header(title: str, subtitle: str = "", action_text: str = "",
                   on_action=None) -> ft.Row:
    items = [
        ft.Column([
            ft.Text(title, size=Typography.H3, color=Colors.TEXT_PRIMARY,
                    weight=Typography.BOLD),
            ft.Text(subtitle, size=Typography.SMALL, color=Colors.TEXT_MUTED) if subtitle else ft.Container(),
        ], spacing=2, tight=True),
        ft.Row([], expand=True),
    ]
    if action_text and on_action:
        items.append(ft.TextButton(
            action_text,
            on_click=on_action,
            style=ft.ButtonStyle(color=Colors.PRIMARY),
        ))
    return ft.Row(items, alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER)


def stat_card(value: str, label: str, icon: str, color: str,
              width: int = None) -> ft.Container:
    return ft.Container(
        content=ft.Column([
            ft.Row([
                ft.Container(
                    content=ft.Text(icon, size=14),
                    width=28, height=28,
                    border_radius=Radius.MD,
                    bgcolor="#505050",
                    alignment=ft.Alignment.CENTER,
                ),
                ft.Column([
                    ft.Text(value, size=Typography.BODY, color=Colors.PRIMARY, weight=Typography.BOLD),
                    ft.Text(label, size=Typography.TINY, color=Colors.TEXT_MUTED),
                ], spacing=0, tight=True),
            ], spacing=Spacing.XS),
        ], spacing=0, tight=True),
        padding=Spacing.XS,
        border_radius=Radius.MD,
        bgcolor=Colors.BG_CARD,
        border=ft.Border.all(1, color + "33"),
        width=width,
    )
