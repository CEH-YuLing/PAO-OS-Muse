# UI 12 Routes — Stage H: Content & Creative

Ngày hoàn tất: 2026-09-26

## Phạm vi

Route `/content-creative` đã thay scaffold bằng workspace độc lập và nối Creative Intelligence backend.

- Creative Library: asset, metadata, trạng thái fatigue và KPI chính.
- Performance: Spend, Revenue, ROAS và bảng CTR/CPM/CPA/Frequency.
- Fatigue Monitor: score, confidence và signals theo current/baseline windows.
- Advertising Memory: learning theo hook, angle hoặc metadata đủ mẫu.
- Strategy Briefs: brief có evidence và yêu cầu human review trước sản xuất.
- Metadata drawer: chỉnh product, market, language, format, hook, angle, offer, CTA, creator và landing page với optimistic version.
- Creative analysis dùng ad-level warehouse và ngày đã hoàn tất.

## Giới hạn an toàn

- Module read-only với nền tảng quảng cáo; không tạo, sửa hoặc launch ads.
- Strategy brief không tự động biến thành creative production.
- Creative thiếu sample giữ trạng thái `insufficient`.
- Frequency không được cộng sai khi một creative dùng trên nhiều ads.

## Kiểm thử

- Next.js production build: đạt, `/content-creative` là route riêng.
- Runtime/SSE: 8/8 đạt.
- Browser acceptance: đạt; kiểm tra 5 tab, library, 8 KPI, fatigue, learning và strategy brief.
- Backend regression gần nhất: 159/159 đạt.
- System verifier: API/web/assets HTTP 200 và toàn bộ process hoạt động.

Ảnh kiểm tra: `.runtime/workspace-content-creative-route-1920.png`.
