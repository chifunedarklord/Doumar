"""
TaskFlow - AI Insights Dashboard Screen
Màn hình phân tích AI chuyên nghiệp: productivity, burnout, heatmap, recommendations.
"""
import flet as ft
from datetime import datetime, date, timedelta
from collections import defaultdict

from core.theme import Colors, Typography, Spacing, Radius
from core.services import AnalyticsService
from components.widgets import section_header, stat_card, primary_divider


def build_insights_screen(page: ft.Page, user, on_navigate):
    """AI Insights Dashboard — motion/sunsama-style analytics."""

    main_col = ft.Column([], expand=True)
    loading_state = {"loading": True}

    def build_content():
        try:
            report = AnalyticsService.get_full_report(user.id)
        except Exception as e:
            report = _default_report()

        burnout   = report.get("burnout", {})
        prod      = report.get("productivity", {})
        focus     = report.get("focus_analysis", {})
        recs      = report.get("recommendations", [])
        weekly_score = report.get("weekly_score", 0)
        peak_hrs  = report.get("peak_hours", [])
        energy    = report.get("energy_level", 7)
        stress    = report.get("stress_level", 5)
        heatmap   = report.get("focus_heatmap", {})
        daily_prod = report.get("daily_productivity", [])
        pomodoro  = report.get("optimal_pomodoro", {})
        cat_perf  = prod.get("category_performance", [])
        streak    = prod.get("streak", {})
        compliance   = report.get("deadline_compliance", {})
        estimation   = report.get("estimation_accuracy", {})
        procrastinate = report.get("procrastination", {})
        workload     = report.get("workload", {})

        from core.services import TaskService as _TS
        from datetime import date as _date
        _tasks_all = _TS.get_tasks(user.id)
        _today_str = _date.today().isoformat()
        _total = len(_tasks_all)
        _done  = sum(1 for t in _tasks_all if t.status == "done")
        _overdue = sum(1 for t in _tasks_all if t.is_overdue)
        _today_cnt = sum(1 for t in _tasks_all
                         if t.due_date == _today_str and t.status != "done")
        _focus_mins = report.get("total_focus_minutes", 0)

        return ft.Column([
            _build_header(user),
            ft.Container(
                content=ft.Column([
                    # Quick summary
                    _build_quick_summary(_total, _done, _overdue, _today_cnt, _focus_mins),
                    ft.Container(height=Spacing.MD),

                    # Status trio
                    _build_status_trio(weekly_score, energy, stress),
                    ft.Container(height=Spacing.MD),

                    # Burnout card
                    _build_burnout_card(burnout),
                    ft.Container(height=Spacing.MD),

                    # Recommendations
                    _build_recommendations(recs, on_navigate, user, page),
                    ft.Container(height=Spacing.MD),

                    # Focus heatmap (24h)
                    _build_focus_heatmap(heatmap, peak_hrs),
                    ft.Container(height=Spacing.MD),

                    # Daily activity chart
                    _build_daily_chart(daily_prod),
                    ft.Container(height=Spacing.MD),

                    # Productivity trends
                    _build_trends(prod.get("productivity_trends", {})),
                    ft.Container(height=Spacing.MD),

                    # Focus stats
                    _build_focus_stats(focus, pomodoro),
                    ft.Container(height=Spacing.MD),

                    # Category performance
                    _build_category_performance(cat_perf),
                    ft.Container(height=Spacing.MD),

                    # Streak
                    _build_streak(streak),
                    ft.Container(height=Spacing.MD),

                    # Behavioral Analytics
                    _build_deadline_compliance(compliance),
                    ft.Container(height=Spacing.MD),
                    _build_estimation_accuracy(estimation),
                    ft.Container(height=Spacing.MD),
                    _build_procrastination_card(procrastinate, workload),
                    ft.Container(height=Spacing.XXXL),
                ], spacing=0, tight=True),
                padding=ft.padding.symmetric(horizontal=Spacing.MD),
            ),
        ], spacing=0, tight=True, scroll=ft.ScrollMode.AUTO, expand=True)

    def rebuild():
        main_col.controls = [build_content()]
        page.update()

    rebuild()
    return main_col


