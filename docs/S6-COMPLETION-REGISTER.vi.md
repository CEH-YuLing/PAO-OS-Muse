# S6 — Sổ triển khai và nghiệm thu business/production

## Bổ sung18/10 — tổ chức và Kho tri thức

Lát cắt nguồn local đã đạt2272full Linux/202Windows/132Node/build23/browser:
doanh nghiệp/nhãn hàng tại Cài đặt; hồ sơ cùng
nguồn Kế hoạch kinh doanh; Skills có nhóm và gán phiên bản agent tại Kho tri thức.
Chủ SME hiện có được tạo SME độc lập mình sở hữu, không mở signup/copy quyền.
[Báo cáo](ENTERPRISE-KNOWLEDGE-LOCAL-2026-10-18.vi.md) sở hữu bằng chứng lát cắt;
399operations/binding8e9a71b9 trong các mục cũ là baseline lịch sử, không bằng
chứng cho source tổ chức mới. Không viết lại receipt S6.2/Phase3 cũ.
Sau cài, current preflight chỉ chấp nhận đúng hash nguồn/CI/Windows/browser/live;
schema0071/153tables giữ nguyên, API mới406operations. Toàn S6 vẫn in_progress.
Receipt bản cài: `.runtime/organization-completion.json`; chỉ pass=true sau
read-only health/replay3/browser/primary-env hash mới là local_accepted.

## Điều hướng hiện hành18/10 — local trước, production hoãn theo người dùng

Lát cắt vòng vận hành local trên nền S5/M6: **local_accepted18/10**, xem
[báo cáo](LOCAL-OPERATING-CYCLE-2026-10-18.vi.md).132Node/125focused backend/
0fail/error/skip/build23; native journey, lost ACK/reload/cancel/stop/dependency/
rework/report/SME và mobile320/390 đạt trên DB riêng; installed read-only đạt.
Receipt `.runtime/local-cycle-completion.json`; giữ nguyên backend/schema0071/
399operations/153tables/binding/.env, không gọi provider. Không coi đây là
full2258backend hoặc toàn M6/S6. S6.1 dữ liệu thật local là gate tiếp theo.

S6 vẫn `in_progress`; không suy toàn M6/S6/production đạt từ UI hoặc fixture.
Ưu tiên: khung local → S6.1 dữ liệu thật local → S6.3 pilot local → VPS/public.
Các gate host/HTTPS/storage/keys/offsite/alerts/reboot/owner giữ chưa đạt và
`deferred_by_user`, không chặn cải thiện local. Master sở hữu thứ tự hiện hành.

Lát cắt M6 UX sáng/tối có bằng chứng riêng tại
[báo cáo18/10](LOCAL-UX-LIGHT-DARK-2026-10-18.vi.md): 128Node, build23, native
business journey và13màn hình x2theme trên môi trường thử riêng. Bản cài thật
được kiểm read-only độc lập; receipt `.runtime/local-ux-completion.json` chỉ
được tạo khi kiểm đạt. Giữ nguyên CI3151851/2258backend như baseline lịch sử,
không nhận là full backend/hosted CI mới cho UX. Không bật provider/chi tiền.

16/10/2026; bổ sung checkpoint bảo vệ17/10. Target duy nhất `F:\PAO-ACOS`.

## Hiện hành17/10 — Giai đoạn3 local_prepared, production_pending

**Cập nhật sau cùng: hosted CI đã accepted.** Repository private CEH-YuLing/Pao-ACOS,
nhánh phase3/hosted-ci, commit3151851; run39030584315 đạt18stage/2258backend/0skip,
120Node/typecheck/build23 và audit Python57/0/npm runtime0. Artifact/JUnit đã tải
và đối chiếu đúng commit. Main không đổi; không merge/deploy/bật provider.
Xem [báo cáo hosted CI](PHASE3-HOSTED-CI-ACCEPTANCE-2026-10-17.vi.md).
`.runtime/phase3-current-status.json` tổng hợp mới; local-only receipts dưới đây
giữ nguyên lịch sử. Còn5high dev, Actions/image drift và host/HTTPS/storage/keys/
offsite/alerts/reboot/owner production; toàn M6/S6/production vẫn false.

