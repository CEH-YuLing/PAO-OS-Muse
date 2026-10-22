# S6.2 — Hướng dẫn tài khoản, nhân viên và dữ liệu

17/10/2026. Áp dụng cho tính năng lifecycle0071; chỉ dùng trên phiên bản đã
nghiệm thu tương ứng. Hướng dẫn không thay bằng chứng test hoặc production gate.

## 1. Tìm khu vực sử dụng

Vào **Cài đặt và kết nối → Tổng quan → Tài khoản, nhân viên và dữ liệu**.
Chọn đúng doanh nghiệp trên thanh trên cùng trước mọi thao tác. Dữ liệu cũ của
panel bị bỏ khi chuyển doanh nghiệp. Một người có thể có vai trò khác ở SME khác.

- Mọi tài khoản tự xem/thu hồi phiên đăng nhập của mình.
- Chỉ owner/chủ doanh nghiệp được mời, quản lý thành viên và tạo yêu cầu dữ liệu.
- Admin không phải owner; owner SME không phải quản trị viên máy chủ.
- Chưa có chuyển chủ, đăng ký công khai, gửi lời mời email/Telegram tự động hoặc
  reset mật khẩu. Gặp vấn đề tài khoản cần quy trình quản trị có kiểm soát;
  không gửi mật khẩu, token hay mã mời cho AI trong chat.

## 2. Mời người vào doanh nghiệp

1. Kiểm tra tên doanh nghiệp, nhập email người nhận và chọn vai trò.
2. Bấm **Tạo mã mời**. Mã có hiệu lực24giờ, dùng một lần, chỉ hiển thị lần này.
3. Chuyển mã qua kênh riêng tin cậy. Tạo mã không đồng nghĩa đã gửi cho người nhận.
4. Người nhận mở `/join`, nhập email/mã và đặt mật khẩu mới tối thiểu12ký tự
   nếu chưa có tài khoản. Có tài khoản rồi phải đăng nhập đúng tài khoản trước.
5. Nhận thành công không tự đăng nhập; đăng nhập lại để cập nhật danh sách SME.

Mã không nằm trong URL/query, lịch sử liệt kê hoặc log. Nếu mất mã hoặc response
không rõ kết quả, đọc danh sách, thu hồi lời mời cũ và tạo lại; không có nút đọc
lại mã plaintext. Backend lưu hash, kiểm lại owner và thời hạn khi nhận.

Không thể mời owner; vai trò của lời mời được chủ doanh nghiệp quyết định, người
nhận không thể tự chọn nâng quyền. Code sai/email sai/hết hạn/đã dùng hoặc account
không khớp đều bị từ chối. Nhiều lần thử có thể bị rate-limit; không tự thử liên tục.

## 3. Đổi vai trò hoặc gỡ thành viên

Bấm **Đọc thành viên** để lấy danh sách đầy đủ theo trang, khác với danh sách
đủ điều kiện kết nối ở panel cũ (có bộ lọc loại vai trò).

- Đổi vai trò cần xác nhận. Cấp quyền kết nối/Brain chia sẻ và liên kết kênh cũ
  trong SME này bị thu hồi; phải kiểm tra/cấp lại rõ ràng khi cần.
- Gỡ nhân viên chỉ gỡ membership SME này, không vô hiệu User toàn hệ thống.
  Quyền và dữ liệu của cùng tài khoản ở doanh nghiệp khác được giữ.
- Brain riêng và lịch sử không bị xóa; grants chia sẻ trong SME bị gỡ để không
  làm hỏng khóa ngoại. Các công việc đang chạy được yêu cầu dừng và kiểm lại quyền.
- Telegram peer/pairing/binding và cấp quyền kết nối liên quan bị vô hiệu theo
  SME; reinvite không tự kích hoạt lại grant hoặc kênh cũ.
- Side effect đã gửi tới provider không thể thu hồi bằng cách gỡ người. Hành động
  sending/unknown phải đối soát riêng; không nhấn thử lại mù quáng.

Không sửa/xóa owner hoặc chuyển chủ qua thao tác này. Không dùng gỡ thành viên
để thay quy trình xóa dữ liệu hoặc vô hiệu toàn tài khoản.

## 4. Phiên đăng nhập

- **Đọc phiên đăng nhập:** thông tin thời gian, phiên hiện tại và trạng thái;
  không hiển thị token/hash. Danh sách giới hạn100phiên gần nhất còn thời hạn.
- **Thu hồi phiên:** chỉ phiên được chọn. Phiên khác của bạn không bị đăng xuất.
- **Đăng xuất phiên hiện tại:** máy chủ ghi thu hồi trước khi giao diện bỏ token.
  Nếu không liên lạc được máy chủ, không coi việc đóng trình duyệt là đã revoke.
- **Đăng xuất tất cả phiên:** yêu cầu xác nhận, ảnh hưởng mọi phiên tài khoản trên
  mọi SME. Phải đăng nhập lại bằng mật khẩu; không đổi JWT secret của máy chủ.

