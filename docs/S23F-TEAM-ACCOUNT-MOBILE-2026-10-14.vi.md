# S2.3F — Tài khoản, đội ngũ và Settings mobile: local accepted

14/10/2026, `F:\PAO-ACOS`. Checkpoint cuối của phần UI S2.3, không thêm
checkpoint G/H. Không sửa backend/schema/contract/quyền native/.env thật,
không invite/grant/revoke tự động, provider thật, Ads writes hoặc public deploy.
S2.3 và toàn S2 còn cổng nghiệm thu tích hợp cuối, không đóng từ focused tests.

## Thay đổi

- General có SettingsAccountTeam: tách tài khoản cá nhân, mã tài khoản, số SME
 trong snapshot đăng nhập với SME đang chọn/mã SME/vai trò trong phiên.
 Không coi snapshot phiên là kiểm chứng quyền hiện tại; backend recheck mỗi
 request. Một người là owner ở SME A không có quyền quản lý SME B mặc định.
- Owner/admin đọc endpoint native `connection-inventory/options`; operator/
 analyst/viewer chỉ thấy tài khoản và ngữ cảnh của mình, không gọi endpoint
 quản lý. Không tạo endpoint nhân sự hoặc mở rộng permission để làm xanh UI.
- Endpoint này là danh sách active eligible grantees (owner/admin/operator/
 analyst), không phải toàn bộ nhân sự. Tối đa 100 thành viên và 100 nhãn hàng;
 has_more chung không chỉ rõ nhóm thiếu, chưa có pagination ở endpoint này.
 UI ghi đúng giới hạn/filter, không gọi kết quả giới hạn là danh bạ đầy đủ.
- Profile JSON đóng, UUID/text/role/boolean/giới hạn/duplicate validation; extra
 fields hoặc missing/truthy flags không thành danh sách đáng tin. Payload native
 không có workspace_id; scope được giữ bằng URL/auth/native SQL/transport và
 epoch, không giả client có thể tự chứng minh mọi hàng thuộc SME.
- Owned GET-only lifecycle no-store, synclock, epoch, abort/15s deadline; bỏ
 snapshot trước refresh, thất bại/response sai => unknown và manual recovery.
 Không echo lỗi riêng tư, không auto retry hoặc publish response cũ sau đổi
 actor/SME/role. Tab đổi/unmount hủy request và bỏ metadata đang giữ.
- Giải thích mapping/consent/version/expiry/brand/account là chốt riêng; consent
 đã ghi không bảo đảm grant còn effective. Model không cấp tool/Ads/Brain;
 brand null không là wildcard. Nút xem quyền chỉ đổi tab sang các panel native
 hiện có; không tự stage/activate/revoke hoặc gộp private Brain/credentials.
- Hội thoại hiện tải không phải tổng SME; agent catalogue không phải đang chạy
 hoặc AI đã gán cho job. Bỏ ENABLED/provider-default suy diễn ở agent catalogue;
 giữ yêu cầu custom routing từng job ở S5.3, không triển khai vượt scope.
- CSS Settings scoped: min-width/wrapping, profile và grid responsive, focus
 outline, scroll margins, tap targets tab/refresh và khoảng trống cuối form.
 Giữ navigation, Ask PAO/Copilot, quota và mọi thao tác hiện có; không đổi shell
 hoặc gỡ chat để xử lý ảnh full-page của phần tử fixed.

## Kiểm chứng

- **63 native backend tests**: inventory/grants và 2 test team mới. Hai SME,
 owner/admin/operator/outsider, inactive/viewer filters, revoke membership,
 no-store, SELECT-only và bounded 100/has_more giữ đúng semantics. Không sửa
 backend, không migration. Tests trên pao_test/Redis15, không database chính.
