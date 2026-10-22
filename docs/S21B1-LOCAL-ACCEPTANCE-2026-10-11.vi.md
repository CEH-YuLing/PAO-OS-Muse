# S2.1B1 — Persisted staged connection grants

Ngày11/10/2026. Target `F:\PAO-ACOS`. Trạng thái **local_accepted** cho B1;
full regression đạt. Manifest/restore niêm phong cuối ghi trong phụ lục dưới cùng.
[Master roadmap](PAO-MASTER-GAP-AND-ROADMAP.vi.md) sở hữu thứ tự;
[ADR-S21B1](ADR-S21B1-STAGED-CONNECTION-GRANTS.vi.md) ghi thiết kế/rủi ro.
Không sửa Apex/Javis hoặc commit/push dirty tree.

## Đã triển khai và giới hạn

- Ba bảng reference/grant/audit scoped SME, native source reference không copy
  credential. Model manager phải chọn rõ chính actor owner/admin, native version
  thiếu giữ null; MCP/Ads giữ native creator và private Brain ACL.
- Sáu operations apply/list/eligibility/revoke reference/revoke grant/audit.
  Apply đối chiếu preview/hash/parent/account/grantee; transaction/UUID replay,
  first-use concurrency, TTL không gia hạn, conflict/CAS và revoke không resurrect.
- Grant read_only gắn đúng brand/account/member; immutable identity/scope/expiry,
  audit UPDATE/DELETE bị DB trigger chặn. Không tuyên bố chống DBA/DDL/TRUNCATE.
- Fresh eligibility kiểm member/User/manager/expiry/source status/version/config
  fingerprint/Brain/account provenance; không load/decrypt credential hoặc gọi
  provider. DB SHA256 projection, fingerprint không trả API/audit.
- JSON8KiB/closed input/redaction/no-store; storage bounded100refs/500grants mỗi
  SME gồm revoked. Đây không phải quota/fairness/vault đã đạt S2.2.
- **Tất cả mới chỉ staged, execution_enabled=false.** Eligibility snapshot
  không là runtime admission, approval hay revoke nguyên tử. B2 phải pin/lock/
  recheck engine/MCP/Ads trước resolve/call/publish; native access cũ chưa đổi.
  Không tự backfill native connections hay installation config vào SME.

## Kiểm chứng

| Gate thực hiện trong lượt này | Kết quả |
|---|---|
| `check_s21b1_tests.py`:10files, grants36 + inventory/native/tenant/factory/engine |172passed/0failed/0skip,100.73s |
| P7 populated restore + S13 tenant/SSE + skill version/fresh-process recovery |32passed/0failed/0skip,53.89s |
| `scripts/test_s03_restore.py` |7/7 normalization guards |
| Node runtime/SSE/tenant suites |25/25; có8runtime/SSE |
| TypeScript noEmit và isolated production frontend build |Đạt;21static pages; không ghi live Web cache |
| `check_s13_tests.py --full`, pao_test/Redis15 |**1240passed/0failed/0skip**,1485.44s;25Node + TypeScript cũng đạt |
| OpenAPI compatibility với checkpoint S21A |311existing operations/components giữ nguyên; thêm6operations/5paths/3schemas; tổng317,42routers |
| Clone0048→0049→0048→0049 |Đạt;114legacy row hashes giữ nguyên, rollback schema tương đương, không backfill; main không đổi khi thử |
| Pre-deploy exact restore |Đạt0048;114business/115physical/3archives,primary unchanged |
| Rollout0049 + alembic check |Đạt;114legacy row hashes/M2archives giữ nguyên,3bảng mới empty |
| Live contract/source binding/M2replay |Đạt317;3/3archives,0049 |
| Live inventory/ref/auth/validation |Đạt1manager scope; no-store/401/redacted422; không tạo live grant |
| API health/ready/Web và worker |200/200/200,healthy;Telegram bridge disabled |
| Idle |Tất cả active jobs/tools/outbox counters0 |
| Final checkpoint/restore |Manifest và kết quả niêm phong ghi trong phụ lục cuối; không dùng checkpoint0048 thay0049 |

AST syntax9file mới/ảnh hưởng đạt; Git diff whitespace với Windows CRLF đạt.
Lần kiểm dùng tạm core.autocrlf=false báo toàn bộ CRLF là trailing whitespace;
không format dirty tree, không đổi global config; kiểm đúng cr-at-eol đạt.

