# Tái cấu trúc UI/UX local — 18/10/2026

[Hướng dẫn sử dụng nhanh](UI-UX-USER-GUIDE.vi.md).

## Phạm vi được duyệt

Một đợt cải thiện UX trước S6.1, triển khai tuần tự bốn phần: điều hướng và
đăng nhập; Cài đặt; Kho tri thức/Kế hoạch; các màn hình vận hành và nghiệm thu.
Không thay roadmap M/P/S, backend, quyền, schema, `.env`, dependency hoặc thêm
connector/runner. PAO local là mục tiêu; VPS/public và dữ liệu thật chưa nghiệm thu.

## Cấu trúc giao diện

- Cài đặt dùng menu phụ trái trên desktop, cuộn ngang trên điện thoại. Bảy
  nhóm: Tổng quan; Doanh nghiệp và nhãn hàng; Tài khoản và nhân sự; Kết nối;
  AI và giọng nói; An toàn và dữ liệu; Hệ thống và năng lực.
- Tổng quan chỉ có tóm tắt, giao diện sáng/tối và lối tắt, không chứa các
  biểu mẫu nhân sự/xuất/xóa. Mỗi nhóm có tối đa bốn mục con.
- Tài khoản của tôi/phiên; Thành viên; Lời mời; Quyền truy cập tách riêng.
  Danh sách đủ điều kiện cấp kết nối không bị gọi là danh bạ đầy đủ.
- Xuất dữ liệu và yêu cầu xóa là hai mục riêng, vẫn có xác nhận native.
  Xác nhận yêu cầu chưa xóa thật; không thêm deletion executor.
- Kết nối giữ bốn nhóm đã nghiệm thu và các vị trí chờ rõ ràng. AI chỉ mở
  biểu mẫu một nhà cung cấp; đổi nhà cung cấp phải bỏ khóa chưa lưu rõ ràng.
- Kho tri thức giữ hồ sơ doanh nghiệp, hồ sơ nhãn hàng, Skills, tri thức/bộ
  nhớ. Skills tách thư viện, agent phụ trách, công cụ nâng cao; chỉ mở trình
  biên tập khi tạo/chọn một mục. Không thay ghim phiên bản hoặc quyền công cụ.
- Tri thức/bộ nhớ tách kho tài liệu, thư viện bộ nhớ và tìm theo ý nghĩa;
  trạng thái trích xuất đưa vào phần nâng cao. Quản lý nhãn hàng dẫn về Cài đặt.
- Kế hoạch có năm tab: Kế hoạch; Phân công AI; Công việc; Phê duyệt; Báo cáo.
  Một operations component giữ cùng state giữa các tab, không thêm runner hoặc
  tự chạy lại. Bản nháp của các bước còn nguyên khi đổi tab.
- Hồ sơ nguồn có tóm tắt/lối mở Kho tri thức. Giữ đường chỉnh sửa nhanh và
  lịch sử native trong phần nâng cao để không làm mất chức năng/draft cũ;
  hai điểm vào dùng cùng API và dữ liệu, không tạo hồ sơ thứ hai.
- Các trang Ads nhóm các chế độ xem cũ thành tối đa bốn nhóm theo nền tảng;
  mục con dùng bộ chọn, không trải tám tab. Không thêm năng lực Ads chưa có.
- Công việc tách việc thường và AI; Bảng/Danh sách/Tiến trình/Lịch là các
  cách xem. Hộp thư tách Hội thoại, Kênh, Tin chờ gửi và Nhật ký. Các menu
  chính CRM/Phân tích/Nội dung/Tự động hóa được Việt hóa, giữ dữ liệu và URL.
- Chat, cửa sổ chi tiết, Ask PAO và Copilot giữ lại. Không thêm nút gửi thật.

## Đăng nhập và lời mời

Nút chính Đăng nhập; nút phụ đầy chiều rộng “Tạo tài khoản bằng mã mời”.
Trang nhận lời mời cùng hệ giao diện sáng/tối/responsive. Chưa đăng nhập:
email được mời, mã riêng và mật khẩu tài khoản mới; đã đăng nhập: nhận lời mời
bằng tài khoản hiện tại, không tạo mật khẩu mới. Mã không đưa vào URL/storage.
Không mở public signup, đổi mật khẩu hoặc tự gửi mã qua email/Telegram.

