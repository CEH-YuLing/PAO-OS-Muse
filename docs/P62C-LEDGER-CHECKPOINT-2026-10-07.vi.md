# P6.2C — Checkpoint 2: ledger job ngắn và receipts

Ngày 07/10/2026, `F:\PAO-ACOS`. **Checkpoint 2 LOCAL đạt.**
**Chưa phải nghiệm thu ARQ bridge hoặc toàn P6.2C.**

## Cấu trúc được dùng lại

Không thêm bảng/migration: `StudioEvent` append-only giữ envelope, claim và
outcome; `TaskAttempt` là projection của attempt. ID bước đã đặt ở P6.1 được dùng
cho attempt và namespace event. Redis không được coi là nguồn kết quả bền vững.
Helper `step_jobs.py` chỉ được gọi tường minh; chưa đăng ký ARQ/live scheduler.

- `reserve`: kiểm tra quyền, flags, snapshot/pins và bước đang chạy; resolve
  input từ workflow hoặc receipt bất biến của mọi dependency. Chỉ trạng thái
  “completed” trong projection mà thiếu receipt thì không đủ.
- `claim`: khóa execution trong transaction; token riêng, đúng một attempt khi
  claim đồng thời. Job reserved nhưng chưa claim là known-no-effect.
- `finish`: xác thực token, lease, permission/pins/flags và cancel; chỉ nhận
  output từ adapter echo cố định. Receipt và attempt được commit cùng transaction.
  Gửi lại cùng output trả receipt cũ; output khác bị conflict.
- `recover`: đọc outcome sau receipt-before-ack; drain cancel dù admission tắt.
  Claim đã hết hạn, không receipt: failed `worker_lost_unknown`, execution
  `manual_review`; không tự retry. Reserved cancel chưa claim không tạo attempt.
- Lease cố định 60s tính từ timestamp immutable claim; sửa `updated_at` của
  TaskAttempt không gia hạn lease. Chưa có heartbeat/lease-renewal service.

Task kế hoạch vẫn `draft`, không có Run hoặc business completion/effect. Receipt
luôn dry-run/schema-only, `model_executed=false`, `model_weights_verified=false`.
API execution đọc số attempt thực tế thay vì hard-code false. Task API update
attempt bị chặn với planned tasks, giống create/patch task đã chặn trước đó.

## Kiểm chứng

Focused trước bổ sung queued-cancel và kiểm chứng final projection: 101 passed,
68.56s. Replay lịch sử Temporal cũ7/7, runtime/SSE8/8; OpenAPI giữ248 operations.
Full regression sau các bổ sung cuối: **715 passed**, không skip, 529.94s;
2 cảnh báo ARQ.close cũ. Tests dùng pao_test/Redis15, khóa giả trong process,
Meta/write/autopilot tắt. Frontend source không đổi ở checkpoint này;
build18pages/browser mock12routes là kết quả C1, không tính thành UI runner.
Fixture ledger hai bước riêng: 1 passed, 2.39s. Backup/restore vào clone UUID
tự tạo đạt, 93 business tables hash-exact, 6 step events và 2 dry-run attempts;
source test DB hash không đổi sau restore. Clone test được dọn sau kiểm tra,
dump riêng giữ trong `.runtime`, không publish; không thay database live.

Checkpoint trước reload verified:
`.runtime/checkpoints/p0-20261007T112542-5f793000/manifest.json`,646sourcefiles,
94physicaltables,3artifacts,revision0038. Không có migration mới.
Sau idle=0 và xác minh executable/start-time, restart riêng API17380/worker19524;
Web/Ollama giữ nguyên. Live health/ready/Web200, worker healthy; contract248 và
execution binding khớp nguồn, archive replay M2 đạt3/3. Flags durable/dispatch/
Temporal/Meta/write/autopilot/M4 vẫn false, studio_executions/commands live đều0.
Các tests mô phỏng claim lease expiry bằng clock advance, **không phải kill/restart
ARQ process thật**. Không chứng nhận Redis loss hoặc Temporal/ARQ end-to-end.

Checkpoint trước code verified:
`.runtime/checkpoints/p0-20261007T110914-6513bd50/manifest.json`.

## Còn thiếu trước khi hoàn tất P6.2C

1. Temporal activity fixed enqueue/poll/heartbeat/cancel qua ARQ, không gọi model.
2. Bounded dispatcher cho các reserved jobs; xử lý enqueue failure/Redis loss,
   fail-closed khi mất quyền và không làm mất cancellation khi tắt flags.
3. Worker crash thật giữa reserve/claim/receipt/ack; concurrency và phục hồi
   ledger qua process restart. Unknown không tự retry side effect.
4. Kiểm thử tích hợp Temporal + ARQ + DB + Redis trước khi đăng ký runner live.

Durable/dispatch/Temporal và Meta writes vẫn tắt. UI runner/P6.2D, M3 real data,
external MCP và production reboot vẫn ngoài checkpoint này.
