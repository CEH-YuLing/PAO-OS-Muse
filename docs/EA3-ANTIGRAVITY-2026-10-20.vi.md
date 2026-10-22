# EA3 — Ưu tiên Antigravity; tạm dừng Claude

Ngày20/10/2026, Asia/Saigon. Chỉ làm tại `F:\PAO-ACOS`.

## Kết luận hiện tại

- Claude: `deferred_by_user_no_Claude_Pro_Max`; không yêu cầu mua gói, không
  mở lại đăng nhập. Giữ hồ sơ ứng viên để tiếp tục sau; chưa là kết nối PAO.
- Antigravity: `metadata_verified_provider_eligibility_pending`; đã đo CLI
  cài sẵn, **chưa kết nối tài khoản hoặc gọi model từ PAO**.
- Codex cá nhân giữ nguyên; EA2.2 dùng chung vẫn hoãn. Không triển khai VPS.

## Antigravity — điều đã đo trên máy

Binary cố định `C:\Users\o0o_v\AppData\Local\agy\bin\agy.exe`, SHA256
`e137ee4f362b5b2f2c37141d4d1d1c12298f6b42873ca6867c618a5b945421df`.
Đã kiểm tra đường dẫn không symlink/junction và hash trước/sau khớp.

`--version` trả1.2.12/exit0; `--help` trảexit0, có `--print`,
`--input-format`, `--output-format`, `--model`, `--print-timeout`, `--sandbox`,
`--disable-slash-commands`. Help ở stderr, không stdout; helper đã sửa cách đọc
hai luồng và giữ receipt lượt đầu, không coi flags rỗng là CLI thiếu headless.
Không bật `--dangerously-skip-permissions`.

Chỉ chạy hai lệnh metadata trong thư mục/home trống, stdin đóng, timeout15s;
không chạy agy trần, `models`, auth/status, prompt, logout hoặc update. Receipt
chỉ lưu version/flags/mã thoát/kích thước, không raw output. HOME trống **không
chứng minh keyring Windows được cách ly**; không dùng nó làm sandbox auth.

## Chốt nhà cung cấp — không phải lỗi cài đặt

Đã đọc nguồn Google chính thức ngày20/10:

