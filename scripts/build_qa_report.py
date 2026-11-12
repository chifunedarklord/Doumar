"""Build the Vietnamese QA report from recorded test evidence."""
from collections import Counter
from datetime import datetime
import json
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'reports'/'qa'
final=json.loads((OUT/'final.json').read_text());baseline=json.loads((OUT/'baseline.json').read_text());expanded=json.loads((OUT/'expanded-baseline.json').read_text());desktop=json.loads((OUT/'desktop.json').read_text())
GROUPS={
 'LocalDataTests':('Công việc, dữ liệu, lịch, nhắc việc và điều hướng','Nhập sai/rỗng/quá dài; Unicode; sửa đồng thời; xóa/khôi phục; JSON/CSV; lịch trùng; nhắc lỗi; 500 việc; nút điều hướng và tìm kiếm.'),
 'FolderFocusTests':('Thư mục và tập trung','ID việc nhỏ ổn định; hoàn thành/mở lại; mục tiêu sau đổi thứ tự; không chạy hai phiên; không cộng thời gian hai lần; cách ly tài khoản.'),
 'PlanningTests':('Cá nhân hóa và lưu kế hoạch','Bảng hỏi bỏ qua; prompt chung; bản nháp không lưu; chọn/xác nhận; công việc–lịch liên kết; kiểm tra trùng giờ; giờ riêng cho việc nhỏ.'),
 'SchedulingTests':('Thuật toán lịch và công việc lặp','20 bộ dữ liệu ngẫu nhiên, mỗi bộ 12 việc; khoảng nghỉ; giờ quá khứ; hạn cứng; phụ thuộc vòng; thiếu chỗ; cuối tháng, năm nhuận.'),
 'SnapshotTests':('Dữ liệu đồng bộ và gộp thay đổi','ID trùng; lịch/tin nhắn mồ côi; múi giờ sai; hạn việc nhỏ; sửa đồng thời; xóa-vs-sửa; dấu vân tay không phụ thuộc thứ tự.'),
 'SyncFlowTests':('Luồng đồng bộ client','Tải lên; không thay đổi; tải xuống; hoãn khi đang sửa; sai tài khoản; mất mạng giữ dữ liệu máy.'),
 'ServerTests':('API tài khoản, AI, thanh toán và OAuth giả lập','Đăng ký/đăng nhập/đổi và reset mật khẩu; token; mã HTTP; JSON lỗi; quota/refund; quyền gói; đơn hàng/webhook lặp; handoff OAuth; giới hạn tần suất.'),
 'LocalAuthTests':('Tài khoản cục bộ','Đăng ký/đăng nhập; trùng tên/email; mật khẩu cũ/xác nhận; tên trống; email sai; giới hạn 72 byte của bcrypt.'),
 'AIAndProviderTests':('Định dạng AI và xác thực provider','JSON/fallback/AI sai kiểu; chữ ký Stripe/payOS; quyền gói sai tài khoản/hết hạn; URL không an toàn; ma trận giá và quyền; nội dung nhãn Pro.'),
 'GoogleTransformTests':('Biến đổi dữ liệu Google Calendar','Múi giờ UTC→Việt Nam; sự kiện cả ngày; chống nhập trùng; xóa vào Thùng rác; giữ tên việc nhỏ khi xuất lịch.'),
}
issues=[
('F01','Phản hồi AI có suggested_tasks chứa null/số/chuỗi làm lỗi giao diện','test_full_app.AIAndProviderTests.test_ai_malformed_task_payload_does_not_crash_ui','core/ai_planner_service.py; components/ai_plan.py','Kiểm tra cấu trúc JSON; bản lỗi chuyển sang khung không thể lưu; renderer phòng vệ.'),
('F02','Đăng ký cục bộ nhận email sai định dạng','test_full_app.LocalAuthTests.test_invalid_bad_email','core/services.py','Kiểm tra định dạng/độ dài email trước khi ghi dữ liệu.'),
('F03','Đăng ký cục bộ nhận tên chỉ có khoảng trắng','test_full_app.LocalAuthTests.test_invalid_blank_username','core/services.py','Bỏ khoảng trắng ngoài và từ chối tên trống/quá dài.'),
('F04','Mật khẩu vượt 72 byte làm bcrypt phát sinh lỗi chưa được xử lý','test_full_app.LocalAuthTests.test_invalid_too_long_bcrypt','core/services.py','Trả thông báo hợp lệ, không lưu tài khoản dở dang; bổ sung kiểm tra khi đổi mật khẩu.'),
('F05','Danh sách việc nhỏ sai kiểu bị tính trạng thái trước khi kiểm tra','test_full_app.LocalDataTests.test_invalid_bad_children','core/repositories.py; core/task_validation.py','Kiểm tra dữ liệu trước khi tính trạng thái cha.'),
('F06','Ngày dạng YYYYMMDD được nhận nhưng có thể làm sai so sánh ngày dạng chuỗi','test_full_app.LocalDataTests.test_invalid_noncanonical_date','core/task_validation.py','Chỉ nhận định dạng YYYY-MM-DD chuẩn.'),
('F07','Công việc có giờ hạn nhưng không có ngày hạn vẫn lưu được','test_full_app.LocalDataTests.test_invalid_time_without_date','core/task_validation.py','Yêu cầu ngày trước khi nhận giờ hạn.'),
('F08','API AI nhận dữ liệu không phải ảnh nhưng khai báo image/png','test_full_app.ServerTests.test_ai_non_image_bytes_must_not_masquerade_as_png','server/app.py; server/ai.py; server/requirements.txt','Dùng Pillow kiểm tra dữ liệu ảnh, MIME, kích thước trước khi gọi AI/trừ lượt.'),
('F09','Snapshot đồng bộ nhận hạn việc nhỏ sau hạn công việc cha','test_full_app.SnapshotTests.test_reject_child_after_parent','core/snapshot.py; core/task_validation.py','Dùng cùng bộ kiểm tra công việc ở desktop và snapshot máy chủ.'),
('F10','Snapshot đồng bộ nhận thời lượng việc nhỏ âm','test_full_app.SnapshotTests.test_reject_invalid_child_duration','core/snapshot.py; core/task_validation.py','Từ chối thời lượng việc nhỏ sai miền giá trị.'),
('F11','Snapshot nhận tên múi giờ không tồn tại','test_full_app.SnapshotTests.test_reject_invalid_timezone','core/snapshot.py','Xác thực múi giờ bằng ZoneInfo trước khi nhận dữ liệu.'),
('F12','Tầng lưu trữ chat cục bộ không kiểm tra chủ hội thoại trước khi chèn tin nhắn','test_full_app.LocalDataTests.test_chat_foreign_write_rejected','core/repositories.py','Kiểm tra user_id của hội thoại; lọc user_id khi đọc tin nhắn. Chỉ tái hiện ở tầng lưu trữ, không kết luận đã có khai thác từ xa.'),
('F13','Xuất lịch Google đổi tên bước nhỏ thành tên công việc cha','test_full_app.GoogleTransformTests.test_google_preserves_subtask_slot_title','server/google_calendar.py','Giữ title của từng khoảng lịch khi xuất.'),
('F14','Đầu trang AI báo Đang hoạt động dù chưa cấu hình kết nối','UI: ai-1040x600.png + assertion trong qa_desktop.py','screens/ai_screen.py; core/i18n.py','Hiển thị Chưa kết nối khi thiếu cấu hình; khi có cấu hình chỉ báo Đã cấu hình, không khẳng định đã kết nối thành công.'),
('F15','Thông báo quyền gói bị lặp Pro và Pro','test_full_app.AIAndProviderTests.test_pro_locked_label + ảnh locked','screens/upgrade_screen.py','Hiển thị đúng gói Pro; thêm kiểm thử hồi quy cho nhãn.'),
]
counts=Counter(t['group'] for t in final['tests'])
now=datetime.now(ZoneInfo('Asia/Bangkok')).strftime('%d/%m/%Y %H:%M:%S UTC+7')
lines=['# Báo cáo kiểm thử Doumar', '',f'Ngày lập: **{now}**. Mã đang ở working tree cục bộ, chưa triển khai máy chủ hoặc phát hành bộ cài.', '',
'## Kết quả chính','',f'- **{final["passed"]}/{final["total"]} kiểm thử tự động đạt**, {final["failed"]} thất bại, {final["errors"]} lỗi chạy và {final["skipped"]} bị bỏ qua.',
f'- **{sum(x["status"]=="PASS" for x in desktop)}/{len(desktop)} lượt dựng giao diện native đạt**: 14 màn hình × 2 kích thước, cộng 1 kiểm tra đồng hồ tập trung.',
'- Phát hiện và sửa **15 tình huống lỗi**: 13 trường hợp tự động thất bại ở các lượt trước và 2 lỗi nhãn phát hiện khi xem ảnh. F15 sau đó có thêm kiểm thử tự động.',
'- Ảnh cửa sổ nhỏ của 14 màn hình đã được rà soát trực quan. Việc chụp được ảnh không đồng nghĩa đã bấm mọi nút hoặc đã kiểm thử end-to-end với dịch vụ thật.',
'- Không dùng cơ sở dữ liệu khách hàng, không gửi email thật, không thu tiền, không gọi nhà cung cấp AI/OAuth/Calendar thật trong các bài kiểm thử.', '',
'**Kết luận có giới hạn:** bộ trường hợp đã chạy đạt sau sửa. Không thể suy ra ứng dụng không còn lỗi, đạt 100% coverage hoặc đã sẵn sàng phát hành trên mọi thiết bị. Những phần chưa xác minh được liệt kê riêng bên dưới.', '',
'## Môi trường và phương pháp','',f'- Python {final["python"]}; Flet {final["flet"]}; {final["platform"]}.',
'- SQLite riêng trong thư mục tạm cho desktop và máy chủ; không kiểm thử trên MySQL/MariaDB thật.',
'- API được chạy qua WSGI thật và giao dịch cơ sở dữ liệu thật; mailer, AI, cổng thanh toán và hồ sơ OAuth dùng test doubles.',
'- Script tự động khóa kết nối Internet bên ngoài. Danh sách kết nối ngoài bị chặn trong lượt cuối: '+str(final['external_network_blocked'])+'.',
'- UI dùng các hàm dựng màn hình thật trong cửa sổ Flet. Thanh bên trong harness chỉ ghi Doumar · QA; đây không phải một lần kiểm thử toàn bộ trình cài đặt/router của bản phát hành.',
'- Kích thước cửa sổ: 1280×820 và 1040×600; theme sáng. Quyền Pro của tài khoản QA được giả lập để dựng đủ màn hình, không cấp gói cho tài khoản thật.',
'- Mỗi test trong bảng tương ứng một phương thức kiểm thử; một phương thức có thể kiểm tra nhiều dữ liệu đầu vào. Không đếm số assert thành số test.', '',
'## Diễn biến trước và sau sửa','', '| Lượt | Tổng test | Đạt | Không đạt/lỗi chạy |', '|---|---:|---:|---:|',
f'| Ban đầu | {baseline["total"]} | {baseline["passed"]} | {baseline["failed"]+baseline["errors"]} |',
'| Chạy lại sau nhóm sửa đầu tiên | 168 | 168 | 0 |',
f'| Mở rộng thêm luồng và dữ liệu | {expanded["total"]} | {expanded["passed"]} | {expanded["failed"]+expanded["errors"]} |',
f'| Cuối cùng, gồm các nút điều hướng mới | {final["total"]} | {final["passed"]} | {final["failed"]+final["errors"]} |','',
'Bằng chứng máy đọc: [baseline.json](baseline.json), [after-fixes.json](after-fixes.json), [expanded-baseline.json](expanded-baseline.json), [final.json](final.json), [desktop.json](desktop.json). Traceback của lượt lỗi nằm trong các tệp log cùng tên.', '',
'## Kết quả theo nhóm chức năng','', '| Nhóm | Test đạt/tổng | Phạm vi đã thử |', '|---|---:|---|']
for group,(name,scope) in GROUPS.items():
    group_tests=[t for t in final['tests'] if t['group']==group]
    lines.append(f'| {name} | {sum(t["status"]=="PASS" for t in group_tests)}/{len(group_tests)} | {scope} |')
