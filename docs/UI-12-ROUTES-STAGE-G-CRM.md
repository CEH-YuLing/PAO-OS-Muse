# UI 12 Routes — Stage G: CRM

Ngày hoàn tất: 2026-09-26

## Phạm vi

Route `/crm` đã thay scaffold bằng workspace độc lập và nối Attribution + CRM backend hiện có.

- Overview: Actual Revenue, Leads, Qualified, Appointments, Sales, Orders, CAC và Revenue/Lead.
- Pipeline: funnel aggregate Lead → Qualified → Appointment → Sale.
- Campaign Revenue: CPL, CAC, actual revenue và tracking health theo campaign.
- Data Sources: nguồn GA4, CRM và orders; owner/admin có thể tạo nguồn mới.
- Tracking Health: discrepancy giữa platform và orders thực, có acknowledge theo quyền.
- Attribution Analyst chạy theo khoảng ngày hoàn tất và idempotency key.

## Mô hình dữ liệu và riêng tư

- Trang chỉ dùng aggregate từ attribution run; backend chưa có API danh sách contact/deal.
- Không tạo contact hoặc deal giả để lấp UI.
- Ingestion dùng external ID và identifier đã băm; không cần email, số điện thoại hoặc tên khách hàng thô.
- Attribution là deterministic; record thiếu liên kết giữ trạng thái unattributed.

## Kiểm thử

- Next.js production build: đạt, `/crm` là route riêng.
- Runtime/SSE: 8/8 đạt.
- Browser acceptance: đạt; kiểm tra 5 tab, 8 KPI, funnel, campaign revenue, sources và tracking state.
- Backend regression: 159/159 đạt.
- System verifier: API/web/assets HTTP 200; toàn bộ process PAO hoạt động.

Ảnh kiểm tra: `.runtime/workspace-crm-route-1920.png`.
