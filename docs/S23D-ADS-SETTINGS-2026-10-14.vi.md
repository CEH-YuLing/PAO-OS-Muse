# S2.3D — Ads Settings lifecycle/help: local accepted

14/10/2026, target `F:\PAO-ACOS`. Không sửa backend/migration/.env/flags hoặc
protected source; không login/provider thật, sync/Ads writes thật hay deploy.
Full S2.3/S2, Meta live login và production gates còn mở.

## Hoàn thiện ở checkpoint này

- Tách OAuth handlers/legacy Meta-Google cards khỏi SettingsWorkspace sang
  AdsConnectionSettings + helper/type/CSS/tests riêng. Own snapshots, không
  reload parent rồi mất notice; System Status vẫn là observation độc lập với
  timestamp cũ, không giả đồng bộ đã cập nhật sau child action.
- GET status từng provider independently, validate bool/status/scopes, không
  coercion truthy/partial data. Error/lost response bỏ provider snapshot/drafts,
  khóa actions tới manual GET; không tự retry. Provider khác không thành lỗi
  chỉ vì một provider failed. Đồng bộ quyền vẫn do backend/context transport.
- Synclock/epoch/abort/15s GET/20s action deadlines; lock controls khi pending,
  bỏ response cũ sau đổi actor/SME/role. Không giữ consent/account/job draft
  SME trước; operator không OAuth/disconnect/password controls.
- Popup about:blank tạo trực tiếp từ click trước await API; blocked popup không
  gửi OAuth start. Bỏ opener, referrer policy, dùng tên cửa sổ riêng. Chỉ navigate
  sau URL validation provider host/path/client ID/unique allowlisted params/
  state/exact callback origin/path/scope. Không render/log URL state hoặc token.
- Meta URL chỉ ads_read, không ads_management; Google adwords scope rộng phải
  kết hợp provider role Read-only + native grants/account pins. Google host API
  access hướng dẫn Cloud project hiện hành, không API Center/developer-token
  đăng ký mới. Không nâng REST/Graph API version, tự mở scope hoặc nạp lại host.
- OAuth ack riêng, không tự connected sau popup; manual refresh sau callback.
  Đổi SME/unmount/refresh đóng cửa sổ owned; đóng popup/abort không hủy server
  state còn hạn hoặc callback đã chạy. Native state/cookie/version/member fences
  giữ nguyên; không invent cancel API hay client nonce/CAS cho start/delete.
- Explicit GET cached accounts và20 job gần nhất của connection chính mình,
  không provider I/O/discovery. Account dropdown chỉ xem ID, không lưu destination
  hoặc grant. Registered legacy source vẫn deny, help chỉ phần quyền Ads riêng;
  không fallback qua owner SME khác hoặc broad discovery để làm xanh.
- Disconnect ack + confirm; DELETE native purge token/invalidate OAuth state/
  cancel queued-running jobs. Revoke provider riêng; grants/history/job cũ không
  tự sống lại. Lỗi mạng sau DELETE không tự gửi lại hay giữ connected cũ.
- Không nhập secret tại Ads component. Host Meta App form giữ native single-owner/
  single-workspace/local guard và cảnh báo; không gọi host App ID/Secret là BYO
  SME. S3 Telegram nhiều bot/S4 tenant App/OAuth giữ đúng scope đã duyệt.
- [Provider dossier](S23D-ADS-PROVIDER-DOSSIER-2026-10-14.vi.md): Google official
  OAuth/access-model/policy đã đọc; Meta official pages trả429/internal-error,
  không giả đã xác minh tài liệu hiện hành. Chỉ refactor native flow đang có;
  gate đọc lại Meta docs/App Review/use-case trước S4/live vẫn mở.

## Bằng chứng kiểm thử

- Affected lượt đầu **104 passed/1 failed**,163.25s: **100 native backend** và
  **4 browser regression** đạt; new Ads browser fail ở harness đếm POST login
  như Ads mutation, không phải lỗi callback/provider. Đã sửa reset capture sau
  login, giữ strict boundary chỉ OAuth start/DELETE connection. Lượt earlier
  khác58.96s fail do helper chọn SME A luôn chờ disconnected dù A connected;
  sửa assertion chờ stored status hợp lệ, không thay code permission để pass.
