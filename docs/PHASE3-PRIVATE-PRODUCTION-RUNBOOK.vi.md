# Giai đoạn 3 — CI và bộ triển khai production riêng

**Cập nhật hosted CI:** run39030584315, commit3151851 đã accepted theo
[biên bản](PHASE3-HOSTED-CI-ACCEPTANCE-2026-10-17.vi.md):18stage/2258backend/
120Node/build23, runtime audit Python57/0/npm0. Main chưa merge; không deploy.
Trạng thái tổng hợp mới `.runtime/phase3-current-status.json`; receipt local
cũ không bị rewrite. Các gate host/public HTTPS/keys/storage/alerts/reboot/
owner và review5high dev/Actions-image drift vẫn mở, toàn production/S6=false.

Target phát triển: `F:\PAO-ACOS`. Bộ này là **candidate để nghiệm thu riêng**,
không phải lệnh chuyển hệ thống đang chạy lên Internet. Master roadmap sở hữu
thứ tự; production/S6 không được đóng chỉ vì build hoặc local test đạt.

Hiện hành17/10: CI Linux11b0 đủ18stage/2258backend/120Node/build23/audit Python0,
Windows111, private profile8fbc và archive clone2d31 đạt; runtime pin mới đã
cài/kiểm installed UI/health/worker/replay3. local_prepared=true,
release_promotable=false vì dev residual risk và gates môi trường thật.
Xem [biên bản xử lý chốt](PHASE3-GATE-REMEDIATION-2026-10-17.vi.md).

## 1. Tách ba môi trường

| Môi trường | Dữ liệu/quyền | Tình trạng |
|---|---|---|
| PAO hiện tại | Primary0071, API8100/Web3200, Windows | Không đổi `.env`, DB role/provider; giữ dữ liệu mới nếu người dùng đang thao tác, không restore đè để ép snapshot |
| CI/private drill local | Source ZIP sạch, DB/container/project UUID, secret tổng hợp | Chỉ để kiểm chứng; tự dọn đúng tài nguyên do lượt test tạo |
| Archive recovery clone | Dump primary riêng tư, không keys thật; internal network/SELECT-only | Chỉ kiểm3archive và từ chối execution sai binding; không Internet/host ports/restore đè |
| Production riêng | VPS/VM, domain/cert, private storage/keys, vận hành và owner | Chưa được cung cấp/nghiệm thu; không tự deploy hoặc reboot |

## 2. CI sạch, không cộng các lượt test rời thành một pipeline xanh

`.github/workflows/p0-foundation.yml` và runner local dùng chung
`scripts/ci_entry.py`: readiness guards → Temporal native/bootstrap → migration →
portability smoke → toàn backend/contract/populated restore → toàn Node helpers
→ TypeScript → production build. Dừng ngay stage lỗi, giữ JUnit/log/JSON.
CI còn kiểm runtime advisory npm (high/critical phải chặn), ba unit tests cho
security gate và ba kiểm tra native PostCSS/Sharp qua Next image optimizer.
`next typegen` chạy trước TypeScript; đây là bước cần cho Next15.5, không bỏ
kiểm kiểu để vượt thay đổi dependency. Dev advisory được báo riêng, không gọi
runtime audit0 là toàn bộ cây dependency sạch.
Backend không đủ2258 hoặc có fail/error/skip thì không đạt.

`scripts/run_s6_linux.py` đóng gói source đã verify, dựng Linux từ Python/Node
và lockfiles, dùng PostgreSQL/Redis riêng, không host bind mount, Docker socket,
key thật hoặc port dịch vụ trên host. Chỉ xóa container UUID có nhãn khớp;
không xóa image/log/source/dump cũ để che lỗi. Môi trường Docker khỏe không có
nghĩa fixture Temporal khởi động kịp; không bỏ test để vượt lỗi tài nguyên.

Chạy local bằng Python môi trường PAO, từ đúng thư mục dự án. Không chạy full
CI cùng tác vụ build nặng nếu startup deadline của Temporal bị ảnh hưởng.
Hosted GitHub CI vẫn cần quyền push/dispatch; không tự thực hiện trong lượt này.
Lịch sử `baca...` FAIL1605passed/1failed ở Temporal recovery và có primary
drift vẫn giữ nguyên; probe3lượt riêng không thay full CI. Lượt11b0 mới đạt
trọn18stage/2258backend/120Node/build23, primary/env khớp, cleanup đạt.
29operator pytest/6pin guards đạt riêng; không cộng vào2258. local_prepared=true
không nghiệm thu toàn production hoặc chứng minh GitHub hosted đã chạy.
Runner lưu hash trước/sau, không lưu nội dung hàng; cần khoảng kiểm chứng không
có thao tác nghiệp vụ đồng thời để kết luận primary không đổi. Không tự tắt
ứng dụng người dùng hoặc sửa dữ liệu để vượt gate này.
Chỉ promote image/source đã xác minh, ghi digest/lockfiles/Python/Node/schema;
không rebuild mù một tag `latest` rồi coi là cùng release đã được kiểm thử.

