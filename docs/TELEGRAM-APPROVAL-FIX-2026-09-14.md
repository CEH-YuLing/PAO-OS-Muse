# Sửa approval Telegram nhiều phần — 14/09/2026

Đã sửa lỗi F1 trong checklist: đề xuất dài/emoji được chia nhiều tin và nút nằm ở tin cuối, nhưng callback trước đây chỉ chấp nhận delivery suffix :0.

Callback hiện tra đúng peer, message ID đã gửi và prefix call/version, sau đó kiểm tra callback_data thực sự nằm trong inline keyboard đã lưu của tin đó. Vì vậy tin chứa nội dung nhưng không có nút không thể được dùng để giả mạo quyết định. Vẫn gọi service decide hiện có để kiểm tra ownership/role/expiry/version và chống quyết định lặp.

Không thay schema, payload nút hoặc nội dung đề xuất. Các đề xuất đã gửi trước bản sửa vẫn có thể bấm lại nếu đang pending và chưa hết hạn; không cần gửi lại nội dung.

Kiểm chứng: **66 backend tests đạt**, gồm 2 ca regression tham số hóa approve/reject cho email chứa 2000 emoji, chia hai tin. Kiểm tra tin đầu không có nút, sai version, sai sender và replay không tạo thêm quyết định/audit. Cả bộ chạy trong pao_test/Redis15 và Telegram adapter giả lập, không gửi email hoặc tin Telegram thử nghiệm ra ngoài. Cảnh báo pytest cache không ảnh hưởng kết quả.

Đã khởi động lại API và Telegram bridge để nạp bản sửa. Worker/model/web và dữ liệu được giữ nguyên. Chưa tuyên bố nghiệm thu thao tác bấm nút thật thay cho người dùng; các giới hạn recovery và deployment khác trong checklist vẫn còn.
