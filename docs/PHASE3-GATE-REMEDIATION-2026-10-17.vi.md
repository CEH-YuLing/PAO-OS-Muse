# Giai đoạn3 — Xử lý các chốt kỹ thuật

Tiếp nối [biên bản Giai đoạn3](PHASE3-CI-PRIVATE-PRODUCTION-2026-10-17.vi.md).
Target ứng dụng `F:\PAO-ACOS`, candidate riêng `F:\Apex\phase3-candidate`.
Không bật provider/quảng cáo, đổi key, deploy công khai, commit/push hoặc reboot.

**Cập nhật sau khi người dùng cấp quyền GitHub:** đã push source đã review vào
nhánh phase3/hosted-ci, commit3151851; run39030584315 đạt18stage/2258backend/
120Node/build23 và audit Python57/0/npm runtime0. Artifact đã xác minh; main
không đổi, không merge/deploy. Xem [nghiệm thu hosted CI](PHASE3-HOSTED-CI-ACCEPTANCE-2026-10-17.vi.md).
Các đoạn không push/hosted pending dưới đây là phạm vi lượt local trước đó,
không phải trạng thái mới. `.runtime/phase3-current-status.json` tổng hợp mới;
receipt local giữ nguyên. Production/M6/S6 vẫn chưa đóng.

## Nghiệm thu local hiện hành17/10/2026

- CI mới: `.runtime/s6-linux-11b0f0133b224899a998da5cce185f3e/`.
  **Toàn18stage đạt trong cùng một lượt:** backend2258/2258,0fail/error/skip,
  1430.03s/62ARQ warnings;120Node/TypeScript/build23 và13native portability
  smoke đạt. Primary trước/sau khớp, `.env` không đổi, containers UUID đã dọn.
  Giữ nguyên lượt FAIL `baca...`1605passed/1failed và các probe lịch sử.
- Candidate khóa PyJWT2.15.1/cryptography50.0.2; không thay các dependency
  runtime khác. Audit Python trong CI kiểm57packages,0advisory được báo;
  tool pip-audit2.10.1 ở venv riêng, không cài vào runtime app.
- Windows candidate venv riêng: pip check đạt,4JWT/Fernet compatibility tests
  đạt bằng vector tổng hợp được tạo với phiên bản cũ;4namespace-readiness
  unit tests đạt. Regression Windows riêng111/111/0skip,45.24s đạt; không gọi
  đây là full Windows2258 mới hoặc kế thừa baseline crypto49 thành crypto50.
- Native preflight13/13 và sau đó full backend đều đạt, gồm test connection
  recovery từng thất bại. Không hứa hết lỗi ở mọi tải/production.
- Helper chọn runtime riêng đạt6guard tests; nhóm operator pytest cuối29/29
  đạt riêng (profile/archive/readiness/release/source-envelope). Không cộng vào
  2258 backend hoặc giả là tất cả đều nằm trong source ZIP CI.
- Profile private `.runtime/phase3-private-8fbc724d98134fe089a8ffc939f69e93/receipt.json`
  đạt TLS/least-privilege/two-SME/static-assets/non-root/read-only/file-secrets/
  restart/cleanup và giữ nguyên primary/env/backend trong phạm vi drill.
- Archive clone `.runtime/phase3-cold-2d31296f41d14e32bc87019d81200895/receipt.json`
  đạt153tables/3archive nguyên hash, wrong-scope/hash bị từ chối,3snapshot khác
  binding bị từ chối thực thi; internal network, mật khẩu admin/reader riêng,
  role không DDL/DML/admin và transaction read-only. Không restore primary.
- Cutover thành công sau checkpoint/idle và kiểm source/evidence hai lần:
  `.runtime/phase3-backend-installed.json`, release2a62981090134b159cc2162fc3e1e15e.
  API/worker dùng runtime PyJWT2.15.1/cryptography50.0.2 riêng; `.venv` cũ
  không sửa. Windows Python3.12.14, binding8e9a71b9 không đổi. Mã API/nghiệp vụ,
  schema0071/399operations/153tables và `.env` không đổi.
