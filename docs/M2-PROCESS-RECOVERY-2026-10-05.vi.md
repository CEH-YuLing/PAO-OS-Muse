# M2 — Kiểm tra process bị ngắt và recovery

Ngày 05/10/2026; chỉ thay đổi tests/tài liệu tại `F:\PAO-ACOS`.
Không thay code runtime hoặc policy recovery trong checkpoint này.

## Kết quả

- Backend **245/245**, 117.36 giây, database `pao_test` riêng.
- Runtime/SSE **8/8**; local idle: runs 0, tool_calls 0.
- API /ready và Web /skills HTTP 200. Source `F:\Apex\apex` không sửa.
- Không sửa frontend, không chạy lại build/browser trong lượt này.

## Hai ca fault

Test khởi động một process Python chạy `runtime.execute_run` với command
daily-business-brief, đọc database thật của test. Gateway giả không gọi LLM.
Sau khi process báo đã tới fault point, parent xác minh trạng thái database
rồi kill process thật bằng OS. Không phải hủy coroutine.

| Điểm kill | Trước kill | Sau process recovery mới |
|---|---|---|
| Sau tool đầu, trước tool thứ hai | Run running, một call completed | Run failed/worker_lost; call đầu vẫn completed, không thêm call |
| Khi tool đầu đang đọc | Run running, một call running | Run failed/worker_lost; call unknown/worker_lost, không tự retry |

Process mới gọi dispatcher production hai lần, sau đó thử execute lại cùng
run. Tests xác minh: snapshot không đổi; không enqueue lại; chỉ một run.failed;
không response/skill_result thành công; không response.completed; agent failed;
event sequence không trùng. Recovery lặp không tạo thêm công cụ.

Files: `apps/api/tests/test_skill_process_recovery.py` và helper
`apps/api/tests/_skill_crash_process.py`. Helper từ chối database không phải
`/pao_test`; integrator external/memory tắt trong process kiểm thử.

## Phạm vi chính xác

Đây là **OS process kill + fresh-process recovery harness**, không phải kill
worker ARQ đang phục vụ local. Redis enqueue được giả lập; không đo retry/job
lease của ARQ hoặc chứng minh khôi phục Redis sau mất dữ liệu. Worker local,
API, Web và containers không bị dừng ở lượt này.

Để không chờ lease thật, chỉ process recovery test đặt clock runtime/tool
gateway tiến 120 giây. Không sửa timestamps database bằng tay. Runtime timeout
trong helper là 10 giây. Đây không phải đo độ trễ recovery thực tế: cấu hình
local bình thường vẫn dùng run timeout chung + 60 giây; call running hết lease
sau 90 giây; dispatcher định kỳ 10 giây. Guard skill không tự đổi lease recovery.

Test chỉ chứng minh **dừng an toàn sau interruption**, không tự tiếp tục task
từ tool tiếp theo, không bảo đảm exactly-once provider khi call unknown.
Không thử mất điện, reboot máy, mạng/database mất kết nối hoặc nâng cấp code
giữa job. Không dùng Ads thật hoặc thay dữ liệu nghiệp vụ.

## Trạng thái và bước tiếp theo

M2 vẫn nghiệm thu có điều kiện. Resource guard command và recovery fail-closed
ở hai fault points trên đã có bằng chứng. Chưa có executable-version archive
để replay code cũ, chưa nghiệm thu toàn stack ARQ/Redis theo wall-clock.

Checkpoint tiếp theo đã kiểm [guard tương thích version](M2-VERSION-GUARD-2026-10-05.vi.md):
khác/thiếu binding phải từ chối, không tự replay job dở bằng code mới. Bước tiếp
theo hiện hành là wrapper attribution read-only bằng fixtures; doanh thu doanh
nghiệp và quan hệ nhân quả vẫn cần dữ liệu/kiểm chứng M3 riêng.
