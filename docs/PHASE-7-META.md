# Phase 7 — Meta chỉ đọc

Ngày cập nhật: 14/09/2026. Phạm vi theo mục 133 master spec: kết nối OAuth, tài khoản quảng cáo, campaigns, adsets, ads, Insights và đồng bộ lịch sử. Không triển khai thao tác ghi quảng cáo, warehouse chuẩn hóa hoặc báo cáo tự động của các phase tiếp theo.

## Đã triển khai trong mã nguồn

- Connector HTTP chỉ cho phép GET ở các endpoint Meta được liệt kê; POST chỉ dùng trao đổi mã OAuth. Chỉ yêu cầu `ads_read`.
- Phiên OAuth tồn tại 10 phút, state lưu dạng hash, gắn cookie HttpOnly và chỉ sử dụng một lần. Đối chiếu origin với callback để tránh lỗi localhost/127.0.0.1. Ẩn query callback trong access log Uvicorn; callback không tải tài nguyên ngoài.
- Access token mã hóa Fernet trước khi ghi DB. Khóa mã hóa và App Secret đặt trong `.env`, không đưa vào frontend, OpenAPI response hay thông báo lỗi nhà cung cấp. Khóa hiện có không tự động thay thế khi cấu hình lại.
- Kết nối thuộc từng user trong workspace. Owner/admin được kết nối và yêu cầu đồng bộ; người dùng khác không xem được snapshot của kết nối này. Kiểm tra lại user/role/phiên bản kết nối trước khi công bố dữ liệu.
- Bốn bảng mới qua migration `0006`: `meta_connections`, `meta_oauth_states`, `meta_sync_jobs`, `meta_snapshots`. Không thay đổi các bảng chat/Memory/Telegram hiện có.
- DB lưu job bền vững; worker ARQ hiện có lấy job mỗi 10 giây, một job tại một thời điểm. Không tạo thêm dịch vụ, model hay GPU workload.
- Đồng bộ accounts trước; lịch sử yêu cầu account đã phát hiện trong phiên kết nối hiện tại. Lấy campaigns/adsets/ads và Insights ở cấp ad theo ngày. Khoảng lịch sử tối đa 31 ngày, chia Insights thành cửa sổ 7 ngày.
- Giới hạn 20 trang/endpoint, 100 kết quả mỗi trang yêu cầu, 2 MB/response, 10.000 dòng và 16 MB payload/lượt, timeout 300 giây. Vượt giới hạn báo lỗi để giảm phạm vi, không công bố snapshot thiếu.
- Dùng cursor để phân trang trên host Meta cố định; không theo URL `paging.next`. Retry tối đa ba lần cho lỗi tạm thời/rate limit. Job mất worker phục hồi tối đa hai lượt, có số thế hệ ngăn worker cũ công bố kết quả.
- Snapshot chỉ được ghi và đánh dấu completed trong cùng transaction. Ngắt kết nối xóa token cục bộ, tăng version, hủy queued/running jobs và ẩn snapshot cũ. Không gọi API thu hồi quyền trên Meta; có thể gỡ ứng dụng trong Meta nếu muốn thu hồi quyền bên Meta.
- API có idempotency key, validation ngày, lịch sử 20 jobs và phân trang 50 snapshot. Lưu phiên bản Graph API và khoảng ngày theo job để truy xuất nguồn dữ liệu.
- Giao diện Meta trong bảng hội thoại: kết nối popup, trạng thái, đồng bộ tài khoản/lịch sử, xem snapshots và ngắt kết nối. Kiểu frontend sinh từ OpenAPI.

## Cấu hình trên máy

Meta mặc định tắt. Cần App ID, App Secret, một phiên bản Graph API được hỗ trợ trong Meta App của bạn và redirect URI đăng ký chính xác. Không gửi App Secret/access token vào chat.

Từ `<PAO_PROJECT_DIR>`, chạy PowerShell:

```powershell
.venv\Scripts\python.exe scripts/setup_meta.py --app-id YOUR_APP_ID --api-version YOUR_SUPPORTED_VERSION --redirect-uri http://localhost:3100/v1/integrations/meta/callback
```

