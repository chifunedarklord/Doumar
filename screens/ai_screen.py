"""
TaskFlow - AI Assistant Screen
AI chat + AI Planner (Notion-like): lập kế hoạch, tạo task, refine plan.
"""
import flet as ft
import threading
import uuid
import logging
from datetime import datetime

from core.theme import Colors, Typography, Spacing, Radius
from components.widgets import snack
from components.desktop_style import monochrome
from core.i18n import t, get_lang, tts_code, stt_code, ai_lang_instruction

logger = logging.getLogger(__name__)
_tasks_changed_callback = [None]


def _notify_task_list():
    if _tasks_changed_callback[0]:
        try:
            _tasks_changed_callback[0]()
        except Exception:
            logger.exception("Could not refresh task list after AI save")

def _get_quick_prompts():
    return [
        ("📊", t("quick_analyze"),  t("quick_analyze_prompt")),
        ("📋", t("quick_plan"),     t("quick_plan_prompt")),
        ("🎯", t("quick_priority"), t("quick_priority_prompt")),
        ("✈️", t("quick_leisure"),  t("quick_leisure_prompt")),
    ]


# ── Plan card renderer ────────────────────────────────────────────────────────

def _render_plan_card(plan: dict, on_save_tasks, on_refine) -> ft.Container:
    from components.ai_plan import build_plan
    return build_plan(plan, _current_page[0], _current_user_id[0], on_save_tasks, on_refine)


# ── Main screen builder ───────────────────────────────────────────────────────

_current_page           = [None]   # module-level refs for save task callbacks
_current_user_id        = [""]
_current_navigate       = [None]
_current_plan_data      = [None, None]  # [plan_result, session_id] — per-session
_pending_prompt         = [None]        # auto-send on next screen load
_current_priority_shown = [False, None] # [shown, session_id] — per-session


def set_pending_prompt(text: str):
    """Đặt tin nhắn sẽ tự động gửi khi AI screen được mở kế tiếp."""
    _pending_prompt[0] = text


