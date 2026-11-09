"""
TaskFlow - Cross-Version & Cross-Platform Compatibility Layer.
Ensures seamless compatibility across Flet versions on Windows, Linux, and macOS.
"""
import sys
import flet as ft

# ── Flet API backwards compatibility (Flet 0.x / 1.x) ────────────
if not hasattr(ft.padding, "symmetric"):
    ft.padding = ft.Padding

if not hasattr(ft.margin, "symmetric"):
    ft.margin = ft.Margin

if hasattr(ft, "border_radius") and not hasattr(ft.border_radius, "all"):
    ft.border_radius = ft.BorderRadius

if hasattr(ft, "border") and not hasattr(ft.border, "all"):
    ft.border = ft.Border

if hasattr(ft, "colors"):
    ft.colors = ft.Colors

if hasattr(ft, "icons"):
    ft.icons = ft.Icons

if hasattr(ft, "alignment") and not hasattr(ft.alignment, "center"):
    class _AlignmentCompat(ft.Alignment):
        center = ft.Alignment.CENTER
        top_left = ft.Alignment.TOP_LEFT
        top_right = ft.Alignment.TOP_RIGHT
        bottom_left = ft.Alignment.BOTTOM_LEFT
        bottom_right = ft.Alignment.BOTTOM_RIGHT
        center_left = ft.Alignment.CENTER_LEFT
        center_right = ft.Alignment.CENTER_RIGHT
        top_center = ft.Alignment.TOP_CENTER
        bottom_center = ft.Alignment.BOTTOM_CENTER
    ft.alignment = _AlignmentCompat
