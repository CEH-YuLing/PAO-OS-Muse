# S2.2B2b — Đóng legacy inference quota bypass

Chú thích hiện hành13/10: shared embedding admission và Memory coverage đã
[đạt local0057](S22B2B-MEMORY-EMBEDDINGS-2026-10-13.vi.md). Phần “tiếp theo” cuối
báo cáo này là snapshot sau legacy guard; hiện chỉ còn Knowledge index/query
trong embeddings. Không sửa ngược kết quả/binding0056 bên dưới.

13/10/2026, F:\PAO-ACOS. Đây là guard cho chế độ không có kế toán AI,
không phải thêm engine mới hoặc bắt buộc toàn PAO dùng cloud. Cùng B2b;
embeddings và full S2 chưa nghiệm thu từ thay đổi này.

## Thay đổi và hành vi vận hành

1. Không có TenantResourcePolicy row vẫn áp dụng default caps, không exemption.
   `gateway_for_workspace` là đường thực thi không pin/ledger đã deprecated:
   native source-reference denial giữ trước, sau đó luôn từ chối unaccounted
   routing **trước decrypt hoặc local/cloud factory**, không fallback.
2. `CHAT_FEATURES_ENABLED=false` không là cách bỏ qua kế toán. Runtime/gateway
   và legacy Memory extraction từ chối với `tenant_resource_accounting_required`,
   kể cả ctx gateway injection. Cached AccountingEngine kiểm flag mỗi begin.
   Guard này không tắt native management probe: probe vẫn billed B1/fixed96 và
   owner/admin/registered-source restrictions. Không thay .env hoặc bật flags.
3. Runtime không repin model/policy cho queued unknown work khi flag bật lại;
   phải có engine snapshot với chat_policy đã lưu. Lịch sử/legacy_unknown vẫn
   đọc được, không rewrite/revive/requeue tự động. Tạo một yêu cầu mới rõ ràng
   trong mode accounted nếu cần chạy lại, giữ nguồn/model/Brain/brand/quyền đúng.
4. Known modern inference tiếp tục AccountingEngine/lease/hard deadline/usage
   unknown, đúng pool SME. Pure knowledge excerpts không gọi inference vẫn giữ;
   không áp guard legacy một cách mù quáng lên nhánh knowledge-no-model.
5. Legacy Memory job thất bại terminal trước gateway; flags tắt trước publication
   thì không lưu facts. Accounting/replay errors terminal, không retry theo một
   default connection mới. Không tạo quota rows cho requests chưa gọi model,
   không xóa lịch sử/debit để refund. Scoped vectors/lexical behavior chưa đổi.
6. Metadata/model/read status phản ánh unaccounted_legacy_denied, không gộp
   embeddings vào accepted model quota. No new migration/route/model/default/
   provider endpoint/credential/OAuth/grant. 0056/334/43 giữ nguyên.

## Test fixture thay đổi có chủ đích

Các positive engine/fence/grant/Memory tests dùng engine+chat features enabled
như runtime hiện tại; cloud positive tests tự owner-opt-in cloud_allowed bằng
chat Settings API. Mock adapters có provider/model/max_tokens/extraction contract
đúng. Không monkeypatch guard/SQL FK/quotas/Brain permissions để làm xanh.
Giữ tests stream/planner/source late revoke/partial/cancel/real ARQ và source
fence component extract riêng; production không dùng unaccounted workspace
resolver. Legacy tests mong terminal denial/no factory/no facts, không còn
mong legacy inference tự chạy khi không có ledger. Historical snapshots không
được sửa để thêm pin, và không xóa các assertion quyền/grant/privacy.

## Verification

Baseline live0056/334/binding1bd51278/main metadata0/native counts unchanged và
M2replay3/3. Checkpoint `.runtime/checkpoints/p0-20261013T093440-d154ab61/manifest.json`:
969source/125physical/124business/3archives/0056; exact row/schema restore,
primary unchanged. Chỉ drop generated clone; giữ private dump/source backup.

