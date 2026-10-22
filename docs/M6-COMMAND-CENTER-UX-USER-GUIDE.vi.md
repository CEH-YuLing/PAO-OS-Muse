# Giai đoạn 2 — Sử dụng giao diện điều hành PAO

## Bổ sung18/10 — theo dõi và phục hồi vòng local

Xem [hướng dẫn và nghiệm thu vòng local](LOCAL-OPERATING-CYCLE-2026-10-18.vi.md).
Vận hành kế hoạch có bảng tiến độ và tự đọc mỗi5giây khi còn job chờ/chạy trong
tab đang mở, không tự retry hoặc gọi AI. “Đã yêu cầu hủy” chưa phải “Đã hủy”.
Mất phản hồi phải Đọc lại để đối soát; lỗi đọc dừng auto refresh. Job lỗi/hủy/
từ chối có lối Chuẩn bị kế hoạch làm lại, vẫn cần lưu/duyệt/chạy riêng; không
sao chép phê duyệt, grant, job hoặc ledger. Kế hoạch có cấu trúc vẫn do người
dùng soạn/lưu; không hứa AI tự lập và thực hiện mọi chiến dịch từ một câu lệnh.

Phạm vi: lát cắt M6 phục vụ S6; không phải nghiệm thu toàn M6, S6 hoặc production.

## Bắt đầu

1. Đăng nhập rồi chọn **Doanh nghiệp**. Đọc lại tên doanh nghiệp trước khi nhập
   dữ liệu. Một người thuộc nhiều doanh nghiệp không có nghĩa được trộn dữ liệu.
2. Mở **Công việc và dự án → Kế hoạch kinh doanh**. Mục này chỉ hiện khi
   chức năng được bật và tài khoản có quyền quản lý; chủ doanh nghiệp duyệt riêng.
3. Chọn toàn doanh nghiệp hoặc nhãn hàng. Dùng thanh hành trình để đến Hồ sơ,
   Kế hoạch, Phân công AI, Duyệt kế hoạch, Chạy và duyệt nội dung, Báo cáo.
   Đây là lối đến từng phần trên cùng trang, không phải sáu chương trình độc lập.

## Đi hết một chu kỳ an toàn

1. Nhập hồ sơ, sản phẩm, khách hàng, giọng thương hiệu, nguồn lực, mục tiêu/KPI
   và ngân sách dự kiến. Chưa biết thì để trống; không coi là 0. Lưu phiên bản.
2. Đặt tên và tháng kế hoạch. Thêm đầu việc, hạn, yêu cầu và tiêu chí nghiệm thu.
   Chọn việc phụ thuộc bằng checkbox, không cần chép mã của đầu việc khác.
3. Chọn kỹ năng văn bản đã được duyệt/xuất bản và model cho từng chuyên môn.
   Ollama dùng tên model đã cài. Cloud chọn kết nối có sẵn trong danh mục quản lý;
   không nhập API key tại Kế hoạch kinh doanh. Lưu cấu hình rồi kiểm tra lựa chọn
   AI cho từng việc; bước kiểm tra không gọi model hoặc giữ token/tiền.
4. Chủ doanh nghiệp kiểm tra đúng phiên bản, xác nhận rồi duyệt chuẩn bị nội bộ.
   Tiếp tục xác nhận tạo công việc nháp. Duyệt kế hoạch không duyệt nội dung,
   không cấp quyền dùng model và không cho phép chạy quảng cáo.
5. Chọn việc, model kế thừa hoặc lựa chọn riêng và quyền cloud phù hợp nếu cần.
   Danh sách quyền chỉ đọc metadata của danh mục bạn quản lý, đã có consent,
   đúng người/SME/nhãn hàng và chưa hết hạn; máy chủ vẫn kiểm tra lại toàn bộ.
   Thiếu lựa chọn: đến **Cài đặt và kết nối → Mô hình AI và giọng nói**, không
   mượn khóa hoặc quyền của SME khác. Chọn một giá trị chưa phải lệnh chạy.
6. Xác nhận gọi AI riêng, đọc trạng thái rồi duyệt bản nháp theo đúng kết quả.
   Tạo ảnh/video, đăng bài và sửa Ads thật không nằm trong lượt nghiệm thu này.
