# TaskFlow

Ứng dụng quản lý công việc thông minh tích hợp AI, xây dựng bằng Python + Flet với giao diện mobile (420×820px).

---

## Tính năng

### 📋 Quản lý Task
- Thêm / sửa / xóa task với đầy đủ trường: tiêu đề, mô tả, danh mục, ưu tiên, trạng thái, ngày đến hạn, thời gian, nhắc nhở, lặp lại
- Bộ lọc & tìm kiếm theo danh mục / ưu tiên / trạng thái
- Subtask, ghi chú, độ phức tạp, ước tính thời gian
- Quét ảnh để tạo task tự động (OCR + AI)

### 🤖 AI Assistant — Doumar
- Chat tự nhiên với AI (Gemini API)
- Lập kế hoạch có cấu trúc: phân tích, sắp xếp lịch, ưu tiên công việc
- Tạo task trực tiếp từ chat
- **Ghi âm giọng nói** → nhận dạng → gửi cho AI phân tích
- Text-to-speech (đọc phản hồi AI)
- Lịch sử chat đa session
- Hỏi nhanh với 4 chip gợi ý: Phân tích / Kế hoạch / Ưu tiên / Giải trí

### 📊 Insights & Analytics
- Điểm năng suất tuần, rủi ro burnout
- Heatmap tập trung theo giờ trong ngày
- Biểu đồ hoạt động 7 ngày
- Xu hướng 4 tuần (tăng / giảm / ổn định)
- Thống kê tuân thủ deadline, độ chính xác ước tính thời gian
- Phân tích procrastination theo danh mục
- Gợi ý Pomodoro cá nhân hoá

### 📅 Lịch
- Xem task theo tháng / tuần / ngày
- Màu sắc theo trạng thái và ưu tiên

### 📈 AI Engine (Backend)
- `AdaptivePriorityEngine` — tính điểm ưu tiên động cho từng task
- `BehaviorLearner` — học giờ cao điểm, mức năng lượng, xu hướng trì hoãn
- `BurnoutIntelligence` — đánh giá nguy cơ kiệt sức
- `FocusEngine` — phân tích chất lượng tập trung, gợi ý Pomodoro tối ưu
- `RecommendationEngine` — gợi ý hành động dựa trên hành vi
- `MemoryEngine` — ghi nhớ dài hạn về thói quen và sở thích người dùng

### 🌐 Đa ngôn ngữ
- Tiếng Việt 🇻🇳 / English 🇬🇧 / 中文 🇨🇳
- AI tự động trả lời theo ngôn ngữ đang chọn

---

## Tech Stack