## 3. Thành phần triển khai riêng

- `infra/production/api.Dockerfile`: API/ARQ cùng source và dependency lock;
  user10001, không copy `.env`/runtime/key, entrypoint không tự migrate.
- `web.Dockerfile`: build stage có dev dependencies; runtime chỉ production
  dependencies và output Next.js23routes, user1000. Không chứa key backend.
- `proxy.Dockerfile` và `Caddyfile`: proxy non-root, TLS CA nội bộ cho test
  loopback18443, không cài root CA vào Windows và không yêu cầu ACME công khai.
- `compose.private.yaml`: không publish API/Web/PostgreSQL/Redis; chỉ publish
  `127.0.0.1:18443`. Read-only filesystem cho API/worker/Web/proxy, cap-drop,
  no-new-privileges, giới hạn bộ nhớ/process và grace period dừng worker210s.
- Named volumes riêng cho PostgreSQL/Redis/runtime private/Caddy. Không gắn
  Docker socket, source tree, thư mục cá nhân hoặc storage của PAO đang chạy.
- `Caddyfile.public.example` chỉ là template tên miền không dùng được; không
  tự thay file TLS nội bộ bằng template này hoặc mở port80/443.

Không có Kubernetes/microservices/runner/scheduler mới. Temporal/Telegram/
Ads/live actions/retention tự xóa giữ tắt trong candidate này; chốt host không
thay thế quyền kết nối hoặc approval của SME. Ollama trên máy Windows chưa
được mở port cho VPS; hybrid cần kênh riêng và policy trước khi bật.

## 4. Quyền database và secret

1. Trên **cluster riêng còn trống**, operator tạo database tên `pao_service_*`,
   role `pao_migrator` và `pao_app`. Không dùng cluster/DB `pao_acos_local` hay
   `pao_test`. `roles.sql` là template cho provision có kiểm soát/test riêng;
   không chạy lại mù nếu role/database đã tồn tại, không tự drop để làm lại.
2. Admin bootstrap tạo extension vector; migrator sở hữu schema và chạy đúng
   revision0071. Cả migrator/app đều không superuser, createdb, createrole,
   replication hoặc bypassrls. App không là member của migrator.
3. Chạy `grants.sql` riêng sau migration đã review: app chỉ connect/schema usage,
   DML bảng và sequence usage; không DDL/TRUNCATE hoặc sửa `alembic_version`.
   Native immutable triggers/audit vẫn giữ. Migration không dùng credential app.
4. Secret runtime/migration là hai file JSON riêng theo shape của
   `runtime.example.json`, chỉ khác role database. JWT và Fernet phải được giữ
   thống nhất theo release. Template có giá trị rỗng/placeholder phải bị từ chối.
5. File nằm ngoài source/build context, owner/quyền truy cập tối thiểu trên
   Linux. API/worker chỉ mount runtime secret, không mount admin/migration.
   Web/proxy không có secret backend. Compose file secrets không là vault hoặc
   mã hóa file trên host; host root/Docker admin vẫn có thể đọc process/file.
6. Entrypoint đọc secret vào môi trường của process, không đặt giá trị vào image,
   Docker Config.Env, source, log hay command history. Không yêu cầu key qua chat.
   Không dùng `docker compose config` để in cấu hình nhạy cảm; dùng kiểm tra yên
   lặng và giữ log đã lọc. Credential trong SQL/bootstrap cũng cần cấp riêng an
   toàn; không truyền mật khẩu thật qua ví dụ command-line của test harness.

Đây là least privilege theo vai trò DB, **không phải RLS theo SME**. Backend vẫn
là authority tenant/brand/Brain/grant. SQL injection hoặc compromise app có thể
ảnh hưởng nhiều SME; cần threat review trước public pilot, không bật RLS mù và
không quảng bá quyền owner hai SME là quyền gộp dữ liệu/bộ nhớ.

## 5. Chạy và nghiệm thu private drill

`scripts/check_private_production.py` tự tạo release source sạch, image tags và
Compose project UUID, secret tổng hợp, cấp role/migrate/grant rồi kiểm:

