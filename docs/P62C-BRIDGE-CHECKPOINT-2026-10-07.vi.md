# P6.2C — Checkpoint 3: bridge Temporal–ARQ giả lập

Ngày 07/10/2026, `F:\PAO-ACOS`. **Checkpoint 3 LOCAL đạt.**
**Chưa nghiệm thu hết P6.2C hoặc runner live.**

## Phạm vi

`arq_bridge.py` nhận Redis pool tường minh, không tạo kết nối live mặc định.
Temporal activity vẫn tên cố định `p62_dryrun_step`, enqueue ARQ function cố định
`execute_studio_echo`; payload queue chỉ có plan/step/execution IDs.
Executor dùng input đã pin, `finish` kiểm tra echo/schema/exit criteria và commit
receipt. Không gọi model, shell, MCP, Ads hay provider; không nhận mã thực thi.

Temporal heartbeat trong lúc chờ DB outcome, cửa sổ chờ25s; mỗi enqueue tối đa2s.
Job ARQ ID là `p62:<step execution ID>`, cùng ID TaskAttempt/namespace receipt.
Redis result không được dùng làm evidence; chỉ outcome DB được kiểm tra lại pin,
quyền, schema và receipt hash. Activity trả receipt tối thiểu tương thích kernel
cũ; history replay không cần thay workflow code.

Khi enqueue lỗi/mất queued entry, chỉ `pending` (chưa claim) được enqueue lại.
`running` không enqueue lại; claim hết hạn/unknown dùng C2 manual_review, không
tự retry. Activity cancellation yêu cầu cancel execution và drain ledger theo
adapter echo không có side effect. Hủy đã có receipt không xóa receipt cũ.
Adapter output không tương thích ghi failed bền vững, không để orphan claim.

Chưa có live registration, cron dispatcher hoặc worker launcher cho bridge.
`arq_bridge_ready=false` vẫn đúng: helper đã có nhưng worker live chưa sẵn sàng.
Không migration/config/frontend change; DB0038, durable/dispatch/Temporal và Meta tắt.

## Kiểm chứng

- 5 bridge tests đạt,19.41s: hai bước qua real local Temporal + ARQ + Redis15 +
  ASGI API + PostgreSQL pao_test, approval từng bước, hai receipt/attempt duy nhất,
  task vẫn draft, không Run; lịch sử mới replay được.
- Lỗi RedisConnectionError đầu enqueue được **inject**, sau đó Redis/ARQ thật;
  không phải bằng chứng outage/restart Redis server thực tế.
- Duplicate ARQ function delivery không thêm attempt, cancel khi flags off,
  cancellation activity helper trước worker và adapter schema failure có outcome.
  Những bài helper không thay thế kiểm thử kill/restart worker thật.
- Replay7 lịch sử P6.2A/runtime8/8/contract248 giữ nguyên.

Lượt focused đầu 104passed/1failed khi dọn continuous ARQ polling task trên
Windows; đã xử lý CancelledError shutdown, không bỏ assertion workflow/receipt.
Một lượt lệnh test tạm dùng URL Redis thiếu auth bị 5 setup errors; đã dùng lại
URL cấu hình giữ auth và đổi riêng DB15, không sửa password hoặc Docker.

Checkpoint trước code verified:
`.runtime/checkpoints/p0-20261007T112939-f3a63c93/manifest.json`.
Full regression: **720passed**, không skip,553.61s;3cảnh báo deprecation
ARQ.close (thêm một lượt dùng real ARQ worker ở bridge). Tests chỉ dùng
pao_test/Redis15, khóa giả trong process, Meta/write/autopilot tắt. Frontend
source không đổi, không tuyên bố nghiệm thu browser runner mới.
Fixture tích hợp chạy riêng lại:1passed/15.71s; restore clone riêng đạt,
93business tables hash-exact,6step events,2dry-run attempts,3delivered commands,
7projections. Source test DB giữ hash; chỉ clone UUID tự tạo được dọn, dump
riêng giữ trong `.runtime`. Không thay ledger/database live.

Checkpoint trước reload verified:
`.runtime/checkpoints/p0-20261007T114649-d91e279a/manifest.json`,650sourcefiles,
94physicaltables,3artifacts,revision0038. Sau idle=0 và xác minh path/start-time,
restart riêng API14772/worker18824; Web/Ollama giữ nguyên. Health/ready/Web200,
worker healthy; full live contract248/execution binding khớp, M2archive3/3replay.
Gates durable/dispatch/Temporal/Meta/write/autopilot/M4 vẫn false, executions/
commands live0. Chưa đăng ký bridge vào worker live, arq_bridge_ready=false.

## Gate tiếp theo

1. Thử kill/restart ARQ/Temporal worker thật tại reserve/claim/receipt/ack;
   late output, duplicate/concurrent enqueue và lỗi DB/Redis/Temporal thực tế.
2. Dispatcher bounded + wiring worker, failure/cancel reconciliation khi gates off.
3. Regression/backup/restore và review quyền trước khi cân nhắc enable dry-run local.
4. P6.2D UI/acceptance riêng; không xem checkpoint này là model/business execution,
   Meta thật, MCP thật hoặc production/reboot acceptance.
