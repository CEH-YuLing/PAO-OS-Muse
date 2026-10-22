# Giai đoạn3 — CI và hạ tầng production riêng

**Cập nhật sau cùng:** hosted CI run39030584315 trên commit3151851 đã PASS,
18stage/2258backend/120Node/build23 và audit Python57/0/npm runtime0; main giữ
nguyên. [Biên bản hosted CI](PHASE3-HOSTED-CI-ACCEPTANCE-2026-10-17.vi.md) và
`.runtime/phase3-current-status.json` sở hữu trạng thái mới. Các mốc hosted
pending/không push bên dưới giữ lịch sử lượt local; production/S6 vẫn pending.

Ngày17/10/2026; target `F:\PAO-ACOS`. Master sở hữu thứ tự phát triển.

## Kết luận

**Cập nhật sau xử lý chốt17/10: local_prepared=true; production/M6/S6 chưa đóng.**
Lượt Linux11b0 đạt cùng18stage/2258backend/120Node/TypeScript/build23/audit
Python57packages0advisory; Windows111 và private profile8fbc đạt. Clone2d31
đọc đủ3archive trên Python3.12.15, chặn3execution khác binding. Runtime pin
PyJWT2.15.1/cryptography50.0.2 đã cài; installed UI/health/worker/replay3 đạt.
Xem [biên bản xử lý chốt hiện hành](PHASE3-GATE-REMEDIATION-2026-10-17.vi.md).
Còn5dev advisories chưa có patch và gates hosted CI/host/HTTPS/keys/storage/
alerts/reboot/owner, release_promotable=false. Không bật kết nối/quảng cáo thật.

**Phần dưới là baseline trước xử lý chốt, giữ nguyên lỗi/bằng chứng lịch sử.**
Bộ CI dùng chung và profile triển khai riêng đã được xây dựng. Private drill
với dependency Web mới đạt trên container riêng. Không push/dispatch CI,
không deploy công khai, reboot host hoặc bật kết nối thật/quảng cáo.

### Baseline ban đầu đã triển khai

| Phần | Thay đổi | Bằng chứng/phạm vi |
|---|---|---|
| CI | Workflow GitHub và local dùng chung `ci_entry.py`; một lượt xuyên suốt, JUnit và stage JSON | FAIL:1605passed/1failed, dừng ở Temporal connection recovery; chưa đạt pipeline sạch |
| Linux runner | Base Python/Node + lockfile tự dựng, test PostgreSQL/Redis riêng, không host ports/socket/key thật | UUID run, source ZIP/hash, log thất bại và cleanup được giữ |
| Database | Tách admin/bootstrap, migrator và app; app không superuser/DDL/TRUNCATE/sửa migration ledger | Thử quyền thật trên DB giả0071, không đổi role primary |
| Containers | API/worker/Web/proxy non-root, read-only, cap-drop, no-new-privileges, tài nguyên/stop grace | Private runtime inspection và restart API/worker đạt |
| TLS/secrets | Caddy internal CA, kiểm hostname/chain; secret runtime/migration riêng, ngoài source/image | Không cài CA lên Windows, không mở Internet; file secrets không phải vault |
| Bảo mật Web | Next15.3.8 →15.5.28 cùng major; eslint tương ứng, override PostCSS/Sharp/source-map-js, lockfile mới | Runtime npm audit0, toàn cây còn5high ở dev lint |
| Tương thích Web | 120UI helpers +3native PostCSS/Sharp tests; build23routes; Edge production browser native hai SME | Không đổi backend/schema/`.env`, primary API/worker giữ nguyên |
| Chốt release | Tách local chức năng khỏi quyền promote, ghi advisory và khác biệt archive binding | Production luôn false cho đến đủ review và gates thực |

## Bằng chứng baseline ban đầu