- TLS với CA riêng được verify hostname/chain, header bảo vệ cơ bản;
- Web và asset production trả200, auth không có token trả401;
- Đăng nhập native và membership hai SME trên DB riêng;
- App CRUD được nhưng DDL/TRUNCATE/sửa ledger migration/SET ROLE bị từ chối;
- API/worker/Web/proxy non-root/read-only, secret không ở Docker Config.Env;
- Restart đúng API/worker container rồi đọc lại auth/readiness, không reboot host;
- Hash dữ liệu/`.env`/backend primary không đổi, dọn đúng project/volumes UUID.

Không chạy helper này để import dữ liệu thật. Private CA không phải public
HTTPS, restart container không thay host reboot/failover; UI M6 browser là
receipt riêng, không gọi HTML smoke ở đây là full browser acceptance production.

## 6. Release lên host riêng — chỉ sau khi được cấp môi trường/quyền

1. Inventory host/OS/Docker/CPU/RAM/disk/private storage/network và owner;
   chưa có host thì pending, không dùng Windows hiện tại thay host để reboot.
2. Chạy hosted CI được cấp quyền, scan source/history/dependencies/image và
   review supply chain; receipt local không chứng minh GitHub đã chạy.
3. Chọn release image theo digest. Giữ dump/schema/keys riêng và đường rollback
   có kiểm chứng trước migration. Không copy source `.env` hoặc demo owner.
4. Provision DB/roles và first owner có xác minh, invite-only; không public
   signup. Không tự đoán email/SME/account hoặc chạy seed test lên production.
5. DNS/ACME/HTTPS/firewall, private admin path và trusted reverse-proxy source
   phải được cấu hình cho host đó. Uvicorn candidate hiện **không tin proxy
   headers**, nên audit/throttle IP có thể thấy proxy IP; không dùng tin `*`
   tùy tiện hoặc coi forwarded IP là identity. Cookie/session nếu đổi thiết kế
   phải có CSRF/CORS/Secure/HttpOnly phù hợp; hiện auth Bearer không phải cookie.
6. Kiểm SSE/streaming thực qua public proxy, rate limits/CSP/XSS, private exports/
   ACL/download, credential rotate/revoke và log redaction trong cấu hình thật.
   Header cơ bản không phải chứng nhận bảo mật hoặc giải pháp XSS đầy đủ.
7. Operator kiểm health/readiness **và worker lease**, queue lag/cancel/drain,
   storage/disk/quota theo SME. Cấu hình alert có đích nhận thực, rehearsal mất
   worker/Redis/DB, load/fair-resource với hai SME; không suy SLA từ4vCPU/8GB.
8. Cold restore DB+private files+keys trên clone riêng; audit/archives/tenant ACL
   phải giữ và không resend job/action đã xảy ra. Mới sau đó thử reboot/recovery
   trên host riêng được cấp, owner review rồi mới có thể xét production.

## 7. Python patch và archive binding — không bỏ qua

Execution binding gồm Python patch và source Python backend, không gồm lockfile.
Windows local3.12.14/binding8e9a71b9, Linux3.12.15/bindingea5394f8 được ghi riêng.
Reader lịch sử hiện có kiểm hash/scope/integrity, không áp current-code binding;
execute/resume vẫn dùng `require_snapshot_execution`. Không suy khác Python
patch là archive hỏng hoặc không đọc được, không sửa hash/reader để ép đạt.
Clone2d31 internal network/role SELECT-only đọc3archive nguyên hash, từ chối
scope/hash sai và3execution khác binding. `archive_read_on_candidate_accepted`
true riêng, còn full production cold restore false: private files/keys/offsite/
host recovery chưa nghiệm thu. Không hạ Python production để khớp binding cũ.
Lock/digest/audit đối chiếu độc lập; Windows interpreter vẫn3.12.14, không gọi
third-party audit0 là toàn runtime/interpreter đã được vá. Không tự chạy lại
tool để tạo archive mới hoặc coi source ZIP/DB dump đã đủ recovery keys/blobs.

## 8. Backup, vận hành và rollback

- Mã nguồn/DB/private blobs có checkpoint/hash; keys/backup offsite thuộc kênh
  riêng có ACL. Quy trình rotate Fernet phải re-encrypt/kiểm tra dữ liệu trước
  bỏ key cũ; không thay host key để khóa riêng một nhân viên.
- Dừng nhận việc mới trước bảo trì; dùng native cancel/drain, giữ unknown actions
  chờ đối soát. SIGTERM/grace không hứa hủy được side effect provider đã nhận.
- `restart: unless-stopped` xử lý crash, không thay monitor/alert/SLO. Chưa có
  receiver alert production, không claim hệ thống đã giám sát24/7.
