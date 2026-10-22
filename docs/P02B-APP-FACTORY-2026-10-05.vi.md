# P0.2B — App factory và router composition

Ngày: 05/10/2026. Phạm vi: F:\PAO-ACOS.
**Trạng thái: PASS local cho checkpoint P0.2B; chưa triển khai P0.3A hoặc M4.**

## 1. Thay đổi có giới hạn

- [app.py](../apps/api/pao/app.py) chứa create_app(), lifespan và registry
  ROUTER_SPECS gồm 21 registrations (core router mới + 20 router registrations cũ).
- [core_api.py](../apps/api/pao/core_api.py) chứa 12 HTTP handlers cũ.
  AST body và signatures bằng source main.py trước extraction; chỉ đổi decorator
  app.* sang router.*. Không đổi auth, RBAC, transaction, cancel hoặc SSE behavior.
- [main.py](../apps/api/pao/main.py) giữ pao.main:app, create_app, lifespan,
  các handler aliases và alias OpenAPI callable.
- Mỗi application có state, dependency_overrides và OpenAPI cache riêng.
  Route definitions/schema models vẫn là shared source; không mutate registry
  router toàn cục khi một app đang phục vụ.
- Factory module import chưa tạo app hoặc import config/DB/runtime. create_app()
  lazy-load routers; các router cũ vẫn khởi tạo settings/ORM engine object và
  registry khi import, nhưng không mở DB/provider/Redis connection trong factory.
  Đây không phải đã chuyển toàn bộ stack sang dependency injection.
- Redis pool mở trong lifespan, thuộc từng app instance; finally đóng pool cả
  khi lifespan body raise exception. Không đổi cấu hình Redis/DB/worker.
- [test_app_factory.py](../apps/api/tests/test_app_factory.py) thêm 6 cases:
  strict saved UTF-8 contract, route uniqueness/order và handler identity,
  independent state/cache/overrides, pool cleanup thường/lỗi, fresh import/
  composition không mở network.
- Giữ mọi thay đổi P0.1/P0.2A; không xóa hoặc reset working tree.

## 2. Gate trước thay đổi

- Revision 0024; 9 nhóm active/pending jobs được kiểm đều bằng 0.
  Meta/write, Google Ads, Temporal, Telegram và autopilot flags đều false.
- API live/generated bằng nhau; đọc saved contract bằng UTF-8 cũng bằng nhau.
- Backup/restore trước refactor đạt **65 bảng, 3 skill archives, revision 0024**.
  Giữ backup private:
  `F:\PAO-ACOS\.runtime\m2-20261005T125706-cf618f13.dump`, 282528 bytes.
  Chỉ DB restore-test mới tạo được xóa sau check; không restore đè database ACOS.
- Dừng riêng API/ARQ sau idle gate, giữ Web/Ollama/containers/volumes.
  Không mutate DB nghiệp vụ để chuẩn bị factory.

## 3. Kết quả kiểm chứng

| Gate | Kết quả |
| --- | --- |
| Factory contract pre/post và saved UTF-8 | PASS full schema equality, không chỉ METHOD/PATH |
| HTTP handlers | 12/12 giữ signature/body AST; route decorators chuyển sang core router |
| Factory targeted tests | 6 passed sau điều chỉnh kiểm tra router representation |
| Full backend regression cuối | **326 passed**, không skip, 325.45s; bật PAO_ARQ_WALL_CLOCK_TESTS=1 |
| Real ARQ/Redis recovery lượt cuối | between 75.81s, during 96.22s, mỗi ca một tool claim |
| Runtime/SSE | 8/8 PASS |
| Browser acceptance | 12 routes PASS với API mock, URL ACOS 3200 |
| Local restart/read-only smoke/replay | API/ARQ restart đạt; 3/3 artifact M2 cũ đọc qua HTTP, không tạo job mới |
| Live full contract | Baseline/source-generated/saved UTF-8/live bằng nhau sau restart |
| Health/ready/Web skills | HTTP 200, local revision 0024 |
| Local smoke DB | Counts/revision/artifact hashes trước/sau smoke giữ nguyên |
| Process identity | API PID 24384, worker PID 2620; interpreter/start-time/entrypoint đúng, worker startup confirmed |

Lượt full đầu tiên: **325 passed, 1 failed**, 331.99s. Lỗi nằm ở test mới giả định
app.routes chỉ chứa APIRoute phẳng. FastAPI đang cài **0.141.1** dùng
included-router wrappers. Không có dependency upgrade trong checkpoint này.
Đã sửa test để kiểm source routers registry (bắt duplicates) và full OpenAPI,
không truy cập private wrapper internals hoặc giảm trần 133 operations.
Targeted 6/6 sau sửa; full regression chạy lại đạt 326/326 trước nghiệm thu cuối.

Không chạy production frontend build ở checkpoint này vì không thay frontend.
Không dùng build/test kết quả lịch sử làm kết quả mới. Backend tests dùng
pao_test và Redis DB15, không --roundtrip hoặc downgrade local.

## 4. Đính chính encoding từ P0.2A

Khác biệt default SessionCreate.title đã ghi trước đây do lệnh kiểm tra dùng
Path.read_text() với code page Windows mặc định, không phải artifact Git hỏng.
Saved OpenAPI UTF-8, source-generated và baseline live bằng nhau, canonical hash:

`bba6b2f7462658b6100a4e991cc3be92c058a385193236e29f948b66eb8f9bf1`.

Đã đính chính [P0.2A report mục 5](P02A-RECONCILIATION-EXTRACTION-2026-10-05.vi.md).
Không sửa openapi.json/schema.d.ts hoặc regenerate types để xử lý khác biệt giả.

## 5. Binding, ownership và giới hạn

Binding trước P0.2B:
`10e8f0983e94b14841f0bb9faceb6bf406bb908ccfa4850e3f38e708a2f617a4`.

Binding source sau extraction:
`eb7f20fd85dd4a127e9ebb6d032524250fdc896a253d4ce74fb7cc1559eb4d55`.

Digest thay đổi đúng policy exact-backend-source-v1. Không sửa pin, rebind job cũ
hay hash artifact lịch sử. API/ARQ phải restart cùng interpreter/source trước
live smoke; execution/recovery được kiểm trên DB test, không tạo business job
ACOS để chứng minh worker digest. Worker không có RPC digest introspection.

Chỉ main.py đổi trong 67 fingerprints code/contracts của preflight P0.2B;
app.py/core_api.py và test factory là file mới. P0.2A source giữ nguyên.
Models/Base/metadata (64 ORM tables), migrations, launch scripts, generated
contracts, packages/agent-config/skill-config và frontend không đổi.

Không sửa F:\Apex\apex hoặc F:\Javis OS, không bật M4 hoặc connector,
không commit/push. Đây là refactor local, không phải production/remote readiness.

## 6. Bước kế tiếp và rollback

Sau khi P0.2B đạt, đề xuất P0.3A: tách schedule_reports và schedule_warehouse
khỏi HTTP modules từng service, giữ shim, không đổi cadence/lease/job names.
Không tách models/db hoặc triển khai M4 cùng checkpoint scheduler.

Rollback bằng review patch riêng khôi phục main.py từ preflight và loại bỏ
factory/core files chỉ khi không còn imports; kiểm idle/backup và restart API/
worker cùng source. Không reset --hard, downgrade DB hoặc sửa binding lịch sử.
