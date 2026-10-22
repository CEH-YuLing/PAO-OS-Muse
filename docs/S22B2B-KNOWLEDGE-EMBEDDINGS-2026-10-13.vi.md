# S2.2B2b — Knowledge embeddings quota và queued source pins

13/10/2026, F:\PAO-ACOS. Tiếp tục phần còn lại của B2b; không engine/quota
ledger mới, không bắt đầu lại metadata/legacy/Memory đã đạt. B3/S2.3/finalS2
và SaaS production vẫn nghiệm thu riêng. Native B2b coverage đạt LOCAL theo
gates dưới đây; không dùng số test như chứng nhận SaaS production/fullS2.

## Thay đổi

- Knowledge.local_embed/index/query đều dùng shared TenantModelLease admission
  đã đạt0057: cùng per-SME model daily calls/token reservations/concurrency với
  inference/probes/Memory, TTL15s/deadline<=2s, actual usage/billing unknown.
  Không synthetic Run/LlmAttempt, cloud router, tool grant hoặc model download.
- Additive0058: index job embedding_engine/model+URL pin và generation; chunk
  embedding_binding hash pin. Không backfill old queued pins/vector bindings,
  rewrite source/version/content/quote/hash, đổi existing unique job ownership.
  Old job thiếu pin vẫn lexical-only. Explicit confirmed rebuild tăng generation
  đúng1, có actor/pin mới; worker retry không tăng generation hoặc tự repin.
- SQL trigger giữ job identity/pin/actor bất biến trong cùng generation, chỉ
  cho intent mới khi không running, queued/attempts0/no claim/no lock. Downgrade
  khi có pin/generation/binding mới từ chối để giữ history. Old column hashes giữ.
- Modern ARQ delivery pin generation trong payload và job id. Old/unversioned
  delivery không được consume một rebuild mới; stale generation không claim.
  Embedding key stable job/generation/chunk, không dùng attempt/claim như quyền
  resend. Cancel/worker-lost/retry/replay giữ debit, không blind resend unknown.
- Mỗi chunk recheck actor/member/private Brain/brand/source/hash/job claim trước
  và sau provider I/O. Preserve16chunks/18s bounds; quota/offline commits lexical
  index, partial có error code sanitized. Không xóa vector tốt khi rebuild lỗi.
- Query chỉ semantic trên current authorized chunks đúng model+endpoint binding;
  không trộn vector spaces khi host setting đổi. No eligible vector/old binding,
  missing queued Run pin/offline/quota thì full-text fallback, không cloud egress.
  API queries là intent mới; grounded Run dùng stable key và immutable run pin.
- Query release caller read transaction trước model, không commit/rollback pending
  unrelated writes: pending write trả409. Collect/rank/semantic uses short-owned
  sessions; fresh ACL/citation checks trước disclosure, kể cả lexical fallback.
  Grounded Run rechecks cancel/channel/Brain trước và sau lookup/publication.
- Không đổi routes/contracts/provider endpoints/model defaults/.env/credentials.
  Resource status báo knowledge_embeddings covered; global host scheduling vẫn
  pending, không lấy scoped caps làm production fairness hoặc provider billing.

## Verification

Prechange live0057/334/bindingb79a09f2/M2replay3/3/metadata1lease0policies khớp.
Checkpoint `.runtime/checkpoints/p0-20261013T135539-8897f110/manifest.json`:
979source/125physical/124business/3archives/0057, private source/dump retained.
Focused Knowledge+Memory/shared-core48passed56.54s. Dedicated fixture ban đầu
thiếu sources_on registration:48pass/15setup errors, không là guard failure.
Đăng ký dependencies đúng, dedicated15/15passed21.23s,1ARQ.close warning;
gồm A/B caps, partial lexical, pin SQL, cancel/recovery và real ARQ generation.
Positive regular-chat fixture sau Knowledge-off chuyển sang explicit accounted
mode/Ollama-compatible Fake; vẫn assert không gửi old source excerpts, không
bỏ history/ACL assertion hoặc bật thật. Test dispatcher assert generation mới.

Owned migration clone0057->0058->0057->0058 đạt: old-column hashes exact,
rollback schema equivalent, populated pin downgrade refused, main unchanged.
Chỉ drop invocation-owned clone, dump giữ private.

