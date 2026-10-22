# P0.3A.2 — Tách report scheduler khỏi HTTP API

Ngày: 05/10/2026. Phạm vi: F:\PAO-ACOS.
**Trạng thái: PASS local P0.3A.2; P0/P01 chưa hoàn tất, M4 chưa triển khai.**

## Thay đổi và giới hạn

- Chuyển schedule_reports sang modules/business/report_scheduler.py.
- report_api.py giữ compatibility alias; runtime.py import trực tiếp service.
- AST signature/thân scheduler trước/sau giống nhau; phần còn lại của report_api
  không đổi. runtime chỉ đổi import scheduler báo cáo so với checkpoint trước.
- Giữ batch 20, row lock, connection-version/permission, Telegram gate,
  timezone, request key/idempotency, build/queue report, next_delivery và xử lý ValueError.
- Không thêm Meta-enabled gate mới: scheduler vẫn đọc lịch enabled từ database
  như trước. Preflight xác nhận không có lịch sync/report được bật.
- Không đổi dispatcher cadence 10s, ARQ names/lease/timeout, models, config,
  dependencies, migrations, frontend hoặc generated API contracts.
- Thêm 3 characterization tests: legacy/runtime/service cùng function; không có
  lịch đến hạn thì không build/deliver; fresh import không mở network hoặc tải
  report_api/warehouse_api/Meta API/app/core API.
- **Telegram vẫn là dependency bắc cầu**: service dùng queue/permitted từ
  pao.telegram, module hiện trộn transport/domain và HTTP router. Không tuyên bố
  toàn worker sạch HTTP dependency. Không tách Telegram trong checkpoint này.

## An toàn trước thay đổi

9 nhóm job active/pending bằng 0; lịch ad_sync_schedules/ad_report_schedules
enabled bằng 0. Meta/write/Google Ads/Telegram/Temporal/autopilot đều tắt.
Live/source/saved UTF-8 OpenAPI bằng nhau trước rollout.

Backup/restore isolated đạt: **65 bảng, 3 skill archives, revision 0024**.
Giữ backup private F:\PAO-ACOS\.runtime\m2-20261005T133622-eeec5c5f.dump
(282528 bytes). Chỉ xóa database restore-test mới tạo, không restore đè local.

API/ARQ dừng sau idle gate và restart cùng source sau regression; Web/Ollama/
containers giữ nguyên. Launcher chạy upgrade head theo hành vi sẵn có, không có
migration mới; database vận hành vẫn revision 0024.

## Kiểm chứng

| Gate | Kết quả |
| --- | --- |
| AST scheduler/API/runtime | Chỉ di chuyển scheduler và đổi import dự kiến |
| Full backend regression | **332 passed**, không skip, 328.67s; pao_test/Redis DB15, PAO_ARQ_WALL_CLOCK_TESTS=1 |
| Real ARQ/Redis recovery | between 74.56s; during 97.45s; mỗi ca một tool claim |
| Runtime/SSE | **8/8 PASS** |
| Browser acceptance | **12 routes PASS**, API mock, local Web port 3200 |
| Full OpenAPI | Baseline/source/saved UTF-8/live cùng canonical SHA |
| Live archive replay | **3/3** M2 artifact cũ qua HTTP; hash/content giữ nguyên |
| Health/ready/Web skills | HTTP 200 |
| DB smoke | Counts/revision/artifact hashes trước/sau smoke bằng nhau; 0 job mới |
| Process identity | API PID 19684, ARQ PID 11244; interpreter/UTC-start-time/entrypoint đạt, worker startup confirmed |

OpenAPI SHA256:
bba6b2f7462658b6100a4e991cc3be92c058a385193236e29f948b66eb8f9bf1.

Backend execution binding trước:
05fb8787f2a47d49d69d07dc8106ab501c93c2b49129deb531f209e574e3ba8f.

Binding mới:
a91975922710d0b40b36dc5a1469101ff2c8244b9c9462e9d511a7b4d1cc8b4d.

Live skills/API binding khớp fresh-process source binding. Worker dùng cùng
interpreter/source và startup được kiểm; chưa có RPC đo riêng digest worker.
Không nới source guard, rebind jobs cũ hoặc sửa archive hashes.

Trong 70 preflight fingerprints, chỉ report_api.py/runtime.py thay đổi; 68
file khác giữ nguyên. Service và test là file mới. Không production frontend
build, không --roundtrip/downgrade local trong checkpoint này.

Công cụ kiểm PID ban đầu so local ticks với UTC ledger và báo mismatch;
đã đối chiếu launcher, sửa phép kiểm dùng ToUniversalTime và xác minh đạt.
Không sửa launcher hoặc restart vì lỗi công cụ kiểm này.

## Bước tiếp và rollback

P0.3A.1 và P0.3A.2 đã bỏ hai import trực tiếp runtime → warehouse_api/report_api.
Đề xuất **P0.3A.3: characterization và tách queue/permitted Telegram khỏi router**,
giữ compatibility alias và không bật bridge/gửi tin thật. Chỉ triển khai khi
người dùng yêu cầu tiếp; Tasks/conversations/models và các P khác chưa làm.

Không bật connector/lịch thật/Ads writes/M4/deploy công khai. Không sửa
F:\Apex\apex hoặc F:\Javis OS; bản gốc Apex git status sạch. Không commit/push.

Rollback bằng patch review riêng đưa schedule_reports về report_api và import
runtime về đường cũ; chỉ bỏ service nếu không còn imports. Idle/backup/restart
API và ARQ cùng source trước rollout; không reset --hard hoặc sửa dữ liệu/artifact.