def _build_header(user):
    return ft.Container(
        content=ft.Row([
            ft.Column([
                ft.Text("AI Insights", size=Typography.H2,
                        color=Colors.TEXT_PRIMARY, weight=Typography.BOLD),
                ft.Text("Phân tích thông minh từ hành vi thực tế",
                        size=Typography.TINY, color=Colors.TEXT_MUTED),
            ], spacing=2, tight=True),
            ft.Row([], expand=True),
            ft.Container(
                content=ft.Row([
                    ft.Text("✨", size=12),
                    ft.Text("AI", size=Typography.TINY, color="white", weight=Typography.BOLD),
                ], spacing=4, tight=True),
                padding=ft.padding.symmetric(horizontal=10, vertical=4),
                border_radius=Radius.FULL,
                gradient=ft.LinearGradient(
                    colors=["#A855F7", "#3B82F6"],
                    begin=ft.Alignment.CENTER_LEFT,
                    end=ft.Alignment.CENTER_RIGHT,
                ),
            ),
        ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
        padding=ft.padding.symmetric(horizontal=Spacing.MD, vertical=Spacing.MD),
    )


def _build_status_trio(weekly_score, energy, stress):
    score_color = Colors.SUCCESS if weekly_score >= 70 else Colors.WARNING if weekly_score >= 40 else Colors.ERROR
    energy_color = Colors.SUCCESS if energy >= 7 else Colors.WARNING if energy >= 4 else Colors.ERROR
    stress_color = Colors.ERROR if stress >= 7 else Colors.WARNING if stress >= 5 else Colors.SUCCESS

    def metric_card(label, value, color, icon, unit=""):
        return ft.Container(
            content=ft.Column([
                ft.Text(icon, size=20, text_align=ft.TextAlign.CENTER),
                ft.Container(height=4),
                ft.Text(f"{value}{unit}", size=Typography.H3,
                        color=color, weight=Typography.EXTRABOLD,
                        text_align=ft.TextAlign.CENTER),
                ft.Text(label, size=Typography.TINY,
                        color=Colors.TEXT_MUTED, text_align=ft.TextAlign.CENTER),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER,
               spacing=0, tight=True),
            padding=Spacing.SM, expand=True,
            border_radius=Radius.LG, bgcolor=Colors.BG_CARD,
            border=ft.Border.all(1, f"#40{color[1:]}" if color.startswith("#") else color),
        )

    return ft.Row([
        metric_card("Năng suất", int(weekly_score), score_color, "📊", "/100"),
        ft.Container(width=Spacing.SM),
        metric_card("Năng lượng", energy, energy_color, "⚡", "/10"),
        ft.Container(width=Spacing.SM),
        metric_card("Stress", stress, stress_color, "🧠", "/10"),
    ], spacing=0)


def _build_burnout_card(burnout: dict):
    b_color = burnout.get("color", Colors.SUCCESS)
    b_score = burnout.get("score", 0)
    level = burnout.get("level", "low")
    reasons = burnout.get("reasons", [])
    suggestions = burnout.get("suggestions", [])

    # Burnout probability bar
    details = burnout.get("details", {})

    return ft.Container(
        content=ft.Column([
            ft.Row([
                ft.Text("🔥", size=18),
                ft.Text("Burnout Intelligence", size=Typography.H4,
                        color=Colors.TEXT_PRIMARY, weight=Typography.BOLD),
                ft.Row([], expand=True),
                ft.Container(
                    content=ft.Text(burnout.get("label", "Thấp"),
                                    size=Typography.SMALL, color="white",
                                    weight=Typography.BOLD),
                    padding=ft.padding.symmetric(horizontal=10, vertical=4),
                    border_radius=Radius.FULL, bgcolor=b_color,
                ),
            ], spacing=Spacing.SM, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ft.Container(height=Spacing.SM),
            # Progress bar
            ft.Stack([
                ft.ProgressBar(value=b_score / 100, height=10, border_radius=Radius.FULL,
                               color=b_color, bgcolor=Colors.BG_SURFACE, expand=True),
                ft.Container(
                    content=ft.Text(f"{b_score}%", size=7, color="white", weight=Typography.BOLD),
                    alignment=ft.Alignment(min(0.9, b_score / 100 * 2 - 1), 0),
                ),
            ]),
            *(
                [ft.Container(height=Spacing.SM)] +
                [ft.Row([
                    ft.Container(width=8, height=8, border_radius=4, bgcolor=b_color),
                    ft.Text(r, size=Typography.TINY, color=Colors.TEXT_SECONDARY, expand=True),
                ], spacing=Spacing.XS) for r in reasons[:3]]
                if reasons else
                [ft.Container(height=Spacing.SM),
                 ft.Text("✅ Không có dấu hiệu kiệt sức", size=Typography.SMALL, color=Colors.SUCCESS)]
            ),
            *(
                [ft.Container(height=Spacing.SM),
                 ft.Container(
                     content=ft.Text(f"💡 {suggestions[0]}", size=Typography.TINY, color="#92400E"),
                     padding=ft.padding.symmetric(horizontal=Spacing.SM, vertical=6),
                     border_radius=Radius.SM, bgcolor="#FEF3C7",
                 )] if suggestions else []
            ),
        ], spacing=4, tight=True),
        padding=Spacing.MD, border_radius=Radius.LG,
        bgcolor=Colors.BG_CARD,
        border=ft.Border.all(1, b_color + "40"),
        shadow=ft.BoxShadow(blur_radius=12, color="#00000018", offset=ft.Offset(0, 3)),
    )


def _build_recommendations(recs: list, on_navigate, user=None, page=None):
    if not recs:
        return ft.Container(
            content=ft.Row([
                ft.Text("🎉", size=20),
                ft.Text("Không có gợi ý đặc biệt! Bạn đang làm rất tốt.",
                        size=Typography.SMALL, color=Colors.SUCCESS),
            ], spacing=Spacing.SM),
            padding=Spacing.MD, border_radius=Radius.LG,
            bgcolor=f"#15{Colors.SUCCESS[1:]}", border=ft.Border.all(1, f"#40{Colors.SUCCESS[1:]}"),
        )

    def rec_card(rec: dict):
        pri = rec.get("priority", "low")
        pri_color = (Colors.ERROR if pri == "critical" else Colors.WARNING if pri == "high"
                     else Colors.PRIMARY if pri == "medium" else Colors.TEXT_MUTED)
        card_ref = ft.Ref[ft.Container]()

        def _feedback(accepted: bool, _e=None):
            if user is None:
                return
            from core.services import BehaviorService
            from core.intelligence.event_bus import EventBus, Events
            event_type = Events.RECOMMENDATION_ACCEPTED if accepted else Events.RECOMMENDATION_DISMISSED
            BehaviorService.log(user.id, event_type, {
                "rec_type": rec.get("type", ""),
                "priority": pri,
            })
            EventBus.get_instance().publish(event_type, {
                "user_id": user.id,
                "rec_type": rec.get("type", ""),
            })
            if card_ref.current and page:
                card_ref.current.visible = False
                page.update()

        return ft.Container(
            ref=card_ref,
            content=ft.Column([
                ft.Row([
                    ft.Text(rec.get("icon", "💡"), size=20),
                    ft.Column([
                        ft.Text(rec.get("title", ""), size=Typography.SMALL,
                                color=Colors.TEXT_PRIMARY, weight=Typography.SEMIBOLD),
                        ft.Text(rec.get("message", ""), size=Typography.TINY,
                                color=Colors.TEXT_MUTED, max_lines=2,
                                overflow=ft.TextOverflow.ELLIPSIS),
                    ], spacing=1, tight=True, expand=True),
                    ft.Container(width=6, height=6, border_radius=3, bgcolor=pri_color),
                ], spacing=Spacing.SM, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ft.Row([
                    ft.TextButton(
                        "✓ Đã làm",
                        on_click=lambda e: _feedback(True, e),
                        style=ft.ButtonStyle(
                            color=Colors.SUCCESS,
                            padding=ft.padding.symmetric(horizontal=8, vertical=2),
                        ),
                    ),
                    ft.TextButton(
                        "✗ Bỏ qua",
                        on_click=lambda e: _feedback(False, e),
                        style=ft.ButtonStyle(
                            color=Colors.TEXT_MUTED,
                            padding=ft.padding.symmetric(horizontal=8, vertical=2),
                        ),
                    ),
                ], spacing=0, tight=True),
            ], spacing=2, tight=True),
            padding=ft.padding.symmetric(vertical=Spacing.SM, horizontal=Spacing.SM),
            border_radius=Radius.MD, bgcolor=Colors.BG_CARD,
            border=ft.Border.all(1, f"#40{pri_color[1:]}" if pri_color.startswith("#") else pri_color),
            margin=ft.Margin.only(bottom=Spacing.XS),
            on_click=lambda _: on_navigate("tasks") if rec.get("action") in ("view_tasks", "start_focus") else None,
            ink=True,
        )

    return ft.Column([
        section_header("🤖 AI Recommendations",
                        f"{len(recs)} gợi ý thực tế"),
        ft.Container(height=Spacing.SM),
        ft.Column([rec_card(r) for r in recs], spacing=0, tight=True),
    ], spacing=0, tight=True)


def _build_focus_heatmap(heatmap: dict, peak_hrs: list):
    """Heatmap 24 giờ hiển thị focus quality."""
    bars = []
    for h in range(24):
        val = heatmap.get(h, 0)
        is_peak = h in peak_hrs
        bar_h = max(4, int(val * 32))  # max 32px
        color = Colors.PRIMARY if is_peak else (
            Colors.SUCCESS if val >= 7 else
            Colors.WARNING if val >= 4 else
            Colors.BORDER if val > 0 else Colors.BG_SURFACE
        )
        bars.append(ft.Column([
            ft.Container(width=10, height=bar_h, border_radius=2, bgcolor=color,
                         tooltip=f"{h:02d}:00 — quality: {val:.1f}"),
            ft.Text(str(h) if h % 6 == 0 else "", size=6, color=Colors.TEXT_MUTED),
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER,
           spacing=2, tight=True))

    peak_str = ", ".join(f"{h:02d}h" for h in peak_hrs) if peak_hrs else "Chưa học được"
    return ft.Container(
        content=ft.Column([
            section_header("⚡ Focus Heatmap 24 giờ",
                           f"Peak hours: {peak_str}"),
            ft.Container(height=Spacing.SM),
            ft.Container(
                content=ft.Row(bars, spacing=1, alignment=ft.MainAxisAlignment.CENTER,
                               vertical_alignment=ft.CrossAxisAlignment.END),
                height=52,
            ),
            ft.Row([
                ft.Container(width=10, height=10, border_radius=2, bgcolor=Colors.PRIMARY),
                ft.Text("Peak hour", size=Typography.TINY, color=Colors.TEXT_MUTED),
                ft.Container(width=Spacing.MD),
                ft.Container(width=10, height=10, border_radius=2, bgcolor=Colors.SUCCESS),
                ft.Text("Focus tinggi", size=Typography.TINY, color=Colors.TEXT_MUTED),
            ], spacing=Spacing.XS),
        ], spacing=0, tight=True),
        padding=Spacing.MD, border_radius=Radius.LG,
        bgcolor=Colors.BG_CARD, border=ft.Border.all(1, Colors.BORDER),
        shadow=ft.BoxShadow(blur_radius=12, color="#00000018", offset=ft.Offset(0, 3)),
    )


def _build_daily_chart(daily_prod: list):
    """Bar chart hoạt động 14 ngày."""
    if not daily_prod:
        return ft.Container(height=0)

    max_val = max(max(d.get("completed", 0), d.get("delayed", 0)) for d in daily_prod) or 1

    bars = []
    for dp in daily_prod[-7:]:  # Last 7 days
        completed = dp.get("completed", 0)
        delayed = dp.get("delayed", 0)
        label = dp.get("day_label", "")
        bar_h = max(4, int(completed / max_val * 60))
        delay_h = max(0, int(delayed / max_val * 20))
        today = (dp.get("date", "") == date.today().isoformat())
        color = Colors.PRIMARY if today else Colors.SUCCESS if completed >= 3 else Colors.BORDER if completed == 0 else Colors.ACCENT_CYAN

        bars.append(ft.Column([
            ft.Text(str(completed) if completed > 0 else "", size=7, color=color),
            ft.Stack([
                ft.Container(width=22, height=bar_h, border_radius=Radius.SM, bgcolor=color),
                ft.Container(width=22, height=delay_h, border_radius=Radius.SM,
                             bgcolor=Colors.ERROR + "80") if delayed > 0 else ft.Container(height=0),
            ]),
            ft.Text(label, size=7, color=Colors.PRIMARY if today else Colors.TEXT_MUTED),
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2, tight=True))

    return ft.Container(
        content=ft.Column([
            section_header("📅 Hoạt động 7 ngày", "Xanh=hoàn thành · Đỏ=delay"),
            ft.Container(height=Spacing.SM),
            ft.Row(bars, spacing=4, alignment=ft.MainAxisAlignment.SPACE_AROUND,
                   vertical_alignment=ft.CrossAxisAlignment.END),
        ], spacing=0, tight=True),
        padding=Spacing.MD, border_radius=Radius.LG,
        bgcolor=Colors.BG_CARD, border=ft.Border.all(1, Colors.BORDER),
        shadow=ft.BoxShadow(blur_radius=12, color="#00000018", offset=ft.Offset(0, 3)),
    )


def _build_trends(trends: dict):
    weekly_scores = trends.get("weekly_scores", [])
    trend = trends.get("trend", "stable")
    trend_icon = "📈" if trend == "up" else "📉" if trend == "down" else "➡️"
    trend_color = Colors.SUCCESS if trend == "up" else Colors.ERROR if trend == "down" else Colors.TEXT_MUTED

    if not weekly_scores:
        return ft.Container(height=0)

    max_score = max(w.get("score", 0) for w in weekly_scores) or 1

    bars = []
    for w in weekly_scores:
        score = w.get("score", 0)
        bar_h = max(4, int(score / max_score * 60))
        bars.append(ft.Column([
            ft.Text(f"{score:.0f}", size=7, color=Colors.PRIMARY),
            ft.Container(width=30, height=bar_h, border_radius=Radius.SM, bgcolor=Colors.PRIMARY),
            ft.Text(w.get("week", ""), size=7, color=Colors.TEXT_MUTED),
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2, tight=True))

    return ft.Container(
        content=ft.Column([
            ft.Row([
                ft.Text("📊 Xu hướng 4 tuần", size=Typography.H4,
                        color=Colors.TEXT_PRIMARY, weight=Typography.BOLD),
                ft.Row([], expand=True),
                ft.Text(trend_icon, size=16),
                ft.Text(
                    "Đang tốt lên" if trend == "up" else "Đang giảm" if trend == "down" else "Ổn định",
                    size=Typography.TINY, color=trend_color,
                ),
            ], spacing=Spacing.XS, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ft.Container(height=Spacing.SM),
            ft.Row(bars, spacing=Spacing.MD, alignment=ft.MainAxisAlignment.SPACE_AROUND,
                   vertical_alignment=ft.CrossAxisAlignment.END),
        ], spacing=0, tight=True),
        padding=Spacing.MD, border_radius=Radius.LG,
        bgcolor=Colors.BG_CARD, border=ft.Border.all(1, Colors.BORDER),
        shadow=ft.BoxShadow(blur_radius=12, color="#00000018", offset=ft.Offset(0, 3)),
    )


def _build_focus_stats(focus: dict, pomodoro: dict):
    quality = focus.get("avg_focus_quality", 0)
    deep_ratio = focus.get("deep_work_ratio", 0)
    total_h = focus.get("total_focus_hours", 0)
    trend = focus.get("focus_trend", "stable")
    pomo_work = pomodoro.get("work_minutes", 25)
    pomo_break = pomodoro.get("break_minutes", 5)
    pomo_source = pomodoro.get("source", "default")

    trend_text = "📈 Đang cải thiện" if trend == "improving" else "📉 Đang giảm" if trend == "declining" else "➡️ Ổn định"
    trend_color = Colors.SUCCESS if trend == "improving" else Colors.ERROR if trend == "declining" else Colors.TEXT_MUTED

    return ft.Container(
        content=ft.Column([
            section_header("🎯 Focus Analytics", f"Tổng: {total_h:.1f}h"),
            ft.Container(height=Spacing.SM),
            ft.Row([
                _mini_metric("Chất lượng TB", f"{quality:.1f}/10", Colors.PRIMARY),
                _mini_metric("Deep Work", f"{deep_ratio*100:.0f}%",
                             Colors.SUCCESS if deep_ratio > 0.4 else Colors.WARNING),
                _mini_metric("Trend", trend_text, trend_color),
            ], spacing=Spacing.SM),
            ft.Container(height=Spacing.SM),
            ft.Container(
                content=ft.Row([
                    ft.Text("⏱️", size=14),
                    ft.Column([
                        ft.Text(f"Pomodoro tối ưu của bạn: {pomo_work} phút làm — {pomo_break} phút nghỉ",
                                size=Typography.SMALL, color=Colors.TEXT_PRIMARY,
                                weight=Typography.MEDIUM),
                        ft.Text(
                            "Được học từ work sessions thực tế" if pomo_source == "learned" else "Mặc định Pomodoro",
                            size=Typography.TINY, color=Colors.TEXT_MUTED,
                        ),
                    ], spacing=1, tight=True, expand=True),
                ], spacing=Spacing.SM, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                padding=ft.padding.symmetric(horizontal=Spacing.SM, vertical=8),
                border_radius=Radius.MD, bgcolor=f"#15{Colors.PRIMARY[1:]}",
                border=ft.Border.all(1, f"#40{Colors.PRIMARY[1:]}"),
            ),
        ], spacing=0, tight=True),
        padding=Spacing.MD, border_radius=Radius.LG,
        bgcolor=Colors.BG_CARD, border=ft.Border.all(1, Colors.BORDER),
        shadow=ft.BoxShadow(blur_radius=12, color="#00000018", offset=ft.Offset(0, 3)),
    )


def _build_category_performance(cat_perf: list):
    if not cat_perf:
        return ft.Container(height=0)

    from core.theme import CATEGORY_MAP

    def cat_row(perf: dict):
        cat = perf.get("category", "")
        info = CATEGORY_MAP.get(cat, {"icon": "📌", "label": cat, "color": Colors.TEXT_MUTED})
        score = perf.get("performance_score", 0)
        done_rate = perf.get("completion_rate", 0)
        overdue_rate = perf.get("overdue_rate", 0)
        color = Colors.SUCCESS if score >= 70 else Colors.WARNING if score >= 40 else Colors.ERROR

        return ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Text(info.get("icon", "📌"), size=14),
                    ft.Text(info.get("label", cat), size=Typography.SMALL,
                            color=Colors.TEXT_PRIMARY, expand=True),
                    ft.Text(f"{done_rate:.0f}%", size=Typography.SMALL,
                            color=color, weight=Typography.BOLD),
                ], spacing=Spacing.SM),
                ft.Container(height=3),
                ft.ProgressBar(value=done_rate / 100, height=6, border_radius=Radius.FULL,
                               color=color, bgcolor=Colors.BG_SURFACE, expand=True),
            ], spacing=0, tight=True),
            margin=ft.Margin.only(bottom=Spacing.SM),
        )

    return ft.Container(
        content=ft.Column([
            section_header("📊 Hiệu suất theo danh mục", f"{len(cat_perf)} danh mục"),
            ft.Container(height=Spacing.SM),
            ft.Column([cat_row(p) for p in cat_perf[:5]], spacing=0, tight=True),
        ], spacing=0, tight=True),
        padding=Spacing.MD, border_radius=Radius.LG,
        bgcolor=Colors.BG_CARD, border=ft.Border.all(1, Colors.BORDER),
        shadow=ft.BoxShadow(blur_radius=12, color="#00000018", offset=ft.Offset(0, 3)),
    )


def _build_streak(streak: dict):
    current = streak.get("current_streak", 0)
    label = streak.get("label", "")
    color = Colors.SUCCESS if current >= 7 else Colors.PRIMARY if current >= 3 else Colors.TEXT_MUTED

    return ft.Container(
        content=ft.Row([
            ft.Text("🔥" if current >= 3 else "📅", size=32),
            ft.Container(width=Spacing.MD),
            ft.Column([
                ft.Text(f"{current}", size=Typography.DISPLAY,
                        color=color, weight=Typography.EXTRABOLD),
                ft.Text(label, size=Typography.SMALL, color=Colors.TEXT_MUTED),
            ], spacing=0, tight=True),
        ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
        padding=Spacing.MD, border_radius=Radius.LG,
        gradient=ft.LinearGradient(
            colors=[Colors.BG_CARD, Colors.BG_SURFACE],
            begin=ft.Alignment.TOP_LEFT, end=ft.Alignment.BOTTOM_RIGHT,
        ),
        border=ft.Border.all(1, f"#40{color[1:]}" if color.startswith("#") else color),
        shadow=ft.BoxShadow(blur_radius=12, color="#00000018", offset=ft.Offset(0, 3)),
    )


def _mini_metric(label: str, value: str, color: str) -> ft.Container:
    return ft.Container(
        content=ft.Column([
            ft.Text(value, size=Typography.SMALL, color=color,
                    weight=Typography.BOLD, text_align=ft.TextAlign.CENTER,
                    max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
            ft.Text(label, size=7, color=Colors.TEXT_MUTED,
                    text_align=ft.TextAlign.CENTER),
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2, tight=True),
        padding=ft.padding.symmetric(horizontal=Spacing.XS, vertical=Spacing.SM),
        border_radius=Radius.MD, bgcolor=f"#10{color[1:]}" if color.startswith("#") else color,
        border=ft.Border.all(1, f"#30{color[1:]}" if color.startswith("#") else color),
        expand=True,
    )


def _build_deadline_compliance(compliance: dict):
    """Card tỷ lệ hoàn thành đúng hạn."""
    rate = compliance.get("compliance_rate", 0.0)
    on_time = compliance.get("on_time", 0)
    late = compliance.get("late", 0)
    samples = compliance.get("samples", 0)
    by_cat = compliance.get("by_category", {})

    if samples == 0:
        return ft.Container(
            content=ft.Row([
                ft.Text("📋", size=16),
                ft.Text("Chưa đủ dữ liệu về deadline compliance",
                        size=Typography.SMALL, color=Colors.TEXT_MUTED),
            ], spacing=Spacing.SM),
            padding=Spacing.MD, border_radius=Radius.LG,
            bgcolor=Colors.BG_CARD, border=ft.Border.all(1, Colors.BORDER),
        )

    rate_color = Colors.SUCCESS if rate >= 80 else Colors.WARNING if rate >= 60 else Colors.ERROR

    cat_rows = []
    for cat, info in sorted(by_cat.items(), key=lambda x: -x[1]["rate"])[:4]:
        c_rate = info["rate"]
        c_color = Colors.SUCCESS if c_rate >= 80 else Colors.WARNING if c_rate >= 60 else Colors.ERROR
        cat_rows.append(ft.Row([
            ft.Text(cat[:12], size=7, color=Colors.TEXT_MUTED, expand=True),
            ft.ProgressBar(value=c_rate / 100, height=6, border_radius=Radius.FULL,
                           color=c_color, bgcolor=Colors.BG_SURFACE, expand=2),
            ft.Text(f"{c_rate:.0f}%", size=7, color=c_color, weight=Typography.BOLD),
        ], spacing=Spacing.SM, vertical_alignment=ft.CrossAxisAlignment.CENTER))

    return ft.Container(
        content=ft.Column([
            ft.Row([
                ft.Text("📋", size=18),
                ft.Text("Deadline Compliance", size=Typography.H4,
                        color=Colors.TEXT_PRIMARY, weight=Typography.BOLD),
                ft.Row([], expand=True),
                ft.Container(
                    content=ft.Text(f"{rate:.0f}%", size=Typography.SMALL,
                                    color="white", weight=Typography.BOLD),
                    padding=ft.padding.symmetric(horizontal=10, vertical=4),
                    border_radius=Radius.FULL, bgcolor=rate_color,
                ),
            ], spacing=Spacing.SM, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ft.Container(height=Spacing.SM),
            ft.Row([
                _mini_metric("Đúng hạn", str(on_time), Colors.SUCCESS),
                ft.Container(width=Spacing.SM),
                _mini_metric("Trễ hạn", str(late), Colors.ERROR),
                ft.Container(width=Spacing.SM),
                _mini_metric("Tổng mẫu", str(samples), Colors.TEXT_MUTED),
            ], spacing=0),
            *(
                [ft.Container(height=Spacing.SM),
                 ft.Column(cat_rows, spacing=4, tight=True)]
                if cat_rows else []
            ),
        ], spacing=4, tight=True),
        padding=Spacing.MD, border_radius=Radius.LG,
        bgcolor=Colors.BG_CARD,
        border=ft.Border.all(1, f"#40{rate_color[1:]}" if rate_color.startswith("#") else rate_color),
        shadow=ft.BoxShadow(blur_radius=12, color="#00000018", offset=ft.Offset(0, 3)),
    )


def _build_estimation_accuracy(estimation: dict):
    """Card độ chính xác ước tính thời gian."""
    tendency = estimation.get("tendency", "accurate")
    error_pct = estimation.get("avg_error_pct", 0.0)
    samples = estimation.get("samples", 0)
    by_cat = estimation.get("by_category", {})

    if samples == 0:
        return ft.Container(
            content=ft.Row([
                ft.Text("⏱️", size=16),
                ft.Text("Chưa đủ dữ liệu về estimation accuracy",
                        size=Typography.SMALL, color=Colors.TEXT_MUTED),
            ], spacing=Spacing.SM),
            padding=Spacing.MD, border_radius=Radius.LG,
            bgcolor=Colors.BG_CARD, border=ft.Border.all(1, Colors.BORDER),
        )

    tendency_map = {
        "underestimate": ("⬆️ Underestimate", Colors.WARNING,
                          f"Thực tế lâu hơn {abs(error_pct):.0f}% so với ước tính"),
        "overestimate": ("⬇️ Overestimate", Colors.PRIMARY,
                         f"Thực tế ngắn hơn {abs(error_pct):.0f}% so với ước tính"),
        "accurate": ("✅ Chính xác", Colors.SUCCESS, "Ước tính khá sát với thực tế"),
    }
    label, t_color, desc = tendency_map.get(tendency, tendency_map["accurate"])

    cat_rows = []
    for cat, info in sorted(by_cat.items(), key=lambda x: abs(x[1]["avg_error_pct"]), reverse=True)[:3]:
        err = info["avg_error_pct"]
        tend = info["tendency"]
        c_color = Colors.WARNING if tend == "underestimate" else Colors.PRIMARY if tend == "overestimate" else Colors.SUCCESS
        sign = "+" if err > 0 else ""
        cat_rows.append(ft.Row([
            ft.Text(cat[:14], size=7, color=Colors.TEXT_MUTED, expand=True),
            ft.Text(f"{sign}{err:.0f}%", size=7, color=c_color, weight=Typography.BOLD),
        ], spacing=Spacing.SM))

    return ft.Container(
        content=ft.Column([
            ft.Row([
                ft.Text("⏱️", size=18),
                ft.Text("Estimation Accuracy", size=Typography.H4,
                        color=Colors.TEXT_PRIMARY, weight=Typography.BOLD),
                ft.Row([], expand=True),
                ft.Container(
                    content=ft.Text(label, size=7, color="white", weight=Typography.BOLD),
                    padding=ft.padding.symmetric(horizontal=8, vertical=4),
                    border_radius=Radius.FULL, bgcolor=t_color,
                ),
            ], spacing=Spacing.SM, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ft.Container(height=Spacing.SM),
            ft.Container(
                content=ft.Row([
                    ft.Text("💡", size=12),
                    ft.Text(desc, size=Typography.TINY, color=Colors.TEXT_SECONDARY, expand=True),
                ], spacing=Spacing.XS),
                padding=ft.padding.symmetric(horizontal=Spacing.SM, vertical=6),
                border_radius=Radius.SM,
                bgcolor=f"#15{t_color[1:]}" if t_color.startswith("#") else Colors.BG_SURFACE,
            ),
            *(
                [ft.Container(height=Spacing.SM),
                 ft.Text("Theo danh mục:", size=Typography.TINY, color=Colors.TEXT_MUTED),
                 ft.Column(cat_rows, spacing=4, tight=True)]
                if cat_rows else []
            ),
            ft.Text(f"Từ {samples} task đã hoàn thành", size=7, color=Colors.TEXT_MUTED),
        ], spacing=4, tight=True),
        padding=Spacing.MD, border_radius=Radius.LG,
        bgcolor=Colors.BG_CARD, border=ft.Border.all(1, Colors.BORDER),
        shadow=ft.BoxShadow(blur_radius=12, color="#00000018", offset=ft.Offset(0, 3)),
    )


def _build_procrastination_card(procrastinate: dict, workload: dict):
    """Card procrastination pattern + workload."""
    p_score = procrastinate.get("procrastination_score", 0)
    high_risk = procrastinate.get("high_risk_categories", [])
    worst_time = procrastinate.get("worst_time_of_day")
    total_delays = procrastinate.get("total_delays", 0)
    postponed = procrastinate.get("postponed_tasks", 0)

    overcommit = workload.get("overcommit_score", 0)
    weekly_load = workload.get("weekly_load", 0)

    p_color = Colors.ERROR if p_score >= 60 else Colors.WARNING if p_score >= 30 else Colors.SUCCESS
    p_label = "Cao" if p_score >= 60 else "Trung bình" if p_score >= 30 else "Thấp"

    risk_chips = []
    for item in high_risk:
        risk_chips.append(
            ft.Container(
                content=ft.Text(item["category"][:12], size=7, color=Colors.ERROR),
                padding=ft.padding.symmetric(horizontal=6, vertical=3),
                border_radius=Radius.FULL,
                bgcolor=f"#15{Colors.ERROR[1:]}", border=ft.Border.all(1, f"#40{Colors.ERROR[1:]}"),
            )
        )

    return ft.Container(
        content=ft.Column([
            ft.Row([
                ft.Text("⏳", size=18),
                ft.Text("Procrastination & Workload", size=Typography.H4,
                        color=Colors.TEXT_PRIMARY, weight=Typography.BOLD, expand=True),
            ], spacing=Spacing.SM, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ft.Container(height=Spacing.SM),
            ft.Row([
                _mini_metric("Trì hoãn", p_label, p_color),
                ft.Container(width=Spacing.SM),
                _mini_metric("Đã delay", str(total_delays), Colors.WARNING),
                ft.Container(width=Spacing.SM),
                _mini_metric("7 ngày tới", str(weekly_load), Colors.PRIMARY),
            ], spacing=0),
            *(
                [ft.Container(height=Spacing.SM),
                 ft.Row([
                     ft.Text("Danh mục hay trì hoãn:", size=Typography.TINY,
                             color=Colors.TEXT_MUTED),
                 ] + risk_chips, spacing=Spacing.XS,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    wrap=True)]
                if risk_chips else []
            ),
            *(
                [ft.Container(
                    content=ft.Text(
                        f"💡 Hay trì hoãn vào buổi {worst_time} — thử làm trước.",
                        size=Typography.TINY, color="#92400E",
                    ),
                    padding=ft.padding.symmetric(horizontal=Spacing.SM, vertical=6),
                    border_radius=Radius.SM, bgcolor="#FEF3C7",
                    margin=ft.Margin.only(top=Spacing.SM),
                )]
                if worst_time else []
            ),
            *(
                [ft.Container(
                    content=ft.Text(
                        f"📦 Workload quá tải: {weekly_load} task/7 ngày — nên rải deadline.",
                        size=Typography.TINY, color=Colors.ERROR,
                    ),
                    padding=ft.padding.symmetric(horizontal=Spacing.SM, vertical=6),
                    border_radius=Radius.SM, bgcolor=f"#15{Colors.ERROR[1:]}",
                    margin=ft.Margin.only(top=Spacing.XS),
                )]
                if overcommit >= 30 else []
            ),
        ], spacing=4, tight=True),
        padding=Spacing.MD, border_radius=Radius.LG,
        bgcolor=Colors.BG_CARD,
        border=ft.Border.all(1, f"#40{p_color[1:]}" if p_color.startswith("#") else p_color),
        shadow=ft.BoxShadow(blur_radius=12, color="#00000018", offset=ft.Offset(0, 3)),
    )


def _build_quick_summary(total: int, done: int, overdue: int,
                         today_cnt: int, focus_mins: int) -> ft.Container:
    """Compact overview card at the top of Insights — quick glance for demo."""
    completion_rate = int(done / total * 100) if total else 0
    focus_h = focus_mins // 60
    focus_m = focus_mins % 60
    focus_str = f"{focus_h}h{focus_m:02d}m" if focus_h else f"{focus_mins}p"

    rate_color  = Colors.SUCCESS if completion_rate >= 70 else Colors.WARNING if completion_rate >= 40 else Colors.ERROR
    over_color  = Colors.ERROR if overdue > 0 else Colors.SUCCESS
    today_color = Colors.PRIMARY if today_cnt > 0 else Colors.SUCCESS

    # Actionable tips per metric
    rate_tip  = "Tiếp tục duy trì!" if completion_rate >= 70 else "Tập trung hoàn thành task tồn đọng."
    over_tip  = "Không có task quá hạn!" if overdue == 0 else f"Giải quyết {overdue} task quá hạn ngay."
    today_tip = "Không có task hôm nay!" if today_cnt == 0 else f"{today_cnt} task cần xong hôm nay."
    focus_tip = "Chưa có phiên Focus." if focus_mins == 0 else "Tăng dần thời gian mỗi ngày."

    def _stat_col(icon, value, label, color, tip):
        return ft.Column([
            ft.Text(icon, size=22, text_align=ft.TextAlign.CENTER),
            ft.Text(value, size=Typography.H3, color=color, weight=ft.FontWeight.BOLD,
                    text_align=ft.TextAlign.CENTER),
            ft.Text(label, size=7, color=Colors.TEXT_MUTED, text_align=ft.TextAlign.CENTER),
            ft.Container(height=4),
            ft.Container(
                content=ft.Text(tip, size=7, color=color, text_align=ft.TextAlign.CENTER,
                                max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                padding=ft.padding.symmetric(horizontal=4, vertical=3),
                border_radius=Radius.SM,
                bgcolor=f"#15{color[1:]}" if color.startswith("#") else Colors.BG_SURFACE,
            ),
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2, tight=True, expand=True)

    return ft.Container(
        content=ft.Column([
            ft.Row([
                ft.Text("📈", size=16),
                ft.Text("Tổng quan hôm nay", size=Typography.H4,
                        color=Colors.TEXT_PRIMARY, weight=ft.FontWeight.BOLD, expand=True),
            ], spacing=Spacing.SM),
            ft.Container(height=Spacing.SM),
            ft.Row([
                _stat_col("✅", f"{completion_rate}%",  "Hoàn thành", rate_color,  rate_tip),
                _stat_col("⚠️", str(overdue),           "Quá hạn",    over_color,  over_tip),
                _stat_col("📅", str(today_cnt),         "Hôm nay",    today_color, today_tip),
                _stat_col("🎯", focus_str,              "Focus",      Colors.PRIMARY, focus_tip),
            ], spacing=Spacing.SM),
        ], spacing=0, tight=True),
        padding=Spacing.MD, border_radius=Radius.LG,
        bgcolor=Colors.BG_CARD,
        border=ft.Border.all(1, Colors.BORDER),
        shadow=ft.BoxShadow(blur_radius=12, color="#00000018", offset=ft.Offset(0, 3)),
    )


def _default_report() -> dict:
    return {
        "weekly_score": 0, "energy_level": 7, "stress_level": 5,
        "peak_hours": [], "focus_heatmap": {},
        "burnout": {"level": "low", "label": "Thấp", "color": Colors.SUCCESS,
                    "score": 0, "reasons": [], "suggestions": [], "details": {}},
        "productivity": {"daily_productivity": [], "productivity_trends": {},
                         "category_performance": [], "streak": {"current_streak": 0}},
        "focus_analysis": {"avg_focus_quality": 0, "deep_work_ratio": 0,
                           "total_focus_hours": 0, "focus_trend": "stable"},
        "optimal_pomodoro": {"work_minutes": 25, "break_minutes": 5, "source": "default"},
        "recommendations": [],
        "daily_productivity": [],
        "deadline_compliance": {"on_time": 0, "late": 0, "compliance_rate": 0.0, "by_category": {}, "samples": 0},
        "estimation_accuracy": {"avg_error_pct": 0.0, "tendency": "accurate", "samples": 0, "by_category": {}},
        "procrastination": {"procrastination_score": 0, "high_risk_categories": [], "worst_time_of_day": None, "total_delays": 0, "postponed_tasks": 0},
        "workload": {"overcommit_score": 0, "weekly_load": 0, "overcommitted_days": [], "total_active": 0},
    }
