# ADR-P01 — Ranh giới module và extraction tuần tự

Ngày: 05/10/2026. Phạm vi: PAO-ACOS, P0.1.
Trạng thái: **Bản đồ P0.1 đã kiểm chứng tĩnh; extraction P0.2A đã nghiệm thu local**.
Xem [P0.2A acceptance](P02A-RECONCILIATION-EXTRACTION-2026-10-05.vi.md).
App factory P0.2B cũng đã nghiệm thu local:
[P0.2B acceptance](P02B-APP-FACTORY-2026-10-05.vi.md).
P0.3/P0.4/P0.5 local đã đạt theo lát cắt, xem
[P0 local acceptance](P0-LOCAL-ACCEPTANCE-2026-10-05.vi.md).
Production/reboot gate chưa đạt; không tuyên bố đã tách toàn monolith.

## 1. Bối cảnh

[Báo cáo P0.1](P01-STRUCTURE-AUDIT-2026-10-05.vi.md) ghi nhận package FastAPI
có 62 Python files, 133 HTTP operations và 64 ORM tables. API/worker đang dùng
chung models/config; runtime import scheduler từ HTTP modules. Hệ thống có
baseline local M0–M2 và M3.1 foundation, không đủ căn cứ thay stack hay runtime.

Đây là bổ sung cho [ADR-0001](ADR-0001-RUNTIME-OWNERSHIP-AND-AUTOMATION-OUTBOX.md),
[ADR-0002](ADR-0002-GOAL-TASK-EXECUTION.md) và
[ADR M2 replay](ADR-M2-RESULT-REPLAY.vi.md), không thay các invariant của chúng.

## 2. Ranh giới thiết kế

- HTTP adapters: validate schema, authenticate/authorize, gọi use case, serialize.
  Worker không import router hay request dependency để thực thi domain.
- Domain/use cases: rule và state transition, nhận context/DB/provider adapters rõ;
  không import app instance hoặc frontend.
- Persistence: một SQLAlchemy Base, Session/config source; metadata đầy đủ khi
  Alembic chạy. Không tạo package db/ cùng lúc còn db.py mà chưa có import plan.
- Runtime/dispatch: điều phối run/jobs, budgets và recovery; không sở hữu bản
  thứ hai của task/message/result. API giữ entrypoint pao.main:app tương thích.
- Integration adapters: network protocol và credential access; domain quyết định
  scope/policy. Không ép cả inference gateway và tool gateway thành cùng một object.
- Frontend feature modules dùng shared shell/runtime. Không rewrite UI khi tách backend.
- Brain Markdown tương lai là projection/export hoặc revisioned import; PostgreSQL
  tiếp tục giữ ACL/metadata/state. Không đặt secrets trong Brain.

Hướng thư mục sau nhiều checkpoint, **chưa phải tree hiện tại**:

```text
pao/
├── main.py                       Compatibility entrypoint
├── app.py                        App factory/composition (bước riêng)
├── modules/
│   ├── business/reconciliation.py Extraction đầu tiên đề xuất
│   ├── conversations/
│   ├── tasks/
│   ├── knowledge/
│   └── tools/
├── runtime/                      Chỉ tạo sau khi xử lý runtime.py/shim cũ
└── integrations/
```

Không tạo hàng loạt placeholder. Chỉ tạo directory cần cho extraction đã duyệt.
Không tạo runtime/ cùng tên runtime.py trong bước đầu; Python import resolution
phải được kiểm thử nếu sau này chuyển module thành package.

## 3. Checkpoint P0.2A — một service thuần, đã đạt local

Chọn `pao.reconciliation` làm lát cắt đầu tiên: không gọi DB/Redis/provider,
chỉ so sánh input/report, xử lý Decimal và scope/timezone/coverage. Đây là bước
thực hành boundaries, không triển khai connector hay thay logic M3.

Các việc theo thứ tự, khi được xác nhận:

1. Snapshot full OpenAPI/schema, imports/public symbols và các tests gọi module.
   Kiểm tra working tree trước; giữ mọi thay đổi không liên quan.
2. Kiểm tra idle ACOS, xác định backup/restore checkpoint trước restart hoặc
   thay đổi binding. Không dùng deploy_phase/deploy_stage lịch sử.
3. Di chuyển implementation sang modules/business/reconciliation.py; giữ module
   pao.reconciliation re-export đầy đủ public symbols và type identity.
4. Giữ URL /v1/reports/{report_id}/reconciliation-preview, payload, error/status,
   auth/RBAC, Decimal semantics và không thêm mutation/network call.
5. Không thay response models hoặc migration; route/API có thể dùng import cũ
   để chứng minh shim trước rồi cập nhật imports từng lượt sau.
6. Unit/API regression trên pao_test và Redis DB15, runtime/SSE và frontend
   contract checks; test non-member/wrong scope/error/replay phải vẫn đạt.
7. So full OpenAPI trước/sau; review phần schema/SSE RunEvent, không chấp nhận
   chỉ METHOD/PATH bằng nhau là đủ.
8. Khi cần restart: drain jobs pin cũ, backup/review; khởi động API + ARQ từ
   cùng source mới. Smoke readonly và đọc artifact M2 cũ, không tạo Ads actions.
9. Ghi báo cáo PASS/FAIL/SKIP, checkpoint và rollback; mới quyết định bước tiếp.

### Rủi ro pin source M2

