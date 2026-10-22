# PAO — 12 routes, shared shell và Dashboard

Ngày triển khai: 25/09/2026.

## Phạm vi hoàn thành

- Giữ trang Orb tại đường dẫn gốc.
- 12 nút Orb điều hướng tới 12 URL độc lập.
- Tạo route registry dùng chung để sidebar và Orb không lệch tên hoặc URL.
- Tạo PaoRuntimeProvider ở root layout; token được giữ trong sessionStorage và xác minh lại bằng /v1/me khi tải lại.
- Tạo App Shell dùng chung: sidebar, topbar, Ask PAO, user/workspace và PAO Copilot.
- Tạo protected route behavior: chưa đăng nhập được đưa về trang gốc.
- Tạo 11 trang scaffold độc lập, không dựng dữ liệu giả.
- Hoàn thiện trang Dashboard theo Executive Command Center.

## Nguồn dữ liệu Dashboard

- Ads Reporting: KPI và xu hướng Revenue/Spend.
- Performance Intelligence: anomaly và recommendation.
- Ads Approval: hành động đang chờ owner/admin.
- Meta/Google integrations: trạng thái kết nối.
- Attribution + CRM: leads, qualified leads, sales, actual orders và actual revenue.
- Automation: workflow đang hoạt động.
- Runtime: phiên hội thoại, agent và trạng thái PAO.

Dashboard giữ giá trị trống hoặc trạng thái chưa kết nối khi nguồn dữ liệu chưa tồn tại. Profit không được suy diễn vì backend chưa có cost-of-goods.

## Route

/dashboard, /pao-ai, /tasks, /meta-ads, /tiktok-ads, /google-ads, /crm, /content-creative, /analytics, /automation, /knowledge, /settings.

## Kiểm thử chấp nhận

- Build Next.js sinh đủ 12 route.
- Orb có 12 link trên một hàng và không còn panel module trên trang gốc.
- Điều hướng từ Orb sang Dashboard giữ phiên đăng nhập.
- Reload Dashboard khôi phục phiên bằng token đã xác minh.
- App Shell có 12 link và Dashboard có 8 KPI.
- Module scaffold mở bằng URL độc lập.
- Runtime/SSE regression tiếp tục đạt.

## Bước kế tiếp

Triển khai PAO AI bằng runtime hiện có, giữ Ask/Analyze/Plan/Execute/Research, conversation list, context inspector, tool activity và input dùng chung.