7. Ngân sách và đề xuất tại đây là **MÔ PHỎNG**. Duyệt hành động riêng; kết quả
   chưa rõ phải đối soát, không gửi lại để vượt khoản đang giữ.
8. Tạo báo cáo 24 giờ hoặc đặt lịch nội bộ có xác nhận. Báo cáo ghi khoảng
   thời gian, nguồn nội bộ, token và KPI chưa có dữ liệu đo; không phải số dư,
   hóa đơn API, doanh thu hoặc chi tiêu quảng cáo thật. Không tự gửi Telegram.

## Bản nháp, liên kết và lịch sử

- Bản nháp hồ sơ/kế hoạch chỉ nằm trong bộ nhớ tab, tối đa 30 phút/20 phạm vi.
  Tách tài khoản, SME, nhãn hàng và vai trò; chỉ khôi phục sau khi đọc quyền và
  đối chiếu phiên bản hiện hành. Phiên bản đã đổi không tự ghép bản nháp cũ.
- Đổi SME rồi quay lại có thể khôi phục bản nháp đúng SME. Lưu chính thức lên
  máy chủ trước khi tải lại/đóng tab hoặc đăng xuất. Thao tác xác nhận bỏ nháp
  khi đổi phạm vi/đọc lại sẽ bỏ nháp đã xác nhận, không hủy tác vụ đã gửi.
- Cấu hình AI chưa lưu, token/secret, xác nhận duyệt và quyền chạy **không**
  được giữ cùng bản nháp kinh doanh. Form kết nối đổi tab có cảnh báo và xóa
  trường chưa lưu; không lưu khóa trong URL hoặc browser storage.
- Khi mở/lưu kế hoạch, URL chỉ ghim mã SME/nhãn hàng/kế hoạch. Có thể lưu liên
  kết để mở lại đúng phiên bản hiện hành; liên kết không tự cấp quyền. Đổi SME
  không áp dụng mã kế hoạch của SME trước. Không đưa token/mật khẩu vào URL.
- Lịch sử hồ sơ và kế hoạch là dữ liệu đọc riêng. Đọc phiên bản cũ không đổi
  phiên bản đang vận hành hoặc phục hồi quyền duyệt đã hết hiệu lực.
- Muốn điều chỉnh/làm lại việc đã có lượt chạy: **Nhân bản thành kế hoạch mới**,
  rà đầu việc/phụ thuộc, lưu, duyệt và khởi chạy riêng. Không tự retry job cũ,
  sao chép phê duyệt, hóa giải chi phí đã có hoặc xóa lịch sử.

## Cài đặt và điều hướng

- Giữ 12 khu vực chính. Kế hoạch nằm dưới Công việc; Mục tiêu, Kết quả và
  phê duyệt, Hộp thư và kênh nằm dưới Tự động hóa. Các URL cũ vẫn dùng được.
- Kết nối có tab riêng Meta, Google, TikTok, Telegram, MCP, Botcake và Zalo OA.
  Có thể lưu URL `?tab=integrations&platform=telegram`. Back/Forward và phím
  mũi tên/Home/End chuyển tab; thay đổi chưa lưu có cảnh báo trước khi rời.
- TikTok/Botcake/Zalo chưa có adapter phải hiện **Chưa hỗ trợ kết nối**, không
  tạo form nhập khóa giả. Các nền tảng đã có code vẫn cần cấu hình/nghiệm thu thật.
- Tìm kiếm trên thanh đầu mở Kho tri thức; nút chuông mở Kết quả và phê duyệt.
  Không giả báo số thông báo chưa đọc hoặc bộ lọc ngày chưa được triển khai.
- Dùng Tab để di chuyển, focus có viền rõ; có liên kết bỏ qua điều hướng.
  Trên điện thoại mở menu điều hướng và dùng thanh hành trình xuống từng phần.

## Khi gặp lỗi

Đọc thất bại: giao diện bỏ dữ liệu chưa xác minh, không tự coi danh sách rỗng
là chưa có dữ liệu. Kiểm tra kết nối/quyền rồi bấm Đọc lại. Gửi/lưu chưa rõ:
không gửi lại mù, đối soát phiên bản/trạng thái trước. Lỗi đọc không phải lý do
nhập lại secret. Mất quyền hoặc đổi SME không giữ phản hồi cũ trong màn hình mới.
