# S2.2B2b — Credential reflection và URL logging

Snapshot security356/source85348d46 giữ nguyên bên dưới. Local discovery quota
follow-up đã đạt425/source1bd51278 theo
[evidence mới](S22B2B-LOCAL-DISCOVERY-2026-10-13.vi.md). Next-step local metadata
trong snapshot này đã xong; còn legacy inference/embeddings, master sở hữu thứ tự.

13/10/2026, F:\PAO-ACOS. Đây là phần security còn mở của cùng B2b,
không milestone mới và không tuyên bố full S2 đã hoàn tất.

## Thay đổi và giới hạn

- `pao/credential_guard.py`: kiểm tra cây JSON đã decode, cả keys và values,
  kể cả fields sau đó bị bỏ qua. Chặn credential của chính request ở dạng
  literal, JSON-escaped string, URL percent encoding, base64/base64url một lớp.
  Bounded depth32/nodes100000, iterator không sao chép cây; không secret registry,
  lưu/log secret, quét vault khác SME hoặc cố giải mã tùy ý. Không cam kết DLP
  toàn diện, arbitrary encoding/splitting/encryption hoặc credential khác request.
- Model catalogue bốn provider: kiểm trước chọn ID/cursor; replacement adapter
  được kiểm lại trước source publication. Tainted response lỗi stable, không
  chọn/lưu model, key/ciphertext, model_count hoặc last_checked_at mới.
- MCP: kiểm toàn JSON-RPC/SSE message trước lấy result, gồm initialize metadata,
  schemas, ignored fields, cursor, error fields, structured/unstructured output;
  kiểm session header trước khi gửi lại. Không partial redact rồi chấp nhận.
  Replacement adapters có publication guard ở probe và ToolCall gateway.
- Native source/actor/Brain CAS, no-store, quotas/replay/unknown và quyền tool giữ
  nguyên. Committed failed metadata vẫn tính daily, chỉ release inflight. MCP
  giữ manifest tốt trước đó và native failure/circuit policy; không cấp quyền
  mới từ payload bị chặn. Failed ToolCall không lưu tainted result/result hash.
- Gemini dùng `x-goog-api-key`, không `key` trong URL ở catalogue, stream và
  structured generation. Giữ origins/v1beta/models/alt=sse/pagination/model,
  body/schema/token limits/usage semantics; không đổi model mặc định hoặc bật
  provider. HTTPX INFO URL log fixture không chứa khóa. Header vẫn là secret:
  không được bật wire/debug capture hoặc log request headers trong production.
- Không migration mới, schema0056/OpenAPI334 giữ nguyên. Không sửa .env,
  Business data, flags, credentials, protected source hoặc Git history.

## Tài liệu chính thức đã đọc