lines+=['', '## Các lỗi đã tái hiện và sửa','', '| Mã | Vấn đề | Thay đổi | Kiểm chứng |', '|---|---|---|---|']
for ident,title,test,files,fix in issues:
    lines.append(f'| {ident} | {title} | {fix} Tệp: `{files}`. | Đạt lại: `{test}` |')
lines+=['', '## Dữ liệu lớn và đồng thời','', '- Xếp lịch với 20 seed cố định, mỗi seed 12 công việc có thời lượng/ưu tiên ngẫu nhiên: kiểm tra không trùng, trong giờ làm, mỗi khối tối đa 90 phút, không mất thời lượng và không sửa lịch cố định.',
'- Hai thao tác bắt đầu tập trung chạy đồng thời: chỉ một phiên thắng; hai xác nhận cùng đề xuất AI không tạo trùng công việc/lịch.',
'- Đây là kiểm tra tính đúng với hai luồng, không phải kiểm thử tải hàng trăm người dùng hoặc benchmark MySQL/Internet.']
for t in final['tests']:
    if '500_tasks' in t['id']:
        lines.append(f'- Tạo 500 công việc, đọc và dựng đối tượng danh sách Python: đạt trong **{t["seconds"]:.3f} giây** cho toàn test trên máy này. Không phải thời gian render native 500 dòng, FPS hoặc SLA hiệu năng sản phẩm.')