| Thành phần | Công nghệ |
|---|---|
| UI Framework | [Flet](https://flet.dev) (Flutter-based Python UI) |
| AI | Google Gemini API (`gemini-2.5-flash`) |
| Database | SQL Server + SQLAlchemy 2.0 + pyodbc |
| Voice Input | `sounddevice` + `SpeechRecognition` (Google STT) |
| Voice Output | `gTTS` + `pygame` / pyttsx3 / Windows SAPI |
| Auth | bcrypt |
| OCR | Tesseract OCR + `pytesseract` + Pillow |
| Notifications | `plyer` |

---

## Yêu cầu hệ thống

- **Python** 3.10+ (khuyến nghị 3.14)
- **SQL Server** (local hoặc remote)
  - ODBC Driver 17 for SQL Server
- **Gemini API key** (miễn phí tại [aistudio.google.com](https://aistudio.google.com/app/apikey))
- **Microphone** (tuỳ chọn — cho tính năng voice)
- **Windows** (đã test; macOS/Linux cần bỏ Windows SAPI fallback)

---

## Cài đặt

### 1. Clone & cài dependencies

```bash
git clone <repo-url>
cd taskflow
pip install -r requirements.txt
pip install sounddevice soundfile SpeechRecognition
```

> **Lưu ý:** `pyaudio` không cài được trên Python 3.14 — dùng `sounddevice` thay thế (đã tích hợp sẵn trong code).

### 2. Cấu hình môi trường

```bash
cp .env.example .env
```

Mở `.env` và điền:

```env
# Bắt buộc
GEMINI_API_KEY=your_gemini_api_key_here
DB_SERVER=.\MSSQLSERVER01          # hoặc localhost, .\SQLEXPRESS, IP...

# Tuỳ chọn
DB_NAME=taskflow
DB_USERNAME=                        # để trống = Windows Authentication
DB_PASSWORD=
DB_DRIVER=ODBC Driver 17 for SQL Server
```

### 3. Tạo database

Tạo database `taskflow` trong SQL Server, sau đó chạy app lần đầu — các bảng sẽ tự tạo qua SQLAlchemy.

```sql
CREATE DATABASE taskflow;
```

### 4. Chạy app

```bash
python main.py
```

---

## Cấu trúc thư mục

```
taskflow/
├── main.py                    # Entry point, router, navbar
├── requirements.txt
├── .env.example
│
├── core/
│   ├── models.py              # Dataclass: User, Task, WorkSession, AIMemory...
│   ├── orm.py                 # SQLAlchemy models + kết nối SQL Server
│   ├── repositories.py        # Storage facade (CRUD)
│   ├── services.py            # Business logic: TaskService, AIMemoryService...
│   ├── ai_planner_service.py  # Phát hiện intent, gọi Gemini tạo kế hoạch
│   ├── ai_engine.py           # Prompt builder, context assembly
│   ├── theme.py               # Colors, Typography, Spacing
│   ├── i18n.py                # Đa ngôn ngữ (vi/en/zh)
│   └── intelligence/
│       ├── priority_engine.py
│       ├── behavior_learner.py
│       ├── burnout_intelligence.py
│       ├── focus_engine.py
│       ├── recommendation_engine.py
│       ├── memory_engine.py
│       ├── scheduling_engine.py
│       ├── productivity_intelligence.py
│       ├── behavioral_analytics.py
│       └── event_bus.py
│
├── screens/
│   ├── auth_screen.py         # Đăng nhập / Đăng ký
│   ├── onboarding_screen.py   # Onboarding lần đầu
│   ├── dashboard_screen.py    # Trang chủ
│   ├── tasks_screen.py        # Danh sách task
│   ├── task_edit_screen.py    # Thêm / sửa task
│   ├── calendar_screen.py     # Lịch
│   ├── ai_screen.py           # Chat AI + Voice
│   ├── insights_screen.py     # Analytics & Insights
│   ├── profile_screen.py      # Hồ sơ người dùng
│   ├── settings_screen.py     # Cài đặt
│   ├── report_screen.py       # Báo cáo
│   └── projects_screen.py     # Projects
│
├── utils/
│   └── ai_helper.py           # Gemini API wrapper, retry, fallback
│
├── components/
│   └── widgets.py             # Shared UI components
│
├── assets/
│   └── avtdoumar.png          # Avatar AI Doumar
│
└── scripts/
    ├── seed_demo_data.py      # Tạo dữ liệu demo
    ├── reset_db.py            # Reset database
    └── migrate_v*.py          # Migration scripts
```

---

## Tính năng Voice

### Cách dùng
1. Vào màn hình **AI (Doumar)**
2. Nhấn nút 🎤 bên trái ô nhập liệu
3. Input bar chuyển sang chế độ ghi âm: `[ ✕ Huỷ ] [ ● 0:03 Đang ghi âm... ] [ 🔴 Gửi ]`
4. Nói nội dung muốn hỏi AI
5. Nhấn **🔴 Gửi** → nhận dạng → gửi cho Doumar → nhận phản hồi

### Yêu cầu
```bash
pip install sounddevice soundfile SpeechRecognition
```
> Cần kết nối Internet để nhận dạng giọng nói (Google Speech-to-Text).

---

## Tính năng OCR (Quét ảnh → Task)

Khi thêm task mới, nhấn icon 📷 góc phải trên cùng để chọn ảnh. AI sẽ OCR + phân tích và tự điền các trường task.

**Yêu cầu:**
- Cài [Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki) (Windows)
- `pip install pytesseract Pillow`

---

## Biến môi trường

| Biến | Mô tả | Mặc định |
|---|---|---|
| `GEMINI_API_KEY` | API key Gemini AI (bắt buộc để dùng AI) | — |
| `DB_SERVER` | SQL Server host/instance (bắt buộc) | — |
| `DB_NAME` | Tên database | `taskflow` |
| `DB_USERNAME` | SQL Server username | Windows Auth |
| `DB_PASSWORD` | SQL Server password | Windows Auth |
| `DB_DRIVER` | ODBC Driver name | `ODBC Driver 17 for SQL Server` |

---

## Dữ liệu demo

```bash
python scripts/seed_demo_data.py
```

Tạo tài khoản demo với task, lịch sử hành vi và AI memory mẫu.

---

## Chạy không có API key

App vẫn khởi động được. Khi `GEMINI_API_KEY` chưa được cấu hình:
- Banner vàng hiển thị ở màn hình AI: *"Chưa có API key — Đang chạy chế độ demo"*
- AI sẽ trả lời bằng template mặc định thay vì Gemini
- Tất cả tính năng khác (task, lịch, insights) hoạt động bình thường

---

## Screenshots

> *(Thêm screenshots vào đây)*

| Dashboard | AI Chat | Insights | Task Edit |
|---|---|---|---|
| — | — | — | — |

---

## Giấy phép

MIT License — © 2025 TaskFlow

---

<div align="center">
  Made with ❤️ using <a href="https://flet.dev">Flet</a> + <a href="https://ai.google.dev">Gemini AI</a>
</div>
