# S0.3 — Phục hồi runtime và verified checkpoint trước S1

Ngày11/10/2026, Asia/Saigon. Target `F:\PAO-ACOS`; không sửa protected source.
**S0.3 đạt LOCAL:** các gates và final source/DB checkpoint đã verified.
Không triển khai S1 trong cùng checkpoint; production vẫn pending.

## 1. Recovery có thể hoàn tác

- Docker Desktop4.74.0 báo đúng lỗi dockerInference inaccessible/invalid listener.
  CLI stop timeout20s. Kiểm executable/creation-time trước dừng đúng process vừa
  launch; một child tự thoát khi parent dừng, xác minh không còn Docker process.
- Hai parent directories không reparse, chỉ chứa socket0byte tên đã allowlist.
  Đổi tên, không xóa, giữ bản cũ:
  `C:\Users\o0o_v\AppData\Local\Docker\run.stale-s03-007ed52e36f94a3695bccb7088911ee0`
  và `C:\Users\o0o_v\AppData\Local\docker-secrets-engine.stale-s03-2962ebc9782b40d9a07e62d38369de42`.
- Tạo runtime dirs trống và start Desktop Hidden. Engine29.4.3 hoạt động; đúng
  ACOS PostgreSQL15432/Redis16379 healthy, sử dụng volumes cũ. Không reset,
  reinstall, reboot, drop primary hoặc sửa settings/VHDX. Docker tự khởi động
  pao-search theo policy sẵn có; không điều khiển các container môi trường nguồn.

## 2. Database/source trước startup

- Primary và source Alembic cùnghead0048; startup upgrade head là no-op, không
  thêm schema/data migration. Idle và safe-repair gates đạt, mọi active job0.
- Source OpenAPI khớp saved UTF-8;114ORM tables,115physical tables gồm alembic_version,
  308operations; exact backend binding không đổi:
  `a298c9003a8ee07db4f164e2786c36f542f814446bf0ed268c9a6013812acdb2`.
- Checkpoint trước startup:
  `.runtime/checkpoints/p0-20261011T075937-6f096c4a/manifest.json`,819source files,
  115physical tables,3archives,0048, verified DB count/archive restore + source SHA256.
  Đây là snapshot trước hoàn thiện restore checker và final acceptance docs.
- `.env` không đổi; local SHA256 trước/sau startup khớp. Source archive loại
  `.env`/runtime/dependencies/.git; Git ignore .env/runtime/.venv/node_modules đạt,
  .env không tracked. Token-pattern scan production source chọn lọc không thấy hit;
  không gọi đây là exhaustive secret/history scan hoặc chứng nhận secret-free Git.
- Không tự stage/commit/tag/push dirty tree. Source.zip + manifest là checkpoint
  ngoài Git có checksum; Git commit/tag và off-device backup vẫn cần bước riêng.

## 3. Restore riêng và khác biệt schema đã xác định

`scripts/check_s03_restore.py` nhận đúng manifest trong runtime, kiểm hash dump/
source và binding, restore vào `pao_s03_restore_<uuid>` chưa tồn tại. Primary
không migrate; chỉ clone do lần gọi tạo mới được drop trong finally.

- Hash dữ liệu/column lists của114business tables khớp;115physical tables/revision
  và3artifact archives đọc lại được. Primary snapshot giữ nguyên trước/sau restore.
- So định nghĩa attributes/defaults,677constraints,386indexes, triggers và
  public functions. `pg_restore` reparse biểu thức text array: cast trên toàn
  `ARRAY[..]::text[]` thành cast từng literal varchar sang text, với ANY và ALL.
- Lần so text tuyệt đối ban đầu thất bại ở constraints/2partial indexes, không
  phải mất dữ liệu hoặc missing constraint. Checker chỉ canonicalize unbounded
  varchar literal arrays tương đương; không xóa checks, đổi literal/order/operator,
  bỏ constraint hay sửa primary. Bounded casts/expressions khác giữ nguyên.
- 7pure tests kiểm cast-equivalence, parentheses, ANY/ALL khác nhau, changed
  values, escaped quotes/comma/order, other SQL không đổi và defaults/functions/
  triggers không bị normalize; tất cả đạt. Canonicalize chỉ constraint/index definition.
- Final gate `row_hashes_exact=true`, `schema_definitions_equivalent=true`,
  `primary_unchanged=true`. Không gọi schema text byte-identical sau pg_dump/reparse.
- Clone thử nghiệm được dọn sau mỗi lượt; querypg_database cuối không còn
  `pao_s03_restore_%`. Dump/source được giữ; không xóa database người dùng.

## 4. Startup/live và kiểm thử

Start đúng `scripts/start_acos_local.ps1`, hidden processes đã đối chiếu:
Ollama7752, API23360, ARQ5128, Web21304. PID chỉ là bằng chứng thời điểm startup;
trước stop sau này phải đối chiếu executable/creation-time lại, không reuse mù.
Studio worker và Telegram bridge không khởi động vì gatefalse.