- Rollback chọn image đã verify và DB/schema tương thích. Không downgrade/drop
  audit hoặc restore đè primary để qua lỗi. Không dùng `down --volumes` trên
  production; thao tác đó trong harness chỉ dành project UUID của test.
- Hạ tầng/security còn pending không được đổi thành pass bằng fixture; phần
  nghiệp vụ thật và owner pilot tiếp tục theo S6.1/S6.3 đã chốt.

## 9. Bản cập nhật bảo mật Web trong lượt chuẩn bị

Audit phát hiện Next15.3.8 nằm trong phạm vi advisory critical; không promote
image cũ. Candidate giữ Next major15, lên Next/eslint-config-next15.5.28 và
override PostCSS8.5.30/Sharp0.35.5/source-map-js1.2.2 bằng lockfile mới. Không
dùng `npm audit fix --force` hoặc tự chuyển major để che kết quả.

Đã kiểm123Node (120UI+3native), build23routes, browser native hai SME và UI
cài thật; API/worker/DB/`.env` không đổi. Runtime npm audit0; toàn cây còn5high
ở tooling dev/lint, cần review riêng trước khi gọi supply chain production
đã sạch. Bản dependency cũ giữ riêng trong `.runtime` để rollback, không phục
vụ Web và không nằm source ZIP. Không tự khôi phục bản dễ tổn thương nếu chỉ
gặp lỗi giao diện; phải đánh giá bảo mật/phạm vi trước rollback.

Biên bản và trạng thái cuối nằm trong báo cáo Giai đoạn3 và
`.runtime/phase3-readiness.json`; không lấy receipt image Next15.3.8 trước
cập nhật làm bằng chứng release mới.

**Lịch sử chốt backend lúc đầu:** read-only pip-audit trên đúng
`requirements.lock` báo16 bản ghi advisory ở PyJWT2.13.0 và cryptography49.0.0
(có alias/trùng nguồn; không diễn giải thành16 đường khai thác độc lập).
Biên bản `.runtime/phase3-python-security.json` lưu hash lockfile đã đối chiếu.
JWT đang cho phép riêng HS256; mã hóa tích hợp dùng Fernet, không thấy đường
PKCS#7 trong source đã rà. Đây chỉ là phân tích phạm vi ban đầu, **không phải
waiver** hoặc bằng chứng không thể khai thác. Không promote backend49/2.13 cũ.

Chốt này đã xử lý bằng candidate riêng PyJWT2.15.1/cryptography50.0.2, CI runtime
audit57/0, full Linux2258 và Windows111; JWT/Fernet tương thích hai chiều bằng
vector giả, không đổi keys. Runtime mới đã cài trong `.runtime/python-releases`
và pin tại `.runtime/acos-python-runtime.json`; `.venv` cũ giữ riêng để rollback.
Start/stop/restart/supervisor đọc pin, launcher legacy từ chối khi pin active.
Metadata generated egg-info cũ giữ recoverable ngoài source để không che metadata
wheel mới. Không chạy pip upgrade vào môi trường đang phục vụ hoặc dùng CLI
`.venv` cũ để kết luận version của API hiện tại. Không có thay mã API/nghiệp vụ
hay schema; dependency lock không nằm trong execution binding nên kiểm release
phải so cả lock và image digest. Dev advisories/hosted CI/host/public HTTPS/
keys/storage/reboot/owner gates còn mở; không cấp waiver production từ local.

## Tài liệu chính thức đã đối chiếu17/10/2026

- [Docker Compose services/hardening](https://docs.docker.com/reference/compose-file/services/)
  và [file secrets](https://docs.docker.com/reference/compose-file/secrets/).
- [PostgreSQL17 roles](https://www.postgresql.org/docs/17/sql-createrole.html)
  và [default privileges](https://www.postgresql.org/docs/17/sql-alterdefaultprivileges.html).
- [Caddy reverse proxy/streaming](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy)
  và [automatic HTTPS](https://caddyserver.com/docs/automatic-https).
- [Next15.5.28](https://github.com/vercel/next.js/releases/tag/v15.5.28),
  [advisory Windows RCE](https://github.com/vercel/next.js/security/advisories/GHSA-p293-qw3h-jr36),
  [Sharp0.35.5](https://github.com/lovell/sharp/releases/tag/v0.35.5),
  [PostCSS8.5.30](https://github.com/postcss/postcss/releases/tag/8.5.30).
- [PyJWT2.15.0](https://github.com/jpadilla/pyjwt/releases/tag/2.15.0) và
  [cryptography advisory](https://github.com/pyca/cryptography/security/advisories/GHSA-g6cj-pr64-35w5).

Đây là tham chiếu thiết kế, không chứng minh host/tài khoản/cert thật đã sẵn sàng.
