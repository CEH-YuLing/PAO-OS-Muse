# P0.2A — Extraction reconciliation đã nghiệm thu local

Ngày: 05/10/2026. Phạm vi: F:\PAO-ACOS.
**Kết quả: PASS local cho lát cắt P0.2A; không triển khai P0.2B hoặc M4.**

## 1. Thay đổi

- Implementation chuyển sang
  [modules/business/reconciliation.py](../apps/api/pao/modules/business/reconciliation.py).
- [pao/reconciliation.py](../apps/api/pao/reconciliation.py) là compatibility shim,
  re-export đủ 15 public symbols trước đây; không tạo model/hàm trùng.
- Hai package init chỉ khai báo docstring, không mở DB/config/runtime.
- [test_reconciliation_imports.py](../apps/api/tests/test_reconciliation_imports.py)
  thêm ba characterization tests: exports/type identity, HTTP router dùng cùng
  objects, và fresh import không mở network hoặc import config/DB/runtime.
- report_api.py giữ nguyên import cũ, URL, input/output, RBAC và behavior.
- AST và normalized source implementation bằng baseline HEAD e1eb473.
  Trong 177 fingerprints P0.1, chỉ file reconciliation.py cũ đổi; 176 file khác
  giữ nguyên. Ba backend files mới và một test file mới nằm đúng lát cắt.

Không thay dependencies, frontend, models, migration, job names, timeout hoặc
source binding policy. Không thay manifest skill hay hash artifact lịch sử.

## 2. Gate trước rollout

- API /ready và Web /skills HTTP 200 trước thay đổi.
- Revision 0024; không có run/tool/attempt/memory/sync/action/workflow active
  trong các trạng thái được khảo sát; pending/unknown tools/actions, waiting timer
  và outbox pending/processing cũng bằng 0 trước restart.
- Meta, Meta write, Google Ads, Temporal, Telegram và autopilot flags đều false.
- Backup/restore đạt: **65 tables, 3 skill archives, revision 0024**.
  Backup giữ riêng tại
  `F:\PAO-ACOS\.runtime\m2-20261005T122916-492f2c3c.dump`
  (282528 bytes). Chỉ database restore-test riêng do check tạo được xóa;
  backup giữ lại, không sửa database ACOS bằng thao tác restore/migrate.
- API và ARQ tạm dừng bằng stop_acos_local -Components api,worker sau idle gate;
  giữ Web/Ollama/containers/volumes và credentials.

## 3. Kết quả kiểm chứng mới

| Kiểm tra | Kết quả |
| --- | --- |
| Full OpenAPI sinh từ source trước/sau | Canonical SHA-256 bằng nhau, cả schema/default/SSE definitions |
| Full OpenAPI API live sau restart | Bằng baseline live trước extraction |
| Public symbol/type identity | Đủ 15 symbols, shim/service/router cùng model và function objects |
| Implementation AST/source | Giữ nguyên logic; chỉ chuyển path và thêm shim |
| Backend regression | **320 passed**, 321.83s; không skip |
| Real ARQ/Redis recovery | Bật PAO_ARQ_WALL_CLOCK_TESTS=1; between 74.66s, during 96.47s, mỗi ca một tool claim |
| Runtime/SSE | **8/8** |
| Browser acceptance | **12 routes PASS**, API được mock; không phải kiểm dữ liệu thật |
| Live /ready và Web /skills | HTTP 200 |
| Local old M2 artifacts qua HTTP replay | **3/3**, hash và nội dung giữ nguyên, không tạo job mới |
| DB trong smoke replay | Counts/revision/artifact hashes trước/sau smoke bằng nhau; revision 0024 |
| API + worker process | PID 4860 / 5468; executable, start-time identity và command đúng; worker startup marker có |
| Integration readiness cuối | Meta/write false, chưa App/connection/report thật; không gọi Meta |