Các nhóm có test trùng, không cộng thành tổng unique. Hai SME/provider/account
trùng ID, rotation/delete/revoke/role/inactive/expiry/private Brain và DB tamper
được kiểm trong pao_test. Live DB chính chỉ có1manager scope và0newmapping;
không lấy live smoke đó làm kiểm chứng hai SME hoặc real provider.
Không thay frontend UI; không có browser acceptance Settings/grants mới,
mic/live channel/production gates vẫn mở.

Lượt focused đầu142pass/27fail vì so UUID model manager với actor string;
đã normalize UUID thành string, giữ explicit-self guard. Lượt sửa169/169 đạt,
bổ sung3case và fresh-request concurrency rồi chạy toàn172case trên bản cuối.
Không bỏ assertion/skip hay nới quyền. Một invocation affected pytest ban đầu
dùng sai tên `test_skill_runs.py`, không collect/chạy test nào; đã chọn đúng
version/process-recovery files và32case đạt. Warnings còn legacy React Hooks
và29ARQ deprecated.close trong full suite, không tắt rule hoặc nâng dependency
ngoài scope. Full có real ARQ/Redis wall-clock recovery79.75s/96.28s, giữ
assertion một tool claim. Đây không là real model/provider hoặc browser acceptance.

## Rollout và khả năng phục hồi

Backup nguyên baseline0048 trước sửa:
`.runtime/checkpoints/p0-20261011T130714-abb534ed/manifest.json`
(857source/115physical/3archives). Pre-deploy current-source backup:
`.runtime/checkpoints/p0-20261011T132807-719578f4/manifest.json`
(866source/115physical/3archives/0048), exact restore row/schema khớp.
Clone migration dump giữ tại `.runtime/s21b1-pre-a596115691f54ff5bcd54bfcded441fa.dump`.
Chỉ các DB clone riêng do invocation tạo đã dọn; primary/dumps/source giữ nguyên.

Apply guardedROOT/main15432/manifest/source+dump hashes/binding và idle trước
upgrade0049. Restart chỉ API PID6316/worker10176 sau kiểm executable/start-time;
không sửa Web/Docker. Main chỉ thêm schema, không sửa tay rows/history/archives.
Không có Docker lỗi nên không recovery Docker.

Source/live binding `exact-backend-source-v1`:
`142d5c0add8c341449165896f201eda2f170c7b90c5ce9bf722c10a1d3f50829`.
`.env` SHA256 không đổi:
`5672F74189BCEF6C110D4C434E956D4F324598EE3901B88BBD56902C945FBEA7`.
Không đọc/in secret, provider calls, tin Telegram, Ads/spending/publishing hoặc
public deploy. Source ZIP không chứa .env/keys; recovery keys cần giữ riêng an toàn.

## Bước kế tiếp duy nhất — S2.1B2

Nối immutable reference/grant/tenant/brand/account/source pins vào admission và
engine/MCP/Ads jobs, fresh recheck trước credential resolve và publish. Test
queue thực khi revoke/expiry/membership/manager/config/account đổi; phải deny
trước call và không fallback legacy với registered connection. Không repin lịch
sử cũ. Chọn từng adapter/checkpoint, giữ native role/private Brain/tool/approval.
S2.1B toàn bộ chưa đạt; S2.2/S2.3/S3/S4 chưa dispatch, không hỏi lại kiến trúc SaaS.

## Checkpoint niêm phong cuối — đạt

`.runtime/checkpoints/p0-20261011T135616-088c2978/manifest.json`

Verified867sourcefiles/118physicaltables/3M2archives/revision0049. Exact restore
117business tables khớp row hashes/schema definitions và archive evidence;
primary unchanged, external_calls=false. Chỉ clone do invocation tạo
`pao_s03_restore_3a3b54ea1b054db1ade5a8beb4d179bd` đã dọn; backup/dump/source
ZIP/manifest và dữ liệu chính giữ nguyên có thể phục hồi.

Sau seal: API health/ready/Web200,workerhealthy,live contract317/source binding
khớp,M2replay3/3,staged API auth/redaction/no-store và idle0 đều đạt. Hash.env
giữ nguyên. Snapshot chứa code và roadmap/ADR/README/register/acceptance đồng bộ
B1 local_accepted → B2 kế tiếp. Không đổi code/config sau seal; chỉ bổ sung
self-reference này vào báo cáo. Toàn S2.1B chưa đóng và chưa bật runtime authority.
