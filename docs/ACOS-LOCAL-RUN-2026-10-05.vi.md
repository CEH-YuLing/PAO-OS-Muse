# Chạy thử PAO-ACOS local — 05/10/2026

Web: http://127.0.0.1:3200
API: http://127.0.0.1:8100

Tài khoản demo: `demo@pao.local`, workspace `PAO-ACOS Demo`.
Mật khẩu không ghi vào tài liệu dự án.

Database riêng `pao_acos_local` nằm trong Docker project `pao-acos-local`,
PostgreSQL cổng 15432 và Redis cổng 16379. Mật khẩu dịch vụ/JWT được tạo mới
trong `.env` bị Git ignore. Meta write, Telegram, Google Ads, Autopilot,
Temporal và Voice đang tắt trong môi trường này.

## Kết quả hôm nay

- Docker Engine đã phục hồi và PostgreSQL/Redis riêng đều healthy.
- Web `/` và `/dashboard`: HTTP 200.
- API `/health` và `/ready`: HTTP 200.
- Đăng nhập thông qua frontend proxy: đạt.
- Tạo hội thoại: đạt.
- Tạo task và đọc lại task đã lưu: đạt.
- API và ARQ worker chạy nền.
- Ollama nhận model `qwen3:4b-instruct-2507-q4_K_M`.
- Lượt chat thực tế qua frontend proxy, API, worker và Ollama: completed sau
  67 giây, trả lời `Chào bạn!`, không có error code. Memory tắt trong hội thoại
  thử này; SSE chưa được kiểm tra trực tiếp trong lượt chạy hôm nay.

## Khởi động lại

Môi trường Python riêng nằm trong `.venv` của PAO-ACOS, cài từ
`requirements.lock`; package PAO cài editable từ thư mục dự án này.
Python nền vẫn là Python 3.12 đã cài trên máy. Khi chuyển sang máy khác,
cài Python và tạo lại `.venv` từ lockfile, không sao chép virtual environment.

```powershell
./scripts/start_acos_local.ps1
```

Frontend chạy Next.js dev. Đây là phiên chạy thử local, chưa phải deploy
production. Secret, cache, log, model và dữ liệu demo đã được tạo để vận hành;
thư mục hiện không còn là bản source-only để gửi trực tiếp. Khi đóng gói lại,
loại `.env`, `.runtime`, `node_modules` và các build/cache theo manifest.

## Phục hồi Docker

Docker Desktop crash lần lượt ở `dockerInference` và `engine.sock`. Các thư mục
socket runtime lỗi đã được đổi tên giữ lại dưới dạng backup với hậu tố
`acos-backup-20261005` và `acos-backup-20261005-2`; không xóa image/container/
volume cũ. Windows chặn cổng 55432 nên môi trường thử dùng 15432/16379 đã kiểm
tra khả năng bind trước khi khởi động.

## Ollama

Chỉ model Qwen được sao chép từ model store có sẵn sang `.runtime/models`;
embedding model chưa sao chép. Ollama 0.34.0 và các thư viện CPU cùng giấy phép
được đặt riêng trong `.runtime/ollama` của PAO-ACOS. Bộ khởi động local tự mở
Ollama với model store `.runtime/models`, CPU, cổng 11434 và cloud tắt.
Memory và các tích hợp chưa được nghiệm thu trong lượt smoke test này.

## Dừng hoặc chuyển môi trường

Đợi chat đang chạy hoàn tất rồi kiểm tra trạng thái:

```powershell
./.venv/Scripts/python.exe scripts/check_acos_idle.py
./scripts/stop_acos_local.ps1
```

Lệnh dừng chỉ tác động process có PID và thời điểm khởi động trùng hồ sơ ACOS;
dừng cả process con. Docker containers và volumes vẫn giữ nguyên.