- CI: `.runtime/s6-linux-baca7f8b6cb54f6ba5acbe7d9d578cc7/`.
 13stage đầu đạt, gồm20profile/archive/readiness tests,3security-unit,
 3native PostCSS/Sharp, runtime npm audit, bootstrap, schema và11portability
 smoke. Full backend dừng1605passed/1failed/0error/0skip trong1287.44s,
 37ARQ warnings; không chạy tiếp Node/TypeScript/build trong lượt CI này.
 Không cộng các lượt frontend độc lập vào để ghi pipeline xanh.
- Private profile: `.runtime/phase3-private-aa39a3ccf40c460daecd23ffc5f06345/receipt.json`;
  Next15.5.28, TLS/least-privilege/two-SME/static-assets/file-secrets/non-root/
  restart/primary-unchanged/cleanup đều true. `production_accepted=false`.
- Browser candidate Web: `.runtime/phase3-browser-runs/pao_s5_browser_bef1f3fc52624d18b342e33840c5ac25/receipt.json`.
  Hành trình business,12khu vực, quyền và nháp SME, deep-links, lịch sử, lỗi mạng,
  keyboard, mobile320/390 đạt; gateway/provider tổng hợp, không kết nối thật.
- Bản cài hiện tại: `.runtime/phase3-security-completion.json` và
  `.runtime/phase3-security-installed-runs/20261017T070123/`.
  TypeScript/120helpers/3security-unit/3native và UI read-only đạt;
  API/ready/Web200, worker khỏe, replay3/3. Windows2258 được kế thừa vì backend
  và môi trường backend không đổi; không gọi đây là lượt full Windows mới.
- Audit Python: `.runtime/phase3-python-security.json`, raw log giữ private.
  `requirements.lock` của image scan đã đối chiếu hash với source hiện tại.
- Tổng hợp chức năng: `.runtime/phase3-readiness.json`.
  Tổng hợp chốt bảo mật: `.runtime/phase3-release-security.json`.
  `local_prepared=false`, production/S6=false; private profile local_accepted,
  clean Linux pipeline pending. Readiness exit1 và release-security exit2 là
  kết quả fail-closed hiện hành, không phải lỗi cần sửa thành pass bằng tay.
- Source/DB checkpoint cuối được ghi ở `.runtime/phase3-post-checkpoint.json`;
  chỉ đạt khi file có `verified=true`, đường dẫn manifest hợp lệ và clone
  restore đạt. Không có biên bản này thì gate checkpoint vẫn pending. Runtime
  artifact nằm ngoài source ZIP nên tài liệu không tự tham chiếu hash của nó.

## Phát hiện baseline — trạng thái mới xem biên bản xử lý chốt

1. **Backend dependency cần xử lý trước promote.** pip-audit báo16 bản ghi
   advisory ở PyJWT2.13.0 và cryptography49.0.0; alias có trùng nguồn, không
   phải16 đường khai thác độc lập. Mã JWT hiện allowlist riêng HS256, tích hợp
   dùng Fernet, chưa thấy đường PKCS#7 trong source đã rà. Không đủ cơ sở cấp
   waiver; backend candidate hiện **không được promote**. Chưa sửa dependency
   primary vì phải kiểm xác thực/mã hóa/archive trên candidate riêng.
2. **Supply chain chưa sạch toàn bộ.** Npm runtime0 khác với full5high dev;
   chưa có scan đầy đủ OS image, history/secret review và hosted CI. Không
   gọi npm audit là chứng nhận bảo mật hoặc dùng audit fix force tự đổi major.
3. **Archive/runtime khác nhau.** Windows Python3.12.14 và Linux3.12.15 làm
   execution binding khác nhau. Source giống không chứng minh archive cũ replay
   được sau cold restore. Không sửa hash/giảm gate hoặc chạy lại tool để ép đạt.
4. **Hạ tầng thật còn thiếu.** Chưa có host riêng/domain/public cert/firewall,
   private storage vận hành, alert receiver, key/offsite recovery hay reboot.
   Restart container không thay host reboot/failover. Private HTML/auth smoke
   không phải full browser/SSE acceptance qua public reverse proxy.
