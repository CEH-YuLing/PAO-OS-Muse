# P6.2B — Admission, command outbox và DB projection

Ngày07/10/2026, F:\PAO-ACOS. Trạng thái: **P6.2B foundation LOCAL đạt**.

## Đã triển khai

Hai bảng additive0038; envelope/identity immutable và audit append-only.
Năm API scoped gated; admission pin/hash/permission validation, one execution
per plan, command dedup/version/transaction, first decision, cancel drain.
Explicit dispatcher ordered/leased/bounded retry, Temporal ID reuse protection.
Monotonic projection/dedup/terminal guard và reauthorization trước step.
Không thay source bảo vệ, credentials, Task API frozen guard hoặc live writes.

## Bằng chứng trước rollout

- Checkpoint verified: `.runtime/checkpoints/p0-20261007T094034-97d7823c/manifest.json`,
  626files,92physicaltables,3artifacts,0037.
- Clone migration0037→0038→0037→0038, alembic check đạt; 91business tables
  hash-exact, source database không đổi.
- Focused75passed/59.98s: contract/Studio/Tasks/admission/outbox/projection và
  real ASGI API/DB/Temporal. Chỉ fixture step, không ARQ/model/tool/business writes.
- Luồng thật: start commit→dispatch→Temporal wait→decision commit→signal→step
  guard→DB projection, hai step approved,3commands,7projection events; history
  replay đạt. TaskAttempt/Run vẫn0, task kế hoạch vẫn draft.
- Schema collision `Decision` đã phát hiện và sửa thành DurableDecision; so sánh
  cuối243API/schema cũ không đổi, đúng5additive→248. Full test đang chạy khi
  sửa tên đã dừng riêng đúng test process và bắt đầu lại trên bản cuối.
- Runtime/SSE8/8; production build cuối18pages và browser12routes mock đạt.
  Mock không thay thế E2E Temporal.
- Replay7/7 history P6.2A với kernel mới đạt, không DB/provider calls.
- Full lượt đầu687passed/1failed/2warnings,534.56s. Failure là test guard
  downgrade hard-code0037 khi test DB đã ở0038; guard thực tế vẫn từ chối
  downgrade có event profiles mới. Sửa test kiểm tra revision VÀ danh sách
  bảng trước/sau không đổi; không nới điều kiện hoặc bỏ qua test. Full đang
  đã chạy lại như bên dưới; không coi lượt failed là đạt.
- Full bản cuối: **688 passed**, không skip,531.49s. Hai cảnh báo ARQ Redis
  deprecated close trong test delivery/source; không có test failure.
- Checkpoint trước rollout verified:
  `.runtime/checkpoints/p0-20261007T100238-dcc74021/manifest.json`,636files,
  92physicaltables,3artifacts,0037; installation schema chưa đổi ở thời điểm này.

## Gate và phạm vi

Fixture cuối1passed/15.09s; dump/restore **93business tables hash-exact**, giữ
3commands/7projections, TaskAttempt/Run/LLM attempt/business event0.
Checkpoint sát rollout verified:
`.runtime/checkpoints/p0-20261007T101707-0dc375a3/manifest.json`,637files,
92physicaltables,3artifacts,0037. Sau gate idle/gates-off, chỉ restart đúng
API/worker và migration0038 qua launcher; alembic check sạch. API PID23296,
worker PID20908 tại nghiệm thu; Web/Ollama không restart.

Live health/ready/Web200, worker healthy; contract248 khớp source/binding,
archive replay3/3 đạt. DB0038; studio_executions0/studio_commands0, không có
fixture trong business DB. P6.1 planning vẫn true/execution false. Durable,
dispatch, Temporal và ba M4 flags false; Meta/write/autopilot false. App/secret
còn cấu hình, Meta connection/report0; không external calls.

Không tự bật durable/
dispatch/Temporal trên installation này khi chưa có ARQ bridge/worker wiring.
Không có UI Run mới; P6.2C/P6.2D chưa triển khai. M3 real data, MCP thật,
production/reboot acceptance vẫn chưa đạt. Meta pause, giữ App/key riêng.

Rollback vận hành: tắt admission/dispatch mới, giữ cancel/read/reconciliation
cho execution đã nhận. Không hạ schema bằng downgrade trên database đang có
execution; up/down/up trong báo cáo chỉ làm trên clone riêng, không phải lệnh
rollback production. Không xóa ledger/commands hoặc reset volumes.

Chi tiết tại [ADR](ADR-P62-DURABLE-WORKFLOWS.vi.md).

Checkpoint cuối verified:
`.runtime/checkpoints/p0-20261007T101944-93ffaa22/manifest.json`,637sourcefiles,
94physicaltables,3artifacts,revision0038. Source archive không chứa credentials;
database backup là dữ liệu riêng, không publish runtime hoặc gửi lên Git.
