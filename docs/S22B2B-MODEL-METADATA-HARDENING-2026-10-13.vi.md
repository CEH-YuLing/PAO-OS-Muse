# S2.2B2b — Model metadata hardening, checkpoint vẫn in_progress

13/10/2026, F:\PAO-ACOS. Đây là tiến độ bên trong B2b, không tạo milestone
mới hoặc đóng quota metadata/legacy/full S2. Không sửa protected originals,
không migration, không credential thật hoặc inference/provider acceptance.

**Snapshot của lượt hardening trước0056.** Metadata quota/model/MCP backend
đã được checkpoint kế tiếp trong cùng B2b thay thế theo
[evidence0056/live334](S22B2B-METADATA-QUOTA-2026-10-13.vi.md). Evidence/history
bên dưới giữ nguyên; dispatch hiện hành là master/register, không phần TODO cũ.

## Phạm vi thay đổi

- `model_router.fetch_models`: fixed provider origins/auth/version/model defaults
  giữ nguyên; streaming decoded bytes tối đa4MiB toàn lượt, tối đa5000 catalogue
  rows/3pages/30s total. Không redirect/proxy/retry; strict JSON/container/ID/MIME,
  timeout/cancel đóng stream, lỗi không chứa raw provider text/key/URL/cause.
- Anthropic `has_more/last_id`→`after_id`, Gemini `nextPageToken`→`pageToken`;
  chỉ opaque cursor tới cùng endpoint, reject loops/malformed/excess pages.
  OpenAI/OpenRouter vẫn một response catalogue. Giữ giới hạn500 model hiển thị
  như native trước đây; không hứa toàn catalogue, chat capability hoặc token quota.
- `model_metadata`: Workspace→scoped advisory→fresh User/Member→source, snapshot
  identity/model/status/default/cipher hash/updated_at. Commit trước network;
  publication recheck active actor/token expiry/manager/current source và CAS.
  Rotation/disconnect/deletion/same-value reconfiguration/role revoke hoặc
  concurrent create không ghi đè winner, không revive consent/pin/grant cũ.
- Native connect/list/select reuse existing encryption store; no new vault.
  Connect kiểm encryption sẵn sàng trước discovery. Listing local không gọi
  provider. Default/disconnect/probe authority không được mở thêm quyền.
- Native model input strict extra-forbid, JSON body8KiB,422 redacted; tất cả
  model-provider responses (cả403/409/413/422/503) no-store.
- Không giữ source/member/database transaction khi chờ mạng. Fixture SME A chậm
  vẫn cho B hoàn tất catalogue. Đây không phải admission quota/global fairness.

## Nguồn chính thức đã đọc13/10/2026

Dùng OpenAI Docs cho phần OpenAI API; giữ endpoint/model hiện có, không migration
model hay inference. Không có công cụ `openai-platform-api-key` trong tool catalog
phiên này; local test dùng mocked transport, không yêu cầu khóa trong chat.

