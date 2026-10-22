# ADR-S2.1A — Kiểm kê kết nối và xem trước mapping

Ngày 11/10/2026. Target `F:\PAO-ACOS`; nguồn gốc `F:\Apex` không thay đổi.
Đây là checkpoint đầu của S2.1, **không phải S2.1/S2 hoàn tất**.
Trạng thái: [local_accepted](S21A-LOCAL-ACCEPTANCE-2026-10-11.vi.md) trong corpus đã định.
Thứ tự do master roadmap sở hữu. Không gọi dịch vụ thật trong checkpoint này.

## 1. Audit source hiện tại và phần tái sử dụng

| Nhóm | Nguồn hiện có | Ownership/version đang có | Phần còn thiếu |
|---|---|---|---|
| Model OpenAI/Anthropic/Gemini/OpenRouter | `model_provider_connections`, model_api/model_router, engines/service | Workspace; unique workspace/provider; chưa có manager ID hoặc config_version. Engine đã pin hash ciphertext và kiểm lại trước resolve | Identity/config version/manager rõ, nhiều connections cùng provider, grants và quota SME; không thay ciphertext hash fence bằng preview |
| MCP read-only | `connector_connections/secrets/events`, modules/connectors | Creator + owner/admin membership, private Brain ACL; version/manifest/schema/bound arguments và queued guards | Team/brand grants riêng; composite Brain/workspace DB fence; không coi manifest tool grant là grant cho nhân viên |
| Meta Ads | `meta_connections`, OAuth states, jobs, snapshots, warehouse | Workspace + connecting user, connection version; OAuth/browser state và worker recheck | App config còn installation-local; selected connection, brand/account/team grants, managed/BYO migration ở S4 |
| Google Ads | `google_ads_connections`, OAuth states, jobs, warehouse | Workspace + connecting user, version; worker recheck | Client/secret/developer token còn installation-local; team/account grants và managed/BYO ở S4 |
| Telegram | config.py, telegram.py, peers/updates/deliveries, channels, bridge | Một installation bot; peer/binding có workspace nhưng bot/dedup chưa namespace theo connection | Explicit bot mapping, nhiều bot, transport ownership/dedup ở S3; không tự chọn SME đầu tiên |
| Ollama | config.py, gateway/engine | Installation endpoint/model, compute dùng chung; context vẫn theo run/Brain/SME | Policy/endpoint reference/quota theo SME ở S2; không nhân bản local model hay chia memory vì dùng chung compute |
| TikTok Ads/Facebook Pages | Chưa có adapter tương ứng đã nghiệm thu trong source | Không tạo connection giả từ trang UI | Provider dossier/auth/adapter/tests riêng sau nền S2 |
| Voice, local channels, workflow/CLI | Các engine/channel/execution hiện có | Local capability không tự thành external connection | Không tạo bản ghi credential từ tên engine; giữ các gates hiện tại |

Audit này dựa vào checkout hiện tại, không xác minh hợp đồng API/version của
provider trên Internet. Không thay adapter/auth flow nên chưa dùng một hồ sơ
provider làm bằng chứng live. Trước S3/S4 hoặc thay connector/model auth, phải
đọc tài liệu chính thức hiện hành theo AGENTS và ADR-S02.

## 2. Contract triển khai S2.1A

`GET /v1/workspaces/{workspace_id}/connection-inventory`

- Principal active và membership owner/admin ở **workspace được yêu cầu**.
  Vai trò ở SME khác không cấp quyền. Nonmember404, member không manager403.
- Inventory model là workspace metadata; không tự suy creator/manager từ owner
  đầu tiên. Meta/Google/MCP giữ filter connecting user/creator hiện tại; không
  owner/admin bypass để kiểm kê các connection của người khác.
- MCP còn lọc Brain đúng workspace, chưa archive, owner hoặc BrainMember đúng
  workspace. Private Brain của đồng nghiệp không tự được đọc. Kết nối bị ẩn
  không xuất count/ID; đây là inventory **trong quyền hiện có**, không full-platform export.
- Identity là `{workspace_id, kind, connection_id, provider}`. Remote account ID,
  tên SME/brand/provider hoặc người dùng chung không là identity.
- Projection SQL chỉ ID/status/owner/version/provider và boolean credential
  tồn tại. Không load ciphertext value, decrypt, endpoint, model, scopes,
  manifest/payload, key hint hoặc global config. Không probe provider.
