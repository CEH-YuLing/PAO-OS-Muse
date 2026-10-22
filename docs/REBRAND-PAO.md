# Đổi tên dự án sang PAO

Bắt đầu 11/09/2026, hoàn tất kiểm chứng ngày 12/09/2026. Phạm vi chức năng giữ ở Phase 1.

## Tên hiện tại

| Thành phần | Tên mới |
| --- | --- |
| Sản phẩm, metadata, Orb và nhãn truy cập | PAO |
| NPM root / frontend | pao-local / pao-ui |
| Python distribution / import | pao-backend / pao |
| API / worker entrypoint | pao.main:app / pao.runtime.WorkerSettings |
| Docker Compose project | pao |
| JWT issuer / audience | pao-local / pao-api |
| Biến tùy chọn | PAO_ROOT, PAO_API_URL, PAO_TEST_DATABASE_URL |
| Database kiểm thử riêng | pao_test |
| Chief of Staff prompt | PAO, phiên bản 1.0.1 |

Component, hook, import, CSS class, DOM selector và animation đã chuyển sang `Pao…` / `pao-…`. `/about` giới thiệu PAO và ghi công nguồn UI gốc; bỏ các liên kết “Follow us” tới tài khoản tác giả gốc.

## Bảo toàn dữ liệu hiện có

Trước chuyển đổi đã dừng API/worker/web do script dự án khởi động, sao lưu PostgreSQL tại `.runtime/pre-pao.dump`, rồi thay container mà không xóa volume.

- Volume vật lý cũ `apex_postgres-data`, `apex_redis-data` được gắn vào container `pao-postgres-1`, `pao-redis-1` bằng `PAO_POSTGRES_VOLUME`, `PAO_REDIS_VOLUME`, `PAO_EXTERNAL_STORAGE=true` trong `.env` được gitignore.
- PostgreSQL role/database `apex` được giữ qua `POSTGRES_USER`, `POSTGRES_DB` và `DATABASE_URL`. Cài mới mặc định dùng `pao`.
- Workspace mặc định `APEX Local` đổi nhãn thành `PAO Local`. Nội dung hội thoại, ID, người dùng, mật khẩu và lịch sử run giữ nguyên.
- Tài khoản đã có `owner@apex.local` vẫn dùng để đăng nhập; email là định danh người dùng, không tự đổi khi đổi thương hiệu. JWT cũ không còn hợp lệ sau đổi issuer/audience: đăng nhập lại.
- Repo vật lý vẫn ở `F:/Apex/apex` để giữ đường dẫn workspace, virtualenv và runtime hiện có. Tên này là đường dẫn kỹ thuật, không phải thương hiệu sản phẩm.

Không bỏ các ánh xạ storage ở máy đang dùng: Compose sẽ chọn volume mặc định mới và trông như mất dữ liệu. Không chạy `down -v` trên dữ liệu cần giữ. Cài mới không cần các giá trị legacy ở trên.

## Nguồn gốc và hồ sơ lịch sử

LICENSE giữ nguyên toàn văn MIT và copyright Ruben Mouradian. APEX-UI trong CREDITS, README và trang About là tên nguồn gốc thực tế, không được sửa thành tên tác giả/dự án mới. Git remote vẫn trỏ tới repository gốc; chưa có repository PAO được cung cấp để đổi remote hoặc push.

Các PHASE-*.md, bằng chứng kiểm thử cũ, archive UI và nghiên cứu tại thư mục cha được giữ như hồ sơ trước đổi tên. Không sửa kết quả lịch sử hay nội dung người dùng để thay tên. Hướng dẫn chạy hiện tại nằm ở LOCAL-DEVELOPMENT.md.

## Kiểm chứng ngày 12/09/2026

- 11 kiểm thử backend đạt; migration downgrade/upgrade/check chạy trên `pao_test` riêng. Pytest có cảnh báo không ghi được cache cũ, không ảnh hưởng kết quả test.
- 2 kiểm thử SSE đạt, gồm UTF-8 tiếng Việt chia giữa các chunk và dữ liệu event lỗi.
- Quét mã nguồn hoạt động: APEX chỉ còn ở phần ghi công nguồn gốc trong trang About.
- Output Next.js chuyển sang `.pao-next` vì cache `.next` cũ có lỗi quyền NTFS. TypeScript và Docker ignore đã cập nhật đồng bộ. Cache cũ và `.next-pre-pao` là dữ liệu sinh tự động, được loại khỏi Git, Docker context và typecheck.
- Docker Desktop tái gặp lỗi ba socket 0 byte. Đã giữ bản dự phòng `.pao-backup-20260912`, khởi động lại daemon thành công, không reset storage.
- Production build frontend đạt, gồm typecheck và trang `/about`; image `pao-api` build thành công.
- Khởi động lại API, worker, web và Ollama CPU. `/health`, `/ready`, trang chính và `/about` đều HTTP 200; tiêu đề frontend và OpenAPI là PAO.
- Sau kiểm thử/khởi động lại, dữ liệu ứng dụng vẫn đủ: 1 tài khoản, 2 hội thoại, 17 tin nhắn, 9 agent run; workspace mặc định là `PAO Local`.
- Kiểm tra nội dung HTTP trang chính không còn APEX; phần About giữ nguồn gốc và copyright. Không chạy thêm inference thực tế ở lượt đổi tên; luồng backend được kiểm thử bằng bộ integration và gateway hiện có.
