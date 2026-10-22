# Quản lý doanh nghiệp, nhãn hàng và Skills

## 1. Chọn đúng doanh nghiệp trước khi làm việc

Hộp chọn ở đầu PAO xác định doanh nghiệp đang hoạt động. Một tài khoản có thể
thuộc nhiều doanh nghiệp với vai trò khác nhau. Đổi doanh nghiệp sẽ bỏ các bản
nháp trong màn hình cũ; không sao chép hoặc tìm kiếm chéo bộ nhớ/kết nối.

## 2. Tạo và quản lý doanh nghiệp

Mở **Cài đặt và kết nối → Doanh nghiệp và nhãn hàng**.

1. Đọc lại danh sách, kiểm tra tên doanh nghiệp đang chọn.
2. Chủ doanh nghiệp nhập “Tên doanh nghiệp mới”, bấm “Tạo doanh nghiệp độc lập”.
3. Đọc xác nhận: doanh nghiệp mới không kế thừa thành viên, nhãn hàng, dữ liệu,
   kết nối hoặc quyền từ doanh nghiệp hiện tại.
4. Khi được xác nhận thành công, chọn “Chuyển sang doanh nghiệp mới” hoặc dùng
   hộp chọn ở đầu trang. Người tạo là chủ doanh nghiệp mới.
5. Mời nhân viên tại **Tổng quan** trong Cài đặt. Tài khoản vẫn theo lời mời;
   không có đăng ký tài khoản công khai.

Chỉ chủ doanh nghiệp được đổi tên doanh nghiệp. Giới hạn bảo vệ ban đầu:
20 doanh nghiệp sở hữu/tài khoản, 10 lượt tạo/giờ. Không hỗ trợ xóa tại đây;
yêu cầu xuất/xóa dữ liệu có quy trình xác nhận riêng, chưa có bộ xóa tự động.

## 3. Tạo nhãn hàng và cập nhật hồ sơ

Chủ doanh nghiệp/quản trị viên tạo hoặc đổi tên nhãn hàng trong tab quản lý
mới. Mỗi doanh nghiệp tối đa 100 nhãn hàng. Tên được kiểm tra trùng không phân
biệt hoa/thường trong cùng doanh nghiệp; đổi tên không chuyển dữ liệu hoặc
cấp thêm quyền kết nối. Các API nhãn hàng cũ giữ nguyên chính sách hiện có;
không suy rằng màn hình mới thay đổi toàn bộ quyền legacy.

Mở **Kho tri thức → Thông tin doanh nghiệp / Thông tin nhãn hàng**:

1. Với nhãn hàng, chọn đúng tên cần xem.
2. Chủ doanh nghiệp/quản trị viên đọc hồ sơ hiện tại trước khi sửa.
3. Nhập mô tả, sản phẩm/dịch vụ, khách hàng, giọng thương hiệu, mục tiêu, chỉ số,
   nguồn lực, ngân sách, tiền tệ và múi giờ. Không nhập token/mật khẩu/secret.
4. Sản phẩm và mục tiêu: mỗi dòng một mục. Ngân sách/chỉ số chưa biết để trống,
   không thay bằng số 0. Tiền tệ dùng mã như VND; múi giờ như Asia/Ho_Chi_Minh.
5. Lưu tạo phiên bản hồ sơ, dùng chính nguồn của **Kế hoạch kinh doanh**.
   Kế hoạch/lượt chạy cũ giữ hồ sơ đã chốt, không tự đổi theo hồ sơ mới.

Hồ sơ không phải một kho bộ nhớ mới và không tự tạo kế hoạch. Người không có
quyền hồ sơ sẽ nhận thông báo, không được xem bằng cách đổi tab.

## 4. Skills và agent chuyên môn

Mở **Kho tri thức → Skills cho agent**. Đường dẫn cũ `/skills` chuyển về tab này.

Các nhóm: Thiết kế, Marketing, Biên tập ảnh/video, Quảng cáo, Nội dung, Phân tích,
Vận hành và Khác. Có tìm theo tên, lọc theo nhóm và agent của phiên bản đã công bố.
Nhóm là nhãn tổ chức thư viện, không phải bằng chứng đã có công cụ chuyên môn.
Biểu mẫu “Biên tập skill hoặc agent” nằm dưới danh mục; sau khi chọn Soạn/Mở,
cuộn xuống biểu mẫu để sửa. Chọn riêng nhóm chuyên môn để thu gọn danh sách.

