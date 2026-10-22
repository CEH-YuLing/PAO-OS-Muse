# Cài đặt và kết nối — phân nhóm giao diện local

## Cách sử dụng

Mở **Cài đặt và kết nối → Kết nối**, kiểm tra doanh nghiệp đang chọn rồi chọn
nhóm và nền tảng. Chỉ một nền tảng được mở tại một thời điểm. Quyền, khóa và
dữ liệu vẫn giới hạn theo doanh nghiệp; thay giao diện không cấp thêm quyền.

| Nhóm | Nội dung |
|---|---|
| Tài nguyên quảng cáo | Meta Ads, TikTok Ads, Google Ads, GPT Ads |
| Hệ thống BOT | Telegram Bot, Zalo Bot, Lark/Feishu, Discord, Slack, WhatsApp |
| Ứng dụng và plugin | Kho ứng dụng, Bán hàng, Mạng xã hội, Marketing, Nhắn tin, Quảng cáo, Sáng tạo, Văn phòng, Website |
| MCP / Công cụ | Luồng cấu hình máy chủ và quyền công cụ hiện có |

Kho ứng dụng là mục xem tất cả; Bán hàng là nhóm riêng. Có thể tìm tên ứng
dụng trong nhóm đang mở. Danh mục quy hoạch gồm Haravan, Pancake, Sapo (Bán
hàng), Botcake và Zalo OA (Nhắn tin), Webcake và Ladipage (Website).

## Phân biệt biểu mẫu hiện có với vị trí chờ

- Meta Ads, Google Ads, Telegram và MCP giữ biểu mẫu/luồng cấp quyền hiện có.
  Có biểu mẫu không đồng nghĩa đã cấu hình, được nhà cung cấp duyệt, đang kết
  nối khỏe hoặc đã nghiệm thu dữ liệu thật. Các cờ an toàn không thay đổi.
- TikTok, GPT Ads, các BOT ngoài Telegram và bảy ứng dụng trong danh mục là
  **vị trí chờ**. Chưa có cài đặt/kết nối mới; không có ô nhập khóa hoặc nút
  kích hoạt. Không nhập thông tin bí mật vào ô tìm ứng dụng.
- GPT Ads chỉ là nhãn quy hoạch được yêu cầu, không khẳng định có API quảng
  cáo GPT, và không phải mục cấu hình mô hình ChatGPT.
- Zalo Bot khác Zalo OA. Liên kết cũ `platform=botcake` và `platform=zalo`
  được mở vào Ứng dụng và plugin → Nhắn tin, không đổi thành Zalo Bot.

Chuyển nhóm/nền tảng khi biểu mẫu chưa lưu vẫn yêu cầu xác nhận. Hủy thì giữ
biểu mẫu; đồng ý rời đi thì bỏ dữ liệu nháp, không lưu secret. Chuyển doanh
nghiệp tháo biểu mẫu cũ. Dùng mũi tên/Home/End để đổi tab, hoặc Back/Forward
của trình duyệt. Danh mục plugin dọc trên máy tính, cuộn ngang trên điện thoại.

## Nguồn và kiểm thử

Thay đổi nằm ở taxonomy trình bày, điều hướng Cài đặt, IntegrationTabs, CSS,
hướng dẫn và các kiểm thử/operator tương ứng. Không đổi API, hợp đồng, lock
dependencies, migration, cấu hình bí mật, quyền SME hoặc dữ liệu nghiệp vụ.

- 148 kiểm thử Node đạt, gồm16kiểm thử taxonomy mới; TypeScript đạt.
- Production frontend build đạt23trang. Build đầu bị từ chối quyền cache;
  đã chạy lại thành công bằng quyền giới hạn, không thay dependencies.
- Native browser đạt: hành trình nghiệp vụ hiện có; bốn nhóm;4Ads/6BOT;
  9khu vực plugin/7ứng dụng; liên kết cũ; bàn phím; Back/Forward; nháp/secret;
  chuyển SME; sáng/tối;320/390px không tràn ngang. Không mutation kết nối,
  không gọi provider. Test dùng DB riêng; cleanup và primary/env hash đạt.
- Một lần khởi động Web fixture trước build hoàn chỉnh bị lỗi; giữ log và
  bằng chứng cleanup, không ghi lần lỗi thành pass.
- Sáu kiểm thử offline của chốt bằng chứng UI đạt. Baseline2272backend và
  202Windows focused là bằng chứng trước đó, chỉ tái sử dụng khi mã backend,
  contracts/locks và binding khớp; không báo là full backend vừa chạy lại.

Bằng chứng native browser:
`.runtime/connections-ui-browser-runs/pao_s5_browser_7b0bd582a8e64706a1361c0413c7cc3b/receipt.json`.
Cùng thư mục có `connections-browser.json`, `cleanup.json`, log và ảnh kiểm tra.

## Chốt bản cài local và phục hồi

Không suy nghiệm thu từ copy nguồn hoặc HTTP200. Operator kiểm hash trước khi
cài, chỉ thay apps/web/scripts/docs, sao lưu nguồn cũ và cache Web, khởi động
lại đúng PID Web đã xác minh. Không khởi động lại API/worker hoặc restore DB.
Vị trí phục hồi được ghi ở `.runtime/connections-ui-installed.json` → `backup`.

Lần kiểm sau cài đầu phát hiện smoke test lấy membership owner đầu tiên không
có thứ tự; owner có SME mới chưa có archive nên kiểm đếm thất bại. Đã xác minh
DB vẫn có đúng3archive ở SME cũ. Sửa riêng script chẩn đoán để chọn owner đang
hoạt động có bằng chứng archive theo thứ tự xác định; vẫn đòi đọc đủ3archive,
đúng hash và không tái chạy tool. Không đổi backend hoặc thêm/sửa dữ liệu.
Release chẩn đoán kế tiếp liên kết manifest cũ qua `supersedes`, kiểm hash bản
cài trước; bằng chứng lần lỗi giữ nguyên, không ghi đè thành pass.

Chỉ khi `.runtime/connections-ui-completion.json` có `pass=true` mới xác nhận
bản cài: trình duyệt read-only sáng/tối/mobile đạt, API mutation=0, health/worker
đạt, đọc lại3archive đạt, primary/env/binding không đổi. Ảnh và bảng hash nằm
trong thư mục `evidence` của receipt. `.runtime/s6-readiness.json` phải ghi
`version=s6-local-connections-ui-v1`, `local_checks_passed=true`.

Toàn S6/production **chưa hoàn tất**: dữ liệu thật S6.1, hành động thật, owner
pilot, hosted CI cho nguồn mới và VPS/public vẫn là các chốt riêng. Không bật
quảng cáo, Telegram hoặc kết nối mới trong lần cải thiện giao diện này.
