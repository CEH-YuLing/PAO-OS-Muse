# S2.1A — Nghiệm thu local inventory và mapping preview

Ngày 11/10/2026. Target `F:\PAO-ACOS`. Trạng thái **local_accepted**.
Không sửa `F:\Apex`, Javis hoặc unrelated dirty changes; không commit/push.
Thứ tự chỉ do [master roadmap](PAO-MASTER-GAP-AND-ROADMAP.vi.md) sở hữu.
Thiết kế/inventory/gates tiếp theo: [ADR-S21A](ADR-S21A-CONNECTION-INVENTORY.vi.md).

## Đã triển khai

- Module `apps/api/pao/modules/connections`: identity metadata từ native model/
  MCP/Meta Ads/Google Ads rows; không tạo credential store/resolver trùng.
- GET inventory theo SME/manager, giữ native creator và private Brain ACL,
  projection boolean credential tồn tại thay vì load/decrypt ciphertext. Không
  trả endpoint, model/config secret, manifest hoặc account payload/key hint.
- POST mapping-preview kiểm connection/expected version/brand/grantee/account
  provenance cùng SME; chỉ SELECT, no-store, deterministic review hash và các
  blocker. Hash không thể dùng làm grant; luôn executable/grant_applied=false.
- Telegram/Ollama/Meta App/Google App có inventory descriptor installation-local
  tĩnh và yêu cầu mapping rõ. Không inspect secret/config presence hoặc gán SME.
- Model manager/version chưa có thì ghi null/blocker, không giả version1 hoặc
  owner. Giữ engine ciphertext hash fence đã có. MCP connection/tool permission
  không trở thành quyền dùng của nhân viên vì đã xuất hiện trong preview.
- JSON8KiB, fields đóng, validation không echo input; pagination bounded theo kind.
- App factory42routers/311operations; chỉ thêm2paths và schema MappingPreview.
  Đối chiếu ZIP S13 cuối: tất cả existing paths/components nguyên vẹn.
- Generated OpenAPI/TypeScript đồng bộ; không thay UI Settings trong checkpoint này.

## Kết quả kiểm chứng trên bản cuối

| Gate chạy trong lượt này | Kết quả |
|---|---|
| `check_s21a_tests.py`: inventory25 + factory/tenant/model/Meta App/Meta/Google/MCP regression | **111 passed / 0 failed / 0 skip**,64.01s |
| `check_s13_tests.py --corpus-only`: S13/job/SSE HTTP cleanup + factory | **26 passed / 0 failed / 0 skip**,35.81s |
| Engine contract + skill version guard + fresh-process recovery + Brain scopes | **43 passed / 0 failed / 0 skip**,30.13s |
| Pure/runtime/SSE Node suite | **25/25**, có8runtime/SSE; chạy cùng cả hai harness |
| TypeScript noEmit sau generated contract | Đạt |
| `PAO_BUILD_CHECK=1 npm run build` | Đạt; static pages21/21; cache riêng live Web |
| AST syntax các file S21A mới/ảnh hưởng | 8files đạt |
| Diff whitespace check | Đạt; chỉ Git LF/CRLF notices |
| Live inventory/source metadata/auth/input-redaction | Đạt,1active manager scope trên DB chính hiện tại |
| Live full contract/binding và M2 archive replay | Đạt,311operations;3/3archives;0048 |
| API health/ready và Web sau reload | 200/200/200;workerhealthy;Telegram bridge disabled |
| Idle trước/sau rollout | Tất cả active job/tool/outbox/unknown counters0 |
| Checkpoint + restore clone | 115physical/114business tables,0048,3archives; exact row hashes/schema equivalent;primary unchanged |

Các nhóm backend có tests trùng (ví dụ factory), không cộng thành số unique.
**Không chạy full regression hoặc browser acceptance mới trong checkpoint này**;
không dùng evidence S13/10/10 để gọi full suite hiện tại xanh. S13 suite ở đây có
HTTP uvicorn/disconnect/timeout thật; P7 synthetic voice/mic gate không được đóng.
Frontend không đổi màn hình; compile/types/build mới đạt, không có acceptance
flow Settings/grants vì chúng chưa triển khai.

