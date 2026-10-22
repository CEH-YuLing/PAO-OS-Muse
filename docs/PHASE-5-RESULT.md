# Phase 5 — Tool Gateway: nghiệm thu local

Ngày 13/09/2026. Hoàn thành phạm vi mục 131: registry, permissions, approval, audit, idempotency và ba công cụ web.search, email.mock_send, calendar.mock_create. Chưa chuyển sang Phase 6.

## Kết quả

- Gateway chung kiểm tra schema, quyền agent/role và chủ run. Payload duyệt bất biến, version chống quyết định trên trạng thái cũ, khóa idempotency và transaction chống thực thi trùng.
- Search thật qua SearXNG tự host; kết quả giới hạn kích thước/số lượng và đưa vào context như dữ liệu không đáng tin cậy. Agent không có quyền gọi URL tùy ý.
- Email/lịch chỉ mô phỏng và yêu cầu duyệt. Worker độc lập nhận job sau approval, không giữ chat chờ người dùng. Có timeout, hết hạn duyệt, hủy theo run, phục hồi trạng thái unknown khi worker mất mà không tự chạy lại.
- UI tạo đề xuất, xem nội dung, duyệt/từ chối, kết quả và audit. Trạng thái công cụ lấy từ backend; không suy đoán từ hoạt động Orb. Bảng được tách theo user/session/run, không giữ draft sau khi đổi hội thoại.
- Migration 0004 thêm hai bảng. Cấu hình CPU và mô hình local giữ nguyên; SearXNG thêm container giới hạn 384 MB, bind localhost, secret riêng và image được cố định theo digest.

## Bằng chứng kiểm thử

- **55 backend tests đạt**, gồm 13 ca Phase 5 bổ sung: quyền/scope, đầu vào, idempotency/concurrency, approval version/retry/reject/expiry, quota, revocation/cancel, worker loss, lỗi provider, giới hạn adapter, kết quả tool trong context và mock không gửi thật.
- **Migration roundtrip trên pao_test và Alembic schema check đạt**. Lần thử đầu bị guard Phase 4 chặn đúng vì pao_test còn lịch sử nhiều agent của ca model thật; chạy fixture test rồi roundtrip đạt. Không dùng database chính để thử downgrade.
- **8 Node runtime tests đạt**, production build và TypeScript đạt; OpenAPI/contracts đã sinh lại.
- Browser Edge headless với API giả lập đạt luồng tạo đề xuất → duyệt → kết quả mô phỏng, từ chối, cùng hồi quy planner/agent, SSE/reconnect, failure/cancel, session/reload/logout, Memory và token expiry. Không có pageerror; đã xem ảnh `.runtime/phase-5-browser.png`.
- **Nghiệm thu thật đạt**: qwen3:4b-instruct-2507-q4_K_M trên CPU tự lập đề xuất web.search, SearXNG trả 5 kết quả qua adapter, Researcher và Chief dùng kết quả và trả URL chính thức PostgreSQL. Tổng **163,8 giây** cho ca này, không phải benchmark chung. Không fallback planner. Có thử mock email riêng: trước duyệt vẫn pending; sau duyệt completed với delivered=false.
- Artifact: `.runtime/phase-5-local-acceptance.json`; script tái lập `scripts/verify_tools_local.py`. Một lần kiểm tra SearXNG riêng có DuckDuckGo CAPTCHA nhưng vẫn nhận nguồn khác; ca model nghiệm thu có 0 engine không phản hồi. Chất lượng/khả dụng tìm kiếm phụ thuộc upstream.

## Triển khai và dữ liệu

Database chính nâng **0003 → 0004**. Backup `.runtime/pre-phase-5-20260913-210519.dump`, **64.288 byte**, kiểm tra pg_restore đọc được. Đối chiếu trước/sau:

| Bảng | Trước | Sau |
|---|---:|---:|
| users | 1 | 1 |
| sessions | 4 | 4 |
| messages | 27 | 27 |
| runs | 14 | 14 |
| agent_runs | 16 | 16 |
| memories | 0 | 0 |

Không đổi mật khẩu, owner hoặc nội dung hội thoại. Artifact đối chiếu `.runtime/phase-5-migration.json`. API/worker/web khởi động lại, worker đăng ký execute_tool và dispatch hoạt động. UI ở http://127.0.0.1:3100; registry yêu cầu đăng nhập.

Giới hạn còn lại thuộc thiết kế: email/lịch không tích hợp dịch vụ thật; approval không tự tiếp tục kế hoạch cũ; audit append-only ở tầng ứng dụng, không chống sửa bởi DBA. Phase 6/Ads chưa triển khai. Xem [hướng dẫn Tool Gateway](TOOL-GATEWAY.md) và [kế hoạch Phase 5](PHASE-5-PLAN.md).