- [OpenAI List models](https://developers.openai.com/api/reference/resources/models/methods/list):
  GET/models, catalogue `data`/model ID; không suy ra khả năng chat hoặc quota.
- [Anthropic List Models](https://platform.claude.com/docs/en/api/models/list):
  GET/v1/models, pinned `anthropic-version:2023-06-01`, x-api-key;
  after_id/has_more/last_id. Không bật beta/scopes mới.
- [Gemini models.list](https://ai.google.dev/api/models): v1beta/models, existing
  key auth, generateContent metadata và nextPageToken/pageToken. Giữ riêng
  embedding models; không thêm OAuth/webhook/redirect vì catalogue không dùng.
- [OpenRouter models](https://openrouter.ai/docs/api/api-reference/models/list-all-models-and-their-properties):
  GET/api/v1/models, catalogue data; pricing vẫn provider metadata, không billing.

Các byte/rows/pages/deadline trên là host guard của PAO, không rate-limit cam kết
của provider. App review/OAuth/provider remaining quota/live credentials không
được kiểm thử ở lượt này. Không thêm endpoint/scope hay quyền hành động ngoài.

## Evidence và rollout

Prechange live0055/332/source83f/M2replay3/3 khớp; backup946source/123physical/
3archives verified tại `.runtime/checkpoints/p0-20261013T070002-fe57f15b/manifest.json`.
`.env` SHA256 giữ `5672F74189BCEF6C110D4C434E956D4F324598EE3901B88BBD56902C945FBEA7`.

- Regression đầu256passed/1failed do OpenAPI chưa export extra-forbid schema;
  checker sửa thứ tự export-before-contract-test. Broad kế265passed/3failed,
  ba failures là fixture DELETE workspace khi còn native FK children. Dọn đúng
  children của fixture, không đổi DB constraints hoặc nới denial assertions.
- **Final focused55passed38.70s**, gồm toàn49metadata cases và6factory gates;
  ba fixture failures trên đã pass. Cùng frozen backend,265affected đạt trước
  đó; coverage268unique cases đạt qua hai lượt có overlap, **không tuyên bố
  một lượt268/268 hoặc full backend regression**.4ARQ.close warnings inherited.
- Generated OpenAPI/types, TypeScript và25Node/runtime/SSE đạt; production build
 21/21 trong `.pao-build-check`, không đổi Web3200 cache. React Hooks warnings
  inherited còn, không tắt lint hoặc coi chúng đã được sửa.
- Browser metadata mới lần đầu sai harness chưa mở Cloud Models tab; lần kế
  chờ success toast bị native reload remount thay vì kiểm actual model. Sửa
  harness để mở đúng tab và kiểm selected model đã lưu, không nới timeout/
  assertions hoặc sửa UI. **Final metadata browser1passed22.69s**: connect/list/
  select/reload/SME-switch/mobile,3catalogue fixture calls/0real provider/inference.
  Screenshot đã xem: `.runtime/s22b2b-metadata-browser-ff16e47239ef409a90db3fc0f3cc17ca/s22b2b-metadata-mobile.png`.
  Read-quota regression browser1passed; grant/consent browser lần đầu fail HTTP
  route `/v1/automation/status`, chạy lại đạt1case cùng source, không nới checker.
  Lỗi gián đoạn này chưa root-cause/fixed; giữ trong final S2 browser risk.
- Predeploy verified953source/123physical/3archives/0055 tại
  `.runtime/checkpoints/p0-20261013T072725-6d63713c/manifest.json`; exact122business
  row hashes/schema restore, primary unchanged, chỉ drop invocation-owned clone.
- Backend source binding cuối `f1751afb6a14e166ae89756fa12e197a6adfe5377f89382867ce075b9718fb13`.
  Restart đúng owned idle API18952/ARQ19428; Web16176/Ollama12836 giữ nguyên.
  API/ready/Web200,workerhealthy; live0055/332/saved contract/source/M2replay3/3
  khớp; native model connection count không đổi. Live422/413redaction/no-store,
  unauthorized401 và read quota metadata đạt; không catalogue/inference request.
- `.env` hash không đổi; không migration, bật flags, OAuth/provider thật, Ads,
  chi tiền/Telegram, Git init/commit/push hoặc sửa protected sources. Postrollout
  seal953source/123physical/3archives/0055 giữ private trong `.runtime/checkpoints`;
  manifest có source/dump hashes và source binding, exact restore checker phải
  kiểm122business rows/schema/primary unchanged. Không chia sẻ runtime backup.

Native CloudModels success toast bị reload unmount là UX gap còn cho S2.3;
không gọi kiểm model persisted là đã chứng minh toast/status/help hoàn thiện.

## Việc tiếp theo duy nhất, không lặp bước đã đạt

Hoàn thiện phần còn lại của **S2.2B2b**: durable per-SME metadata policy/admission/
leases/expiry/no replay trước decrypt hoặc body-key request; MCP discovery/probe
transaction/publication fences; legacy unaccounted engines và embedding coverage.
Không dùng model inference leases fixed96 như metadata ledger hoặc khai metadata
quota đã có chỉ từ actor rate-limit/transport guards. Sau B2b là B3 quota Settings,
S2.3 unified status/help/audit/mobile và full integrated S2 gates.
