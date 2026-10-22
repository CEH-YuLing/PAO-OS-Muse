# P0.5 — Local operations, CI và checkpoint backup
Ngày 05/10/2026. Repo F:\PAO-ACOS.
**PASS local. Production supervisor/reboot gate CHƯA ĐẠT.**
Người dùng xác nhận chưa có máy ảo/VPS thử riêng; không reboot host hiện tại.

## Đã triển khai

- ARQ worker lease key pao:worker:health, chu kỳ15s/TTL native16s; catalog chỉ đọc
  pTTL. Scope liveness_only, không khẳng định nghiệp vụ/provider inference khỏe.
- Bridge phát lease15s sau collect/deliver và dọn khi lỗi/thoát; disabled không
  đọc Redis hoặc gọi Telegram. Real Telegram vẫn tắt, chưa live acceptance.
- Catalog operations additive: worker/bridge liveness và production_reboot_accepted=false.
  API vẫn authenticated và workspace membership; không endpoint admin mới/public.
- Request middleware sinh X-Request-ID server-side, log JSON allowlist:
  event/request_id/method/status/duration_ms. Không log path/query/header/body/
  raw exception; không tin incoming correlation header. Launcher tắt Uvicorn
  access log để không ghi raw URL. Không tuyên bố mọi thư viện/Next dev log đã
  được redaction toàn cục; chỉ log HTTP mới được kiểm.
- Supervisor ACOS-local mặc định observe-only, xác minh PID+UTC start-time+
  interpreter+entrypoint. RepairMissing opt-in, max3 restart, giới hạn số vòng và
  poll5–60s. Chỉ khởi động process mất, không kill process sống/hung, không rebind.
  --safe-repair từ chối pending/active jobs, external flags hoặc enabled schedules.
  Chưa đăng ký Scheduled Task/service tự chạy khi boot; không production supervisor.
- check_acos_health.py: HTTP và worker lease probe có giới hạn; fail nếu chưa khỏe.
  HTTP retry3 lần/timeout3s, worker tối đa20 probes1s, không sửa trạng thái.
- run_p0_checks.py kiểm full savedUTF8 OpenAPI,64ORM tables, backend test runner
  pao_test/Redis15, runtime/SSE và TypeScript. GitHub workflow read-only permissions,
  synthetic CI credentials, Postgres/pgvector + Redis services; không real connector.
  **Local runner đã chạy. YAML kiểm cú pháp. GitHub Actions remote chưa chạy/push.**
- Isolated production build PAO_BUILD_CHECK=1 → .pao-build-check; dev cache giữ.
  Next tự thêm generated types vào tsconfig và format file, đã typecheck/build đạt.
- backup_acos_checkpoint.py tạo source.zip+DB backup+manifest SHA256 không overwrite.
  DB restore-test cô lập so counts/revision/3 archives. Archive read-back từng file
  theo manifest; không extract lên workspace, không full cold machine rebuild.
  Loại operational .env/runtime/models/dependencies/build/cache/Git history.
  Khóa encryption/JWT không nằm trong source archive: phải giữ qua private recovery
  procedure riêng. Đây là backup private, không phải chứng nhận mọi source không
  chứa hardcoded secret. DB dump chứa dữ liệu riêng, tuyệt đối không commit/share.

## Gate và kiểm chứng

Preflight jobs9nhóm/lịch0, flags bên ngoài false. Backup trước rollout:
.runtime/m2-20261005T150147-3ee14ac5.dump,286494bytes;65tables/3archives/revision0024.
API/ARQ drain trước source đổi; không migration mới hay sửa dữ liệu thật.