`skills._execution_digest` hash path và nội dung **tất cả** backend Python source.
Thêm package/shim hoặc move file cũng đổi binding, dù logic không đổi.
EXECUTION_DIGEST tính một lần mỗi process; API và worker chạy khác source/restart
không đồng bộ có thể pin khác nhau. Không sửa hash hoặc nới guard để “cho test qua”.

Queued/running attempt hoặc run pin cũ không được âm thầm rebind/replan.
Phải kiểm idle và chính sách recovery trước rollout. Artifact terminal giữ
reader-v1 và snapshot cũ; không chạy executable cũ hoặc bổ sung dữ liệu hiện tại.
Nếu môi trường không thể drain/kiểm restore, dừng trước restart, không coi deploy đạt.

### Điều kiện đạt

- Không đổi method/path/schema, RBAC, job names hay DB revision.
- Shim imports và public type identity giữ tương thích; import graph không thêm cycle.
- Regression đạt, opt-in/skips được ghi riêng; không kế thừa số test lịch sử làm kết quả mới.
- Runtime/API/worker cùng binding sau restart; replay terminal không sinh side effects.
- Chỉ file trong lát cắt được đổi; source Apex/Javis không đổi.
- Rollback qua patch/revert riêng có review, không git reset --hard, không DB downgrade;
  drain/check binding trước restart rollback.

## 4. Checkpoint kế tiếp, không gộp vào P0.2A

- P0.2B: app factory và router registration contract, giữ pao.main:app và
  OpenAPI override. Đã đạt local với 326 tests không skip; factory module import
  thuần, Redis theo lifespan. Settings/ORM engine object/registry initialization
  qua các router cũ vẫn giữ như trước, kiểm soát tiếp ở bước riêng.
- P0.3A: tách schedule_reports/schedule_warehouse ra service; giữ shim API cho
  tests/runtime cũ, sau đó bỏ dependency runtime → HTTP từng lượt.
  **P0.3A.1 warehouse scheduler đã đạt local**, xem
  [acceptance P0.3A.1](P03A1-WAREHOUSE-SCHEDULER-2026-10-05.vi.md).
  **P0.3A.2 report scheduler đã đạt local**, xem
  [acceptance P0.3A.2](P03A2-REPORT-SCHEDULER-2026-10-05.vi.md).
  **P0.3A.3 Telegram queue/permitted đã đạt local**, xem
  [acceptance P0.3A.3](P03A3-TELEGRAM-HELPERS-2026-10-05.vi.md).
  Hai scheduler không còn tải API/router Telegram qua dependency này; P0.3A
  đạt phạm vi đã chọn. Ingest/collect/deliver/router vẫn chung module;
  chưa tuyên bố toàn backend sạch HTTP hoặc toàn P0 đạt.
- P0.3B: Task domain và conversations/state helpers sau khi có characterization
  tests; models.py tách cuối, giữ một metadata source và migration discovery.
  **P0.3B.1 call-map/characterization Task đã đạt local**, xem
  [acceptance P0.3B.1](P03B1-TASK-CHARACTERIZATION-2026-10-05.vi.md).
  P0.3B.2 đã tách 3 pure helpers với aliases và regression/replay đạt:
  [Task values](P03B2-TASK-VALUES-2026-10-05.vi.md). P0.3C đã tách run state/tool audit:
  [state/audit](P03C-STATE-AUDIT-2026-10-05.vi.md). Transaction ownership giữ nguyên;
  progress/default status/lock-order risks còn ghi riêng, chưa fix trong extraction.
- P0.4: catalog implemented/configured/healthy/accepted tách riêng;
  không suy healthy từ token có mặt. Đã đạt API/UI local:
  [catalog evidence](P04-CAPABILITY-EVIDENCE-2026-10-05.vi.md).
- P0.5: local observability/backup gates; supervisor/reboot production là gate
  chạy 24/7 riêng, không bắt Brain read-only local đợi production đầy đủ.
  [Local operations](P05-LOCAL-OPERATIONS-2026-10-05.vi.md) đạt local; người dùng
  chưa có môi trường reboot riêng, production gate vẫn chưa đạt.

## 5. Phương án không chọn

- Copy backend Javis hoặc chuyển toàn bộ sang SQLite: đổi authority và regression surface.
- Tách microservices/Kubernetes: thêm delivery/ops boundary chưa cần thiết.
- Tách toàn bộ 64 tables hoặc task_api trước: khó xác định nguyên nhân regression.
- Làm M4 cùng refactor: trộn thay đổi kiến trúc với quyền/hành động bên ngoài.
- Chạy script historical để “test nhanh”: có target DB/container cũ và mutation.
- Tạo thêm queue/runtime/Brain authority riêng: trái ownership đã chốt.

## 6. Gate lựa chọn M4

P0.1 không tự cho phép M4. M4 vẫn cần người dùng xác nhận riêng, trạng thái M3
và dữ liệu thật phù hợp, policy/approval/audit/dry-run/recovery đủ bằng chứng.
P0.2A đã được thực hiện và kiểm chứng riêng theo báo cáo acceptance; không có
quyền tự triển khai M4 từ kết quả refactor. P0.2B đã đạt local; P0.3A là đề xuất
checkpoint theo từng lát cắt. P0.3A.1/A.2/A.3 đã đạt phạm vi scheduler boundary.
P0 local đã nghiệm thu theo lát cắt; P1.1 là bước đề xuất, chưa triển khai;
không tự triển khai từ việc cập nhật tài liệu này.

