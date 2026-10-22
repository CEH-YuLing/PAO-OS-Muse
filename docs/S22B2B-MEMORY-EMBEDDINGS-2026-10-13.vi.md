# S2.2B2b — Shared embedding admission và Memory coverage

Chú thích hiện hành13/10: Knowledge index/query đã [đạt local0058](S22B2B-KNOWLEDGE-EMBEDDINGS-2026-10-13.vi.md).
B2b native coverage đóng local; next-only B3 quota Settings/integration theo
master. Nội dung/binding0057 và “tiếp theo” dưới đây là snapshot sau Memory,
không sửa ngược bằng chứng cũ hoặc làm lại checkpoint này.

13/10/2026, F:\PAO-ACOS. Cùng B2b, chưa nghiệm thu toàn embeddings/S2.
Scope hiện tại: standalone admission dùng TenantModelLease/model pool hiện có,
Memory create/edit/search/runtime recall/extracted facts. Knowledge index/query
còn chưa nối quota, là đầu việc tiếp theo duy nhất; không lặp metadata/legacy.

## Thiết kế

- Dùng chung 500calls/1M reserved-or-reported tokens/ngày UTC và2inflight mặc
  định của SME, gồm inference/probe/embedding; owner/admin đổi trong ceilings
  hiện có. Không tạo Run/LlmAttempt giả, database vault hoặc billing ledger mới.
- Migration0057 chỉ thêm nullable embedding_pin và mở rộng existing lease
  constraint/immutability trigger. Old LLM/probe pins là SQL NULL, không JSON null.
  Giữ row hashes trên toàn bộ cột cũ; downgrade có embedding history phải từ chối.
- 1lease cho mỗi embed thực sự, admission atomic trước adapter/I/O, TTL15s,
  hard provider deadline<=2s. Replay cùng scoped request key không resend kể
  cả expired. Timeout/cancel/offline/invalid retains debit, release slot; lost
  worker reaped bởi pool hiện có, không tự refund hoặc retry unknown work.
- Reserved input tokens = UTF-8bytes, bounded8KiB/call, conservative estimate,
  actual token usage/billing unknown, không zero. Adapter vector-only chưa lưu
  prompt_eval_count thành actual. SQL immutable pin giữ model/endpoint hash,
  purpose/Brain/brand/input hash, không raw prompt/vector/token/ciphertext.
- Local-only explicit loopback/http, không userinfo/path/proxy/redirect, cloud
  fallback/model download. Capture URL/model trước await; queued modern Run
  lưu embedding_engine pin mới. Old Run không pin thì lexical-only, không rewrite.
- Memory extraction có stable run/fact key, recheck actor/brand/Brain/session
  opt-out và đúng job attempt trước/sau embedding. Model extraction inference
  debit và fact embedding debit là hai provider invocations, không double bill
  cùng một invocation. Manual create/edit không giữ transaction qua model I/O;
  fresh authorize/CAS/tombstone recheck trước publication. Query lexical fallback
  không được tiết lộ facts nếu quyền bị thu hồi trong lúc embed.
- Vector768finite/nonzero/bounded được validate kể cả adapters thay thế. Native
  response<=64KiB; no raw provider diagnostics trong public resource status.
  Resource API báo memory_embeddings covered, knowledge_embeddings pending.

