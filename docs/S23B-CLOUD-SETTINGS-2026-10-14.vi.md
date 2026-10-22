# S2.3B — Cloud Model Settings lifecycle/help: local accepted

14/10/2026, target `F:\PAO-ACOS`. Không sửa protected source; không key thật,
provider thật, Ads/data business writes hoặc deploy. S2.3/fullS2 chưa đóng.

## Đã thực hiện

- Tách legacy CloudModels khỏi SettingsWorkspace vào `CloudModelSettings`.
  Form sở hữu listing GET và mutation lifecycle riêng; không reload parent
  rồi mất success message/bản nháp do unmount như trước. Parent catalog vẫn
  có observation timestamp riêng, không giả vờ đã refresh sau child mutation.
- Fresh actor/SME/role scope qua runtime transport; own synchronous operation
  lock+epoch+abort/deadlines, all controls khóa khi pending. Không chạy đồng
  thời hai thao tác từ cùng panel, không giữ response/draft SME trước.
- Key password chỉ ở bộ nhớ form, không storage/URL/log. Clear ngay khi bắt
  đầu thao tác, validate lỗi, refresh/error, pagehide/hidden-tab event hoặc
  context remount. Không hứa zeroize mọi bản sao JavaScript/network memory.
- Connect/catalogue/select dùng UUID Idempotency-Key native, không auto retry.
  Focus dropdown không fetch; onchange chỉ staging draft; Save riêng sau
  consent. Không hardcode model/vendor vào vai trò job (routing S5.3 riêng).
- Metadata consent khác probe inference consent, probe có thể dùng token/
  phí. Registered model references giữ denial legacy probe; hướng dẫn dùng
  grant/Run đúng scope, không tự activate grant hoặc tạo Run từ form này.
- Sau lost response/API failure, form bỏ records/keys/drafts và khóa mutation
  cho tới manual GET. Cảnh báo GET khi request cũ còn pending chưa chứng minh
  kết quả cuối; không blind resend. Role/source/nonce/quota errors có help;
  không echo private error/key. Nonce không tự tái sử dụng hay đổi để retry.
- Default/disconnect dùng contract native hiện hành. Disconnect yêu cầu ack
  và confirm; chỉ xóa bản lưu PAO, không revoke key trên provider. Grants/pins/
  history/TTL cũ không revive. Không thêm vault/ledger/scheduler/backend route.
- Provider-specific help và official links theo
  [dossier đã đối chiếu](S23B-CLOUD-PROVIDER-DOSSIER-2026-10-14.vi.md).
  OpenAI Docs giúp tách standard key/server storage/Models metadata khỏi Admin
  APIs và inference; không thay default model từ trí nhớ. Anthropic workspace
  header/WIF và Gemini Vertex IAM chưa được form này hỗ trợ, ghi rõ giới hạn.

## Kiểm chứng

- Affected suite ban đầu **147 passed**,145.53s,0skip: model metadata/router/
  connection fences, metadata/model quotas và S23B/S23A/B3 browser. Hai warnings
  ARQ.close cũ giữ nguyên. Không phải full backend mới.
- Screenshot đầu có Dev issue. Thêm console gate phát hiện hai sibling
  CloudModelSettings/ModelAccessPanel dùng cùng workspace key. Đã namespace
  riêng cloud key, không che warning hoặc sửa backend để làm xanh.
- Bản cuối sau sửa: **3/3 HTTP browser** đạt60.96s; 144 native backend tests
  trước đó không đổi source/backend binding. Không gọi lượt147 đầu là final
  full checkout console-clean. Cloud browser console chỉ có2 expected HTTP
  failures (lost response và registered probe refusal),0React/unknown errors.
- **57 Node/runtime/SSE** đạt (49 baseline+8 cloud helpers), TypeScript và
  isolated production build21/21 đạt. Không disable lint; warnings ngoài scope
  còn tồn tại. Không overlap build/browser cache hoặc pytest pao_test/Redis15.
- Cloud browser thật kiểm local invalid-key clear; POST commit response lost
  chỉ1 request; manual refresh, no focus-fetch; catalogue nonce, staged select;
  explicit probe; second provider connect/default/disconnect; mobile catalogue
  action; delayed A response khi chuyển B; registered B probe deny before
  factory; hidden-tab event clear; operator không key/probe controls; return B
  không draft; DOM/storage không chứa full fixture key. Fetch/gateway đều fake.
- Fixture ghi nhận **7 metadata admissions,1 management probe**,2 model
  connection rows cuối (A model thứ hai, B model thứ nhất), factory/stream1/1.
  Native grants/actor/source fences không bị bypass. Không dữ liệu fixture main.
- Report/screenshot bản cuối:
  `.runtime/s23b-cloud-browser-90e31ebe285a49e2bf96eeb8637f78c1/`.
  Screenshot đã xem; mobile interaction/no horizontal overflow đạt. Grant/
  composer/legacy forms toàn Settings còn cần polish, không nghiệm thu toàn UX.
- Installed GET-only check:9/9 snapshots hợp lệ,0058/live334/binding
  `c136c3aa3f11a5f582fa007f5a5820f6b3d1e68ac5f64ce72cbd5cf01d6b72a9`
  không đổi; native connection hashes/.env không đổi, API/ready/Web200.
- Checkpoint cuối source+DB niêm phong riêng `.runtime/checkpoints/` sau docs,
  exact restore clone125physical/124business/3archives/0058 so row hashes và
  schema definitions, primary unchanged. Chỉ drop clone của invocation; giữ
  dump/source backup. Không migration, Git init/push hoặc copy secret.

## Ranh giới

Đây là UI/native local gates. Chưa actual provider health/billing/quota,
multi-workspace Anthropic/WIF/Vertex IAM, provider OAuth hay production. Native
source-stamp CAS qua metadata I/O giữ nguyên; default/delete/probe chưa có
durable client CAS/nonce chung. Không gọi frontend checks là CAS mới cho CRUD.
Backend initial model/default selection giữ nguyên, không tự chọn model mới
nhất, thay API version hoặc model routing S5.3 trong checkpoint này.

**S2.3B local_accepted; tiếp theo duy nhất S2.3C MCP Settings lifecycle/help.**
Tái sử dụng P5 registry/transport/native grants, đọc MCP official spec trước
UI changes, clear bearer/drafts/error/publication/nonce/disconnect/audit/mobile.
Ads/Meta host config/team/account integration còn lại sau MCP; Telegram bot
SaaS và tenant app credentials giữ S3/S4, không tự kéo vào bước này. Final S2
regression/release vẫn gate riêng, không nghiệm thu từ số tests hoặc fixtures.
