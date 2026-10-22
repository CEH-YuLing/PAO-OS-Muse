# S5 — Hướng dẫn kế hoạch, công việc AI và báo cáo

Hướng dẫn tính năng source candidate đang nghiệm thu. Chỉ dùng khi quản trị đã
phát hành đúng schema và bật chức năng; lưu cấu hình không phải nghiệm thu live.
Không đưa khóa bí mật vào hồ sơ, brief hoặc kỹ năng. Màn hình này không thay thế
Cài đặt và kết nối theo SME. Đọc sổ S5 để biết bản đang chạy thực tế.

## Những khái niệm cần biết

- Doanh nghiệp/SME là ranh giới dữ liệu. Đổi SME không tự chuyển hồ sơ, quyền,
  model, Brain hoặc tiền giữa các doanh nghiệp.
- Nhãn hàng là phạm vi hồ sơ trong một SME. Hồ sơ chung không phải quyền đọc
  Brain riêng tư; chủ hai SME không tự được trộn dữ liệu của hai SME.
- Kế hoạch có phiên bản: lần lưu mới giữ lịch sử cũ. Thay hồ sơ/kế hoạch khiến
  phê duyệt nguồn cũ hết hiệu lực, không sửa ngầm công việc đã ghim.
- Chuyên môn (Nội dung/Sáng tạo/Quảng cáo/Phân tích), kỹ năng, model và công cụ
  là các cấu hình khác nhau. Chọn một model không cấp quyền công cụ.
- Bản nháp AI không phải bằng chứng đã kiểm chứng. “Hoàn thành” công việc nội bộ
  nghĩa là bản nháp đã được người có quyền duyệt, không phải chiến dịch đạt KPI.

## Điều kiện để bắt đầu

Quản trị cần phát hành schema S5 đã nghiệm thu, bật Business Planning, Studio,
Engine Contract và Chat Features; API/DB/Redis và worker dùng chung phải khỏe.
Không tự sửa cờ Meta/Google/Telegram hoặc dùng ứng dụng host làm quyền tenant.
Menu Kế hoạch kinh doanh chỉ hiện khi server xác nhận đã bật và bạn là owner/admin.
Nếu không thấy, liên hệ quản trị; không nhập lại secret hoặc dùng SME khác.

Ollama cần có đúng model đã cài và đang hoạt động. PAO kiểm tra qua admission
metadata hiện có khi khởi chạy; không tự tải model, chọn model khác hoặc chuyển
cloud khi máy local mất kết nối. Cloud cần cấu hình kết nối SME và grant model
đã kích hoạt cho chính người chạy, đúng nhãn hàng; thu hồi/đổi khóa sẽ chặn lượt
chạy cũ. Không nhập API key vào ô mã quyền model hoặc tham chiếu kết nối.

## Quy trình sử dụng

1. Chọn đúng doanh nghiệp ở thanh điều hướng, rồi chọn toàn doanh nghiệp hoặc
   nhãn hàng trong Hồ sơ. Nhập sản phẩm, giọng thương hiệu, người mua, nguồn lực,
   mục tiêu, KPI, ngân sách dự kiến, tiền tệ và múi giờ. Điều chưa biết để trống;
   không điền 0 để vượt hướng dẫn. Lưu phiên bản hồ sơ.
2. Soạn kế hoạch tháng: brief, các đầu việc, chuyên môn, hạn, tiêu chí nghiệm thu
   và phụ thuộc. Mã phụ thuộc phải tồn tại, không tạo vòng lặp hoặc hạn ngược.
   Lưu bản nháp trước khi duyệt.
3. Owner kiểm tra bản đã lưu, xác nhận tự duyệt/dữ liệu còn thiếu nếu có, rồi
   duyệt chuẩn bị nội bộ. Admin không tự trở thành người duyệt tài chính.
   Tạo công việc nháp để liên kết Project/Goal/Task hiện có; chưa gọi AI lúc này.