1. Nếu chưa có agent hợp lệ, chọn **Soạn agent mới**. Điền tên, mã gọi duy nhất
   bằng chữ thường/số/gạch ngang và hướng dẫn chuyên môn.
2. Lưu bản nháp → Kiểm tra bản nháp → Duyệt phiên bản → Công bố phiên bản.
   Tự duyệt cần xác nhận rõ; duyệt/công bố chỉ dành cho chủ/quản trị viên.
3. Chọn **Soạn skill mới**, nhập tên/mã/hướng dẫn, nhóm và phiên bản agent đang
   được công bố trong cùng doanh nghiệp. Mẫu hệ thống cần sao chép bằng công cụ
   nâng cao trước khi chỉnh sửa.
4. Lưu bản nháp. Skill mới dùng đầu vào/đầu ra JSON có trường `text`.
   Mở **Kiểm tra dữ liệu mẫu — không gọi mô hình**, kiểm tra mẫu theo lược đồ.
   Đây không phải kiểm thử chất lượng AI.
5. Kiểm tra → duyệt → công bố skill. Chỉ lưu/gán nhóm chưa làm skill sẵn sàng chạy.
6. Đổi agent/hướng dẫn của skill tạo phiên bản nháp mới, giữ nguyên lược đồ,
   giới hạn công cụ và phiên bản đang sử dụng. Kiểm tra/duyệt/công bố lại nếu
   muốn dùng phiên bản mới. Lịch sử và công việc đã chốt không bị sửa.
7. **Lưu riêng nhóm thư viện** chỉ đổi nhãn phân loại; không đổi payload/hash
   thực thi hoặc agent. Lưu hướng dẫn trước nếu đang có bản nháp chưa lưu.

Quyền soạn kế thừa Studio: thành viên không phải người xem được tạo; sửa định
nghĩa của mình hoặc theo quyền chủ/quản trị viên. Quyền đọc danh mục không
thay thế quyền Brain, mô hình, công cụ, ngân sách, chính sách hay phê duyệt.
Skills ở phạm vi doanh nghiệp; quyền Brain riêng và nhãn hàng vẫn được kiểm
tra bởi các dịch vụ hiện có. Không gán một skill sang agent doanh nghiệp khác.

Các skill hiện dùng chế độ văn bản `llm_text`. Nhóm thiết kế/editor hỗ trợ
hướng dẫn, ý tưởng, mô tả và kịch bản; chưa tự tạo ảnh/video. Nhóm Ads không
tự chạy quảng cáo. Chọn model theo công việc dùng cơ chế phân công AI hiện có,
không hardcode hãng theo tên agent.

Công cụ nâng cao giữ nhập/xuất, sao chép, lưu trữ, lịch sử và khôi phục phiên
bản hiện có. Xuất JSON định nghĩa giữ payload thực thi; nhãn phân nhóm thư viện
là metadata riêng, chưa cam kết đi kèm mọi luồng xuất/import cũ.
Các Skills báo cáo có sẵn, xem trước chỉ đọc và đọc lại kết quả lịch sử vẫn
nằm trong mục mở rộng dưới thư viện.

## 5. Bộ nhớ cũ và xử lý lỗi

**Tri thức và bộ nhớ** giữ Brain, thư viện, tìm ngữ nghĩa, phạm vi nhãn hàng và
trạng thái bộ nhớ. Quyền riêng tư cũ không đổi; thêm hồ sơ/Skills không chia sẻ
bộ nhớ riêng với nhân viên khác.

Nếu mạng mất lúc lưu/tạo: không bấm gửi lại mù. Đọc lại danh sách/hồ sơ/mục
Skills, đối chiếu tên và phiên bản trước khi thao tác tiếp. Xung đột phiên bản
nghĩa là dữ liệu đã đổi; không ghi đè bằng dữ liệu cũ. Lưu tên cũng làm phiên
bản quản lý thay đổi, nên bản xem trước xuất dữ liệu cũ có thể cần chuẩn bị lại.

Lưu cấu hình, công bố định nghĩa, kiểm thử chất lượng mô hình và nghiệm thu
bằng dữ liệu thật là các việc khác nhau. Không có thao tác trong hướng dẫn này
tự bật kết nối thật, quảng cáo, gửi tin nhắn hoặc deploy công khai.
