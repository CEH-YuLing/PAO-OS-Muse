# Phase 5 — Tool Gateway

Phạm vi mục 131: registry, permissions, approval, audit, idempotency; web.search qua SearXNG local, calendar.mock_create và email.mock_send. Không gửi email hoặc tạo lịch bên ngoài.

Một gateway duy nhất xác thực schema/agent/role và scope từ run sở hữu. Request content bất biến, khóa idempotency theo run, hash đối chiếu để chặn cùng khóa khác nội dung. Tối đa 2 tool đề xuất bởi planner, tối đa 4 tool/run tổng cộng. Model không tự cấp quyền hoặc tự approve.

Read search có thể chạy trong runtime trước specialist; kết quả là reference không đáng tin cậy. Mock writes tạo pending approval, Chief báo rõ chưa chạy. Duyệt/từ chối trên UI cùng version/nội dung cụ thể. Approval không giữ chat/worker chờ: tool job độc lập qua ARQ outbox; kết quả xem ở UI và có thể dùng trong lượt tiếp theo. Chưa xây durable workflow pause/resume nhiều bước của phase sau.

Audit append-only trong ứng dụng: đề xuất, từ chối quyền, approve/reject, started/completed/failed/cancelled/unknown/expired. Không log raw exception hoặc credentials. Khi worker mất sau claim, đánh unknown và không tự retry thao tác có side effect không xác định. Recheck quyền/run trạng thái trước thực thi. Pending hết hạn sau 24 giờ.

Migration 0004: tool_calls và tool_audits; không sửa lịch sử hội thoại. API/UI xem registry, đề xuất, duyệt/từ chối, kết quả và audit đúng chủ run. Kiểm thử concurrency/replay/conflicting payload/revocation/cancel/failure + HTTP adapter thật với server test; cuối cùng thử SearXNG local, backup/migration và smoke bản triển khai.
