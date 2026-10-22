# S2.2B2b — Durable model/MCP metadata resources

Snapshot quota backend bên dưới giữ nguyên bằng chứng298/source96d3. Follow-up
credential payload/URL logging đã đạt local356/source85348d46 theo
[evidence mới](S22B2B-CREDENTIAL-PAYLOAD-2026-10-13.vi.md). Security TODO cuối
snapshot này đã được xử lý; local discovery follow-up cũng đã đạt theo
[evidence](S22B2B-LOCAL-DISCOVERY-2026-10-13.vi.md). Còn legacy inference/embeddings.

13/10/2026, F:\PAO-ACOS. Tiếp tục cùng B2b, không milestone mới. Metadata
coverage không đóng legacy/embeddings/B2b/B3/S2.3/full S2/production.

## Thiết kế

1. Native model connect/catalogue/select và MCP discovery dùng chung pool theo
   SME. Default100logical admissions/ngày UTC,2inflight; host ceilings1000/ngày,
   8inflight. Đây là host policy PAO, **không provider RPM/RPC/token/billing**.
   Model inference/probe vẫn B1; native ToolCall/Ads jobs vẫn B2a. Không double
   charge LlmAttempt hoặc lấy metadata fixed96tokens như management inference.
2. 0056 chỉ thêm `tenant_metadata_policies/leases`; không copy credentials,
   stamp legacy rows hoặc tạo policy/lease trên primary tự động. Version/CAS
   owner/admin, strict/bounded/redacted/no-store tại `/resources/metadata`.
3. Admission trước decrypt/encrypt/client/provider: metadata Workspace lock và
   scoped advisory trước subordinate actor/source/Brain locks. DB trigger là
   guard cuối chống alternate INSERT bypass, server UTC stamp/TTL90s/policy
   version. App admission error429 trước credential resolution; source identity
   scope drift không được bill SME A rồi resolve credential của B.
4. Optional `Idempotency-Key` UUID theo workspace, unique trên mọi metadata
   kinds. Reuse key409, kể cả released/expired hoặc đổi endpoint/kind; không
   resend. Không header nghĩa là một thao tác manual mới, không lời hứa dedup
   body/same click/transport retries. Native clients không tự retry request.
5. Lease durable, identity/time/source digest immutable/no delete/no renewal.
   Committed requests lỗi/hủy không refund daily; complete releases only inflight.
   Local model key-preparation failure trước commit không gọi provider và
   transaction rollback, không được coi là provider usage. Metadata luôn có
   `provider_remaining_quota/billing_amount=null`.
6. Network ngoài source/member/Brain transaction: model total30s/4MiB/3pages;
   MCP native30s/outer adapter32s/64KiB/page và P5 DNS/SSRF/version/redirect guards
   giữ nguyên. Check lease còn ít nhất40s **trước I/O**, tính RTT bảo thủ bằng
   monotonic; delayed/expired claim409, không starting I/O từ lease được recover.
7. Sau TTL, next admission đánh expired_unknown, giữ daily/key, không tự gửi
   lại. Status read không xóa history; active snapshot excludes expired deadlines.
   Không cam kết physical cancellation/provider billing/global host fairness.
8. MCP publication fresh active owner/manager/JWT/private Brain/member/source/
   secret/status/version/circuit/manifest fences. Rotation/disconnect/role revoke/
   Brain archive/Brain grant removal không publish hoặc poison health/failure
   counters. Manifest drift vẫn clears permissions/cancels old calls, không grant
   tool permission từ annotations. Success/failure commit trước cleanup; rollback
   source transaction trước finally để tránh source→quota lock inversion.
9. Metadata history chặn xóa enterprise parent và downgrade populated; deletion/
   retention/erasure cần quy trình riêng, không xóa lịch sử để refund. Không thêm
   arbitrary endpoint, scope, account, OAuth, webhook, anonymous grant hoặc engine.
   Native legacy management token-optional behavior giữ nguyên; registered grant
   execution vẫn bắt buộc credential, không nới gate bị từ chối trước đây.

## Nguồn/giới hạn đã đọc13/10

