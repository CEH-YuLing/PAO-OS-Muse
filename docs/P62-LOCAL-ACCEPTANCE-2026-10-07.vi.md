# P6.2 — Nghiệm thu workflow bền vững LOCAL, dry-run

Ngày07/10/2026, dự án `F:\PAO-ACOS`.
**P6.2 LOCAL dry-run đã đạt.** Các gate model/business execution và production
vẫn chưa đạt và không được tự bật theo kết quả này.
Không tương đương nghiệm thu model execution hoặc production.

## Phần triển khai cuối C4/D

- Dispatcher bounded trong ARQ cron hiện hữu; không thêm scheduler sở hữu waits.
  Reconcile reservation chưa có outcome, kiểm tra quyền/pin ngay trước enqueue.
  Pending permission-lost ghi failed known-no-effect; không tạo Attempt.
- Executor echo đăng ký đúng một lần khi `WORKFLOW_WORKER_ENABLED=true`.
  Worker Temporal riêng chỉ đăng ký kernel P6.2, projection và bridge;
  startup gate false từ chối trước mọi kết nối. Không đăng ký legacy automation.
- Readiness cần cả ARQ/Temporal lease20s, marker khớp backend hash/task queue;
  stale/thiếu lease fail closed. Heartbeat worker riêng lỗi thì worker thoát,
  không giữ process sống với một task health đã chết.
- Launcher hỗ trợ Studio; stop worker kiểm tra idle và executable/start time.
  Rollback tắt admission/dispatch trước, giữ worker để drain cancel/reconcile.
- UI ở Skills: mở immutable Plan ID, xác nhận echo, start, approve/reject,
  cancel, trạng thái/sequence/completed steps, manual-review và command ledger.
  Network chưa rõ kết quả giữ nguyên request key/body, không gửi quyết định khác.
  Guards ngăn dữ liệu cũ cập nhật workspace mới. Không có retry side effect unknown.

## Bằng chứng kiểm thử

- Regression checkpoint đầu: **728passed**, không skip,651.10s,3cảnh báo
  ARQ.close deprecation từ dependency. Backend implementation giữ nguyên sau lượt này.
- ARQ subprocess chết sau claim: exit91, đợi lease60s bằng đồng hồ thật;
  `worker_lost_unknown`/manual_review, một Attempt, không tự claim lại.
- Chết sau receipt: exit92, DB receipt còn nguyên. ARQ subprocess mới nhận lại
  execution envelope trên transport queue test riêng và transport ID khác,
  cố ý vượt Redis dedup; receipt DB chặn claim thứ hai. Không chứng minh đã
  restart Redis server hoặc tái chạy business side effect.
- Hai bài actual TCP connection loss đạt: PostgreSQL/Redis kết nối đến cổng
  đóng không tạo Attempt, reconnect executor hoàn thành một lần; Temporal
  connection refused giữ command pending, sau backoff thật2s gửi đến server
  fixture thật, delivered ở attempt2. Không dừng container live.
- Browser thật qua HTTP API subprocess riêng, DB pao_test/Redis15/Temporal/ARQ
  thật: start + approve hai bước -> completed; reject -> cancelled; cancel ->
  cancelled; checkbox confirmation gate; không page error. DB chỉ2Attempt,
  mọi Task vẫn draft, Run0. Forward HTTP request, không fabricate API JSON.
- Focused browser/restarted-ARQ cuối:2passed39.57s. Các lỗi harness trước đó
  đã sửa: chờ login lưu session trước điều hướng; Windows Redis timeout cũng
  là lỗi kết nối; ARQ burst không chờ stale transport lock của process đã chết.
  Không bỏ assertion receipt, permission hoặc cancellation để đạt test.
- Runtime/SSE8/8,12trang UI fixture cũ đạt,7Temporal histories replay,
  production frontend build18pages; source OpenAPI UTF-8 giữ nguyên248operations.
  UI fixture cũ không thay thế bài HTTP browser P6.2.
- Smoke worker-off từ chối kết nối; worker-off không đăng ký echo;
  worker-on đăng ký đúng một function echo. PowerShell/Node/Python syntax đạt.
  Một smoke command bị treo trong sandbox đã dọn đúng owned PID/path/start-time;
  lượt có quyền workspace thích hợp đạt, không đụng runtime đang dùng.

## Rollout và phục hồi

Checkpoint trước rollout verified:
`.runtime/checkpoints/p0-20261007T122515-26f988bb/manifest.json`,658sourcefiles,
94physicaltables,3artifacts,revision0038. Không migration mới.
Idle mọi loại job0 trước restart. Restart riêng API22812/ARQ7520;
Web18064/Ollama1780 và Docker volumes giữ nguyên. Health/ready/Web200,
worker healthy, full live contract/binding khớp, M2archive3/3replay.
Live StudioExecution/Command0; durable/dispatch/worker/Temporal và Meta/write/
autopilot/M4 gates vẫn tắt. Không tạo workflow trên dữ liệu đang dùng.

Regression cuối: **731passed**, không skip,780.66s,4cảnh báo deprecation
ARQ.close từ dependency. Lượt này gồm730backend +1HTTP browser. Sau đó tách
browser khỏi collection mặc định để backend-only CI không cần Web; các test
assertion không bị bỏ. Browser tại đường dẫn mới chạy riêng lại đạt1/1,51.94s.
Pytest directory + filename có thể dedup mất file nonstandard, nên `--browser`
gọi subprocess nghiệm thu riêng sau backend, không dựa vào collection cộng gộp.

Fixture bridge cuối chạy riêng lại1passed16.91s; clone restore đạt
**93business tables hash-exact**,6step events,2dry-run attempts,
3delivered commands và7projections. Source hash giữ nguyên qua restore;
chỉ clone UUID tự tạo được dọn, dump giữ trong `.runtime`. Đây không phải
restore/reboot database đang dùng. Handoff health/ready/Web200, worker healthy,
mọi loại active job0, worker flag thực tế false. Không có migration mới.
Checkpoint source/DB cuối được tạo bằng `scripts/backup_acos_checkpoint.py`
sau khi chốt các tài liệu này; manifest nằm trong `.runtime/checkpoints`.

## Giới hạn và cách chạy lại

**LOCAL dry-run không phải model/business execution.** Echo receipt chỉ kiểm tra
schema/exit criteria, không phải evidence quảng cáo hoặc báo cáo bằng model.
Actual TCP failure kiểm tra client loss/recovery, không phải thử shutdown/reboot
PostgreSQL/Redis/Temporal production. Gate VPS/reboot, external MCP read-only,
Meta OAuth/M3realdata vẫn chưa đạt; không bỏ các gate đó để chạy automation thật.

- Backend-only: `python scripts/test_backend.py` (pao_test + Redis15).
- Backend + HTTP browser: `python scripts/test_backend.py --browser`; cần
  Web đang chạy và Playwright browser. URL mặc định3200, có thể đặt
  `PAO_FRONTEND_URL`. Browser gate explicit để backend-only CI không phụ thuộc UI.
- Browser riêng: pytest `apps/api/tests/p62_browser_acceptance.py` với cấu hình
  pao_test/Redis15, PYTHONPATH apps/api, synthetic secrets chỉ trong process.
- Replay: `python scripts/check_p62_history_replay.py`.
- Fixture/restore: `python scripts/check_p62c_bridge_fixture.py`.
- Vận hành/drain: [runbook](P62-RUNBOOK.vi.md).

P6.3 trở đi chưa triển khai trong lượt này. Không commit/push, không thay nguồn
bảo vệ, không lưu secret mới hoặc sửa dữ liệu database đang dùng để qua test.
