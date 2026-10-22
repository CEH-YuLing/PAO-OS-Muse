> Bản vá 14/09/2026: [approval Telegram nhiều phần đã sửa](TELEGRAM-APPROVAL-FIX-2026-09-14.md), 66 backend tests đạt; API và bridge đã nạp lại bản sửa.

> Cập nhật sau thiết lập bot: @paovn_acos_bot đã liên kết whitelist người dùng và chạy polling thật. Task Telegram `352bc4ed-0c8b-4077-814c-51e60ab409b9` hoàn tất qua runtime local, error_code=null; Telegram xác nhận gửi kết quả (delivery=sent). Artifact `.runtime/phase-6-telegram-connection.json`. Luồng giao task → nhận kết quả thật đã đạt; callback approval qua Telegram thật chưa thử riêng. Phần bên dưới lưu kết quả tại thời điểm triển khai mã trước khi có bot.

# Phase 6 — Telegram: triển khai local, chờ bot thật

Ngày 13/09/2026. Phạm vi mục 132 đã có implementation và kiểm thử local. **Chưa nghiệm thu end-to-end với Telegram thật vì người dùng chưa tạo bot.** Telegram giữ tắt; không gửi tin nhắn thực, không tạo whitelist giả trong database chính. Chưa chuyển Phase 7.

## Đã triển khai

- Whitelist gắn cả Telegram user ID/private chat ID với một tài khoản PAO/workspace. /start không tự cấp quyền; group, người ngoài whitelist và tài khoản bị thu hồi quyền không điều khiển hệ thống.
- Nhận văn bản tự nhiên vào Run/Agent Runtime hiện có, cùng quota với web, một run hoạt động mỗi hội thoại. Có /help, /start, /status, /cancel, /new. Hội thoại Telegram mặc định tắt Memory và có thể xem từ web.
- Webhook kiểm tra secret header, mode, body 64 KB. Polling mặc định cho máy local; bridge riêng dùng PostgreSQL advisory lock chống chạy hai instance, không bị inference CPU giữ chờ.
- Update ledger và outbox PostgreSQL chống tạo task/thông báo lặp. Gửi ack, kết quả, cảnh báo failed/cancelled và trạng thái tool. Kết quả cũ còn thiếu được phát hiện khi bridge hoạt động lại. Chia tin nhắn theo giới hạn UTF-16; không bật parse_mode hoặc link preview.
- Approval gửi đầy đủ nội dung mô phỏng, có nút duyệt/từ chối. Callback gắn với message đã gửi, chủ tài khoản, chat và version; quyết định đi qua Tool Gateway, không gọi adapter trực tiếp. Có answerCallbackQuery để kết thúc trạng thái chờ của nút.
- Delivery không rõ kết quả chuyển unknown, không tự phát lại; kiểm tra lỗi trong bảng Telegram trên web hoặc endpoint có xác thực. Không tuyên bố exactly-once cho mạng Telegram.
- CLI nhập token ẩn, xem ID ứng viên, cấp/thu hồi whitelist, bật cấu hình và đăng ký/xóa webhook. Token không đưa vào command arguments hoặc thông báo lỗi provider. UI chỉ hiển thị trạng thái cấu hình, không coi đó là bằng chứng kết nối bot.

## Kiểm chứng

- **64 backend tests đạt**: 55 tests Phase 0–5 và 9 tests Telegram. Bao gồm whitelist user/chat/group, concurrent replay, scope session, busy/cancel/new, revocation, webhook secret/body/disabled, runtime task→delivery, approval message binding/version, uncertain/stale delivery, status ownership và kết quả cũ/Unicode.
- Migration **0005 roundtrip trong pao_test** và Alembic schema check đạt. Database thật không dùng để thử downgrade.
- **8 Node runtime tests đạt**; production build/TypeScript/OpenAPI/contracts đạt.
- Browser Edge headless với API giả lập đạt trạng thái Telegram chưa cấu hình và toàn bộ hồi quy Phase 2–5; không có pageerror.
- Script bridge khi chưa có token thoát bình thường và không gọi mạng. CLI cấu hình chạy được phần help. Gửi/nhận Telegram thật, getUpdates/setWebhook/answerCallbackQuery qua provider thật chưa thử do chưa có bot.

## Triển khai

Database chính nâng **0004 → 0005**, thêm telegram_peers, telegram_updates, telegram_deliveries. Backup `.runtime/pre-phase-6-20260913-212726.dump`, **73.475 byte**, pg_restore đọc được. Artifact đối chiếu `.runtime/phase-6-migration.json`.

| Bảng | Trước | Sau |
|---|---:|---:|
| users | 1 | 1 |
| sessions | 4 | 4 |
| messages | 29 | 29 |
| runs | 15 | 15 |
| agent_runs | 17 | 17 |
| memories | 0 | 0 |
| tool_calls | 0 | 0 |
| tool_audits | 0 | 0 |

Giữ nguyên owner, mật khẩu và nội dung hội thoại. API/worker/web đã khởi động lại trên local. Bridge tắt khi chưa cấu hình bot, không tạo traffic Telegram.

## Còn lại để nghiệm thu Phase 6 thật

Người dùng tạo bot qua BotFather, nhập token ẩn bằng CLI, xác nhận user/chat ID và cấp whitelist. Sau khi bật/restart: gửi task từ Telegram → nhận ack → nhận kết quả thật → thử duyệt/từ chối công cụ mô phỏng; kiểm tra user ngoài whitelist không có quyền. Đây là bước chưa hoàn thành, không được thay bằng test giả lập.

Xem [hướng dẫn thiết lập Telegram](TELEGRAM.md) và [kế hoạch Phase 6](PHASE-6-PLAN.md). Phạm vi triển khai được kiểm chứng là Windows local/native; chưa nghiệm thu bridge trong container hay webhook với reverse proxy công khai.
