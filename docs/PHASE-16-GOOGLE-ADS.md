# Phase 16 — Google Ads

## Phạm vi

Phase 16 thêm connector Google Ads read-only và dịch response GAQL vào cùng `ad_entities`/`ad_metrics` của Ads Warehouse. PAO không tạo campaign, đổi budget, pause/resume hay đưa Google Ads vào Autopilot trong phase này.

Connector dùng Google Ads API `v25`. OAuth xin duy nhất scope `https://www.googleapis.com/auth/adwords`, yêu cầu offline access và lưu refresh token bằng Fernet. Từ ngày 09/09/2026, Google gắn API access level với Google Cloud project; developer token trở thành tùy chọn và bị API bỏ qua. PAO vì vậy không bắt buộc developer token, nhưng vẫn chấp nhận biến cấu hình cũ cho dự án đã chuyển đổi. Tham khảo [Google Ads API access migration](https://developers.google.com/google-ads/api/docs/api-policy/developer-token) và [v25 release notes](https://developers.google.com/google-ads/api/docs/release-notes).

## Mô hình dữ liệu

Migration `0015` thêm `google_ads_connections`, `google_ads_oauth_states` và `google_ads_sync_jobs`. Hai bảng warehouse dùng chung được mở rộng bằng khóa ngoại Google riêng. Check constraint bắt buộc mỗi row chỉ thuộc Meta hoặc Google, cùng source job tương ứng; không bỏ foreign key và không tạo warehouse song song.

`AdGroup` được map thành normalized `adset`. Google primary conversions map vào hai trường platform-neutral `conversions` và `conversion_value`; `purchase`/`revenue` giữ NULL vì Google conversions không mặc nhiên là purchase. Meta rows được backfill và tiếp tục ghi hai trường mới từ purchase/revenue. Tiền `cost_micros` được đổi chính xác sang currency unit bằng Decimal.

## Luồng và giới hạn

- `POST /v1/integrations/google-ads/oauth/start` và callback CSRF/cookie one-time.
- `GET/DELETE /connection` với workspace RBAC và generation fence.
- `POST /sync` cho accessible accounts hoặc historical tối đa 31 ngày.
- Worker đơn chạy sync có timeout, bounded pagination/rows, recovery và atomic publish.
- `GET /accounts`, `/jobs`, `/metrics` chỉ đọc dữ liệu normalized đã hoàn tất.
- Daily và hourly hỗ trợ campaign/ad group/ad; không cộng dữ liệu giữa các level.

Manager-account child discovery nhiều tầng, lịch sync, reporting/intelligence cross-platform và Google write nằm ngoài lát cắt Phase 16 hiện tại. Account trực tiếp hoặc account xuất hiện trong `customers:listAccessibleCustomers` được hỗ trợ.

## Cấu hình

Các biến mới trong `.env.example`: `GOOGLE_ADS_ENABLED`, Client ID/Secret, API version, redirect URI, login customer ID tùy chọn và developer token tùy chọn. Cài mới mặc định `GOOGLE_ADS_ENABLED=false`.

## Xác minh

- Migration roundtrip base → `0015` và `alembic check`.
- Transport allowlist chỉ token exchange, accessible customers và GAQL `SELECT`; không có mutate endpoint.
- Test OAuth/RBAC/replay/encryption, read-only transport, account sync và normalized shared warehouse.
- Browser acceptance kiểm tra Google account sync, conversion/value/ROAS và toàn bộ luồng Phase 1–15.


## Kết quả triển khai local ngày 22/09/2026

- Backend: 148 kiểm thử đạt; Alembic roundtrip/check đạt.
- Frontend: 8 runtime tests đạt; production build và toàn bộ browser acceptance Phase 1–16 đạt.
- OpenAPI: 75 paths; TypeScript contracts đã sinh lại và biên dịch.
- Database chính: backup 235.162 bytes đã kiểm tra bằng `pg_restore --list`; 45 bảng cũ giữ nguyên counts; revision `0015`.
- Runtime: API/Web/worker/Telegram/Ollama cùng PostgreSQL/Redis/Search đang chạy; `/ready`, web và static assets đều HTTP 200.
- Trạng thái an toàn: Google Ads chưa cấu hình và đang tắt; Meta Write và Autopilot vẫn tắt; không có provider write trong triển khai.