Dùng OpenAI Docs; [Rate limits](https://developers.openai.com/api/docs/guides/rate-limits)
phân biệt giới hạn organization/project/model với policy SME của PAO. Không đọc
quota account thật; không có công cụ `openai-platform-api-key` trong tool catalog,
chỉ fixture/mock HTTP, không yêu cầu secret trong chat. Endpoints/auth/model/version
cũ không thay; catalogue dossier tại [hardening](S22B2B-MODEL-METADATA-HARDENING-2026-10-13.vi.md).

[MCP Tools2025-11-25](https://modelcontextprotocol.io/specification/2025-11-25/server/tools)
đã đọc cho discovery/pagination và untrusted annotations. Giữ protocol2025-11-25,
HTTPS pinned transport, Bearer credential native và owner-approved read-only tools;
không upgrade protocol, sampling, roots, server-pushed jobs hoặc tool scopes.
API review/OAuth redirect/webhooks không áp dụng mới ở metadata checkpoint này;
provider acceptance/account authentication/rotation/revoke thật vẫn gate riêng.

## Verification/rollout

Prechange live0055/332/sourcef175/M2replay3/3 và backup953source/123physical/
3archives verified `.runtime/checkpoints/p0-20261013T073443-d1f4aeb9/manifest.json`.
Nhóm đầu101pass/10fail do mock class-scope NameError, đã sửa fixture; corpus32pass
18.95s. Regression295pass206.50s trước review bổ sung scope/lease-before-I/O;
không dùng295 làm acceptance source cuối. Migration clone0055→56→55→56 exact
122legacy tables/schema và independent policy/lease populated downgrade refuse,
primary unchanged; dump giữ private `.runtime/s22b2b-metadata-pre-8b39a5d832ad4126a80e0622dbc66043.dump`.
- **Final frozen backend298passed/0failed/0skipped211.54s** trên pao_test/Redis15;
  có quota trước key, SQL alternate insert/stamp/immutable/history, cross-kind/
  cross-SME/real ARQ regression, late source/actor/private Brain, cancellation/
  timeout/lease-before-I/O/replay/unknown recovery.8inherited ARQ.close warnings.
- OpenAPI334/types, TypeScript và25Node/runtime/SSE đạt; production build21/21
  trong `.pao-build-check`, không dùng build cache của Web3200. React Hooks
  warnings inherited còn, không tắt lint/assertions để làm xanh gate.
- Browser **3passed65.75s**: quota metadata3lượt/429deny/CAS/reload/SME-switch,
  native read policy và MCP explicit consent/actual fixture call/replay/revoke.
  0real provider/credential; quota-form UI vẫn false. Screenshot đã xem
  `.runtime/s22b2b-metadata-browser-6d3a40c2a7cb4c45b8605075413b59f8/s22b2b-metadata-mobile.png`.
- Backend binding cuối `96d3a6dd301759b637846c26daf0837a68ba24492f6a47ea4563981699b2698c`;
  predeploy `.runtime/checkpoints/p0-20261013T080609-e2a81078/manifest.json`:
 961source/123physical/3archives/0055; exact122business hashes/schema restore,
  primary unchanged. Guarded0056 giữ old native columns/counts vàM2archives;
  metadata policy/lease0, không auto config/admission trên business data.
- Owned idle restart API13184/ARQ13380; Web16176/Ollama12836 giữ nguyên.
  API/ready/Web200/workerhealthy, live0056/334/saved contract/source/M2replay3/3
  khớp; native connection counts không đổi. New quota default100/2,401/foreign404,
  422redaction/malformed nonce/no-store đạt;0metadata rows,0external requests.
  `.env` hash giữ nguyên; không bật Ads/Telegram/Studio/writes, deploy công khai,
  Git init/push hoặc sửa protected source. Backup/dumps private; chỉ drop các
  invocation-owned clones, bản sao phục hồi được giữ lại.

## Còn mở, thứ tự tiếp theo

Sau metadata backend gate: **legacy unaccounted engines/local discovery/embeddings** trong B2b,
không lặp metadata hardening đã đạt. Sau đóng B2b là B3 quota Settings/forms/help/
usage theo SME; S2.3 hợp nhất status/saved/connected/healthy/accepted, audit,
errors/mobile/switch/reload; cuối full S2 integrated gates. Native quota denial
có thể hiển thị raw stable error code; chưa là friendly-help/quota-form UI.
Global actor anti-abuse rate-limit vẫn native và có thể áp dụng trên nhiều SME;
pool isolation không chứng minh global host scheduling hoặc tất cả noisy-neighbor
paths đã tối ưu. Browser intermittent HTTP route và CloudModels toast remount
vẫn là risk/UX gap chưa root-cause/fixed ở scope này.

Code-read follow-up trước đóng B2b/full S2: cần corpus và taint fence cho provider
phản chiếu credential trong catalogue ID/schema/manifest (native parser hiện
chưa có explicit discovery payload filter); kiểm Gemini key-in-query logging
và auth header theo docs chính thức. Chưa kiểm chứng exploit, không gọi provider
hoặc dùng credential thật để thử. Quota acceptance không là payload-security
acceptance, và không cho phép bật live connector khi gate còn mở.
