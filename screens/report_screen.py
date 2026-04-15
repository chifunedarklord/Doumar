"""
TaskFlow - Report & Statistics Screen
Báo cáo thống kê theo tháng với biểu đồ đẹp.
"""
import flet as ft
from datetime import date, datetime
from collections import defaultdict
from core.theme import Colors, Typography, Spacing, Radius, CATEGORY_MAP, PRIORITY_MAP
from core.models import Storage, Task
from components.widgets import gold_divider, stat_card, section_header


def build_report_screen(page: ft.Page, user, on_navigate):
    today = date.today()
    sel_month = {"y": today.year, "m": today.month}

    def get_month_tasks(y, m):
        tasks = Storage.get_tasks(user.id)
        return [t for t in tasks if t.created_at[:7] == f"{y:04d}-{m:02d}"]

    def build_content():
        y, m = sel_month["y"], sel_month["m"]
        tasks = get_month_tasks(y, m)
        all_tasks = Storage.get_tasks(user.id)

        total       = len(tasks)
        done        = sum(1 for t in tasks if t.status == "done")
        in_prog     = sum(1 for t in tasks if t.status == "in_progress")
        cancelled   = sum(1 for t in tasks if t.status == "cancelled")
        overdue_cnt = sum(1 for t in tasks if t.is_overdue)
        completion  = int(done / total * 100) if total else 0

        # By category
        cat_counts = defaultdict(int)
        for t in tasks:
            cat_counts[t.category] += 1

        # By priority
        pri_counts = defaultdict(int)
        for t in tasks:
            pri_counts[t.priority] += 1

        # Daily completion heatmap (done per day)
        done_by_day = defaultdict(int)
        for t in tasks:
            if t.status == "done" and t.completed_at:
                day = t.completed_at[:10]
                done_by_day[day] += 1

        # All-time stats
        all_done = sum(1 for t in all_tasks if t.status == "done")
        all_total = len(all_tasks)

        MONTHS_VI = ["","Tháng 1","Tháng 2","Tháng 3","Tháng 4","Tháng 5","Tháng 6",
                     "Tháng 7","Tháng 8","Tháng 9","Tháng 10","Tháng 11","Tháng 12"]

        # ── Month picker ─────────────────────────────────────
        def prev_month(_):
            if sel_month["m"] == 1:
                sel_month["m"] = 12; sel_month["y"] -= 1
            else:
                sel_month["m"] -= 1
            rebuild()

        def next_month(_):
            if sel_month["m"] == 12:
                sel_month["m"] = 1; sel_month["y"] += 1
            else:
                sel_month["m"] += 1
            rebuild()

        month_picker = ft.Row([
            ft.IconButton(ft.Icons.CHEVRON_LEFT, icon_color=Colors.PRIMARY,
                          on_click=prev_month),
            ft.Text(f"{MONTHS_VI[m]} {y}", size=Typography.H4,
                    color=Colors.TEXT_PRIMARY, weight=Typography.BOLD,
                    expand=True, text_align=ft.TextAlign.CENTER),
            ft.IconButton(ft.Icons.CHEVRON_RIGHT, icon_color=Colors.PRIMARY,
                          on_click=next_month),
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
           vertical_alignment=ft.CrossAxisAlignment.CENTER)

        # ── Summary stats cards ──────────────────────────────
        stats_row = ft.Row([
            stat_card(str(total),   "Tổng CT",     "📋", Colors.VIOLET),
            stat_card(str(done),    "Hoàn thành",  "✅", Colors.SUCCESS),
            stat_card(f"{completion}%", "Tỷ lệ",   "📈", Colors.PRIMARY),
            stat_card(str(overdue_cnt), "Quá hạn", "⚠️", Colors.ERROR),
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, spacing=Spacing.SM)

        # ── Completion gauge ─────────────────────────────────
        gauge_card = ft.Container(
            content=ft.Row([
                ft.Stack([
                    ft.Container(
                        content=ft.ProgressRing(
                            value=completion / 100,
                            width=110, height=110,
                            stroke_width=10,
                            color=Colors.PRIMARY,
                            bgcolor=Colors.BG_SURFACE,
                        ),
                        alignment=ft.Alignment.CENTER,
                    ),
                    ft.Container(
                        content=ft.Column([
                            ft.Text(f"{completion}%", size=Typography.H2,
                                    color=Colors.PRIMARY, weight=Typography.EXTRABOLD),
                            ft.Text("done", size=Typography.TINY, color=Colors.TEXT_MUTED),
                        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                           spacing=0, tight=True),
                        alignment=ft.Alignment.CENTER,
                    ),
                ], width=110, height=110),
                ft.Container(width=Spacing.LG),
                ft.Column([
                    ft.Text("Tỷ lệ hoàn thành", size=Typography.H4,
                            color=Colors.TEXT_PRIMARY, weight=Typography.BOLD),
                    ft.Container(height=Spacing.SM),
                    _legend_item("Hoàn thành", done, total, Colors.SUCCESS),
                    ft.Container(height=4),
                    _legend_item("Đang làm",   in_prog, total, Colors.CYAN),
                    ft.Container(height=4),
                    _legend_item("Đã hủy",     cancelled, total, Colors.ERROR),
                    ft.Container(height=4),
                    _legend_item("Chưa làm",
                                 total - done - in_prog - cancelled, total, Colors.TEXT_MUTED),
                ], expand=True, spacing=0, tight=True),
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
            padding=Spacing.MD,
            border_radius=Radius.LG,
            bgcolor=Colors.BG_CARD,
            border=ft.border.all(1, Colors.BORDER),
        )

        # ── Category bar chart ────────────────────────────────
        def cat_bar_row(cat_key, count) -> ft.Container:
            info  = CATEGORY_MAP.get(cat_key, {"label": cat_key, "icon": "📌", "color": Colors.TEXT_MUTED})
            ratio = count / total if total else 0
            return ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.Text(info["icon"], size=14),
                        ft.Text(info["label"], size=Typography.SMALL,
                                color=Colors.TEXT_PRIMARY, expand=True),
                        ft.Text(str(count), size=Typography.SMALL,
                                color=info["color"], weight=Typography.BOLD),
                    ], spacing=Spacing.SM),
                    ft.Container(height=4),
                    ft.ProgressBar(
                        value=ratio,
                        height=8,
                        border_radius=Radius.FULL,
                        color=Colors.PRIMARY,
                        bgcolor=Colors.BG_SURFACE,
                        expand=True,
                    ),
                ], spacing=0, tight=True),
                margin=ft.Margin.only(bottom=Spacing.SM),
            )

        cat_bars = ft.Column(
            [cat_bar_row(k, v) for k, v in sorted(cat_counts.items(),
                                                    key=lambda x: -x[1])] or
            [ft.Text("Chưa có dữ liệu", size=Typography.SMALL, color=Colors.TEXT_MUTED)],
            spacing=0, tight=True,
        )

        cat_card = ft.Container(
            content=ft.Column([
                section_header("📊 Theo danh mục", f"{len(cat_counts)} danh mục"),
                ft.Container(height=Spacing.MD),
                cat_bars,
            ], spacing=0, tight=True),
            padding=Spacing.MD,
            border_radius=Radius.LG,
            bgcolor=Colors.BG_CARD,
            border=ft.border.all(1, Colors.BORDER),
        )

        # ── Priority distribution ────────────────────────────
        def pri_chip_stat(key, count) -> ft.Container:
            info  = PRIORITY_MAP.get(key, {"label": key, "icon": "●", "color": Colors.TEXT_MUTED})
            ratio = count / total if total else 0
            pct   = int(ratio * 100)
            return ft.Container(
                content=ft.Column([
                    ft.Container(
                        content=ft.Text(info["icon"], size=24),
                        width=52, height=52,
                        border_radius=Radius.MD,
                        bgcolor="#505050",
                        border=ft.Border.all(1, Colors.BORDER),
                        alignment=ft.Alignment.CENTER,
                    ),
                    ft.Text(f"{pct}%", size=Typography.H3, color=Colors.PRIMARY,
                            weight=Typography.BOLD, text_align=ft.TextAlign.CENTER),
                    ft.Text(info["label"], size=Typography.TINY,
                            color=Colors.TEXT_MUTED, text_align=ft.TextAlign.CENTER),
                    ft.Text(str(count), size=Typography.SMALL, color=Colors.TEXT_PRIMARY,
                            text_align=ft.TextAlign.CENTER),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                   spacing=4, tight=True),
                padding=Spacing.SM,
                expand=True,
            )

        pri_card = ft.Container(
            content=ft.Column([
                section_header("🎯 Mức ưu tiên", ""),
                ft.Container(height=Spacing.MD),
                ft.Row([pri_chip_stat(k, pri_counts.get(k, 0))
                        for k in ["high", "medium", "low"]],
                       alignment=ft.MainAxisAlignment.SPACE_AROUND),
            ], spacing=0, tight=True),
            padding=Spacing.MD,
            border_radius=Radius.LG,
            bgcolor=Colors.BG_CARD,
            border=ft.border.all(1, Colors.BORDER),
        )

        # ── All-time summary ──────────────────────────────────
        alltime_card = ft.Container(
            content=ft.Row([
                ft.Column([
                    ft.Text("✦ Tổng toàn thời gian", size=Typography.H4,
                            color=Colors.PRIMARY, weight=Typography.SEMIBOLD),
                    ft.Container(height=Spacing.SM),
                    ft.Row([
                        ft.Column([
                            ft.Text(str(all_total), size=Typography.DISPLAY,
                                    color=Colors.TEXT_PRIMARY, weight=Typography.EXTRABOLD),
                            ft.Text("Tổng công việc", size=Typography.SMALL,
                                    color=Colors.TEXT_MUTED),
                        ], spacing=0, tight=True),
                        ft.Container(width=Spacing.XL),
                        ft.Column([
                            ft.Text(str(all_done), size=Typography.DISPLAY,
                                    color=Colors.SUCCESS, weight=Typography.EXTRABOLD),
                            ft.Text("Đã hoàn thành", size=Typography.SMALL,
                                    color=Colors.TEXT_MUTED),
                        ], spacing=0, tight=True),
                    ]),
                ], expand=True, spacing=0, tight=True),
                ft.Container(
                    content=ft.Stack([
                        ft.Container(
                            content=ft.ProgressRing(
                                value=all_done / all_total if all_total else 0,
                                width=80, height=80,
                                stroke_width=7,
                                color=Colors.ACCENT_WARM,
                                bgcolor=Colors.BG_SURFACE,
                            ),
                            alignment=ft.Alignment.CENTER,
                        ),
                        ft.Container(
                            content=ft.Text(
                                f"{int(all_done/all_total*100) if all_total else 0}%",
                                size=Typography.H4, color=Colors.ACCENT_WARM,
                                weight=Typography.BOLD,
                            ),
                            alignment=ft.Alignment.CENTER,
                        ),
                    ]),
                    width=80, height=80,
                ),
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
               vertical_alignment=ft.CrossAxisAlignment.CENTER),
            padding=Spacing.MD,
            border_radius=Radius.LG,
            gradient=ft.LinearGradient(
                colors=[Colors.BG_CARD, Colors.BG_SURFACE],
                begin=ft.Alignment.TOP_LEFT,
                end=ft.Alignment.BOTTOM_RIGHT,
            ),
            border=ft.Border.all(1, Colors.BORDER),
            shadow=ft.BoxShadow(blur_radius=16, color="#00000066",
                                offset=ft.Offset(0, 4)),
        )

        # ── Assemble ─────────────────────────────────────────
        return ft.Column([
            ft.Container(
                content=ft.Row([
                    ft.Text("Báo cáo", size=Typography.H2, color=Colors.TEXT_PRIMARY,
                            weight=Typography.BOLD),
                ]),
                padding=ft.padding.symmetric(horizontal=Spacing.MD, vertical=Spacing.MD),
            ),
            ft.Container(
                content=ft.Column([
                    month_picker,
                    ft.Container(height=Spacing.MD),
                    stats_row,
                    ft.Container(height=Spacing.MD),
                    gauge_card,
                    ft.Container(height=Spacing.MD),
                    cat_card,
                    ft.Container(height=Spacing.MD),
                    pri_card,
                    ft.Container(height=Spacing.MD),
                    alltime_card,
                    ft.Container(height=Spacing.XXXL),
                ], spacing=0, tight=True),
                padding=ft.padding.symmetric(horizontal=Spacing.MD),
            ),
        ], spacing=0, tight=True, scroll=ft.ScrollMode.AUTO, expand=True)

    container_ref = ft.Ref[ft.Column]()
    main_col = ft.Column([], ref=container_ref, expand=True)

    def rebuild():
        main_col.controls = [build_content()]
        page.update()

    rebuild()
    return main_col


def _legend_item(label: str, count: int, total: int, color: str) -> ft.Row:
    pct = int(count / total * 100) if total else 0
    return ft.Row([
        ft.Container(width=10, height=10, border_radius=Radius.FULL, bgcolor=color),
        ft.Text(label, size=Typography.TINY, color=Colors.TEXT_SECONDARY, expand=True),
        ft.Text(f"{count}  ({pct}%)", size=Typography.TINY, color=color,
                weight=Typography.SEMIBOLD),
    ], spacing=Spacing.SM, vertical_alignment=ft.CrossAxisAlignment.CENTER)
