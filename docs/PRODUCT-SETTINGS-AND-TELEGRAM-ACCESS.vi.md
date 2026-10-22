# Yêu cầu sản phẩm — Hướng dẫn tiếng Việt và quyền sử dụng Telegram

Chốt ngày 15/10/2026 theo yêu cầu người dùng. Áp dụng tại `F:\PAO-ACOS`.
Trạng thái: yêu cầu đã chốt; thiết kế chi tiết và các gate chưa triển khai không
được coi là đã nghiệm thu. [Master](PAO-MASTER-GAP-AND-ROADMAP.vi.md) vẫn sở hữu
thứ tự S3.2B → S3.2C → S3.3; không mở roadmap cạnh tranh hoặc làm lại S2.

**Cập nhật16/10:** S3 và S4 đã đạt local theo
[sổ S3](S3-COMPLETION-REGISTER.vi.md)/[sổ S4](S4-COMPLETION-REGISTER.vi.md);
tiếp theo S5 theo master. Các nhận định tiến độ ở dưới ghi lại thời điểm chốt
yêu cầu15/10, không phải lệnh triển khai lại; yêu cầu quyền/tiếng Việt vẫn hiệu lực.

## 1. Kết quả đối chiếu mã khi chốt yêu cầu — trước triển khai S3.2B

Cập nhật sau đó: [S3.2B đã source_verified](S32B-SCOPED-EXECUTION-2026-10-15.vi.md),
368affected/25Node/candidate0063; primary0060 chưa rollout. Các nhận định dưới
đây là snapshot lúc chốt yêu cầu, không phủ nhận store/identity/admission/outbox
đã triển khai sau đó. S3.3 pairing/team UI và Việt hóa Cài đặt vẫn chưa nghiệm thu.

- `modules/channels/api.py`: quản lý kênh giới hạn owner/admin; tạo binding cá
  nhân yêu cầu actor là chính người tạo, chưa phải màn hình mời/liên kết đội ngũ.
- `modules/channels/service.py`: kiểm tra binding, người dùng còn hoạt động,
  thành viên, chặn viewer, kiểm quyền Brain và kiểm lại run. Nhánh connection
  riêng hiện trả `telegram_connection_transport_pending`, không phải đã có
  bot nhiều doanh nghiệp hoạt động trọn vẹn.
- S3.1A+B đạt local theo register; S3.2A kernel đã source_verified nhưng chưa
  nối worker/API hoặc lưu credential. S3.2B/C và giao diện S3.3 còn mở.
- Settings đã có hướng dẫn từng phần từ S2.3, nhưng chưa thuần tiếng Việt.
  `SettingsWorkspace.tsx` còn các nhãn như General, Integrations, Cloud Models
  & Voice, Safety & Approvals, System Status và thông báo trộn thuật ngữ.
  Đây là tồn tại quan sát từ mã, không phải kết quả audit toàn bộ giao diện.

## 2. Telegram: yêu cầu bắt buộc và phạm vi thiết kế

### 2.1. Ranh giới bot, người dùng và nơi nhận báo cáo

- Một bot chỉ thuộc một doanh nghiệp; một doanh nghiệp có thể có nhiều bot và
  nhiều thành viên. Không tự chuyển bot hoặc dùng token của doanh nghiệp khác.
- Token xác thực bot với Telegram; không phải mật khẩu chung cho nhân viên.
  Chỉ nhập trong trường bí mật của giao diện được phép, mã hóa phía server,
  không trả token về trình duyệt, log, hội thoại hoặc bản hướng dẫn.
- Telegram user ID dạng số và chat ID được kiểm tra riêng; username có thể đổi,
  tên hiển thị, /start hoặc quản trị nhóm Telegram không cấp quyền trong PAO.
- Người điều khiển, người cấu hình kết nối, người duyệt và đích nhận báo cáo
  là bốn khái niệm khác nhau. Nhận báo cáo không tự có quyền giao việc.
- Hội thoại riêng tách theo người/bot/doanh nghiệp; tài nguyên chia sẻ cần quyền
  nhãn hàng/Brain. Một người thuộc hai doanh nghiệp không được trộn bộ nhớ.

### 2.2. Luồng liên kết người dùng dự kiến cho S3.3

