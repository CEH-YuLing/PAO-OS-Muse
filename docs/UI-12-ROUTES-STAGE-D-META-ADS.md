# UI 12 Routes — Stage D: Meta Ads

Ngày hoàn tất: 2026-09-26

## Phạm vi

Route độc lập `/meta-ads` đã thay scaffold và dùng App Shell chung của PAO. Trang theo logic Ads Manager nhưng chỉ hiển thị dữ liệu thật đã đồng bộ từ backend.

- OAuth, chọn ad account, trạng thái sync và đồng bộ 30 ngày.
- Tám tab: Overview, Campaigns, Ad Sets, Ads, Creatives, Audiences, Insights, Recommendations.
- KPI Spend, Revenue, ROAS, CPA, CTR, CPM, CPC, Conversions và biểu đồ Spend/Revenue.
- Bảng campaign, ad set, ad và creative lấy từ snapshot thật.
- Anomaly, recommendation và thao tác acknowledge/dismiss theo quyền workspace.
- Approval inbox dùng pipeline snapshot → approval → worker hiện có.
- Trạng thái trống rõ ràng; Audience chưa có backend connector nên không dựng dữ liệu giả.

## An toàn

- UI không gọi Meta write API trực tiếp.
- Live write phụ thuộc `META_WRITE_ENABLED`; trạng thái hiện tại là `false`.
- Quyết định quan trọng yêu cầu owner/admin và đi qua approval backend.
- Đồng bộ lịch sử giới hạn 30 ngày hoàn tất, granularity daily, có warehouse.

## Kiểm thử

- `npm run build`: đạt, `/meta-ads` là route riêng.
- `npm run test:runtime`: 8/8 đạt.
- `npm run test:frontend`: đạt; kiểm tra 8 tab, KPI, chart, campaign, insight, recommendation và Safe Mode.
- `python scripts/test_backend.py`: 159/159 đạt.
- `python scripts/verify_system_local.py`: đạt; migration `0018`, 60 bảng, 89 OpenAPI paths, API/web/assets đều HTTP 200.

Ảnh kiểm tra: `.runtime/workspace-meta-ads-route-1920.png`.
