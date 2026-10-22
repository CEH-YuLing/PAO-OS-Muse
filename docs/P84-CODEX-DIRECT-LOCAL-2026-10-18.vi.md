# P8.4-C — Thử Codex đang cài trực tiếp trên Windows

Ngày18/10/2026, Asia/Saigon. Người dùng yêu cầu thử trực tiếp Codex sẵn có sau
khi trước đó đã chọn chuẩn bị Docker local. Thử trực tiếp không tự thay phương
án cách ly cho các job nhiều SME hoặc cho phép dùng chung thuê bao trên SaaS.

## Kết quả thực tế

- CLI npm: **0.157.1**, gọi executable nguyên bản, không wrapper PowerShell.
- SHA256 `8cb0e69e99ff2a158c54815db82d0f2e524d8f301bc30184722cfd1ae5973574`.
- `codex login status`: exit0, **ChatGPT**. Chỉ phân loại trạng thái, không xuất
  nội dung auth hoặc sao chép cache vào PAO.
- Một lượt `exec --json --ephemeral --ignore-user-config --ignore-rules`,
  giữ `--sandbox read-only`, approval `never`; shell/apps/web bị tắt bằng cấu
  hình. Không dùng `--yolo`, không nâng quyền Windows hoặc thay tài khoản.
- Chỉ gửi câu thử cố định yêu cầu trả `PAO_CODEX_OK`; thư mục làm việc trống,
  không đính kèm mã PAO hoặc dữ liệu doanh nghiệp, không truyền API key/proxy.
- Exit0, parser đọc đúng **PAO_CODEX_OK**, usage CLI báo12.203 input/9output
  tokens. Đây không phải số tiền hoặc phép đo quota còn lại của thuê bao.
- Bản bundled của desktop còn có `0.163.0-alpha.10.2`; chỉ kiểm tra version/help,
  không nâng cấp npm, không dùng bản alpha cho lượt gọi thật.

Receipt trực tiếp:
`.runtime/p84-codex-direct-9e566836ff98436da0e9b46ba089f479/direct-smoke.json`.
Chạy lúc15:17UTC, tức22:17 Việt Nam. Không lặp lại inference khi nghiệm thu.

## Kiểm thử và bảo toàn

Receipt:
`.runtime/p84-codex-preparation-1f11ebafef994c19b6aeb4aca5b2e100/receipt.json`.

-26/26 foundation +23/23 parser/preview = **49/49 unit offline** trên Windows.
- Parser kiểm tra UTF8 phân mảnh, thứ tự event, hoàn tất/exit, usage thiếu/sai,
  giới hạn byte/dòng, từ chối tool event và lỗi không phản chiếu secret.
- Preview không thực thi, không biến boolean/grant giả thành quyền dispatch.
- Serving API/UI/config/launchers so với checkpoint C giữ nguyên; schema0071,
 153bảng; binding
 `225ef02c99913df671fbc382f2baee3614274f130c89890fa8c700094070a22c`.
- API/readiness/web đều200. Không migration, restart, sửa `.env` hoặc restore DB.
- Không đo hash nội dung nghiệp vụ, không đóng sự cố drift lịch sử.
- Chưa chạy full regression/backend/browser mới hoặc hosted CI. Đã thêm stage
  parser offline vào CI entry; không gọi việc sửa CI là CI đã chạy.

Lượt unit đầu trong sandbox công cụ lỗi tạo fixture trong thư mục temp của
sandbox:18parser pass,5preview lỗi setup/cleanup (10errors). Chạy lại ngoài
sandbox bằng đúng test/assertion đạt23/23. Không bỏ test hay nới assertion.

## Giới hạn quan trọng

Thử trả lời văn bản thành công **không chứng minh sandbox công cụ an toàn**.
Probe unelevated trước đó từ chối restricted read-only với lỗi yêu cầu elevated
backend; receipt thất bại giữ nguyên ở
`.runtime/p84-codex-sandbox-8491f7ec143e4107aa0f205e8ec497be`.
Lượt thử mới không chạy tool nên không tái kiểm định rào đọc/ghi/mạng đó.

Docker đã kiểm tra server29.4.3; tải base Python chính thức theo digest và gói
Codex Linux0.157.1 đã khớp SHA512 registry. Chuẩn bị image lần đầu dừng ở kiểm
tra archive vì platform package không có LICENSE riêng và binary285MB lớn hơn
giới hạn ban đầu256MiB. Đã sửa preparer giữ metadata/README Apache-2.0 và nâng
giới hạn binary có kiểm soát384MiB; **chưa build/test lại**, chưa có Docker
acceptance. Không đưa thư mục nguồn PAO/home/token vào container. Giữ artifact
thất bại ở `.runtime/p84-codex-image-b61d681cec8c477cbed018bdde712c14`.

Chưa có connection/profile CLI theo SME trong backend, native grant/accounting,
durable attempt fencing, routing hoặc Settings đăng nhập. Không gọi PAO job,
không tự chia tài khoản hiện tại cho nhân viên/SME khác. Package vẫn tách khỏi
backend; `dispatch()` từ chối `cli_native_bridge_pending`.

**C vẫn in_progress**, chưa nghiệm thu toàn P8.4/S6/production. Có thể dùng
binary sẵn có cho local; việc chọn native/container cho job phải qua gate
cách ly và quyền, không suy từ câu chào. Ollama chưa bị gỡ hoặc đổi mặc định.

## Nguồn chính thức đã đối chiếu

- [Đăng nhập và kiểm tra trạng thái](https://learn.chatgpt.com/docs/auth).
- [Chạy không tương tác và JSONL](https://learn.chatgpt.com/docs/non-interactive-mode).
- [Cấu hình provider](https://learn.chatgpt.com/docs/config-file/config-advanced).
- [Windows sandbox](https://learn.chatgpt.com/docs/windows/windows-sandbox).

Nguồn đọc18/10/2026. Điều kiện commercial/hosted vẫn review riêng theo ADR-P84;
không lấy local ChatGPT login làm bằng chứng đã được phép bán lại quyền truy cập.
