# UI 12 Routes — Stage E: TikTok Ads

Ngày hoàn tất: 2026-09-26

## Phạm vi

Route `/tiktok-ads` đã thay scaffold bằng workspace độc lập dùng App Shell PAO.

- Tám khu vực: Overview, Campaigns, Ad Groups, Ads, Creative Center, Audiences, Insights và Recommendations.
- Overview có KPI placeholders trung thực, integration readiness, pipeline dự kiến và task TikTok thật từ `/v1/tasks`.
- Creative Center liên kết các task có nội dung TikTok.
- Insights mô tả data contract bắt buộc trước khi phân tích.
- Recommendations giữ Safe Mode và không tạo hành động khi chưa có evidence.
- Các bảng quảng cáo ghi rõ connector chưa triển khai và không dùng dữ liệu mẫu.

## Giới hạn hiện tại

Backend chưa có TikTok OAuth, token storage, sync job hoặc warehouse adapter. Đây là giới hạn đã được ghi trong roadmap PAO từ trước. Stage E không giả lập trạng thái kết nối hay chỉ số quảng cáo.

Thứ tự backend đề xuất khi tiếp tục TikTok:

1. Cấu hình TikTok Developer App và redirect URI.
2. OAuth có state một lần, mã hóa credential và kiểm tra membership.
3. Connector read-only với allowlist endpoint và giới hạn response.
4. Sync account/campaign/ad group/ad/metrics có idempotency.
5. Mở rộng normalized warehouse cho platform TikTok.
6. Chỉ bật insight/recommendation sau khi kiểm tra freshness và attribution.

## Kiểm thử

- Next.js production build: đạt, `/tiktok-ads` là route riêng.
- Runtime/SSE: 8/8 đạt.
- Browser acceptance: đạt; kiểm tra 8 tab, readiness, trạng thái dữ liệu trống, Insights và Safe Mode.
- System verifier: API/web/assets HTTP 200; toàn bộ process PAO còn hoạt động.

Ảnh kiểm tra: `.runtime/workspace-tiktok-ads-route-1920.png`.