| Gate chạy trong lượt S0.3 | Kết quả |
|---|---|
| Docker/PG/Redis | Engine29.4.3; hai ACOS containers healthy |
| Primary/source revision | 0048/head; không migration mới |
| check_acos_health.py | APIhealth200,ready200,Web200,workerhealthy; production_reboot_accepted=false |
| check_p7_live.py | 308operations full contract/binding khớp; M2archives3/3; P7tables rỗng; external/voice gatesfalse |
| Focused backend | 19passed/0failed/0skipped,13.52s: operations/app factory/platform readiness trên pao_test/Redis15 |
| Restore checker pure tests | 7/7passed; clone restore row/schema/archive gate đạt |
| Runtime/SSE | 8/8passed,0failed/skip |
| TypeScript | noEmit đạt |
| Production build | 21/21entries, cache `.pao-build-check` riêng; Hooks và pages lint configuration warnings còn |
| Browser shell | 12module routes/interaction surfaces đạt; API fixtures của existing harness, không live-provider/business acceptance |
| Idle/safe-repair | Mọi active jobs0; sync/report schedules không enabled |

Web lần health đầu chưa cold-start xong. Sau WebHTTP200 chạy lại toàn checker
nguyên vẹn, không bỏ/nới endpoint assertion. Full1156 regression và8P6/P7HTTP
browser là evidence10/10, không chạy lại/tính là kết quả mới trong S0.3.

## 5. Thay đổi và safety gates

- Thêm restore checker +7pure tests; cập nhật `run_p0_checks.py` ORM count91
  lịch sử thành114 theo schema0048 đã đối chiếu. Giữ assertion, không bỏ contract.
  Chưa chạy full CI pipeline hoặc xác nhận GitHub CI xanh trong lượt này.
- Không đổi business backend/frontend runtime, credential, permission hoặc feature flags.
- Baseline tools_enabled/agent_runtime_enabled/engine_contract_enabled true giữ nguyên.
  Meta/Google/Telegram/Temporal/write/autopilot/Goal/channel/voice gates giữfalse.
- Không gọi provider/model inference, mở mic, gửi Telegram, đăng bài hoặc chi tiền.
- Backup ở cùng máy là local recovery checkpoint, không thay offsite disaster
  recovery; encryption/JWT keys không nằm trong source.zip, cần recovery procedure riêng.
- P7.5 microphone tiếng Việt/live channel, M3real data/Meta OAuth, live-model
  Goal, remote CI, supervisor/reboot/failover và production vẫn pending.

## 6. Lệnh tái kiểm có phạm vi

Đặt PAO_ROOT/PYTHONPATH tới target và PYTHONDONTWRITEBYTECODE/PYTHONUTF8 trong
process; không in DATABASE_URL/token/password.

```powershell
.\.venv\Scripts\python.exe scripts/check_acos_idle.py --safe-repair
.\.venv\Scripts\python.exe scripts/check_acos_health.py
.\.venv\Scripts\python.exe scripts/check_p7_live.py
.\.venv\Scripts\python.exe scripts/test_s03_restore.py
.\.venv\Scripts\python.exe scripts/backup_acos_checkpoint.py
.\.venv\Scripts\python.exe scripts/check_s03_restore.py <owned-manifest-path>
node --test apps/web/lib/runtime-state.test.mjs apps/web/lib/sse.test.mjs
```

Focused pytest yêu cầu PAO_TEST_DATABASE_URL=/pao_test và RedisDB15; fixture có
TRUNCATE trên test DB, không chạy với primary. Build dùng PAO_BUILD_CHECK=1;
browser shell dùng PAO_FRONTEND_URL=http://127.0.0.1:3200/. Không chạy lại toàn
checkpoint nếu source/phụ thuộc không đổi, trừ release gate có lý do cụ thể.

## 7. Checkpoint cuối và bước tiếp theo

Final checkpoint verified:
`.runtime/checkpoints/p0-20261011T081309-dec8abb3/manifest.json`,821source files,
115physical tables,3archives,0048. Restore chính dump này vào clone mới khớp
row hashes/schema equivalence/artifacts; primary giữ nguyên. Clone đã dọn;
backup/source giữ nguyên. Health200/workerhealthy/idle0 chạy lại sau checkpoint.

Checkpoint081026 trước đó cũng verified, giữ nguyên nhưng bị081309 thay thế cho
source checker cuối. Source.zip081309 bao gồm checker/7tests cuối và bản acceptance trước ghi dòng manifest
này; sau checkpoint chỉ cập nhật docs trạng thái/evidence, không đổi code hoặc
backend binding. Không gọi source.zip là bản chứa chính dòng self-reference này.

**Việc tiếp theo duy nhất S1.1 — tenant context và chọn doanh nghiệp đang hoạt động.**
Chưa triển khai S1; không làm lại P6/P7. Git commit/offsite backup và production
restore/reboot vẫn là gates riêng, không suy ra từ local checkpoint.