1. Đăng nhập PAO, chọn đúng doanh nghiệp và kiểm tra thành viên hiện hành.
2. Tạo mã/liên kết một lần có thời hạn, pin người dùng/doanh nghiệp/kết nối và
   phiên bản cấu hình. Hạn chế tốc độ; không nhúng JWT, token bot hoặc dữ liệu
   riêng vào URL. Lưu bằng chứng an toàn, không lưu/in mã bí mật rõ trong log.
3. Người dùng mở đúng bot, xác nhận danh tính và phạm vi; backend kiểm tra mã,
   nguồn gửi, hết hạn, replay và tiêu thụ nguyên tử. Link bị chuyển tiếp không
   được tự gán người lạ; xác nhận lại trong PAO bằng phiên đăng nhập tương ứng.
4. Chỉ có quyền sau khi grant rõ ràng được cấp bởi người có quyền quản trị.
   Tự liên kết danh tính không tự tạo membership, nâng vai trò hay bật công cụ.
5. Cho phép xem liên kết, thu hồi và liên kết lại có audit; không tự nhập lịch
   sử cũ. Khởi đầu ưu tiên chat riêng; nhóm phải có thiết kế quyền/đích riêng.

Luồng này là thiết kế cần triển khai/kiểm thử, không phải mô tả tính năng đã có.

### 2.3. Phân quyền theo khả năng, không chỉ tên vai trò

Tái sử dụng quyền hiện có; không thêm vai trò database chỉ từ bảng đề xuất.
Chủ doanh nghiệp/quản trị viên cấu hình trong phạm vi được phép. Người thực thi
chỉ giao việc theo nhãn hàng/Brain/công cụ được cấp. Quyền đọc/phân tích và đăng
ký nhận báo cáo không cấp quyền thực thi. Viewer hiện bị chặn ở đường actor;
không được quảng bá đã có đăng ký báo cáo read-only cho viewer qua bot.

Quyền duyệt tách khỏi quyền cấu hình bot, pin hành động/tài khoản/nội dung/hạn
mức/thời hạn. Các thao tác nhạy cảm trước mắt đi qua dashboard có xác thực.
Chăm sóc khách hàng không kế thừa quyền chủ bot; giữ profile grounding/no-tools
hiện có, ưu tiên bot riêng với phạm vi rõ khi triển khai.

S3.2B/C phải kiểm lại actor/membership/grant/Brain/destination/generation khi
nhận, chạy việc và gửi kết quả. Thu hồi chặn thao tác tiếp theo, không hứa thu
hồi được tin đã gửi hoặc hành động provider đã nhận. Mất ACK phải đối soát,
không tự gửi lại. Không fork hàng đợi, approval hoặc agent engine.

### 2.4. Gate cần ghi bằng chứng trước khi đóng S3

- Hai doanh nghiệp/hai bot dùng cùng Telegram user/chat/update ID vẫn cách ly.
- Không liên kết, mã sai/hết hạn/replay/chuyển tiếp, người dùng bị khóa hoặc rời
  doanh nghiệp đều không được cấp quyền. Người thiếu quyền không bị lộ dữ liệu.
- Kiểm thử chủ/quản trị/người thực thi/viewer; quản trị nhóm Telegram không có
  membership bị chặn; quyền đọc/nhận báo cáo không thể chạy công cụ hoặc duyệt.
- Brain riêng, nhãn hàng khác, đổi vai trò/thu hồi khi đang chờ và trước gửi
  đều có test từ chối; không chuyển kết quả sang chat hoặc bot khác.
- Rotate/disconnect/restart/no-resend, lịch báo cáo và thu hồi phải đi qua
  adapter/worker thật với HTTP fixture; bot thật là gate external riêng.
- Browser kiểm thử liên kết/thu hồi/phân quyền, hướng dẫn tiếng Việt và không
  hiện token. Không đánh dấu toàn S3 đạt chỉ bằng test metadata kernel.

## 3. Tiếng Việt là ngôn ngữ giao diện PAO

Áp dụng toàn bộ giao diện khách hàng, không chỉ Telegram: điều hướng, tiêu đề,
nút, trợ giúp, placeholder, xác nhận, quyền, trạng thái, lỗi và trợ năng.
Tên hãng/sản phẩm như PAO, Telegram, Meta Ads, Ollama, OAuth, API được giữ khi
cần nhận diện và giải thích bằng tiếng Việt. Giữ nguyên dữ liệu khách nhập,
model ID, URL, lệnh, credential và mã API; dịch lớp hiển thị, không đổi contract.

