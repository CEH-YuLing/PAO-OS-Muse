# PAO — Bổ sung giao diện Tự động theo giờ thiết bị

Ngày21/10/2026. Phạm vi frontend local tại `F:\PAO-ACOS`, trước GD00.
Đây là bổ sung nhỏ, không phải hoàn tất GD03 hoặc nghiệm thu toàn hệ thống.

## Sử dụng

**Cài đặt và kết nối → Tổng quan → Giao diện hiển thị** có ba lựa chọn:

| Lựa chọn | Hành vi |
|---|---|
| Sáng | Luôn nền sáng, không phụ thuộc giờ |
| Tối | Luôn nền tối, không phụ thuộc giờ |
| Tự động | Từ06:00 đến trước18:00 dùng Sáng; từ18:00 đến trước06:00 dùng Tối |

Dùng giờ địa phương của **thiết bị/trình duyệt**, không giờ VPS, UTC hoặc giao diện OS.
Mặc định người chưa chọn vẫn Tối; lựa chọn Sáng/Tối cũ không bị đổi thành Auto.
Chỉ lưu `light`/`dark`/`auto` ở khóa không nhạy cảm `pao.ui.theme` của trình duyệt.
Không phải cấu hình đồng bộ giữa thiết bị hay cấp quyền doanh nghiệp.

Auto tính màu trước paint khi tải trang, đặt timer đến mốc06:00/18:00,
kiểm lại đồng hồ tối đa mỗi60giây khi tab hoạt động và kiểm ngay lúc focus,
pageshow hoặc tab trở lại visible. Tab ngủ bị trình duyệt trì hoãn timer sẽ
chuyển đúng trạng thái khi mở lại; không hứa timer chạy khi máy tắt/ngủ.
Các tab cùng origin đồng bộ qua storage event, không gọi API.

Nút mặt trời/mặt trăng cũ vẫn chuyển Sáng/Tối cố định. Khi đang Auto,
tooltip cho biết chế độ và màu đang dùng; bấm nút đó chuyển sang lựa chọn
cố định đối diện. Có thể bật lại Auto trong Settings.

## Thay đổi

- `apps/web/lib/theme.mjs` và `theme.d.mts`: tách lựa chọn khỏi màu được áp dụng,
  tính giờ/mốc chuyển, watcher có cleanup, bootstrap trước paint.
- `apps/web/lib/ThemeProvider.tsx`: lựa chọn thứ ba, trạng thái tiếng Việt,
  tự chuyển theo giờ, wake/focus và đồng bộ tab. Vẫn giữ nhãn nút đổi Sáng/Tối.
- `apps/web/app/theme.css`: card thứ ba, thông tin đang dùng và bố cục một cột
  trên điện thoại; không sửa palette cũ.
- `apps/web/lib/theme.test.mjs`: kiểm boundary, clock, persistence và bootstrap.

## Nghiệm thu

| Kiểm tra | Kết quả và giới hạn |
|---|---|
| Theme unit |19/19 đạt: trước/đúng06:00,18:00, qua ngày/năm, manual ổn định, wake/clock edit, stop timer, bootstrap24giờ |
| Toàn bộ Node tests frontend |228/228 đạt, bao gồm19theme; không cộng hai số thành tổng mới |
| Typegen/TypeScript/build production | Đạt trong source copy cách ly; frontend source không đổi trong lượt build |
| Bản cài Web3200 | Settings hiển thị3lựa chọn; manual Sáng/Tối đạt; Auto áp dụng đúng Sáng tại thời điểm kiểm |
| Reload | Giữ Auto và màu đúng, không biến lựa chọn thành light cố định |
| Cross-tab thật | Settings và tab `/join` đồng bộ manual Dark rồi Auto; tab thử đã đóng |
| Responsive | Kiểm bản cài với viewport hẹp; đo CSS viewport320px,3nút nằm trong khung, không tràn ngang; override đã reset |
| Chuyển đúng mốc giờ | Clock/timer giả lập trong unit, **không đổi giờ Windows** hoặc chờ đến18:00 thật |

Build receipt:
`.runtime/model-provider-tabs-frontend-bdf688d5fc6d47d08db4c901313de5d4/receipt.json`.
Backup5file trước sửa và ảnh installed desktop/mobile:
`.runtime/theme-auto-ed39542d93084a2d94cf59a0d61c76b5/`.

Không sửa backend/schema/contract/.env, không gọi model/quota hoặc lưu cấu hình
doanh nghiệp. Không chạy backend regression/database tests cho thay đổi này.
Web hiện chạy Next dev và nhận nguồn qua hot reload; không restart API/worker/Docker.
Trang xem trước cách ly không dùng database, được giữ làm fixture; process thử dừng riêng.
Receipt tổng hợp: `.runtime/theme-auto-ed39542d93084a2d94cf59a0d61c76b5/receipt.json`.
Cleanup đầu bị chốt danh tính từ chối do timestamp Int64 bị làm tròn khi qua JavaScript;
đã đọc lại timestamp chuỗi nguyên vẹn, kiểm executable/command rồi mới dừng đúng preview.
Không nới chốt và không dừng process PAO chính. Một patch tài liệu sai context được sửa lại,
không ảnh hưởng code hoặc kết quả build.

GD00 chưa triển khai. Thứ tự tiếp theo vẫn do
[master roadmap](PAO-MASTER-GAP-AND-ROADMAP.vi.md) sở hữu.

