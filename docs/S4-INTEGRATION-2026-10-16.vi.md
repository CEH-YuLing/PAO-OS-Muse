# S4 — Meta/Google theo doanh nghiệp, nghiệm thu tích hợp

Ngày16/10/2026, `F:\PAO-ACOS`. Master sở hữu phạm vi S4.1–S4.3. Không
triển khai S5 hoặc bật tài khoản thật trong milestone này.

## Trạng thái hiện hành

**Toàn S4.1–S4.3 đạt local_accepted ngày16/10.** Đã rollout0065/live353,
136physical/135business tables/3archives, API/ready/Web200, workerhealthy;
live binding aef563f8 khớp source, host config API cũ410. Dữ liệu cũ và `.env`
nguyên vẹn; không App/token thật được nhập hoặc provider/Ads/Telegram được bật.
S3 không bị mở lại. Bước tiếp theo của master là **S5 — kế hoạch doanh nghiệp
và điều phối công việc**, chưa triển khai trong lượt này.
Hồi quy toàn backend trên pao_test đã kết thúc:2089passed/10failed/0error/
0skip,1947.15s,59ARQ warnings; cả10lỗi thuộc fixture báo cáo cũ thiếu app_binding.
Đã sửa chỉ fixture, không sửa backend hoặc nới assert;52recovery và82caller
trực tiếp/gián tiếp đều đạt.2099danh tính có kết quả cuối đạt, source aef không
đổi. Giữ nguyên XML/JSON full có10lỗi; đây không phải một full rerun xanh.
Đối soát tường minh tại `.runtime/s4-regression.json`, không miễn trừ lỗi bất kỳ.
Rollout/live/exact restore sau cập nhật đã đạt; real OAuth/public HTTPS/
production vẫn external_pending, không suy từ local accepted.

Baseline đầu lượt: Docker/Desktop và PAO đã tắt. Log mới xác nhận lỗi socket
dockerInference. Thử stop có timeout20s; xác minh executable/start-time rồi
dừng đúng tiến trình Docker. Hai thư mục không reparse/chỉ có socket0byte đã
giữ tại suffix `stale-s4-735255cc0fc2447e9b7a9a54d06a06f7`, không xóa volume,
settings, reset/reinstall hoặc reboot. Engine29.4.3 phục hồi; chỉ bật hai
container ACOS PostgreSQL/Redis có sẵn. Launcher khởi động API/worker/Web,
không Telegram/Studio daemon. Không coi startup là production reboot drill.

Checkpoint trước code: `.runtime/checkpoints/p0-20261016T025909-10147544/manifest.json`,
1128source/0064/134physical/3archives, verified backup/restore. Secret không
được sao chép sang mã nguồn hoặc in vào tài liệu.

Checkpoint candidate trước release:
`.runtime/checkpoints/p0-20261016T034525-b3c18406/manifest.json`,1147source/
0064/134physical/3archives. Exact restore133business row hashes/schema tương
đương/current binding khớp/primary unchanged đã đạt; full regression vẫn phải
kết thúc trước migration. Bản chạy cũ health/ready/Web200,349operations; Meta/
Google saved tokens0 và mọi chốt provider/Ads/Telegram thật false. `.env` SHA256
vẫn `5672f74189bcef6c110d4c434e956d4f324598ee3901b88bbd56902c945fbea7`.

Sau khóa hostAPI, checkpoint candidate cuối là
`.runtime/checkpoints/p0-20261016T035515-c167f4ac/manifest.json`,1147source/
0064/134physical/3archives, verified backup/restore, bindingaef563f8. Bản
034525 thuộc candidate cũ324deb26, không được dùng thay mốc source cuối.

Checkpoint thực sự dùng trước migration:
`.runtime/checkpoints/p0-20261016T043141-486eb878/manifest.json`,1148source/
0064/134physical/3archives, exact restore đạt trước upgrade. Checkpoint sau
rollout `.runtime/checkpoints/p0-20261016T043439-bd733ddb/manifest.json` có
1148source/0065/136physical/3archives;135business row hashes exact/schema
tương đương/primary unchanged/current binding đã xác minh. Sau cập nhật
tài liệu, bản niêm phong bàn giao lưu ở checkpoint mới và được kiểm lại cùng
script, không thay backend hoặc ghi lại dữ liệu.

## Phần triển khai

### S4.1 — Sở hữu ứng dụng và OAuth

- Mặc định ứng dụng PAO (managed); nâng cao ứng dụng riêng (BYO) theo khóa
  `(workspace_id,provider)`. Không nhân bản host secret vào tenant; BYO có
  encrypted envelope riêng cho App/Client ID/Secret/API version và Google
  optional developer token/manager ID. Không lấy trường thiếu từ host làm fallback.
- URL callback thuộc máy chủ, không nhận redirect tùy ý từ form. Config có
  revision/CAS, consent và audit metadata không secret. Save không gọi provider
  hoặc đổi `.env`/chốt nền tảng; app config host cũ không còn là form SME chính.
