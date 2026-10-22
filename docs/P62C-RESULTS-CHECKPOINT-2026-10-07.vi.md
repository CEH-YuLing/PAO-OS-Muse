# P6.2C — Checkpoint 1: kiểm tra kết quả và schema receipt

Ngày 07/10/2026, chỉ làm trong `F:\PAO-ACOS`.
Trạng thái: **checkpoint 1 LOCAL đạt**. Đây là một phần của P6.2C,
**chưa phải nghiệm thu ARQ bridge hoặc toàn P6.2**.

## Thay đổi

- Thêm `modules/studio/results.py`: kiểm tra input/output theo schema đã pin,
  kiểm tra mọi `exit_criteria` thuộc subset `non_empty` / `equals_input`.
- Sửa fixture API dùng cùng bộ kiểm tra. Trước checkpoint này fixture chỉ kiểm
  tra schema; output hợp schema nhưng không đạt exit criteria vẫn có thể pass.
  Nay trả 422 `studio_fixture_invalid`, không ghi `fixture_passed` khi sai.
- Receipt ghi hash contract/input/output và danh sách checks trong StudioEvent
  append-only, không thêm raw input/output vào event. Response fixture giữ nguyên.
- Adapter `fixture_echo` chỉ sao chép input và kiểm tra; schema không tương thích
  thì lỗi, không tạo output giả cho đủ trường. Chưa đăng ký vào worker live.
- Receipt `schema_only` luôn `model_executed=false`,
  `model_weights_verified=false`: đúng schema không chứng minh model đã chạy,
  nội dung đúng nghiệp vụ hoặc một task thật đã hoàn thành.

Không migration, không thay config/secrets, không sửa frontend hay Task API.
DB giữ 0038. Các event fixture cũ không được sửa hoặc tự chuyển thành receipt mới.
Caller tương lai vẫn phải kiểm tra pin/membership/permission trước claim;
helper thuần không tự cấp quyền execution.

## Kiểm chứng

Full backend sau sửa: **704 passed**, không skip, 610.39s; có 2 cảnh báo
deprecation `ARQ.close` đã có từ baseline. Database test `pao_test`, Redis15;
Meta/write/autopilot tắt, khóa test giả trong process, không dùng credential thật.
Replay 7 lịch sử Temporal P6.2A đạt; runtime/SSE 8/8. Frontend production build
18 pages và browser mock acceptance 12 routes đạt; không coi mock browser là
nghiệm thu UI runner hoặc live workflow. OpenAPI nguồn giữ nguyên 248 operations.
Lượt focused đầu: 90 passed, 1 failed vì assertion mới dùng nhầm tên field
`content_hash` thay vì `hash` trong response version. Đã sửa assertion, không
nới kiểm tra receipt. Kết quả sau sửa được cập nhật bên dưới.

Checkpoint trước thay đổi verified:
`.runtime/checkpoints/p0-20261007T104823-f46cc4be/manifest.json`.

Checkpoint trước reload verified:
`.runtime/checkpoints/p0-20261007T110607-793f854c/manifest.json`, 641 source files,
94 physical tables, 3 artifacts, revision0038; có thử backup/restore trên clone.
Database backup là dữ liệu riêng, không publish `.runtime` hoặc credentials.

Sau khi kiểm tra mọi active jobs đều 0 và xác minh executable + start-time,
đã restart riêng API/worker (API22340, worker22632); không restart Web/Ollama,
không xóa volumes. Health/ready/Web200, worker healthy; full live contract248
khớp nguồn, execution binding mới khớp, archive replay M2 đạt3/3.
`workflow_durable_enabled`, `workflow_dispatch_enabled`, `temporal_enabled`,
Meta/write/autopilot và M4 gates vẫn false; studio_executions/commands đều0.
Không có runner live mới hoặc actual provider calls từ checkpoint này.

## Checkpoint tiếp theo (chưa triển khai)

1. Resolve input binding từ snapshot bất biến và receipt của bước trước đã xác thực.
2. DB ledger job ngắn với ID xuyên execution/TaskAttempt/ARQ/receipt; claim/lease
   và commit receipt cùng transaction có fencing, duplicate không chạy thêm.
3. ARQ fixture executor + Temporal bridge enqueue/poll/heartbeat/cancel,
   kiểm tra permission ngay trước claim và commit result; không gọi provider.
4. Kill sau claim/trước receipt, Redis loss và receipt-before-ack: unknown phải
   manual review, không tự retry side effect. Chứng minh phục hồi/restore.
5. Regression rồi mới xem xét worker wiring; durable/dispatch/Temporal vẫn tắt.

Published fixture hiện chỉ có hash và checks, không có raw output lưu trong event.
Bridge không được giả định có fixture output đã lưu để làm kết quả bước tiếp.
M3 Meta thật, external MCP và production reboot vẫn là gate riêng chưa đạt.
