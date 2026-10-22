# P6.2 — Điều phối bền vững, từng checkpoint

Ngày07/10/2026. Không mở Meta, MCP thật, business writes hoặc M4 flags.
**Trạng thái cuối: P6.2 LOCAL dry-run đã đạt C4/D.** Xem
[nghiệm thu cuối](P62-LOCAL-ACCEPTANCE-2026-10-07.vi.md) và
[runbook](P62-RUNBOOK.vi.md). Các phần A–B mô tả checkpoint lịch sử;
không phải nghiệm thu model/business execution hoặc production.
P6.1 planning-only và frozen-task guard vẫn giữ nguyên.

## P6.2A: kernel deterministic, không nối dữ liệu thật

Module `pao/modules/studio/durable_workflow.py` không import cấu hình, database,
provider hoặc filesystem. Envelope nội bộ dry-run có format, plan ID,
snapshot hash, deadline và step execution ID ổn định. Kiểm tra tối đa32steps,
ID không trùng, dependency đã xuất hiện trong thứ tự topo, timer/deadline hữu hạn.
Envelope này chưa xác minh snapshot P6.1 hoặc quyền; không được expose trực tiếp
cho người dùng. Không đăng ký workflow mới trong worker live.

Temporal sở hữu trạng thái chờ approval, timer và thứ tự dependency. Signal
chỉ nhận quyết định cho step đang chờ, first-decision-wins; signal trùng không
chạy lại step. Chạy tuần tự topo ở checkpoint này, không có parallel branches.
Không dùng polling database/scheduler thứ hai để điều phối waits.

Activity projection được phép retry tối đa3 vì contract yêu cầu idempotency
theo `(plan_id,sequence)`; P6.2A dùng fixture in-memory, P6.2B thêm DB projection.
Activity step tên cố định, retry tối đa1. Lỗi hoặc receipt không đúng đưa về
`manual_review`, không chạy step tiếp theo. Receipt dry-run không phải evidence
nghiệp vụ và không chứng minh đã gọi model hoặc tool.

Request cancel dừng bước tiếp theo và gửi cancel cho activity đang chạy, chờ
acknowledgment; heartbeat và timeout giới hạn thời gian chờ. Hủy không thể
hoàn tác một side effect đã xảy ra; ARQ bridge phải reconcile trường hợp này.
Signal raw chưa có authorization; API/outbox ở P6.2B phải kiểm tra membership,
owner/version/scope trước khi gửi. Temporal server không được mở công khai.

## P6.2B: admission, outbox và projection database — LOCAL đạt

Xem [nghiệm thu B](P62B-LOCAL-ACCEPTANCE-2026-10-07.vi.md): full688passed,
runtime8/8, build18pages, restore93business tables, live contract248/replay3/3,
0038. Đây là foundation gated-off, không phải P6.2 runner hoàn chỉnh.

Migration0038 thêm `studio_executions` và `studio_commands`. Không thay bảng
Task/Attempt hoặc StudioEvent snapshot. Trigger khóa identity/envelope; audit
command và projection dùng StudioEvent append-only hiện hữu. DB row là projection
và delivery state, Temporal vẫn sở hữu wait/timer. Không có scheduler mới.

Năm operation additive trong router Studio: status, admit plan, read execution,
decision, cancel. Start mặc định tắt, cần Studio/planning/durable/Temporal gates
và owner/admin; actor phải trùng người tạo plan. Mỗi plan chỉ một execution,
không tự restart plan terminal. Ghim toàn bộ execution IDs dự trữ P6.1;
step đều cần approval. API không cho gửi activity name/shell/endpoint tùy ý.

Admission xác minh hash snapshot/input/pins, scoped published definition,
permission/brain/MCP lint và draft tasks/dependencies. Definition republish
khi đang chạy làm reauthorization fail closed, không tự đổi sang bản mới.
Không gỡ frozen-task guard; Task vẫn draft, chưa tạo Attempt/Run/evidence thật.

Request key UUID + fingerprint + row lock chống lệnh trùng/competing decisions.
Command cùng audit trong transaction, không network trước commit. Dispatcher
explicit có ordered commands, lease token30s, reclaim lease, tối đa8 attempts,
backoff hữu hạn; error chỉ lưu code, không log payload/credential. Temporal
ID stable và REJECT_DUPLICATE ngăn restart một execution đã đóng khi retry.
Start/decision mất quyền bị dead; unknown delivery cần manual review.