4. Trong Studio, tạo/kiểm tra trợ lý và kỹ năng văn bản, chạy fixture cấu trúc,
   duyệt và xuất bản bằng các bước hiện có. Không dùng seed chưa được clone/
   duyệt. Kỹ năng S5 nhận object có trường `text`; đầu vào do máy chủ ghép từ
   brief, tiêu chí, sản phẩm, giọng thương hiệu, đối tượng và kết quả phụ thuộc
   đã duyệt. Brain là ràng buộc ACL, không tự nạp toàn bộ Brain hoặc memory.
5. Trong Phân công AI: thêm lựa chọn provider/model, đặt trần token/output/time,
   chọn kỹ năng đã xuất bản cho mỗi chuyên môn. Model preference của trợ lý đã
   ghim phải tương thích; muốn đổi phải dùng phiên bản trợ lý được duyệt phù hợp.
   Cấp SME → nhãn hàng → trợ lý → bước quy trình → công việc chỉ thu hẹp quyền.
   Lưu cấu hình rồi dùng xem trước. Xem trước không gọi model hoặc giữ hạn mức.
6. Tại Vận hành, chọn công việc và model (hoặc kế thừa), nhập grant nếu dùng
   cloud. Xác nhận rõ lượt gọi AI. Một native Run/TaskAttempt được tạo nguyên tử;
   worker và sổ tài nguyên chung thực thi. Bấm Đọc lại để xem kết quả. Không
   bấm lặp khi mạng mất ACK; đọc lại để đối soát công việc đã tạo.
7. Owner đọc bản nháp, đối chiếu nguồn và tiêu chí rồi duyệt hoặc từ chối đúng
   hash kết quả. Duyệt kế hoạch không thay thế duyệt nội dung. Công việc phụ
   thuộc chưa được chạy nếu nội dung nguồn chưa được duyệt hoặc đã mất hiệu lực.
8. Chỉ dùng phần ngân sách/hành động mô phỏng để nghiệm thu. Chọn tài khoản/
   chiến dịch `mock:...`, trần, dự phòng an toàn, số đã chi lúc quan sát và tiền
   tệ. Nhập số chính xác, không dấu phân cách hàng nghìn; VND/JPY không có lẻ,
   USD/EUR/GBP có tối đa hai chữ số lẻ. Không cộng tiền khác loại hoặc suy đổi tỷ giá.
9. Tạo đề xuất từ bản nháp đã duyệt: hệ thống giữ hạn mức nguyên tử. Owner phải
   duyệt riêng hành động trước mô phỏng. Thành công chuyển khoản giữ thành chi
   mô phỏng; từ chối/hủy khi chưa thực hiện giải phóng hạn mức. “Chưa rõ” giữ
   nguyên khoản giữ, không tự thử lại hoặc tự giải phóng. Đối soát là ghi kết
   quả quá khứ, không gọi lại dịch vụ.
10. Tạo báo cáo nội bộ hoặc đặt lịch giờ/ngày. Lịch dùng owner P6 hiện có, ghim
    phiên bản nguồn và khử trùng slot; khi mất lượt, coalesce trong cửa sổ có
    giới hạn, không tạo hàng loạt báo cáo cũ. Không tự gửi Telegram/email.

## Gợi ý hướng dẫn cho bốn chuyên môn

Các đoạn sau là gợi ý dữ liệu định nghĩa, không tự được xuất bản hay cấp quyền.
Hãy kiểm tra chúng bằng nguồn sản phẩm thật của doanh nghiệp trước sử dụng.

| Chuyên môn | Nhiệm vụ của kỹ năng | Kết quả cần duyệt |
|---|---|---|
| Nội dung | Soạn bản nháp theo giọng thương hiệu, chỉ dùng dữ kiện đã cung cấp | Đúng tên/giá/ưu đãi, kênh, độ dài, nguồn và điều còn thiếu |
| Sáng tạo | Soạn ý tưởng hình/video, bố cục và brief sản xuất | Bám thương hiệu, không tự nhận đã tạo ảnh/video |
| Quảng cáo | Phân tích dữ kiện được cung cấp, đề xuất phân bổ | Không bịa KPI, không tự đổi ngân sách hoặc trạng thái Ads |
| Phân tích | Tổng hợp dữ kiện, nêu thiếu sót và mâu thuẫn | Phân biệt mục tiêu với số đã đo, số chưa biết không phải 0 |