Lượt đầu S21A:104passed/1failed do fixture BrainMember thiếu workspace_id, không
phải bỏ DB constraint. Đã bổ sung đúng workspace và6ca provenance/readonly/
foreign Brain/pagination/revoke; **chạy lại toàn bộ8file:111passed** trên bản cuối.
Không skip, xóa assertion hoặc làm lỏng permission/constraint để đạt.
Warnings còn: legacy React Hooks trong build và dependency ARQ deprecated.close
ở2real-queue S13 tests. Không tắt rule hoặc nâng dependency ngoài checkpoint.

## Rollout, config và checkpoint

Baseline đầu lượt API/ready/Web200,workerhealthy,idle0; Docker không lỗi nên
không recovery/restart Docker. Trước reload đã verified source+DB checkpoint:

`.runtime/checkpoints/p0-20261011T105506-b5441e71/manifest.json`

856sourcefiles,115physicaltables,3archives,0048. Exact restore114business tables
khớp hash/schema; primary unchanged. Chỉ clone
`pao_s03_restore_a204dfa49fb440be9ebfa5921fce0355` do invocation tạo đã dọn;
DB chính/dump/source/manifest được giữ. Snapshot này chứa code và docs trước
ghi trạng thái local_accepted, không phải snapshot tài liệu cuối.

`restart_acos_backend.ps1` kiểm executable/start-time cả hai processes và idle
trước khi stop; replacement API PID1920/worker3688. Không stop process wildcard,
đổi Web/Docker/schema/.env/flags hoặc sửa DB tay. M2 executable archives cũ giữ
nguyên, replay3/3; không tự repin history để phù hợp source mới.

Source/saved/live exact binding:
`cd6ba74d8dfdbad3f3f9dc9ab89f7eb200036cb8ffff7ceaaa7360a668aac913`.

`.env` SHA256 không đổi:
`5672F74189BCEF6C110D4C434E956D4F324598EE3901B88BBD56902C945FBEA7`.
Secret chỉ được kiểm hash, không xuất giá trị; .env/keys không nằm trong source ZIP.
Không provider calls, tin Telegram, Ads/spending/publishing hoặc public deploy.

## Ranh giới và bước tiếp theo

Đạt **S2.1A**, không tuyên bố S2.1 hay SaaS toàn hệ thống hoàn tất. Chưa lưu
identity mapping/grants, chưa migrate secrets, chưa grant cho nhân viên, chưa
có UI inventory/Settings mới, multi-bot, managed/BYO app, vault/quota/SLA hoặc
production acceptance. Live API gate trên1manager scope không thay corpus
hai SME thật trong pao_test; preview không xác minh provider/network.

Inventory giữ native ownership nên admin không thấy các connection của người
khác; không dùng nó để kết luận platform không có legacy orphan. Preview là
snapshot không lock authority: apply/execution phải kiểm lại actor/tenant/Brain/
connection/grant/version/account lúc thực hiện; no silent fallback.

**Tiếp theo duy nhất S2.1B:** persisted identity/reference + explicit mapping
apply + brand/account/member grants và execution fences, migration clone/rollback
sau checkpoint. Tiếp tục tái sử dụng các adapter/pins, không mở S2.2/S2.3/S3/S4
cùng lúc hoặc yêu cầu user chọn lại kiến trúc đã duyệt.

## Checkpoint niêm phong cuối

`.runtime/checkpoints/p0-20261011T105825-b3988c11/manifest.json` verified:
857sourcefiles,115physicaltables,3M2archives,0048, bindingcd6ba74d… khớp live.
Exact restore114business tables: hash/schema equivalent,primary unchanged,
external_calls=false. Chỉ clone invocation-owned
`pao_s03_restore_afc793e7189f4f7eb10cb4453acdf230` đã dọn; backup/source/manifest
giữ nguyên có thể phục hồi. Health/ready/Web200,workerhealthy,live inventory,
full contract/M2replay3/3 và hash.env chạy lại sau seal đều đạt.

Snapshot này chứa code và roadmap/ADR/README/register/acceptance đồng bộ
S2.1A local_accepted → S2.1B tiếp theo. Không đổi code/config sau seal;
chỉ bổ sung self-reference này vào báo cáo.