## Nghiệm thu và giới hạn bằng chứng

- 157Node (148 cũ +9 điều hướng/taxonomy), TypeScript và production build23trang.
- Native browser dùng database riêng và API hiện có: lời mời sai/hợp lệ,
  hành trình kế hoạch/phê duyệt/AI fixture/ngân sách mô phỏng/báo cáo; đủ12khu
  vực; bốn nhóm kết nối; scope SME/role; nháp; bàn phím; Back/Forward; sáng/tối;
 320/390px. Không suy fixtures thành chất lượng AI hoặc nghiệm thu provider thật.
- Hồi quy giao diện native tổ chức/Skills: tạo SME riêng, đổi tên, tạo nhãn
  hàng với mất phản hồi không tự gửi lại, hồ sơ dùng chung, duyệt/công bố skill,
  đổi gán agent tạo phiên bản mới, không thay phiên bản đã công bố; scope và role.
- Hồi quy vòng vận hành: mất phản hồi khởi chạy, hủy chờ ACK rồi terminal,
  phụ thuộc chỉ chạy sau duyệt, làm lại không sao chép quyền, phục hồi báo cáo,
  dừng thế hệ, lịch sử, lỗi đọc và đổi SME. Cả hai phải có receipt riêng pass=true
  cùng nguồn frontend; không dùng bằng chứng UI cũ thay lần nghiệm thu này.
- Lượt đầu thất bại vì test chưa mở phần hồ sơ nâng cao; giữ log/cleanup riêng,
  cập nhật thao tác test, không gỡ assertion nghiệp vụ.
- Browser cũng phát hiện nút đổi giao diện public bị lặp; đã giữ một nút dùng
  chung. Selector test được giới hạn đúng summary/biểu mẫu lỗi, không nhầm
  summary lịch sử hoặc route announcer. Kiểm ảnh bổ sung cân lại độ rộng biểu
  mẫu nhận lời mời; chạy lại build và nghiệm thu trên nguồn cuối.
- Baseline2272Linux backend và202Windows focused trước đó chỉ tái sử dụng khi
  source API/contracts/locks và execution binding khớp. Không gọi là full backend
  mới, hosted CI hoặc toàn S6 hoàn tất.

Kết quả native cuối chỉ được xác nhận từ receipt pass=true và cleanup pass=true
trong `.runtime/ux-restructure-browser-runs/`. Bản cài chỉ được nghiệm thu khi
`.runtime/ux-restructure-completion.json` pass=true: browser read-only, health,
worker và replay3 đạt, dữ liệu chính/cấu hình/binding không đổi. Bằng chứng ảnh,
log và hash nằm ở `evidence` trong receipt. Readiness phải là
`s6-local-ux-restructure-v1`, `local_checks_passed=true`; S6/production vẫn false.

Native cuối của nguồn UI này đã đạt ở
`.runtime/ux-restructure-browser-runs/pao_s5_browser_9d5252a876fb4aef830b4d7468abf564/receipt.json`:
M6, Kết nối, UX mới, vòng vận hành và tổ chức/Skills cùng đạt; cleanup, hash
primary và `.env` đạt. Sáu kiểm thử offline chốt release đạt riêng, không cộng
vào157Node hoặc2272backend. Giữ các lượt lỗi trước đó và bằng chứng cleanup;
không dùng receipt nguồn trước lần cân biểu mẫu làm bằng chứng cho nguồn cuối.

Manifest phát hành giới hạn apps/web/scripts/docs, kiểm hash nguồn trước-sau.
Bản phục hồi nằm ở `backup` trong `.runtime/ux-restructure-installed.json`.
Chỉ Web được khởi động lại sau xác minh executable/PID/start ticks; không
restore DB để ép khớp hash. Không tự push, bật dịch vụ hoặc thay cấu hình thật.