Nên yêu cầu ít nhất hai câu hoàn chỉnh, kiểm tra từng chữ số của giá với nguồn,
nêu rõ thiếu thông tin khuyến mãi và không nói đã đăng nội dung. Model nhỏ đã
từng viết sai giá trong nghiệm thu; bộ kiểm chất lượng có lưu ca này. Kỹ năng
và schema chặt hơn giảm lỗi, không bảo đảm AI luôn đúng và không thay duyệt người.

## Điều kiện chặn và cách xử lý

| Tình huống | Cách xử lý |
|---|---|
| Chưa có kỹ năng/model phù hợp | Hoàn thành Studio publish và cấu hình routing đúng SME; không tự chọn model mặc định khác |
| Model local offline/chưa cài | Kiểm tra Ollama và tên model; không gửi lại lệnh liên tục hoặc chuyển cloud ngầm |
| Input schema/context quá lớn | Rút gọn brief/dữ liệu, dùng kỹ năng có schema phù hợp; native Run giới hạn prompt 2.000 ký tự, không tự cắt nguồn |
| Kế hoạch/hồ sơ đã đổi hoặc review hết hạn | Đọc lịch sử, lập phiên bản mới và duyệt lại; không repin task cũ |
| Lượt chạy lỗi/hủy/worker gián đoạn | Đọc lỗi/sổ usage và đối soát; không tự chạy lại tác vụ. Candidate hiện giới hạn một admission cho mỗi task của phiên bản kế hoạch |
| Dữ liệu ngân sách cũ, lệch currency, không đủ tiền | Không giảm kiểm soát để vượt gate; đây là tiền mô phỏng, không phải số dư provider |
| Đã duyệt nội dung nhưng chưa duyệt hành động | Duyệt riêng đề xuất; không dùng approval loại khác thay thế |
| Hành động chưa rõ | Giữ khoản giữ; chỉ đối soát kết quả được xác nhận, không retry bằng mã yêu cầu mới |
| Dừng khẩn cấp | Ngăn job/hành động mới và công bố kết quả; mở lại không hồi sinh pin cũ. Không hoàn tác chi phí đã phát sinh |
| Báo cáo thiếu doanh thu/Ads thực | Giữ measured/cost/quota chưa biết. Báo cáo tiến độ không chứng minh hiệu quả quảng cáo |

## Giới hạn của nghiệm thu S5 local

- Chỉ adapter văn bản; tạo ảnh/video, đăng social, chiến dịch Ads thật và giao
  báo cáo ra kênh ngoài cần adapter, quyền và nghiệm thu riêng.
- Sổ tiền này mô phỏng theo account/campaign/currency và kế hoạch. Nó không
  phải phí LLM hoặc chi tiêu Ads authoritative; chi tiêu provider có độ trễ.
- Màn Vận hành hiển thị phiên bản kế hoạch hiện hành. Trước khi sửa kế hoạch
  đã có đề xuất, hãy đối soát mọi khoản “chưa rõ” và hủy đề xuất chưa thực hiện.
  Nếu đã đổi phiên bản khi còn khoản giữ cũ, giữ mã hành động và nhờ quản trị
  đối soát qua API owner có kiểm quyền; không tự tạo ngân sách khác để bù hoặc
  xóa lịch sử. Lịch sử vận hành xuyên phiên bản bằng UI cần mở rộng trước pilot.
- Brain/cloud/capability không tương thích bị chặn. Chưa có automatic fallback.
- Có một model vật lý trên máy khi kiểm chất lượng; hai model/step được kiểm
  riêng bằng fixture. Không gọi fixture là hai provider thật đã nghiệm thu.
- Chỉ dữ liệu tổng hợp được dùng trong nghiệm thu; OAuth thật/HTTPS/reboot/
  production/pilot có người dùng là các gate khác, không suy ra từ HTTP200/build.