### Baseline local trước lượt hosted CI

[Xử lý chốt](PHASE3-GATE-REMEDIATION-2026-10-17.vi.md) sở hữu bằng chứng mới:
CI `11b0f0133b224899a998da5cce185f3e` đạt18stage/2258backend/0fail/error/skip,
120Node/TypeScript/build23,13native smoke và Python runtime57audit0.
Windows `1c17...`111/111, private `8fbc...`TLS/minimum-role/non-root/restart và
clone `2d31...`153tables/3archive nguyên hash,3execution khác binding bị chặn.
Runtime release `2a629...` đã cài PyJWT2.15.1/cryptography50.0.2 riêng; `.venv`
cũ giữ nguyên, `.env`/schema0071/399operations/153tables/binding8e9a71b9 không đổi.
UI read-only `f534...`12khu vực/Settings/business journey đạt; health/worker và
replay3/3 đạt. Không gọi Windows111 là full Windows2258 mới.
29operator pytest và6pin guards đạt riêng, không cộng vào backend2258.
Readiness local_prepared=true; Python/JS runtime clear, archive read accepted,
nhưng release_promotable=false:5high dev chưa có patch và hosted CI/host/public
HTTPS/storage/keys-offsite/alerts/reboot/owner review vẫn pending.
**Toàn M6/S6/production=false**, không push/deploy/bật provider/quảng cáo.
Checkpoint sau cùng trỏ tại `.runtime/phase3-remediation-post-checkpoint.json`.

## Lịch sử17/10 — Giai đoạn3 trước xử lý chốt

CI local/hosted dùng chung entry; đã thêm profile triển khai riêng, minimum DB
role tách migrator, runtime non-root/read-only, file secrets, Caddy TLS nội bộ
và restart drill. Private receipt `phase3-private-aa39a3ccf40c460daecd23ffc5f06345`
đạt với Next15.5.28, đã dọn đúng test resources và giữ primary/`.env` nguyên vẹn.
Web candidate/browser và bản cài thật đạt; runtime npm0/full5high dev.
Backend Python có advisory PyJWT/cryptography; không promote backend hiện tại.
Linux Python patch và archive binding khác primary nên cold restore chưa đạt.
Xem [báo cáo Giai đoạn3](PHASE3-CI-PRIVATE-PRODUCTION-2026-10-17.vi.md) cho CI,
hash/artifact/test history; [runbook](PHASE3-PRIVATE-PRODUCTION-RUNBOOK.vi.md)
cho điều kiện vận hành. Hosted CI/host/public HTTPS/key-offsite/alerts/reboot
vẫn pending; chốt bảo mật local cần xử lý trước. **Toàn M6/S6/production=false**,
không bật provider/quảng cáo/kết nối thật hoặc tự chuyển pilot.
CI Linux `baca...` FAIL1605passed/1failed, dừng ở Temporal connection recovery;
primary_unchanged=false, `.env` không đổi, cleanup đạt. Điều tra read-only có
login/chat/Brain mới, chưa quy kết tác nhân. Probe `2ded...` test gốc đạt2/2x3,
không thay full pass.24guard mới đạt; readiness local_prepared=false và release
promotable=false. Kiểm cuối live0071/399/153/replay3 và health/worker đạt.

## Baseline17/10 — Giai đoạn2 M6 UX local_accepted

Trọn lát cắt UX phục vụ S6 đã kiểm chứng và chuyển vào PAO-ACOS:12khu vực/view
con, hành trình kinh doanh, nháp có phạm vi, deep-links, lựa chọn kết nối/quyền,
lịch sử/điều chỉnh có kiểm soát, Settings và báo cáo trung thực.
120Node/typecheck/build23, Edge production candidate + API native/DB0071 riêng
đạt toàn flow,12routes,SME/role/draft/deep-links/network/keyboard/mobile.
UI cài thật read-only đạt; API/ready/Web200, worker lease khỏe và replay3/3.
Primary0071/399/153physical và backend binding8e9a71b9 không đổi;2258backend
baseline được kế thừa, không rerun full. Dữ liệu nghiệp vụ/`.env` giữ nguyên.
Receipt `.runtime/m6-completion.json`, browser artifacts trong
`.runtime/m6-browser-runs/pao_s5_browser_ed1b71dd167840e0b8dc2afd59568a4f/`.
Xem [báo cáo M6](M6-COMMAND-CENTER-UX-LOCAL-ACCEPTANCE-2026-10-17.vi.md)
và [hướng dẫn](M6-COMMAND-CENTER-UX-USER-GUIDE.vi.md).
Tiếp theo Giai đoạn3 — CI/private production theo master; gates môi trường/
HTTPS/reboot/keys/hosted CI còn pending, không tự push/deploy. Dữ liệu thật
hoãn; toàn M6/S6/production chưa đóng. Không mở lại P6/lifecycle.

