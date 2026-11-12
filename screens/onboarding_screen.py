"""
TaskFlow - Onboarding Survey Screen
Hiển thị 1 lần sau khi đăng ký. Thu thập preferences để AI có baseline ngay từ đầu.
"""
import flet as ft
from core.theme import Colors, Typography, Spacing, Radius
from core.services import AIMemoryService
from core.database import Storage
from components.widgets import primary_button


# ── Survey data ───────────────────────────────────────────────────────────────

_STEPS = [
    {
        "key": "work_style",
        "question": "Phong cách làm việc của bạn?",
        "icon": "🧠",
        "options": [
            {"label": "Tập trung sâu", "value": "maker",    "desc": "Thích làm 1 việc liên tục 2-4 tiếng"},
            {"label": "Linh hoạt",     "value": "balanced", "desc": "Xen kẽ nhiều loại việc, chuyển đổi dễ"},
            {"label": "Quản lý",       "value": "manager",  "desc": "Nhiều cuộc họp, task ngắn, multitask"},
        ],
    },
    {
        "key": "peak_time",
        "question": "Bạn làm việc tốt nhất lúc nào?",
        "icon": "⏰",
        "options": [
            {"label": "Buổi sáng",  "value": "morning",   "desc": "6h – 12h"},
            {"label": "Buổi chiều", "value": "afternoon",  "desc": "12h – 18h"},
            {"label": "Buổi tối",   "value": "evening",    "desc": "18h – 23h"},
        ],
    },
    {
        "key": "focus_duration",
        "question": "Bạn thường tập trung được bao lâu?",
        "icon": "⏱️",
        "options": [
            {"label": "25 phút",  "value": 25,  "desc": "Pomodoro cổ điển"},
            {"label": "45 phút",  "value": 45,  "desc": "Phổ biến nhất"},
            {"label": "60 phút",  "value": 60,  "desc": "Deep work ngắn"},
            {"label": "90 phút",  "value": 90,  "desc": "Deep work dài"},
        ],
    },
    {
        "key": "stress_tolerance",
        "question": "Mức chịu áp lực của bạn?",
        "icon": "💪",
        "options": [
            {"label": "Thấp",    "value": "low",    "desc": "Dễ bị stress, cần môi trường nhẹ nhàng"},
            {"label": "Trung bình", "value": "medium", "desc": "Chịu được áp lực vừa phải"},
            {"label": "Cao",     "value": "high",   "desc": "Làm tốt nhất dưới deadline"},
        ],
    },
    {
        "key": "role",
        "question": "Vai trò / công việc của bạn?",
        "icon": "💼",
        "options": [
            {"label": "Sinh viên",    "value": "student",      "desc": "Học tập, nghiên cứu"},
            {"label": "Lập trình viên","value": "developer",   "desc": "Code, tech"},
            {"label": "Freelancer",   "value": "freelancer",   "desc": "Làm việc độc lập"},
            {"label": "Khác",         "value": "other",        "desc": "Nghề nghiệp khác"},
        ],
    },
    {
        "key": "main_goal",
        "question": "Mục tiêu chính khi dùng Doumar?",
        "icon": "🎯",
        "options": [
            {"label": "Năng suất công việc", "value": "work",     "desc": "Hoàn thành nhiều việc hơn"},
            {"label": "Học tập",             "value": "study",    "desc": "Quản lý lịch học, bài tập"},
            {"label": "Cân bằng cuộc sống",  "value": "personal", "desc": "Work-life balance"},
            {"label": "Tất cả",              "value": "mixed",    "desc": "Kết hợp nhiều mục tiêu"},
        ],
    },
    {
        "key": "daily_workload",
        "question": "Khối lượng công việc lý tưởng mỗi ngày?",
        "icon": "📋",
        "options": [
            {"label": "Nhẹ",     "value": "light",    "desc": "3-4 task / ngày"},
            {"label": "Vừa phải","value": "moderate", "desc": "5-7 task / ngày"},
            {"label": "Nhiều",   "value": "heavy",    "desc": "8+ task / ngày"},
        ],
    },
    {
        "key": "sleep_schedule",
        "question": "Thói quen ngủ của bạn?",
        "icon": "🌙",
        "options": [
            {"label": "Ngủ sớm",    "value": "early",  "desc": "Ngủ trước 22h, dậy trước 6h"},
            {"label": "Bình thường","value": "normal", "desc": "Ngủ 22-23h, dậy 6-7h"},
            {"label": "Cú đêm",     "value": "late",   "desc": "Ngủ sau 0h, dậy sau 8h"},
        ],
    },
]

_STEP_ORDER = ['main_goal', 'role', 'work_style', 'peak_time', 'focus_duration', 'sleep_schedule', 'daily_workload', 'stress_tolerance']
_STEPS.sort(key=lambda step: _STEP_ORDER.index(step['key']))