Projection kiểm tra hash/sequence/topo prefix, dedup immutable event và không
overwrite terminal state. Retry projection không vượt qua quyền mới bị thu hồi;
step guard kiểm tra lại ngay trước future ARQ claim. API cancel/read không
phụ thuộc admission flag; cancel đã được chấp nhận tiếp tục drain khi flags
tắt. Cancel trước start chưa claim hủy atomically tại DB, không cần Temporal.
Cancel đã dispatch cần Temporal ack, không tự gán completed/cancelled tại API.

**Chưa đăng ký dispatcher hoặc workflow trong worker live**. Các gates durable/
dispatch/Temporal giữ false. Test E2E dùng ASGI API + DB pao_test + server Temporal
thật, nhưng activity step là fixture không gọi ARQ/model/provider. Bridge/P6.2C
và UI/P6.2D còn thiếu; không gọi P6.2 toàn bộ đã xong.

1. Ánh xạ immutable P6.1 plan vào command; xác minh hash, task IDs, actor,
   membership, current permissions, pinned definitions và feature gates.
2. Command start/decision/cancel cùng transaction với audit, có request key,
   fingerprint, scoped uniqueness; dispatch sau commit, không signal trực tiếp
   trước commit. Temporal workflow ID không đổi khi retry.
3. DB projection monotonic sequence, lock và dedup; terminal state không bị
   late delivery ghi đè. Không thay StudioEvent snapshot hoặc gỡ frozen guard
   rộng rãi để lách sang Task API.
4. Permission loss ở mỗi bước phải fail closed, không chỉ kiểm tra khi start.
5. Rollback gates phải tiếp tục phục vụ cancellation/reconciliation cho job
   đã nhận; không để tắt flag gây orphan workflows.

## P6.2C: ARQ bridge và receipts — LOCAL dry-run đạt

Checkpoint 1: bộ kiểm tra schema/exit criteria và schema-only receipt dùng chung
cho fixture API; adapter echo không đăng ký worker live. Không migration/config
change. Xem [checkpoint kết quả](P62C-RESULTS-CHECKPOINT-2026-10-07.vi.md) để biết
kết quả kiểm thử. Checkpoint 2 bổ sung job ledger bằng StudioEvent bất biến và
TaskAttempt, không migration, LOCAL đạt full715passed/restore93business tables;
xem [ledger C2](P62C-LEDGER-CHECKPOINT-2026-10-07.vi.md).
Checkpoint 3 bridge echo LOCAL đạt real Temporal/ARQ/Redis/API/DB,
full720passed/restore93business tables; xem [bridge C3](P62C-BRIDGE-CHECKPOINT-2026-10-07.vi.md).
C4 đã kiểm chứng ARQ process chết sau claim và receipt, receipt redelivery
qua process mới, actual TCP connection recovery và dispatcher/worker opt-in.
Cron owner vẫn là ARQ hiện hữu; Temporal worker riêng không đăng ký legacy
automation. Readiness cần cả hai lease source/queue-matched. Flags live vẫn tắt.

Job ngắn do ARQ sở hữu; Temporal activity chỉ điều phối, không tự gọi provider.
Execution ID P6.1 là idempotency key xuyên TaskAttempt/ARQ/receipt. Claim/lease,
result receipt và projection cần bền vững trong DB. Kill sau claim/trước receipt
cần xác định known-no-effect hay unknown; unknown không tự retry side effect.
Đầu ra phải qua pinned schema/exit criteria; model weights/evidence chỉ được
đánh dấu verified sau kiểm chứng thực. Không xem receipt fixture là kết quả thật.

## P6.2D: acceptance/UI/rollout — LOCAL dry-run đạt

Browser real HTTP start/wait/decision/cancel; duplicate/concurrent commands,
worker crash giữa step/wait/approval, DB/Redis/Temporal outage, permission loss,
deadline, uncertain side effect, snapshot replay/restore. Chạy regression toàn
bộ sau DB/API/worker changes. Chỉ enable local dry-run sau checkpoint verified;
M3 real-data và first live write vẫn là gate riêng. P6.3–P6.7 ngoài phạm vi này.

Nghiệm thu cuối đạt731tests không skip, UI real HTTP completion/reject/cancel,
ARQ claim lease60s bằng đồng hồ thật, replay7histories/restore93tables.
Actual TCP loss không phải shutdown/reboot service production. Không bật flag
trên primary DB chỉ để gọi nghiệm thu đã đạt; echo không phải model evidence.

Tham khảo deterministic workflow và history replay trong
[Temporal Python SDK](https://github.com/temporalio/sdk-python/blob/main/README.md#workflow-replay).
