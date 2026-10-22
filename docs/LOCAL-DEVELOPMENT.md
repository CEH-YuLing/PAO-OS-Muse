# Chạy PAO local — Phase 1–18

Hướng dẫn này áp dụng cho bản local đến migration `0017`: Telegram, Tool Gateway/SearXNG, Ads read-only/Copilot, Temporal và Voice. Tích hợp quảng cáo cài mới mặc định tắt; live Meta write và Autopilot phải giữ tắt cho đến khi nghiệm thu account thật.

Mã nguồn đã clone ở `F:/Apex/apex`; UI archive và tài liệu nghiên cứu cũ ở thư mục cha chỉ để đối chiếu. Chạy mọi lệnh dưới đây từ repository root. Không đưa `.env`, `.runtime`, `.venv` lên Git.

## 1. Cấu hình

Python 3.12, Node 24, Docker Compose, Ollama. Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock
.\.venv\Scripts\python.exe -m pip install --no-deps -e .
npm ci
.\.venv\Scripts\python.exe scripts/init_local.py
```

Script chỉ tạo `.env` nếu chưa tồn tại, sinh riêng password PostgreSQL, Redis và JWT secret. `.env.example` mô tả các biến; không dùng nguyên giá trị mẫu. Khi dùng Python đi kèm Codex, thay `python` đầu tiên bằng đường dẫn executable tương ứng. Không có API key cloud bắt buộc.

## 2. PostgreSQL và Redis

```powershell
docker compose --env-file .env -f infra/compose.yaml up -d postgres redis
.\.venv\Scripts\alembic.exe upgrade head
.\.venv\Scripts\alembic.exe current
.\.venv\Scripts\python.exe -m pao.bootstrap --email owner@example.com --workspace Personal
```

CLI hỏi mật khẩu ẩn (12–256 ký tự). Email trên là ví dụ; chọn tài khoản của bạn. Không có đăng ký công khai, mật khẩu mặc định hay tài khoản admin hard-code. Mỗi lần bootstrap tạo user và workspace riêng. Quản trị/invite thành viên qua UI chưa thuộc Phase 1.

Database dùng volume riêng, chỉ publish `127.0.0.1:5432`, Redis `127.0.0.1:6379`. Không chạy `down -v` nếu cần giữ dữ liệu. Migration 0002 tạo extension pgvector và schema Memory. Kéo `embeddinggemma:300m` bằng Ollama đang dùng; xem [Memory](MEMORY.md) trước khi upgrade cài đặt cũ.

Máy chuyển từ APEX sang PAO dùng ánh xạ storage trong `.env`; giữ nguyên các biến này. Lệnh quản trị PostgreSQL trên máy đó dùng `-U apex` thay cho `-U pao`, database ứng dụng vẫn là `apex`. Database kiểm thử mới là `pao_test`. Cài mới dùng tên `pao` hoàn toàn. Xem [ghi chép chuyển đổi](REBRAND-PAO.md).

## 3. Mô hình local

```powershell
.\scripts\start_ollama.ps1 -Engine cpu
```

Nếu đã cài Ollama thì dùng `ollama` trên PATH; không khởi động server thứ hai trên cùng cổng. Ở terminal khác: `ollama pull qwen3:4b-instruct-2507-q4_K_M` (hoặc executable trong `.runtime/ollama`). Dùng rõ tag Instruct vì `qwen3:4b` đã trỏ tới bản Thinking ở lần kiểm tra này. Bản standalone chính thức được lấy từ [Ollama releases](https://github.com/ollama/ollama/releases); kiểm SHA-256 từ release trước khi giải nén. Runtime tạo khóa tại hồ sơ người dùng; model đặt trong workspace như cấu hình trên. [Tài liệu Windows](https://docs.ollama.com/windows).

CPU là profile đã sinh được câu trả lời trên máy hiện tại. `-Engine vulkan` chỉ dành cho kiểm tra tương thích, chưa đạt acceptance GPU; lần nạp GPU trước bị gián đoạn. Sau khi nâng driver/phần cứng, dùng `-Engine auto` để Ollama tự chọn CUDA. [Hỗ trợ phần cứng Ollama](https://docs.ollama.com/gpu) yêu cầu driver 570+ cho NVIDIA compute capability 5.0–6.2; GTX 1060 là 6.1. Không thay driver hệ thống trong lượt triển khai này.

Mặc định: context 4096, output 512, không thinking, một job/worker, một model loaded. Input tối đa 2000 ký tự và history giới hạn 4000 ký tự/12 message; Ollama giới hạn context thực tế. Timeout 180 giây. Đổi `OLLAMA_MODEL`, `CONTEXT_TOKENS`, `OUTPUT_TOKENS`, `RUN_TIMEOUT_SECONDS` trong `.env` khi nâng phần cứng rồi restart API/worker.

## 4. Chạy ứng dụng

Máy đã setup có thể chạy `./scripts/start_local.ps1` từ root: khởi động nền các process, mặc định CPU và cổng web 3100, logs/PID ở `.runtime`. Docker Desktop phải hoạt động; script không tự reset Docker. Khi `TEMPORAL_ENABLED=true`, script khởi động schema/server/namespace trước Temporal worker. Sau reboot chạy lại script. Đây chưa phải Windows service. Script tái dùng PID đã ghi nếu process đó vẫn còn đúng thời điểm khởi động.

Ba terminal riêng, đều ở root:

```powershell
.\.venv\Scripts\uvicorn.exe pao.main:app --host 127.0.0.1 --port 8000
.\.venv\Scripts\arq.exe pao.runtime.WorkerSettings
.\.venv\Scripts\python.exe scripts/temporal_worker.py
npm run dev -- --hostname 127.0.0.1 --port 3000
```

Hoặc `npm run build` rồi `npm run start -- --hostname 127.0.0.1 --port 3000`. Mở `http://127.0.0.1:3000`; API docs `http://127.0.0.1:8000/docs`. Next proxy `/v1` đến API; Next không gọi model hay giữ business data. Chỉ chạy một worker replica. Ollama chạy native tận dụng GPU, không đặt GPU trong Docker mặc định.

