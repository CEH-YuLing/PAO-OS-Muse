> Hồ sơ Phase 0/1 trước khi đổi tên sang PAO. Tên APEX và đường dẫn dưới đây phản ánh thời điểm triển khai; xem [đổi tên PAO](REBRAND-PAO.md) và [hướng dẫn hiện tại](LOCAL-DEVELOPMENT.md).

# Phase 1 — Kết quả nghiệm thu

Ngày chốt: 11/09/2026. **Đạt luồng acceptance local của mục 153 bằng CPU. Chưa triển khai Phase 2+.** Không đồng nghĩa production-ready hoặc đã đạt tăng tốc GPU.

## Đối chiếu lộ trình

Phase 0 đã hoàn thành trước khi thay UI: clone Git thật, nhánh `architecture/phase-0-1`, build upstream pass, chạy và kiểm tra browser, sơ đồ component. Xem PHASE-0-PLAN.md và PHASE-0-RESULT.md.

Phase 1 đã xây FastAPI, PostgreSQL, Redis/ARQ, JWT, workspace membership, sessions/messages/runs, migration, SSE replay, một LLM Gateway Ollama và một chief_of_staff. Hook/Orb là cầu nối tối thiểu bắt buộc ở mục 153 của master, không phải triển khai toàn bộ Phase 2.

Kế hoạch cũ chỉ là tài liệu, chưa có backend. Các điểm đã điều chỉnh theo master: prefix `/v1`, sessions thay conversations, Redis/ARQ thay PostgreSQL queue, JWT và monorepo `apps/*`. Brand chưa có trong Phase 1; cần thêm brand entity/FK trước mọi dữ liệu nhiều thương hiệu. Chưa có Ads, tools, memory, Telegram, voice, delegation hoặc autopilot.

## Bằng chứng acceptance thật

Run `74338025-0cc6-44e3-bcb5-a9b8e381f4ef` được gửi từ UI, xử lý bởi process worker thật, gọi `qwen3:4b-instruct-2507-q4_K_M` trên Ollama local CPU, kết thúc completed.

- Backend ghi 53 `response.delta`; sequence liên tục, có run.started/core.processing/agent.started/agent.completed/run.completed.
- Câu trả lời hiển thị trên UI; Orb nhận state từ runtime và trở lại idle khi kết thúc.
- Mở lại trang, đăng nhập lại, chọn hội thoại: câu trả lời vẫn tồn tại. Đã kiểm tra cả sau khi khởi động lại các process; không dựa vào React state cũ.
- Nội dung assistant message trong PostgreSQL bằng chính xác response của run.
- Run trước bị gián đoạn `f3722218-fbbd-4d4d-8c00-ec1c01b0381a` được dispatcher chuyển failed/worker_lost sau restart, không tự sinh lại câu trả lời.
- Run nghiệm thu: 149 prompt tokens, 54 output tokens, khoảng 29,84 giây tính từ worker bắt đầu tới kết thúc. Đây là một mẫu trên máy hiện tại, chưa phải benchmark tải nhiều người dùng.

Số liệu máy đọc được: [phase-1-evidence.json](phase-1-evidence.json). Không ghi private reasoning vào events. Kiểm thử gateway xác nhận bỏ trường thinking.

## Build và test

| Kiểm tra | Kết quả |
|---|---|
| Build UI upstream Phase 0 | PASS |
| Build Next.js/TypeScript sau tích hợp và sửa nhãn running | PASS |
| Backend pytest, PostgreSQL + Redis thật, provider giả lập trong tests | 11 PASS |
| Decoder SSE: UTF-8 chia byte, CRLF, heartbeat, JSON lỗi | 2 PASS |
| Alembic upgrade development | PASS |
| Downgrade/upgrade database riêng apex_test + alembic check | PASS, không schema drift |
| OpenAPI → TypeScript | PASS |
| Compose PostgreSQL/Redis + healthchecks | PASS |
| Image API Linux từ requirements.lock | Built |
| Browser E2E với model thật | PASS trên CPU |
| GPU CUDA/Vulkan | CHƯA ĐẠT |
| Toàn bộ app profile trong container | Chưa nghiệm thu end-to-end; native API/worker/web là cấu hình đã dùng |

