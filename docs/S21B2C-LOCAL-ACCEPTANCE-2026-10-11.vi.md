# S2.1B2c — MCP tenant authority

Ngày 11/10/2026, F:\PAO-ACOS. **local_accepted**, đã rollout0051.
Local code không xác nhận server MCP thật. Dossier/ADR riêng cùng ngày;
không đổi transport/auth/protocol hoặc bật flags/.env.
Tenant grants MCP mới yêu cầu credential. Đề xuất hỗ trợ anonymous bị auto-review
chặn vì rủi ro network/data egress; không có code đó được áp dụng. Muốn mở mode
này cần phê duyệt riêng, không chặn việc hoàn thiện luồng có credential.

Đã thêm consent append-only read-only riêng, explicit grant_id trong proposal,
immutable authority pins trong ToolCall, registration-denial cho legacy owner/
old pins; không autoactivate B1 hoặc dùng model grant cho tools. Native owner
vẫn quản lý endpoint/token/manifest/bounded args; grantee không có quyền config.
Giữ published Skill/review/proof, exact brand/Brain editor ACL, current manager/
grantee/expiry/config/source stamp và recheck trước token/call/publication.

Lock Workspace trước connection/call. Connection SHARE giữ check→token resolve
đồng bộ với native rotation/disconnect; thả trước network. Không giữ transaction
suốt request, không hứa exactly-once hoặc thu hồi bytes đã gửi trước revoke.
Kết quả về muộn bị bỏ. Catalog metadata lấy scope từ owned Run khi được chọn,
không trả endpoint/credential. UI shared ConnectionGrantPanel dùng chung với
model, consent riêng; McpGrantedCalls chọn Run/grant/tool, retry cùng request key.

## Gate hiện tại

- Lượt đầu29tests:7passed/22failed do UUID strict JSON tại Call DTO và import
  create_worker sai module. Sửa DTO/import, không nới authority:23MCP passed43.41s.
- Clone0050→0051→0050→0051 đạt,118legacy tables row hashes/schema rollback exact,
  primary unchanged. Dump giữ tại `.runtime/s21b2c-pre-cab81a9c7a1d4a86b6e14d1d158d50a8.dump`.
- Thêm native rotation race + four native authority denial tests; affected group
  đạt232passed247.99s/6ARQ deprecation warnings. Sau đó thêm owned Run discovery
  và cross-workspace consent INSERT cases; source cuối còn kiểm lại.
- Final affected group **234passed/0failed/0skipped**,235.64s/6ARQ warnings;
  25Node/runtime/SSE và TypeScript đạt. Backend frozen binding:
  `378e4146dd8ee5db47a431c95ebc0ff1c05d04764d2cc1243f11dee471fe2109`.
- Browser model/MCP đạt2tests77.70s; S12/S11/P7 regression đạt3tests127.83s.
  Mobile MCP đã xem ảnh; không horizontal overflow. Build production21/21 đạt,
  còn cảnh báo React Hooks kế thừa, không có lỗi build.
- Predeploy manifest `.runtime/checkpoints/p0-20261011T163857-b5631727/manifest.json`:
  900source/119physical/3archives, exact restore118business/schema và primary unchanged.
  Guarded additive0051 giữ hashes mọi legacy row, consent mới0; API/ARQ thay đúng
  process sở hữu21636/21280. API/ready/Web200,workerhealthy; live323/saved contract/
  binding378/M2replay3/3 khớp, không provider call/live consent.
- Final seal `.runtime/checkpoints/p0-20261011T164109-140da5c3/manifest.json`:
  900source/120physical/3archives, exact restore119business/schema, primary unchanged.
  Chỉ drop clone sở hữu bởi invocation, giữ backup. `.env` hash không đổi.
- Full1298 của B2b là evidence source fa91, không của
  MCP source mới. Không suy ra full S2 đã đạt từ nhóm MCP.

S2.1B2d Ads, S2.2 lifecycle/vault/quota và S2.3 Settings hợp nhất còn mở.
External MCP/OAuth/remote-production acceptance vẫn riêng; không cần hỏi lại
provider credentials để hoàn thiện code và fixture gates local.
