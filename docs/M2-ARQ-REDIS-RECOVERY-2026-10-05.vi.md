# M2 — ARQ/Redis recovery bằng đồng hồ thực

Ngày 05/10/2026; target F:\PAO-ACOS. Chỉ thêm tests/tài liệu; không đổi
runtime, manifest, frontend hoặc schema database trong checkpoint này.

## Hai ca đã kiểm

| Điểm kill worker ARQ riêng | Thời gian thực từ kill/restart đến trạng thái yêu cầu | Kết quả |
|---|---|---|
| Sau business tool đầu, trước tool thứ hai | 72.69s | Run failed/worker_lost, call đầu vẫn completed |
| Tool đầu đang đọc | 96.83s | Run failed/worker_lost, call unknown/worker_lost |

Mỗi ca dùng PostgreSQL pao_test và Redis DB15 thật, queue UUID riêng. API test
tạo queued run đã commit; test xóa đúng Redis payload/queue member của run đó.
Worker startup dispatcher đưa durable run lại vào queue và ARQ claim job thật.
Test xác minh in-progress key thật trước khi kill process bằng OS.

Worker process mới chạy dispatcher production và cron mỗi 10s. Không mock Redis
hoặc now(), không sửa started_at/updated_at trong database, không gọi dispatcher
trực tiếp từ parent để làm quá trình recovery nhanh hơn.

Sau recovery: một run.started, một run.failed; snapshot giữ nguyên; một tool
proposed/started, không call thứ hai hoặc claim lặp; không response/skill_result
hoàn chỉnh và không response.completed. Call unknown không tự retry.

## Cấu hình kiểm thử và giới hạn

- Worker test đặt runtime timeout **10s**, ARQ job timeout **30s**, max_jobs 1,
  max_tries 1. LLM gateway giả; các command đang kiểm không gọi LLM. External
  integrations/memory tắt. Hook chỉ giữ process ở fault boundary để parent kill.
- Run recovery theo timeout cấu hình + 60s; call running lease 90s; cron 10s.
  Các số 72.69/96.83s chỉ đúng cấu hình test ngắn, không phải SLA local/production.
- Worker local đang phục vụ dùng cấu hình riêng. Recovery hiện vẫn dựa timeout
  chung, không theo deadline skill snapshot; manifest deadline ngắn không tự làm
  thời gian phát hiện worker mất ngắn hơn. Cần rà gate này trước production.
- API tạo run trong ASGI test client; đây không phải kiểm socket HTTP/UI end-to-end
  trong lúc crash. Redis server/container không bị restart hoặc mất điện. “Mất
  Redis job” là xóa một payload/member riêng; không phải FLUSHDB hoặc chứng minh
  recovery khi toàn Redis mất dữ liệu/mạng.
- Không thử upgrade executable, corruption, tải nhiều worker hoặc exactly-once
  external provider. Snapshot/version tests riêng vẫn là những bằng chứng khác.

## Cô lập và chạy lại

Files: apps/api/tests/_arq_recovery_worker.py và test_arq_wall_clock_recovery.py.
Helper từ chối DB không phải /pao_test, Redis không phải DB15 hoặc queue không
có prefix test. Queue cron name cũng riêng để không chung keys với worker khác.
Cleanup chỉ xóa queue/health key và job keys thuộc test; không FLUSHDB, không
đụng runtime queue local. Một số cron progress keys tự hết TTL theo ARQ.

Hai ca là opt-in vì đợi lease thực. Đặt PAO_ARQ_WALL_CLOCK_TESTS=1 khi chạy
scripts/test_backend.py; driver vẫn tự chọn pao_test và Redis15. Khi không opt-in,
hai ca được skip có lý do, không được báo là đã kiểm recovery wall-clock.

## Trạng thái

Kết quả full regression cuối khi bật opt-in: **267/267**, 373.04 giây (6 phút
13 giây), không skip hai ca wall-clock. Runtime/SSE **8/8**. API /ready và Web
/skills HTTP 200; PAO local idle 0 runs/0 tool calls; source F:\Apex\apex không
sửa. Không restart worker/API/Web/containers local; chỉ kill process test riêng.
Không chạy lại frontend build/browser ở lượt này vì chỉ đổi tests/tài liệu.

M2 vẫn chưa đánh dấu hoàn tất toàn bộ. Local command/read-only recovery đã có
bằng chứng ARQ/Redis thật với cấu hình test; không tự resume hoặc báo success.
Bước kế tiếp: rà gate M2, đặc biệt deadline recovery theo snapshot so với timeout
chung, trước khi đưa dữ liệu thật M3 vào scope. Artifact archive/replay, token
budget skill LLM và business correctness vẫn chưa được nghiệm thu toàn bộ.

Cập nhật checkpoint sau: deadline cleanup đã theo effective pinned budget;
helper recovery đổi global timeout lên 120s để kiểm pin 10s vẫn có hiệu lực.
Kết quả mới và giới hạn xem M2-PINNED-RECOVERY-DEADLINE-2026-10-05.vi.md.
Các số và mô tả timeout chung ở trên là lịch sử checkpoint trước, không phải
trạng thái implementation hiện tại.