Container hoá app là lựa chọn khác: `docker compose --env-file .env -f infra/compose.yaml --profile app up --build -d`. Migration là service one-shot; web/API/worker dùng đúng cùng code. Với Ollama trên host, worker container cần truy cập `host.docker.internal:11434`; cấu hình mạng Ollama phù hợp trước khi dùng profile này. Trên Linux, firewall giới hạn host gateway; không mở Ollama ra Internet. Native mode ở trên phù hợp máy hiện tại và tránh yêu cầu mở địa chỉ bind của Ollama.

## 5. Kiểm chứng và hợp đồng

```powershell
.\.venv\Scripts\python.exe scripts/export_openapi.py
npm run contracts
npm run build
npm run test:runtime
npm run test:frontend
.\.venv\Scripts\python.exe scripts/verify_system_local.py
```

TypeScript trong `packages/contracts/schema.d.ts` sinh từ OpenAPI của FastAPI, không sửa bằng tay. Cài bộ test bằng `pip install -e ".[test]"`. Tạo database RIÊNG `pao_test` cùng PostgreSQL bằng `docker compose --env-file .env -f infra/compose.yaml exec -T postgres createdb -U pao pao_test` (chỉ lần đầu); chạy `.venv/Scripts/python.exe scripts/test_backend.py`. Script tự đặt URL test và Redis DB 15. Thêm `--roundtrip` để kiểm thử downgrade/upgrade, xóa schema **chỉ trong pao_test**. Conftest từ chối mọi tên DB khác và TRUNCATE dữ liệu chỉ trong pao_test. Không chạy worker development vào queue test.

## Acceptance thủ công

1. `/health` trả ok, `/ready` trả ready; Ollama `/api/tags` có model.
2. Đăng nhập, tạo hội thoại, gửi yêu cầu ngắn. Thấy run → agent → delta → completed, Orb thinking rồi speaking rồi idle.
3. Reload, đăng nhập lại, chọn hội thoại: cả user message và câu trả lời vẫn tồn tại. JWT chỉ lưu trong memory nên refresh cần login lại.
4. Gửi yêu cầu dài, hủy: run cancelled, partial answer được ghi rõ trạng thái. Ngắt kết nối rồi bấm kết nối lại: replay không nhân đôi output.
5. Dừng Ollama: run kết thúc failed với thông báo; không fallback cloud. Dừng worker khi run running: sau restart và timeout, run chuyển worker_lost; queued run được dispatcher phục hồi.

## Ranh giới hiện tại

Chief điều phối tối đa hai bước Researcher/Editor/Marketing rồi tổng hợp; Memory, Tool Gateway, Telegram, Ads read-only/Copilot, Temporal và Voice đã có. Email/calendar vẫn chỉ mô phỏng; Meta/Google cần account thật để nghiệm thu, TikTok chưa triển khai. Hội thoại riêng theo user/workspace; Memory thêm phạm vi brand bằng FK, chưa chia sẻ giữa thành viên. Role viewer chỉ đọc. JWT không có refresh token/logout toàn thiết bị; logout hiện tại xóa token trên trình duyệt. Muốn vô hiệu ngay một tài khoản, operator đổi `users.active=false` bằng công cụ quản trị DB. API và stream đều kiểm tra active/membership.

Không public deployment Phase 1. Muốn dùng qua LAN cần HTTPS/reverse proxy, giới hạn origin/host và review bảo mật trước. Backup PostgreSQL/retention, user management UI, pagination sâu, observability tập trung và durable workflow nhiều bước nằm ngoài acceptance này.
