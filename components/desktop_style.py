"""Monochrome styling for desktop surfaces, including legacy Flet controls."""
from dataclasses import fields, is_dataclass
import flet as ft

INK = "#111111"
WHITE = "#FFFFFF"
PAPER = "#FFFFFF"
LINE = "#E5E5E5"
MUTED = "#666666"
HOVER = "#F5F5F5"


def desktop_theme():
    """Specify the complete scheme so Material does not introduce accent hues."""
    scheme = ft.ColorScheme(
        primary=INK, on_primary=WHITE, primary_container=HOVER, on_primary_container=INK,
        secondary=INK, on_secondary=WHITE, secondary_container=HOVER, on_secondary_container=INK,
        tertiary=INK, on_tertiary=WHITE, tertiary_container=HOVER, on_tertiary_container=INK,
        error=INK, on_error=WHITE, error_container=HOVER, on_error_container=INK,
        surface=WHITE, on_surface=INK, on_surface_variant=MUTED,
        surface_bright=WHITE, surface_dim=HOVER, surface_container_lowest=WHITE,
        surface_container_low=WHITE, surface_container=WHITE,
        surface_container_high=HOVER, surface_container_highest="#EEEEEE",
        surface_tint=WHITE, outline="#A0A0A0", outline_variant=LINE,
        inverse_surface=INK, on_inverse_surface=WHITE, inverse_primary=WHITE,
        shadow="#000000", scrim="#000000",
    )
    button = ft.ButtonStyle(
        color=INK, icon_color=INK, bgcolor={ft.ControlState.HOVERED: HOVER, ft.ControlState.DEFAULT: WHITE},
        elevation=0, shape=ft.RoundedRectangleBorder(radius=6),
        padding=ft.Padding.symmetric(horizontal=14, vertical=10),
        text_style=ft.TextStyle(size=16, weight=ft.FontWeight.W_500),
        overlay_color="#0D000000",
    )
    return ft.Theme(
        use_material3=True, color_scheme=scheme, scaffold_bgcolor=PAPER, canvas_color=PAPER,
        text_theme=ft.TextTheme(body_large=ft.TextStyle(size=17, color=INK), body_medium=ft.TextStyle(size=17, color=INK), body_small=ft.TextStyle(size=14, color=MUTED)),
        icon_theme=ft.IconTheme(color=INK, size=18),
        text_button_theme=ft.TextButtonTheme(style=button),
        outlined_button_theme=ft.OutlinedButtonTheme(style=button),
        filled_button_theme=ft.FilledButtonTheme(style=button),
        icon_button_theme=ft.IconButtonTheme(style=ft.ButtonStyle(color=INK, icon_color=INK, overlay_color="#0D000000")),
        checkbox_theme=ft.CheckboxTheme(check_color="#FFFFFF", fill_color={ft.ControlState.SELECTED: INK, ft.ControlState.DEFAULT: WHITE},
                                       border_side=ft.BorderSide(1, "#999999")),
        divider_color=LINE, hover_color=HOVER, focus_color="#18000000",
    )


def monochrome(control):
    """Adapt older control compositions without changing callbacks or content.

    Called when a surface or AI reply is constructed. Images and intentional ink
    surfaces retain their content; native selection state stays under Material.
    """
    seen = set()

    def walk(node, dark=False):
        if not isinstance(node, ft.Control) or id(node) in seen:
            return
        seen.add(id(node))
        if isinstance(node, ft.Container):
            if node.gradient is not None:
                node.gradient = None
                node.bgcolor = HOVER
            if node.bgcolor and node.bgcolor not in ("transparent", "#00000000", INK, "#111111", "#000000"):
                node.bgcolor = WHITE
            if node.bgcolor and node.bgcolor not in ("transparent", "#00000000"):
                dark = node.bgcolor in (INK, "#111111", "#000000")
            if isinstance(node.border, ft.Border):
                node.border = ft.Border(**{
                    edge: ft.BorderSide(getattr(node.border, edge).width, LINE)
                    for edge in ("top", "right", "bottom", "left")
                    if getattr(node.border, edge) is not None
                })
            node.shadow = None
        if isinstance(node, (ft.Text, ft.Icon)):
            node.color = "#FFFFFF" if dark else INK
        if isinstance(node, ft.Text):
            node.size = max(node.size or 17, 16)
        if isinstance(node, ft.Checkbox):
            node.check_color = "#FFFFFF"
            node.fill_color = {ft.ControlState.SELECTED: INK, ft.ControlState.DEFAULT: WHITE}
            node.border_side = ft.BorderSide(1.2, MUTED)
        if isinstance(node, ft.IconButton):
            node.icon_color = INK
        if isinstance(node, ft.TextField):
            node.bgcolor = WHITE
            node.cursor_color = INK
            node.text_style = ft.TextStyle(color=INK, size=17)
            node.hint_style = ft.TextStyle(color=MUTED, size=16)
            node.label_style = ft.TextStyle(color=MUTED, size=16)
            node.border_radius = 6
        if isinstance(node, ft.ProgressBar):
            node.color, node.bgcolor = INK, LINE
        if isinstance(node, ft.ProgressRing):
            node.color, node.bgcolor = INK, LINE
        if is_dataclass(node):
            for field in fields(node):
                if field.name.startswith("_") or field.name in ("data", "parent"):
                    continue
                value = getattr(node, field.name, None)
                if isinstance(value, ft.Control):
                    walk(value, dark)
                elif isinstance(value, (list, tuple)):
                    for child in value:
                        walk(child, dark)
    walk(control)
    return control


def readable(control):
    """Raise legacy small type without recoloring provider logos or user images."""
    seen = set()
    def walk(node):
        if not isinstance(node, ft.Control) or id(node) in seen:
            return
        seen.add(id(node))
        if isinstance(node, ft.Text):
            node.size = max(node.size or 17, 16)
        if isinstance(node, ft.TextField):
            node.text_size = max(node.text_size or 17, 17)
        if isinstance(node, ft.Dropdown):
            node.text_size = 17
        if isinstance(node, ft.Checkbox):
            node.check_color = '#FFFFFF'
            node.fill_color = {ft.ControlState.SELECTED: INK, ft.ControlState.DEFAULT: WHITE}
        if is_dataclass(node):
            for field in fields(node):
                if field.name.startswith('_') or field.name in ('data', 'parent'):
                    continue
                value = getattr(node, field.name, None)
                if isinstance(value, ft.Control):
                    walk(value)
                elif isinstance(value, (list, tuple)):
                    for item in value:
                        walk(item)
    walk(control)
    return control
