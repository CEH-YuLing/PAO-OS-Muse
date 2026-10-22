> Hồ sơ Phase 0/1 trước khi đổi tên sang PAO. Tên APEX và đường dẫn dưới đây phản ánh thời điểm triển khai; xem [đổi tên PAO](REBRAND-PAO.md) và [hướng dẫn hiện tại](LOCAL-DEVELOPMENT.md).

# Phase 1 — Kế hoạch trước triển khai

## Phạm vi và thứ tự

1. Di chuyển UI đã qua baseline vào `apps/web`, giữ các visual component. Tạo npm workspace.
2. FastAPI tại `apps/api`, worker ARQ tại `apps/worker` dùng chung domain Python; cấu hình local tại `infra`. PostgreSQL là nguồn dữ liệu chính, Redis chỉ giao việc. Alembic quản lý schema.
3. Auth JWT, workspace membership, session riêng từng người; bootstrap user bằng CLI. Không có đăng ký công khai. Password Argon2, token ngắn hạn lưu trong memory trình duyệt, không localStorage. Request SSE dùng fetch với Authorization.
4. Sessions/messages/runs/events; tối đa một run hoạt động mỗi session. Run có request key chống gửi lặp. Worker một job một lúc cho máy 16GB/6GB VRAM. Recover queued jobs từ PostgreSQL; run mất worker được đánh failed thay vì tự lặp generation.
5. Gateway Ollama, một chief_of_staff với prompt có phiên bản; giới hạn input/history/context/output/time. Không tool/delegation/memory.
6. SSE lưu event trước khi phát, replay theo sequence; chỉ trạng thái tác vụ và output, không chain-of-thought. Hook `useApexRuntime` nối Orb/ReasoningWeb, hội thoại có thể tải lại từ DB. OpenAPI sinh TypeScript.
7. Kiểm thử auth/isolation/idempotency/replay/cancel/worker failure; build UI; kiểm chứng compose/migration và luồng Ollama thật nếu môi trường chạy được. Ghi rõ bằng chứng và điểm chưa đạt.

## File và dữ liệu

Thay đổi chính: root package/ignore; `apps/web` (UI cũ + hook/chat); `apps/api/apex` (config/db/models/auth/routes/gateway/runtime); `apps/api/migrations`; `apps/api/tests`; `apps/worker`; `packages/contracts`; `packages/agent-config`; `infra/compose.yaml`, Dockerfiles; runbook và kết quả trong docs.

Migration đầu: users, workspaces, workspace_members, sessions, messages, runs, run_events, agent_runs. workspace_id trên dữ liệu nghiệp vụ, session owner kiểm tra cùng membership. Brand chưa tồn tại ở Phase 1: không nhận brand_id giả định chưa thể validate; migration brand + FK sẽ bổ sung trước mọi dữ liệu đa thương hiệu. Đây là giảm phạm vi có chủ ý, không hứa brand isolation khi chưa có brand.

API: `/health`, `/ready`, `/v1/auth/token`, `/v1/me`, `/v1/sessions` (GET/POST), `/v1/sessions/{id}` (GET), `/v1/runs` (POST), `/v1/runs/{id}` (GET), `/v1/runs/{id}/events` (GET SSE), `/v1/runs/{id}/cancel` (POST). Không có API Ads hay quyền hành động bên ngoài.

## Quyết định / rủi ro

- JWT bearer in-memory giảm độ phức tạp cookie/CSRF; phải đăng nhập lại sau refresh. Chỉ bind localhost mặc định; truy cập LAN cần HTTPS và firewall theo runbook.
- Redis + ARQ thay queue PostgreSQL của kế hoạch cũ. DB giữ trạng thái và replay; không tuyên bố workflow engine lâu dài.
- Stream không tự retry inference sau lỗi. UI reconnect chỉ replay event; hủy giữ partial output có trạng thái rõ ràng.
- Windows Docker có thể phụ thuộc WSL/virtualization. Không dùng SQLite thay Postgres rồi đánh dấu integration đạt.
- Mặc định Qwen3 4B local, context 4096, output 512, concurrency 1; chất lượng và tốc độ cần đo trên GPU thực tế, không cam kết từ cấu hình giấy.
- Phần hook/Orb là cầu nối tối thiểu theo mục 153, không triển khai toàn bộ Phase 2. Chỉ qua phase kế tiếp khi acceptance hiện hành pass.