## Baseline17/10 — nghiệm thu trọn Giai đoạn1

**Giai đoạn1 — cả bốn phần đã local_accepted; S6 vẫn in_progress.** Bảo vệ phiên
bản, lời mời/thành viên, thu hồi phiên và xuất/yêu cầu xóa đều có API/UI/tests.
Full Windows mới2258/2258/0skip,2291.43s,62ARQ warnings;114Node/typecheck/build23,
browser thật hai SME/desktop/mobile và migration/populated restore clone đạt.
Primary0071/live399/153physical/binding8e9a71b9, API/ready/Web200, worker khỏe,
replay3/3; cột cũ/dữ liệu nghiệp vụ/archives/`.env` không đổi. Hai lifecycle
gates local_accepted, preflight local_checks_passed=true; production/S6=false.
Không bật provider/xóa tự động. Tiếp theo M6 UX; hạ tầng/CI/dữ liệu thật/pilot
còn gate riêng, không làm lại lifecycle. Giữ mọi log lỗi trước lượt xanh.
Xem [báo cáo hiện hành](S62-ACCOUNT-DATA-LOCAL-ACCEPTANCE-2026-10-17.vi.md)
và [hướng dẫn](S62-ACCOUNT-DATA-USER-GUIDE.vi.md).

## Lịch sử bảo vệ trước implementation —17/10/2026

Docker hoạt động; khởi động lại đúng PostgreSQL/Redis đã dừng, giữ volumes.
Checkpoint `.runtime/checkpoints/p0-20261017T024623-0631c516/manifest.json`
đã verify1219sourcefiles/149tables/3artifacts/0070 và restore clone. Không nâng
schema, không sửa backend/UI/env, không gọi provider/khởi động API/Web/worker.
Git93tracked/819untracked; rà1212sourcefiles có35review signals, không in giá
trị.3Python literal passwords bị đánh dấu không khớp1active local account;
không gọi đây là audit sạch secret hoặc full Git history.4helper tests đạt.
Không commit/push, chỉ dọn đúng restore DB tạm do script tạo, giữ dump private.
Xem [chi tiết/phạm vi/gate](S62-RELEASE-PREPARATION-2026-10-17.vi.md).
**Tiếp theo vẫn S6.2A lời mời/thành viên**; session/export/deletion chưa triển
khai, toàn S6.2/S6 chưa đạt. Bằng chứng16/10 bên dưới giữ nguyên, không phải
test/health mới17/10. Source review trước publish/key-offsite recovery còn mở.

**S6: in_progress; local preparation đạt, toàn S6 chưa nghiệm thu.** Người dùng
đã xác nhận chưa có dữ liệu thật và yêu cầu chuẩn bị local trước. Không hỏi lại
lựa chọn này trong các bước local. Không tự chọn SME/account/đích gửi hoặc tạo
dữ liệu giả trong primary để thay bằng chứng thật.

## Baseline được giữ nguyên

- S5.1–S5.6 local_accepted:0070/live382,148ORM/149physical/3archives.
- Backend binding c22f08ca…f94269,2224/2224 hồi quy trước đạt,0fail/0error/0skip.
  Đây là full Windows S5, không phải full Windows rerun S6. Lượt S6 có full
  backend Linux mới2224/2224 đạt,0fail/0error/0skip,1512.57s,61ARQ warnings.