- **565passed/0failed/0skipped465.43s** frozen integrated B2b regression trên
  pao_test/Redis15: Metadata/cloud/MCP/local/credential guards, model/read quota,
  generations/grants/private Brain/legacy/Memory/Knowledge/factory, real ARQ.
  11inherited ARQ.close warnings, không bỏ case khó hoặc gọi đây là full backend.
- **25Node/runtime/SSE**, contracts/TypeScript và isolated build21/21 đạt.
  Generated `.pao-build-check/BUILD_ID` đã xác minh; Web3200 cache không bị build
  ghi vào. Existing Hooks warnings và root pages-dir lint notice còn, build exit0.
- **Browser2+1 đạt cùng frozen backend**: Memory và MCP regressions đạt trong
  lượt đầu; Knowledge fail vì 2selector SME cùng nhãn trên trang Knowledge.
  Chọn đúng topbar control, giữ assertion, Knowledge rerun đạt19.47s. Hybrid,
  quota-denied lexical fallback, reload/SME switch/no cross-Brain quotes và
  explicit rebuild queued generation2 đạt. Browser rebuild chỉ nghiệm thu enqueue;
  actual worker execution nghiệm thu riêng bằng real ARQ dedicated test.
- Screenshot `.runtime/s22b2b-knowledge-browser-80190a869f3241faa0492d0dbb3387e6/s22b2b-knowledge-mobile.png`
  đã xem: Brain B/quote B/hybrid, no horizontal overflow. Floating chat composer
  che một phần controls trên mobile, giữ là S2.3 layout/navigation gap; không
  dùng no-overflow làm full mobile acceptance hoặc gọi UI đã tối ưu hoàn toàn.
- Predeploy checkpoint `.runtime/checkpoints/p0-20261013T142649-8e750bd4/manifest.json`:
  986source/125physical/124business/3archives/0057, exact rows/schema restore đạt,
  primary unchanged.8pure restore-checker tests đạt,0058 explicit allowlist;
  không bỏ hash/schema comparison để làm xanh revision mới.
- Idle/safe0active. Additive0058 rollout old-column hashes/M2archives/table counts
  khớp, không backfill old pins/generation hoặc chunk bindings. Owned API14440/
  ARQ14132 thay theo executable/start-time/cmdline, giữ Web3528/Ollama12836.
  API/ready/Web200,workerhealthy. Frozen binding
  `c136c3aa3f11a5f582fa007f5a5820f6b3d1e68ac5f64ce72cbd5cf01d6b72a9`.
- Live0058/334/saved contract/current binding/M2replay3/3 và model coverage
  Memory+Knowledge/pending[] khớp. Main metadata1legitimate released catalogue
  lease/0policies giữ nguyên; usageAPI vs SQL và exact metadata hashes trước/sau
  read-only checker khớp. Native connection counts unchanged; không reset quota
  để làm gate0 xanh. Checker không discovery/embedding/inference/provider thật.
- .env SHA256 vẫn `5672F74189BCEF6C110D4C434E956D4F324598EE3901B88BBD56902C945FBEA7`.
  Không đổi secret/flags/provider default, public deploy, Git init/push/protected
  source, actual Ads/MCP/cloud/mic hoặc external writes. Chỉ cleanup generated
  invocation-owned DB clones; retained private dump/source. Main không sửa tay.
- README/master/unified/S2register/ADRs/P6/P7 current-head đồng bộ B2b scoped
  native coverage local_accepted; next-only B3 quota Settings/integration.
  Source+DB final seal được exact-restore/live-check sau docs; không share dumps.

## Tiếp theo

**B3 quota Settings/integration**: owner/admin policy/usage forms, clear unknown
usage vs billing, actionable denial/fallback/recovery help, desktop/mobile,
switch/reload và cross-module acceptance. Sau đó S2.3 unified Settings/finalS2.
Global host fairness và true-model/provider/production acceptance còn mở;
local scoped caps không là host load test hoặc provider subscription guarantee.
Không mở live Ads/MCP/cloud hoặc production reboot/HTTPS để làm xanh fixture.
