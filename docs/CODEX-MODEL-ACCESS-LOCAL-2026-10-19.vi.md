# Codex — quyền dùng mô hình trên giao diện PAO

Ngày 19/10/2026. Phạm vi P8.4-C/E local cá nhân, không phải SaaS/production.

## Kết quả và giới hạn

Đã bổ sung mục thu gọn **Quyền dùng Codex** trong Cài đặt và kết nối → AI và
giọng nói → Nhà cung cấp mô hình → Kết nối qua Client. Mở mục này mới tải danh
mục/quyền, không tự đăng ký hoặc kích hoạt. Dùng ConnectionGrantPanel và API
connection-inventory/model-grants/engine hiện có; không thêm runner hay API.

Backend, schema0072, hợp đồng416 API, Python pin, CLI registry, .env, model mặc
định và dependencies không đổi. Không tự tạo grant, gọi provider hoặc dùng quota.
Profile đã đăng nhập là khác với quyền PAO và khác với một job chạy thành công.

## Luồng chủ tài khoản thực hiện

1. Chọn đúng doanh nghiệp, mở **Quyền dùng Codex**. Chọn hồ sơ đã ghi nhận đăng
   nhập. Người sử dụng bị khóa là chính tài khoản PAO hiện tại; không chia thuê
   bao cho đồng nghiệp. Quyền của một doanh nghiệp không dùng cho doanh nghiệp khác.
2. Chọn nhãn hàng hoặc **Chỉ hội thoại không gắn nhãn hàng**, thời hạn ví dụ
   30 phút. Xác nhận phạm vi rồi bấm **Lưu quyền chờ kích hoạt**. Bước này chưa
   cho phép chạy AI.
3. Đọc cam kết sử dụng mô hình, đánh dấu đồng ý rồi bấm **Kích hoạt quyền này**
   trên đúng quyền. Có thể tiêu hạn mức thuê bao. Không cấp quyền shell, Ads,
   gửi tin, kho tri thức hoặc chuyển default; không bật dự phòng API có phí.
4. Để thử thật, tạo hội thoại mới đúng doanh nghiệp và nhãn hàng đã chọn; mở
   **Model**, chọn quyền `codex_cli` đã kích hoạt, bấm **Áp dụng model**. Dùng
   hội thoại văn bản, tắt công cụ/nguồn tri thức và không gửi dữ liệu nhạy cảm.
   Có thể gửi: `Chỉ trả lời: PAO kết nối Codex thành công.`
5. Sau đó đối chiếu trạng thái run, LlmAttempt, CliModelDispatch, lease và usage
   theo pipeline native. Kết quả chat hoặc profile connected riêng lẻ chưa đóng
   chốt này. Thử dừng/thu hồi/recovery thật là nghiệm thu tiếp theo, không suy từ fixture.

## Tình huống lỗi và an toàn

- Mất phản hồi ghi: khóa thao tác thay đổi; **Đọc lại quyền Codex** trước khi thử
  tiếp. Không tự gửi lại và không tự tạo grant mới để thay kết quả chưa biết.
- Đổi doanh nghiệp/tài khoản đóng form, bỏ kết quả cũ; preview đến muộn không
  được nối thành POST lưu quyền. Thay nguồn/nhãn hàng/thời hạn xóa các xác nhận.
- Danh mục bị giới hạn/phân trang tạm chặn ghi, không đoán phần dữ liệu còn thiếu.
- Quyền hết hạn/thu hồi không kích hoạt lại ngầm. Cấp lại thế hệ cần xác nhận
  riêng, thu hồi quyền cũ theo API hiện hành; job và pin cũ không tự chuyển đổi.
- Đọc danh sách chưa xác minh provider/quota/model entitlement. Ngắt Codex trong
  PAO khác với logout ứng dụng Codex khác. Không đọc/import auth.json hoặc token.
- Chỉ dùng auth local cá nhân. Commercial/hosted/SaaS vẫn là gate riêng theo
  [tài liệu OpenAI App Server](https://learn.chatgpt.com/docs/app-server), đọc lại
  ngày 19/10/2026; không suy từ hỗ trợ CLI thành quyền bán dịch vụ thuê bao.

## Bằng chứng

- Checkpoint hai file UI trước sửa và quan sát DB SELECT-only:
  `.runtime/codex-access-ui-e5987cf536194e1ea5dbf7125bbd9f58/before.json`.
  Lúc kiểm tra: profile connected/v5/model gpt-6.1-sol; CLI references0,
  dispatches0; engine contract và hai cổng CLI đã bật sẵn từ trước.
- 167 Node/0fail/error/skip, typegen/TypeScript/build23:
  `.runtime/model-provider-tabs-frontend-f2f5328ffa4b436d892edd4a791fa2f4/receipt.json`.
- UI quyền Codex fixture đạt: self-only, nhãn hàng/TTL/ACK rõ ràng, lưu khác
  kích hoạt, thu hồi giữ lịch sử, mất ACK đọc lại, phân trang chặn ghi, đổi SME
  chặn late stage, viewer, sáng/tối,1440/390/320:
  `.runtime/codex-access-browser-1792403903403/receipt.json`.
- Hồi quy đăng nhập/hủy/phục hồi Codex:
  `.runtime/codex-login-browser-1792403938252/receipt.json`.
- Hồi quy bốn ô API/ba ô Client, save/delete/mask/draft/role/mobile:
  `.runtime/model-provider-tabs-browser-1792403954831/receipt.json`.
- Các browser test chặn tất cả API/provider thật; không dùng fixture làm
  bằng chứng grant hoặc job thật. Không chạy lại backend2356 vì backend/CLI/
  contracts/dependencies không đổi; bằng chứng2356 trước đó vẫn là prefix1416
  cộng suffix940 sau sửa helper, không gọi là full xanh mới.
- Receipt cuối chỉ tạo khi nguồn backend/env/runtime giữ nguyên, hai file UI
  khớp bản build đã kiểm tra và bốn proof đạt. Dữ liệu chính có thể thay đổi do
  người dùng đang thao tác; không tuyên bố hash nghiệp vụ bất biến, không restore
  primary để làm kiểm tra đạt. Xem `.runtime/codex-access-current-status.json`.

Chưa nghiệm thu một native job thật, quota hoặc toàn C/E/G, S6/pilot/production.
Claude Code, Antigravity và gỡ bắt buộc Ollama không thuộc lát cắt này.