- Không đổi backend/UI/schema/.env, không restart và không mở cờ provider.
- Preflight S6 mới chạy lại installed contract/binding, HTTP/worker lease,
  replay3/3 và kiểm tra read-only không đổi business rows; local_checks_passed=true.
  `.runtime/s6-readiness.json` luôn giữ s6_accepted/production_accepted=false.
- Sáu nhóm unit offline của preflight đạt, gồm dữ liệu thiếu, source cũ,
  regression có skip/lỗi, worker chết và cố chèn claim production đã đạt.
- Bốn nhóm unit profile CI đạt: chặn Windows/manifest/roundtrip, sai workspace,
  database primary, port/host/user/driver sai và container ID không hợp lệ.
- Native populated restore Windows kiểm lại trên pao_test đạt1/1,26.58s;
  clone giữ hashes, audit/identity và không resend.114Node tests đạt. Không
  cộng các lượt này thành một full backend mới hoặc CI Linux đã chạy.

## Kết quả cuối phần kiểm thử local16/10

- Full backend Linux: **2224/2224 đạt**, không skip. Artifact
  `.runtime/s6-linux-3a1b5903bbeb452297dce4d3c5180c39/backend-full.xml`.
- Pipeline cùng lượt đó **FAIL ở TypeScript**, vì archive thiếu5JSX; không
  đổi manifest lỗi thành PASS. Sau sửa allowlist, kiểm frontend riêng trên
  cùng image và đúng5file JSX gốc, hash toàn bộ app/API/tests/contracts/locks
  khớp. **114Node/TypeScript/build22 đạt**, không sửa UI/backend hoặc chạy lại
  full backend. Receipt
  `.runtime/s6-frontend-linux-007a30565a024df997e531c7cd2072c1/manifest.json`.
- Linux portability smoke10/10 gồm Temporal,ARQ,cancel,populated restore đạt;
  18unit offline và4archive tests đạt. Windows44cấu hình/restore và9Temporal/
  ARQ đạt. Browser nghiệp vụ/mobile/phân quyền2SME và populated restore đạt.
- Đã sửa fixture phụ thuộc `.env`, chọn binary Temporal native thay `.exe`
  Windows, và backup thiếu `.d.mts`/`.jsx`/Dockerfiles/shell hạ tầng. Không
  skip/giảm assertions, không dùng mock thay Temporal/Redis/PostgreSQL thật.
- Primary snapshot/hash `.env` trước/sau giữ nguyên; owned test containers
  đã dọn, log/source/JUnit/image/backup được giữ. Fresh preflight15:36:47UTC đạt.
- Còn61ARQ deprecation warnings và React-hook build warnings; build đạt không
  đồng nghĩa đã xử lý warnings, GitHub CI hoặc production đã được nghiệm thu.

Chi tiết, phiên bản runtime và lịch sử từng lỗi tại
[báo cáo Linux/Windows](S6-LINUX-LOCAL-2026-10-16.vi.md).
Checkpoint mới sau sửa backup: `.runtime/checkpoints/p0-20261016T153537-821c7155/manifest.json`,
1218sourcefiles/149tables/3M2artifacts/0070, verified; credentials tách riêng.

## Đã triển khai trong phần chuẩn bị local

1. `scripts/check_s6_readiness.py`: dùng lại checker live S5 và health/lease
   native, không tạo hệ thống health hoặc execution thứ hai. Kết quả có giờ
   kiểm tra, source binding, local gates riêng với external_pending. Không log
   raw subprocess exception, URL chứa credential hoặc nội dung report.
2. `scripts/test_s6_readiness.py`: không DB/network/provider; một kết quả local
   xanh không thể tự đóng gate business/CI Linux/production.
3. Sửa CI precheck còn ghim114ORM thành148ORM theo schema0070; chạy đủ danh
   sách Node tests thay vì chỉ runtime25ca. Thêm `--preflight-only` để kiểm
   contract/metadata an toàn, không gọi đó là full regression.
4. Workflow dùng PostgreSQL/pgvector17 cùng baseline local, thời hạn60phút
   vì full Windows gần nhất mất35phút; synthetic config, read-only repository
   permissions, không credential thật. Thêm unit preflight S6 vào CI.
