# S2.2B2b — Local catalogue/selection resource coverage

Chú thích hiện hành13/10: phần legacy inference kế tiếp bên dưới đã được
[legacy acceptance](S22B2B-LEGACY-ACCOUNTING-2026-10-13.vi.md) thay thế. Giữ nguyên
kết quả/snapshot của local discovery; đầu việc tiếp theo hiện tại chỉ embeddings.

13/10/2026, F:\PAO-ACOS. Tiếp tục cùng B2b, không milestone mới; legacy
inference và embeddings chưa đạt từ checkpoint local metadata này.

## Thiết kế và thay đổi

1. `/v1/engines` và chọn Ollama ở `/v1/sessions/{id}/engine` dùng pool metadata
   SME hiện có: default100admissions/ngày UTC,2inflight; ceilings1000/8,lease90s.
   Dùng kinds `model_catalogue/model_select` hiện hữu với hashed target Ollama/
   endpoint/session pin. Không migration, stamp dữ liệu cũ hoặc pool mới.
   Catalogue mount/reload của UI cũng là request metadata mới, không chỉ manual
   click. Không tính inference/token/provider subscription hoặc billing.
2. Optional UUID `Idempotency-Key` trên cả hai native routes, không retry tự động.
   Reuse key409 xuyên cloud/local/MCP kinds trong cùng SME; failure/cancel đã
   commit vẫn dùng daily, chỉ giải phóng slot. Native cloud selection chỉ đọc
   cấu hình đã lưu, không gọi catalogue provider và không bill metadata.
3. Pool lock trước fresh User/Member/session. Viewer vẫn đọc catalogue nhưng
   không được sửa model hội thoại; không biến read thành owner/admin. JWT expiry,
   active user/membership/feature gate kiểm lại trước publication, cả success và
   failure. Model list không là quyền inference/tool hoặc private Brain access.
4. Không transaction/source/member/session lock qua Ollama I/O. Chọn model dùng
   fresh owned session/version/no-active-run trước admission và publication;
   owner/archive/workspace/brand/Brain/engine config/chat revision/knowledge mode
   đổi trong lúc chờ thì deny, không ghi lựa chọn. Một run mới có thể nhập hàng
   đợi trong lúc chờ; chooser phải nhận conflict, không chặn bằng khóa dài.
5. Ollama endpoint loopback HTTP fixed `/api/tags`, captured trước await; không
   proxy/redirect/auth key/pull/download/remote fallback. Inner/outer5s tổng,
   native read3s,262144decoded bytes/500rows; JSON MIME/schema và bounded model
   names. Adapter malformed/timeout/error dùng stable offline, không raw errors.
   Lease-current check trước I/O, fresh endpoint pin và flag trước/ sau I/O.
6. Chọn Ollama nhận catalogue đã được admission từ boundary; choose_config
   không tự gọi `/api/tags` lần thứ hai. Cleanup rollback publication transaction
   trước release, giữ lock order và durable replay/unknown semantics0056.
7. Engines/session/run engine DTO success/422/error đều no-store; body chooser
  8KiB, input/header validation redacted. Giữ334operations/43routers, thêm optional
   UUID headers và coverage local trong metadata status; generated contract/types.
   Không thay frontend UI, cloud defaults, settings/credentials/live integrations.

## Tài liệu/giới hạn