| Gate | Kết quả |
| --- | --- |
| Local CI full contract/metadata | PASS full OpenAPI;64 ORM tables; Alembic check không có thay đổi mới |
| Backend full regression | **366 passed**, không skip,408.69s; pao_test/Redis15; real-clock bật |
| Real ARQ recovery | between70.94s/during96.84s; một tool claim mỗi ca |
| Runtime/SSE | **8/8 PASS** |
| TypeScript | PASS --noEmit |
| Production build | PASS;18 pages; dist riêng, không deploy |
| Browser acceptance | **12 routes PASS** bằng mock API |
| Live OpenAPI | Baseline/source/savedUTF8/live bằng nhau |
| Live artifact replay | **3/3** M2 cũ; hash/content giữ nguyên;0job mới |
| HTTP/correlation/catalog | API health/ready/Web200, X-Request-ID32hex, worker healthy lease, bridge disabled |
| PID identity | API1828/worker17104 đúng interpreter/UTC-start-time/entrypoint |
| Supervisor repair drill | Worker riêng dừng khi idle; phát hiện missing; restart1; API/Web/Ollama giữ; final0missing/healthPASS |
| Bounded startup probe unit | PASS retry/recovery/permanent-failure/exhaustion, không network |
| Bridge lease unit | PASS mock publication/cleanup; không DB/provider network |
| Backup checkpoint | Manifest/source hash read-back + DB restore đạt;65tables/3archives/0024 |

Check startup đầu tiên API chưa bind nên unavailable; probe ngay sau worker
repair ban đầu chưa thấy lease nên FAIL. Không ghi các lần này là PASS.
Steady-state probe/log xác minh startup bình thường; thêm retry/chờ lease có
giới hạn trong health checker, kiểm unit và lặp repair drill đã PASS.
Không đổi native lease thành healthy giả để qua gate.

Checkpoint đã verify:
.runtime/checkpoints/p0-20261005T152541-08ae6dbb/manifest.json (441 source files).
Checkpoint final có thêm tài liệu nghiệm thu đã verify443source files; xem manifest
mới nhất dưới .runtime/checkpoints, không sửa snapshot/manifest cũ. Manifest là
snapshot tại thời điểm tạo; không chỉnh nó để khớp thay đổi source về sau.

Binding cuối:
4b59dc6f87bafea566a03b03266d93d9a94c01dceed220ad18771249813d0712.

Chỉ app/platform_api/runtime trong preflight backend đổi; modules operations/tests
mới. Shared schema/models và migration vẫn nguyên. Script/UI build config thay
theo scope operations, không dependency mới. API binding/source khớp; worker
interpreter/source/startup/liveness kiểm, chưa có digest RPC riêng.

## Runbook local

Từ F:\PAO-ACOS với PAO_ROOT/PYTHONPATH local như launcher:

1. scripts/start_acos_local.ps1: khởi động local, không deploy công khai.
2. .venv/Scripts/python.exe scripts/check_acos_health.py: readiness/liveness,
   nonzero exit là chưa đạt, không chỉ nhìn PID.
3. scripts/supervise_acos_local.ps1: mặc định observe-only.
4. -RepairMissing -Cycles1: chỉ idle+disabled integrations/schedules; nếu active/
   pending/source pin cũ cần người xử lý, không tự resume.
5. .venv/Scripts/python.exe scripts/backup_acos_checkpoint.py: private backup,
   verified source archive+DB; không ghi đè hoặc restore DB local.
6. CI local: PAO_ARQ_WALL_CLOCK_TESTS=1 python scripts/run_p0_checks.py;
   build isolated: PAO_BUILD_CHECK=1 node node_modules/next/dist/bin/next build apps/web.

## Chưa đạt / rollback

Production service installation, unattended recovery khi jobs active, OS reboot/
power-loss drill trên môi trường riêng, real bridge/provider health, remote CI
execution và cold restore gồm private keys đều chưa nghiệm thu. Restart worker
local không phải reboot; archive read-back không phải rebuild máy mới.

Không bật Ads/email/Telegram thật/M4, không sửa bản gốc Apex/Javis, không commit/
push. Source protected Apex clean. Không --roundtrip/downgrade/rebind/sửa archives.

Rollback bằng patch review theo checkpoint, idle/backup/drain trước restart
API/ARQ cùng source; trả middleware/health settings/imports về cũ. Không reset
--hard, xóa DB hoặc sửa digest để tiếp tục job cũ.