5. Runbook S6 và checklist pilot/production trong `S6-LOCAL-PREPARATION.vi.md`.
6. Profile phục hồi CI riêng đã source_verified tại `ci_restore_profile.py`:
   chỉ Linux/GitHub workspace tương ứng, DBpao_test/127.0.0.1:5432/userpao và
   container ID64hex do job cung cấp; chỉ --populated, cấm --apply-manifest.
   Nhánh Windows giữ nguyên guard root/port/container local. Profile GitHub chưa
   chạy hosted; Linux local dùng PG client native riêng, có guard test-only và
   đã chạy populated restore thật trong smoke/full suite, không mount Docker socket.
7. Runner tạo JUnit trong `.runtime/backend-full.xml`, workflow chỉ upload đúng
   file test synthetic này, không upload runtime directory/.env/dumps/keys.

## Các gate vẫn mở — không biến thành PASS bằng fixture

| Gate | Trạng thái | Điều kiện đóng |
|---|---|---|
| S6.1 read-only business | external_pending, người dùng hoãn | Chọn SME/brand/account/kỳ, cấp quyền đọc, export thật, đối chiếu nguồn/coverage/tiền/timezone/attribution/quota |
| S6.1 một hành động thật | external_pending | Adapter hỗ trợ, đích/quyền/phê duyệt riêng, giới hạn tiền và đối soát unknown; không kế thừa quyền từ S5 mock |
| S6.2 kiểm thử Linux local | đạt theo từng stage, không một pipeline end-to-end xanh | Backend2224/Node114/typecheck/build22/restore có bằng chứng riêng; giữ pipeline TypeScript lỗi nguyên trạng |
| S6.2 GitHub CI | chưa chạy hosted | Workflow/guard có sẵn, không tự push/dispatch hoặc gọi local container là GitHub run |
| S6.2 tài khoản | implementation_pending | Invite-only do owner mời, member deprovision theo SME và thu hồi phiên server-side; chưa có luồng đầy đủ |
| S6.2 dữ liệu | implementation_pending | Export theo ACL, yêu cầu xóa có preview/xác nhận; đồng bộ retention cũ với chính sách chưa tự xóa |
| S6.2 production | chưa đạt | Môi trường riêng, HTTPS/security/lifecycle/retention/monitoring/restore/rotation/reboot-failover có bằng chứng |
| S6.3 owner pilot | chưa đạt | Owner thật nghiệm thu; đo chất lượng, resource và chi phí theo từng tenant |

## Phát hiện CI và profile đã chuẩn bị — chưa thay cho chạy Linux thật

`test_p7_restore.py` gọi `check_p7_restore.py --populated`; script phục hồi cố
ý chỉ cho `F:/PAO-ACOS`, port15432 và Docker container local. Workflow Linux
dùng workspace/port5432/container service khác. Đã thêm profile restore riêng
và unit guard, giữ guard Windows/primary nguyên vẹn; không bỏ test/skip để làm
CI xanh. Nay có Linux local thật với PG client native, binary Temporal ELF,
full backend2224và frontend kiểm riêng sau sửa archive. Không suy GitHub run
hay production từ unit platform giả lập hoặc từ Docker build thành công.
**Một YAML đã sửa không phải một CI Linux đã chạy thành công.** Không tự push
mã hay dispatch workflow từ yêu cầu chuẩn bị local.

## Việc tiếp theo duy nhất

**Triển khai lifecycle tài khoản/dữ liệu S6.2 đã được chốt**, bắt đầu lời mời và
thành viên theo SME, rồi thu hồi phiên và export/yêu cầu xóa. Xem
[ADR đã duyệt](ADR-S6-ACCOUNT-AND-DATA-LIFECYCLE.vi.md). Không hỏi lại hai lựa chọn;
không gọi tài liệu này là các tính năng đã có. Backup/restore verified trước
migration, test clone và browser trước rollout. Không làm lại P6/S5 hoặc full
Linux baseline khi code/test inputs không đổi; không bật Ads/Telegram/public
deploy. Các gate dữ liệu thật/host/pilot vẫn giữ pending theo lựa chọn người dùng.