OpenAI Docs: [API Authentication](https://developers.openai.com/api/reference/overview)
và [List models](https://developers.openai.com/api/reference/resources/models/methods/list):
giữ Bearer credential server-side và native API-key catalogue, không chuyển sang
ChatGPT OAuth hoặc API/model mới. Không có tool openai-platform-api-key trong
catalog phiên này; chỉ fixture, không yêu cầu key trong chat.

[Gemini API keys](https://ai.google.dev/gemini-api/docs/api-key) xác nhận REST
`x-goog-api-key`; [models.list](https://ai.google.dev/api/models) xác nhận fixed
v1beta endpoint và pageToken. Không tự rotate keys, thay scopes hoặc upgrade models.
[MCP security2025-11-25](https://modelcontextprotocol.io/docs/2025-11-25/tutorials/security/security_best_practices)
được đối chiếu; vẫn pinned protocol/HTTPS/SSRF/read-only consent. Guard phản chiếu
credential là defence PAO, không tuyên bố đây là validator MCP chuẩn.
OAuth redirect/webhook/review/account/remaining quota/live acceptance không thay
ở scope này và vẫn có gate riêng.

## Verification

Prechange live0056/334/binding96d3 khớp, metadata rows0, native connection counts
không đổi/M2replay3/3. Checkpoint
`.runtime/checkpoints/p0-20261013T083923-ec2e7937/manifest.json`:961source,
125physical/124business/3archives/0056; restore exact rows/schema, primary unchanged.
Chỉ drop invocation-owned clone; retained backup/source có thể phục hồi.

Lượt đầu136pass/1fail do deep top-level non-object trả limit thay invalid; đã giữ
lại native schema rejection trước guard. Intermediate353pass244.05s/8inherited
ARQ.close warnings; sau đó phát hiện thêm hai Gemini inference URLs và sửa header,
không dùng353 làm acceptance source cuối. 25Node/runtime/SSE, TypeScript/contracts,
isolated production build21/21 đạt; inherited React Hooks warnings còn.

- **Final frozen356passed/0failed/0skipped240.78s** trên pao_test/Redis15:
  58security/header cases cộng regression quota/source/actor/Brain/real ARQ,
  replay/rotation/revocation.8inherited ARQ.close warnings. Không là full backend.
- Browser **3passed93.18s**: model connect/catalogue/select/quota/CAS/reload/
  SME-switch/mobile, native read quotas và explicit MCP consent/tool/replay/revoke.
  Không provider thật hoặc inference cloud; quota-form UI vẫn false. Screenshot
  `.runtime/s22b2b-metadata-browser-9fbe278c689c4e678e925918912ccad5/s22b2b-metadata-mobile.png`
  đã xem: SME B/input trống, không lẫn model/grant/secret từ SME A; UI không đổi.
- Binding cuối **85348d46c52a639a320526b19430b31e94fdc749c2d096cfba233038583b6e80**.
  Predeploy checkpoint `.runtime/checkpoints/p0-20261013T085255-65a26187/manifest.json`:
  964source/125physical/124business/3archives/0056; restore exact rows/schema,
  primary unchanged. Chỉ drop generated owned clone, giữ dump/source private.
- Idle/safe gate0active; restart đúng owned API20540/ARQ21780 theo executable/
  start-time/cmdline, giữ Web16176/Ollama12836. API/ready/Web200, workerhealthy.
  Installed0056/334/saved contract/source binding/M2replay3/3 khớp; metadata rows0,
  policy defaults100/2,401/foreign404/422redaction/no-store/malformed nonce đạt,
  native source counts không đổi. Không remote metadata/inference/live writes.
- `.env` SHA256 giữ
  `5672F74189BCEF6C110D4C434E956D4F324598EE3901B88BBD56902C945FBEA7`.
  Không bật Ads/Telegram/Studio/write/deploy hoặc sửa protected source/Git.
  Source/DB seal cuối được giữ riêng dưới `.runtime/checkpoints`, không chia sẻ
  runtime dump/ciphertext/credential. Local security gate đạt; B2b/S2 chưa đóng.

## Tiếp theo duy nhất

Sau security acceptance, **legacy unaccounted engines/local discovery/embeddings**
trong B2b. Code-read xác nhận require_accounted hiện chỉ deny khi SME đã có policy;
gateway_for_workspace/gateway_for_run và Memory extraction cần ledger/deadline
khi chat_features off, không chỉ workspace đã cấu hình. `/v1/engines` local tags
và chọn Ollama cần per-SME admission mà không nâng viewer thành manager hoặc giữ
session lock qua I/O. Memory.vectorize/retrieve và knowledge embeddings cần
được rà riêng, không giả định extraction ledger đã tính embeddings.

Giữ run model/source pin bất biến, private Brain ACL và không cross-SME fallback.
Không tự thay semantics knowledge-no-inference hoặc grandfather old jobs để làm
xanh test. Sau đóng B2b là B3 quota UI, S2.3 hợp nhất Settings, cuối integrated S2.
Browser intermittent HTTP route và toast remount vẫn chưa root-cause/fixed.
