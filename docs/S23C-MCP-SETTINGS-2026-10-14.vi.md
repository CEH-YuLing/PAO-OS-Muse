# S2.3C — MCP Settings lifecycle/help: local accepted

14/10/2026, `F:\PAO-ACOS`. Chỉ checkpoint Settings MCP; không sửa backend/
migration/flags/credential thật hoặc nguồn bảo vệ. Full S2.3/S2 còn mở.

## Thay đổi

- Refactor ConnectorPanel với helper/type/tests/CSS riêng, tái sử dụng native
  P5 transport/registry/vault/grants/Gateway. Owner/admin quản lý kết nối của
  mình trong SME; operator không có password/management controls. Không gán
  model vendor vào job, không biến token nhập được thành quyền thực thi.
- Own synchronous operation lock, epoch, abort và deadlines15s GET/60s thao
  tác; tenant transport/body fences giữ nguyên. Busy khóa controls/selection;
  response cũ không publish sau đổi SME/role. Không reload parent rồi mất toast.
- Bearer không storage/URL/log; clear ở operation start/local validation lỗi,
  failed response/refresh/selection/context/pagehide/hidden-tab event. Endpoint/
  arguments/run/key/consent drafts cũng bỏ; không hứa zeroize JS/network memory.
- HTTPS/domain/path và token prevalidation; strict native snapshot workspace/
  version/protocol/tool namespace/permissions, không Boolean coercion hoặc tin
  partial GET. Native backend vẫn quyết định DNS/SSRF/credential/schema/quyền.
- Discovery consent riêng và UUID Idempotency-Key native, không tự gọi khi
  focus/select/refresh; version CAS/source/actor/Brain/publication/quota giữ.
  Không thêm client nonce vào create/rotation/permissions/disconnect khi API
  không có contract đó. ReadOnlyHint không phải authorization/read-only proof.
- Rotate dùng endpoint credential native: version conflict bị từ chối, token
  mới đưa về draft và xóa permission/cancel calls; không auto-discover/regrant.
  Permission cần schema/hash/arguments/ack riêng; queue cần ack khác và Run/key;
  Skill publish, grant/brand/Brain/native policy luôn được Gateway kiểm lại.
- Lost response hoặc API failure bỏ records/drafts và khóa mutations đến manual
  catalog GET; không retry/replay hay tự đổi nonce. GET khi request cũ chưa kết
  thúc không bảo đảm kết quả cuối. Stable error help cho quota/version/auth/
  circuit/profile/authority; không render raw provider error chứa private data.
- Disconnect ack + confirmation, purge token/permission/cancel native calls;
  server token phải revoke/rotate riêng. Audit chỉ ID/action, không raw event data;
  native limits20 own connections/100 recent events ghi rõ, không full-history claim.
- [Official MCP dossier](S23C-MCP-PROVIDER-DOSSIER-2026-10-14.vi.md) phân biệt
  restricted2025-11-25 transport/bearer với OAuth metadata/PKCE/resource binding
  và protocol upgrade chưa có. Help liên kết tài liệu chính thức, không yêu cầu
  App ID/Secret chung cho tất cả server. Server thật vẫn chưa được chọn/nghiệm thu.

## Kiểm chứng

- **157 affected backend passed**,85.23s,0skip: connectors, MCP tenant authority,
  metadata resources và credential payload guards. Bao gồm2 native real ARQ
  tests;2 ARQ.close deprecation warnings cũ, không che/disable. Không full backend.
  Lượt gọi nhầm tên test lifecycle không tồn tại thu được0tests; đã sửa danh sách
  đúng, không báo lượt đó là pass hoặc thêm test giả để làm xanh.
- **5 HTTP browser passed**,99.81s,0skip:2 S23C lifecycle/legacy call, S21B2C
  granted call, S23A observations và S23B cloud Settings. Test API/Web/DB thật,
  MCP/mock provider transport giả; pao_test/Redis15, không business fixture main.
- Lifecycle browser: invalid token không POST; draft committed/response lost
  chỉ1 POST; manual recovery/no automatic discovery; discovery nonce/consent;
  bounded permission; concurrent-tab rotation gây409; rotate mới sau GET;
  delayed A metadata response sau switch B không render; hidden-tab clear;
  operator không password; mobile actual disconnect + confirm/audit/no overflow.
  Fixture có đúng3 initialize/tools-list exchanges,3 metadata leases,0tools/call,
  1 connection cuối revoked/token purged/permissions empty; không server thật.
- Legacy browser: selection đổi thì mất run/key/consent; queue chỉ sau explicit
  ack; đúng1 native tool call completed, bound arguments không lấy draft mới;
  UI bỏ run/key sau admit, không auto-repeat. Granted call replay/revoke và
  registered-source denial vẫn qua regression native và S21B2C browser.
- MCP lifecycle console0React/hydration/unknown errors;6 expected HTTP failures
  thuộc response lost/version conflict/feature-off fixture. Không che console
  React warnings; console categories được lưu không chứa token/raw provider text.
- **64 Node/runtime/SSE passed**,0skip (57 baseline/cloud +7 MCP helpers);
  TypeScript noEmit và isolated production build **21/21** đạt, không disable lint.
  Các warnings ngoài ConnectorPanel vẫn tồn tại. Không overlap build/browser cache.
- Screenshots final MCP panel/mobile đã xem tại
  `.runtime/s23c-mcp-browser-0d18daec10ab40ec8a97282333ecca60/`;
  legacy report tại `.runtime/s23c-legacy-browser-f4d4425f821544a6a2ac8531130ee980/`.
  Whole Settings composer overlay/legacy long forms còn cần mobile polish;
  không dùng panel no-overflow để nghiệm thu toàn bộ UX.
- Installed GET-only9/9 snapshots hợp lệ, schema0058/live334/backend binding
  `c136c3aa3f11a5f582fa007f5a5820f6b3d1e68ac5f64ce72cbd5cf01d6b72a9`
  không đổi; API/ready/Web200, ARQ workerhealthy, Telegram bridge disabled.
  Native connection hashes/.env không đổi trong live check; không external I/O.
- Source+DB checkpoint cuối lưu riêng `.runtime/checkpoints/` sau docs; exact
  restore clone0058/125physical/124business/3archives so row hashes/schema và
  xác nhận main không đổi. Giữ backup/dump, chỉ bỏ owned restore clone; không Git
  init/commit/push hoặc deploy. Không thêm manifest path vào docs sau seal.

## Tiếp theo và giới hạn

**S2.3C local_accepted; tiếp theo duy nhất S2.3D — Ads Settings lifecycle/help.**
D là phân rã phần Ads UI đang mở của S2.3, không phase SaaS mới: audit native
Meta/Google account/status/consent/disconnect/error/help trước, giữ read-only
grants và không sửa mô hình tenant App/OAuth/Telegram vốn ở S4/S3. Host-config/
team/account/mobile consolidation và full integrated S2 regression còn mở.

Chưa provider/server health/billing, OAuth conformance, protocol mới, global host
fairness, production reboot/HTTPS hay Ads writes. Không bắt đầu lại P6/P7 hoặc
full S2 chỉ để làm lại số tests; chỉ regression liên quan checkpoint thay đổi.
