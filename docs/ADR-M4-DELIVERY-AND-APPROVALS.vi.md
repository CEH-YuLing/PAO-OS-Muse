# ADR M4.2–M4.5 — Delivery nội bộ và phê duyệt xuyên module

Ngày07/10/2026. Chỉ checkout PAO-ACOS, không tự mở business writes/P6.

## Ownership và delivery

Ledger business và outbox ở PostgreSQL; worker ARQ hiện có đánh thức một consumer
cố định `internal.audit.v1`. Không thêm scheduler khác, không dùng SSE làm ledger,
không gọi LLM/connector hay tạo Task/Ads action từ consumer.

0036 thêm lease token/thời hạn, available_at, delivered_at, error_code và receipt
scope. Claim dùng `FOR UPDATE SKIP LOCKED`, tăng attempts trong transaction.
Job ID chứa token; worker cũ không thể ack/fail lease mới. Lease60s, tối đa5lượt,
backoff2^attempts tối đa60s. Mất enqueue hoặc process chết giữ dữ liệu trong
PostgreSQL để thử lại; attempt hết thì dead_letter, không tự retry vô hạn.

Consumer kiểm user active/membership/write role hiện hành, schema/hash/scope.
Receipt unique event và ack commit cùng transaction. Bản phát lại không thêm
receipt. Đây là at-least-once vận chuyển, **không phải exactly-once external
effects**. Consumer không tạo external effects và không cần aggregate ordering
cho receipt từng event; projection trạng thái phụ thuộc thứ tự cần gate riêng.

Không có API xoá ledger/reset retry/dead-letter để tránh vượt guardrail. Diagnostic
và ledger là view bounded theo workspace, không trả evidence/payload thô. Pending
và dead-letter không tự tạo hành động. Bảo trì/retention giữ ledger và receipts;
không tự purge/TTL trước quyết định riêng và backup thử restore.

## Unified Approval Center

M4 thêm một router với6operations, không thay API Task/Tool/Ads cũ. Inbox đọc qua
adapters, không chuyển quyền domain sang một quyền UI chung. Tool chỉ thuộc người
gọi; Ads quyết định owner/admin; Task giữ membership write và domain transition.
Viewer có thể đọc nhưng không quyết định. API xác thực kiểm User.active.

Snapshot ký JWT HS256 bằng key local hiện có, issuer/audience riêng; chứa actor,
workspace, source kind/id, version, input hash, expiry. Không chứa credentials
hoặc evidence thô trong ticket. UI hiển thị nội dung cần kiểm, yêu cầu checkbox,
disable khi hết quyền/hạn; nhưng backend vẫn kiểm lại dù client bỏ qua UI.
Snapshot cũ/mất quyền/hết hạn/sai người/sửa nội dung không tăng version đều bị từ
chối. Refresh cần snapshot mới, không âm thầm approve dữ liệu đã đổi.

Task decision tái sử dụng TaskPatch dưới cùng lock/transaction. Tool/Ads dùng
domain service và kiểm expected_hash trong transaction đã lock source. Cùng
snapshot concurrent approve/reject chỉ một quyết định được nhận; replay snapshot
cũ trả409, không tạo outcome mới. Domain API cũ giữ semantics replay hiện có.

Tool/Ads giữ hash đầu vào thực thi lúc duyệt. Executor kiểm hash/permission/
expiry; Ads còn kiểm connection, live-write flag và autopilot policy trước claim
và sau resource-read. Revoke pending/queued chỉ có hiệu lực trước claim; đã
executing trả409. Không hứa có thể thu hồi HTTP write đã gửi hoặc ngăn thay đổi
quyền xảy ra sau lần preflight cuối; đó là giới hạn distributed external effects.

## Event profiles và scope

0037 mở3profiles: task.completed, approval.requested (Task/Tool/Ads),
ads.analysis.completed. Producer thuộc transaction nguồn, không commit riêng.
Approval bao phủ create/transition Task và completed attempt vào waiting_approval;
Tool propose pending; Ads propose chưa được autopilot duyệt. Analysis phát sau khi
summary hoàn chỉnh, cả API và scheduler dùng cùng service.

Composite FK riêng Task/Tool/AdAction/AdIntelligenceRun giữ tenant, CHECK đúng một
target không null và khớp aggregate id/type. Migration backfill target cho Task
event cũ trong transaction, rồi phục hồi immutable trigger. Downgrade0037 từ chối
khi có profiles mới để không âm thầm mất/ép dữ liệu thành Task event.

Approval requested là lịch sử lúc cần duyệt, không phải state hiện hành của inbox.
Inbox luôn đọc nguồn domain; receipt của event cũ không approve hoặc execute.

## Flags và rollout

BUSINESS_EVENTS_ENABLED, BUSINESS_EVENT_DELIVERY_ENABLED, UNIFIED_APPROVALS_ENABLED
đều false mặc định. Delivery cần cả hai cờ event/delivery. Local acceptance bật
trong pao_test/Redis15; vận hành giữ cả ba false khi M3 dữ liệu thật chưa đạt.
Checkpoint/clone migration/contract/regression/browser/restore/live replay phải
đạt trước rollout. Không bật Meta/Telegram/public deploy hoặc thay Temporal outbox.
Rollback vận hành ưu tiên tắt flags, restart scoped, giữ ledger/receipt/backup;
không chạy downgrade lossy hoặc xoá volume. Không dùng test fixture để mở P6.