Tests bao phủ auth/isolation, role viewer, idempotency/conflicting requests, duplicate worker delivery, persisted SSE/replay, cancel queued/running và partial response, provider failure, outbox recovery, stale worker, timeout, thu hồi quyền user trước execution, contract/readiness. Không dùng SQLite thay Postgres để báo integration pass.

## File thay đổi và migrations

- Root npm workspace, pyproject/requirements lock, .gitignore/.dockerignore.
- `apps/web`: UI gốc được di chuyển; thêm ApexConsole, CSS, useApexRuntime, decoder SSE; nối state/trace vào ApexWorld, giữ visual gốc.
- `apps/api/apex`: config, SQLAlchemy models, auth, routes, gateway, runtime/worker, bootstrap.
- `apps/api/migrations/versions/0001_foundation.py`: users, workspaces, workspace_members, sessions, messages, runs, run_events, agent_runs; constraints và indexes.
- `apps/api/tests`, `apps/worker/README.md`, `packages/contracts`, `packages/agent-config/chief_of_staff.json`.
- `infra/compose.yaml`, API/web Dockerfiles; `scripts` cho config, contracts, tests và khởi động local; docs kế hoạch/kết quả/runbook.

Các API và biến môi trường được mô tả trong PHASE-1-PLAN.md, LOCAL-DEVELOPMENT.md và `.env.example`. Secret thật chỉ ở `.env` được ignore. Giữ nguyên LICENSE và CREDITS. Chưa commit/push/merge các thay đổi.

## Khởi động và kiểm tra thủ công

Trên máy đã setup, từ `F:/Apex/apex`, chạy `./scripts/start_local.ps1`. Script chạy migration và khởi động nền Ollama CPU, API, worker, web. Mở `http://127.0.0.1:3100`. Logs/PID tại `.runtime`; đây không phải Windows service tự chạy sau reboot. Docker Desktop cần đang hoạt động.

Đăng nhập, chọn hoặc tạo hội thoại, gửi câu ngắn, xem trace; reload và chọn lại để kiểm tra dữ liệu. Hủy một yêu cầu đang chạy để kiểm tra cancelled. Hướng dẫn đầy đủ và bootstrap tài khoản tại LOCAL-DEVELOPMENT.md. Tài khoản local đã tạo trong quá trình nghiệm thu vẫn được giữ; không thay mật khẩu của người dùng trong bước bàn giao.

## Điểm còn hạn chế

- GPU: CUDA nhận GTX 1060 nhưng lỗi PTX/toolchain; Vulkan đã nhận GPU nhưng chưa hoàn tất nghiệm thu. CPU chạy thật thành công. Không nâng driver hệ thống. Lần nạp CPU đầu khoảng 71 giây, nên có độ trễ khi model chưa ở RAM.
- Docker Desktop từng lỗi socket sau lần dừng không sạch; đã sao lưu riêng socket runtime, không reset volumes. Cách chẩn đoán và nguồn đối chiếu ở ENVIRONMENT-NOTES.md.
- Chỉ một worker, một Chief, session riêng từng user. JWT in-memory: reload cần login; chưa refresh/revoke từng token hay UI quản trị user.
- Chưa load test, chưa kiểm định chất lượng model hoặc bảo mật public deployment. UI/voice không thực thi hành động ngoài hệ thống.
- Conversation listing giới hạn 100 mục, lịch sử tải 100 message gần nhất; retention/backup tự động chưa có. Chưa tạo brand isolation giả khi chưa có brand schema.

Lượt này dừng tại Phase 1 theo yêu cầu. Phase 2 cần kế hoạch riêng và giữ các giới hạn nêu trên rõ ràng.