5. **Least privilege DB chưa phải tenant RLS.** API tiếp tục chịu trách nhiệm
   SME/brand/Brain/grants; app compromise/SQL injection vẫn có blast radius
   nhiều SME. Trusted proxy/IP throttling, CSP/CSRF/CORS/session cần threat
   review theo cấu hình thật; không tin forwarded IP từ mọi nguồn.
6. **Nợ kỹ thuật giữ nguyên:** ARQ warnings/React-hook warnings, giới hạn tài
   nguyên/fairness chưa có phép đo production; không hứa SLA/công suất VPS.
7. **CI Temporal chưa ổn định.** Test
   `test_real_temporal_connection_loss_then_outbox_delivery` mong dispatch1
   nhưng nhận0; native server báo `GetNamespace context deadline exceeded`.
   Probe trên đúng image đóng băng, DB/Redis riêng, test gốc không sửa đạt
   2/2 trong cả3lượt (6.73/7.43/6.18s). Receipt tại
   `.runtime/phase3-temporal-probe-2ded0d9d2e98467f85796c6a2bd3f1e9/`.
   Đây là bằng chứng lỗi không tái hiện khi chạy riêng, **không phải đã sửa**
   hoặc đủ thay full regression. Không rerun full mù, skip test/nới deadline
   hoặc sửa backend khi chưa phân biệt startup readiness/tài nguyên/runtime.
8. **Primary drift trong lượt CI.** Manifest báo primary_unchanged=false,
   `.env` không đổi, owned containers đã dọn. Snapshot đầu lượt cũ chưa được
   lưu nên không đủ truy ngược diff chính xác. Điều tra read-only thấy bản ghi
   đăng nhập/chat/Brain mới lúc07:21–07:22UTC; chưa quy kết tác nhân. Không xóa
   hoặc restore đè dữ liệu để ép hash khớp. `.runtime/phase3-primary-drift.json`
   lưu count/hash/timestamp, không lưu nội dung hàng. Probe sau đó có snapshot
   trước/sau khớp; live check cuối giữ hash nguyên trong phạm vi kiểm tra đó.

24guard tests độc lập cuối lượt đạt (profile13+archive4+readiness4+release3);
không ghi đè20guard đã chạy trong source CI cũ. Runner tương lai lưu snapshot
hash trước/sau và tên bảng đổi; readiness từ chối drift/thiếu cleanup ngay cả
khi test xanh. Không sửa manifest thất bại trước để áp dụng schema báo cáo mới.

`check_phase3_release_security.py` và3unit tests độc lập kiểm việc scan thiếu/
cũ hoặc còn findings không được coi là sạch; scan sạch cũng không tự cấp
production/cold restore. Kết quả lệnh thực tế exit2 nghĩa là **chặn release
đúng thiết kế**, không ghi thành một security pass. Các3unit này không được
cộng vào2258 backend hoặc giả là đã nằm trong source ZIP của lượt CI trước.

## Trình tự đã dùng xử lý chốt — các gate thật vẫn còn pending

1. Xử lý CI Temporal trước: giữ repro/log, điều tra namespace readiness và
   tải tài nguyên/SQLite khi chạy đầy đủ; fixture chuẩn bị phải có điều kiện
   sẵn sàng rõ, không thay assertion nghiệp vụ. Chỉ chạy lại full sau một thay
   đổi có căn cứ; dùng snapshot mới trong khoảng không có thao tác nghiệp vụ
   đồng thời để nghiệm thu guard primary. Không tự dừng app người dùng.
2. Tạo candidate nâng PyJWT/cryptography theo changelog chính thức, resolve
   và khóa dependency; audit lại và chạy regression xác thực/session/Fernet,
   Windows/Linux. Giữ khóa thật nguyên vẹn; không yêu cầu gửi key qua chat.