- [Điều khoản](https://antigravity.google/terms): khoản6 nêu sử dụng phần mềm
  bên thứ ba truy cập Service, ví dụ OpenClaw với Antigravity OAuth, vi phạm
  thỏa thuận và có thể bị đình chỉ tài khoản. Nhánh Enterprise/Cloud/Workspace
  đủ điều kiện ở phần đầu áp dụng thỏa thuận khác, không tự suy tài khoản này
  thuộc nhánh đó.
- [Headless CLI](https://www.antigravity.google/docs/cli/headless/): có print,
  JSON/NDJSON, model pin; file trong workspace mặc định có thể được đọc/ghi và
  permission Ask có thể soft-deny mà exit0. Parser phát hiện tool không phải
  rào OS ngăn tool chạy. Không dùng ví dụ headless để coi gate điều khoản đã đạt.
- [Xác thực](https://www.antigravity.google/docs/install/): CLI có keyring native
  và sign-in chính chủ; phần programmatic authentication liệt kê Gemini API,
  Enterprise/ADC và local models. `auth.type=oauth-personal` ở mục cấu hình
  editor không tự chứng minh PAO là tích hợp được cho phép.
- [SDK chính thức](https://www.antigravity.google/docs/sdk/overview/): có đường
  API key và Gemini Enterprise. Không thấy nguồn xác nhận PAO dùng thuê bao
  OAuth cá nhân thay API. Chưa cài SDK hoặc thay dependency/billing.

Vì vậy chưa kích hoạt luồng PAO tự dùng OAuth cá nhân. Đây là quyết định giữ
gate trước khi có xác nhận phù hợp, không phải kết luận mọi chạy CLI/headless
đều bị cấm. Không lấy token từ Javis, keyring hay file auth; không giả Google
client, chuyển token sang API key hoặc dùng Enterprise/ADC ngầm.

## Công việc còn lại — theo thứ tự, không làm lại runner

1. Xác nhận phạm vi dùng được Google hỗ trợ cho PAO: thuê bao cá nhân cần bằng
   chứng/clarification phù hợp; hoặc người dùng chọn riêng API/Enterprise và
   chấp nhận phương thức cấp quyền/chi phí. **Chưa có lựa chọn này**.
2. Sau khi qua bước1: profile riêng cho scope hợp lệ, chọn destination/account
   rõ ràng, không sao chép credential từ máy host/Javis. Kiểm tra native
   version/auth/catalog độc lập; lưu cấu hình khác với connected/tested.
3. Chứng minh OS isolation cho tool/hook/MCP/memory/file/network/cancel/timeout
   bằng binary đã pin; không bật mọi quyền, không mount thư mục nguồn/user home.
4. Tích hợp vào Run/ARQ/LlmAttempt/dispatch/lease hiện có; recheck actor/SME và
   nguồn/model/version, lịch sử bất biến, lost ACK/cancel/revoke; không thêm runner.
   Schema hiện chỉ có Codex không được nới enum trước checkpoint/compatibility.
5. UI Client có trạng thái cài đặt/đăng nhập/danh mục/kiểm thử tách biệt, hướng
   dẫn tiếng Việt, Lưu/Ngắt rõ, không dùng cờ đã cài để báo đang kết nối.
6. Regression/contract/restore/browser và một bài model thật có usage/ledger
   mới đóng native gate. Fixture/95unit không phải proof model hoặc quota thật.

Không mở rộng offline fixtures vô hạn để che chốt bước1; chưa thể đánh dấu
Antigravity/EA3 hoàn tất khi chưa có đường tích hợp hợp lệ được xác nhận.

## Claude — phần đã chuẩn bị được bảo toàn

Ứng viên riêng nằm ngoài transport Codex: parser text-only, inert invocation
plan và scoped candidate profile; chưa import vào backend/worker/pyproject.
CLI Windows2.1.220 được đo help/version. Image Linux dùng binary chính chủ đã
kiểm npm SHA512, giữ LICENSE; test chưa auth có network-none, nonroot/read-only,
không host mount, hooks/MCP synthetic không chạy, timeout cleanup đạt.

Đã giữ các failure managed-settings permission, ngữ nghĩa result auth error,
bootstrap và Windows PS5 module import; không xóa failure hoặc gọi lần test
sau là sửa bằng chứng cũ. CLI có thể trả subtype=success nhưng is_error=true
và exit1: parser vẫn deny. Chưa chứng minh live authenticated tool isolation.

Một hồ sơ ứng viên riêng đã được tạo; từng mở CLI auth chính chủ nhưng chưa
nghiệm thu đăng nhập/inference. Khi người dùng yêu cầu dừng, kiểm tra xác nhận
không còn auth container/operation lock; số container cần stop lúc đó là0.
Không suy nguyên nhân auth đã thoát hoặc trạng thái tài khoản từ điều này.
Volume được giữ, chưa native enroll/grant/connected. Không đọc nội dung auth.

## Bằng chứng và giới hạn

- `.runtime/ea3-offline-1418693307314951b7c3b1c4d8564398/receipt.json`:
  **95tests/0failure/error/skip**, socket/subprocess bị chặn trong testchild;
  source/config không đổi trong lượt test. Không cộng61/69/82/83/95.
- `.runtime/ea3-claude-isolation-03dab1bae7524c3aa7825c90478de0fb/receipt.json`:
  hai fixture normal/timeout đạt, container của bài test đã dọn.
- `.runtime/ea3-claude-native-20261020/user-deferred-claude.json`: dừng theo user,
  profile giữ nguyên, không container auth/operation pending.
- `.runtime/ea3-antigravity-metadata-fadfbb1d42384df9880949045fea985b/receipt.json`:
  lượt đầu đọc help sai stream; giữ nguyên.
- `.runtime/ea3-antigravity-metadata-3409aef66e4c483daecc86514a5babd6/receipt.json`:
  version/help đầy đủ, không auth/inference/raw output.
- `scripts/probe_ea3_antigravity_metadata.py`: helper chỉ metadata, không runner.
- `.runtime/ea3-antigravity-final-check-4d9abd8723a9478c8ffef42a530dc47e.json`:
  cuối bước API/ready/Web200; hash cấu hình/serving Codex/ứng viên vẫn khớp
  snapshot95test, không operation Claude pending. Lượt kiểm tra trong sandbox
  trước đó bị URLError, giữ receipt879762; chạy chỉ đọc ngoài sandbox đạt,
  không restart hoặc sửa ứng dụng để che lỗi kiểm tra mạng.
- `.runtime/ea3-completion.json`: overlay trạng thái mới, không sửa raw receipts.

Không migration, thay serving backend/UI, restart, DB mutation/restore, update
CLI host, sao chép credential, quota call hay push/deploy trong bước Antigravity.
Không tuyên bố full backend/browser, toàn EA3/S6 hoặc production đã đạt.
