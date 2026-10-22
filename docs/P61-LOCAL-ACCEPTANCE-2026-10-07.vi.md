# P6.1 — Nghiệm thu workflow planning local

Ngày 07/10/2026; dự án F:\PAO-ACOS. Trạng thái: **P6.1 planning-only LOCAL đạt**.

## Đã triển khai

- Compiler DAG dùng lại validation Studio: cycle, dependency, binding/schema,
  scoped published/reviewed workflow, skill và agent; input JSON có giới hạn.
- Preview hash và xác nhận trước khi lưu snapshot bất biến + task draft,
  dependency, activity trong cùng transaction. Retry cùng request key không
  nhân đôi; phiên bản agent mới không thay snapshot lịch sử.
- API khóa sửa/chạy task đã plan; khóa vẫn có hiệu lực khi tắt planning flag.
- UI `/skills` → Workflows → definition published → preview → xác nhận tạo
  task nháp. Không gọi LLM, provider hay tool; không thêm runner/schedule.
- Meta pause, bảo toàn App/secret/encryption key. M3 live vẫn chờ xử lý OAuth.

## Bằng chứng trước rollout

- Focused backend: 49 passed, 35.42s; gồm 8 test P6.1 mới.
- Runtime/SSE: 8/8.
- Frontend production build: 18 pages, TypeScript/lint thành công.
- Browser P6.1 real HTTP trên pao_test: preview/xác nhận/2 task nháp/PATCH409 đạt.
- Browser mock: toàn bộ 12 route đạt; không dùng mock thay cho kiểm thử P6.1 thật.
- Restore fixture: 91 bảng nghiệp vụ hash-exact; 2 task/1 dependency, không
  TaskAttempt/Run/LLM attempt/business event. Không sửa database local.
- OpenAPI: 239 operation/schema cũ giữ nguyên, thêm đúng 4 operation → 243.
- Checkpoint trước triển khai: `.runtime/checkpoints/p0-20261007T090449-24deaf2a/manifest.json`.
- Checkpoint trước rollout: `.runtime/checkpoints/p0-20261007T092015-64c2b9cc/manifest.json`,
  619 source files, 92 physical tables, 3 artifacts, revision0037, verified.
  Credentials bị loại khỏi source archive; key riêng phải được bảo quản riêng.

## Kết quả rollout

- Full backend: **662 passed**, không skip, 584.08s. Hai cảnh báo ARQ deprecated
  Redis `close` trong test delivery/source; không có test failure.
- Chỉ bật `WORKFLOW_PLANNING_ENABLED=true`; Meta/write/autopilot và ba flags
  M4 vẫn false. Không thay secret, key, tài khoản hoặc remote.
- Restart đúng API/worker path và start-time sau idle gate; API PID11012,
  worker PID4772 tại nghiệm thu. Web/Ollama không bị restart.
- API health/ready và Web HTTP200; worker lease healthy. Docker DB/Redis healthy.
- Full live OpenAPI khớp 243 operation; ba artifact M2 cũ replay3/3 đạt.
- Authenticated planning status: enabled=true, execution_enabled=false,
  model_calls=false. Active runs0, saved business plans0; không tạo fixture
  trong database local. Revision0037, không có migration mới/sửa tay database.
- Meta disabled/write disabled; App/secret còn cấu hình, connection/report0,
  không gọi dịch vụ bên ngoài. M3 live chưa đạt.

Không đánh dấu P6/P6.2 hoặc production hoàn tất. Bước tiếp theo là thiết kế
và triển khai P6.2 có xác nhận riêng; không tự mở workflow runner.

## Giới hạn

Xem [ADR](ADR-P61-WORKFLOW-PLANNING.vi.md). Model chỉ pin name/config, không
weights; evidence chỉ là kỳ vọng. Không có attempt, execution, timer hoặc
cancel propagation. M3 real-data, external MCP và reboot/VPS acceptance vẫn
chưa đạt. Snapshot input không được chứa secret. Nếu trình duyệt mất phản hồi
khi lưu, retry API phải dùng cùng request key; chủ động tạo preview mới là một
yêu cầu mới, không phải replay của yêu cầu trước.
