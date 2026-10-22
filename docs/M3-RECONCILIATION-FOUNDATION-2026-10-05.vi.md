# M3.1 — Chuẩn bị đối soát Meta chỉ đọc

Target F:\PAO-ACOS. M3 đã bắt đầu; chưa nghiệm thu dữ liệu thật.

## Readiness kiểm trực tiếp

META_ENABLED=false, META_WRITE_ENABLED=false. Không có App ID/App Secret,
không có connection còn hạn, không có saved AdReport trong database local.
Không gọi Meta hoặc bật feature flags để bỏ qua việc chọn account/quyền.

## Đã triển khai

POST /v1/reports/{report_id}/reconciliation-preview nhận totals đã chuẩn hóa
do người dùng cung cấp và so với một saved report đúng owner/workspace/connection
version. Không sync, write, LLM, email hoặc Telegram. Không tạo bảng/migration.
OpenAPI/TypeScript đã cập nhật; script check_m3_readiness.py chỉ in booleans/counts.

So account, kỳ, currency, timezone, attribution và đủ coverage trước. Khác scope
trả incomparable, không tính chênh lệch vô nghĩa. Cùng scope mới so spend, clicks,
platform_reported_purchases bằng Decimal chính xác, chưa áp dụng sai số làm tròn.
NULL là unknown, không đổi thành 0; số âm/NaN/bool/float amount và input ngoài
schema bị từ chối. Kỳ input tối đa 30 ngày inclusive; timezone IANA bắt buộc.

Purchases không phải mọi conversion; không so doanh thu hoặc suy luận nhân quả.
file_sha256/totals/exported_at là metadata người dùng cung cấp, không chứng minh
file chính thức. Endpoint chưa đọc/xác thực file export. values_match chỉ nói các
giá trị đã nhập khớp report, business_verified luôn false. Công cụ chưa tự tạo
báo cáo 30 ngày: API report hiện có daily/weekly; luồng 30 ngày cần checkpoint riêng.

## Kiểm thử

Fixture pao_test: match/mismatch, unknown/zero, scope/timezone/attribution/coverage,
Decimal, input invalid, auth/owner/connection version. Regression **315 passed,
2 skipped**, 146.12 giây; hai ca wall-clock opt-in không bật ở checkpoint M3.1.
Runtime/SSE **8/8**. API/worker đã nạp sau idle 0 jobs; readiness HTTP 200,
ba archive M2 đọc được qua executable mới, report không tồn tại bị từ chối 404.
Smoke không tạo run/report mới và không gọi Meta. Revision giữ **0024**, không
migration mới. Chưa thay frontend UI, không chạy lại production build/browser.
Source F:\Apex\apex không sửa. Meta/readiness flags vẫn tắt như trước.
Không dùng fixture làm bằng chứng nghiệm thu số liệu Meta thật.

## Cần người dùng để sang nghiệm thu thật

1. Chọn một account act_… và kỳ 7 ngày đã hoàn tất theo timezone account.
2. Cấu hình Meta App/OAuth local an toàn, chỉ ads_read; không gửi secret vào chat.
3. Cấp rõ quyền sync chỉ đọc cho account/kỳ đã chọn; lấy export cùng phạm vi.
4. Đối soát 7 ngày trước; sai/thiếu thì xử lý tại checkpoint này, chưa sang 30 ngày.
5. Sau đó mới CRM/orders dedup/freshness, Chief Brief có nguồn và draft dry-run.
   Telegram schedule/recipient không tự bật.

M3 chưa đạt; blockers hiện tại là credentials/account/kỳ/export thật chưa có.
