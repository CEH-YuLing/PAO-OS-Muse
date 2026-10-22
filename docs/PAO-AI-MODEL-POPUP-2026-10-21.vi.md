# PAO AI — Popup chọn mô hình theo nhà cung cấp

Ngày: **21/10/2026**. Phạm vi: frontend PAO AI; không thay backend/contract/schema,
cấu hình provider, dữ liệu doanh nghiệp hoặc quyền công cụ.

## Đã triển khai

- Nút chọn mô hình ở đầu khung chat lớn hơn, có nhãn **Mô hình đang chọn** và
  hiển thị **nhà cung cấp — model — mức suy luận** nếu đã lưu mức suy luận.
  CLI và API được phân biệt, ví dụ `Codex — gpt-6-astra`, `API-OpenAI — <model>`.
  Giữ nguyên model ID do nhà cung cấp/server trả về, không đổi ID khi gửi API.
- Popup top-layer ở giữa viewport, hai tab: **Kết nối qua Client** rồi **Kết nối qua API**.
- Client:4ô **Codex, Claude, Antigravity, Muse**. API:4ô **OpenAI, Claude,
  Google Gemini, OpenRouter**. Desktop2cột, màn hình nhỏ1cột; danh sách dài có cuộn.
- Tìm theo tên hiển thị, model ID hoặc nhà cung cấp. Danh sách lấy từ `/v1/engines`
  và nguồn/quyền cũ khi cần, không gắn danh sách model ví dụ thành dữ liệu thật.
- Chọn model bằng radio, mức suy luận theo metadata đúng **model và resource**;
  không tự giả định hỗ trợ effort. Lựa chọn mới chưa đổi header cho tới khi bấm
  **Áp dụng mô hình** và PUT thành công. Thành công đóng popup, trả focus về nút.
- Giữ contract/version/source ID của lượt chọn cũ. Không trộn resource khi nhiều
  nguồn có cùng provider/model; legacy grant/personal/enterprise và Ollama không bị bỏ.
- Nguồn đang lưu nhưng không còn trong catalog vẫn hiển thị để đối chiếu, không
  được giả định là nguồn khả dụng. Không tự fallback, đăng nhập CLI hoặc gọi model.
- Các giải thích kỹ thuật gom vào phần mở rộng; giữ cảnh báo nguồn tri thức đang
  ghi đè chat. Lựa chọn bị khóa khi lượt chạy đang xử lý hoặc đang lưu.
- Giữ cửa sổ Hội thoại/quyền riêng tư và lịch sử chat ở vị trí hiện có.

## Phân biệt giao diện với tích hợp thật

Backend hiện chỉ công bố engine chat cho `ollama`, `codex_cli` và4nhà cung cấp API.
Việc có ô Claude Client/Antigravity không mở thêm engine hoặc vượt điều kiện tài khoản;
khi không có danh mục khả dụng, ô báo rõ chưa khả dụng. **Muse chưa có adapter**, ô là
vị trí chờ có ghi **Chưa triển khai**, không có model giả hoặc nút đăng nhập giả.

Kiểm tra trực tiếp trên tab Chrome PAO AI đã thấy popup Client bốn ô và header
`Codex — gpt-6-astra`; ở thời điểm quan sát, model Codex đã lưu không xuất hiện
trong catalog khả dụng nên hiển thị cần kiểm tra lại nguồn. Đây không phải
nghiệm thu quota Codex hoặc xác nhận client đã mất đăng nhập.
Tab người dùng có thay đổi trang trong lúc kiểm tra; không khôi phục/ghi đè dữ liệu
hoặc dùng phiên đó để thử lưu model. Các bài lưu lựa chọn thực hiện trong fixture riêng.

## Bằng chứng kiểm thử

