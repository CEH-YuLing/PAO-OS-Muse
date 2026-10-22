# P7.5 — Nghiệm thu tiếng Việt trên thiết bị thật

Đây là bộ câu và cách kiểm tra, **không phải kết quả nghiệm thu**. Browser dùng
WebAudio tổng hợp và benchmark SAPI không thay thế giọng người/microphone thật.
Không tự mở microphone, lưu bộ audio hoặc gửi audio ra cloud.

## Chuẩn bị một lần

1. Chọn máy thử local và microphone của người đồng ý tham gia. Giữ Telegram,
   Meta, tools, Goal và workflow thật tắt; chỉ dùng câu hỏi vô hại dưới đây.
2. Engine STT phải có model local; TTS cần giọng tiếng Việt phù hợp. Máy hiện tại
   chỉ có SAPI English nên phần chất lượng TTS tiếng Việt đang **chưa đạt**.
3. Owner bật riêng `VOICE_ENABLED` và `VOICE_TURNS_ENABLED` khi bắt đầu nghiệm
   thu; không bật kênh ngoài. Không chép hoặc chia sẻ các dòng secret trong `.env`.
   Khởi động lại API/worker bằng launcher của ACOS sau khi idle checker đạt.
4. Mở PAO AI, chọn hội thoại thử, mở Activity (mobile: nút microphone), đọc và
   chọn đồng ý xử lý audio local/lưu transcript. Chỉ sau đó bấm “Nói với PAO”.
5. Thử từ chối quyền mic trước; không được tự thu âm. Cấp lại quyền trong browser,
   nói một câu, dừng nghe và kiểm tra transcript rồi mới xác nhận gửi.

## Hai lượt đọc, mỗi lượt 20 câu

Lượt A trong phòng yên tĩnh. Lượt B dùng môi trường ồn/echo tự nhiên và ghi rõ
điều kiện; không mở dịch vụ âm thanh bên ngoài để tạo nhiễu. Người kiểm thử đọc
đúng câu, ghi transcript máy nhận và turn ID. Không dùng quảng cáo/dữ liệu thật.

1. Xin chào PAO.
2. Hôm nay tôi cần làm những việc gì?
3. Hãy tóm tắt ghi chú thử nghiệm này.
4. Đừng gửi bất kỳ tin nhắn nào ra ngoài.
5. Tôi muốn kiểm tra một hội thoại mới.
6. Đây là bản nháp, chưa được phê duyệt.
7. Hãy phân biệt kế hoạch với kết quả đã kiểm chứng.
8. Tôi có ba công việc cần ưu tiên trong tuần này.
9. Ngày mười tháng mười năm hai nghìn không trăm hai mươi sáu.
10. Cuộc họp bắt đầu lúc chín giờ ba mươi phút sáng.
11. Giá trị thử nghiệm là một triệu hai trăm năm mươi nghìn đồng.
12. Tỷ lệ chuyển đổi giả lập là hai phẩy năm phần trăm.
13. Chi phí trên mỗi đơn hàng trong ví dụ là một trăm nghìn đồng.
14. Doanh thu giả lập là mười hai triệu đồng.
15. Giữ nguyên quyền đọc và không thay đổi ngân sách.
16. Tôi muốn tìm tài liệu hướng dẫn đổi trả sản phẩm.
17. Nếu không có nguồn đáng tin cậy thì hãy nói rằng chưa đủ dữ liệu.
18. Bản chép lời phải thuộc đúng hội thoại đang mở.
19. Sau khi tải lại trang, không tự bật microphone hay phát lại câu trả lời.
20. Kết thúc lượt thử nghiệm và dừng nghe.

Số viết bằng chữ ở đây giúp ground truth rõ ràng. Có thể thêm tên riêng/thuật ngữ
do người tham gia cung cấp; không ghi thông tin khách hàng thật vào bộ kiểm thử.

## Ghi kết quả, không tự nới gate để đánh dấu đạt

Mỗi câu: thiết bị/browser, lượt A/B, ground truth, transcript, turn ID, STT
latency, thời gian tới audio đầu tiên và lỗi. Tính WER sau normalize NFC,
lowercase/whitespace; giữ cả bản gốc để xem lỗi dấu, số và tên riêng. WER có thể
vượt 1 do insertion. Báo median/p95 cho latency, không chỉ lấy câu nhanh nhất.
Đo baseline trước, ghi threshold chấp nhận trước lượt nghiệm thu tiếp theo;
không tuyên bố realtime chỉ vì transcript không rỗng.

## Các ca lifecycle bắt buộc

- Mute: không thu mic hoặc tiếp tục phát audio.
- Cancel giữa STT: kết quả muộn không thành transcript gửi tự động.
- Cancel giữa Run: dùng luồng hủy chung; không cam kết rollback tool đã thực thi.
  Việc hủy tool thực tế chỉ thử bằng fixture vô hại, không bật tool thật.
- Barge-in trong TTS: chỉ mở mic monitor khi có consent và bật ngắt lời; dừng
  audio cũ, không tạo hai Run hoặc ghi nhầm hội thoại.
- Đổi session/đóng panel: dừng tracks/audio; không phát kết quả cũ vào session mới.
- Reload/reconnect: khôi phục đúng draft, không tự bật mic, gửi lại hoặc phát TTS.
- Kiểm tra cleanup file tạm và transcript policy; không lưu raw audio làm dataset.
  Crash/power-loss cleanup là gate production riêng, chưa được chứng minh local.

Chỉ đóng P7.5 khi có kết quả mic thật, quality tiếng Việt, noise/echo và lifecycle
đạt. Nếu STT/TTS chưa đạt, giữ voice tắt và ghi rõ nguyên nhân. Sau nghiệm thu,
owner tắt lại hai voice flags nếu chưa muốn sử dụng hằng ngày.