Từ ngữ thống nhất: Settings → Cài đặt; Workspace → Doanh nghiệp; Brand → Nhãn
hàng; Brain → Kho tri thức; Integrations → Kết nối; Approval → Phê duyệt;
Owner → Chủ doanh nghiệp; Admin → Quản trị viên; Viewer → Người xem.
Không đổi nghĩa dữ liệu cũ hoặc coi tất cả Brain đều là kho dùng chung.

Lỗi cần có: việc gì xảy ra, cấu hình có đổi không, bước khắc phục và khi nào cần
quản trị viên hỗ trợ. Không hiển thị nguyên lỗi provider có khả năng chứa secret.
Mã tra cứu kỹ thuật có thể ở phần chi tiết, không thay lời hướng dẫn tiếng Việt.

## 4. Mẫu hướng dẫn bắt buộc cho mọi nhóm Cài đặt

1. Mục đích: dùng để làm gì, dành cho ai, thuộc cá nhân/doanh nghiệp/máy chủ nào.
2. Chuẩn bị: tài khoản/quyền cần có, điều kiện dịch vụ và phí nếu có; không hứa
   thuê bao chat thay thế quota API hoặc model đồng nghĩa được dùng công cụ.
3. Từng trường: tên tiếng Việt, bắt buộc/tùy chọn, ý nghĩa, định dạng, lấy ở đâu,
   liên kết tài liệu chính thức và ví dụ giả không dùng được như secret thật.
4. Các bước đánh số: nhập/kết nối, chọn tài khoản hoặc nơi nhận, chọn nhãn hàng,
   phân quyền, lưu, kiểm tra, xác nhận rồi mới bật khi đủ điều kiện.
5. Phân biệt rõ: Đã lưu cấu hình / Đã kiểm tra kết nối / Đang bật / Đã nghiệm thu
   thực tế. Lỗi đọc trạng thái là Chưa xác minh, không tự nhận đã kết nối.
6. Quyền và bảo mật: ai xem/sửa, việc lưu hoặc kiểm tra có gọi ra ngoài không,
   dữ liệu nào được gửi, trường bí mật che/mất sau lưu và không yêu cầu qua chat.
7. Xử lý sự cố: thiếu quyền, định dạng sai, khóa hết hạn, dịch vụ chưa hỗ trợ,
   timeout/kết quả chưa rõ; không hướng dẫn nhập lại hoặc gửi lại mù.
8. Vòng đời: đổi khóa/thu hồi/ngắt kết nối ảnh hưởng ra sao đến việc đang chờ,
   báo cáo/lịch, dữ liệu đã lưu và cách kiểm tra lại sau thay đổi.

Phạm vi tối thiểu phải rà: tài khoản/đội ngũ, quota, quyền kết nối, model local/
cloud, MCP, Meta/Google Ads, Telegram, giọng nói, an toàn/phê duyệt và trạng thái
hệ thống. TikTok hoặc chức năng chưa triển khai phải nói rõ chưa dùng được,
không tạo form nhập khóa làm người dùng tưởng đã có connector.

## 5. Triển khai và nghiệm thu, không thay thứ tự hiện hành

- S3.2B: lưu và kiểm quyền đúng phạm vi theo mục 2; không mở UI kích hoạt sớm.
- S3.2C: nối worker/đích/báo cáo, test thu hồi và cách ly đầy đủ theo mục 2.4.
- S3.3: giao diện thiết lập Telegram và liên kết đội ngũ; đồng thời kiểm kê,
  Việt hóa và bổ sung hướng dẫn các nhóm Cài đặt hiện có theo mục 3–4, từng
  nhóm một. Không mở lại nghiệm thu S2 cũ hoặc tuyên bố cả sản phẩm đã Việt hóa.
- Các màn hình mới từ đây dùng tiếng Việt ngay; phần còn lại của PAO được kiểm
  kê và xử lý theo checkpoint liên quan, không sửa hàng loạt backend/frontend.
- Gate: ma trận từng nhóm màn hình/trường/trạng thái với bằng chứng; test ánh
  xạ thông báo và browser các luồng liên quan, lỗi/quyền/đổi SME/mobile; typecheck
  và build cho release giao diện. Giữ selector kiểm thử dựa trên ID ổn định.
  Không thay flag, quyền thực thi hoặc gọi provider chỉ để giao diện báo xanh.

Lượt chốt yêu cầu này chỉ đổi tài liệu/quy tắc. Chưa đổi giao diện, backend,
database, `.env`, dịch vụ đang chạy hoặc kết nối Telegram thật.