def build_ai_screen(page: ft.Page, user, on_navigate, compact=False, on_close=None, on_tasks_changed=None, standalone=False):
    from core.services import TaskService, ChatService
    from core.access import require_feature, UpgradeRequired

    def allowed(feature):
        try:
            require_feature(user.id, feature)
            return True
        except UpgradeRequired as exc:
            snack(page, str(exc))
            return False

    _current_page[0]     = page
    _current_user_id[0]  = user.id
    _current_navigate[0] = on_navigate
    _tasks_changed_callback[0] = on_tasks_changed

    tasks   = TaskService.get_tasks(user.id)
    total   = len(tasks)
    done    = sum(1 for t in tasks if t.status == "done")
    pending = sum(1 for t in tasks if t.status == "todo")
    pct     = int(done / total * 100) if total else 0

    # ── State ──────────────────────────────────────────────────
    _state = {
        "session_id": None,
        "last_plan": None,      # stores last plan_result for refine
    }

    # ── Chat ListView ──────────────────────────────────────────
    chat_lv = ft.ListView(
        expand=True,
        spacing=12,
        padding=ft.Padding.symmetric(horizontal=Spacing.MD, vertical=Spacing.MD),
        auto_scroll=True,
    )

    # ── TTS helper (language-aware, gTTS → pygame → PowerShell) ─
    def _speak_text(text: str):
        if not allowed("ai_voice"):
            return
        lang_code = tts_code()   # "vi" / "en" / "zh-CN"
        def _run():
            import os as _os, tempfile as _tmp
            tmp_path = None
            try:
                from gtts import gTTS
                tts = gTTS(text=text[:600], lang=lang_code, slow=False)
                fd, tmp_path = _tmp.mkstemp(suffix=".mp3")
                _os.close(fd)
                tts.save(tmp_path)
                # Try pygame first
                try:
                    import pygame
                    pygame.mixer.init()
                    pygame.mixer.music.load(tmp_path)
                    pygame.mixer.music.play()
                    import time
                    while pygame.mixer.music.get_busy():
                        time.sleep(0.05)
                    pygame.mixer.music.unload()
                    return
                except Exception:
                    pass
                # Fallback player: platform-specific
                try:
                    import subprocess, sys as _sys, shutil as _shutil
                    cflags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if _sys.platform == "win32" else 0
                    sp_kwargs = {"creationflags": cflags} if _sys.platform == "win32" and cflags else {}

                    if _sys.platform == "win32":
                        safe = tmp_path.replace("\\", "/")
                        subprocess.run(
                            ["powershell", "-NoProfile", "-Command",
                             f'$p=New-Object -ComObject WMPlayer.OCX.7;'
                             f'$p.URL="{safe}";$p.controls.play();'
                             f'Start-Sleep -Seconds 30;$p.controls.stop()'],
                            timeout=35, **sp_kwargs
                        )
                    elif _sys.platform == "darwin":
                        subprocess.run(["afplay", tmp_path], timeout=35)
                    elif _sys.platform.startswith("linux"):
                        for player in ["paplay", "aplay", "ffplay", "mpg123"]:
                            if _shutil.which(player):
                                if player == "ffplay":
                                    subprocess.run(["ffplay", "-nodisp", "-autoexit", tmp_path], timeout=35, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                                else:
                                    subprocess.run([player, tmp_path], timeout=35, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                                break
                except Exception:
                    pass
            except ImportError:
                # gTTS not installed — fall back to pyttsx3 / SAPI / macOS say / Linux spd-say
                try:
                    import pyttsx3
                    engine = pyttsx3.init()
                    engine.setProperty("rate", 155)
                    for v in engine.getProperty("voices"):
                        id_name = (v.id + v.name).lower()
                        if lang_code == "vi" and any(k in id_name for k in ("vi", "viet")):
                            engine.setProperty("voice", v.id); break
                        elif lang_code == "en" and "en" in id_name:
                            engine.setProperty("voice", v.id); break
                        elif lang_code.startswith("zh") and any(k in id_name for k in ("zh", "chin")):
                            engine.setProperty("voice", v.id); break
                    engine.say(text[:600])
                    engine.runAndWait()
                except Exception:
                    try:
                        import subprocess, re, sys as _sys, shutil as _shutil
                        clean = re.sub(r'[\"\'\\]', "", text[:400]).replace("\n", " ")
                        cflags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if _sys.platform == "win32" else 0
                        sp_kwargs = {"creationflags": cflags} if _sys.platform == "win32" and cflags else {}

                        if _sys.platform == "win32":
                            subprocess.run(
                                ["powershell", "-NoProfile", "-Command",
                                 f'Add-Type -AssemblyName System.Speech;'
                                 f'$s=New-Object System.Speech.Synthesis.SpeechSynthesizer;'
                                 f'$s.Rate=1;$s.Speak("{clean}")'],
                                timeout=40, **sp_kwargs
                            )
                        elif _sys.platform == "darwin":
                            subprocess.run(["say", clean], timeout=40)
                        elif _sys.platform.startswith("linux"):
                            for tts_cmd in ["spd-say", "espeak"]:
                                if _shutil.which(tts_cmd):
                                    subprocess.run([tts_cmd, clean], timeout=40)
                                    break
                    except Exception:
                        pass
            except Exception:
                pass
            finally:
                if tmp_path:
                    try:
                        _os.unlink(tmp_path)
                    except Exception:
                        pass
        threading.Thread(target=_run, daemon=True).start()

    # ── Markdown renderer (AI bubble only) ────────────────────
    def _render_md(text: str) -> ft.Column:
        """Convert markdown-like AI text to rich Flet controls."""
        import re as _re

        TC = Colors.TEXT_PRIMARY
        TP = Colors.PRIMARY
        TE = Colors.ERROR
        TW = Colors.WARNING
        TS = Colors.SUCCESS

        BODY = Typography.BODY
        SEMI = Typography.SEMIBOLD
        BOLD = Typography.BOLD

        # emoji → color mapping for leading status emoji
        EMOJI_COLOR = {
            "🔴": TE, "⚠️": TE, "❌": TE,
            "🟡": TW, "⏰": TW, "💡": TW,
            "🟢": TS, "✅": TS, "🎉": TS,
            "⚡": TP, "📊": TP, "📋": TP, "🎯": TP,
        }

        def _spans(raw: str) -> list:
            """Split **bold** into TextSpan list for ft.Text(spans=...)."""
            parts = _re.split(r'\*\*(.+?)\*\*', raw)
            result = []
            for i, p in enumerate(parts):
                if p:
                    result.append(ft.TextSpan(
                        p,
                        style=ft.TextStyle(
                            weight=BOLD if i % 2 == 1 else None,
                            color=TC, size=BODY,
                        ),
                    ))
            return result or [ft.TextSpan(raw, style=ft.TextStyle(color=TC, size=BODY))]

        def _line_ctrl(raw: str):
            s = raw.strip()
            if not s:
                return ft.Container(height=4)

            # ## Section header
            if s.startswith('## '):
                return ft.Container(
                    content=ft.Text(s[3:], size=Typography.SMALL, color=TC,
                                    weight=BOLD, selectable=True),
                    padding=ft.padding.only(top=8, bottom=2),
                )

            # → Action line  (e.g. "**→ Gợi ý:**" or "→ Hành động")
            m = _re.match(r'^(?:\*\*)?→\s*(?:\*\*)?\s*(.*)', s)
            if m:
                body = _re.sub(r'\*\*', '', m.group(1)).strip()
                return ft.Container(
                    content=ft.Row([
                        ft.Container(
                            content=ft.Text("→", size=BODY, color=TP, weight=BOLD),
                            width=18,
                        ),
                        ft.Text(body, size=BODY, color=TP, weight=SEMI,
                                expand=True, selectable=True),
                    ], spacing=4, vertical_alignment=ft.CrossAxisAlignment.START),
                    padding=ft.padding.only(top=3),
                )

            # • Bullet  (•, -, *)
            bm = _re.match(r'^[•\-\*]\s+(.*)', s)
            if bm:
                body = bm.group(1)
                if '**' in body:
                    content_ctrl = ft.Text(
                        spans=_spans(body), selectable=True,
                        expand=True,
                    )
                else:
                    content_ctrl = ft.Text(body, size=BODY, color=TC,
                                           selectable=True, expand=True)
                return ft.Container(
                    content=ft.Row([
                        ft.Container(
                            width=5, height=5, border_radius=3, bgcolor=TP,
                            margin=ft.margin.only(top=6),
                        ),
                        content_ctrl,
                    ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.START),
                    padding=ft.padding.only(left=4, top=2, bottom=2),
                )

            # Regular line — parse inline **bold**
            if '**' in s:
                return ft.Text(spans=_spans(s), selectable=True)

            # Plain text — detect leading emoji for color tinting
            first_emoji = s[:2].strip()
            accent = EMOJI_COLOR.get(first_emoji)
            return ft.Text(
                s, size=BODY,
                color=accent if accent else TC,
                selectable=True,
            )

        lines = text.split('\n')
        controls: list = []
        prev_spacer = False
        for raw in lines:
            ctrl = _line_ctrl(raw)
            is_spacer = (isinstance(ctrl, ft.Container)
                         and getattr(ctrl, 'height', None) in (3, 4, 6))
            if is_spacer and prev_spacer:
                continue         # collapse consecutive blank lines
            controls.append(ctrl)
            prev_spacer = is_spacer

        return ft.Column(
            controls or [ft.Text(text, size=BODY, color=TC, selectable=True)],
            spacing=1, tight=True,
        )

    # ── Bubble helper ──────────────────────────────────────────
    def _bubble(text: str, is_user: bool = False, animate: bool = True) -> ft.Row:
        # User bubble: plain white text (short, no markdown)
        # AI bubble: rich markdown renderer
        if is_user:
            content = ft.Text(
                text,
                size=Typography.BODY,
                color="white",
                selectable=True,
            )
        else:
            content = _render_md(text)

        bubble = ft.Container(
            content=content,
            padding=ft.Padding.symmetric(horizontal=14, vertical=10),
            border_radius=ft.BorderRadius(
                top_left=16, top_right=16,
                bottom_right=4 if is_user else 16,
                bottom_left=16 if is_user else 4,
            ),
            bgcolor=Colors.PRIMARY if is_user else Colors.BG_CARD,
            border=ft.Border.all(1, Colors.BORDER) if not is_user else None,
            shadow=ft.BoxShadow(blur_radius=8, color="#00000018", offset=ft.Offset(0, 2)),
            animate=ft.Animation(300, ft.AnimationCurve.EASE_OUT) if animate else None,
        )
        if compact:
            bubble.bgcolor = "#F5F5F5" if is_user else "#FFFFFF"
            bubble.border_radius = 6
            bubble.border = None
            bubble.shadow = None
            monochrome(bubble)
        ai_avatar = ft.Container(
            content=ft.Image(src="ink-cat.png", fit="cover"),
            width=44, height=44, border_radius=0,
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        )
        if compact:
            ai_avatar.content = ft.Image(src="ink-cat.png", fit="contain")
            ai_avatar.width = 44
            ai_avatar.height = 44
        if is_user:
            return ft.Row([ft.Container(expand=1),
                           ft.Column([bubble], expand=4,
                                     horizontal_alignment=ft.CrossAxisAlignment.END)],
                          spacing=0)
        speak_btn = ft.GestureDetector(
            on_tap=lambda _, tx=text: _speak_text(tx),
            content=ft.Container(
                content=ft.Row([
                    ft.Icon(ft.Icons.VOLUME_UP_OUTLINED, size=12, color=Colors.TEXT_MUTED),
                    ft.Text(t("listen"), size=11 if compact else 8, color=Colors.TEXT_MUTED),
                ], spacing=3, tight=True),
                padding=ft.padding.symmetric(horizontal=8, vertical=3),
                border_radius=Radius.FULL,
                border=ft.Border.all(1, Colors.BORDER),
                margin=ft.margin.only(top=3),
            ),
        )
        return ft.Row([ai_avatar,
                       ft.Column([bubble, speak_btn], expand=True,
                                 horizontal_alignment=ft.CrossAxisAlignment.START)],
                      spacing=Spacing.SM, vertical_alignment=ft.CrossAxisAlignment.START)

    def _bubble_voice(text: str) -> ft.Row:
        """User-side voice message bubble (purple, with mic icon)."""
        bubble = ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Icon(ft.Icons.MIC_ROUNDED, size=11, color="rgba(255,255,255,0.8)"),
                    ft.Text(t("voice_label"), size=8,
                            color="rgba(255,255,255,0.7)", weight=Typography.SEMIBOLD),
                ], spacing=4, tight=True),
                ft.Text(text, size=Typography.BODY, color="white", selectable=True),
            ], spacing=3, tight=True),
            padding=ft.Padding.symmetric(horizontal=14, vertical=10),
            border_radius=ft.BorderRadius(top_left=16, top_right=16,
                                          bottom_right=4, bottom_left=16),
            bgcolor=Colors.VIOLET,
            shadow=ft.BoxShadow(blur_radius=8, color="#00000020", offset=ft.Offset(0, 2)),
        )
        return ft.Row(
            [ft.Container(expand=1),
             ft.Column([bubble], expand=4, horizontal_alignment=ft.CrossAxisAlignment.END)],
            spacing=0,
        )

    def _bubble_file(fname: str, is_image: bool = False) -> ft.Row:
        """User-side file/image bubble (teal, with file icon)."""
        icon = ft.Icons.IMAGE_ROUNDED if is_image else ft.Icons.DESCRIPTION_ROUNDED
        accent = "#06B6D4"   # cyan-500
        accent_bg = "#0E7490"
        bubble = ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Icon(icon, size=13, color="rgba(255,255,255,0.85)"),
                    ft.Text(
                        "Ảnh" if is_image else "File",
                        size=8,
                        color="rgba(255,255,255,0.7)",
                        weight=Typography.SEMIBOLD,
                    ),
                ], spacing=4, tight=True),
                ft.Text(fname, size=Typography.BODY, color="white",
                        selectable=True, max_lines=2,
                        overflow=ft.TextOverflow.ELLIPSIS),
            ], spacing=3, tight=True),
            padding=ft.Padding.symmetric(horizontal=14, vertical=10),
            border_radius=ft.BorderRadius(top_left=16, top_right=16,
                                          bottom_right=4, bottom_left=16),
            gradient=ft.LinearGradient(
                colors=[accent, accent_bg],
                begin=ft.Alignment.TOP_LEFT,
                end=ft.Alignment.BOTTOM_RIGHT,
            ),
            shadow=ft.BoxShadow(blur_radius=8, color="#00000020", offset=ft.Offset(0, 2)),
        )
        return ft.Row(
            [ft.Container(expand=1),
             ft.Column([bubble], expand=4, horizontal_alignment=ft.CrossAxisAlignment.END)],
            spacing=0,
        )

    def _plan_row(plan_data: dict) -> ft.Row:
        """Wrap plan card in the AI-side row layout."""
        ai_avatar = ft.Container(
            content=ft.Image(src="ink-cat.png", fit="cover"),
            width=44, height=44, border_radius=0,
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        )

        def _on_save(evt=None):
            _notify_task_list()

        def _on_refine(option: str):
            _do_refine(option)

        card = _render_plan_card(plan_data, _on_save, _on_refine)
        return ft.Row(
            [ai_avatar,
             ft.Column([card], expand=True,
                       horizontal_alignment=ft.CrossAxisAlignment.START)],
            spacing=Spacing.SM,
            vertical_alignment=ft.CrossAxisAlignment.START,
        )

    def _scroll_down():
        async def _s():
            try:
                await chat_lv.scroll_to(offset=99999, duration=300)
            except Exception:
                pass
        try:
            page.run_task(_s)
        except Exception:
            pass

    def _add_to_chat(control, scroll=True):
        if compact:
            monochrome(control)
        if _typing in chat_lv.controls:
            idx = chat_lv.controls.index(_typing)
            chat_lv.controls.insert(idx, control)
        else:
            chat_lv.controls.append(control)
        page.update()
        if scroll:
            _scroll_down()

    # ── Typing indicator ───────────────────────────────────────
    _typing = ft.Container(
        content=ft.Row([
            ft.Container(
                content=ft.Image(src="ink-cat.png", fit="cover"),
                width=26, height=26, border_radius=13,
                clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            ),
            ft.Container(
                content=ft.Row([
                    ft.Container(width=7, height=7, border_radius=4,
                                 bgcolor=Colors.TEXT_MUTED,
                                 animate=ft.Animation(600, ft.AnimationCurve.EASE_IN_OUT)),
                    ft.Container(width=7, height=7, border_radius=4,
                                 bgcolor=Colors.TEXT_MUTED,
                                 animate=ft.Animation(600, ft.AnimationCurve.EASE_IN_OUT)),
                    ft.Container(width=7, height=7, border_radius=4,
                                 bgcolor=Colors.TEXT_MUTED,
                                 animate=ft.Animation(600, ft.AnimationCurve.EASE_IN_OUT)),
                ], spacing=4),
                padding=ft.Padding.symmetric(horizontal=14, vertical=10),
                border_radius=ft.BorderRadius(16, 16, 16, 4),
                bgcolor=Colors.BG_CARD,
                border=ft.Border.all(1, Colors.BORDER),
            ),
            ft.Container(expand=True),
        ], spacing=Spacing.SM, vertical_alignment=ft.CrossAxisAlignment.END),
        visible=False,
    )

    # ── Input bar ──────────────────────────────────────────────
    tf = ft.TextField(
        hint_text=t("ai_typing"),
        hint_style=ft.TextStyle(color=Colors.TEXT_MUTED),
        bgcolor=Colors.BG_INPUT,
        border_color=Colors.BORDER,
        focused_border_color=Colors.PRIMARY,
        text_style=ft.TextStyle(color=Colors.TEXT_PRIMARY),
        border_radius=Radius.LG,
        cursor_color=Colors.PRIMARY,
        expand=True,
        on_submit=lambda e: _send(e),
    )

    # ── Image picker ───────────────────────────────────────────
    def _pick(e):
        if not allowed("ai_images"):
            return
        tf.hint_text = "Đang chọn Ảnh..."
        tf.disabled = True
        page.update()

        def _run():
            try:
                import tkinter as tk
                from tkinter import filedialog
                root = tk.Tk()
                root.attributes('-topmost', True)
                root.withdraw()
                file_path = filedialog.askopenfilename(
                    title="Chọn ảnh",
                    filetypes=[("Image files", "*.jpg;*.jpeg;*.png;*.bmp;*.webp")]
                )
                root.destroy()
            except Exception:
                file_path = None
            tf.hint_text = t("ai_typing")
            tf.disabled = False
            try: page.update()
            except Exception: pass
            if file_path:
                import os as _os
                fname = _os.path.basename(file_path)
                _add_to_chat(_bubble_file(fname, is_image=True))
                if _state["session_id"]:
                    ChatService.add_message(user.id, _state["session_id"],
                                            "user", f"[📷 Đã gửi ảnh: {fname}]")
                try:
                    from core.services import BehaviorService as _BS
                    _BS.log(user.id, "chat_sent", {"length": 0, "via": "image"})
                except Exception:
                    pass
                _load_sessions_ui()
                try: page.update()
                except Exception: pass
                # Route image through plan reply for structured plan card
                _run_plan_reply(
                    "Hãy phân tích hình ảnh này, nhận diện các công việc/nhiệm vụ "
                    "cần làm và lập kế hoạch chi tiết với các bước thực hiện cụ thể.",
                    image_path=file_path,
                )

        threading.Thread(target=_run, daemon=True).start()

    # ── Voice recording (bấm mic → record mode → bấm Gửi → AI) ──
    # Dùng sounddevice (có wheel cho Python 3.14); fallback sang sr.Microphone
    _mic_state = {"recording": False}
    _rec_ctx   = {}      # frames, samplerate
    _rec_secs  = [0]
    rec_timer_ref  = ft.Ref[ft.Text]()
    input_area_ref = ft.Ref[ft.Container]()

    SAMPLERATE = 16000

    def _start_recording() -> bool:
        """Bắt đầu ghi âm non-blocking qua sounddevice. Trả về False nếu lỗi."""
        if not allowed("ai_voice"):
            return False
        try:
            import sounddevice as sd
            import numpy as np

            _rec_ctx.clear()
            _rec_ctx["frames"] = []
            _rec_ctx["sr"]     = SAMPLERATE
            _mic_state["recording"] = True

            def _callback(indata, frames_count, time_info, status):
                if _mic_state["recording"]:
                    _rec_ctx["frames"].append(indata.copy())

            stream = sd.InputStream(
                samplerate=SAMPLERATE, channels=1, dtype="int16",
                callback=_callback, blocksize=1024,
            )
            stream.start()
            _rec_ctx["stream"] = stream
            return True

        except ImportError:
            snack(page, "❌ Thiếu thư viện sounddevice. Chạy: pip install sounddevice")
            try: page.update()
            except Exception: pass
            return False
        except Exception as _ex:
            msg = str(_ex)
            if "No Default Input" in msg or "Invalid" in msg or "device" in msg.lower():
                snack(page, "❌ Không tìm thấy micro. Hãy cắm mic và thử lại.")
            else:
                snack(page, f"❌ Lỗi micro: {msg[:80]}")
            try: page.update()
            except Exception: pass
            return False

    def _stop_recording() -> str:
        """Dừng ghi, nhận dạng Google STT, trả về text."""
        _mic_state["recording"] = False

        stream = _rec_ctx.pop("stream", None)
        frames = _rec_ctx.pop("frames", [])
        sr_    = _rec_ctx.pop("sr", SAMPLERATE)
        _rec_ctx.clear()

        try:
            if stream:
                stream.stop(); stream.close()
        except Exception:
            pass

        if not frames:
            snack(page, "⚠️ Không ghi được âm thanh — thử lại.")
            try: page.update()
            except Exception: pass
            return ""

        try:
            import numpy as np, io, wave as _wave
            import speech_recognition as sr

            # Gộp frames numpy → bytes PCM int16
            audio_np = np.concatenate(frames, axis=0).astype(np.int16)
            raw_bytes = audio_np.tobytes()

            # Tạo WAV in-memory để sr đọc được
            buf = io.BytesIO()
            with _wave.open(buf, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)          # int16 = 2 bytes
                wf.setframerate(sr_)
                wf.writeframes(raw_bytes)
            buf.seek(0)

            r = sr.Recognizer()
            with sr.AudioFile(buf) as src:
                audio_data = r.record(src)

            lang = stt_code()
            try:
                return r.recognize_google(audio_data, language=lang)
            except sr.UnknownValueError:
                snack(page, "❌ Không nhận dạng được — nói to và rõ hơn.")
                try: page.update()
                except Exception: pass
                return ""
            except sr.RequestError as _re:
                snack(page, f"❌ Lỗi Google STT: {str(_re)[:60]}")
                try: page.update()
                except Exception: pass
                return ""
            except Exception:
                try:
                    return r.recognize_google(audio_data, language="vi-VN")
                except Exception:
                    snack(page, "❌ Nhận dạng thất bại — thử lại.")
                    try: page.update()
                    except Exception: pass
                    return ""
        except ImportError as _ie:
            snack(page, f"❌ Thiếu thư viện: {_ie}")
            try: page.update()
            except Exception: pass
            return ""
        except Exception as _ex:
            snack(page, f"❌ Nhận dạng: {str(_ex)[:60]}")
            try: page.update()
            except Exception: pass
            return ""

    def _timer_loop():
        import time as _time
        _rec_secs[0] = 0
        while _mic_state.get("recording"):
            _time.sleep(1)
            _rec_secs[0] += 1
            if rec_timer_ref.current:
                s = _rec_secs[0]
                rec_timer_ref.current.value = f"{s // 60}:{s % 60:02d}"
                try: page.update()
                except Exception: pass

    # ── Chuyển đổi giao diện recording / normal ────────────────
    def _make_rec_row():
        return ft.Row([
            # Nút hủy
            ft.Container(
                content=ft.Icon(ft.Icons.CLOSE_ROUNDED, size=20, color=Colors.TEXT_MUTED),
                width=42, height=42, border_radius=Radius.LG,
                bgcolor=Colors.BG_INPUT, border=ft.Border.all(1, Colors.BORDER),
                alignment=ft.Alignment.CENTER,
                on_click=_cancel_recording, ink=True, tooltip="Huỷ",
            ),
            # Thanh hiển thị đang ghi
            ft.Container(
                content=ft.Row([
                    ft.Container(
                        width=9, height=9, border_radius=5, bgcolor=Colors.ERROR,
                        animate=ft.Animation(700, ft.AnimationCurve.EASE_IN_OUT),
                    ),
                    ft.Text("Đang ghi âm...", size=Typography.SMALL,
                            color=Colors.ERROR, weight=Typography.SEMIBOLD),
                    ft.Container(expand=True),
                    ft.Text("0:00", ref=rec_timer_ref,
                            size=Typography.SMALL, color=Colors.TEXT_MUTED),
                ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                expand=True, height=44,
                border_radius=Radius.LG,
                bgcolor=f"#14EF4444",
                border=ft.Border.all(1.5, Colors.ERROR),
                padding=ft.padding.symmetric(horizontal=14),
                animate=ft.Animation(200, ft.AnimationCurve.EASE_OUT),
            ),
            # Nút gửi giọng nói
            ft.Container(
                content=ft.Row([
                    ft.Icon(ft.Icons.SEND_ROUNDED, color="white", size=18),
                ], alignment=ft.MainAxisAlignment.CENTER),
                width=46, height=46, border_radius=Radius.LG,
                gradient=ft.LinearGradient(
                    colors=["#EF4444", "#B91C1C"],
                    begin=ft.Alignment.TOP_LEFT, end=ft.Alignment.BOTTOM_RIGHT,
                ),
                alignment=ft.Alignment.CENTER,
                on_click=_send_voice, ink=True,
                tooltip="Gửi giọng nói",
                shadow=ft.BoxShadow(blur_radius=10, color="#40EF4444",
                                    offset=ft.Offset(0, 3)),
            ),
        ], spacing=Spacing.SM)

    def _enter_recording_mode():
        if input_area_ref.current:
            input_area_ref.current.content = _make_rec_row()
        try: page.update()
        except Exception: pass
        threading.Thread(target=_timer_loop, daemon=True).start()

    def _exit_recording_mode():
        if input_area_ref.current:
            input_area_ref.current.content = _normal_input_row
        try: page.update()
        except Exception: pass

    def _cancel_recording(_=None):
        _mic_state["recording"] = False
        import time; time.sleep(0.05)
        _exit_recording_mode()

    def _send_voice(_=None):
        """Dừng ghi, nhận dạng, gửi cho AI."""
        def _worker():
            _exit_recording_mode()          # trả UI về normal ngay
            recognized = _stop_recording()
            if not recognized:
                return
            # Thêm voice bubble tím
            _add_to_chat(_bubble_voice(recognized))
            if _state["session_id"]:
                from core.services import ChatService as _CS
                _CS.add_message(user.id, _state["session_id"], "user", recognized)
            try:
                from core.services import BehaviorService as _BS
                _BS.log(user.id, "chat_sent", {"length": len(recognized), "via": "voice"})
            except Exception:
                pass
            _load_sessions_ui()
            try: page.update()
            except Exception: pass
            # Gửi cho AI
            from core.ai_planner_service import detect_plan_intent
            intent = detect_plan_intent(recognized)
            if intent or _state.get("last_plan"):
                _run_plan_reply(recognized, last_plan=_state.get("last_plan"), feature='ai_voice')
            else:
                _run_text_reply(recognized)
        threading.Thread(target=_worker, daemon=True).start()

    def _toggle_mic(_):
        if _mic_state.get("recording"):
            _cancel_recording()
            return
        if _start_recording():
            _enter_recording_mode()

    btn_mic = ft.Container(
        content=ft.Icon(ft.Icons.MIC_NONE_ROUNDED, size=22, color=Colors.TEXT_MUTED),
        width=42, height=42,
        border_radius=Radius.LG,
        bgcolor=Colors.BG_INPUT,
        border=ft.Border.all(1, Colors.BORDER),
        alignment=ft.Alignment.CENTER,
        on_click=_toggle_mic, ink=True,
        tooltip=t("mic_hint"),
    )

    # ── Attachment menu ────────────────────────────────────────
    def _open_attach_menu(_):
        attach_bs = [None]

        def _close():
            attach_bs[0].open = False
            page.update()

        def _pick_image(_):
            _close()
            _pick(None)

        def _show_history(_):
            _close()
            toggle_history(None)

        def _pick_file(_):
            _close()
            if not allowed("ai_documents"):
                return
            def _run():
                try:
                    import tkinter as tk
                    from tkinter import filedialog
                    root = tk.Tk()
                    root.attributes("-topmost", True)
                    root.withdraw()
                    path = filedialog.askopenfilename(
                        title="Chọn file",
                        filetypes=[
                            ("Tài liệu", "*.docx;*.doc;*.xlsx;*.xls;*.pdf;*.txt;*.csv;*.md"),
                            ("Tất cả", "*.*"),
                        ],
                    )
                    root.destroy()
                except Exception:
                    path = None

                if not path:
                    return

                import os as _os
                fname = _os.path.basename(path)
                ext = fname.rsplit(".", 1)[-1].lower() if "." in fname else ""

                # Show file bubble in chat
                _add_to_chat(_bubble_file(fname, is_image=False))
                if _state["session_id"]:
                    ChatService.add_message(user.id, _state["session_id"],
                                            "user", f"[📎 File: {fname}]")
                try: page.update()
                except Exception: pass

                # ── Extract text from file ────────────────────────────────
                extracted = ""
                error_msg = ""
                try:
                    if ext in ("txt", "csv", "md", "log", "ini", "json", "xml"):
                        with open(path, "r", encoding="utf-8", errors="ignore") as f:
                            extracted = f.read(12000)

                    elif ext in ("xlsx", "xls"):
                        try:
                            import openpyxl
                            wb = openpyxl.load_workbook(path, data_only=True)
                            lines = []
                            for ws in wb.worksheets[:3]:
                                lines.append(f"=== Sheet: {ws.title} ===")
                                for row in ws.iter_rows(max_row=150, values_only=True):
                                    row_vals = [str(c) if c is not None else "" for c in row]
                                    if any(v.strip() for v in row_vals):
                                        lines.append(" | ".join(row_vals))
                            extracted = "\n".join(lines)[:10000]
                        except ImportError:
                            try:
                                import pandas as _pd
                                df = _pd.read_excel(path, nrows=150)
                                extracted = df.to_string(max_rows=150)[:10000]
                            except ImportError:
                                error_msg = "Cần cài thư viện: pip install openpyxl"

                    elif ext in ("docx", "doc"):
                        try:
                            import docx as _docx
                            doc = _docx.Document(path)
                            paras = [p.text for p in doc.paragraphs if p.text.strip()]
                            extracted = "\n".join(paras)[:10000]
                        except ImportError:
                            error_msg = "Cần cài thư viện: pip install python-docx"

                    elif ext == "pdf":
                        try:
                            import pdfplumber
                            with pdfplumber.open(path) as pdf:
                                pages_text = []
                                for pg in pdf.pages[:15]:
                                    txt = pg.extract_text() or ""
                                    if txt.strip():
                                        pages_text.append(txt)
                                extracted = "\n".join(pages_text)[:10000]
                        except ImportError:
                            try:
                                import PyPDF2
                                with open(path, "rb") as f:
                                    reader = PyPDF2.PdfReader(f)
                                    pages_text = []
                                    for pg in reader.pages[:15]:
                                        pages_text.append(pg.extract_text() or "")
                                extracted = "\n".join(pages_text)[:10000]
                            except ImportError:
                                error_msg = "Cần cài thư viện: pip install pdfplumber"

                    else:
                        # Fallback: try reading as UTF-8 text
                        try:
                            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                                extracted = f.read(8000)
                        except Exception:
                            error_msg = f"Không hỗ trợ định dạng .{ext}"

                except Exception as _fe:
                    error_msg = f"Lỗi đọc file: {str(_fe)[:80]}"

                if error_msg:
                    _add_to_chat(_bubble(f"❌ {error_msg}", is_user=False))
                    try: page.update()
                    except Exception: pass
                    return

                if not extracted.strip():
                    _add_to_chat(_bubble(
                        "⚠️ Không đọc được nội dung file — file có thể trống hoặc bị mã hóa.",
                        is_user=False))
                    try: page.update()
                    except Exception: pass
                    return

                # ── Send extracted content to AI planner ─────────────────
                analysis_msg = (
                    f"Đây là nội dung file '{fname}':\n\n"
                    f"{extracted}\n\n"
                    "Hãy phân tích nội dung trên, nhận diện các công việc/nhiệm vụ/deadline "
                    "và lập kế hoạch chi tiết với các bước thực hiện cụ thể, "
                    "sau đó đề xuất các task có thể lưu vào app."
                )
                _run_plan_reply(analysis_msg, last_plan=_state.get("last_plan"), feature='ai_documents')

            threading.Thread(target=_run, daemon=True).start()

        def _menu_opt(icon, label, subtitle, color, on_tap):
            return ft.Container(
                content=ft.Row([
                    ft.Container(
                        content=ft.Icon(icon, size=22, color=color),
                        width=46, height=46, border_radius=Radius.MD,
                        bgcolor=f"#18{color[1:]}" if color.startswith("#") else Colors.PRIMARY_BG,
                        alignment=ft.Alignment.CENTER,
                    ),
                    ft.Column([
                        ft.Text(label, size=Typography.BODY, color=Colors.TEXT_PRIMARY,
                                weight=Typography.SEMIBOLD),
                        ft.Text(subtitle, size=Typography.TINY, color=Colors.TEXT_MUTED),
                    ], spacing=1, tight=True, expand=True),
                    ft.Icon(ft.Icons.CHEVRON_RIGHT, size=16, color=Colors.TEXT_MUTED),
                ], spacing=Spacing.MD, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                padding=ft.padding.symmetric(horizontal=Spacing.LG, vertical=13),
                on_click=on_tap, ink=True, border_radius=Radius.SM,
            )

        _div_line = lambda: ft.Container(height=1, bgcolor=Colors.BORDER,
                                         margin=ft.margin.only(left=74, right=Spacing.LG))

        sheet_content = ft.Column([
            ft.Container(
                content=ft.Container(width=40, height=4, border_radius=2, bgcolor="#888888"),
                alignment=ft.Alignment.CENTER,
                padding=ft.padding.only(top=12, bottom=12),
            ),
            ft.Container(
                content=ft.Text(t("attach_title"), size=Typography.H4,
                                color=Colors.TEXT_PRIMARY, weight=Typography.BOLD,
                                text_align=ft.TextAlign.CENTER),
                alignment=ft.Alignment.CENTER,
                padding=ft.padding.only(bottom=Spacing.SM),
            ),
            ft.Container(height=1, bgcolor=Colors.BORDER,
                         margin=ft.margin.symmetric(horizontal=Spacing.LG)),
            _menu_opt(ft.Icons.DESCRIPTION_ROUNDED, t("upload_file"),
                      t("upload_file_sub"), Colors.ACCENT_CYAN, _pick_file),
            _div_line(),
            _menu_opt(ft.Icons.IMAGE_ROUNDED, t("upload_image"),
                      t("upload_image_sub"), Colors.VIOLET, _pick_image),
            _div_line(),
            _menu_opt(ft.Icons.HISTORY_ROUNDED, t("chat_history"),
                      t("chat_history_sub"), Colors.PRIMARY, _show_history),
            ft.Container(height=Spacing.XXL),
        ], spacing=0, tight=True)

        bs = ft.BottomSheet(
            content=ft.Container(
                content=sheet_content,
                bgcolor=Colors.BG_CARD,
                border_radius=ft.BorderRadius.only(top_left=Radius.XL, top_right=Radius.XL),
                padding=0,
                clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            ),
            open=True, draggable=True, use_safe_area=True,
        )
        attach_bs[0] = bs
        page.overlay.append(bs)
        page.update()

    btn_attach_menu = ft.Container(
        content=ft.Icon(ft.Icons.ADD_ROUNDED, size=20, color=Colors.TEXT_PRIMARY),
        width=42, height=42,
        border_radius=Radius.LG,
        bgcolor=Colors.BG_INPUT,
        border=ft.Border.all(1, Colors.BORDER),
        alignment=ft.Alignment.CENTER,
        on_click=_open_attach_menu, ink=True,
        tooltip=t("attach_title"),
    )

    # ── Reply logic ────────────────────────────────────────────
    def _do_refine(option: str):
        """User clicked a refine option — update the plan."""
        tf.value = ""
        _add_to_chat(_bubble(option, is_user=True))
        if _state["session_id"]:
            ChatService.add_message(user.id, _state["session_id"], "user", option)
        try:
            from core.services import BehaviorService as _BS
            _BS.log(user.id, "plan_refine", {"option": option})
        except Exception:
            pass
        _run_plan_reply(option, last_plan=_state.get("last_plan"))

    def _run_plan_reply(message: str, last_plan: dict = None, image_path: str = None, feature: str = 'ai_chat'):
        if not allowed("ai_images" if image_path else "ai_chat"):
            return
        _typing.visible = True
        try:
            page.update()
        except Exception:
            pass
        _scroll_down()

        def _worker():
            try:
                from core.ai_planner_service import get_plan_response
                lang_instr = ai_lang_instruction()
                full_msg = f"{lang_instr}\n{message}".strip() if lang_instr else message
                session = ChatService.get_session(user.id, _state['session_id']) if _state['session_id'] else None
                import json
                history = json.dumps((session or {}).get('messages', [])[-20:], ensure_ascii=False)[-20000:]
                result = get_plan_response(full_msg, user.id, last_plan=last_plan,
                                           image_path=image_path, feature=feature, history=history)
            except Exception as _exc:
                logger.exception("_run_plan_reply failed")
                result = {"type": "normal_chat",
                          "message": f"❌ Lỗi kết nối AI: {str(_exc)[:80]}"}
            finally:
                _typing.visible = False

            try:
                if result.get("type") == "plan_result":
                    _state["last_plan"] = result
                    _current_plan_data[0] = result
                    _current_plan_data[1] = _state["session_id"]  # bind to session
                    row = _plan_row(result)
                    _add_to_chat(row)
                    summary = f"[Kế hoạch] {result.get('title', '')}\n{result.get('summary', '')}"
                    if _state["session_id"]:
                        ChatService.add_message(user.id, _state["session_id"], "model", summary)

                elif result.get("type") == "task_create":
                    msg = (f"📋 Task gợi ý:\n"
                           f"**{result.get('title', '')}**\n"
                           f"Ưu tiên: {result.get('priority', 'medium')} | "
                           f"Hạn: {result.get('due_date') or 'chưa đặt'}")
                    _add_to_chat(_bubble(msg, is_user=False))
                    result = dict(result)
                    result.setdefault('start_at', None)
                    task_plan = {'type': 'plan_result', 'title': 'Công việc đề xuất',
                                 'ready_to_save': result.get('ready_to_save') is True,
                                 'suggested_tasks': [result], 'missing_information': result.get('missing_information') or [],
                                 'follow_up_question': result.get('follow_up_question', '')}
                    _state['last_plan'] = task_plan
                    _add_to_chat(_plan_row(task_plan))
                    if _state["session_id"]:
                        ChatService.add_message(user.id, _state["session_id"], "model", msg)

                else:
                    msg = result.get("message", "Mình sẽ hỗ trợ bạn lập kế hoạch và quản lý task.")
                    _add_to_chat(_bubble(msg, is_user=False))
                    if _state["session_id"]:
                        ChatService.add_message(user.id, _state["session_id"], "model", msg)

                _load_sessions_ui()
            except Exception:
                logger.exception("_run_plan_reply render failed")
            try:
                page.update()
            except Exception:
                pass

        threading.Thread(target=_worker, daemon=True).start()

    def _run_text_reply(message: str, image_path: str = None):
        if not allowed("ai_images" if image_path else "ai_chat"):
            return
        _typing.visible = True
        try:
            page.update()
        except Exception:
            pass
        _scroll_down()

        def _worker():
            reply = ""
            try:
                from utils.ai_helper import get_ai_reply, extract_task_from_reply
                lang_instr = ai_lang_instruction()
                full_msg = f"{lang_instr}\n{message}".strip() if lang_instr else message
                reply = get_ai_reply(user.settings, full_msg, user.id,
                                     _state["session_id"], image_path)
            except Exception as _exc:
                logger.exception("_run_text_reply get_ai_reply failed")
                reply = f"❌ Không thể kết nối AI: {str(_exc)[:80]}"
            finally:
                _typing.visible = False

            try:
                _add_to_chat(_bubble(reply, is_user=False))
                if _state["session_id"]:
                    ChatService.add_message(user.id, _state["session_id"], "model", reply)

                # Check for inline task suggestion
                try:
                    from utils.ai_helper import extract_task_from_reply as _etr
                    task_data = _etr(reply, user.id)
                    if task_data:
                        _show_inline_task_btn(task_data)
                except Exception:
                    logger.exception("extract_task_from_reply failed")

                _load_sessions_ui()
            except Exception:
                logger.exception("_run_text_reply render failed")
            try:
                page.update()
            except Exception:
                pass

        threading.Thread(target=_worker, daemon=True).start()

    def _send(_, image_path=None):
        if not allowed("ai_images" if image_path else "ai_chat"):
            return
        text = tf.value.strip()
        if not text and not image_path:
            return
        tf.value = ""
        if text and not image_path:
            _add_to_chat(_bubble(text, is_user=True))
            if _state["session_id"]:
                ChatService.add_message(user.id, _state["session_id"], "user", text)
            # Log behavior + extract memory in background
            def _bg_process(msg=text, uid=user.id):
                try:
                    from core.services import BehaviorService as _BS
                    from core.ai_planner_service import detect_plan_intent as _dpi
                    _BS.log(uid, "chat_sent", {
                        "length": len(msg),
                        "has_plan_intent": bool(_dpi(msg)),
                    })
                    from utils.ai_helper import extract_memory_from_user_message
                    extract_memory_from_user_message(uid, msg)
                except Exception:
                    pass
            threading.Thread(target=_bg_process, daemon=True).start()
        elif image_path:
            if _state["session_id"]:
                ChatService.add_message(user.id, _state["session_id"], "user",
                                        f"[Đã gửi hình ảnh] {text}")
        _load_sessions_ui()
        page.update()

        # One structured conversation handles drafts, clarification and final plans.
        _run_plan_reply(text, last_plan=_state.get("last_plan"), image_path=image_path)

    # ── Inline task creation button ─────────────────────────────
    def _show_inline_task_btn(task_data: dict):
        from core.models import Task as _Task
        from core.services import TaskService as _TS

        def _do_create(_):
            try:
                now_str = datetime.now().isoformat()
                new_t = _Task(
                    id=str(uuid.uuid4()),
                    user_id=user.id,
                    title=task_data.get("title", "Task mới"),
                    description=task_data.get("description", ""),
                    category=task_data.get("category", "personal"),
                    priority=task_data.get("priority", "medium"),
                    status="todo",
                    due_date=task_data.get("due_date"),
                    due_time=task_data.get("due_time"),
                    estimated_minutes=int(task_data.get("estimated_minutes") or 30),
                    reminder_minutes=int(task_data.get("reminder_minutes") or 0),
                    created_at=now_str,
                    updated_at=now_str,
                )
                _TS.save_task(new_t)
                _notify_task_list()
                snack(page, t("task_created", title=new_t.title))
                if btn_row in chat_lv.controls:
                    chat_lv.controls.remove(btn_row)
                page.update()
            except Exception:
                logger.exception("Inline task creation failed")
                snack(page, "Không tạo được công việc. Vui lòng thử lại.")

        btn_row = ft.Row([
            ft.Container(expand=True),
            ft.Container(
                content=ft.Row([
                    ft.Icon(ft.Icons.ADD_TASK_ROUNDED, size=13, color="white"),
                    ft.Text(t("create_short", title=task_data.get("title", "")[:28]),
                            size=Typography.TINY, color="white",
                            weight=Typography.SEMIBOLD),
                ], spacing=5, tight=True),
                padding=ft.padding.symmetric(horizontal=12, vertical=7),
                border_radius=Radius.FULL,
                gradient=ft.LinearGradient(
                    colors=["#A855F7", "#3B82F6"],
                    begin=ft.Alignment.CENTER_LEFT,
                    end=ft.Alignment.CENTER_RIGHT,
                ),
                on_click=_do_create, ink=True,
                shadow=ft.BoxShadow(blur_radius=8, color="#40A855F7",
                                    offset=ft.Offset(0, 2)),
            ),
        ], spacing=0)
        _add_to_chat(btn_row)

    # ── Task create confirm sheet ───────────────────────────────
    def _show_task_create_confirm(data: dict):
        from core.models import Task as _Task
        from core.services import TaskService as _TS

        tf_title = ft.TextField(
            value=data.get("title", ""),
            label=t("title_label"),
            bgcolor=Colors.BG_SURFACE, border_color=Colors.BORDER,
            focused_border_color=Colors.PRIMARY,
            text_style=ft.TextStyle(color=Colors.TEXT_PRIMARY, size=Typography.SMALL),
            label_style=ft.TextStyle(color=Colors.TEXT_MUTED, size=Typography.TINY),
            border_radius=Radius.MD, cursor_color=Colors.PRIMARY,
            content_padding=ft.padding.symmetric(horizontal=12, vertical=10),
        )
        tf_due = ft.TextField(
            value=data.get("due_date") or "",
            label=t("due_date_label"),
            bgcolor=Colors.BG_SURFACE, border_color=Colors.BORDER,
            focused_border_color=Colors.PRIMARY,
            text_style=ft.TextStyle(color=Colors.TEXT_PRIMARY, size=Typography.SMALL),
            label_style=ft.TextStyle(color=Colors.TEXT_MUTED, size=Typography.TINY),
            border_radius=Radius.MD, cursor_color=Colors.PRIMARY,
            content_padding=ft.padding.symmetric(horizontal=12, vertical=10),
            expand=True,
        )
        tf_time = ft.TextField(
            value=data.get("due_time") or "",
            label=t("due_time_label"),
            bgcolor=Colors.BG_SURFACE, border_color=Colors.BORDER,
            focused_border_color=Colors.PRIMARY,
            text_style=ft.TextStyle(color=Colors.TEXT_PRIMARY, size=Typography.SMALL),
            label_style=ft.TextStyle(color=Colors.TEXT_MUTED, size=Typography.TINY),
            border_radius=Radius.MD, cursor_color=Colors.PRIMARY,
            content_padding=ft.padding.symmetric(horizontal=12, vertical=10),
            expand=True,
        )

        def _save(_):
            title = tf_title.value.strip()
            if not title:
                snack(page, t("title_required"))
                return
            now_str = datetime.now().isoformat()
            new_t = _Task(
                id=str(uuid.uuid4()),
                user_id=user.id,
                title=title,
                description=data.get("description", ""),
                category=data.get("category", "personal"),
                priority=data.get("priority", "medium"),
                status="todo",
                due_date=tf_due.value.strip() or None,
                due_time=tf_time.value.strip() or None,
                estimated_minutes=int(data.get("estimated_minutes") or 30),
                reminder_minutes=int(data.get("reminder_minutes") or 0),
                created_at=now_str,
                updated_at=now_str,
            )
            _TS.save_task(new_t)
            bs[0].open = False
            page.update()
            snack(page, t("task_created", title=title))

        def _cancel(_):
            bs[0].open = False
            page.update()

        sheet = ft.Column([
            ft.Container(
                content=ft.Container(width=40, height=4, border_radius=Radius.FULL,
                                     bgcolor="#444444"),
                alignment=ft.Alignment.CENTER,
                padding=ft.padding.only(top=12, bottom=8),
            ),
            ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.Icon(ft.Icons.ADD_TASK_ROUNDED, size=18, color=Colors.PRIMARY),
                        ft.Text(t("confirm_create_task"), size=Typography.H3,
                                color=Colors.TEXT_PRIMARY, weight=Typography.BOLD),
                    ], spacing=Spacing.SM),
                    ft.Container(height=Spacing.SM),
                    tf_title,
                    ft.Container(height=Spacing.XS),
                    ft.Row([tf_due, ft.Container(width=8), tf_time]),
                    ft.Container(height=Spacing.MD),
                    ft.Row([
                        ft.Container(
                            content=ft.Text(t("cancel"), size=Typography.BODY,
                                            color=Colors.TEXT_MUTED),
                            height=44, expand=True, border_radius=Radius.MD,
                            bgcolor=Colors.BG_SURFACE,
                            border=ft.Border.all(1, Colors.BORDER),
                            alignment=ft.Alignment.CENTER,
                            on_click=_cancel, ink=True,
                        ),
                        ft.Container(width=8),
                        ft.Container(
                            content=ft.Row([
                                ft.Icon(ft.Icons.CHECK_ROUNDED, size=16, color="white"),
                                ft.Text(t("save_task_btn"), size=Typography.BODY, color="white",
                                        weight=Typography.SEMIBOLD),
                            ], alignment=ft.MainAxisAlignment.CENTER, spacing=4),
                            height=44, expand=True, border_radius=Radius.MD,
                            bgcolor=Colors.PRIMARY,
                            alignment=ft.Alignment.CENTER,
                            on_click=_save, ink=True,
                        ),
                    ]),
                    ft.Container(height=Spacing.XL),
                ], spacing=0, tight=True),
                padding=ft.padding.symmetric(horizontal=Spacing.LG),
            ),
        ], spacing=0, tight=True)

        cbs = ft.BottomSheet(
            content=ft.Container(
                content=sheet, bgcolor=Colors.BG_CARD,
                border_radius=ft.BorderRadius.only(top_left=Radius.XL, top_right=Radius.XL),
                padding=0, clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            ),
            open=True, draggable=True, use_safe_area=True,
        )
        bs = [cbs]
        page.overlay.append(cbs)
        page.update()

    # ── Send button ────────────────────────────────────────────
    send_btn = ft.Container(
        content=ft.Icon(ft.Icons.SEND_ROUNDED, color="white", size=20),
        width=46, height=46,
        border_radius=Radius.LG,
        gradient=ft.LinearGradient(
            colors=[Colors.PRIMARY_LIGHT, Colors.PRIMARY],
            begin=ft.Alignment.TOP_LEFT,
            end=ft.Alignment.BOTTOM_RIGHT,
        ),
        alignment=ft.Alignment.CENTER,
        on_click=_send, ink=True,
        shadow=ft.BoxShadow(blur_radius=12, color=Colors.PRIMARY_SHADOW,
                            offset=ft.Offset(0, 3)),
    )

    # ── Priority task card (real DB tasks, clickable) ─────────
    def _render_priority_card() -> ft.Row:
        """Fetch active tasks, sort by urgency/priority, render as clickable cards."""
        try:
            all_t = TaskService.get_tasks(user.id)
        except Exception:
            all_t = []

        active = [tk for tk in all_t if tk.status not in ("done", "cancelled")]
        pri_order = {"high": 0, "medium": 1, "low": 2}
        sorted_t = sorted(active, key=lambda tk: (
            0 if tk.is_overdue else 1,
            -getattr(tk, "ai_priority_score", 50),
            pri_order.get(tk.priority, 1),
            tk.due_date or "9999",
        ))[:7]

        ai_avatar = ft.Container(
            content=ft.Image(src="ink-cat.png", fit="cover"),
            width=44, height=44, border_radius=0,
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        )

        pri_color_map = {"high": Colors.ERROR, "medium": Colors.WARNING, "low": Colors.SUCCESS}

        def _task_row(tk, rank: int) -> ft.GestureDetector:
            pri_c  = pri_color_map.get(tk.priority, Colors.TEXT_MUTED)
            overdue = tk.is_overdue
            days   = tk.days_until_due

            if days is None:
                date_txt, date_c = "Chưa đặt deadline", Colors.TEXT_MUTED
            elif days < 0:
                date_txt, date_c = f"Quá hạn {abs(days)}n", Colors.ERROR
            elif days == 0:
                date_txt, date_c = "Hạn hôm nay", Colors.WARNING
            elif days == 1:
                date_txt, date_c = "Hạn ngày mai", Colors.WARNING
            else:
                date_txt, date_c = f"Còn {days} ngày", Colors.TEXT_MUTED

            est = getattr(tk, "estimated_minutes", 30)
            cat_info = {"work": "💼", "personal": "👤", "health": "💪",
                        "finance": "💰", "education": "📚"}.get(tk.category, "📌")

            return ft.GestureDetector(
                on_tap=lambda _, task=tk: on_navigate("task_edit", task=task),
                content=ft.Container(
                    content=ft.Row([
                        # Rank badge
                        ft.Container(
                            content=ft.Text(
                                str(rank), size=8, color="white",
                                weight=Typography.BOLD,
                                text_align=ft.TextAlign.CENTER,
                            ),
                            width=20, height=20, border_radius=10,
                            bgcolor=Colors.ERROR if overdue else Colors.PRIMARY,
                            alignment=ft.Alignment.CENTER,
                        ),
                        # Info
                        ft.Column([
                            ft.Text(
                                tk.title, size=Typography.SMALL,
                                color=Colors.TEXT_PRIMARY, weight=Typography.SEMIBOLD,
                                max_lines=1, overflow=ft.TextOverflow.ELLIPSIS,
                            ),
                            ft.Row([
                                ft.Text(cat_info, size=10),
                                ft.Text(date_txt, size=Typography.TINY,
                                        color=date_c,
                                        weight=Typography.SEMIBOLD if days is not None and days <= 0
                                               else Typography.REGULAR),
                                ft.Text("·", size=Typography.TINY, color=Colors.TEXT_MUTED),
                                ft.Container(width=6, height=6, border_radius=3, bgcolor=pri_c),
                                ft.Text(f"{est}p", size=Typography.TINY, color=Colors.TEXT_MUTED),
                            ], spacing=4, tight=True,
                               vertical_alignment=ft.CrossAxisAlignment.CENTER),
                        ], spacing=2, tight=True, expand=True),
                        ft.Icon(ft.Icons.CHEVRON_RIGHT_ROUNDED, size=15, color=Colors.TEXT_MUTED),
                    ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    padding=ft.padding.symmetric(vertical=8, horizontal=10),
                    border_radius=Radius.MD,
                    bgcolor=f"#12{Colors.ERROR[1:]}" if overdue else Colors.BG_SURFACE,
                    border=ft.Border.all(
                        1, f"#35{Colors.ERROR[1:]}" if overdue else Colors.BORDER),
                    margin=ft.margin.only(bottom=4),
                    ink=True,
                    animate=ft.Animation(150, ft.AnimationCurve.EASE_OUT),
                ),
            )

        if not sorted_t:
            card_content = ft.Container(
                content=ft.Text("🎉 Không có task nào — rảnh thôi!",
                                size=Typography.BODY, color=Colors.SUCCESS),
                padding=ft.padding.all(14),
            )
        else:
            rows = [_task_row(tk, i + 1) for i, tk in enumerate(sorted_t)]
            see_all_btn = ft.Container(
                content=ft.Row([
                    ft.Icon(ft.Icons.CHECKLIST_ROUNDED, size=13, color=Colors.PRIMARY),
                    ft.Text("Xem tất cả task", size=Typography.TINY,
                            color=Colors.PRIMARY, weight=Typography.SEMIBOLD),
                ], spacing=6, alignment=ft.MainAxisAlignment.CENTER),
                height=34, border_radius=Radius.MD,
                bgcolor=Colors.PRIMARY_BG,
                border=ft.Border.all(1, Colors.PRIMARY_BORDER),
                alignment=ft.Alignment.CENTER,
                on_click=lambda _: on_navigate("tasks"), ink=True,
                margin=ft.margin.only(top=4),
            )
            card_content = ft.Column(
                [
                    ft.Row([
                        ft.Icon(ft.Icons.AUTO_AWESOME_ROUNDED, size=13, color=Colors.PRIMARY),
                        ft.Text("Task ưu tiên cao nhất", size=Typography.SMALL,
                                color=Colors.TEXT_PRIMARY, weight=Typography.BOLD,
                                expand=True),
                        ft.Text(f"{len(sorted_t)} task", size=Typography.TINY,
                                color=Colors.TEXT_MUTED),
                    ], spacing=6, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    ft.Container(height=8),
                    *rows,
                    see_all_btn,
                ],
                spacing=0, tight=True,
            )

        card = ft.Container(
            content=card_content,
            padding=ft.padding.all(12),
            border_radius=ft.BorderRadius(4, 16, 16, 16),
            bgcolor=Colors.BG_CARD,
            border=ft.Border.all(1, Colors.PRIMARY_BORDER),
            shadow=ft.BoxShadow(blur_radius=10, color=Colors.PRIMARY_SHADOW,
                                offset=ft.Offset(0, 2)),
        )

        return ft.Row(
            [ai_avatar,
             ft.Column([card], expand=True,
                       horizontal_alignment=ft.CrossAxisAlignment.START)],
            spacing=Spacing.SM, vertical_alignment=ft.CrossAxisAlignment.START,
        )

    def _run_priority_reply(prompt: str):
        if not allowed("ai_chat"):
            return
        """Show real priority task card + brief AI note."""
        _typing.visible = True
        try: page.update()
        except Exception: pass
        _scroll_down()

        def _worker():
            try:
                # 1. Show real task card + bind to current session
                card_row = _render_priority_card()
                _current_priority_shown[0] = True
                _current_priority_shown[1] = _state["session_id"]
                _add_to_chat(card_row)

                # 2. Get a short AI recommendation
                from utils.ai_helper import get_ai_reply
                lang_instr = ai_lang_instruction()
                brief = (
                    f"{lang_instr}\n"
                    "Dựa vào danh sách task vừa hiển thị, hãy đưa ra lời khuyên ngắn "
                    "(2-3 câu) về thứ tự ưu tiên và lý do."
                ).strip()
                reply = get_ai_reply(user.settings, brief, user.id, _state["session_id"])
                _add_to_chat(_bubble(reply, is_user=False))
                if _state["session_id"]:
                    ChatService.add_message(user.id, _state["session_id"], "model", reply)
            except Exception as _exc:
                logger.exception("_run_priority_reply failed")
                _add_to_chat(_bubble(f"❌ Lỗi: {str(_exc)[:80]}", is_user=False))
            finally:
                _typing.visible = False
                _load_sessions_ui()
                try: page.update()
                except Exception: pass

        threading.Thread(target=_worker, daemon=True).start()

    # ── Quick prompt chips ─────────────────────────────────────
    def _chip(emoji: str, label: str, prompt: str, reply_fn=None):
        def _tap(_):
            _add_to_chat(_bubble(prompt, is_user=True))
            if _state["session_id"]:
                ChatService.add_message(user.id, _state["session_id"], "user", prompt)
            try:
                from core.services import BehaviorService as _BS
                _BS.log(user.id, "chat_sent", {"length": len(prompt), "via": "chip"})
            except Exception:
                pass
            _load_sessions_ui()
            try: page.update()
            except Exception: pass
            if reply_fn:
                reply_fn(prompt)
            else:
                _run_plan_reply(prompt, last_plan=None)
        return ft.GestureDetector(
            content=ft.Container(
                content=ft.Row([
                    ft.Text(emoji, size=12),
                    ft.Text(label, size=Typography.TINY, color=Colors.TEXT_SECONDARY),
                ], spacing=4, tight=True),
                padding=ft.Padding.symmetric(horizontal=10, vertical=6),
                border_radius=Radius.FULL,
                border=ft.Border.all(1, Colors.BORDER),
                bgcolor=Colors.BG_SURFACE,
            ),
            on_tap=_tap,
        )

    chips_row = ft.Row(
        [
            _chip(e, l, p,
                  reply_fn=_run_priority_reply if i == 2 else None)
            for i, (e, l, p) in enumerate(_get_quick_prompts())
        ],
        scroll=ft.ScrollMode.AUTO, spacing=Spacing.SM,
    )

    # ── History panel ──────────────────────────────────────────
    _history_state = {"open": False}

    def toggle_history(e):
        _history_state["open"] = not _history_state["open"]
        if _history_state["open"]:
            history_panel.width = 260
            history_panel.padding = 0
        else:
            history_panel.width = 0
            history_panel.padding = 0
        page.update()

    def _start_new_chat(_):
        _state["session_id"] = ChatService.create_session(user.id, "Chat mới")
        _state["last_plan"] = None
        _load_active_session()  # session_id mismatch sẽ tự hide card cũ
        if _history_state["open"]:
            toggle_history(None)

    history_lv = ft.ListView(
        expand=True, spacing=0, controls=[],
        padding=ft.padding.symmetric(horizontal=8, vertical=8),
    )

    history_panel_header = ft.Container(
        content=ft.Row([
            ft.Icon(ft.Icons.HISTORY_ROUNDED, size=16, color=Colors.PRIMARY),
            ft.Text(t("history"), size=Typography.BODY, color=Colors.TEXT_PRIMARY,
                    weight=Typography.BOLD, expand=True),
            ft.Container(
                content=ft.Icon(ft.Icons.EDIT_OUTLINED, size=15, color=Colors.TEXT_MUTED),
                width=30, height=30, border_radius=Radius.MD,
                bgcolor=Colors.BG_SURFACE, alignment=ft.Alignment.CENTER,
                on_click=_start_new_chat, ink=True, tooltip=t("new_chat"),
            ),
            ft.Container(width=4),
            ft.Container(
                content=ft.Icon(ft.Icons.CLOSE_ROUNDED, size=15, color=Colors.TEXT_MUTED),
                width=30, height=30, border_radius=Radius.MD,
                bgcolor=Colors.BG_SURFACE, alignment=ft.Alignment.CENTER,
                on_click=toggle_history, ink=True,
            ),
        ], spacing=6, vertical_alignment=ft.CrossAxisAlignment.CENTER),
        padding=ft.padding.symmetric(horizontal=12, vertical=10),
        border=ft.Border(bottom=ft.BorderSide(1, Colors.BORDER)),
    )

    history_panel = ft.Container(
        content=ft.Column([
            history_panel_header,
            history_lv,
        ], spacing=0, tight=True, expand=True),
        width=0, bgcolor=Colors.BG_DARK, padding=0,
        border=ft.Border(left=ft.BorderSide(1, Colors.BORDER)),
        animate=ft.Animation(250, ft.AnimationCurve.EASE_OUT_CUBIC),
        clip_behavior=ft.ClipBehavior.HARD_EDGE,
    )

    def _load_sessions_ui():
        from datetime import datetime as _dt, timedelta as _td
        sessions = ChatService.get_sessions(user.id)

        today     = _dt.now().date()
        yesterday = today - _td(days=1)
        week_ago  = today - _td(days=7)

        g_keys = [t("today"), t("yesterday"), t("last_7_days"), t("older")]
        groups = {k: [] for k in g_keys}
        for s in sessions:
            try:
                d = _dt.fromisoformat(s.get("created_at", "")).date()
            except Exception:
                d = today
            if d == today:
                groups[g_keys[0]].append(s)
            elif d == yesterday:
                groups[g_keys[1]].append(s)
            elif d >= week_ago:
                groups[g_keys[2]].append(s)
            else:
                groups[g_keys[3]].append(s)

        def make_select(sid):
            return lambda e: _switch_session(sid)

        def make_delete(sid):
            return lambda e: _delete_session(sid)

        controls = []
        for group_name, group_sessions in groups.items():
            if not group_sessions:
                continue
            controls.append(ft.Container(
                content=ft.Text(group_name, size=9, color=Colors.TEXT_MUTED,
                                weight=Typography.SEMIBOLD),
                padding=ft.padding.only(left=6, top=8, bottom=2),
            ))
            for s in group_sessions:
                is_active = (s["id"] == _state["session_id"])
                item = ft.Container(
                    content=ft.Row([
                        ft.Icon(
                            ft.Icons.CHAT_BUBBLE_ROUNDED if is_active
                            else ft.Icons.CHAT_BUBBLE_OUTLINE_ROUNDED,
                            size=13,
                            color=Colors.PRIMARY if is_active else Colors.TEXT_MUTED,
                        ),
                        ft.Text(
                            s.get("title", "Chat"),
                            expand=True,
                            color=Colors.TEXT_PRIMARY if is_active else Colors.TEXT_SECONDARY,
                            size=Typography.TINY,
                            no_wrap=True,
                            overflow=ft.TextOverflow.ELLIPSIS,
                            max_lines=1,
                        ),
                        ft.GestureDetector(
                            on_tap=make_delete(s["id"]),
                            content=ft.Container(
                                content=ft.Icon(ft.Icons.CLOSE_ROUNDED, size=11,
                                                color=Colors.TEXT_MUTED),
                                width=20, height=20, border_radius=Radius.SM,
                                alignment=ft.Alignment.CENTER,
                            ),
                        ),
                    ], spacing=6, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    padding=ft.padding.symmetric(horizontal=8, vertical=7),
                    border_radius=Radius.MD,
                    bgcolor=Colors.PRIMARY_BG if is_active else "transparent",
                    border=ft.Border.all(1, Colors.PRIMARY_BORDER) if is_active else None,
                    on_click=make_select(s["id"]),
                    ink=True,
                    margin=ft.margin.only(bottom=2),
                )
                controls.append(item)

        if sessions:
            controls.append(ft.Container(
                content=ft.Container(height=1, bgcolor=Colors.BORDER),
                padding=ft.padding.only(top=10, bottom=2),
            ))
            controls.append(ft.Container(
                content=ft.Row([
                    ft.Icon(ft.Icons.DELETE_SWEEP_ROUNDED, size=13, color=Colors.ERROR),
                    ft.Text(t("delete_all"), size=Typography.TINY, color=Colors.ERROR),
                ], spacing=6),
                padding=ft.padding.symmetric(horizontal=8, vertical=7),
                border_radius=Radius.MD,
                bgcolor=f"#10{Colors.ERROR[1:]}",
                on_click=lambda _: _clear_all_sessions(),
                ink=True,
            ))

        history_lv.controls = controls
        try:
            page.update()
        except Exception:
            pass

    def _switch_session(sid):
        _state["session_id"] = sid
        _state["last_plan"] = None
        _load_active_session()  # session_id check tự lọc card đúng session
        if _history_state["open"]:
            toggle_history(None)

    def _confirm_history_delete(action, title):
        def cancel(_):
            dialog.open = False
            page.update()
        def confirm(_):
            try:
                action()
                dialog.open = False
            except Exception:
                dialog.content = ft.Text("Không xóa được lịch sử. Hãy thử lại.")
            page.update()
        dialog = ft.AlertDialog(title=ft.Text(title),
            content=ft.Text("Lịch sử này sẽ bị xóa khỏi ứng dụng. Bạn có thể sao lưu trước trong mục Dữ liệu."),
            actions=[ft.TextButton("Hủy", on_click=cancel), ft.TextButton("Xóa", on_click=confirm)])
        page.overlay.append(dialog)
        dialog.open = True
        page.update()

    def _delete_session(sid):
        _confirm_history_delete(lambda: _perform_delete_session(sid), "Xóa cuộc trò chuyện?")

    def _perform_delete_session(sid):
        ChatService.delete_session(user.id, sid)
        if _state["session_id"] == sid:
            _state["session_id"] = None
            _load_active_session()
        else:
            _load_sessions_ui()

    def _clear_all_sessions():
        _confirm_history_delete(_perform_clear_all_sessions, "Xóa tất cả lịch sử chat?")

    def _perform_clear_all_sessions():
        ChatService.clear_all(user.id)
        _state["session_id"] = None
        _state["last_plan"] = None
        _current_plan_data[0] = None;     _current_plan_data[1] = None
        _current_priority_shown[0] = False; _current_priority_shown[1] = None
        _load_active_session()

    def _load_active_session():
        chat_lv.controls.clear()
        sessions = ChatService.get_sessions(user.id)
        if not _state["session_id"]:
            if sessions:
                _state["session_id"] = sessions[0]["id"]
            else:
                _state["session_id"] = ChatService.create_session(user.id, "Chat mới")
        session = ChatService.get_session(user.id, _state["session_id"])
        if not session:
            _state["session_id"] = ChatService.create_session(user.id, "Chat mới")
            session = ChatService.get_session(user.id, _state["session_id"])

        history = session.get("messages", [])
        if not history:
            name = user.full_name or user.username

            # Top 3 công việc quan trọng nhất
            pri_order = {"high": 0, "medium": 1, "low": 2}
            active_tasks = [tk for tk in tasks if tk.status not in ("done", "cancelled")]
            top3 = sorted(active_tasks, key=lambda tk: (
                0 if tk.is_overdue else 1,
                -getattr(tk, "ai_priority_score", 50),
                pri_order.get(tk.priority, 1),
                tk.due_date or "9999",
            ))[:3]

            if top3:
                task_lines = []
                for tk in top3:
                    days = tk.days_until_due
                    if days is None:
                        suffix = ""
                    elif days < 0:
                        suffix = f" ⚠️ quá hạn {abs(days)}n"
                    elif days == 0:
                        suffix = " 🔔 hạn hôm nay"
                    elif days == 1:
                        suffix = " · hạn ngày mai"
                    else:
                        suffix = f" · còn {days} ngày"
                    pri_icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(tk.priority, "⚪")
                    task_lines.append(f"• {pri_icon} **{tk.title}**{suffix}")
                tasks_section = "\n".join(task_lines)
                welcome_text = (
                    f"Xin chào **{name}**! 👋\n\n"
                    f"Tôi là **Doumar** — trợ lý AI lập kế hoạch của bạn.\n"
                    f"Hiện bạn có {total} công việc · ✅ {done} xong ({pct}%) · 📋 {pending} chờ\n\n"
                    f"Công việc cần làm:\n"
                    f"{tasks_section}"
                )
            else:
                welcome_text = (
                    f"Xin chào **{name}**! 👋\n\n"
                    f"Tôi là **Doumar** — trợ lý AI lập kế hoạch của bạn.\n"
                    f"Hiện bạn có {total} công việc · ✅ {done} xong ({pct}%) · 📋 {pending} chờ\n\n"
                    f"🎉 Tuyệt vời — không có công việc nào cần làm ngay!"
                )

            if compact:
                welcome_text = "Tôi có thể giúp bạn tạo công việc, sắp xếp kế hoạch hoặc xem lại tiến độ. Bạn muốn bắt đầu từ đâu?"
            chat_lv.controls.append(_bubble(welcome_text, is_user=False, animate=False))
            ChatService.add_message(user.id, _state["session_id"], "model", welcome_text)
        else:
            for msg in history:
                chat_lv.controls.append(
                    _bubble(msg["text"], is_user=(msg["role"] == "user"), animate=False)
                )

        # Re-render plan card only if it belongs to this session
        if (_current_plan_data[0] and
                _current_plan_data[1] == _state["session_id"]):
            chat_lv.controls.append(_plan_row(_current_plan_data[0]))

        # Re-render priority card only if it belongs to this session
        if (_current_priority_shown[0] and
                _current_priority_shown[1] == _state["session_id"]):
            chat_lv.controls.append(_render_priority_card())

        chat_lv.controls.append(_typing)
        if compact:
            monochrome(chat_lv)
        _load_sessions_ui()
        try:
            page.update()
            _scroll_down()
        except Exception:
            pass

    # ── AI mode banner (no API key) ────────────────────────────
    import os as _os
    from core.cloud import CloudClient
    _has_api_key = CloudClient(user.id).configured or bool(_os.environ.get("GEMINI_API_KEY", "").strip())
    ai_mode_banner = ft.Container(
        content=ft.Row([
            ft.Text("🤖", size=12),
            ft.Text(t("ai_connection_status"),
                    size=Typography.TINY, color="#92400E", expand=True),
        ], spacing=6, vertical_alignment=ft.CrossAxisAlignment.CENTER),
        padding=ft.Padding.symmetric(horizontal=Spacing.MD, vertical=6),
        bgcolor="#FEF3C7",
        border=ft.Border(bottom=ft.BorderSide(1, "#FDE68A")),
        visible=not _has_api_key,
    )

    # ── Header ─────────────────────────────────────────────────
    header = ft.Container(
        content=ft.Row([
            ft.Container(
                content=ft.Image(src="ink-cat.png", fit="cover"),
                width=44, height=44, border_radius=22,
                clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                shadow=ft.BoxShadow(blur_radius=10, color=Colors.PRIMARY_SHADOW,
                                    offset=ft.Offset(0, 3)),
            ),
            ft.Column([
                ft.Text("Doumar", size=Typography.H3,
                        color=Colors.TEXT_PRIMARY, weight=Typography.BOLD),
                ft.Row([
                    ft.Container(width=7, height=7, border_radius=4,
                                 bgcolor=Colors.SUCCESS if _has_api_key else Colors.TEXT_MUTED),
                    ft.Text(t("ai_ready") if _has_api_key else t("ai_unconfigured"), size=Typography.TINY,
                            color=Colors.SUCCESS if _has_api_key else Colors.TEXT_MUTED),
                ], spacing=4, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ], spacing=2, tight=True),
            ft.Container(expand=True),
            ft.IconButton(
                icon=ft.Icons.ADD_COMMENT_ROUNDED,
                icon_color=Colors.TEXT_MUTED,
                tooltip="Chat mới",
                on_click=_start_new_chat,
            ),
            ft.Container(
                content=ft.Text("AI", size=Typography.TINY, color="white",
                                weight=Typography.BOLD),
                padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                border_radius=Radius.FULL,
                gradient=ft.LinearGradient(
                    colors=[Colors.PRIMARY_LIGHT, Colors.PRIMARY],
                    begin=ft.Alignment.CENTER_LEFT,
                    end=ft.Alignment.CENTER_RIGHT,
                ),
            ),
        ], spacing=Spacing.SM, vertical_alignment=ft.CrossAxisAlignment.CENTER),
        padding=ft.Padding.symmetric(horizontal=Spacing.MD, vertical=Spacing.MD),
        border=ft.Border(bottom=ft.BorderSide(1, Colors.BORDER)),
        bgcolor=Colors.BG_DARKEST,
        shadow=ft.BoxShadow(blur_radius=8, color="#00000012", offset=ft.Offset(0, 2)),
    )

    # ── Normal input row (defined here so all widgets exist) ──────
    _normal_input_row = ft.Row(
        [btn_attach_menu, btn_mic, tf, send_btn], spacing=Spacing.SM
    )

    # ── Assemble ───────────────────────────────────────────────
    main_chat = ft.Column([
        header,
        ai_mode_banner,
        chat_lv,
        ft.Container(
            content=chips_row,
            padding=ft.Padding.symmetric(horizontal=Spacing.MD, vertical=Spacing.XS),
            border=ft.Border(top=ft.BorderSide(1, Colors.BORDER)),
        ),
        ft.Container(
            ref=input_area_ref,
            content=_normal_input_row,
            padding=ft.Padding.symmetric(horizontal=Spacing.MD, vertical=Spacing.SM),
            bgcolor=Colors.BG_DARKEST,
        ),
    ], spacing=0, tight=True, expand=True)

    _load_active_session()

    # ── Auto-send pending prompt (từ dashboard / tasks screen) ──
    if _pending_prompt[0]:
        _auto_msg = _pending_prompt[0]
        _pending_prompt[0] = None          # consume ngay để không lặp lại

        def _auto_send():
            import time as _t
            _t.sleep(0.3)                  # đợi UI render xong
            _add_to_chat(_bubble(_auto_msg, is_user=True))
            if _state["session_id"]:
                ChatService.add_message(user.id, _state["session_id"], "user", _auto_msg)
            _load_sessions_ui()
            try: page.update()
            except Exception: pass
            from core.ai_planner_service import detect_plan_intent
            if detect_plan_intent(_auto_msg):
                _run_plan_reply(_auto_msg, last_plan=None)
            else:
                _run_text_reply(_auto_msg)

        threading.Thread(target=_auto_send, daemon=True).start()

    if compact:
        header.content = ft.Row([
            ft.Text("Trò chuyện với AI", size=16, weight=Typography.SEMIBOLD,
                    color=Colors.TEXT_PRIMARY, expand=True),
            ft.IconButton(icon=ft.Icons.ADD_COMMENT_OUTLINED, tooltip="Chat mới", on_click=_start_new_chat),
            ft.IconButton(icon=ft.Icons.CLOSE, tooltip="Đóng chat", on_click=lambda e: on_close() if on_close else None),
        ])
        header.shadow = None
        chips_row.visible = False
        main_chat.controls.remove(main_chat.controls[3])
        tf.border_radius = 6
        tf.hint_text = "Nhắn tin…"
        send_btn.gradient = None
        send_btn.shadow = None
        send_btn.bgcolor = Colors.BG_CARD
        send_btn.border = ft.Border.all(1, Colors.BORDER)
        send_btn.border_radius = 6
        send_btn.tooltip = "Gửi tin nhắn"
        send_btn.content.color = Colors.TEXT_PRIMARY
        monochrome(main_chat)
        if not _has_api_key:
            ai_mode_banner.content = ft.Text("Kết nối AI chưa được cấu hình.", size=16, color=Colors.TEXT_SECONDARY)
            ai_mode_banner.bgcolor = Colors.BG_INPUT
        if standalone:
            header.content = ft.Row([
                ft.Image(src="ink-cat.png", width=52, height=52, fit=ft.BoxFit.CONTAIN),
                ft.Column([ft.Text("Chat AI", size=28, weight=Typography.SEMIBOLD, color=Colors.TEXT_PRIMARY),
                           ft.Text("Doumar · Trợ lý lên kế hoạch", size=16, color=Colors.TEXT_SECONDARY)], spacing=2, expand=True),
                ft.IconButton(icon=ft.Icons.ADD_COMMENT_OUTLINED, tooltip="Chat mới", on_click=_start_new_chat),
                ft.IconButton(icon=ft.Icons.HISTORY_OUTLINED, tooltip="Lịch sử trò chuyện", on_click=toggle_history),
            ])
            monochrome(history_panel)
            return ft.Row([
                ft.Container(ft.Column([ft.Container(main_chat, width=960, expand=True)],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER, expand=True), expand=True, bgcolor=Colors.BG_DARK),
                history_panel,
            ], expand=True, spacing=0, vertical_alignment=ft.CrossAxisAlignment.STRETCH)
        return main_chat
    return ft.Row([main_chat, history_panel], expand=True, spacing=0)