- **8 browser cases khác nhau** đạt: F team/account, A observations, E host/scope,
 B Cloud, C MCP lifecycle/legacy và D Ads. Sweep67/67 (143.95s) và regression5/5
 (130.55s) có F lặp để kiểm ảnh cuối; không cộng thành 72 test khác nhau.
 Final F1/1 (23.22s) kiểm thêm sidebar/viewport screenshots sau resize settle.
- F: native HTTP rồi synthetic failed/malformed/partial overlays; metadata cũ
 mất khi lỗi, không echo private error; late owner GET sau switch operator bị
 bỏ, operator/reload không gọi manager API; cả 6 Settings tabs ở390/320px không
 horizontal overflow. Focus + elementFromPoint xác nhận tâm điều khiển có thể
 tương tác sau owned snapshot tải xong, không dùng nút disabled làm focus proof.
 Sidebar đổi SME, desktop navigation và Copilot vẫn tương tác; 0 UI mutation,
 không có TenantConnectionGrant/Reference được tạo bởi F.
- F console0React/hydration/unknown issues. Có1 cảnh báo THREE.Clock deprecated
 của Orb cũ lúc login; classifier chỉ tách đúng literal warning này và ghi
 riêng, không gọi toàn app warning-free hay đổi Three.js trong checkpoint UI.
 Những lượt đầu fail do focus trước snapshot hoàn tất và cảnh báo baseline;
 đã sửa harness/chờ đúng trạng thái, không nới quyền hoặc bỏ assertion mutation.
- **80 Node/runtime/SSE passed**,0skip. Production build21/21 đạt, TypeScript
 standalone chạy sau browser/build để tránh generated-cache race. Warnings
 ESLint có sẵn còn; không disable lint, sửa tsconfig hoặc claim hết tech debt.
- Installed GET-only9/9 status snapshots và team profile hợp lệ (1 eligible
 member/0 brand/has_more false). Đây là dữ liệu hiện có, không auto seed SME
 thật. Native connection/team/grant hashes và .env hash không đổi. API/ready/
 Web200, ARQworkerhealthy, Telegrambridge disabled. Frontend primary dev bundle
 chứa SettingsAccountTeam; không cần restart API/worker.
- Schema0058/live334/binding
 `c136c3aa3f11a5f582fa007f5a5820f6b3d1e68ac5f64ce72cbd5cf01d6b72a9`
 giữ nguyên. Local fixture/browser không là provider live, production hoặc
 nghiệm thu bàn phím/mic trên điện thoại vật lý.
- Final F report/screenshots:
 `.runtime/s23f-team-browser-7e6c1c8ee0c0494ea76177e727a41c89/`.
 Desktop/mobile viewport thật đã xem. Full-page ảnh có thể tái bố cục fixed
 sidebar/launcher; không dùng nó thay viewport geometry/hit-test. B/C/D final
 browser reports nằm ở .runtime theo invocation, giữ history lỗi để đối chiếu.
- Source+DB seal sau đồng bộ docs; exact restore clone kiểm row hashes/schema/
 0058/125physical/124business/3archives và primary unchanged. Backup/source giữ
 trong .runtime/checkpoints, credential/key cần procedure private riêng; không
 Git init/commit/push. Không sửa docs thêm manifest self-reference sau seal.

## Tiếp theo duy nhất — Nghiệm thu tích hợp toàn bộ S2

S2.1/S2.2 và UI S2.3A–F đạt từng local checkpoint. Tiếp theo chạy full backend
regression, resource/authority/private Brain/real ARQ corpus, runtime/SSE, build,
browser các luồng liên quan, live contract/binding/health và backup/exact restore.
Chỉ sau kết quả tích hợp mới đóng S2; không bắt đầu lại P6 hoặc mở S3/S4 trước gate.

Provider live/OAuth/App Review, tenant App vault/S4, Telegram nhiều bot/S3,
global host fairness, SaaS public admin/HTTPS/reboot và P7 mic thật còn gate riêng.
Không cần hỏi lại lựa chọn sản phẩm đã chốt hoặc credential để nghiệm thu local.
