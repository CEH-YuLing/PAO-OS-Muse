# Telegram — giao diện thứ hai của PAO

Telegram dùng cùng runtime với web: nhận yêu cầu văn bản, lưu run/hội thoại, trả kết quả hoặc cảnh báo lỗi/hủy, gửi đề xuất công cụ và nhận duyệt/từ chối. Chưa tích hợp Ads, lịch tác vụ tương lai, tệp hoặc giọng nói. Email/lịch trong Phase 5 vẫn chỉ mô phỏng.

**Cài đặt mới mặc định tắt.** Bản local hiện tại đã liên kết bot @paovn_acos_bot và whitelist tài khoản người dùng; polling đang chạy. Đã xác minh nhận tin và Telegram chấp nhận phản hồi thật. Không dán token vào hội thoại, Git hoặc đối số dòng lệnh.

## Thiết lập lần đầu

1. Mở [BotFather chính thức](https://t.me/BotFather), gửi `/newbot`, chọn tên/username và nhận token. Thao tác này cần tài khoản Telegram của bạn. [Hướng dẫn chính thức](https://core.telegram.org/bots/tutorial#obtain-your-bot-token).
2. Từ `F:/Apex/apex`, nhập token ẩn vào cấu hình local:

```powershell
.venv/Scripts/python.exe scripts/setup_telegram.py --token
```

Lệnh giữ nguyên credentials database và sinh riêng webhook secret; bot vẫn tắt.

3. Mở chat riêng với bot vừa tạo và gửi `/start`, sau đó chạy `.venv/Scripts/python.exe scripts/telegram_identity.py` khi bridge chưa bật để xem các ID đã nhắn bot. Lệnh không tự cấp quyền hoặc xóa update. Xác nhận **numeric Telegram user ID** của chính bạn. Đây không phải username hay số điện thoại. Private chat ID tương ứng phải trùng user ID. Cấp quyền cho tài khoản PAO hiện có (thay `123456789` bằng ID thật):

```powershell
.venv/Scripts/python.exe scripts/setup_telegram.py --email owner@apex.local --user-id 123456789 --chat-id 123456789
.venv/Scripts/python.exe scripts/setup_telegram.py --enable
```

CLI chỉ cho liên kết tài khoản đang hoạt động, có đúng một workspace với quyền ghi. Không chuyển whitelist đã tồn tại sang tài khoản khác để tránh trộn lịch sử. `/start` không tự cấp quyền. Thu hồi liên kết bằng cùng lệnh whitelist thêm `--disable`.

4. Khởi động lại API và bridge để đọc cấu hình mới; `start_local.ps1` giữ tiến trình cũ nên chỉ chạy lại script sẽ không reload `.env` của API đã chạy. Khi bot đã cấu hình, có thể yêu cầu Codex khởi động lại các tiến trình đúng PID đã lưu. Bridge riêng có thể chạy từ terminal:

```powershell
.venv/Scripts/python.exe scripts/telegram_bridge.py
```

Không chạy hai bridge: advisory lock PostgreSQL sẽ chặn instance thứ hai. Mở chat riêng với bot của bạn, bấm Start và gửi một yêu cầu ngắn. Polling mặc định không cần mở cổng public. Bot token đã lộ cần thu hồi ở BotFather; không chỉ đổi biến môi trường.

## Sử dụng

- Gửi văn bản 1–2000 ký tự như “Tóm tắt nội dung sau…”; Chief dùng planner, specialist và công cụ hiện có.
- `/status`: xem trạng thái lượt gần nhất; `/cancel`: yêu cầu dừng lượt hiện tại.
- `/new`: lượt kế tiếp vào hội thoại mới; không tự hủy task cũ. `/help`: hướng dẫn.
- Mỗi hội thoại chỉ một run hoạt động; yêu cầu mới khi đang bận được báo lại. Rate limit task chia sẻ với web.
- Hội thoại Telegram thuộc tài khoản PAO được cấp quyền, xem được trong web. Memory mặc định tắt cho hội thoại Telegram mới, có thể bật trong bảng Memory của chính hội thoại.
- Đề xuất email/lịch chứa nội dung cụ thể và nút duyệt mô phỏng/từ chối. Callback phải từ đúng user/chat, message đã gửi và đúng version. Gateway kiểm tra quyền lại; callback không trực tiếp gọi adapter.

## Webhook (tùy chọn)

Endpoint `POST /v1/telegram/webhook` kiểm tra `X-Telegram-Bot-Api-Secret-Token`, giới hạn body 64 KB và whitelist. Webhook chỉ bật khi `TELEGRAM_MODE=webhook`; polling và webhook không dùng đồng thời. Telegram yêu cầu HTTPS endpoint công khai; chỉ reverse proxy route webhook, không công khai toàn bộ API local.

```powershell
.venv/Scripts/python.exe scripts/configure_telegram_webhook.py --url https://YOUR-DOMAIN/v1/telegram/webhook
```

Đổi `.env` sang `TELEGRAM_MODE=webhook` và khởi động lại API/bridge. CLI đăng ký webhook nhưng không tạo tunnel, DNS hay reverse proxy. Quay lại polling bằng `--remove`, đổi mode và restart; không xóa pending updates. [Telegram Bot API: nhận update, webhook, sendMessage và callbacks](https://core.telegram.org/bots/api).

## Độ tin cậy và dữ liệu

Migration 0005 thêm whitelist, update ledger và delivery outbox. Update xử lý bằng transaction, giữ nguyên run khi Telegram gửi lại; không lưu toàn bộ raw update. Ledger thuộc một bot/database: không thay sang bot khác trên ledger cũ mà chưa lập kế hoạch chuyển dữ liệu.

Thông báo ack/kết quả/lỗi/approval có khóa dedup. Bridge giữ tốc độ gửi thấp và gom mỗi lần tối đa 100 run cần thông báo mỗi peer. Mất mạng sau khi gửi có thể không biết Telegram đã nhận chưa: đánh `unknown`, không tự gửi lặp. Kiểm tra `GET /v1/telegram/status` hoặc bảng Telegram trên web; dữ liệu chi tiết vẫn ở PAO. Việc thay đổi role, vô hiệu hóa user hoặc whitelist chặn nhận task và gửi mới; tin đã gửi ra Telegram không tự thu hồi.

Thời gian model CPU không chặn bridge vì chúng chạy tiến trình riêng. Khi bot bị chặn/credential sai hoặc mạng lỗi, bridge ghi lỗi đã loại token rồi thử kết nối lại sau 10 giây. Delivery unknown cần kiểm tra thủ công; không đảm bảo exactly-once trên mạng ngoài. Cảnh báo hiện tại là trạng thái task/tool, không phải hệ thống giám sát Ads.

Chạy `scripts/test_backend.py` để kiểm thử bằng pao_test, Redis 15 và provider giả lập. Không bật bot thật trong pytest. Muốn xác nhận end-to-end thật: gửi task từ whitelist → nhận ack → PAO hoàn tất run → nhận kết quả → thử đề xuất email mô phỏng và duyệt; đồng thời thử user/chat ngoài whitelist không tạo run.