- Bản cuối new Ads HTTP browser **1/1 passed**,22.60s; hợp với4 regression trên
  source frontend/backend không đổi = **5 browser scenarios đạt**, không gọi
  lượt104/1fail là full backend/checkout xanh. Regression gồm granted Meta
  account sync/report/revoke, S23A observations và2 S23C lifecycle/legacy calls.
- 100 native gồm Meta/Google OAuth/token encryption/cookie replay/account/sync,
  Ads tenant authority/read resources và Meta host config guards. Bao gồm4 native
  real ARQ tests (MCP không thay SourceWorker);4 ARQ.close deprecation warnings
  cũ giữ nguyên. Không skip, nới quota/role fences hoặc disable warnings/lint.
- New browser dùng API/Web/cookie/database thật; provider landing HTTPS bị
  fulfill offline, exchange/identity/accessible mock. Popup blocker0POST;
  malicious OAuth host bị chặn;2 callback native thành công với cookie/state,
  opener null; Meta/Google caches/jobs đọc rõ; delayed A start sau switch B
  không navigate/render; operator0controls; return A mất drafts; committed Meta
  DELETE response lost chỉ1 request/manual recovery; mobile Google ack+delete.
- Đúng4 starts,2 DELETE,2 offline provider landings/2 callbacks,0 sync/Ads write.
  Meta exchange/identity và Google exchange/accessible mỗi loại1. Hai connections
  cuối thuộc SME A, disconnected/token purged; OAuth states used,0queued/running
  fixture jobs. Không cookies/token fixture main hoặc browser storage.
- Browser console0React/hydration/unknown errors,5 expected HTTP failures;
  không ghi raw provider URL/errors/token vào diagnostic. Final report/screenshot:
  `.runtime/s23d-ads-browser-75f80bb8726f44128e1f25960ac96300/`.
  Panel/mobile screenshot đã xem; actual mobile disconnect/no overflow đạt.
  Composer overlay/long legacy Settings mobile polish vẫn mở, không fullUX claim.
- **71 Node/runtime/SSE passed**,0skip (64 trước đó +7 Ads helpers); TypeScript
  noEmit đạt sau sửa variable destructuring wrapper, isolated production build
  **21/21** đạt. Các lint warnings ngoài scope còn tồn tại, không disable lint.
- Installed GET-only9/9 snapshots/schema0058/OpenAPI334/binding
  `c136c3aa3f11a5f582fa007f5a5820f6b3d1e68ac5f64ce72cbd5cf01d6b72a9`
  giữ nguyên; API/ready/Web200, ARQ workerhealthy, Telegram bridge disabled.
  Native connection hashes/.env không đổi trong live check, không external calls.
- Seal source+DB sau docs trong `.runtime/checkpoints/`, exact restore clone
 0058/125physical/124business/3archives/row hashes/schema equivalence/main
  unchanged. Giữ source/dump backup, chỉ drop clone của invocation; không Git
  init/commit/push/migration hoặc deploy. Không đổi docs sau seal để ghi manifest.

## Tiếp theo duy nhất

**S2.3D local_accepted; S2.3E — Host-config Settings lifecycle/scope kế tiếp.**
E là phần host-config đã mở trong S2.3: rõ managed host vs SME connection, bảo vệ
App Secret/drafts/unknown/role/runtime restart boundaries trên form hiện có.
Không chuyển host secret sang tenant vault hoặc implement S4 trong UI checkpoint.
Team/account/mobile consolidation và full integrated S2 gate tiếp tục còn mở.

Local OAuth fixtures không giải quyết Meta login bị provider chặn, App Review,
Cloud approval/quota/billing, true-provider health/benchmark hoặc production.
Meta official dossier refresh gate còn mở vì rate limit nguồn; không gọi tất cả
kết nối SaaS/Settings/S2 đã hoàn thiện từ các kiểm thử local này.
