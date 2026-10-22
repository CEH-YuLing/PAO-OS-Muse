# M2 — Skill Registry và business tools: nghiệm thu cuối

Target F:\PAO-ACOS. Phạm vi local, ba skill command được duyệt, dữ liệu fixture/
demo, chỉ đọc nghiệp vụ. **Kết luận: M2 đạt local theo các gate trong roadmap.**
M3–M8 chưa được nghiệm thu; kết luận này không phải production/business-data acceptance.

## Gate M2

| Gate theo roadmap | Implementation và bằng chứng |
|---|---|
| Manifest versioned, schema/quyền/evaluator/budget | Ba manifest được nạp từ allowlist; execution_mode chỉ deterministic_read_only; catalog/preflight có RBAC |
| Chief chọn đúng skill cho câu hỏi chuẩn | Corpus command VI/EN trong test_skill_router; không suy đoán account/kỳ hoặc chạy lệnh ghép write |
| Input/tool không hợp lệ bị từ chối | Schema extra forbid, agents/tools allowlist, scope user/workspace/account/kỳ và gateway worker recheck |
| Wrapper business chỉ đọc | Task/KPI/intelligence/creative/attribution quanh service có sẵn; SELECT-only transaction, bounded output và timeout |
| Thiếu connector/dữ liệu | insufficient_data và hướng dẫn cụ thể; NULL là unknown, currency/attribution không cộng lẫn, không bịa nguyên nhân |
| Budget | Timeout pin + recovery grace; tối đa hai command tools, response 32000 ký tự; artifact 256000 bytes; không gọi LLM (0 generated tokens) |
| Replay giữ đúng version | Artifact v1 lưu snapshot/schema/input/tools/results/nguồn/hash; run và TaskAttempt replay read-only, độc lập registry/code mới |
| Failure/recovery | Hủy/mất quyền/provider lỗi/worker kill không success giả; queued pin cũ không tự resume/replan; ARQ/Redis test riêng |
| UI/contract | OpenAPI/TypeScript, Skills preview và replay run ID, desktop/mobile, empty/error/stale response |
| Vận hành local | Regression, build, migration rollback test, backup/restore, API/Web health và idle gate |

Quyết định replay: [ADR](ADR-M2-RESULT-REPLAY.vi.md). Replay ở đây là kiểm tra và
xem lại **kết quả lịch sử**, không chạy lại executable hoặc đọc nguồn hiện tại.
Run/attempt trước 0024 không có artifact sẽ trả 409; không dựng lại bằng dữ liệu mới.
Completed về kỹ thuật không đồng nghĩa verified business; replay luôn ghi rõ false.

## Thay đổi checkpoint cuối

- skill_artifacts.py giữ reader v1 và archive byte/hash/scope/source guards.
- API GET /v1/runs/{run_id}/skill-replay; owner/session/membership như run.
- API GET /v1/tasks/{task_id}/attempts/{attempt_id}/skill-replay; task RBAC.
- Migration 0024 thêm nullable task_attempts.skill_artifact; result/evidence/
  snapshot cũ không bị đổi. Không backfill, không downgrade local tự động.
- Runtime archive cùng transaction với response/result, chỉ phục vụ khi completed.
- Attempt archive cùng transaction terminal state; terminal PATCH không được sửa.
- execution_mode=deterministic_read_only khóa skill model path. LLM mode mới bị
  từ chối; không khẳng định có token metering cho skill LLM chưa triển khai.
- Skills UI nhập Run UUID để xem lại; đổi ID/workspace/unmount bỏ response muộn.
- Scripts check_m2_test_migration.py và check_m2_restore.py có DB scope guard.

## Kết quả

Lượt đầu regression: 295 passed, 1 test mới lỗi
do dùng RunEvent.id không tồn tại, 2 wall-clock tests skip. Đã sửa test sang seq;
lượt cuối bật cả wall-clock, không dùng kết quả lượt đầu làm nghiệm thu.
Kết quả cuối:

- Backend **298/298**, 311.57 giây (5 phút 11); hai ca real-clock bật, không skip.
- ARQ/Redis riêng: OS kill giữa tools recovery **71.75s**; trong read **97.08s**.
  Test pin 10s, restart global 120s; tool lease 90s, cron 10s. Không phải SLA production.
- Runtime/SSE **8/8**; frontend build/type/lint **18/18** trang.
- Migration **0024 → 0023 → 0024** đạt trên pao_test; không downgrade local.
- Backup/restore trước migration: **65 bảng**, revision 0023, counts khớp; nâng
  local 0024 không đổi số dòng cũ. Backup .runtime/m2-20261005T112003-dbb8e92a.dump.
- Restore sau migration/smoke: **65 bảng, 3 artifacts**, revision 0024,
  counts/archive hashes khớp và reader v1 kiểm artifact trong DB restored.
  Backup .runtime/m2-20261005T112127-bb1c1c3e.dump.
- Hai DB restore-test UUID do script tạo đã xóa sau kiểm; cả hai dump giữ lại
  trong .runtime, không commit vào Git. Không xóa/sửa database chính.
- Live API → ARQ ba Chief commands đạt, kết quả insufficient_data; replay API
  và mobile UI đạt, đổi Run ID xóa output cũ và UUID sai báo lỗi.
- Skills/attribution desktop/mobile, fixtures unknown/zero/currency, response
  muộn/403 đạt; regression **12 routes** đạt ở cổng 3200. Lượt gọi sai cổng
  mặc định 3100 ban đầu connection refused; verifier test đã dừng và chạy lại
  với PAO_FRONTEND_URL, không thay config PAO để che lỗi.
- API /ready và Web /skills HTTP 200; local revision **0024 (head)**.
- Idle trước/sau nạp: 0 runs/0 tool calls. Chỉ restart API/worker/Web của ACOS;
  Docker Postgres/Redis healthy, Ollama giữ process đang chạy. Source Apex không sửa.

Demo run IDs: daily dfbe4311-66e8-4391-b275-3ae1fedfd96f; Ads
d52c62d6-e0c1-4c9b-a966-707e28046c2c; creative 82bfec00-a628-423d-9c70-362c344e316e.

## Giới hạn và bước tiếp theo

M2 local không nghiệm thu data/account ngoài PAO, causal reasoning hoặc business
revenue thật. Những phần đó là M3 theo roadmap, cần credential/account/export do
người dùng cấp rõ ràng. Không Ads write, không email/Telegram, không deploy public.

Không thực thi lại backend cũ, không auto retry tool unknown, không rolling upgrade/
HA/Redis network-loss/production SLA. Hash không phải chữ ký chống DBA; dependency
và native runtime chưa archive. Khi cần skill LLM mới, phải triển khai token guard
và evaluation riêng trước mở mode. Không đổi scope để giả vờ những phần này đã đạt.
