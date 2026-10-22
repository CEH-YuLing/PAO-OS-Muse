# UI 12 Routes — Stage F: Google Ads

Ngày hoàn tất: 2026-09-26

## Phạm vi

Route `/google-ads` đã thay scaffold bằng workspace độc lập và nối connector Google Ads read-only hiện có.

- OAuth Google Ads, trạng thái connection, danh sách accessible accounts và sync jobs.
- Khoảng ngày tối đa theo contract backend, granularity daily/hourly.
- Đọc normalized metrics ở ba cấp: Campaign, Ad Group và Ad.
- Overview có Spend, Conversion Value, ROAS, CPA, CTR, CPC, CPM và Conversions.
- Biểu đồ Spend so với Conversion Value được tổng hợp theo ngày.
- Insights dùng deterministic checks và evidence của phạm vi đang xem.
- Search Terms hiển thị giới hạn data contract hiện tại; không suy đoán query từ metric entity.

## An toàn

- Connector chỉ dùng GAQL read-only được allowlist.
- Không tạo/sửa campaign, không đổi budget và không tham gia Autopilot.
- OAuth credential được backend mã hóa; owner/admin mới quản lý connection và sync.
- UI không gọi Google Ads provider trực tiếp.

## Kiểm thử

- Next.js production build: đạt, `/google-ads` là route riêng.
- Runtime/SSE: 8/8 đạt.
- Browser acceptance: đạt; kiểm tra connected state, 8 KPI, campaign/ad group metrics, Search Terms state và Insights.
- Backend regression: 159/159 đạt.
- System verifier: API/web/assets HTTP 200, toàn bộ process hoạt động, provider write không được gọi.

Ảnh kiểm tra: `.runtime/workspace-google-ads-route-1920.png`.
