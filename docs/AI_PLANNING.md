# Cá nhân hóa và lập kế hoạch Doumar

Prompt hệ thống chung nằm trong `core/ai_policy.py` (`POLICY_VERSION`). Chat, kế hoạch JSON và máy chủ AI đều dùng chính sách này. Dữ liệu cá nhân được lấy riêng theo `user_id`, không đưa hồ sơ một người vào prompt dùng chung.

## Luồng sử dụng

- Lần đầu đăng nhập: bảng hỏi mục tiêu, vai trò, thói quen và các ràng buộc; bỏ qua từng câu hoặc kết thúc sớm vẫn lưu phần đã trả lời. Không tự chọn đáp án.
- Cài đặt → Cập nhật hồ sơ và thói quen cho AI: bổ sung câu trả lời sau này.
- AI thiếu thông tin: đưa khung sơ bộ, hỏi tiếp; bản sơ bộ chưa được lưu. Yêu cầu lên lịch rõ ràng cho phép nhận bản lịch đề xuất, vẫn cần xác nhận lưu.
- Kế hoạch đủ thông tin: chọn các mục và Xác nhận lưu. Chưa có giờ chỉ tạo công việc; có giờ tạo công việc và các khoảng lịch liên kết trong cùng giao dịch.
- Giờ thực hiện (`start_at/end_at`) tách khỏi hạn chót (`due_date/due_time`). Có thể xếp giờ riêng cho việc nhỏ; không đồng thời đặt lịch cha để tránh chiếm lịch hai lần. Khoảng lịch đã xác nhận được giữ cố định khi tạo đề xuất ngày.
- Lưu lại cùng mã đề xuất không tạo bản sao. Xung đột giờ được kiểm tra lại khi lưu; không tự dời lịch cũ. Nếu lưu nhiều mục mà một mục lỗi, giao diện báo riêng số mục thành công và lỗi.
- Trang Công việc hiển thị các công việc lớn như thư mục. Bấm biểu tượng hoặc tên thư mục để xem các việc nhỏ như tệp. Bấm tên việc để mở chi tiết, tích ô hoặc bấm Đánh dấu hoàn thành để lưu trạng thái ngay. Sửa thư mục mở trình chỉnh sửa, có kéo thả và mũi tên để đổi thứ tự.
- Mỗi việc nhỏ có nút Tập trung: bắt đầu một phiên gắn với mã việc nhỏ ổn định và đồng hồ thực. Mục tiêu vẫn còn khi chuyển trang hoặc mở lại ứng dụng trên cùng thiết bị. Mỗi tài khoản chỉ có một phiên đang chạy; cần kết thúc trước khi chuyển mục tiêu. Kết thúc tập trung chỉ ghi thời gian, không tự hoàn thành. Hoàn thành việc đang tập trung sẽ kết thúc phiên. Thời gian được ghi cho cả việc nhỏ và công việc cha, không cộng lặp khi kết thúc lại.
- Tên việc nhỏ bắt buộc; thời lượng và hạn riêng tùy chọn, hạn trống dùng hạn cha. Việc không có bước nhỏ vẫn có thể được tập trung và hoàn thành trực tiếp. Phiên tập trung đang chạy được lưu cục bộ; chưa chuyển phiên đang chạy giữa thiết bị qua luồng đồng bộ.
- Hoàn thành hết việc nhỏ thì cha hoàn thành, kể cả sau hạn. Bỏ chọn một bước thì cha được tính lại trạng thái. Thời điểm hoàn thành được giữ trong dữ liệu, không tiếp tục gắn nhãn Quá hạn cho việc đã hoàn thành.

Hồ sơ tự khai được lưu trong settings và bản ghi preference `planning_profile` để đi cùng luồng đồng bộ tài khoản hiện có. Xu hướng hành vi chỉ là suy luận chưa xác nhận; các trường mặc định không được giới thiệu là sở thích người dùng.

## Áp dụng bản cập nhật

Khởi động lại ứng dụng từ mã mới. Nếu dùng AI qua máy chủ, cập nhật cùng mã nguồn và khởi động lại dịch vụ máy chủ để nạp chính sách chung. Các bản ứng dụng đã phát hành cần được cập nhật để có bảng hỏi và giao diện mới; sửa mã cục bộ không tự cập nhật thiết bị khách hàng. Không cần thay đổi schema cho bản nâng cấp này.

## Kiểm chứng

Chạy `.venv/bin/python -m unittest discover -s tests -v`. Bộ kiểm thử dùng SQLite trong thư mục tạm, không dùng cơ sở dữ liệu tài khoản thật. Kiểm tra cú pháp bằng `python -m compileall -q core screens components utils server main.py`.

Các ảnh kiểm tra giao diện được tạo từ cửa sổ Flet thật với dữ liệu tạm. Phản hồi từ nhà cung cấp AI cần được kiểm thử thêm trên môi trường có kết nối dịch vụ; kiểm thử tự động hiện không gọi API tính phí.
