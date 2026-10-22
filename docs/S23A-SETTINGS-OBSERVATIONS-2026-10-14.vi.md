# S2.3A — Trạng thái Settings đáng tin cậy, local accepted

14/10/2026, target `F:\PAO-ACOS`. Master sở hữu thứ tự. Đây là bước nền
read-only của S2.3, không phải nghiệm thu toàn bộ Settings hay toàn S2.

## Audit và phần đã sửa

Controller cũ dùng Promise.allSettled nhưng chỉ cập nhật các hàng thành công;
refresh lỗi để lại giá trị của lần trước. Không có epoch/deadline riêng cho
refresh. Telegram enabled+configured bị hiển thị connected; System Status
đánh READY từ cấu hình/token; safety mất dữ liệu lại mặc định disabled/safe.

- `useSettingsStatus` dùng tenant apiRaw/no-store/body-ticket hiện có; own
  abort+epoch, timeout15s mỗi GET, cleanup/unmount. Mỗi refresh bỏ toàn bộ
  observations cũ trước khi đọc. Chỉ kết quả của thế hệ hiện tại được publish.
- `settings-status.mjs` kiểm shape cho chín nguồn GET; dữ liệu malformed dù
  HTTP200 vẫn unknown. Không gọi discovery/test/OAuth để làm xanh status.
  Endpoint lỗi hiện tên nguồn+manual recovery, không echo raw private error.
- Meta/Google status theo actor+SME; configured là App runtime trên bản cài,
  stored connected chỉ là nhãn OAuth đã lưu. Healthy và nghiệm thu thật không
  suy ra từ chúng. Thiếu App xác nhận khóa nút OAuth; không đổi OAuth params.
- Telegram/Voice/Temporal được ghi rõ host runtime, không phải kết nối riêng
  SME. Telegram có token không thành connected. Voice dependency readiness
  không thay mic thật. System Status dùng OBSERVED/UNKNOWN, không READY giả.
- Safety chỉ đọc đủ dữ liệu mới hiển thị cờ. Unknown không SAFE MODE; kể cả
  write gates off cũng không chứng nhận quyền thực thi/production.
- Hiển thị thời điểm GET và giải thích đó không phải last provider check.
  Runtime context vẫn remount theo actor/SME/role revision; không repin jobs,
  mở tool/Brain/Ads grants, thay quota/vault hoặc thêm dữ liệu giả vào main.

Các nguồn giữ scope native:

| Nguồn | Phạm vi | Chỉ báo |
|---|---|---|
| Meta / Google connection | actor trong SME đã chọn | OAuth state đã lưu, không live health |
| model-providers listing | SME | Metadata kết nối, không tự fetch model catalogue |
| Platform catalog | query SME, có cả host flags | Evidence native; không nâng legacy labels thành healthy |
| Telegram / Voice / Temporal | bản cài máy chủ | Cờ/dependency readiness, không credential riêng SME |
| Ads write / autopilot | bản cài máy chủ | Gates, không quyền thực thi |

## Kiểm chứng trên bản cuối

- **76 passed**,0skip,131.70s: platform/readiness, Meta app Settings,
  model metadata và hai HTTP browser tests (S23A mới + B3 regression).
  Không phải full backend mới. Không đổi backend/schema nên không migration.
- **49 Node/runtime/SSE** đạt (35 baseline+14 Settings), TypeScript và isolated
  production build21/21 đạt. Không tắt lint; warnings ngoài phạm vi vẫn có.
- Browser HTTP thật kiểm stored connected không healthy/accepted; Telegram
  flags không connected; refresh503 bỏ state cũ/khóa OAuth; private error
  không render; JSON200 malformed vẫn unknown; safety thiếu không safe;
  normal refresh recovery; response A trễ trong lúc chuyển B; reload B;
  mobile390x844/menu switch và operator không nút OAuth. Không API mutation.
- Synthetic status overlays khai báo rõ trong browser report, không giả
  provider acceptance. Sau browser native Meta/Google/model connections0.
- Browser report/screenshot:
  `.runtime/s23a-settings-browser-b18e80a24df54ba58b25f320148895b2/`;
  B3 regression `.runtime/s22b3-quota-browser-29639047074a49239244b3b7c96bb529/`.
  Screenshot đã xem: không overflow ngang; MCP/legacy forms còn chật trên
  mobile, không coi UX toàn trang đã hoàn thiện.
- Installed **9/9 snapshots** qua chính validator frontend, API/ready/Web200,
  OpenAPI334/schema0058/binding`c136c3aa3f11a5f582fa007f5a5820f6b3d1e68ac5f64ce72cbd5cf01d6b72a9`
  không đổi. Native connection row hashes/.env không đổi. Không gọi provider.
- Baseline trước sửa `check_s22b3_live.py` đạt. Checkpoint cuối source+DB
  lưu riêng `.runtime/checkpoints/`; exact restore chỉ trong clone mới,
  so row hashes/schema/archives và primary unchanged. Chỉ drop clone của
  invocation, giữ dump/source backup. Không tạo Git/push/commit hoặc đụng Apex.

## Ranh giới / checkpoint kế tiếp

**S2.3A local_accepted; S2.3 in_progress.** Không nâng global Telegram thành
multi-bot SaaS; không chuyển Meta .env thành BYO SME hoặc thay auth fields.
Những phần đó giữ thứ tự S3/S4. Không thay đổi credential/gates, gọi Meta thật,
đăng nội dung, chi tiền hoặc deploy. Chưa fullS2/global host fairness/production.

**Tiếp theo duy nhất S2.3B: Cloud Model Settings lifecycle và help.** Tách form
model khỏi file Settings lớn, clear credentials/drafts sau failure/switch/role,
operation locks/deadlines và result publication, unknown-save/manual recovery,
metadata nonce/CAS theo native contract, explicit model/probe consent và
registered-grant refusal; không auto catalogue on focus hay automatic inference.
Đọc official provider docs trước thiết kế help/auth flow; ghi version/date/
scopes/quota/rotation/revoke. Không hardcode provider vào job; S5.3 giữ routing.

Sau model checkpoint mới xử lý MCP/Ads/Meta host-config và team/account panels
còn lại, lifecycle/disconnect/error/help/mobile hợp nhất. Không tạo vault hay
provider engine thứ hai, không gọi form đã lưu là kết nối thật đã nghiệm thu.