- Installed Edge read-only UI đạt12khu vực/business journey/Settings deep-link,
  0API mutations/provider calls; health/ready/Web200, worker khỏe, replay3/3.
  Artifact `.runtime/phase3-backend-ui-f5347d21c91d418189469b5ff28f8dbc/`;
  supervisor observe-only không thiếu process,0restart.
- `.runtime/phase3-readiness.json`: **local_prepared=true**, production/S6=false.
  `.runtime/phase3-release-security.json`: Python/JS runtime clear,
  archive_read_on_candidate_accepted=true nhưng release_promotable=false vì
  dev advisories và gates hạ tầng thật chưa đủ. Exit2 là chặn production đúng.
- Checkpoint sau cùng: `.runtime/phase3-remediation-post-checkpoint.json`;
  chỉ đạt khi có verified=true và clone restore thành công. Artifact nằm ngoài
  source ZIP để tài liệu không tự tham chiếu hash của chính nó.

## 1. Temporal — chuẩn bị fixture, không làm yếu assertion nghiệp vụ

Test trước chỉ biết dev server đã mở gRPC socket. Thêm đọc DescribeNamespace
để xác nhận namespace REGISTERED trước khi bắt đầu phần phục hồi.
`namespace_ready` có setup deadline5s, mỗi read không SDK retry, chỉ chờ lỗi
startup xác định; permission error phải fail. Không skip khi chưa sẵn sàng.

Giữ nguyên outage TCP thật, backoff2.1s, assertion dispatch1, attempts2 và
TaskAttempt0; không sửa Gateway/outbox/lease/cancel hay deterministic workflow.
CI smoke chạy thêm toàn file connection recovery, để lỗi này xuất hiện sớm
thay vì chỉ sau1600test. Chỉ đóng chốt nếu cùng lượt full regression đạt.
Lượt11b0... đáp ứng điều kiện đó; không dùng3probe riêng cũ thay full pass.
Guard từ chối reuse CI nếu thêm/sửa/xóa source runtime. Generated next-env/
cache/egg-info không là mã runtime;4file egg-info cũ trong ZIP lịch sử không
được diễn giải là code đã chạy. Metadata package cũ giữ recoverable ngoài
source, không xóa source người dùng để ép hash khớp.

## 2. Dependency và release an toàn

- Giữ major Next15 đã vá; không hạ về Next14 hoặc audit-fix force để giảm số.
- Backend candidate chỉ nâng PyJWT và cryptography theo changelog, khóa phạm
  vi pyproject tương ứng; audit runtime là một CI gate fail-closed mới.
- Bộ cài/rollback wheels tách biệt và có hash. Candidate check đối chiếu CI,
  private profile, Windows regression, archive clone và source hiện tại trước
  khi cho phép cutover. Không overwrite source người dùng đã sửa ngoài phạm vi.
- Cài runtime mới vào `.runtime/python-releases/<uuid>` trước khi dừng app;
  không thay/tháo DLL cryptography của `.venv` đang chạy. `.venv` cũ giữ nguyên.
- Chỉ khi idle và đủ checkpoints mới dừng đúng API/worker có executable và
  start-time đã xác nhận; Web/Ollama giữ chạy. Runtime pin chỉ trỏ venv trong
  project, từ chối traversal/link/hash sai; launcher/stop cùng đọc pin.
- Migrate launcher vẫn đúng0071, không có migration schema mới. Post-cutover
  phải kiểm health/Web/worker, native contract và replay3; `.env` không đổi.
  Nếu không đạt, bỏ pin của đúng lượt này về thư mục rollback, phục hồi source
  đã backup và khởi động runtime cũ; không restore database primary.

Pin/backup/guard và JWT/Fernet hai chiều đã kiểm bằng dữ liệu tổng hợp. Không
cố ý downgrade primary để diễn tập rollback; cần rehearsal release/rollback
đầy đủ trên host riêng trước public production. Không gọi rollback-ready là
rollback-on-production-tested.

Runtime phục vụ được chọn bởi `.runtime/acos-python-runtime.json`. Start/stop/
restart/supervisor đồng bộ pin; launcher legacy `start_local` từ chối khi pin
active để tránh quay về runtime cũ hoặc mở stack/port khác. `.venv` vẫn giữ
crypto49/PyJWT2.13 để rollback, **không** là interpreter API/worker hiện tại.
Release venv chỉ có runtime lock, không cài pytest hoặc audit tool.

