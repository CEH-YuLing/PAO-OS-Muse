# P6 — Xác nhận hủy qua ARQ thật (local, fixed Echo)

Ngày kiểm chứng: 08/10/2026. Đây là checkpoint nhỏ, không phải nghiệm thu hết P6.

## Đã triển khai và kiểm chứng

- `studio/queue_cancel.py`: helper nội bộ nhận pool Redis từ server, suy ra job ID ổn định từ execution; không nhận tên hàm tùy ý từ người dùng.
- Kiểm tra workspace, quyền hiện tại, plan đã đóng băng, command hủy có audit và reservation trước khi thao tác hàng đợi.
- Gọi ARQ `Job.abort()` và chờ kết quả; yêu cầu đúng tên hàm, tham số, queue và kết quả hủy.
- Chỉ tạo immutable `p62_step_queue_cancel_ack` khi job payload, in-progress và queue member đều đã biến mất, đồng thời native DB outcome xác nhận cancelled.
- Worker Echo bắt cancellation để chốt native outcome khi cờ hủy đã được ghi. Shutdown thông thường không tự biến thành yêu cầu hủy của người dùng.
- ACK lưu lâu dài liên kết command, snapshot, native claim/outcome và hash; retry sau Redis result hết hạn không tạo thêm ACK.
- Job thiếu, sai định danh, timeout không worker: UNKNOWN, không có ACK. Late finish không ghi đè native cancellation.

## Bằng chứng lần chạy này

Lệnh pytest gồm `test_studio_queue_cancel.py`, `test_studio_arq_bridge.py`,
`test_studio_step_jobs.py`, `test_goal_claimed_cancel.py`:
**41 passed, 4 warnings, 96.24 giây**. Warning là ARQ dùng Redis `close()` deprecated.

Năm case mới dùng PostgreSQL `pao_test`, Redis database 15 và queue riêng:
running abort, queued abort, absent, mismatched và unserved timeout.
Running/queued dùng worker thật với `allow_abort_jobs=True`; không mock ARQ abort.
Các case thành công kiểm tra ACK một lần và retry sau xóa riêng retained result.
Case running còn kiểm tra finish đến muộn giữ cancelled.
Fixture test tạo native plan/projection qua API/DB; không tuyên bố parent Goal command
đã được Temporal ACK thực tế. Bài Temporal/ARQ bridge trong bộ hồi quy là luồng
completed/replay riêng, không phải chứng minh end-to-end Goal cancellation.

Read-only health: API health/ready/Web HTTP 200, worker healthy, Telegram disabled.
Idle checker: tất cả nhóm active jobs bằng 0, gồm Studio và Goal.
Không migration, không sửa `.env`, không bật live Goal/Studio worker, không chạy
model/tool/Ads/outbound. Runtime đang chạy vẫn là bản trước checkpoint mới.

Checkpoint bảo vệ trước sửa:
`.runtime/checkpoints/p0-20261008T151025-4b7a07bc/manifest.json`
(702 source files, 97 physical tables, 3 artifacts, revision 0039).

## Chưa đạt / bước tiếp theo

1. Helper chưa nối vào dispatcher/Temporal cancellation thực tế; chưa có endpoint hay poller mới.
2. Chưa nối ACK này vào Goal budget reconciliation: proof cũ vẫn `queue_ack_verified:false`.
3. Chưa nghiệm thu full regression với mã mới, restart/restore populated ACK, worker crash/network partition và toàn chuỗi parent → child → ARQ.
4. ACK chỉ cho adapter cố định `fixture_echo`, không chứng minh hủy được tác dụng phụ từ API bên ngoài.

Không đổi baseline 951 tests đã đạt của checkpoint trước thành kết quả của mã mới.
Không giải phóng reservation Goal chỉ dựa vào job biến mất khỏi Redis.