[Ollama List models](https://docs.ollama.com/api/tags) đọc13/10 xác nhận GET
`/api/tags`, JSON models/name. Không upgrade server/model/API endpoint hoặc thêm
OAuth/secret/scopes/webhooks; loopback server và model inventory là host-owned.
Quotas là policy PAO, không giới hạn Ollama công bố. Catalogue không xác nhận
model load thành công, capability thực tế, remote production hoặc GPU cancellation.
Host-global metadata scheduling/fairness và quota Settings UI còn gate riêng.

## Verification

Baseline live0056/334/source85348d46,metadata rows0/M2replay3/3/native counts không
đổi. Checkpoint `.runtime/checkpoints/p0-20261013T090159-c4453950/manifest.json`:
964source/125physical/124business/3archives/0056; exact rows/schema restore,
primary unchanged. Chỉ drop generated owned clone, giữ dump/source private.

Focused engine/model-grant/factory60passed57.21s; corpus đầu33passed/1failed do
fixture đổi workspace mà không thay Brain FK. Đã sửa fixture dùng brain/brand=None,
không tháo FK hoặc nới production scope guard. Corpus cuối44passed24.85s, gồm
success/failed late authority, no transaction qua loader, selection CAS/run
race, quota trước I/O/key, cross-SME busy/cancel/replay và native protocol bounds.
25Node/runtime/SSE, TypeScript/contracts và isolated production build21/21 đạt;
inherited Hooks warnings giữ nguyên.

- **425passed/0failed/0skipped291.13s** frozen affected regressions trên
  pao_test/Redis15: local metadata/engines, cloud/MCP quota/security, tenant
  model/read pools, role/rotation/revoke/Brain/grants/real ARQ/factory.8inherited
  ARQ.close warnings; không dùng nhóm này làm full backend/full S2 acceptance.
- **Browser4passed110.14s**: local chooser/quota/reload/error/SME switch/mobile,
  cloud metadata Settings và model/MCP explicit consent/tool/replay/revoke.
 0real local/cloud provider calls; HTTP/DB thật trong fixture-only environment.
  Screenshot `.runtime/s22b2b-local-browser-49fa414f20164352b587925147e5e332/s22b2b-local-mobile.png`
  đã xem. No overflow, SME B dùng default local-a, không mang lỗi quota/model đã
  chọn local-b của SME A sang B. Đây là no-horizontal-overflow/chooser gate,
  không phải tất cả mobile UI: explanatory text vẫn bị cắt trong scroll area
  hiện hữu của chat; S2.3 cần rà layout đó. Quota-form UI vẫn chưa triển khai.
- Predeploy `.runtime/checkpoints/p0-20261013T092225-cba33c5d/manifest.json`:
 969source/125physical/124business/3archives/0056; exact rows/schema restore,
  primary unchanged. Giữ dump/source private, chỉ drop generated owned clone.
- Source binding **1bd512785a3aaaa728c19276e206c81d0db0a657908c27d3c498f3c7b456703b**.
  Idle/safe gate0active, thay đúng owned API15784/ARQ19544 theo executable/start-time/
  cmdline, giữ Web16176/Ollama12836. API/ready/Web200,workerhealthy. Installed
 0056/334/saved contract/current binding/M2replay3/3 khớp, local coverage reported;
  invalid engine nonce422/foreign404/no-store/redaction trước I/O đạt.
  Main metadata policies/leases0 và native connection counts không đổi; checker
  không gọi local discovery hoặc provider thật. Không sửa tay main database.
- `.env` hash giữ
  `5672F74189BCEF6C110D4C434E956D4F324598EE3901B88BBD56902C945FBEA7`.
  Không migration/new policy, đổi credentials/flags, bật Ads/Telegram/Studio/write,
  Git init/push/protected source hoặc public deploy. Source/DB seal cuối private
  dưới `.runtime/checkpoints`; không chia sẻ dump/credential. Local discovery gate
  đạt; B2b/S2 chưa đóng. Browser intermittent route/toast gap vẫn chưa root-cause.

## Phần tiếp theo duy nhất

Sau local discovery acceptance: **legacy unaccounted inference và embeddings**
trong B2b. Không lặp credential payload/model/MCP/local metadata đã đạt.
require_accounted hiện chỉ deny khi SME có explicit policy; legacy gateway,
runtime/memory extraction khi chat_features off vẫn cần ledger/hard deadline/
recovery. Memory vectorize/retrieve và Knowledge local_embed chưa được tính
SME quota từ ledger extraction; rà từng call site, preserve private Brain/
owner/brand/run pin và lexical/knowledge degraded behavior. Không grandfather
unaccounted calls hoặc tự bật provider để làm xanh test. Sau B2b là B3 quota UI,
S2.3 unified Settings và integrated final S2; chưa đóng B2b/S2/production.
