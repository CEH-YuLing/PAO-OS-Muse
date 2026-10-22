# P6.2 — Vận hành workflow echo cục bộ

Phạm vi: workflow tuần tự, dependency, approval từng bước, timer/deadline,
outbox bền vững và receipt echo. Không phải workflow gọi model, Ads, MCP,
shell hoặc automation nghiệp vụ. Task của plan vẫn draft; không mở frozen guard.

## Thành phần

- API nhận start/decision/cancel và ghi command cùng audit trong transaction.
- ARQ worker hiện hữu (`pao.runtime.WorkerSettings`) sở hữu cron dispatcher
  và function `execute_studio_echo` khi `WORKFLOW_WORKER_ENABLED=true`.
- `scripts/studio_temporal_worker.py` là worker riêng chỉ đăng ký workflow
  P6.2 và hai activity projection/bridge. Không đăng ký legacy automation.
- Temporal sở hữu wait/timer và thứ tự bước; Redis chỉ giao job ngắn.
  PostgreSQL giữ claim/receipt; không tin Redis result như bằng chứng nghiệp vụ.
- Không khởi động thêm dispatcher ngoài ARQ cron hiện hữu.

## Trước khi bật trên máy local

1. Tạo và kiểm tra checkpoint; xác nhận đúng `F:\PAO-ACOS`, DB0038,
   Docker/health/ready bình thường và không có job đang chạy.
2. Kiểm tra Temporal server riêng đang hoạt động tại `TEMPORAL_ADDRESS`,
   namespace đúng. Không mở cổng này công khai. Script khởi động worker không
   tự cài hoặc giả vờ khởi động Temporal server.
3. Giữ toàn bộ Meta/write/autopilot/business-event/unified-approval gates tắt.
4. Bật Studio/planning/durable/dispatch/Temporal/worker có chủ ý trong cấu hình
   local. Giữ `WORKFLOW_TEMPORAL_TASK_QUEUE=pao-studio-dryrun` khác queue legacy.
   Các flags mặc định trong `.env.example` đều false.
5. Restart API và ARQ sau thay cấu hình; gọi `start_acos_local.ps1` để khởi động
   thêm worker Studio. Launcher kiểm tra executable/PID/start time, ghi record;
   không đổi flag hộ người dùng và không làm mất dữ liệu Docker.
6. Status chỉ báo worker sẵn sàng khi có cả hai lease Redis (TTL20s), marker
   khớp hash nguồn và task queue. Flag true không đồng nghĩa worker đã sống.
7. Vào Skills → P6.2 runner, mở Plan ID đã lưu, xác nhận chỉ echo, start,
   duyệt từng bước. Theo dõi sequence, completed steps, commands và lỗi.

## Quy tắc khi lỗi

- Request chưa rõ kết quả: thử lại cùng command/request key. UI giữ nguyên
  command khi network lỗi; không tự gửi một quyết định khác.
- Pending chưa claim có thể enqueue lại với cùng execution ID. Running không
  enqueue lại. Claim60s hết hạn -> `worker_lost_unknown`, manual_review.
- ARQ chết sau receipt: receipt DB đã commit thắng; redelivery không claim lại.
- Không xóa ledger, sửa thời gian lease, chỉnh trạng thái DB hoặc reset workflow
  để ép retry. Không có nút retry side effect không rõ.
- Mất quyền/pin/schema không hợp lệ: fail closed; không chạy bước sau.
- Kiểm tra Docker trước nếu lỗi hạ tầng, theo runbook recovery hiện có;
  không xóa volume, reset Docker, reboot Windows hoặc dừng process không rõ.

## Rollback và drain

1. Tắt admission (`WORKFLOW_DURABLE_ENABLED=false`) và dispatch mới
   (`WORKFLOW_DISPATCH_ENABLED=false`); restart API/ARQ để áp dụng cấu hình.
2. **Giữ `WORKFLOW_WORKER_ENABLED=true` và Temporal server/worker hoạt động**
   để cancellation/reconciliation tiếp tục xử lý các execution đã nhận.
3. Gửi cancel qua API/UI; chờ acknowledgment và terminal state/receipt.
   Cancel accepted không có nghĩa side effect đã được hoàn tác.
4. Xem ledger/manual_review và kiểm tra idle. Chỉ khi đã drain mới tắt worker
   và dùng `stop_acos_local.ps1 -Components studio`.
5. Giữ backup, DB, Redis và logs; không xóa dữ liệu để rollback.

## Nghiệm thu khác với production

Fixture integration dùng pao_test, Redis15 và Temporal riêng; browser chuyển
toàn bộ API request đến HTTP fixture thật, không fabricate JSON response.
Production reboot/VPS, MCP thật, Meta OAuth/dữ liệu thật và model execution
là các gate riêng. Không dùng receipt echo như evidence của chúng.
