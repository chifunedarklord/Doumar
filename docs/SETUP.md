# Cấu hình và triển khai

## 1. Desktop và tài khoản

Desktop dùng SQLite để lưu dữ liệu cục bộ. API dùng MySQL/MariaDB khi triển khai; SQLite phía API phù hợp môi trường phát triển. Không cho desktop kết nối trực tiếp MySQL hoặc giữ mật khẩu cơ sở dữ liệu máy chủ.

```bash
python -m pip install -r requirements.txt
python -m pip install -r server/requirements.txt
cp .env.example .env
cp server/.env.example server/.env
```

Trên Windows PowerShell, dùng `Copy-Item` thay cho `cp` nếu cần.

Để chạy API cục bộ, mở terminal thứ nhất:

```bash
python -m server.app
```

Đặt trong `.env` của desktop, rồi chạy `python main.py` từ terminal thứ hai:

```dotenv
TASKFLOW_API_URL=http://127.0.0.1:8787
TASKFLOW_ALLOW_LOCAL_API=1
```

Đây là API thật với tài khoản do người dùng tự đăng ký, không có tài khoản mẫu hoặc cơ chế cấp gói thử. Không bật cho phép HTTP cục bộ khi kết nối máy chủ công khai. Không cấu hình API thì đăng ký/đăng nhập chỉ lưu trên máy.

Chủ bản cài có thể cấp quyền admin và toàn bộ chức năng Pro cho một tài khoản cục bộ đã tồn tại:

```bash
python scripts/manage_admin.py --username admin
# Thu hồi nếu cần:
python scripts/manage_admin.py --username admin --revoke
```

Lệnh giữ nguyên mật khẩu và dữ liệu, không tạo giao dịch thanh toán. Giao diện ghi rõ `Admin · Quyền chủ ứng dụng`. Quyền này không được xuất, khôi phục hay đồng bộ theo workspace; chỉ áp dụng khi desktop không cấu hình API. Tài khoản đồng bộ vẫn cần quyền do máy chủ xác nhận. Các dịch vụ AI/OAuth/thanh toán vẫn cần cấu hình kết nối thật.

Token tài khoản được giữ trong bộ nhớ và kho thông tin xác thực của hệ điều hành nếu có. Nếu kho hệ điều hành không khả dụng, người dùng cần đăng nhập lại khi mở app. Không phân phối token dùng chung.

## 2. MySQL / MariaDB và XAMPP

phpMyAdmin là công cụ quản trị MySQL/MariaDB. XAMPP thường cho phép quản trị cục bộ không cần mật khẩu; không dùng cấu hình này cho máy chủ công khai.

1. Bật MySQL trong XAMPP.
2. Tạo database bằng `server/mysql_setup.sql`. Tạo thêm một tài khoản MySQL có mật khẩu riêng và cấp quyền trên database `taskflow` qua phpMyAdmin hoặc công cụ quản trị của bạn.
3. Đặt URL kết nối trong `server/.env`:

```dotenv
TASKFLOW_SERVER_DATABASE_URL=mysql+pymysql://taskflow:YOUR_PASSWORD@127.0.0.1:3306/taskflow?charset=utf8mb4
```

Mật khẩu có ký tự đặc biệt cần được mã hóa theo định dạng URL. Không đặt chuỗi này trong `.env` của desktop. Schema được khởi tạo khi API mở cơ sở dữ liệu.

Nếu đã có SQLite của **API**, dừng API/worker và sao lưu trước khi chuyển. Lệnh đầu tiên chỉ xem trước:

```bash
python scripts/migrate_server_database.py --source server-data/taskflow.sqlite
python scripts/migrate_server_database.py --source server-data/taskflow.sqlite --apply
```

Database đích phải trống. Công cụ giữ nguyên nguồn và ID. SQLite desktop có schema khác; dùng xuất JSON/khôi phục theo tài khoản thay vì chuyển trực tiếp bằng công cụ này.

## 3. AI do nhà phát hành chi trả

Chỉ đặt trong `server/.env`:

```dotenv
GEMINI_API_KEY=YOUR_SERVER_KEY
TASKFLOW_AI_MODEL=gemini-3.1-flash-lite
```

Khóa phải được cấp quyền dùng model. Không đóng gói `.env` máy chủ, khóa AI, thông tin merchant hoặc mật khẩu MySQL vào ứng dụng desktop. Có thể đổi model qua cấu hình; kiểm tra lại khả năng phản hồi và chi phí trước khi thay.

API xác thực tài khoản, kiểm tra gói, giữ chỗ hạn mức rồi mới gọi AI. Mặc định Plus 300 lượt/tháng UTC, Pro 1.500 lượt/tháng UTC; giới hạn 10 yêu cầu/phút và tối đa 4.096 token đầu ra/lượt. Lỗi nhà cung cấp được trả lại lượt. Pro mở toàn bộ nhóm chức năng, không có nghĩa là số lượt AI vô hạn.

Kế hoạch theo quy tắc khi mất kết nối được ghi rõ là kế hoạch mẫu, không phải phản hồi từ mô hình.

## 4. Đăng nhập Google / Facebook

Đăng nhập mở trình duyệt hệ thống và dùng OAuth thật. Các nút không tự tạo phiên đăng nhập khi thiếu cấu hình. Callback phải khớp hoàn toàn trong App Console và trên API.

### Google

Tạo OAuth Client loại Web application và cấu hình consent screen. Thêm callback cho đăng nhập, rồi điền `server/.env`:

```dotenv
GOOGLE_LOGIN_CLIENT_ID=YOUR_CLIENT_ID
GOOGLE_LOGIN_CLIENT_SECRET=YOUR_CLIENT_SECRET
GOOGLE_LOGIN_REDIRECT_URI=http://127.0.0.1:8787/v1/auth/social/google/callback
```

Khi triển khai, thay loopback bằng URL HTTPS của API. Scope đăng nhập chỉ gồm danh tính và hồ sơ; không tự cấp quyền Calendar.

### Facebook

Tạo Meta App có Facebook Login, khai báo domain/callback và điền:

```dotenv
FACEBOOK_APP_ID=YOUR_APP_ID
FACEBOOK_APP_SECRET=YOUR_APP_SECRET
FACEBOOK_GRAPH_VERSION=vNN.0
FACEBOOK_LOGIN_REDIRECT_URI=https://api.example.com/v1/auth/social/facebook/callback
```

Thay `vNN.0` bằng phiên bản đang được App Dashboard hỗ trợ. Trong chế độ phát triển, chỉ các tài khoản được App cho phép có thể đăng nhập. Hoàn tất yêu cầu công bố của Google/Meta trước khi mở cho khách hàng. Định danh dựa vào nhà cung cấp và subject ID; không tự liên kết hai tài khoản chỉ vì trùng email.

## 5. Google Calendar hai chiều

Bật Calendar API trong Google Cloud và thêm callback Calendar riêng. Điền trên server:

```dotenv
GOOGLE_CLIENT_ID=YOUR_CLIENT_ID
GOOGLE_CLIENT_SECRET=YOUR_CLIENT_SECRET
GOOGLE_REDIRECT_URI=http://127.0.0.1:8787/v1/google/callback
TASKFLOW_TOKEN_ENCRYPTION_KEY=YOUR_FERNET_KEY
```

Tạo khóa mã hóa bằng lệnh sau và lưu riêng, không đưa lên Git:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Không đổi khóa khi chưa mã hóa lại token đã lưu. Chạy worker cạnh API:

```bash
python -m server.calendar_worker
```

Người dùng vào Cài đặt để liên kết Google. App dùng một lịch TaskFlow riêng, lưu token mã hóa trên server và đồng bộ hai chiều. Khi có xung đột, chọn bản muốn giữ trong app. Lịch lặp hoặc sự kiện kéo dài nhiều ngày chưa được xử lý đầy đủ; app bỏ qua và thông báo thay vì tự chuyển sai.

## 6. Visa và QR ngân hàng