Browser/SSE kiểm lại trạng thái session; token cũ bị từ chối sau revoke. Logout
không phải lệnh hủy công việc nền đã được chấp nhận hoặc ngắt bot lâu dài. Công
việc/kênh vẫn phải có quyền nghiệp vụ hiện tại; muốn dừng việc thì dùng lệnh dừng,
muốn gỡ quyền SME thì dùng quản lý thành viên hoặc quyền kết nối.

Token trước0071 vẫn được chấp nhận nếu còn hợp lệ; có thể chưa có hàng trong
danh sách phiên. Đăng xuất hiện tại vẫn thu hồi được token này; logout-all chặn
mọi token phiên bản xác thực cũ. Không làm mất dữ liệu cũ để ép đăng nhập lại.

## 5. Xuất dữ liệu theo phạm vi

1. Chọn nhóm dữ liệu nghiệp vụ và/hoặc Brain mình có quyền đọc.
2. Bấm **Tạo và tải bản xuất**; tải JSON riêng tư có xác thực.
3. Có thể tải lại trong15phút qua lịch sử yêu cầu; quyền được kiểm lại mỗi lần.

Danh mục nghiệp vụ: nhãn hàng, dự án, mục tiêu, task, hồ sơ/phiên bản hồ sơ,
kế hoạch/phiên bản kế hoạch, job/budget/action/report theo các cột được công bố
trong bản xuất. Hồ sơ/kế hoạch có nội dung được lọc khóa xác thực. Brain đã chọn
có file hiện tại dạng base64 và ghi chú hiện tại; đây không phải export lịch sử
toàn DB. Giới hạn2.000bản ghi/2MiB; phạm vi vượt giới hạn bị từ chối, không cắt
ngầm rồi nói đã xuất đủ. Brain lớn dùng export Brain chuyên biệt.

Loại trừ thông tin xác thực hệ thống, token/password hashes/ciphertext kết nối,
private chat, audit bất biến, backup hạ tầng, raw execution JSON không nằm trong
danh mục và dữ liệu doanh nghiệp khác. Owner không tự được đọc Brain riêng của
nhân viên. Dữ liệu nhạy cảm do bạn tự nhập trong tài liệu vẫn cần tự rà trước khi
chia sẻ bản xuất; tải về không đồng nghĩa được phép công bố cho người khác.

Bản lưu trên DB được mã hóa bằng khóa máy chủ, không lưu file public. Hết thời
hạn thì không tải được; **hết hạn tải không tự xóa dữ liệu**. Thay khóa mã hóa
có thể làm bản xuất cũ không đọc được; tạo bản mới sau khi quyền/khóa đúng.

## 6. Yêu cầu xóa — không tự thực thi

1. Bấm **Xem trước phạm vi yêu cầu xóa**, đọc nhóm dữ liệu/số lượng và ngoại lệ.
2. Bấm **Tạo yêu cầu — chưa xóa**, xác nhận lần đầu.
3. Bấm **Xác nhận yêu cầu — không tự xóa**, xác nhận riêng lần thứ hai.

Preview gắn scope, hash dữ liệu và phiên bản membership doanh nghiệp; quyền
đọc Brain được kiểm tra hiện tại mỗi lần. Preview hết hạn sau15phút.
Nếu dữ liệu hoặc membership thay đổi, cần xem trước lại. Không thể dùng mã/hash
của yêu cầu khác hoặc của người khác. Lịch sử ghi preview/request/confirmation.

Trạng thái confirmed nghĩa là chủ doanh nghiệp đã xác nhận yêu cầu để quản trị
xem xét, **không phải dữ liệu đã xóa**. Chưa có executor purge SME. Audit, backup,
account chung ở SME khác, job đang chạy và hành động chưa rõ kết quả cần xử lý
riêng theo quy trình được duyệt. Không tắt trigger audit để xóa cho nhanh.

## 7. Retention và lỗi thường gặp

- Tự dọn nội dung kênh mặc định tắt trong cấu hình SaaS. Mốc retention_days cũ
  không tự bật xóa; `collect()` khi channels tắt cũng không được purge mặc định.
  Cờ host `CHANNEL_RETENTION_ENABLED` không phải tùy chọn khách hàng được tự bật.
-403/404: kiểm tra đúng SME, vai trò, Brain grant và tài khoản; không đổi sang
  quyền owner của SME khác để thử.
-409: phiên bản/preview cũ, lời mời đã dùng hoặc trạng thái không đúng; đọc lại,
  không gửi lại hành động xóa/remote theo suy đoán.
-413: giảm phạm vi;2MiB/2.000records là giới hạn, không phải xuất toàn hệ thống.
-422: kiểm tra email/code/field; lỗi không phản chiếu mật khẩu hoặc mã mời.
-429: chờ hết hạn rate-limit; không lặp gửi liên tục.
-503khóa mã hóa: quản trị kiểm tra secret store; SME không nhập khóa máy chủ vào
  form hoặc chat. Không tự thay khóa nếu còn dữ liệu mã hóa đang dùng.

## 8. Không thuộc nghiệm thu giai đoạn này

Public signup, thanh toán/billing, reset mật khẩu tự phục vụ, chuyển owner,
provider/OAuth/Ads/Telegram thật, production HTTPS/host/reboot/DR và pilot thật.
Không dùng local lifecycle acceptance để tuyên bố các phần đó đã hoàn tất.
