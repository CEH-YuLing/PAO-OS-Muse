# S2.1B2c — Quyền MCP theo SME, không bỏ quyền tool

Thiết kế ngày 11/10/2026; đã nghiệm thu LOCAL theo S21B2C acceptance cùng ngày.
Nguồn provider/version/auth tại dossier MCP cùng ngày. Không sửa transport,
không cài code/stdio/plugin, không gọi server ngoài. Fixture không xác nhận
server thực sự chỉ đọc; readOnlyHint không là bằng chứng quyền.

Giới hạn nghiệm thu: tenant execution MCP mới yêu cầu credential đã cấu hình,
giữ B1 credential requirement. Không mở chế độ anonymous cho grants. Auto-review
đã từ chối đề xuất mở anonymous do rủi ro unauthenticated tool calls/data egress;
không áp dụng hoặc bypass. Native unregistered P5 behavior không được mở rộng.

## Authority

- Consent read-only riêng, append-only, CAS/request UUID/fingerprint; không
  đổi grant B1 staged thành trạng thái executable hoặc sửa TTL/history.
- Proposal chọn grant_id rõ. Pin workspace/actor/brand/Brain/source/ref/grant/
  consent/revisions/expiry/capability cùng manifest/schema/bound arguments,
  published skill/review và execution binding của P5 hiện có.
- Grantee active owner/admin/operator/analyst được dùng đúng tool đã được native
  owner cấp và skill được duyệt; không được config/probe/token/manifest/permission.
  Viewer không có execution. Manager phải tiếp tục active owner/admin.
- Null brand chỉ unbranded, không wildcard. Brain private phải còn quyền editor
  của tác vụ, không chuyển quyền từ manager sang grantee. Source Brain, run Brain,
  current brand và pinned brand phải khớp; không repin queued/history.
- Registered source không có explicit consent/pin hợp lệ bị deny, kể cả native
  owner hoặc old call. Unregistered legacy path giữ P5 ACL; không fallback khi deny.
- Admission, trước token resolve, trong network wait và publication recheck.
  Không giữ transaction suốt network; kết quả về muộn bỏ, không hứa thu hồi bytes
  đã gửi trước revoke hoặc exactly-once từ external provider.

## Lock order / rollout

Mapping lấy Workspace trước connection/reference/grant. Gateway cũng lấy
Workspace KEY SHARE trước các lock connection/call để tránh chu trình với mapping.
Không đảo call→workspace tại publication. Consent/revoke không cần scan/mutate
ToolCall pins; fresh checks vô hiệu hóa queued/running call.

Migration additive có backup, clone upgrade/downgrade/upgrade và exact restore;
không downgrade primary hoặc tạo live grants. Existing native secret store được
tái sử dụng, không nhân bản token. API validation và public snapshots không xuất
source_stamp, fingerprint hoặc plaintext/ciphertext credentials.

## Gates

Hai SME cùng endpoint/tool/actor, exact brand/Brain, manager/grantee role và
membership/expiry/revoke/config/manifest/schema/bound args drift; registered
owner legacy deny, model grant không cấp tool; queued no-decrypt/no-network,
late publication discard, idempotency/CAS/immutable DML, real ARQ/Redis15,
metadata discovery/no-store/auth, browser mobile/switch và regression.

S2.1B2d Ads, S2.2 lifecycle/quota, S2.3 Settings tích hợp vẫn riêng. Managed MCP
OAuth đầy đủ và external server acceptance chưa được suy ra từ local gates.