Thanh toán thật cần tài khoản merchant và webhook. Không có nút thanh toán mô phỏng hoặc cờ môi trường mở khóa Plus/Pro trong bản này. Khi chưa cấu hình nhà cung cấp, API từ chối tạo đơn và không xác nhận thu tiền.

- **Visa:** đặt `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`; webhook `POST /v1/webhooks/stripe`.
- **QR ngân hàng:** đặt `PAYOS_CLIENT_ID`, `PAYOS_API_KEY`, `PAYOS_CHECKSUM_KEY`; webhook `POST /v1/webhooks/payos`.
- Đặt `TASKFLOW_PUBLIC_URL=https://api.example.com` để tạo URL quay lại.

Giá được tính ở server; phía desktop không gửi số tiền hay tự xác nhận ưu đãi. Quyền sử dụng chỉ thay đổi sau callback có chữ ký hợp lệ hoặc kiểm tra trạng thái từ nhà cung cấp. Việc mở URL quay lại, ảnh chuyển khoản và thao tác trên client không cấp gói.

Gia hạn cùng gói cộng thời gian từ ngày hết hạn. Nâng từ Plus lên Pro bắt đầu kỳ mới ngay khi thanh toán, không tự quy đổi thời gian Plus. Không tự động trừ tiền gia hạn. Xác minh luồng sandbox của merchant, điều khoản, hóa đơn và xử lý hoàn tiền trước khi bán.

## 7. Nhắc việc và thêm lịch khi không mở cửa sổ

Bật nhắc nền/tự khởi động trong Cài đặt. Người dùng có thể mở nhập nhanh từ khay hệ thống hoặc chạy:

```bash
python main.py --background
python main.py --quick-add
```

Nhắc việc có đánh dấu đã gửi, thử lại khi lỗi và nhắc bù trong 24 giờ. Hệ điều hành phải cho phép thông báo. Trên Linux, khả năng hiển thị menu khay phụ thuộc desktop environment/AppIndicator. Kiểm tra đăng nhập hệ thống, sleep/resume và quyền microphone trên máy đích.

## 8. Đồng bộ và phục hồi

Mỗi tài khoản có snapshot và số phiên bản riêng. Không đồng bộ mật khẩu, token, quyền sử dụng hoặc cấu hình khởi động của máy. Các thay đổi trên mục độc lập được gộp; cùng sửa một mục sẽ yêu cầu chọn bản muốn giữ. Bản bị thay được sao lưu cạnh database trong thư mục `recovery/`.

App vẫn giữ dữ liệu cục bộ khi mất mạng. Có nút Đồng bộ ngay trong Dữ liệu/Cài đặt; kiểm tra tự động được tạm hoãn trong lúc sửa công việc hoặc chat. Sao lưu database, khóa mã hóa token và dữ liệu phục hồi trước khi nâng cấp server.

## 9. Máy chủ công khai

Chạy API sau reverse proxy HTTPS. Không công khai server WSGI phát triển hoặc dùng MySQL root không mật khẩu.

```bash
python -m pip install -r server/requirements.txt
gunicorn --bind 127.0.0.1:8787 --workers 2 --timeout 90 server.app:application
```

Chạy Calendar worker như một service riêng, cùng cấu hình database. Chỉ đặt `TASKFLOW_TRUSTED_PROXIES` cho IP reverse proxy thực sự kiểm soát; proxy phải ghi đè `X-Real-IP`. Giới hạn body 8 MB. Thiết lập quyền ghi database/backup, log và giám sát phù hợp.

Khôi phục mật khẩu cần SMTP STARTTLS: `SMTP_HOST`, `SMTP_PORT`, `SMTP_FROM`, `SMTP_USERNAME`, `SMTP_PASSWORD`. Mã dùng một lần, hết hạn sau 15 phút; không cấu hình SMTP thì API báo chưa kết nối thay vì trả mã ra màn hình.

Trước phát hành thương mại cần xác nhận trên Windows và Linux: cài đặt/đóng gói, OAuth thật, sandbox thanh toán, thông báo nền, phục hồi backup và cập nhật phiên bản. Mã nguồn sạch không đồng nghĩa dịch vụ bên ngoài đã được cấu hình.