Script hỏi App Secret bằng nhập ẩn, kiểm tra cấu hình rồi cập nhật `.env`. Bảo vệ và sao lưu riêng khóa `INTEGRATION_ENCRYPTION_KEY`: mất khóa sẽ không đọc được token đã lưu, phải kết nối lại. Không đưa `.env` vào Git hoặc bản sao chia sẻ.

Sau khi API và worker nạp lại cấu hình, mở **http://localhost:3100**, đăng nhập PAO, mở **Meta Ads · Chỉ đọc** → **Kết nối Meta**. Đăng nhập Facebook và cấp quyền trong popup. Đóng popup khi hoàn tất; bảng PAO tự làm mới mỗi 5 giây. Chọn **Đồng bộ tài khoản**, chọn account, nhập khoảng ngày rồi **Đồng bộ lịch sử**.

Nếu dùng host/HTTPS khác, cấu hình URI đó trong Meta và PAO. Host của trang PAO phải khớp host callback. Reverse proxy ngoài PAO cũng cần tránh ghi query chứa OAuth code/state.

## Triển khai local

Đã triển khai migration `0006` cùng đợt [Phase 8](PHASE-8-WAREHOUSE.md), sau đó lên `0007`. API/worker/web/Telegram đã khởi động lại; web và assets cổng 3100 đã kiểm tra HTTP 200. Lần chặn auto-review trước đó đã được giải quyết trong lượt triển khai này. Meta vẫn tắt do chưa nhập cấu hình/cấp quyền thật.

Dùng quy trình cập nhật local hiện tại:

```powershell
./scripts/deploy_local_phase8.ps1
```

Script kiểm tra công việc đang chờ/chạy, đối chiếu PID cùng thời điểm khởi động trước khi dừng dịch vụ, sao lưu PostgreSQL bằng `pg_dump -Fc`, kiểm tra mục lục backup, migrate, đối chiếu số bản ghi rồi khởi động lại. Nếu một bước lỗi, dừng để kiểm tra; không reset volume. Báo cáo triển khai nằm ở `.runtime/phase-8-migration.json`.

Cổng 3101 dùng cho kiểm thử riêng và đã dừng sau nghiệm thu. Bản sử dụng chính là cổng 3100.

## Nghiệm thu và giới hạn

- 81 backend tests đạt, gồm 15 trường hợp Phase 7: OAuth role/cookie/replay/expiry, token mã hóa, endpoint chỉ đọc, cursor host cố định, retry/lỗi token/quyền, idempotency, scope, phạm vi ngày/account, dữ liệu dở dang, thu hồi quyền lúc đang sync và worker recovery.
- Migration downgrade → upgrade → `alembic check` đạt trên `pao_test`; không chạm dữ liệu chính.
- 8 runtime tests, TypeScript, `pip check` và production build đạt.
- Browser acceptance **đạt** trên cổng 3101 với API giả lập: đồng bộ lịch sử Meta, xem snapshot hoàn tất, ngắt kết nối xóa dữ liệu khỏi UI; đồng thời regression Telegram/agents/tools/Memory/SSE/logout đều đạt, không có browser errors. Ảnh bằng chứng `.runtime/phase-7-meta-browser.png`.
- Chưa nghiệm thu OAuth hoặc dữ liệu Meta thật vì chưa nhập cấu hình/cấp quyền. Quyền khả dụng phụ thuộc Meta App, tài khoản và người đăng nhập; cần kiểm chứng bằng account của bạn.
- Token hiện dùng thời hạn do trao đổi OAuth trả về; chưa có cơ chế long-lived exchange/refresh. Hết hạn cần kết nối lại.
- UI chọn tài khoản hiện hiển thị 50 tài khoản đầu; API snapshot có phân trang. Dữ liệu giữ dạng snapshot theo lượt, chưa chuẩn hóa currency/timezone/action attribution thành warehouse và chưa phục vụ suy luận quảng cáo trong chat.
- Những mục vận hành F2–F4 trong audit hệ thống chưa được giải quyết bởi Phase 7.

Nguồn kỹ thuật đã tham khảo: [Meta Python Business SDK](https://github.com/facebook/facebook-python-business-sdk), [Fernet — cryptography](https://cryptography.io/en/latest/fernet/). Các trang tài liệu Meta trả HTTP 429 trong lượt nghiên cứu; không giả định một Graph API version mới nhất mà bắt buộc cấu hình phiên bản của App.
