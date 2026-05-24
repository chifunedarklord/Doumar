"""
TaskFlow - Analytics & AI Insights Screen
Dashboard phân tích thông minh: productivity, burnout, behavior patterns, AI recommendations.
"""
import flet as ft
from datetime import date, datetime, timedelta
from collections import defaultdict
from core.theme import Colors, Typography, Spacing, Radius, CATEGORY_MAP, PRIORITY_MAP
from core.services import TaskService, BehaviorService, AnalyticsService
from components.widgets import primary_divider, stat_card, section_header


def build_report_screen(page: ft.Page, user, on_navigate):
    today = date.today()
    sel_month = {"y": today.year, "m": today.month}

    MONTHS_VI = ["","Tháng 1","Tháng 2","Tháng 3","Tháng 4","Tháng 5","Tháng 6",
                 "Tháng 7","Tháng 8","Tháng 9","Tháng 10","Tháng 11","Tháng 12"]

    def build_content():
        y, m = sel_month["y"], sel_month["m"]
        all_tasks = TaskService.get_tasks(user.id)
        tasks = [t for t in all_tasks if t.created_at[:7] == f"{y:04d}-{m:02d}"]

        # ── Load AI analytics ──────────────────────────────
        try:
            report = AnalyticsService.get_full_report(user.id)
        except Exception:
            report = {
                "weekly_score": 0, "burnout": {"level":"low","label":"Thấp","color":Colors.SUCCESS,"score":0,"reasons":[],"suggestions":[]},
                "peak_hours": [9,10,11], "daily_productivity": [],
                "suggestions": [], "total_focus_minutes": 0,
                "total_tasks": len(all_tasks),
                "done_tasks": sum(1 for t in all_tasks if t.status=="done"),
                "overdue_tasks": sum(1 for t in all_tasks if t.is_overdue),
                "completion_rate": 0,
            }

        burnout   = report["burnout"]
        peak_hrs  = report.get("peak_hours", [9,10,11])
        daily_prod = report.get("daily_productivity", [])
        # Use recommendations (list of dicts) not suggestions (list of strings)
        suggestions = report.get("recommendations", [])
        focus_min = report.get("total_focus_minutes", 0)
        weekly_score = report.get("weekly_score", 0)

        # ── Month stats ────────────────────────────────────
        total     = len(tasks)
        done      = sum(1 for t in tasks if t.status == "done")
        in_prog   = sum(1 for t in tasks if t.status == "in_progress")
        cancelled = sum(1 for t in tasks if t.status == "cancelled")
        overdue   = sum(1 for t in tasks if t.is_overdue)
        completion = int(done / total * 100) if total else 0

        # Category & priority counts
        cat_counts = defaultdict(int)
        pri_counts = defaultdict(int)
        for t in tasks:
            cat_counts[t.category] += 1
            pri_counts[t.priority] += 1

        # All-time
        all_done  = sum(1 for t in all_tasks if t.status == "done")
        all_total = len(all_tasks)

        # ── Month picker ───────────────────────────────────
        def prev_month(_):
            if sel_month["m"] == 1: sel_month["m"] = 12; sel_month["y"] -= 1
            else: sel_month["m"] -= 1
            rebuild()

        def next_month(_):
            if sel_month["m"] == 12: sel_month["m"] = 1; sel_month["y"] += 1
            else: sel_month["m"] += 1
            rebuild()

        month_picker = ft.Row([
            ft.IconButton(ft.Icons.CHEVRON_LEFT, icon_color=Colors.PRIMARY, on_click=prev_month),
            ft.Text(f"{MONTHS_VI[m]} {y}", size=Typography.H4, color=Colors.TEXT_PRIMARY,
                    weight=Typography.BOLD, expand=True, text_align=ft.TextAlign.CENTER),
            ft.IconButton(ft.Icons.CHEVRON_RIGHT, icon_color=Colors.PRIMARY, on_click=next_month),
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER)

        # ── Summary stats ──────────────────────────────────
        stats_row = ft.Row([
            stat_card(str(total), "Tổng CT", "📋", Colors.VIOLET),
            stat_card(str(done), "Hoàn thành", "✅", Colors.SUCCESS),
            stat_card(f"{completion}%", "Tỷ lệ", "📈", Colors.PRIMARY),
            stat_card(str(overdue), "Quá hạn", "⚠️", Colors.ERROR),
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, spacing=Spacing.SM)

        # ── Productivity Score Card ────────────────────────
        score_color = (Colors.SUCCESS if weekly_score >= 70 else
                       Colors.WARNING if weekly_score >= 40 else Colors.ERROR)
        prod_card = ft.Container(
            content=ft.Row([
                ft.Stack([
                    ft.Container(
                        content=ft.ProgressRing(value=weekly_score/100, width=90, height=90,
                                               stroke_width=8, color=score_color, bgcolor=Colors.BG_SURFACE),
                        alignment=ft.Alignment.CENTER,
                    ),
                    ft.Container(
                        content=ft.Column([
                            ft.Text(f"{weekly_score:.0f}", size=Typography.H2, color=score_color, weight=Typography.EXTRABOLD),
                            ft.Text("score", size=Typography.TINY, color=Colors.TEXT_MUTED),
                        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=0, tight=True),
                        alignment=ft.Alignment.CENTER,
                    ),
                ], width=90, height=90),
                ft.Container(width=Spacing.LG),
                ft.Column([
                    ft.Text("Productivity Score", size=Typography.H4, color=Colors.TEXT_PRIMARY, weight=Typography.BOLD),
                    ft.Text("Tuần này", size=Typography.SMALL, color=Colors.TEXT_MUTED),
                    ft.Container(height=Spacing.SM),
                    _legend_item("Hoàn thành", done, total, Colors.SUCCESS),
                    ft.Container(height=4),
                    _legend_item("Đang làm", in_prog, total, Colors.ACCENT_CYAN),
                    ft.Container(height=4),
                    _legend_item("Đã hủy", cancelled, total, Colors.ERROR),
                ], expand=True, spacing=0, tight=True),
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
            padding=Spacing.MD, border_radius=Radius.LG, bgcolor=Colors.BG_CARD,
            border=ft.Border.all(1, Colors.BORDER),
            shadow=ft.BoxShadow(blur_radius=12, color="#00000018", offset=ft.Offset(0, 3)),
        )

        # ── Burnout Risk Card ──────────────────────────────
        b_color = burnout["color"]
        b_score = burnout.get("score", 0)
        burnout_card = ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Text("🔥", size=20),
                    ft.Text("Burnout Risk", size=Typography.H4, color=Colors.TEXT_PRIMARY, weight=Typography.BOLD),
                    ft.Row([], expand=True),
                    ft.Container(
                        content=ft.Text(burnout["label"], size=Typography.SMALL, color="white", weight=Typography.BOLD),
                        padding=ft.Padding.symmetric(horizontal=10, vertical=4),
                        border_radius=Radius.FULL, bgcolor=b_color,
                    ),
                ], spacing=Spacing.SM, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ft.Container(height=Spacing.SM),
                ft.ProgressBar(value=b_score/100, height=8, border_radius=Radius.FULL,
                               color=b_color, bgcolor=Colors.BG_SURFACE),
                ft.Container(height=Spacing.SM),
                *(
                    [ft.Text(f"• {r}", size=Typography.SMALL, color=Colors.TEXT_SECONDARY)
                     for r in burnout.get("reasons", [])[:3]]
                    if burnout.get("reasons") else
                    [ft.Text("✅ Bạn đang làm việc rất tốt!", size=Typography.SMALL, color=Colors.SUCCESS)]
                ),
            ], spacing=4, tight=True),
            padding=Spacing.MD, border_radius=Radius.LG, bgcolor=Colors.BG_CARD,
            border=ft.Border.all(1, b_color + "40"),
            shadow=ft.BoxShadow(blur_radius=12, color="#00000018", offset=ft.Offset(0, 3)),
        )

        # ── Peak Hours Card ────────────────────────────────
        peak_items = []
        for h in range(24):
            is_peak = h in peak_hrs
            peak_items.append(ft.Container(
                width=10, height=24 if is_peak else 10,
                border_radius=2,
                bgcolor=Colors.PRIMARY if is_peak else Colors.BORDER,
                tooltip=f"{h:02d}:00",
            ))

        peak_card = ft.Container(
            content=ft.Column([
                section_header("⚡ Giờ vàng làm việc",
                               ", ".join(f"{h:02d}h" for h in peak_hrs) if peak_hrs else "Chưa có dữ liệu"),
                ft.Container(height=Spacing.SM),
                ft.Container(
                    content=ft.Row(
                        [ft.Column([
                            ft.Container(width=12, height=max(4, int(24 * (1 if h in peak_hrs else 0.3))),
                                        border_radius=2,
                                        bgcolor=Colors.PRIMARY if h in peak_hrs else Colors.BORDER),
                            ft.Text(str(h) if h % 6 == 0 else "", size=7, color=Colors.TEXT_MUTED),
                         ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2, tight=True)
                         for h in range(24)],
                        spacing=2, alignment=ft.MainAxisAlignment.CENTER,
                        vertical_alignment=ft.CrossAxisAlignment.END,
                    ),
                    height=50,
                ),
                ft.Container(height=Spacing.XS),
                ft.Text(f"Giờ tốt nhất để làm task khó: {', '.join(f'{h:02d}:00' for h in peak_hrs)}" if peak_hrs else "Hãy dùng app nhiều hơn để AI học thói quen của bạn",
                        size=Typography.TINY, color=Colors.TEXT_MUTED),
            ], spacing=0, tight=True),
            padding=Spacing.MD, border_radius=Radius.LG, bgcolor=Colors.BG_CARD,
            border=ft.Border.all(1, Colors.BORDER),
            shadow=ft.BoxShadow(blur_radius=12, color="#00000018", offset=ft.Offset(0, 3)),
        )

        # ── Daily Activity (7 days) ────────────────────────
        daily_card = ft.Container(
            content=ft.Column([
                section_header("📅 Hoạt động 7 ngày gần đây", f"Focus: {focus_min//60}h{focus_min%60}p"),
                ft.Container(height=Spacing.SM),
                ft.Row(
                    [_day_bar(dp) for dp in daily_prod] if daily_prod else
                    [ft.Text("Chưa có dữ liệu", size=Typography.SMALL, color=Colors.TEXT_MUTED)],
                    spacing=4, alignment=ft.MainAxisAlignment.CENTER,
                    vertical_alignment=ft.CrossAxisAlignment.END,
                ),
            ], spacing=0, tight=True),
            padding=Spacing.MD, border_radius=Radius.LG, bgcolor=Colors.BG_CARD,
            border=ft.Border.all(1, Colors.BORDER),
            shadow=ft.BoxShadow(blur_radius=12, color="#00000018", offset=ft.Offset(0, 3)),
        )

        # ── AI Recommendations ─────────────────────────────
        def sug_item(s: dict) -> ft.Container:
            pri_color = Colors.ERROR if s.get("priority") == "high" else Colors.WARNING if s.get("priority") == "medium" else Colors.TEXT_MUTED
            return ft.Container(
                content=ft.Row([
                    ft.Text(s.get("icon", "💡"), size=20),
                    ft.Column([
                        ft.Text(s.get("title", ""), size=Typography.SMALL,
                                color=Colors.TEXT_PRIMARY, weight=Typography.SEMIBOLD),
                        ft.Text(s.get("message", ""), size=Typography.TINY, color=Colors.TEXT_MUTED),
                    ], spacing=1, tight=True, expand=True),
                    ft.Container(width=6, height=6, border_radius=3, bgcolor=pri_color),
                ], spacing=Spacing.SM, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                padding=ft.Padding.symmetric(vertical=Spacing.SM, horizontal=Spacing.MD),
                border_radius=Radius.MD, bgcolor=Colors.BG_CARD,
                border=ft.Border.all(1, Colors.BORDER),
                margin=ft.Margin.only(bottom=Spacing.XS),
            )

        rec_section = ft.Column([
            section_header("🤖 AI Gợi ý", f"{len(suggestions)} gợi ý thực tế"),
            ft.Container(height=Spacing.SM),
            ft.Column(
                [sug_item(s) for s in suggestions if isinstance(s, dict)] if suggestions else
                [ft.Text("✅ Không có gợi ý đặc biệt!", size=Typography.SMALL, color=Colors.SUCCESS)],
                spacing=0, tight=True,
            ),
        ], spacing=0, tight=True)

        # ── Category bars ──────────────────────────────────
        cat_bars = ft.Column(
            [_cat_bar(k, v, total) for k, v in sorted(cat_counts.items(), key=lambda x: -x[1])]
            or [ft.Text("Chưa có dữ liệu", size=Typography.SMALL, color=Colors.TEXT_MUTED)],
            spacing=0, tight=True,
        )
        cat_card = ft.Container(
            content=ft.Column([
                section_header("📊 Theo danh mục", f"{len(cat_counts)} danh mục"),
                ft.Container(height=Spacing.MD), cat_bars,
            ], spacing=0, tight=True),
            padding=Spacing.MD, border_radius=Radius.LG, bgcolor=Colors.BG_CARD,
            border=ft.Border.all(1, Colors.BORDER),
            shadow=ft.BoxShadow(blur_radius=12, color="#00000018", offset=ft.Offset(0, 3)),
        )

        # ── All-time summary ───────────────────────────────
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
                            ft.Text("Tổng công việc", size=Typography.SMALL, color=Colors.TEXT_MUTED),
                        ], spacing=0, tight=True),
                        ft.Container(width=Spacing.XL),
                        ft.Column([
                            ft.Text(str(all_done), size=Typography.DISPLAY,
                                    color=Colors.SUCCESS, weight=Typography.EXTRABOLD),
                            ft.Text("Đã hoàn thành", size=Typography.SMALL, color=Colors.TEXT_MUTED),
                        ], spacing=0, tight=True),
                    ]),
                ], expand=True, spacing=0, tight=True),
                ft.Stack([
                    ft.Container(
                        content=ft.ProgressRing(value=all_done/all_total if all_total else 0,
                                               width=80, height=80, stroke_width=7,
                                               color=Colors.PRIMARY, bgcolor=Colors.BG_SURFACE),
                        alignment=ft.Alignment.CENTER,
                    ),
                    ft.Container(
                        content=ft.Text(f"{int(all_done/all_total*100) if all_total else 0}%",
                                       size=Typography.H4, color=Colors.PRIMARY, weight=Typography.BOLD),
                        alignment=ft.Alignment.CENTER,
                    ),
                ], width=80, height=80),
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            padding=Spacing.MD, border_radius=Radius.LG,
            gradient=ft.LinearGradient(colors=[Colors.BG_CARD, Colors.BG_SURFACE],
                                       begin=ft.Alignment.TOP_LEFT, end=ft.Alignment.BOTTOM_RIGHT),
            border=ft.Border.all(1, Colors.BORDER),
            shadow=ft.BoxShadow(blur_radius=16, color="#0000001A", offset=ft.Offset(0, 4)),
        )

        # ── Assemble ──────────────────────────────────────
        return ft.Column([
            ft.Container(
                content=ft.Row([
                    ft.Text("Analytics", size=Typography.H2, color=Colors.TEXT_PRIMARY, weight=Typography.BOLD),
                    ft.Row([], expand=True),
                    ft.Container(
                        content=ft.Text("AI", size=Typography.TINY, color="white", weight=Typography.BOLD),
                        padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                        border_radius=Radius.FULL,
                        gradient=ft.LinearGradient(colors=["#A855F7","#3B82F6"],
                                                   begin=ft.Alignment.CENTER_LEFT, end=ft.Alignment.CENTER_RIGHT),
                    ),
                ]),
                padding=ft.padding.symmetric(horizontal=Spacing.MD, vertical=Spacing.MD),
            ),
            ft.Container(
                content=ft.Column([
                    month_picker, ft.Container(height=Spacing.MD),
                    stats_row, ft.Container(height=Spacing.MD),
                    prod_card, ft.Container(height=Spacing.MD),
                    burnout_card, ft.Container(height=Spacing.MD),
                    peak_card, ft.Container(height=Spacing.MD),
                    daily_card, ft.Container(height=Spacing.MD),
                    rec_section, ft.Container(height=Spacing.MD),
                    cat_card, ft.Container(height=Spacing.MD),
                    alltime_card, ft.Container(height=Spacing.XXXL),
                ], spacing=0, tight=True),
                padding=ft.padding.symmetric(horizontal=Spacing.MD),
            ),
        ], spacing=0, tight=True, scroll=ft.ScrollMode.AUTO, expand=True)

    main_col = ft.Column([], expand=True)

    def rebuild():
        main_col.controls = [build_content()]
        page.update()

    rebuild()
    return main_col


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _legend_item(label, count, total, color):
    pct = int(count / total * 100) if total else 0
    return ft.Row([
        ft.Container(width=10, height=10, border_radius=Radius.FULL, bgcolor=color),
        ft.Text(label, size=Typography.TINY, color=Colors.TEXT_SECONDARY, expand=True),
        ft.Text(f"{count} ({pct}%)", size=Typography.TINY, color=color, weight=Typography.SEMIBOLD),
    ], spacing=Spacing.SM, vertical_alignment=ft.CrossAxisAlignment.CENTER)


