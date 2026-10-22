# Baseline hệ thống PAO — 29/09/2026

## Kết luận

**Giai đoạn 1 đạt.** PAO có thể khởi động lại từ mã nguồn và dữ liệu hiện có mà không sửa tay database. Web, API, PostgreSQL, Redis, SearXNG, Temporal, Ollama, ARQ worker, Temporal worker và Telegram bridge đang hoạt động trên máy local.

Các khóa an toàn vẫn giữ nguyên: Meta provider write tắt, global autopilot tắt và không có provider write nào được thực hiện trong quá trình kiểm tra.

## Phiên bản đã kiểm chứng

| Thành phần | Phiên bản |
|---|---|
| Windows | Windows 10 Pro 25H2, build `26200.9550` |
| Docker Desktop | `4.74.0.227015` |
| Docker Engine | client/server `29.4.3` |
| Docker Compose | `v5.1.3` |
| Node.js | `v24.13.0` |
| npm | `11.6.2` |
| Python | `3.12.14` |
| PostgreSQL | `17.11`, image `pgvector/pgvector:pg17` |
| Redis | `7.4.11`, image `redis:7.4-alpine` |
| Temporal | `1.30.6` |
| Ollama | `0.34.0` |
| LLM kiểm thử | `qwen3:4b-instruct-2507-q4_K_M` |
| Embedding model | `embeddinggemma:300m`, 768 chiều |

## Kết quả theo điều kiện hoàn thành

| Điều kiện | Kết quả | Bằng chứng |
|---|---:|---|
| API trả HTTP 200 | Đạt | `/health` và `/ready` đều 200 |
| Web trả HTTP 200 | Đạt | `http://127.0.0.1:3100/` trả 200; toàn bộ asset trả 200 |
| Database ở revision `0020` | Đạt | Alembic `0020 (head)`, 61 bảng public |
| Backend regression 100% | Đạt | `173 passed in 126.55s` trên `pao_test`; Alembic check không phát hiện migration thiếu |
| Runtime/SSE 8/8 | Đạt | 8 pass, 0 fail |
| Production frontend build | Đạt | Next.js 15.3.8 compile thành công trong 22 giây; 17 static/dynamic page entries |
| Browser acceptance | Đạt | 12/12 route PAO pass |
| Không sửa tay database | Đạt | Migration idempotent; không chạy SQL sửa dữ liệu production |
| Full local system verifier | Đạt | 97 OpenAPI paths; 6/6 process nền sống; Telegram, Voice và Temporal ready |

## Trạng thái runtime

- Web: `127.0.0.1:3100`
- FastAPI: `127.0.0.1:8000`
- PostgreSQL: `127.0.0.1:5432`, healthy
- Redis: `127.0.0.1:6379`, healthy
- Temporal: `127.0.0.1:7233`, healthy; namespace `default`; task queue `pao-automation`
- SearXNG: `127.0.0.1:8888`, HTTP 200
- Ollama: `127.0.0.1:11434`, HTTP 200
- Process nền: Ollama, API, ARQ worker, Temporal worker, Next.js và Telegram bridge đều sống theo PID + start time.
- Docker API vượt qua ba probe liên tiếp; bốn container hạ tầng phản hồi ổn định.

## Kiểm tra chức năng

### Login và API có xác thực

- Login sai bị từ chối HTTP 401.
- Bearer token hợp lệ truy cập được `/v1/me` và workspace.
- Bộ backend regression đã kiểm tra cả login đúng và sai trên database test.

### Chat, session, task và memory

- API production đọc được 2 session; session mới nhất có 4 message.
- API production đọc được 1 task.
- Tài khoản production hiện có 0 memory; đây là trạng thái dữ liệu hiện tại, không phải lỗi endpoint.
- Acceptance riêng trên `pao_test` đã chạy Ollama thật: chat hoàn thành, trích xuất 1 fact, tạo embedding 768 chiều, gọi lại đúng dữ kiện “Malaysia” ở session khác và loại trừ memory của brand khác.
- Thời gian acceptance chat/memory CPU: 201,1 giây.

### Telegram

- Bridge ở chế độ polling đã gọi `getWebhookInfo` thành công và ghi `Telegram bridge ready`.
- 1 private peer được phép; 0 delivery issue.
- Không gửi tin nhắn thử hoặc báo cáo ra Telegram trong baseline này.

### Frontend

- Production build hoàn tất sau khi cache `.pao-next` cũ được chuyển vào `.runtime/pao-next-backup-20260929-195122`.
- Browser acceptance đi qua Orb, shared shell, Dashboard, PAO AI, Tasks, Ads, CRM, Creative, Analytics, Automation, Knowledge và Settings.
- Test acceptance được cập nhật để chờ dữ liệu bất đồng bộ thay vì đếm DOM quá sớm.
- Mock Settings được đồng bộ với tab mới `Năng lực Javis` và `Cloud Models & Voice`.

## Phục hồi Docker không phá hủy dữ liệu

Docker Desktop ban đầu crash vì các AF_UNIX socket 0 byte cũ. Quy trình phục hồi chỉ sao lưu/đổi tên thư mục và socket runtime; không factory reset, không xóa image, container, volume hoặc VHDX dữ liệu.

Các bản sao lưu chính:

- `<DOCKER_RUNTIME_BACKUP_DIR>\run.pao-backup-20260929-195908`
- `<DOCKER_RUNTIME_BACKUP_DIR>\docker-secrets-engine.pao-backup-20260929-200125`
- `engine.sock.pao-backup-20260929-2003`
- `dockerInference.pao-backup-20260929-2005`

Sau phục hồi, Docker Engine client/server đều là 29.4.3; PostgreSQL, Redis và Temporal đều healthy.

## Backup database trước migration

- File: `<PAO_BACKUP_DIR>\pao-pre-stage1-20260929-200909.dump`
- Kích thước: 309.254 byte
- SHA-256: `FEF9957E0822AED57C74DF8F681BAC18134C1B03ACB845367530F16F2B83EA52`
- Revision trước và sau migration: `0020 (head)`

## Rủi ro còn lại

1. Docker Desktop 4.74 có thể tái gặp socket AF_UNIX cũ sau khi bị shutdown cưỡng bức. Luôn thoát Docker sạch; không dùng factory reset.
2. Cache `.pao-next` hỏng có thể làm `next build` dùng CPU vô hạn trước bước compile. Cách an toàn là chuyển cache cũ sang `.runtime` rồi build sạch.
3. Ollama chạy CPU ổn định nhưng chậm; bài chat/memory hai lượt mất khoảng 201 giây.
4. Các process ứng dụng là process nền local, chưa phải Windows service và chưa tự khởi động sau reboot.
5. Tên logical database còn là `apex` từ lịch sử dự án; không ảnh hưởng vận hành nhưng nên đổi có migration/backup riêng ở giai đoạn sau.

## Lệnh kiểm chứng lại

```powershell
cd <PAO_PROJECT_DIR>
.\scripts\start_local.ps1
.\.venv\Scripts\python.exe scripts\test_backend.py
npm run test:runtime
npm run build
npm run test:frontend
.\.venv\Scripts\python.exe scripts\verify_system_local.py
.\.venv\Scripts\python.exe scripts\verify_live_readonly.py
```

Không chạy `verify_memory_local.py` thường xuyên: đây là acceptance Ollama thật, dùng CPU lâu và tạo dữ liệu tổng hợp trong `pao_test`.
