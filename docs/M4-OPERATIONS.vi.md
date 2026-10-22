# M4 — Hướng dẫn vận hành local an toàn

## Phân biệt các trạng thái

- Pending: sự kiện đã lưu, chưa có worker nhận xử lý.
- Processing: worker có lease, chưa phải đã xong.
- Delivered: consumer nội bộ đã lưu receipt; **không nghĩa là Ads/email đã chạy**.
- Dead-letter: tạm dừng tự retry, cần kiểm tra nguyên nhân.

Approval Center nằm trong trang Tasks, chỉ xuất hiện khi UNIFIED_APPROVALS_ENABLED
bật. Xem nội dung, thời hạn và phạm vi rồi xác nhận checkbox trước quyết định.
409 nghĩa snapshot/input/version đã đổi hoặc hết hạn: tải lại, đọc lại và quyết
định lại, không sửa database hay bấm lặp để ép qua guardrail. Viewer không được
quyết định; Tool thuộc người gọi, Ads owner/admin, Task theo domain membership.

## Ba công tắc độc lập

Mặc định cả3false và nghiệm thu vận hành vẫn giữ false:
BUSINESS_EVENTS_ENABLED, BUSINESS_EVENT_DELIVERY_ENABLED, UNIFIED_APPROVALS_ENABLED.
Chỉ bật trong profile kiểm thử `scripts/run_p1_browser_acceptance.py --m4` sau
backend regression; profile dùng pao_test/Redis15/API18100 và worker receipt riêng.
Không chạy profile đồng thời pytest vì chúng dùng chung database kiểm thử.

Không bật Meta/Ads writes, Telegram hoặc Temporal để thử M4. Không tự có P6 runner.
Khi có đủ M3 dữ liệu thật, cần scope/approval riêng trước bật các công tắc live.

## Chẩn đoán

API /v1/business-events/diagnostics theo workspace trả counts từng trạng thái,
event type, receipts, oldest pending, expired leases và50dead-letter gần nhất.
API /ledger trả tối đa100event gần nhất với payload reference/hash, không evidence
thô. Inbox đọc trạng thái domain trực tiếp; event approval.requested lịch sử có
receipt không tự duyệt và không thay nguồn trạng thái hiện hành.

Mất Redis: PostgreSQL giữ pending/retry, không tự repair bằng xoá queue hay event.
Process chết: lease60s hết hạn rồi được claim lại; token cũ không thể ack lease mới.
Đạt5lượt: dead-letter. Actor mất quyền/inactive: dead-letter ngay; không đổi actor
hoặc reset attempts để ép xử lý. Không có endpoint replay dead-letter ở M4 này.

## Backup, retention và rollback

Trước migration: health/idle, checkpoint có restore, clone migration giữ hash.
Sau restart: health/worker, saved contract/binding, old M2 replay3/3 và live flag-off
gate. Source/checkpoint chứa AGENTS.md; secrets được giữ riêng, không vào archive.

Giữ ledger/receipts và backup; chưa có purge tự động. Không tuỳ ý DELETE/TRUNCATE,
reset Docker hay xoá volumes để sửa sự kiện. Hash không phải mã hoá/chữ ký và
immutable trigger không chống DBA có quyền disable trigger/TRUNCATE.

Rollback thông thường: tắt flags, xác nhận idle và restart riêng API/worker theo
PID/executable/start-time; giữ dữ liệu để điều tra. Downgrade0037 sẽ từ chối khi có
profiles mới. Cold restore cần môi trường riêng với backup/keys được xác minh;
không restore đè database live trong quá trình nghiệm thu này.

Thu hồi Tool/Ads chỉ khi pending/queued và đúng version, có audit. Nếu đã executing
thì API trả409; không hứa có thể dừng hoặc đảo ngược external HTTP write đã gửi.
Các API domain/executor vẫn giữ policy/permission guardrails riêng.

Production reboot drill, monitoring24/7 và M3 dữ liệu thật chưa được thay thế bởi
nghiệm thu local. Xem [ADR M4](ADR-M4-DELIVERY-AND-APPROVALS.vi.md).
