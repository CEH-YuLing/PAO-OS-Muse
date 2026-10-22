# P6.3A — Policy và goal controller thuần

Ngày07/10/2026, `F:\PAO-ACOS`. **Checkpoint A LOCAL đã đạt.**
**P6.3 toàn bộ chưa hoàn tất.** Chưa có API/DB ledger/Temporal worker/UI `/goal`.

Thêm module `goals` riêng để giữ Studio/Task/Goal API hiện hữu không bị trộn
với một loop tự chạy. Đã có strict closed contracts, identity/version/actor pins,
max iterations/cost reservation/elapsed/deadline, criteria subset, proposal hash,
approval từng iteration, dedup receipts/decisions và manual-review cho unknown.
Không dùng lại Plan ID đã approve; không tăng deadline/policy khi replan.

37 unit tests đạt0.15s: policy boundaries/type rejection, Goal version,
mutable input/snapshot isolation, tất cả criteria phải đạt, cost0 và ceilings,
elapsed/deadline ưu tiên hạn sớm hơn, kiểm tra lại trước approve, clock regression,
duplicate/conflicting receipts/decisions, pin mismatch, cancelled/unknown/late
outputs và replan có duyệt. Đây là pure tests, không chứng minh durable ownership
hoặc xác thực receipt. Không import/khởi động service/model từ module mới.

Checkpoint trước code verified:
`.runtime/checkpoints/p0-20261007T132511-6d949aa5/manifest.json`,659sourcefiles,
94physicaltables,3artifacts,revision0038. Hạ tầng health/ready/Web200,
worker healthy; không có Docker error để cần sửa Docker. Không migration,
không chỉnh `.env`, không thêm config gate, không đổi API/OpenAPI/frontend.
P6.2 history replay7/7 đã đạt trên source mới; contract giữ248operations.

Budget receipts chỉ echo0cost; hash không thay authorization. Không gọi đây
là model budget enforcement hay kết quả mục tiêu nghiệp vụ thật. Các trạng thái
controller chưa được project vào bảng Goal M1. Giới hạn và bước B/C tại
[ADR](ADR-P63-BOUNDED-GOALS.vi.md).

Full backend regression: **767passed**, không skip,767.43s;3cảnh báo deprecation
ARQ.close từ dependency. Browser/UI không đổi và không nghiệm thu goal browser
trong lượt này. Không cộng bài P6.2 browser cũ vào con số backend này.

Checkpoint trước reload verified:
`.runtime/checkpoints/p0-20261007T134929-0acfde9e/manifest.json`,664sourcefiles,
94physicaltables,3artifacts,0038. Sau kiểm tra mọi loại active job0 và xác minh
PID/path/start time bằng launcher, reload riêng API21776/ARQ6208.
Web18064/Ollama1780 và Docker volumes giữ nguyên. API health/ready/Web200,
worker healthy; live full contract248/binding khớp và M2archive replay3/3.
StudioExecution/Command trên primary DB0, durable/dispatch/worker/Temporal
vẫn false. Không đăng ký goal controller vào worker hoặc đổi Goal M1 status.

Checkpoint source/DB sau chốt tài liệu được tạo và kiểm tra bằng
`scripts/backup_acos_checkpoint.py`, manifest ở `.runtime/checkpoints`.
M3/MCP thật/production gates vẫn chưa đạt; không tự mở trong checkpoint này.
Bước tiếp theo là **P6.3B Temporal + admission/ledger/API**, chưa triển khai.
