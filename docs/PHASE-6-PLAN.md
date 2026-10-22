# Phase 6 — Telegram

Phạm vi mục 132 và mục 24–27: bot, webhook, whitelist user/chat, messages, natural language, task delivery, alerts và approval buttons. Telegram là giao diện thứ hai dùng cùng Run/Agent Runtime/Tool Gateway; không tạo thêm agent, không triển khai Meta Ads hay scheduler tương lai.

- Bot token nhập ẩn qua CLI vào .env. Mặc định TELEGRAM_ENABLED=false; không bật khi chưa có whitelist. Một bot cho một cài đặt database; không thay bot mà tái sử dụng update ledger cũ.
- Whitelist quản trị local liên kết Telegram user ID và private chat ID với một tài khoản PAO/workspace; không tự đăng ký bằng /start, không cho group điều khiển hệ thống.
- Nhận update có ledger PostgreSQL và transaction gắn run/message/ack. Task được worker hiện có nhận qua dispatcher. Mỗi hội thoại một run đang hoạt động; giới hạn văn bản 2000 ký tự và rate limit chia sẻ với web.
- /help, /start, /new, /status, /cancel là tiện ích; câu tự nhiên đi thẳng planner hiện có. Hội thoại Telegram mới mặc định tắt Memory; chủ tài khoản có thể xem và bật từ UI.
- Delivery outbox có khóa dedup. Gửi thất bại không rõ đã nhận hay chưa chuyển unknown, không gửi lặp tự động; trạng thái kiểm tra bằng endpoint xác thực. Cảnh báo lỗi/hủy task và kết quả tool được gửi một lần.
- Approval chứa nguyên nội dung đề xuất, chỉ chấp nhận callback từ whitelist, đúng message ID đã gửi, call/version và chủ run. Quyết định đi qua service Phase 5, không thực thi tool trực tiếp từ callback.
- Polling là mặc định cho local, không cần cổng public. Webhook hỗ trợ secret header, giới hạn body và yêu cầu HTTPS khi đăng ký. Bridge I/O riêng không bị model CPU giữ chờ; advisory lock chặn hai bridge.
- Migration 0005 thêm telegram_peers/telegram_updates/telegram_deliveries. Kiểm thử chỉ dùng pao_test và Bot API giả lập. Backup trước khi nâng database chính.

Người dùng chưa có bot tại thời điểm triển khai: nghiệm thu Telegram thật cần BotFather, token và whitelist do người dùng thiết lập. Không đánh dấu ca gửi/nhận thật đạt bằng kết quả giả lập.
