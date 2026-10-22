# Hồ sơ MCP cho checkpoint tenant execution kế tiếp

Ngày kiểm tra 11/10/2026. Đây là thiết kế/gate **pending**, không evidence đã
triển khai. Chỉ bắt đầu code sau B2-model local acceptance. Reuse P5 service,
gateway và transport; không fork MCP client hoặc đổi protocol trong lượt model.

## Nguồn chính thức đã đối chiếu

- [Authorization, revision 2025-11-25](https://modelcontextprotocol.io/specification/2025-11-25/basic/authorization): HTTP auth/OAuth và resource audience là chuyện transport/provider, tách khỏi tenant grants nội bộ của PAO.
- [Security Best Practices](https://modelcontextprotocol.io/docs/2025-11-25/tutorials/security/security_best_practices): không chuyển tiếp token sang dịch vụ khác; cần chặn SSRF và confused deputy.
- [Tools](https://modelcontextprotocol.io/specification/2025-11-25/server/tools): annotations là thông tin từ server, không tự thành quyền thực thi.

Giữ protocol 2025-11-25 hiện có để tương thích; không gọi đó là cam kết hỗ trợ
mọi extension/OAuth discovery. Native P5 là endpoint HTTPS + optional bearer
token được nhập riêng cho server, chưa phải flow OAuth đầy đủ. Settings phải
nói rõ mode/token presence/status, không giả managed OAuth bằng form API key.

## Cách nối vào quyền SME

1. Consent explicit cho grant MCP read-only, không auto-activate B1 staged.
   Reuse immutable grants/ref/source stamp; không nhân bản ConnectorSecret.
2. Proposal yêu cầu chọn grant rõ; pin actor/workspace/brand/Brain/source,
   grant/ref/consent/version/expiry cùng native tool schema/manifest/bound args.
3. Cấp connection không cấp tool. Giữ published skill/review, closed output,
   bounded argument permission, manager acknowledgement và Brain ACL hiện có.
4. Admission/call/publication kiểm lại trước token resolve. Registered/revoked
   không quay về service.owned legacy. Không giữ DB transaction suốt network.
5. Manager vẫn cần quyền native để config/probe/rotate/revoke; grantee không
   tự quản lý token hoặc tải manifest khác. Không mở quyền shell/code/plugins.
6. Không dùng readOnlyHint như bảo đảm server thật không ghi. Trust/review và
   việc chứng minh read-only trên server được owner cấp là external gate riêng.

## Checklist Settings và local acceptance

Endpoint có hướng dẫn HTTPS/trust, token nhập password không echo, credential
presence không plaintext, chỉ đọc manifest sau thao tác test rõ; không probe khi
render. Hiển thị configured/connected/circuit/error/last-check đúng bằng chứng;
chọn Brain/tool/args và SME/brand/grantee riêng. Disconnect giữ tombstone/audit.

Test hai SME cùng endpoint/tool name/actor, grant sai brand/Brain, mất membership,
role/expiry/revoke/rotate/manifest drift giữa enqueue/call/publish, idempotency và
real ARQ/Redis15. Fixture server không là server thật. Chưa owner cấp server thật
thì external_pending; không chặn local implementation hoặc hỏi lại quyết định SaaS.

Audit API hiện chỉ trả B1 actions; S2.3 phải hợp nhất consent history (bao gồm
thời điểm/actor/capability) từ bảng append-only, không giả ghi activation vào
enum audit B1 hoặc xóa/sửa lịch sử để hợp schema cũ.