| Kiểm tra | Kết quả |
|---|---|
| Unit helper mới |10/10; phân nhóm, labels, source pins, effort riêng mỗi resource, stale current, legacy, tìm kiếm và không mutate input |
| Toàn bộ frontend Node |**238/238**, đã bao gồm10test mới, không cộng lần nữa |
| Typegen/TypeScript/production build |Đạt trong source copy riêng; không thay output đang phục vụ |
| Browser Codex dùng chung |Đạt; model và effort high lưu đúng resource/version |
| Browser Codex cá nhân cũ |Đạt; giữ personal source ID và contract legacy |
| Browser OpenAI |Đạt; model có/không có effort, reset effort khi đổi model, API prefix đúng |
| Browser OpenRouter |Đạt; lưu model/effort và quyền riêng tư không đổi |
| Responsive/theme/keyboard |Mỗi profile đều dark/light ×1600/1024/768/390/320; hai tab, tìm kiếm, Enter/Escape, đóng trả focus; popup không làm dịch khung tin nhắn |
| Cách ly fixture |Toàn bộ `/v1` giả lập, chặn origin ngoài;0request chuyển đến backend/provider; mỗi profile chỉ2PUT giả lập cho model và cấu hình chat |

Build receipt: `.runtime/model-provider-tabs-frontend-24d75d5dc9e342be968b771b2a2404b8/receipt.json`.
Browser receipts và ảnh:

- `.runtime/chat-controls-browser-1792559727742`: Codex dùng chung.
- `.runtime/chat-controls-browser-1792559798360`: OpenAI.
- `.runtime/chat-controls-browser-1792559815361`: Codex cá nhân cũ.
- `.runtime/chat-controls-browser-1792559829675`: OpenRouter.

Không chạy lại backend regression/database tests; không gọi inference thật, thay secret,
migrate, restart process, push Git hoặc deploy. Next dev nhận thay đổi frontend qua HMR.
Không tạo/chuyển backup mới trong lượt UI; quy ước backup vẫn do
`infra/backup-storage.json` và `docs/BACKUP-STORAGE.vi.md` sở hữu.

Đây là lát cắt UX đã nghiệm thu, **không đánh dấu toàn bộ GD01/GD03 hoàn tất**.
Kết nối AI dùng xuyên Chat/Agent/Job và điều kiện từng CLI vẫn theo master roadmap.

## Cập nhật khung và chữ theo ảnh mẫu —21/10

Chỉ sửa trình bày nút model và bố cục header, không đổi dữ liệu, sự kiện chọn,
popup, API, quyền sử dụng hoặc model đã lưu của người dùng:

- Viền cyan mảnh,4góc vát8px, nền nhấn nhẹ theo theme; bỏ khung bo tròn cũ.
- Khung đo trên desktop cao50,25px, tối đa420px rộng, căn giữa với cụm PAO AI.
- Nhãn mono10px; dòng provider/model/effort **13,5px sans-serif**, có fallback
  `system-ui, sans-serif` để không rơi về serif khi biến `--font-sans` chưa khai báo.
- Header thu gọn padding, khoảng cách; dòng thông tin dài vẫn được xuống dòng,
  không làm mất tên nguồn/model. Mobile giữ co giãn và vùng bấm tối thiểu44px.
- Kiểm tra lại4profile Codex dùng chung/cá nhân, OpenAI, OpenRouter, mỗi profile
  dark/light ×1600/1024/768/390/320. Khung góc vát/font được đo trong browser;
  lựa chọn, effort, popup, bàn phím và quyền riêng tư vẫn giữ contract cũ.

Bằng chứng cập nhật (các ảnh đều từ fixture riêng, không phải lượt gọi model thật):

- OpenAI: `.runtime/chat-controls-browser-1792567246128/receipt.json`;
  ảnh `dark-model-header.png`, `light-model-header.png` trong cùng thư mục.
- Codex dùng chung: `.runtime/chat-controls-browser-1792567259493/receipt.json`.
- Codex cá nhân: `.runtime/chat-controls-browser-1792567273025/receipt.json`.
- OpenRouter: `.runtime/chat-controls-browser-1792567288536/receipt.json`.
- Pipeline frontend cuối: `.runtime/model-provider-tabs-frontend-2cfafad7497d430188642e0f0dbbf127/receipt.json`;
  chỉ dùng khi `pass=true`, không coi các log stage riêng lẻ là pipeline hoàn tất.

Đây vẫn là chỉnh sửa UI nhỏ, không phải triển khai GD01 hoặc thử quota AI.
