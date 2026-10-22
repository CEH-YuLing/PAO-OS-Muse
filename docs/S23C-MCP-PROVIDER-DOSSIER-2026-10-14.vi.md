# S2.3C — Hồ sơ MCP Settings / restricted native profile

Đối chiếu ngày14/10/2026. Không chọn/kết nối server thật; người dùng đã chọn
nghiệm thu local bằng server giả lập ở P5. Đây là profile PAO có giới hạn,
không tuyên bố hỗ trợ đầy đủ MCP/OAuth hoặc mọi phiên bản protocol mới.

## Nguồn chính thức và quyết định UI

- [Transport2025-11-25](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports):
  Streamable HTTP khác transport HTTP+SSE cũ; JSON/SSE responses, version header,
  session và Origin security. PAO giữ phiên bản native2025-11-25, không tự
  nâng protocol, thêm stdio/installer hoặc legacy transport trong UI checkpoint.
- [Authorization2025-11-25](https://modelcontextprotocol.io/specification/2025-11-25/basic/authorization):
  access token ở Authorization header, không URI query; token phải cho đúng
  resource/server. Chuẩn OAuth có metadata/issuer discovery, PKCE và resource
  binding. PAO hiện chỉ nhập bearer đã cấp cho đúng MCP server; không hỗ trợ
  OAuth authorization/refresh/step-up hay nhận App Secret thay bearer. Không
  hiển thị nút login/OAuth giả hoặc suy ra đã đạt OAuth conformance.
- [Tools2025-11-25](https://modelcontextprotocol.io/specification/2025-11-25/server/tools):
  tools/list khác tools/call, schema và annotations; annotations không được
  tin như authorization. UI tách discovery consent khỏi permission/call consent;
  readOnlyHint không bảo đảm server không ghi hoặc không tiêu tài nguyên.

## Contract native giữ nguyên

Profile HTTPS443/domain/path đơn giản, không userinfo/query/fragment/IP hoặc
localhost; backend tiếp tục DNS pinning/SSRF, TLS, no redirects/environment
proxies/retry và bounded transport. Form chỉ prevalidate, không thay server gates.
Tool names native tối đa20 ký tự, bắt đầu bằng chữ; tối đa32 tools; cả input và
output object schema đóng, giới hạn native chặt hơn spec chung. Unsupported
schemas/protocol fail closed, không cố đoán hoặc chuyển transport tự động.

| Thao tác | Contract / ảnh hưởng |
|---|---|
| Catalog/templates/connections/audit GET |Chỉ đọc bản lưu PAO, không MCP I/O; catalog tối đa20 kết nối của chính manager; audit100 sự kiện gần nhất |
| Create draft |Endpoint + optional token + read-only acknowledgement; lưu encrypted native, chưa discovery/grant; không client nonce/CAS mới |
| Discover |POST test version + UUID Idempotency-Key, metadata quota/source/actor/private Brain/publication fences native; initialize/tools/list, không tools/call |
| Rotate |PUT credential version + token mới; về draft, xóa quyền đọc, cancel calls, không auto-discover hoặc revive grants |
| Bounded permission |PUT version/tool/schema_hash/arguments/readonly acknowledgement; native schema/manager checks; không thay Skill/grant/Run |
| Queue legacy / granted call |Gateway vẫn kiểm published Skill/native permission/run/actor/Brain/scope/quota; registered sources không fallback legacy. Chỉ queued không chứng minh thực thi |
| Disconnect |POST version; purge token/native permission, cancel queued/running calls; không tự revoke token ở server và không xóa history |

Không yêu cầu API key trong chat. Token chỉ ở password form memory; clear ở
operation start/error/refresh/context/selection/pagehide/hidden event, không
browser storage. Không hứa zeroize bản sao JS/network hoặc bảo vệ khỏi malware
trên host. Audit UI chỉ projection ID/action; không render arbitrary data/error.
Unknown response => bỏ snapshot/drafts, khóa mutation tới manual GET; GET khi
request cũ còn chạy không bảo đảm kết quả cuối. Không retry/replay/đổi nonce mù.

## Việc còn cần server cụ thể / production

Chọn server/account/dataset đích và đọc tài liệu chính thức của server trước
live smoke: auth/token audience, scopes read-only, review/account requirements,
expiry/rotation/revoke, quota/billing, webhook/redirect nếu cần OAuth. MCP chung
không quy định một App ID/Secret, token lifetime hay số quota chung cho mọi server.
PAO không chứng minh downstream read-only từ checkbox hoặc tool annotation.

OAuth chuẩn đầy đủ, protocol upgrade, stdio/code install, server/provider health,
tenant-owned connector sharing UX, paginated full history và production security
được theo dõi riêng; không tự kéo vào S2.3C. Bound arguments/Skill/grants không
thể bị bypass chỉ vì Settings cho nhập token hoặc catalogue trả connected.
