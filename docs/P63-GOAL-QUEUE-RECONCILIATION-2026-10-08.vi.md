# P6 — Đối soát Goal bằng ACK hủy ARQ (local)

Ngày 08/10/2026. Checkpoint này không phải nghiệm thu toàn bộ Goal → Temporal →
ARQ, không phải hoàn tất P6.

## Thay đổi

`goals/cancel_recovery.py` thêm entry point nội bộ `reconcile_cancelled_queue`.
Hai entry point native trước giữ nguyên nghĩa. Không endpoint, poller, schema
migration hoặc live worker registration.

Trong một transaction, khóa Goal rồi child, reauthorize original actor và người
gửi lệnh hủy, xác minh admission/plan/claim/slot/projection cùng delivered
parent/child cancel command và audit. Mọi step đã reserved phải có immutable
queue ACK đúng execution, snapshot, native outcome/claim và child cancel command.
Step đã claim còn phải đạt native attempt/input/lease/timestamp checks.
Không có queue ACK thì từ chối queue mode, dù DB đã cancelled.

Đủ bằng chứng mới ghi immutable `cancelled_queue_reconciled`, ghim ACK ID/hash,
đánh dấu `queue_ack_verified:true` và release ceiling một lần. Retry tái kiểm
quyền/bằng chứng; status/reason/sequence vẫn dừng, không resume hoặc complete
Goal M1. Cost0 chỉ fixed dry-run Echo, không phải billing thật. UNKNOWN, mất
quyền, thiếu command ACK hoặc attempt sai giữ khoản dự phòng.

## Kiểm chứng

- 43 focused tests đạt, không skip, gồm7ca mới trong test_goal_queue_cancel.py.
- ARQ/Redis thật, pao_test, Redis15, queue riêng: trước/sau claim, concurrent
  reconciliation và retry release một lần; thiếu queue ACK, mất quyền,
  parent/child command chưa ACK hoặc attempt sai đều không release.
- Parent projection và parent/child delivered-command trong ca mới vẫn fixture
  rõ ràng, không phải chứng minh Temporal cancellation thật.
- Hai populated dump/restore profiles claimed/unclaimed hash exact trên96bảng
  snapshot. Retry sau restore giữ ledger, Goal M1 vẫn draft; trigger chống sửa
  Goal audit được kiểm. Profile unclaimed còn kiểm trigger chống sửa queue ACK.
- Runtime/SSE8/8. API health/ready/Web200, workerhealthy, Telegramdisabled;
  tất cả nhóm active jobs trên database chính bằng0.
- Warning hiện có: ARQ dùng Redis close() deprecated, không làm test thất bại.

Không sửa .env, không gọi model/Ads/MCP/outbound, không migration hoặc restart
runtime hiện tại. Chưa full regression mã mới; không dùng số951 của baseline cũ
làm kết quả checkpoint này.

## Tiếp theo

1. Nối bridge cancellation và kiểm Temporal child drain thực tế.
2. Nối parent Goal dispatcher/cancel/reconciliation; nghiệm thu end-to-end,
   timeout/disconnect/kill/restart, giữ tương thích kernel/history cũ.
3. Full regression, populated restore và live source-contract/replay trước
   đăng ký worker hoặc mở UI chạy Goal.

Live Goal gates vẫn tắt. Queue ACK không chứng minh hủy được tác dụng phụ đã gửi
đến dịch vụ ngoài và không áp dụng tùy tiện cho model/tool adapter khác.