Metadata generated cũ giữ tại
`.runtime/phase3-backend-2a62981090134b159cc2162fc3e1e15e/generated-metadata-before/`;
source trước cutover, checkpoint và log cùng thư mục. Negative gate đã thử:
receipt private cũ aa39... dùPASS vẫn bị từ chối vì source khác candidate mới.
Không dùng wheel/source/image `latest` hoặc receipt cũ để promote.

## 3. Đính chính chốt archive bằng code, không bằng giả định

`skill_artifacts.read_artifact` đã gọi `require_snapshot_integrity`, **không**
gọi current-code `require_execution_binding` khi đọc kết quả lịch sử. API vẫn
kiểm quyền chủ thể/scope và đối chiếu record. Ngược lại, resume/execution dùng
`require_snapshot_execution`, vẫn phải trùng execution binding hiện hành.

Do đó Python3.12.14/3.12.15 khác binding là điều cần kiểm khi thực thi, không
tự suy thành archive không đọc được. Không thay backend reader hay hash để
ép tương thích. Đã drill dump/restore lên PostgreSQL UUID, internal
network không Internet/không host ports, reader chỉ SELECT và transaction
read-only, đúng image CI. Đã đọc3archive nguyên hash, từ chối scope/hash sai
và từ chối thực thi cả3snapshot khác binding. Private files/keys/offsite/host
reboot vẫn là gate production khác, không được đóng bằng DB-only drill.

Python3.12.15 có security fixes; không hạ production về3.12.14 để làm hash khớp.
Runtime local Windows hiện3.12.14; không suy runtime local đã có bản vá
interpreter mới chỉ vì third-party audit0. Execution binding hiện băm source
Python và Python patch, không băm dependency lock; release gate/digest/lockfile
được đối chiếu độc lập, không gọi binding là toàn bộ supply-chain attestation.

Clone đã chứng minh đọc tương thích; **không có sửa reader/binding**.
`existing_archive_cold_restore_accepted` toàn production vẫn false, còn
`archive_read_on_candidate_accepted` riêng được true từ đúng receipt. Không
gộp hai phạm vi hoặc suy việc đọc cho phép thực thi snapshot cũ.

## 4. Những gì không thể gọi là đã sạch

Npm runtime audit0 khác với full5high trong dev lint chain
eslint-config-next→plugin→fast-glob→micromatch→braces. Advisory upstream hiện
không có patched braces; registry vẫn3.0.3. Không xóa lint, sửa số audit hoặc
đổi major Next để giấu cảnh báo. Dev packages không ở Web production runtime;
lint chỉ trên source được review trong runner giới hạn tài nguyên/timeout,
token repo read-only, không secret production. Vẫn ghi residual risk và cần
review trước public release; chưa cấp waiver production từ fixture/local CI.

Hosted CI, host/domain/public HTTPS/trusted proxy, private storage/keys/offsite/
alerts/reboot/owner review tiếp tục external_pending. Người dùng đã hoãn dữ
liệu thật; không hỏi lại hoặc tự chọn SME/account/provider/action để vượt gate.

**Tiếp theo:** nghiệm thu môi trường thật/hosted CI được cấp quyền và review
residual dev/image/supply-chain/secret/history risk. Không rerun toàn baseline
khi inputs không đổi, không tự push/deploy/reboot; S6.1 real data và S6.3 owner
pilot vẫn chưa đạt. Toàn M6/S6/production chưa đóng.

## Nguồn chính thức đối chiếu17/10/2026

- [Temporal WorkflowService](https://python.temporal.io/temporalio.service.WorkflowService.html).
- [PyJWT changelog](https://pyjwt.readthedocs.io/en/stable/changelog.html),
  [cryptography changelog](https://cryptography.io/en/latest/changelog/).
- [Python3.12.15 security release](https://www.python.org/downloads/release/python-31215/).
- [Braces advisory, chưa có bản vá](https://github.com/advisories/GHSA-vfj7-8cjw-p6xm).

Nguồn mô tả upstream, không phải bằng chứng đã cài hoặc nghiệm thu ở PAO.