lines+=['', '## Giao diện và ảnh bằng chứng','', '| Màn hình | 1280×820 | 1040×600 |', '|---|---|---|']
names={'tasks':'Công việc','folder':'Thư mục','editor':'Sửa công việc','schedule':'Lịch','projects':'Dự án','report':'Báo cáo','data':'Dữ liệu','trash':'Thùng rác','settings':'Cài đặt','plans':'Nâng cấp','onboarding':'Bảng hỏi','auth':'Đăng nhập','ai':'Chat AI','locked':'Tính năng bị khóa'}
for key,title in names.items():
    values=[]
    for width,height in [(1280,820),(1040,600)]:
        r=next((r for r in desktop if r.get('screen')==key and r.get('width')==width),None)
        values.append(f'[{r["status"]}]({r["file"]})' if r else 'Chưa có')
    lines.append(f'| {title} | {values[0]} | {values[1]} |')
lines+=['', '[Ảnh đồng hồ tập trung đang chạy](screens/focus-running.png). Phiên được kết thúc khi đánh dấu hoàn thành việc nhỏ trong kiểm tra native.', '',
'## Chưa xác minh đầy đủ / không được tính là đạt','', '| Chức năng/môi trường | Đã kiểm tra | Phần còn thiếu |', '|---|---|---|',
'| Gemini thật, chất lượng tư vấn và học thói quen | Prompt, JSON, fallback, quota, lỗi provider giả lập | Phản hồi với tài khoản/dữ liệu thực, độ đúng lời khuyên, độ trễ và độ ổn định nhà cung cấp. |',
'| Stripe/payOS thật | Chữ ký, số tiền, idempotency và cấp gói trong DB tạm | Merchant sandbox/live, QR thật, thẻ thật, callback qua Internet. Không có tiền nào được thu. |',
'| Google/Facebook đăng nhập | OAuth handoff/ticket dùng một lần bằng profile giả lập | Trình duyệt consent thật, tài khoản nhà cung cấp, thu hồi quyền, điều kiện công bố ứng dụng. |',
'| Google Calendar và worker | Biến đổi sự kiện, múi giờ, xóa, ID, giữ tên việc nhỏ | Đồng bộ hai chiều với lịch Google thật, refresh token và worker chạy dài hạn. |',
'| SMTP | Token reset một lần, hết hiệu lực token cũ, mailer giả lập | Gửi/nhận email thật, rơi spam, độ trễ nhà cung cấp. |',
'| MySQL/MariaDB | Logic server chạy với SQLite | Chạy cùng bộ kiểm thử trên MySQL/MariaDB thật và cơ chế khóa InnoDB. |',
'| Microphone, STT, TTS, loa | Thư viện Python hiện diện, UI render được | Ghi âm/phát âm thật, quyền microphone, nhận giọng nói, thiết bị không tồn tại và chuyển thiết bị. |',
'| OCR | Có thư viện pytesseract | Không tìm thấy chương trình Tesseract trong môi trường này; chưa kiểm thử OCR end-to-end. |',
'| Đính kèm PDF/Word/Excel và hộp thoại tệp | UI tải tệp được dựng; dữ liệu sao lưu/CSV kiểm thử ở service | Chưa kiểm thử đủ tệp thực, tài liệu mã hóa/hỏng/lớn, định dạng cũ .doc/.xls và mọi nhánh chọn/hủy hộp thoại native. |',
'| Nhắc việc hệ điều hành | Tính thời điểm, chống trùng, retry sau lỗi, autostart trong thư mục tạm | Thông báo hiển thị thật, máy ngủ/thức, khởi động lại OS, chạy nền lâu và system tray. |',
'| Windows, bộ cài, theme/DPI | UI Linux theme sáng ở hai kích thước | Windows, bộ cài sạch/nâng cấp, dark mode đầy đủ, DPI khác nhau và nhiều màn hình. |',
'| Độ bền và tải lớn | 500 bản ghi; hai thao tác đồng thời; 20 seed lịch | Nhiều người dùng, hàng chục nghìn bản ghi, chạy nhiều ngày, mất điện/đĩa đầy hoặc hỏng DB thật. |', '',
'## Cảnh báo còn lại','', '- Flet 1.0.5 phát cảnh báo deprecation cho một số thuộc tính border cũ. Hiện vẫn render được; cần chuyển API trước khi nâng Flet lên bản loại bỏ chúng.',
'- Native Flet có cảnh báo OpenGL lúc thay kích thước và Flutter/GLib lúc đóng cửa sổ kiểm thử. Tiến trình trả exit code 0 và ảnh được tạo đủ; chưa xem đây là xác nhận mọi trường hợp thoát ứng dụng/driver đều ổn.',
'- Bộ test không thay cho đánh giá bảo mật độc lập hoặc kiểm thử nghiệm thu trên môi trường phát hành.', '',
'## Chạy lại','', 'Từ thư mục dự án:', '', '```bash', '.venv/bin/python scripts/run_qa.py --label final', '.venv/bin/python scripts/qa_desktop.py', '.venv/bin/python scripts/build_qa_report.py', '.venv/bin/python -m compileall -q core screens components utils server scripts main.py', 'git diff --check', '```', '',
'Script UI cần môi trường desktop và quyền tạo cửa sổ/socket cục bộ. Cài phụ thuộc máy chủ theo `server/requirements.txt`; bản sửa kiểm tra ảnh bổ sung Pillow. Không cần sửa schema cho các bản sửa trong lượt QA này.', '',
'## Danh sách chi tiết từng kiểm thử','', 'Mỗi dòng có mô tả mục tiêu, trạng thái cuối và thời gian thực thi quan sát được. ID đầy đủ và traceback trước sửa nằm trong JSON/log bằng chứng.']
for group,(title,_) in GROUPS.items():
    lines+=['', '### '+title, '', '| ID test | Mục tiêu/trường hợp | Kết quả | Giây |', '|---|---|---|---:|']
    for t in final['tests']:
        if t['group']==group:
            desc=t['description'].replace('|','/').replace('\n',' ')
            lines.append(f'| `{t["id"].split(".")[-1]}` | {desc} | {t["status"]} | {t["seconds"]:.4f} |')
path=OUT/'BAO_CAO_KIEM_THU_2026-11-11.md';path.write_text('\n'.join(lines)+'\n',encoding='utf-8')
print(path);print('report lines',len(lines),'tests',final['total'],'screens',len(desktop))