Initial legacy guard regression65pass/30fail do old fixture accounting-off
assumptions; đã sửa explicit fixture mode/privacy và dedicated legacy assertions.
Affected engine/Memory/fence/grants96passed81.30s. Corpus93pass/1fail do ARQ
qualified function registration và Windows SIGUSR1 fixture; sửa test registration
explicit name và SIGTERM alias, không đổi production worker. Dedicated
12passed9.84s gồm real ARQ legacy A deny/accounted B success, absence of policy,
cached mode-off/no repin/terminal Memory. 25Node/runtime/SSE, contracts/TypeScript
và isolated production build21/21 đạt; inherited Hooks warnings còn.

Frozen affected regression: **472passed/1failed/9warnings369.60s** trên pao_test/
Redis15. Một failure là test monkeypatch namespace cũ `pao.memory.gateway_for_workspace`
sau khi production đã bỏ import đó, không phải provider/quota/Brain assertion.
Đã đổi spy sang namespace thật `pao.model_router.gateway_for_workspace`; pytest
đang chạy đã import bản fixture cũ nên kết quả lượt đó vẫn ghi fail. Fresh rerun
toàn chat management + legacy corpus **38/38passed32.56s**,1ARQ.close warning;
backend không đổi giữa broad và focused rerun. Không tuyên bố đã chạy một lượt
473/473 hoặc full backend xanh mới. Ba pure Knowledge grounded/history-redaction/
feature-off tests thêm **3/3passed5.43s**, không LLM, giữ Brain ACL.

**Browser4/4passed116.98s**: local selection/quota/reload/SME switch/mobile,
cloud metadata Settings và model/MCP consent/replay/revoke. Real HTTP/DB riêng,
0local/cloud provider calls. Mobile screenshot
`.runtime/s22b2b-local-browser-44471bba436e4607ab533f76ab519540/s22b2b-local-mobile.png`
đã xem: no horizontal overflow nhưng explanatory chat text còn clipped; S2.3
layout/error/help và quota form chưa được nghiệm thu từ browser gate này.
Intermittent browser route/toast gap lịch sử chưa root-cause, không gọi đã sửa.

Predeploy checkpoint `.runtime/checkpoints/p0-20261013T101115-051da0bf/manifest.json`:
971source/125physical/124business/3archives/0056. Exact row hashes/schema definitions
restore trên generated owned clone đạt; primary unchanged. Retain private dump/
source; chỉ drop database clone do invocation tạo. Source binding:
`d41d7a1db39532071d28b43ee9505c0a62f0a2356dc1c4afcb83714c179904c4`.
Idle/safe gate0active, thay đúng owned API16812/ARQ17768 bằng executable/start-time/
cmdline check. Giữ Web/Ollama. API/ready/Web200,workerhealthy; live saved contract
334/schema0056/current binding và M2replay3/3 khớp. Read-only resource status báo
unaccounted_legacy_denied, pending embeddings. Main metadata policies/leases0,
native connection counts không đổi; checker không discovery/model inference.

`.env` hash giữ `5672F74189BCEF6C110D4C434E956D4F324598EE3901B88BBD56902C945FBEA7`.
Không migration/sửa tay main database, bật flags, sửa credentials, external writes,
Git init/push, protected source hoặc public deploy. README/master/unified/S2
register/ADRs và P6/P7 current-head đã đồng bộ next-only embeddings; lịch sử giữ.
Final source+DB seal nằm trong private `.runtime/checkpoints`, được exact-restore
và live-check riêng sau cập nhật tài liệu; không chia sẻ dump/credential.
Legacy guard đạt local, không full B2b/S2/SaaS production acceptance.

## Phần tiếp theo duy nhất

**Embeddings** trong B2b: Memory.vectorize/retrieve, Memory CRUD/extraction vectors,
Knowledge.local_embed/index/query. Cần standalone scoped admission/ledger/lease
và deadline trước embed, không giả lập Run để được tính quota và không double
charge extraction/inference. Giữ lexical fallback, private Brain/user/brand ACL,
local-only pin và unknown usage/billing semantics. Không tắt vector search rồi
gọi đó là hoàn thiện. Sau B2b là B3 quota UI/S2.3/final integrated S2; không mở
M6/P8 hoặc lặp metadata/security/local discovery đã đạt.
