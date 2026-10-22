# Phase 15 — Attribution + CRM Intelligence

## Kết quả

Phase 15 nối dữ liệu Meta warehouse với web analytics, CRM và orders qua một lớp nhập chuẩn hóa. Lớp này phù hợp webhook, file export hoặc adapter tự host; mỗi nhà cung cấp có thể được nối vào mà không thay đổi mô hình phân tích. Phase này không triển khai đồng thời nhiều OAuth connector riêng.

Attribution Analyst chỉ dùng liên kết deterministic. Campaign lấy từ `campaign_id`, UTM đã được adapter phân giải thành campaign, hoặc order liên kết duy nhất đến CRM lead. Record không đủ bằng chứng giữ nguyên `unattributed`; PAO không phân bổ xác suất hoặc dùng LLM để đoán nguồn.

## Dữ liệu và tính nhất quán

Migration `0014` thêm tám bảng: nguồn attribution, analytics events, CRM leads, CRM stage history, business orders, analysis runs, campaign metrics và tracking alerts. Dữ liệu nhập có `external_id`, fingerprint và transaction idempotency. Analytics/lead/stage là immutable; order update dùng optimistic version. Timestamp bắt buộc kèm timezone, tiền dùng Decimal và currency phải khớp tài khoản.

Identifier khách hàng/visitor/session chỉ nhận SHA-256 dạng 64 ký tự hex. API không nhận email, số điện thoại hoặc tên khách hàng thô. Workspace, user, Meta connection version và account được kiểm tra ở mọi đường nhập/đọc.

CRM funnel dùng cohort lead được acquire trong kỳ; stage được tính theo trạng thái cuối cùng tại cuối kỳ để tránh nhìn trước tương lai. Order trong kỳ có thể liên kết đến lead cũ. Nếu cùng external lead ID tồn tại ở nhiều nguồn CRM thì liên kết được xem là mơ hồ và order giữ `unattributed`.

## Chỉ số và tracking health

Mỗi campaign có sessions, form submits, analytics purchases, leads, qualified leads, appointments, sales, actual orders và actual revenue. Các chỉ số dẫn xuất gồm landing CVR, CPL, CPQL, cost per appointment, CAC và revenue per lead.

Tracking discrepancy so sánh conversion/doanh thu Meta với orders thực. Ngưỡng mặc định 25%; mức vượt ngưỡng là `watch`, vượt hai lần ngưỡng là `unhealthy`. Tracking alert có fingerprint, acknowledge và resolve lifecycle. Một campaign `unhealthy` tạo anomaly `TRACKING_DISCREPANCY`; recommendation của Performance Intelligence nhận blocker `tracking_health` và confidence bị giới hạn. Hệ thống không tự pause ads chỉ vì landing CVR giảm.

Báo cáo daily/weekly dùng attribution run đúng cùng kỳ khi có, rồi hiển thị actual orders, actual revenue, CAC, revenue per lead và trạng thái khóa tối ưu. Không có run phù hợp thì báo cáo không bịa số business.

## API và giao diện

- `POST/GET /v1/attribution/sources`
- `POST /v1/attribution/sources/{id}/analytics|leads|stages|orders`, tối đa 500 rows/batch
- `POST /v1/attribution/analyze`, kỳ tối đa 366 ngày và có request-key idempotency
- `GET /v1/attribution/dashboard`
- `POST /v1/attribution/alerts/{id}/acknowledge`

Panel **Attribution + CRM · Phase 15** cho phép owner/admin tạo nguồn, nhập batch JSON, chạy phân tích và xem business value/tracking health. Toàn bộ Phase 15 là read-only với nền tảng quảng cáo.

## Xác minh

- Migration roundtrip đến `0014`, `alembic check` sạch và **142 backend tests** đạt.
- OpenAPI **68 paths**, TypeScript contracts, Next production build và **8 runtime tests** đạt.
- Bộ test chứng minh campaign CPL 7 có CAC 24,5 và 20 sales tốt hơn campaign CPL 4 nhưng CAC 80 và chỉ 5 sales.
- Test kiểm tra retry/conflict, RBAC, currency, hashed identifier, lead cũ, tracking alert và Performance Intelligence blocker.

Production chỉ có schema/API sau triển khai; bảng Phase 15 khởi tạo trống cho đến khi tạo nguồn và nhập dữ liệu thật. Meta Write và Limited Autopilot tiếp tục OFF.
