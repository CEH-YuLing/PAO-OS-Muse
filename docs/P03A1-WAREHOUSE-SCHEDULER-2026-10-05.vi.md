# P0.3A.1 — Tách warehouse scheduler khỏi HTTP API

Ngày: 05/10/2026. Phạm vi: F:\PAO-ACOS.
**Trạng thái: PASS local P0.3A.1; P0.3A chưa hoàn tất, P0.3A.2/M4 chưa triển khai.**

## Thay đổi

- Implementation schedule_warehouse chuyển từ warehouse_api.py sang
  [modules/business/warehouse_scheduler.py](../apps/api/pao/modules/business/warehouse_scheduler.py).
- warehouse_api.py giữ compatibility alias; test/script dùng import cũ tiếp tục hoạt động.
- runtime.py import service trực tiếp, bỏ cạnh runtime → warehouse_api.
- AST của scheduler trước/sau bằng nhau: giữ Meta enabled gate, batch 20,
  khóa connection và refresh schedule, connection-version permission,
  active-job guard, idempotency key, timezone/lookback và next_at.
- Không đổi cadence dispatcher 10s, ARQ job names/lease/timeout,
  models/migration/config flags hoặc bất kỳ API schema nào.
- schedule_reports còn trong report_api.py và runtime vẫn import nó:
  **P0.3A mới hoàn thành một lát cắt khi P0.3A.1 được nghiệm thu**, không phải
  worker đã loại hết dependency HTTP.
- Thêm 3 tests tại
  [test_warehouse_scheduler_boundary.py](../apps/api/tests/test_warehouse_scheduler_boundary.py):
  API/runtime/service function identity; disabled gate không dùng Session;
  fresh import không tải HTTP adapters hoặc mở network.

## Gate trước thay đổi

9 nhóm job active/pending được kiểm bằng 0; các flags Meta/write/Google Ads/
Telegram/Temporal/autopilot đều false. Full live/generated/saved UTF-8 OpenAPI
bằng nhau. Giữ các thay đổi P0.1/P0.2A/B hiện có, không reset working tree.

Backup/restore đạt: **65 bảng, 3 skill archives, revision 0024**.
Backup private được giữ:
`F:\PAO-ACOS\.runtime\m2-20261005T132116-058a3e6b.dump`, 282528 bytes.
Chỉ xóa database restore-test mới tạo; không restore đè hoặc migrate ACOS.

API và worker tạm dừng sau idle gate, sau đó restart bằng launcher hiện tại;
Web/Ollama/containers/data giữ nguyên. Launcher chạy alembic upgrade head theo
hành vi sẵn có nhưng không có migration mới; revision vẫn 0024.

## Kiểm chứng

| Gate | Kết quả |
| --- | --- |
| Scheduler AST | Không đổi signature/body |
| Full OpenAPI | Baseline/source/saved UTF-8 bằng nhau trước rollout |
| Targeted boundary tests | 3 passed, 1.20s |
| Full regression | **329 passed**, không skip, 334.02s; PAO_ARQ_WALL_CLOCK_TESTS=1, pao_test và Redis DB15 |
| Real ARQ/Redis recovery | between 78.55s, during 97.20s; mỗi ca một tool claim |
| Runtime/SSE | 8/8 PASS |
| Browser | 12 routes PASS bằng API mock trên ACOS 3200 |
| Restart/live replay | API/ARQ restart đạt; **3/3** artifact M2 cũ đọc qua HTTP, hash/content giữ nguyên, không tạo job mới |
| Live full contract | Baseline/source/saved UTF-8/live bằng nhau sau restart |
| Health/ready/Web skills | HTTP 200, DB giữ revision 0024 |
| DB smoke | Counts/revision/artifact hashes trước/sau smoke giữ nguyên |
| Process identity | API PID 22184, worker PID 15264; interpreter/start-time/entrypoint đúng, worker startup confirmed |

Không chạy --roundtrip, downgrade database local hoặc production frontend build
trong checkpoint này. Không dùng số test/build lịch sử làm kết quả mới.

Trong 69 preflight fingerprints source/contracts, chỉ warehouse_api.py và
runtime.py thay đổi; 67 files khác giữ nguyên. Scheduler service và test là
file mới. Generated contracts, app factory, reconciliation, launch scripts,
dependency/config packages, models/schema và frontend không sửa.

Binding trước:
`eb7f20fd85dd4a127e9ebb6d032524250fdc896a253d4ce74fb7cc1559eb4d55`.

Binding source sau extraction:
`05fb8787f2a47d49d69d07dc8106ab501c93c2b49129deb531f209e574e3ba8f`.

Không nới exact-backend-source-v1 guard, rebind jobs cũ hoặc sửa archive hashes.
Pool/engine nguồn dùng chung như trước; service vẫn import config/db để lấy
settings/Session, không tuyên bố đã loại mọi import-time initialization.

## Giới hạn và bước tiếp

Không tạo lịch/task/report/job nghiệp vụ mới trên ACOS trong smoke. Không gọi
Meta hoặc bật connector/M4. Source F:\Apex\apex và F:\Javis OS không sửa;
không commit/push. Đây là refactor local, không phải production acceptance.

Kế tiếp đề xuất **P0.3A.2: tách report scheduler**, giữ alias và các phụ thuộc
transport/permission rõ ràng. Telegram hiện có code domain/transport và router
trong cùng module; không khẳng định scheduler báo cáo sẽ sạch mọi dependency
HTTP chỉ bằng đổi import runtime. Chỉ chọn một lát cắt, kiểm đạt rồi mới tiếp.

Rollback qua review patch riêng đưa scheduler về warehouse_api và import
runtime về đường cũ, bỏ module mới chỉ khi không còn imports. Kiểm idle/backup,
restart API/ARQ cùng source; không reset --hard, downgrade hoặc sửa artifact.
