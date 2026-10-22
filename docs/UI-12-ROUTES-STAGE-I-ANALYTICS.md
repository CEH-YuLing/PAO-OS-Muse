# Stage I — Analytics

## Phạm vi

Route độc lập `/analytics` thay thế scaffold bằng Analytics workspace sử dụng dữ liệu thật đã có trong PAO:

- report warehouse theo Meta ad account;
- daily revenue/spend trend;
- deterministic attribution từ GA4/CRM/orders aggregate;
- performance anomaly và recommendation hiện hành;
- tracking discrepancy và data-quality state.

## Khu vực giao diện

1. **Overview** — 8 KPI, biểu đồ revenue/spend và decision context.
2. **Trends** — bảng daily trend kèm coverage.
3. **Attribution** — platform value so với business value theo campaign.
4. **Funnel** — sessions → form submits → leads → qualified → appointments → sales → orders.
5. **Tracking Health** — trạng thái campaign và tracking alert.
6. **Data Quality** — coverage, freshness, source, attribution run và analysis signals.

## Quy tắc dữ liệu

- Actual revenue/orders chỉ dùng khi attribution metrics tồn tại.
- Khi chưa có attribution, KPI dùng platform report và ghi rõ nguồn.
- Không tự suy đoán conversion, không phân bổ doanh thu xác suất.
- Trang Analytics không thực hiện write lên nhà cung cấp quảng cáo.

## Kiểm thử chấp nhận

Browser acceptance kiểm tra route, 6 khu vực, 8 KPI, trend, attribution table, 7 funnel stages, tracking state, data quality và ảnh chụp desktop.
