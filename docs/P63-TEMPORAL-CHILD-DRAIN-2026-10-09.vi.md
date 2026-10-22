# P6 — Temporal child cancellation → ARQ ACK thật (local)

Ngày 09/10/2026. Đây là nghiệm thu một checkpoint child drain, không phải toàn
bộ parent Goal executor hay hoàn tất P6.

## Triển khai

DryRunBridge thêm tùy chọn nội bộ `require_queue_ack=True`, mặc định false để
không đổi nghĩa bridge/native cancellation cũ. Không thêm env flag, endpoint,
worker registration hoặc migration. Worker test opt-in có ARQ allow_abort_jobs
và giữ result đủ lâu để helper kiểm chứng; không suy luận ACK từ job biến mất.

Ở chế độ opt-in, activity bị hủy hoặc quan sát native cancelled sẽ gọi helper
abort/wait đã có. Chỉ nhận thành công khi immutable queue ACK được xác minh.
Timeout/missing result trả step_queue_drain_unknown; không ghi queue ACK.
Chế độ strict không tự tạo user cancel khi activity shutdown: vẫn yêu cầu
persisted authorized cancel command. Không sửa kernel hoặc tên activity P6.2.

Kernel P6.2 cũ có thể project child cancelled sau tín hiệu hủy ngay cả khi drain
không xác định; vì vậy projection cancelled KHÔNG đồng nghĩa queue đã dừng.
Goal queue reconciliation phải yêu cầu ACK riêng, thiếu ACK vẫn giữ reservation.

## Kiểm chứng

51 focused tests đạt, không skip, 192.08 giây; gồm3ca mới:

1. HTTP cancel → outbox dispatch thật → Temporal signal thật → cancellation
   activity → ARQ abort thật → immutable ACK/native outcome → child cancelled.
   Delivered command/attempt timestamp là kết quả dispatcher thật, không sửa DB
   giả ACK. Queue/in-progress rỗng, native attempt cancelled, M1 tasks vẫn draft.
2. Không có ARQ worker: Temporal xử lý hủy nhưng queue còn job, không queue ACK.
   Không coi child terminal projection là proof đã drain.
3. Strict drain không có user cancel: từ chối, không đổi cờ hủy/outcome/ACK.

Hai lịch sử Temporal mới được replay bằng kernel P6.2 không đổi. Fixture Temporal
dùng binary local đã có, SQLite riêng; PostgreSQL pao_test/Redis15 và queue riêng.
Không model/tool/Ads/outbound. Duplicate HTTP cancel không dispatch thêm command.
Các ca hồi quy Goal vẫn dùng parent projection/command fixtures; không tuyên bố
parent Goal end-to-end đã đạt. Runtime/SSE8/8. ARQ Redis close() deprecated warning
hiện có, không làm test thất bại. Chưa chạy full regression của toàn repo mã mới.

## Docker recovery và runtime

Engine ban đầu tắt, PostgreSQL/Redis không kết nối. Sau start Desktop, log mới
xác nhận lỗi socket dockerInference. CLI stop timeout20s; đã xác minh executable/
start-time, dừng đúng process Docker, kiểm hai directories không reparse chỉ có
socket0byte. Giữ nguyên bản cũ để hoàn tác:

- Docker/run.stale-3057c36e3e8e4080a6ae804bd83aef35
- docker-secrets-engine.stale-f6756e7cdaa04503bfac55a728be425d

Không xóa volumes/settings, reset/reinstall hoặc reboot. Engine29.4.3; khởi động
lại đúng ACOS PostgreSQL/Redis containers. Checkpoint trước startup verified:
`.runtime/checkpoints/p0-20261009T092055-6e26668b/manifest.json`
(708source files/97physical tables/3artifacts/revision0039).

Khôi phục API/ARQ/Web/Ollama local; Goal/Studio/Temporal execution gates vẫn tắt.
Web cold-start được warmup HTTP200 rồi rerun readiness nguyên vẹn. API health/
ready/Web200, workerhealthy, live source binding khớp; M2 archive replay3 đạt.

## Còn lại

Parent Goal dispatcher/child ownership/start/cancel và drain reconciliation
thực tế chưa được nghiệm thu end-to-end; chưa worker crash/restart/network
partition acceptance, full regression, Goal worker/UI hoặc P6.4–P6.7.
Không bật live Goal chỉ vì child fixture đã đạt. Không dùng Echo ACK để chứng
minh hủy tác dụng phụ đã gửi đến dịch vụ ngoài.
