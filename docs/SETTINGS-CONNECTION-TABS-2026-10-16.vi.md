# Cài đặt — Kết nối theo nền tảng

Ngày 16/10/2026, target `F:\PAO-ACOS`. Nghiệm thu UI local; không đổi milestone
S4 đã đóng, bước sản phẩm tiếp theo vẫn là S5.

## Phạm vi đã triển khai

- Giữ sáu tab Cài đặt chính. Trong Kết nối có bảy tab nhỏ: Meta Ads, Google Ads,
  TikTok Ads, Telegram, MCP / Công cụ, Botcake và Zalo OA.
- Meta/Google chỉ mount cấu hình ứng dụng và OAuth của nền tảng đang chọn.
  Tài khoản/nhãn hàng/grants và đồng bộ/báo cáo nằm trong các mục thu gọn riêng.
  AdsGrantedReads lọc quyền hiển thị theo nền tảng; backend vẫn là authority.
- Telegram gom bot, danh tính, đội ngũ và thiết lập; cơ chế cũ/chuyển đổi đặt
  trong mục Nâng cao. MCP gom cấu hình, phân quyền và gọi công cụ.
- Các mục thu gọn chỉ mount nội dung khi mở. TikTok/Botcake/Zalo OA là placeholder
  chưa hỗ trợ rõ ràng, không có form nhập khóa hoặc kết nối giả.
- Tab dùng tablist/tab/tabpanel, phím trái/phải/Home/End, focus và cuộn ngang
  mobile. Form nhạy cảm không giữ mount khi rời nền tảng.
- Cảnh báo khi rời tab nền tảng/tab Cài đặt hoặc làm mới trạng thái sau chỉnh
  biểu mẫu; hủy giữ nguyên form, đồng ý bỏ draft. Cảnh báo mang tính bảo thủ:
  thao tác đã gửi không tự bị hủy/hoàn tác. Reload/đóng trang có beforeunload
  khi dirty; không tuyên bố mọi điều hướng SPA khác đều được chặn.
- Key doanh nghiệp/vai trò và cleanup/epoch/abort hiện có giữ quyền và bỏ dữ liệu
  cũ. Không persist khóa hoặc draft vào browser storage. Không thay backend,
  schema, credential, .env, cờ kích hoạt hoặc quyền tại provider.

## Bằng chứng

- TypeScript noEmit đạt; 114 Node tests đạt, gồm 25 runtime/tenant/SSE tests
  (không cộng hai nhóm thành 139 ca riêng).
- Production build source cuối đạt 21/21; còn React Hooks warnings đã có.
  Cảnh báo CSS flex `start` mới đã đổi thành `flex-start` trước build cuối.
- S3 browser qua API/PostgreSQL riêng đạt: bot giả lập, pairing hai bước,
  report-only, revoke, secret wipe, mobile và đổi SME. Không bot thật.
- S4 browser mở rộng qua API/PostgreSQL riêng đạt: Meta/Google OAuth giả lập,
  BYO/managed, rotation/lost ACK, bảy tab, lazy panels, placeholder không form,
  bàn phím, hủy/đồng ý rời draft, tab Cài đặt chính, secret wipe và SME isolation.
  390/320px không tràn ngang. Kết quả tại `.runtime/s4-browser.json`.
- Có lượt mở rộng chưa đạt vì Fast Refresh khi còn sửa UI đóng popup; các lượt
  sau do harness chọn enterprise selector trùng, chưa mở lại Kết nối sau đổi
  SME, hoặc chọn nút đóng drawer off-screen. Đã sửa harness theo trạng thái
  thực, giữ nguyên assertions; lượt cuối đạt toàn kịch bản. Không gọi lượt lỗi
  là pass và không lấy test giả lập làm nghiệm thu dịch vụ thật.
- `check_s4_live.py` đạt: 0065/353 operations, exact backend binding không đổi,
  API/ready/Web200, replay3/3, business hashes và .env nguyên vẹn; không provider calls.
- Không chạy lại toàn bộ backend regression vì thay đổi frontend/test harness.
  Dọn đúng database/API tạm do mỗi runner tạo; primary không bị thay đổi.

## Giới hạn giữ nguyên

Không triển khai connector mới, không bật bot/Ads, không thử tài khoản bên ngoài,
không public deploy. Provider review, OAuth thật và production vẫn external_pending.
