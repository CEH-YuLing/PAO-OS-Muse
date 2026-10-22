# P0.3A.3 — Tách Telegram permission/outbox helpers

Ngày 05/10/2026. Phạm vi F:\PAO-ACOS.
**PASS local P0.3A.3. Nhóm P0.3A scheduler boundary đã đạt phạm vi đã chọn;
toàn P0/P01 chưa hoàn tất. M4 không triển khai.**

## Thay đổi

- Chuyển nguyên hai hàm permitted/queue từ telegram.py sang
  modules/channels/telegram_helpers.py; telegram.py giữ compatibility aliases.
- Report scheduler dùng helper trực tiếp, không còn import pao.telegram.
- Namespace channels chỉ chứa helper quyền và durable outbox, không tạo runtime,
  scheduler, queue backend hay authority dữ liệu mới.
- AST hai hàm bằng nhau trước/sau; phần còn lại của telegram.py không đổi;
  report scheduler chỉ đổi import. Giữ quyền user active/member không viewer,
  UTF-16 chunk limit 3500, fallback rỗng, plain text/link-preview disabled,
  markup chỉ ở đoạn cuối và dedup ON CONFLICT DO NOTHING.
- Không đổi ingest/collect/deliver/bot_api, webhook/router, bridge, job cadence,
  schema/migrations/config/dependencies hoặc frontend.
- Thêm 4 boundary tests: alias identity; permission matrix; Unicode/chunk/final
  markup/dedup SQL/fallback; fresh helper import không mở network hoặc tải router.
- Cập nhật test report scheduler để yêu cầu không tải pao.telegram nữa.
  Tests Telegram/reporting hiện có tiếp tục kiểm nghiệp vụ và dedup thật trên pao_test.

## Gate an toàn

9 nhóm job active/pending đều 0; lịch sync/report enabled 0; Meta/write/Google Ads/
Telegram/Temporal/autopilot đều false. Bản gốc Apex git status sạch.
Backup/restore isolated đạt **65 bảng, 3 archives, revision 0024**.
Backup private giữ tại F:\PAO-ACOS\.runtime\m2-20261005T135807-be38ed24.dump,
282528 bytes. Chỉ database restore-test mới tạo được dọn; không restore đè local.

API/ARQ dừng sau gate, restart cùng source sau regression. Web/Ollama/containers
giữ nguyên. Launcher chạy upgrade head như trước, không có migration mới.

## Kết quả kiểm chứng

| Gate | Kết quả |
| --- | --- |
| AST helper/router/report service | Giữ logic, chỉ di chuyển helper và đổi import |
| Source fingerprints | 69 Python files trước thay đổi; chỉ telegram.py/report_scheduler.py thay đổi, 67 files khác giữ nguyên |
| Backend regression | **336 passed**, không skip, 357.16s; pao_test/Redis DB15, real-clock tests bật |
| Real ARQ/Redis recovery | between 72.94s; during 95.92s; mỗi ca một tool claim |
| Runtime/SSE | **8/8 PASS** |
| Browser | **12 routes PASS**, mock API, port 3200 |
| Live contract | Baseline/source/saved UTF-8/live OpenAPI bằng nhau |
| Replay artifact cũ | **3/3** qua HTTP; hashes/content giữ nguyên |
| Health/ready/Web skills | HTTP 200 |
| Database smoke | Counts/revision/artifacts giữ nguyên; revision 0024; 0 job mới |
| Process identity | API 13180, worker 16644; interpreter/UTC-start-time/entrypoint đạt; worker startup confirmed |

Full OpenAPI SHA:
bba6b2f7462658b6100a4e991cc3be92c058a385193236e29f948b66eb8f9bf1.

Binding trước:
a91975922710d0b40b36dc5a1469101ff2c8244b9c9462e9d511a7b4d1cc8b4d.

Binding mới:
395487f16b9623ceef7244992c10a92f33c06907902ae547b868a77680253a6e.

Live API binding khớp fresh-process source. Worker identity/source/startup kiểm
trực tiếp, chưa có RPC đo riêng worker digest. Không nới pin, rebind jobs cũ,
sửa artifact hoặc tạo job nghiệp vụ trong smoke.

## Giới hạn và bước tiếp

P0.3A đạt **phạm vi hai scheduler và helper phụ thuộc**: runtime bỏ import
warehouse_api/report_api và report service không tải Telegram router.
Không đồng nghĩa mọi module/backend sạch HTTP hoặc toàn P0/P01 hoàn tất.
telegram.py vẫn trộn ingest/collect/deliver và router; chưa tách bridge toàn bộ.
Helper vẫn dùng shared ORM models, không phải hoàn tất dependency injection.

Không chạy production frontend build, --roundtrip/downgrade local, gửi Telegram
thật, bật lịch/connector/Ads writes/M4/deploy công khai. Không sửa bản gốc
F:\Apex\apex hoặc F:\Javis OS; không commit/push.

Bước đề xuất **P0.3B.1: lập call-map và characterization Task domain** trước
khi chọn helper nhỏ để extraction. Không di chuyển toàn task_api/models một lượt.

Rollback bằng patch review đưa helpers về telegram.py và report import về
đường cũ, bỏ module mới chỉ khi không còn consumers; idle/backup/restart API
và ARQ đồng bộ. Không reset --hard, sửa database hoặc archive hashes.
