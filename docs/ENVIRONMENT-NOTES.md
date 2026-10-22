# Môi trường kiểm chứng ngày 10/09/2026

Cập nhật 11/09: Docker lỗi socket tái phát sau phiên bị dừng; xử lý cùng cách, giữ nguyên volume và kiểm tra dữ liệu còn nguyên. Cập nhật 15/09: lỗi lặp ở `dockerInference`, sau đó `engine.sock`; đã dừng riêng Docker Desktop, đổi tên ba socket IPC 0 byte sang `.pao-backup-20260915*`, khởi động lại và xác nhận daemon 29.4.3 cùng PostgreSQL/Redis healthy. Không reset Docker hoặc xóa volume. CPU đã hoàn tất luồng thực tế; GPU không được đánh dấu pass. Xem PHASE-1-RESULT.md. `scripts/start_local.ps1` khởi động process nền riêng, tránh phụ thuộc vòng đời phiên công cụ.

## Docker Desktop

CLI 29.4.3, Desktop 4.74.0. Khởi động lỗi lần lượt tại các AF_UNIX socket 0 byte:

- `%LOCALAPPDATA%/Docker/run/dockerInference`
- `%LOCALAPPDATA%/docker-secrets-engine/engine.sock`
- `%LOCALAPPDATA%/Docker/run/userAnalyticsOtlpHttp.sock`

Windows trả `ERROR_CANT_ACCESS_FILE`; WSL vẫn chạy. Đã dừng tiến trình Docker lỗi, đổi tên riêng các socket sang `.apex-backup*` bằng WSL và khởi động lại. Không factory reset, không xóa image/volume hay dữ liệu secrets. Daemon trả 29.4.3; compose khi đó khởi tạo `apex-postgres-1`, `apex-redis-1` (nay chuyển sang `pao-*`, xem REBRAND-PAO.md). Các bản dự phòng 0 byte giữ nguyên ở vị trí cũ.

Đây là loại lỗi đã được báo tại [Docker desktop-feedback #531](https://github.com/docker/desktop-feedback/issues/531). Thông tin issue chỉ để đối chiếu; không tự áp dụng thay đổi setting/driver hay hướng dẫn xóa dữ liệu trong issue. Nếu lỗi lặp sau shutdown cưỡng bức, kiểm tra đúng socket từ log trước khi xử lý. Ưu tiên thoát Docker bình thường.

## Ollama và GPU

Ollama standalone 0.34.0, archive Windows SHA-256 `a7dd1b174f39d3d1b8a25d4cbc86045d0e190b17187bfdcbe2f2ee3b5a11470e`, khớp `sha256sum.txt` trên release chính thức.

Runtime nhận CPU i3-10105F, RAM ~15.9GiB, NVIDIA GTX 1060 6GB, CUDA compute 6.1. Driver API báo CUDA 12.6; tải model qua CUDA lỗi `the provided PTX was compiled with an unsupported toolchain`. Không nâng driver tự động. Profile Vulkan: `CUDA_VISIBLE_DEVICES=-1`, `GGML_VK_VISIBLE_DEVICES=0`, `OLLAMA_VULKAN=1`.

Tag `qwen3:4b` tải model metadata `Qwen3 4B Thinking 2507`; chuyển rõ `qwen3:4b-instruct-2507-q4_K_M` theo yêu cầu trả lời trực tiếp. Model cũ vẫn ở cache, không có fallback sang nó. Chỉ model cấu hình được gọi; `OLLAMA_NO_CLOUD=1`.

Runtime/model/cache tại `.runtime` được gitignore; private key Ollama tự tạo ở `%USERPROFILE%/.ollama`. Không đưa các thư mục này lên Git. Kết quả inference thực tế xem PHASE-1-RESULT.md; nhận diện GPU riêng lẻ không được coi là acceptance sinh câu trả lời.