Đã đối chiếu [Ollama /api/embed](https://docs.ollama.com/api/embed) ngày13/10:
model/input/truncate=false/dimensions768/keep_alive0s giữ API hiện có, không
đổi embedding model mặc định, credentials hoặc provider auth flow. Endpoint
trả vector và có thể có prompt_eval_count; adapter hiện không coi đó là billing.

## Verification và rollout

**Shared admission + Memory coverage đạt LOCAL; Knowledge embeddings/S2 chưa đạt.**
Baseline0056/live334/bindingd41d7a1d/metadata0/M2replay3/3 đã refresh.
Prechange checkpoint `.runtime/checkpoints/p0-20261013T101959-7d757c13/manifest.json`:
971source/125physical/124business/3archives.
Tests và browser chỉ pao_test/Redis15/owned HTTP server, fake adapters, không
local/cloud inference thật hoặc Ads. Không đổi .env/secret/feature gates.

- Initial76tests:48pass/28fail do JSONB None thành JSON null ở old LLM/probe
  rows. Sửa ORM none_as_null=True, không bỏ SQL constraints. Lượt sau91pass/
  1fixture keyword sai; rồi187pass/1fixture sai tên bảng revocation. Sửa fixture
  bằng ORM Member thật, không bỏ assertion; late revoke vẫn phải403/no facts.
- **Final frozen189/189passed166.45s,0skip**,5ARQ.close deprecation warnings:
  dedicated embedding20 + Memory/gateway/chat/legacy/model quota/engines/fence/
  grants, gồm real ARQ. Default/no policy, A exhausted/B independent, token/
  concurrent/probe shared cap, cancel/timeout/provider/invalid/expiry/replay,
  SQL immutable pin/history, deny-before-factory, queued native embedding pin,
  terminal legacy và late role/actor/brand revocation đều đạt. Ledger test xác
  nhận final+extraction+embedding=3distinct calls, embedding replay không thêm.
- **25/25Node/runtime/SSE**, generated contracts và TypeScript đạt;
  isolated production build21/21 đạt. Existing React Hooks warnings còn.
  Không chạy lại full backend/full S2 integrated regression ở checkpoint này.
- **Browser2+1 đạt trên cùng frozen backend**: local chooser và model consent
  regressions đạt trong lượt đầu; Memory mới thất bại vì fixture chưa mở tab
  Activity hiện có, không quota/runtime bug. Sửa thao tác test, Memory browser
  riêng đạt26.73s: create/edit, quota exhausted lexical search, reload và switch
  SME B có cap riêng và không thấy memory A. Không gọi local/cloud model thật.
  Screenshot `.runtime/s22b2b-memory-browser-a4c4934e083e49f5a7f7109e93a8df1a/s22b2b-memory-mobile.png`
  đã xem: shell no horizontal overflow; sidebar/Memory panel không hiện ở mobile.
  Không gọi đó là full mobile Memory UI; S2.3 layout/navigation/help còn mở.
- Migration clone0056->0057->0056->0057 đạt: old-column hashes exact, rollback
  schema equivalent, populated embedding history từ chối downgrade và giữ
  toàn bộ schema/rows. Chỉ drop generated invocation-owned clone, retain dump.
- Predeploy checkpoint `.runtime/checkpoints/p0-20261013T103732-12192083/manifest.json`:
  979source/125physical/124business/3archives/0056. Exact row/schema restore đạt,
  primary unchanged. Idle/safe0active, additive0057 rollout giữ hashes mọi cột
  cũ, M2 archives3/3 và table counts; không tự tạo embedding admission/policy.
- Frozen backend binding `b79a09f2d06077fab4fe3095e8b2931bb9fe311d251b60aee1027db68da8571c`.
  Owned API6064/ARQ17380 thay theo executable/start-time/cmdline, Ollama giữ.
  API/ready200 và workerhealthy; initial Web500 do missing generated191.js.
  Verified owned Web16176 restart thành3528, giữ cache cũ tại
  `.runtime/web-cache-quarantine-d42b2716f8d84c9090e3e619c7abe3d3`, không xóa.
  Không khẳng định nguyên nhân sâu của cache corruption đã giải quyết vĩnh viễn.
- Sau recovery: API/ready/Web200, live0057/334/saved contract/binding/M2replay3/3
  và memory_embeddings/knowledge_embeddings pending khớp. Open Web phát sinh
  1legitimate model_catalogue released admission. Không reset hoặc delete history
  để làm gate0 xanh: checker so usageAPI với SQL và exact metadata row hashes
  trước/sau, 0policies/1lease giữ nguyên; native connection counts unchanged.
  Checker không discovery/inference, không sửa main. .env SHA256 vẫn
  `5672F74189BCEF6C110D4C434E956D4F324598EE3901B88BBD56902C945FBEA7`.
- README/master/unified/S2register/ADRs/P6/P7 current-head đồng bộ next-only
  Knowledge index/query. Final private source+DB seal được exact-restore và
  live-check sau cập nhật tài liệu. Không Git init/push/protected source,
  public deploy, external writes hoặc model benchmark thật. Dumps/keys private.

Gate phục hồi cuối đã hoàn tất sau gián đoạn xét duyệt công cụ: checker cũ
chưa allowlist0057 nên dừng trước khi tạo clone. Đã thêm explicit0057 (vẫn từ
chối unknown revisions),8pure checker tests đạt; không nới hash/schema checks.
Checkpoint `.runtime/checkpoints/p0-20261013T105206-b772dcb0/manifest.json` đạt
exact124business/125physical/3archives/0057, primary unchanged và bindingb79a09f2.
Live0057/334/M2replay3/3/metadata1lease0policies khớp và không bị checker đổi.
Final seal sau đoạn bổ sung này bao gồm checker allowlist/test và báo cáo cập
nhật; retained backup/source, chỉ xóa invocation-owned clone phục hồi.

## Tiếp theo duy nhất

Nối shared admission vào Knowledge.local_embed/index/query: pin source/version/
job/claim và actor/private Brain trước/sau I/O, replay stable chunk key, lexical
fallback có provenance, không giữ source/Brain/transaction lock qua model call.
Sau coverage đó mới đóng B2b; B3quota UI/S2.3/integrated finalS2 còn mở.