3. Kiểm tương thích execution binding và cold restore ba archive trên clone;
   pin runtime phù hợp hoặc thiết kế migration/review được chứng minh. Không
   chuyển backend primary nếu checkpoint và recovery còn chưa đạt.
4. Xử lý/review dev advisories và image/history/secret/supply-chain; chạy
   hosted CI khi có quyền repo. Chọn source/image digest đã verify.
5. Khi được cấp host riêng, inventory/provision minimum DB roles, first owner
   invite-only, DNS/HTTPS/firewall/private storage/keys/monitoring. Không copy
   `.env`, demo seed hoặc secret của máy này vào production.
6. Cold restore/reboot/failover/queue-drain/SSE/auth/load hai SME trên host
   riêng; owner review. Các gate chưa đạt giữ production_pending.
7. S6.1 dữ liệu thật/read-only và S6.3 pilot vẫn theo quyền riêng; người dùng
   đã hoãn dữ liệu thật, không hỏi lại trong các bước chuẩn bị local.

## Lịch sử lỗi và phục hồi

- Lượt Linux `e560...` lỗi npm HOME không ghi được; đã cấp HOME của user
  non-root. `b4c...` lỗi Temporal native không khởi động trong5s khi build nặng
  đồng thời; giữ nguyên test/deadline. Runner riêng dùng tmpfs/giới hạn tài
  nguyên và tránh build nặng đồng thời. Không cộng các stage cũ thành CI xanh.
- Linux `d020...` dừng có chủ đích khi phát hiện dependency Web critical;
  chỉ dừng đúng runner có nhãn UUID, giữ manifest false và cleanup.
- Linux `baca...` full regression FAIL và primary drift được giữ nguyên; probe
  riêng không ghi thay kết quả full. Probe `4ff...` ban đầu bị guard test-DB
  từ chối do thiếu biến PAO_TEST_DATABASE_URL, đã dọn đúng tài nguyên; bổ sung
  biến bắt buộc rồi mới chạy probe `2ded...`, không nới guard.
- Private `f2e...`/`eb1...` lỗi internal TLS/Caddy binary capability. Đã bỏ
  filecap không tương thích cap-drop, bật internal CA, sửa UTF8 logging/finally
  cleanup. Một lượt bị lỗi log trước cleanup đã dọn đúng project/volumes giả
  theo nhãn; không đụng database hay volume chính.
- Private `b445...` từng đạt với Next15.3.8 nhưng là lịch sử, không dùng để
  nghiệm thu release dependency mới. Lượt `aa39...` mới thay thế bằng chứng.
- Hai lần audit Python đầu lỗi quyền executable/cache của container read-only;
  cấp riêng scratch tmp/cache rồi scan thành công. Không cài pip-audit vào
  `.venv` hoặc thay runtime dự án để vượt lỗi công cụ audit.
- Dependency Web cũ giữ recoverable tại
  `.runtime/phase3-web-d1903aec693f4ff89926f79d14a91f62/`; không xóa, không
  phục vụ Web. Không tự rollback về bản dễ tổn thương nếu chưa review.

## Tài liệu vận hành và nguồn

[Runbook](PHASE3-PRIVATE-PRODUCTION-RUNBOOK.vi.md) ghi thành phần/quyền/secret,
quy trình lên host và rollback; [master](PAO-MASTER-GAP-AND-ROADMAP.vi.md) ghi
trạng thái hiện hành. Nguồn chính thức đối chiếu17/10:
[Next15.5.28](https://github.com/vercel/next.js/releases/tag/v15.5.28),
[Windows advisory](https://github.com/vercel/next.js/security/advisories/GHSA-p293-qw3h-jr36),
[PyJWT2.15.0](https://github.com/jpadilla/pyjwt/releases/tag/2.15.0),
[cryptography advisory](https://github.com/pyca/cryptography/security/advisories/GHSA-g6cj-pr64-35w5).
Thông tin upstream hỗ trợ quyết định dependency, không chứng minh deployment
thật đã an toàn hoặc tất cả chức năng provider đã nghiệm thu.