Backend runner dùng pao_test và Redis DB15; không chạy --roundtrip hoặc downgrade.
Launcher có gọi alembic upgrade head theo hành vi sẵn có; không có migration mới
và local revision vẫn 0024. Không chạy production frontend build ở checkpoint
này vì không thay frontend; không tái sử dụng build lịch sử làm kết quả mới.

Browser lần đầu dùng default lịch sử 3100 nên connection refused; chạy lại đúng
PAO_FRONTEND_URL=http://127.0.0.1:3200/ đạt. Không sửa verifier. Các lần đọc Docker/
process metadata cần quyền host đã được thực hiện lại có quyền; không coi kết quả
permission denied là bằng chứng process hỏng.

## 4. Binding và replay

Binding cũ:
`f2a5c7b13cdf50289b4657928180b851aff15087ba4d099c349ef78d833bbfdc`.

Binding mới:
`10e8f0983e94b14841f0bb9faceb6bf406bb908ccfa4850e3f38e708a2f617a4`.

Digest đổi đúng thiết kế vì path/source trong pao thay đổi; không nới guard.
API catalog sau restart trả binding mới khớp process kiểm chứng mới.
Worker khởi động sau extraction từ cùng interpreter/source, identity/entrypoint
được kiểm; không có RPC introspection digest worker và không tạo local business
job để thử. Execution/recovery được kiểm riêng trên DB test.

Ba artifact terminal cũ vẫn đọc qua HTTP và đối chiếu hash với archive đã lưu.
Replay chỉ đọc lịch sử, không chạy registry/tools/model mới. Không rebind job cũ.

## 5. Đính chính kiểm tra encoding tại P0.2B

Ghi nhận ban đầu của P0.2A cho rằng OpenAPI live khác artifact
packages/contracts/openapi.json ở **đúng một field**:

`/components/schemas/SessionCreate/properties/title/default`

**Kiểm tra lại tại P0.2B ngày 05/10/2026:** file Git là UTF-8 đúng. Lệnh kiểm
tra trước dùng Path.read_text() không chỉ định encoding, nên Python trên Windows
đọc bằng code page mặc định và tạo khác biệt giả. Không phải lỗi trong artifact
hoặc backend. Đọc bằng encoding='utf-8' cho thấy saved/generated/live khớp.
Canonical hash live trước/sau và artifact khi đọc đúng UTF-8:
`bba6b2f7462658b6100a4e991cc3be92c058a385193236e29f948b66eb8f9bf1`.
Hash khi đọc sai encoding trong lần kiểm tra cũ (không phải canonical hash UTF-8):
`5cbc9059c1102d0bf1db29e5890e483f4958fcb7c0665033a944027b3489e489`.

Không sửa generated artifact/types ở P0.2A hoặc để xử lý đính chính này.
P0.2B dùng strict full contract gate với encoding UTF-8 rõ ràng. Không cần
checkpoint sửa chuỗi tiếng Việt hoặc regenerate contract vì khác biệt giả này.

## 6. Giới hạn và bước kế tiếp

P0.2A đạt extraction nhỏ local, không phải toàn P0 hoặc production/remote readiness.
M3 dữ liệu thật chưa đạt; M4 vẫn tắt. Không sửa F:\Apex\apex hoặc F:\Javis OS.
Không commit/push trong checkpoint này; các tài liệu P0.1 trước đó vẫn được giữ.

Tiếp theo đề xuất **P0.2B — app factory và router composition có compatibility
entrypoint pao.main:app**, kèm full contract gate dùng UTF-8 rõ ràng như đính chính
ở mục 5. Không tách models/db, bật connector hoặc tăng worker replicas cùng bước.

Nếu rollback: review patch riêng để đưa implementation về path cũ và bỏ shim/
package chỉ khi không còn imports, kiểm idle/backup và restart API+ARQ đồng bộ.
Không reset --hard, không sửa artifact hash hoặc downgrade database.