_SLEEP_MAP = {
    "early":  ("21:30", "05:30"),
    "normal": ("23:00", "07:00"),
    "late":   ("01:00", "08:30"),
}

_PEAK_HOUR_MAP = {
    "morning":   [7, 8, 9, 10],
    "afternoon": [13, 14, 15, 16],
    "evening":   [19, 20, 21, 22],
}

_WORKLOAD_MAP = {
    "light":    3,
    "moderate": 5,
    "heavy":    4,   # focus_hours, not task count
}


def survey_to_ai_memory(user_id: str, answers: dict):
    """Chuyển survey answers thành AIMemory entries và cập nhật User model."""
    import json
    users = Storage.get_users()
    user = next((u for u in users if u.id == user_id), None)
    if user is None:
        raise ValueError("Không tìm thấy tài khoản để lưu hồ sơ.")
    profile = dict((user.settings or {}).get('planning_profile', {}))
    profile.update(answers)
    user.settings = dict(user.settings or {}, planning_profile=profile)
    field_map = {'role': 'role', 'work_style': 'work_style', 'focus_duration': 'preferred_work_duration'}
    for key, field in field_map.items():
        if key in answers:
            setattr(user, field, answers[key])
    if answers.get('sleep_schedule') in _SLEEP_MAP:
        user.sleep_time, user.wake_time = _SLEEP_MAP[answers['sleep_schedule']]
    if answers.get('peak_time') in _PEAK_HOUR_MAP:
        user.peak_productivity_hours = json.dumps(_PEAK_HOUR_MAP[answers['peak_time']])
    Storage.save_user(user)
    AIMemoryService.remember(user_id, 'preference', 'planning_profile', profile, 1.0)
    for key, value in answers.items():
        AIMemoryService.remember(user_id, 'preference', key, value, 1.0)
    AIMemoryService.remember(user_id, 'system', 'onboarding_done', True, 1.0)
    from utils.ai_helper import invalidate_context_cache
    invalidate_context_cache(user_id)


# ── Screen builder ────────────────────────────────────────────────────────────

