# M4.1 — Thiết kế event ledger/outbox và gate khởi động

## Trạng thái ngày 07/10/2026

User đã cho phép tiếp tục M4. Code/migration0035 đã triển khai và M4.1 đạt LOCAL;
producer live vẫn tắt, chưa có consumer. Xem
[nghiệm thu M4.1](M41-LOCAL-ACCEPTANCE-2026-10-07.vi.md). Ban đầu baseline
không sẵn sàng; **Docker đã được khôi phục** cùng ngày theo quyền user cho phép:
Engine29.4.3, containers healthy, API/Web200, worker healthy, live contract và
replay M2 đạt3/3. Xem [runbook khôi phục](DOCKER-RECOVERY-2026-10-07.vi.md).
Checkpoint P5 gần nhất trước xử lý Docker
đã được xác minh ở lượt trước:
`.runtime/checkpoints/p0-20261006T154827-3e0a5648/manifest.json`.
Database đã được kiểm lại trước thay đổi M4.1 bằng checkpoint có restore:
`.runtime/checkpoints/p0-20261007T061230-fe0bac54/manifest.json`, revision0034,
89bảng vật lý, 3artifact. Đây là checkpoint rollback trước rollout0035.

M3 dữ liệu thật chưa đạt theo báo cáo M3 hiện hành. Lát cắt M4.1 dự kiến chỉ
chứng minh nền tảng transaction bằng fixture; không thay thế gate business/M3.
Không mở Ads, Telegram, MCP thật, public deploy hoặc P6 runner.

## Blocker đã quan sát

- PostgreSQL local port15432 từ chối kết nối; Redis16379 không sẵn sàng.
- Docker API pipe `dockerDesktopLinuxEngine` ban đầu không tồn tại.
- Đã khởi động Docker Desktop hiện có; backend gặp lỗi và shutdown toàn bộ engines.
- Log host ghi lỗi `initializing Inference manager` tại
  `AppData\Local\Docker\run\dockerInference`: `The file cannot be accessed by
  the system` và `The filename, directory name, or volume label syntax is incorrect`.
- User đã cho phép xử lý Docker và tự xử lý trước trong các lượt sau. Đã cô lập
  có thể hoàn tác các directory chỉ socket; không reset factory, xoá volume,
  shutdown WSL, sửa settings hoặc sửa reparse tag. Blocker Docker hiện đã gỡ.

## Thiết kế lát cắt đầu tiên

1. Phục hồi Docker theo phạm vi được user cho phép, giữ nguyên volumes/data.
   Chạy health, M3 readiness, live contract/replay và checkpoint mới; lỗi thì
   không chạy migration hoặc cập nhật business state.
2. Thêm module `pao/modules/events` riêng; không ghép event ledger vào SSE hay
   tạo scheduler thứ hai. Cờ `BUSINESS_EVENTS_ENABLED=false` mặc định, test opt-in.
3. Migration additive sau0034: ledger bất biến và outbox có FK scope composite.
   Không sửa nội dung Task/Tool/Ads hiện có; audit không chứa evidence/secret thô.
4. Envelope server-generated: event_id, type, schema_version, workspace_id,
   aggregate_type/id/version, actor, occurred_at, correlation_id, causation_id,
   payload_reference và hash. Không tin workspace/actor/version của client.
5. Chỉ producer `task.completed` ở bước này, bao phủ tạo task completed và
   transition completed sau kiểm tra evidence/criteria/approval hiện hành.
   Event và outbox ghi trong cùng transaction với TaskActivity/business state;
   rollback phải xoá cả ba thay đổi, không commit riêng trong event service.
6. Unique key theo workspace/type/aggregate/version. Publish lại cùng nội dung
   không tạo event/outbox thứ hai; trùng key nhưng khác nội dung phải fail closed.
   FK scope và immutable triggers chống đổi tenant hoặc sửa envelope bằng SQL.
7. Outbox mới chỉ pending, chưa có delivery worker/consumer hay outbound effects.
   Không tuyên bố đã đạt at-least-once delivery ở M4.1.

## Kiểm thử cần đạt trước đóng M4.1

- Flag off không tạo ledger/outbox; không thay đổi API contract cũ.
- Tạo/transition completed hợp lệ tạo đúng một ledger và một outbox pending.
- Task chưa đủ evidence/criteria, sai version, mất quyền hoặc sai workspace bị
  từ chối; không để lại event/outbox.
- Cùng transaction rollback không để task completed hoặc event/outbox mồ côi.
- Concurrent completion chỉ một version có hiệu lực; idempotent event không trùng.
- SQL update/delete ledger bị chặn; cross-tenant outbox FK bị chặn.
- Migration trên clone up/down/up giữ nguyên hash dữ liệu cũ; Alembic check đạt.
- Backend regression, runtime/SSE, browser Task và live contract/replay đạt.
- Checkpoint cuối verified; feature vẫn tắt nếu chưa được phép bật local.

## Các bước M4 sau đó — không gộp vào lượt này

M4.2: durable delivery/lease/consumer dedup, bounded retries/dead-letter,
permission loss và crash recovery; consumer đầu chỉ projection nội bộ không LLM.

M4.3: approval read projection hợp nhất Task/Tool/Ads qua adapters, giữ scope,
immutable hash/version/expiry và chính sách từng domain; không approve từ UI thôi.

M4.4: decision race/replay/revocation và executor permission recheck; event
`approval.requested`, `ads.analysis.completed` chỉ sau producer tests tương ứng.

M4.5: nghiệm thu tổng hợp duplicate events, restart, concurrent approve/reject,
stale policy/actor, observability/retention/rollback. Business acceptance vẫn cần
M3 dữ liệu thật. Không dùng fixture để đánh dấu M4 production hoặc mở P6 ngầm.

Quyết định implementation tại [ADR M4.1](ADR-M41-TASK-EVENT-LEDGER.vi.md).

Lượt tiếp theo đã triển khai/nghiệm thu M4.2–M4.5 LOCAL; xem
[nghiệm thu M4 tổng hợp](M4-LOCAL-ACCEPTANCE-2026-10-07.vi.md).
Các giới hạn/gate M3/production/outbound ở trên vẫn giữ nguyên.