def _cat_bar(cat_key, count, total):
    info  = CATEGORY_MAP.get(cat_key, {"label": cat_key, "icon": "📌", "color": Colors.TEXT_MUTED})
    ratio = count / total if total else 0
    return ft.Container(
        content=ft.Column([
            ft.Row([
                ft.Text(info["icon"], size=14),
                ft.Text(info["label"], size=Typography.SMALL, color=Colors.TEXT_PRIMARY, expand=True),
                ft.Text(str(count), size=Typography.SMALL, color=info["color"], weight=Typography.BOLD),
            ], spacing=Spacing.SM),
            ft.Container(height=4),
            ft.ProgressBar(value=ratio, height=8, border_radius=Radius.FULL,
                           color=Colors.PRIMARY, bgcolor=Colors.BG_SURFACE, expand=True),
        ], spacing=0, tight=True),
        margin=ft.Margin.only(bottom=Spacing.SM),
    )


def _day_bar(dp: dict) -> ft.Column:
    completed = dp.get("completed", 0)
    d_str = dp.get("date", "")
    day_label = ""
    try:
        d = date.fromisoformat(d_str)
        day_label = ["T2","T3","T4","T5","T6","T7","CN"][d.weekday()]
    except Exception:
        day_label = d_str[-2:] if d_str else "?"

    bar_height = min(60, max(8, completed * 15))
    color = Colors.SUCCESS if completed >= 3 else Colors.PRIMARY if completed >= 1 else Colors.BORDER

    return ft.Column([
        ft.Text(str(completed) if completed > 0 else "", size=7,
                color=color, text_align=ft.TextAlign.CENTER),
        ft.Container(width=24, height=bar_height, border_radius=Radius.SM, bgcolor=color),
        ft.Text(day_label, size=7, color=Colors.TEXT_MUTED, text_align=ft.TextAlign.CENTER),
    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2, tight=True)