- API host cũ mặc định410 cả khi hệ thống chỉ có một SME. Vai trò chủ SME không
  cấp quyền sửa máy chủ. Tương thích installer riêng phải opt-in host rõ ràng,
  giữ toàn bộ single-owner/loopback/no-active-token-job/read-only guards; cờ
  `META_INSTALLATION_CONFIG_ENABLED` giữ false trên SaaS dùng chung.
- OAuth state pin HMAC cấu hình/SME và connection version, cookie HttpOnly,
  SameSite=Lax,Secure khiHTTPS,10phút và một lần. Consume trước exchange;
  replay/duplicate query/cookie sai/rotation/membership loss bị từ chối.
- Callback kiểm tài khoản active và quyền owner/admin, dùng đúng app client
  từng SME, mã hóa token riêng user/SME, pin cấu hình vào connection. Không in
  code, token, lỗi provider hoặc chuyển token giữa hai SME.
- Token legacy không có app_binding bắt buộc OAuth lại; migration không tự
  nhận token cũ sang app mới hoặc xóa dữ liệu lịch sử để làm migration xanh.

### S4.2 — Một resolver cho dữ liệu, công việc và quyền

- Clients nhận config snapshot riêng, không thay settings toàn cục, không
  dùng ambient context chung giữa request/worker. Meta appsecret_proof và
  Google refresh/headers lấy cùng resolver với OAuth/connection đã chọn.
- Đồng bộ, scheduler warehouse và hành động Meta dùng cùng connection,
  version và app context. Tái sử dụng native grant/brand/account/capability,
  accounting/quota, approval và read-only GAQL; không thêm engine/queue mới.
- Mỗi HTTP provider có guard lấy lại quyền hiện hành và giữ khóa SME/source
  đến khi request kết thúc. Rotation/config save lấy khóa độc quyền; client
  cũ/queued job bị chặn trước HTTP, không tự đổi sang app/SME khác. Không hứa
  thu hồi được request đã admitted tại provider trước ranh giới revoke.
- Trigger DB ngắt mọi connection cùng provider trong SME, tăng version, xóa
  token, vô hiệu OAuth state và hủy queued/running sync khi lưu/đổi cấu hình.
  SME/provider khác không bị ảnh hưởng. Source version fences khiến schedules/
  grants/approval/report cũ không tự sống lại; history không bị repin.
- Dữ liệu cached accounts/warehouse/metrics vẫn theo connection/version;
  managed host key thay đổi cũng mất hiệu lực pin. Quyền đọc Ads không cấp
  quyền tài sản khác, discovery toàn bộ tài khoản hoặc quyền ghi.

### S4.3 — Cài đặt tiếng Việt

- Hai khung ứng dụng riêng Meta/Google tại Cài đặt → Kết nối. Mỗi khung có
  phương thức mặc định/nâng cao, revision, chốt nền tảng, trạng thái có khóa,
  callback cố định, hướng dẫn chuẩn bị/lấy từng trường/lưu/OAuth/quay vòng/ngắt.
- App/Client Secret là trường password write-only; Google developer token và
  manager ID riêng, không nhầm Gemini key hoặc customer đích. Không hứa toàn
  bộ manager hierarchy từ danh sách accessible customers.
- Lưu yêu cầu consent và xác nhận tác động ngắt kết nối. Token/mã không vào
  browser storage; secret xóa sau thao tác/ẩn trang/đổi mode/đổi SME. Request
  và response ticket/abort giữ scope; mất ACK khóa thao tác tới đọc lại.
- Nhân viên không có form quản lý, nhưng vẫn dùng nguồn/grant native đã được
  cấp; là owner SME A không cho quyền admin SME B. OAuth và quản trị app không
  thay quyền công cụ/Brain hoặc approval chi tiền.

## Gate và bằng chứng

