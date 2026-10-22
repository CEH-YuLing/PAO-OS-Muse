# P6 — Dispatcher parent Goal, nghiệm thu trước child

Ngày09/10/2026. Checkpoint này chưa phải parent → active child → ARQ drain
end-to-end. Không đổi kernel/iteration grants hoặc bật live Goal.

## Đã triển khai

Module nội bộ goals/dispatcher.py: pass tối đa50lệnh, thứ tự ordinal theo
execution, row locks và lease30s, token bảo vệ final ACK, network timeout10s,
retry backoff tối đa60s/tối đa8attempts. Không giữ DB lock trong network call.
Không ghi trạng thái thành công, release budget hoặc resume từ transport ACK.

Start/decision mặc định không được gửi; explicit server opt-in và gates cần
thiết vẫn phải bật, kiểm admission/command/audit/actor/plan mỗi lần. Cancel dựa
trên persisted command + immutable audit và stable execution ID, vẫn gửi được
khi admission/Temporal gates rollback. Lost permission không biến cancel thành
quyền chạy mới. Không có implicit client connection hoặc browser input gateway.

GoalGateway dùng injected Temporal client, kiểm namespace. Retry start khi
AlreadyStarted và mọi signal đều kiểm immutable workflow start input/type/task
queue đúng envelope/proposal; workflow-ID collision không được coi là ACK.
Lỗi/timeout giữ pending hoặc dead khi hết retry, không giả delivered.

## Bằng chứng

- 62focused tests đạt/không skip/135.71s, gồm8ca dispatcher mới; runtime/SSE8/8.
- Lease/concurrent/default denial, reclaim expired lease, mất quyền, cancellation
  khi rollback, không finalize ACK sau token đổi.
- Temporal thật: lost ACK sau start được retry idempotent; input collision chặn
  cả start ACK và cancel signal, không nhận delivered giả.
- HTTP admission → start outbox → Temporal start → HTTP cancel → cancel outbox →
  Temporal signal → real pre-child DB projections → parent cancelled, iteration0.
  Không sửa DB để giả start/cancel ACK. Duplicate cancel không thêm command.
  Lịch sử parent replay đạt với kernel không đổi, không child/native attempt.
- Bộ hồi quy còn kiểm provenance/projection/Goal queue và real child drain,
  nhưng những ca riêng này KHÔNG cộng lại thành full parent/child acceptance.
- Warning ARQ Redis close() deprecated vẫn có, không làm test thất bại.

Populated restore dùng scripts/check_p63_dispatch_restore.py trên clone riêng:
đọc lại admission, audit và hai transport ACK, Goal M1 vẫn draft, child/attempt/
model/business rows0; không restore đè database chính. Chưa chạy full regression
của toàn repository mã mới; không dùng baseline cũ làm kết quả checkpoint này.

## Còn phải triển khai

Pre-child và first-iteration projection vẫn trả allow_iteration:false. Chưa
đăng ký dispatcher/Goal worker hoặc thay status API thành working executor.
Thiếu durable execution grant, real first-iteration approval/child ownership và
child start/cancel provenance, cancelled receipt/projection path, parent drain
reconciliation sau active child, crash/restart/unknown acceptance và UI.

Bước tiếp theo phải bổ sung trusted grant/projection theo checkpoint riêng,
không chỉ đổi false thành true hoặc bypass activity trong test. P6 chưa hoàn tất.
