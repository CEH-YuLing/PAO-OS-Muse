> Hồ sơ Phase 0/1 trước khi đổi tên sang PAO. Tên APEX và đường dẫn dưới đây phản ánh thời điểm triển khai; xem [đổi tên PAO](REBRAND-PAO.md) và [hướng dẫn hiện tại](LOCAL-DEVELOPMENT.md).

# Phase 0 — Kết quả

Ngày 10/09/2026. PASS, đủ điều kiện bắt đầu Phase 1.

- Clone Git thật, upstream `f9fd176833a39b4634bad23cdc898fac4e0ab6a2`, nhánh `architecture/phase-0-1`.
- Node 24.13.0, npm 11.6.2; `npm ci --no-audit --no-fund` theo lockfile.
- `npm run build`: PASS, biên dịch, kiểm tra TypeScript, sinh trang Next.js 15.3.8.
- `npm run start -- --hostname 127.0.0.1 --port 3100`: Ready.
- Browser mở trang thành công, thấy 18 agent, nút Orb, overview và liên kết upstream; click Orb nhận được tương tác. Chưa đánh giá hiệu năng GPU.
- Không sửa UI, database hoặc API trong Phase 0. Sơ đồ component và đối chiếu lộ trình nằm trong PHASE-0-PLAN.md.

Tài liệu nghiên cứu ở `F:/Apex/docs` là kế hoạch lịch sử, không phải các chức năng đã xây. Phase trong master specification hiện hành được ưu tiên.

Chuyển Phase 1: Docker CLI có nhưng daemon chưa chạy, Ollama chưa cài; cần kiểm chứng dịch vụ thật riêng với các kiểm thử dùng provider giả lập.