| Gate | Kết quả hiện có |
|---|---|
| S4 corpus |20ca trước khóa hostAPI đạt; ca21 kiểm single-SME owner không có quyền đọc/ghi host đã bổ sung và đạt trong140affected cuối; actual worker HTTP fixturehai SME/cùngremoteaccount, old-client pre-HTTP denial, legacy token không tự adopt, host rotation |
| Affected trên source cuối |140passed/0fail/0skip,92.38s,4ARQ deprecation warnings; gồm21corpus và legacy installer opt-in riêng |
| Node |114passed/0fail/0skip/0cancelled, reporter gốc;8pure restore tests cũng đạt |
| TypeScript |exit0 sau nối Settings/form và Content-Type JSON |
| Migration |0064→0065→0064→0065 trên clone; old-column hashes/rollback schema exact; populated downgrade refused; primary unchanged, `s4-migration.json` |
| HTTP/rotation concurrency + restart |`s4-locks.json` đạt: rotation chờ HTTP đang admitted, SMEkhác vẫn cấu hình được, stale client bị chặn trước HTTP; tiến trình mới giải mã/pin exact, primary unchanged |
| Telegram browser regression |API/PG thật ở DBriêng0065, Telegram giả lập; pairing/team/report-only/revoke/secret wipe/mobile/SMEswitch/Việt hóa hướng dẫn đạt. Chỉ sửa harness chờ context và schema hiện hành, không mở lại S3 |
| Toàn backend |2089passed/10fixture failures/0error/0skip,1947.15s; `s4-full.xml`/`s4-backend.json` giữ nguyên.52recovery+82shared-fixture callers đạt;2099danh tính cuối đạt, backend aef không đổi, không full rerun; `s4-regression.json` |
| Fixture portability |6Telegram report tests dùng App credentials giả rõ ràng, không phụ thuộc khóa thật của máy chủ; có trong52recovery. Fixture business source thêm app_binding đúng SME, toàn bộ caller trực tiếp/gián tiếp đã kiểm |
| Browser |S4 API/PG thật/provider synthetic đã đạt managed/BYO/OAuth cả Meta và Google/rotation/unknown ACK/secret wipe/tenant-role isolation/mobile. Google test qua cả chốt tắt và bật riêng trong process fixture; BYO không mượn developer token/manager ID host. `.runtime/s4-browser.json`; XML/backend không dùng để thay browser |
| Production build |exit0,21/21trang, Settings43.3kB/161kBfirstload; cache kiểm riêng, còn React Hook warnings cũ, không tuyên bố lintclean |
| Primary rollout |0064→0065;136physical tables; old-column hashes/counts/3archives nguyên vẹn,2bảng mới rỗng; alembic check sạch; `s4-schema-rollout.json` |
| Live sau restart |API/ready/Web200,workerhealthy;353operations vàbinding aef khớp;3/3replay chỉ đọc không chạy tool; hostAPI410, provider flags/.env không đổi, `s4-live.json` |
| Exact restore |Checkpoint0065 sau rollout phục hồi sang clone riêng đạt135business/136physical/3archives, row hashes exact/schema tương đương/primary unchanged; không provider call |

<details>
<summary>Lịch sử focused trước source cuối — không thay thế gate hiện hành</summary>

33/33API/client/OAuth ban đầu đạt;174affected/4ARQ warnings đạt trước bổ sung
ca cuối. Một lượt180passed/2failed do phân biệt409/403 legacy; đã sửa đúng mã
từ chối, không nới assert, rồi corpus chạy lại đạt. Source cuối có140affected,
vòng tổng2099 và52+82kiểm lại như bảng trên. XML gốc được giữ nguyên.

</details>

## Lỗi tìm được và giới hạn

- Giữ tương thích409 `meta_app_restart_required` của cấu hình host cũ; factory
  fake trong test không có tham số config, đã phân biệt native class với factory
  injected. Không giảm quyền hoặc bỏ guard của client production.
- Hai ca HTTP fixture đầu thay package export nhưng httpx đã bind transport
  trong module client: token **giả** bị provider từ chối. Không có credential
  thật hoặc Ads write. Đã sửa cả default binding, kiểm số request/host/body/
  appsecret_proof và chạy lại đạt; không gọi hai ca lỗi đó là offline fixture đạt.
- Browser phát hiện form mới thiếu Content-Type JSON; đã sửa và typecheck.
  Harness có race điều hướng ngay sau select SME, trước khi server xác nhận
  context; đã sửa chờ lựa chọn được commit, không bỏ kiểm tenant. Selector
  connected dùng đúng nhãn “Đã lưu kết nối”, không suy ra live acceptance.
- Playwright redirect chain không đi qua callback route fixture như dự kiến;
  sửa thành provider landing offline và điều hướng callback explicit, đối
  chiếu response callback thật. Không bỏ cookie/state check. Browser sau đó
  bắt lỗi trạng thái public sau rotation: token/job đã bị thu hồi nhưng UI
  báo expired thay disconnected. Đã sửa phân biệt token connected sai pin với
  connection đã ngắt, bổ sung assert API và browser. Vòng full trước bị ngắt
  ở27% để đưa sửa này vào; không coi vòng bị ngắt là passed. Vòng cuối pin
  backend324deb26 cũng bị ngắt ở34% để khóa thêm hostAPI mặc định sau review;
  cả hai vòng ngắt không có XML hoàn tất và không dùng làm gate. Source cuối
  cố định `aef563f8c0664b061f47961cae673afc5372923563bc5a663b04153c3ce19977`,
  đã qua140affected/browser/lock/fresh-process; full cuối chạy lại trên đúng
  binding này. Không sửa backend trong vòng cuối.
- Tài liệu trực tiếp Meta vẫn429; hồ sơ chính chủ và giới hạn tại
  [provider dossier](S4-PROVIDER-DOSSIER-2026-10-16.vi.md). Không bypass App review.
- Local corpus không là benchmark tải lớn, phép đo quota/hóa đơn, nghiệm thu
  OAuth tài khoản thật, HTTPS/public callback hoặc reboot/production restore.
- TikTok native còn backlog S6; không thêm form khóa giả. S5 business planning
  và AI routing theo job chưa triển khai từ các form S4 này.

## Gate bên ngoài

Meta app review/real OAuth, Google consent/API access/real account và public
HTTPS callback cần tài khoản/phạm vi được owner cấp riêng. Chưa yêu cầu secret
qua chat, chưa tự nối tài khoản hoặc bật flag thật. Giữ external_pending.
