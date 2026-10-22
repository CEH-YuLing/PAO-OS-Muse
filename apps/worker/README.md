# Worker

Chạy từ repository root: `.venv/Scripts/arq.exe pao.runtime.WorkerSettings` (Linux: `.venv/bin/arq`).

Entrypoint ARQ nằm cùng Python package với domain tại `apps/api/pao/runtime.py` để không sao chép schema/config. Đây là process riêng với API; không có HTTP server trong worker. `max_jobs=1`, chỉ một worker replica cho Phase 1. PostgreSQL giữ run và sự kiện; Redis giao việc. Dispatcher mỗi 10 giây phục hồi queued run; stale running run kết thúc `worker_lost`, không tự phát lại câu trả lời.