- `stored_status` chỉ là giá trị DB, `acceptance=not_verified_by_inventory`.
  Không gọi credential_present thành configured/healthy/accepted.
- Limit1–100 và offset0–10000 **cho từng kind**, stable order created_at/ID,
  `has_more` từng kind. Không merge page bằng tên/remote ID.
- Installation sources là danh mục tĩnh, không chứa cấu hình hay presence thật,
  không gán token/app vào SME nào. Telegram và Ollama không giả thành DB row.
- `Cache-Control: no-store`; input validation không echo giá trị; JSON8KiB bounded.

`POST /v1/workspaces/{workspace_id}/connection-inventory/mapping-preview`

- Chỉ SELECT; không lưu mapping, đổi owner/credential/status/secret, ghi audit
  giả hoặc enqueue. Request không nhận token/secret/endpoint; extra fields bị từ chối.
- Connection phải đúng workspace và native ownership/Brain ACL hiện tại;
  expected_version phải khớp. Model chưa có version thì trả null + blocker,
  **không giả version1** và không suy manager từ actor.
- Brand nếu chọn phải cùng SME. Grantee phải active và có role owner/admin/
  operator/analyst trong SME; viewer không được dự kiến quyền gọi công cụ.
- Ads cần account cụ thể có dữ liệu đã quan sát local của đúng connection và
  version. Warehouse account còn kiểm source job completed đúng connection/version;
  Meta snapshot chỉ từ completed account sync. Cùng account ID ở SME B không đủ.
  Không đọc payload account hoặc gọi API để xác minh.
- `permission=read_only` chỉ là ý định review, không cho gọi tools/model.
  MCP/model không nhận account Ads. Không suy grant toàn bộ tài khoản từ token.
- Hash deterministic chứa identity/version/native manager/status/presence/
  brand/account/grantee/role/requester; chỉ giúp đối chiếu review. Không phải
  signed token, approval, reservation hoặc admission pin; không có apply endpoint.
- Luôn `grant_applied=false`, `executable=false`, có blocker cần S2.1B.
  Credential thiếu/status chưa connected hoặc model chưa version/manager được
  ghi rõ; reference validation không là live acceptance.
- Snapshot đọc không atomic với revoke xảy ra đồng thời. Preview không dùng làm
  authority nên không có side effect; bước apply/execute sau phải đọc lại/lock.

## 3. S2.1B — bước tiếp theo, chưa triển khai

1. Từ native rows xây metadata identity/reference **không sao chép secrets** và
   không tạo credential engine thứ hai. Unique theo workspace/kind/native ID;
   schema/check/FK cụ thể chốt trước migration. Rà legacy orphan/foreign Brain.
2. Có preview + explicit apply do manager được phép thực hiện, chọn SME/manager/
   brand/account/grantee rõ. Không lấy owner/workspace đầu tiên làm mapping;
   installation token chỉ được migrate bởi flow S3/S4 được chọn và kiểm riêng.
3. Model bổ sung version/manager hoặc scope quản lý rõ; reuse engine ciphertext
   binding. Version tăng khi thay cấu hình/quyền; không repin run cũ tự động.
4. Grant có workspace/connection/brand/account/principal/permission/version/
   expiry/revoked và immutable audit. Manage không đồng nghĩa use hay spend.
   Owner/admin không tự cấp quyền private Brain của đồng nghiệp.
5. Resolver/execution adapter recheck membership active/role + native ownership/
   Brain + grant + version + account trước decrypt/external call và publish;
   job queued không dùng preview hash hoặc cached Settings làm quyền.
6. Tái sử dụng MCP/Ads/engine fences hiện có; thử revoked grant/rotation sau enqueue,
   hai SME cùng provider/remote account, không credential fallback chéo tenant.
7. Verified pre-migration checkpoint, clone upgrade/rollback/hash preservation,
   corpus trên pao_test/Redis15; rollout từng provider, không sửa DB tay.

S2.2 vault/reference/rotate/redaction/SSRF/quota và S2.3 Settings vẫn pending.
S3 Telegram/S4 Ads không được gọi đã tenant-aware chỉ từ inventory này.
AI tùy chọn theo job giữ S5.3; model choice không cấp tool permission.