def build_onboarding_screen(page: ft.Page, user, on_complete):
    """
    on_complete(): called when user finishes or skips onboarding.
    """
    stored_profile = AIMemoryService.recall_value(user.id, 'preference', 'planning_profile')
    state = {"step": 0, "answers": dict(stored_profile if isinstance(stored_profile, dict) else (user.settings or {}).get("planning_profile", {}))}

    step_indicator = ft.Row([], spacing=4, alignment=ft.MainAxisAlignment.CENTER)
    content_area   = ft.Column([], expand=True, scroll=ft.ScrollMode.AUTO)

    def _update_indicators():
        total = len(_STEPS)
        step_indicator.controls = [
            ft.Container(
                width=24 if i == state["step"] else 8,
                height=8,
                border_radius=4,
                bgcolor=Colors.PRIMARY if i <= state["step"] else Colors.BORDER,
                animate=ft.Animation(200, ft.AnimationCurve.EASE_OUT),
            )
            for i in range(total)
        ]

    def _build_step(idx: int):
        step = _STEPS[idx]
        selected = {"v": state["answers"].get(step["key"])}

        def extra_answer(e, key):
            value = e.control.value.strip()
            if value:
                state['answers'][key] = value
            else:
                state['answers'].pop(key, None)

        extra = ft.Column([
            ft.TextField(label="Lịch cố định và thời gian có thể làm việc (tùy chọn)",
                         hint_text="Ví dụ: học 8–11h thứ 2–6, rảnh chiều thứ 3",
                         value=state['answers'].get('availability', ''), multiline=True,
                         on_change=lambda e: extra_answer(e, 'availability')),
            ft.TextField(label="Thời gian cần giữ riêng / ràng buộc khác (tùy chọn)",
                         value=state['answers'].get('constraints', ''), multiline=True,
                         on_change=lambda e: extra_answer(e, 'constraints')),
        ], visible=idx == len(_STEPS)-1)
        option_controls = ft.Ref[ft.Column]()

        def _select(value):
            selected["v"] = value
            state["answers"][step["key"]] = value
            _refresh_options()

        def _refresh_options():
            option_controls.current.controls = [
                _option_card(opt, selected["v"], _select)
                for opt in step["options"]
            ]
            page.update()

        opts_col = ft.Column(
            [_option_card(opt, selected["v"], _select) for opt in step["options"]],
            spacing=Spacing.SM,
            ref=option_controls,
        )

        is_last = (idx == len(_STEPS) - 1)
        btn_label = "Bắt đầu!" if is_last else "Tiếp theo"

        def _next(_):
            if is_last:
                _finish()
            else:
                state["step"] += 1
                _render()

        return ft.Column([
            ft.Container(
                content=ft.Column([
                    ft.Text(step["icon"], size=40, text_align=ft.TextAlign.CENTER),
                    ft.Container(height=Spacing.SM),
                    ft.Text(
                        step["question"],
                        size=Typography.H3,
                        color=Colors.TEXT_PRIMARY,
                        weight=Typography.BOLD,
                        text_align=ft.TextAlign.CENTER,
                    ),
                    ft.Text(
                        f"Câu {idx + 1}/{len(_STEPS)}",
                        size=Typography.TINY,
                        color=Colors.TEXT_MUTED,
                        text_align=ft.TextAlign.CENTER,
                    ),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                   spacing=4, tight=True),
                padding=ft.padding.symmetric(vertical=Spacing.MD),
            ),
            opts_col,
            extra,
            error,
            ft.Container(height=Spacing.MD),
            ft.FilledButton(btn_label, on_click=_next, height=48, style=ft.ButtonStyle(bgcolor=Colors.PRIMARY, color=Colors.TEXT_ON_PRIMARY)),
            ft.TextButton("Bỏ qua câu này", on_click=lambda e: _skip_step(idx)),
            ft.TextButton("Quay lại", disabled=idx == 0, on_click=lambda e: _back()),
        ], spacing=0, tight=True)

    def _option_card(opt: dict, selected_val, on_select):
        is_sel = (opt["value"] == selected_val)
        return ft.Container(
            content=ft.Row([
                ft.Container(
                    width=20, height=20, border_radius=10,
                    bgcolor=Colors.PRIMARY if is_sel else "transparent",
                    border=ft.Border.all(2, Colors.PRIMARY if is_sel else Colors.BORDER),
                    content=ft.Icon(ft.Icons.CHECK, size=12, color="white") if is_sel else None,
                    alignment=ft.Alignment.CENTER,
                ),
                ft.Column([
                    ft.Text(opt["label"], size=Typography.SMALL,
                            color=Colors.TEXT_PRIMARY, weight=Typography.SEMIBOLD),
                    ft.Text(opt["desc"], size=Typography.TINY, color=Colors.TEXT_MUTED),
                ], spacing=1, tight=True, expand=True),
            ], spacing=Spacing.SM, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            padding=ft.padding.symmetric(horizontal=Spacing.MD, vertical=Spacing.SM),
            border_radius=Radius.LG,
            bgcolor=Colors.PRIMARY_BG if is_sel else Colors.BG_CARD,
            border=ft.Border.all(2, Colors.PRIMARY if is_sel else Colors.BORDER),
            on_click=lambda _, v=opt["value"]: on_select(v),
            ink=True,
            animate=ft.Animation(150, ft.AnimationCurve.EASE_OUT),
        )

    error = ft.Text('', color=Colors.ERROR)

    def _skip_step(idx):
        state['answers'].pop(_STEPS[idx]['key'], None)
        if idx == len(_STEPS) - 1:
            _finish()
        else:
            state['step'] += 1
            _render()

    def _back():
        state['step'] = max(0, state['step'] - 1)
        _render()

    def _finish():
        try:
            survey_to_ai_memory(user.id, state["answers"])
        except Exception as e:
            error.value = "Chưa lưu được hồ sơ. Câu trả lời vẫn được giữ; hãy thử lại."
            page.update()
            return
        user.settings = next((u.settings for u in Storage.get_users() if u.id == user.id), user.settings)
        on_complete()

    def _skip(_):
        _finish()

    def _render():
        _update_indicators()
        content_area.controls = [_build_step(state["step"])]
        page.update()

    _render()

    return ft.Column([
        # Header
        ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Column([
                        ft.Text("Xin chào!", size=Typography.H2,
                                color=Colors.TEXT_PRIMARY, weight=Typography.EXTRABOLD),
                        ft.Text(f"{user.full_name or user.username} 👋",
                                size=Typography.H4, color=Colors.PRIMARY,
                                weight=Typography.SEMIBOLD),
                    ], spacing=2, tight=True, expand=True),
                    ft.TextButton(
                        "Bỏ qua",
                        on_click=_skip,
                        style=ft.ButtonStyle(color=Colors.TEXT_MUTED),
                    ),
                ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ft.Container(height=4),
                ft.Text(
                    "Giúp Doumar hiểu bạn. Bạn có thể bỏ qua từng câu và bổ sung sau.",
                    size=Typography.SMALL, color=Colors.TEXT_MUTED,
                ),
                ft.Container(height=Spacing.SM),
                step_indicator,
            ], spacing=0, tight=True),
            padding=ft.padding.symmetric(horizontal=Spacing.MD, vertical=Spacing.MD),
            bgcolor=Colors.BG_CARD,
            border=ft.Border(bottom=ft.BorderSide(1, Colors.BORDER)),
        ),

        # Step content
        ft.Container(
            content=content_area,
            expand=True,
            padding=ft.padding.symmetric(horizontal=Spacing.MD, vertical=Spacing.MD),
            bgcolor=Colors.BG_DARKEST,
        ),
    ], spacing=0, tight=True, expand=True)
