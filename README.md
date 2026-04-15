# ✦ TaskFlow — Smart Personal Task Manager

> Ứng dụng quản lý công việc cá nhân thông minh, được xây dựng bằng Python + Flet

---

## 🚀 Tính năng

| Tính năng | Mô tả |
|-----------|-------|
| 🔐 Đăng ký / Đăng nhập | Xác thực người dùng, lưu local |
| 📋 Quản lý công việc | Thêm, sửa, xóa, lọc, tìm kiếm |
| 📅 Lịch biểu | Xem công việc theo tháng/ngày |
| 🔔 Nhắc nhở | Đặt hạn và mức ưu tiên |
| 🤖 Trợ lý thông minh | Phân loại và sắp xếp tự động |
| 📊 Báo cáo thống kê | Biểu đồ tháng, tỷ lệ hoàn thành |
| 👤 Quản lý tài khoản | Cập nhật hồ sơ, đổi mật khẩu |
| 💾 Đồng bộ dữ liệu | Lưu local JSON (~/.taskflow/) |

---

## 📁 Cấu trúc dự án

```
taskflow/
├── main.py                    # Entry point, navigation
├── requirements.txt
├── assets/                    # Icons, images
├── core/
│   ├── __init__.py
│   ├── models.py              # Data models (User, Task, Storage, Auth)
│   └── theme.py               # Color palette, typography, spacing
├── screens/
│   ├── __init__.py
│   ├── auth_screen.py         # Đăng nhập / Đăng ký
│   ├── dashboard_screen.py    # Trang chủ / Tổng quan
│   ├── tasks_screen.py        # Quản lý công việc
│   ├── calendar_screen.py     # Lịch biểu
│   ├── report_screen.py       # Báo cáo thống kê
│   └── profile_screen.py      # Tài khoản người dùng
├── components/
│   ├── __init__.py
│   └── widgets.py             # Reusable UI components
├── utils/
│   └── __init__.py
└── data/
    └── __init__.py
```

---

## ⚙️ Cài đặt & Chạy

```bash
# 1. Clone / tải về project
cd taskflow

# 2. Cài thư viện
pip install -r requirements.txt

# 3. Chạy ứng dụng
python main.py
```

**Yêu cầu:** Python 3.10+

---

## 🎨 Thiết kế

- **Theme:** Luxury Dark với Gold/Amber accents
- **Layout:** Mobile-first (420×820)
- **Navigation:** Bottom tab bar với 5 màn hình chính
- **Data:** Lưu JSON local tại `~/.taskflow/`

---

## 📱 Màn hình chính

1. **Dashboard** — Tổng quan, lịch tuần, công việc hôm nay, ưu tiên cao
2. **Tasks** — Danh sách công việc, filter đa chiều, CRUD đầy đủ
3. **Calendar** — Lịch tháng, click ngày xem tasks
4. **Report** — Thống kê tháng, biểu đồ danh mục/ưu tiên, all-time stats
5. **Profile** — Cập nhật hồ sơ, đổi mật khẩu, đăng xuất

---

*© 2025 TaskFlow — Made with ❤️ & Python*
