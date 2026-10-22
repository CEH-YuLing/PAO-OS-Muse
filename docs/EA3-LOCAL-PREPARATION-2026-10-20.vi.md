# EA3 — Chuẩn bị Claude Code / Antigravity trên local

Ngày20/10/2026, Asia/Saigon. Target `F:\PAO-ACOS`.

## Trạng thái mới nhất — Claude hoãn, Antigravity ưu tiên

Người dùng chưa có Claude Pro/Max nên yêu cầu dừng Claude, chuyển Antigravity.
Không còn container auth/operation lock của hồ sơ Claude ứng viên; volume được
giữ nguyên, chưa enroll vào PAO. Không yêu cầu mua gói hoặc mở lại login.

Ứng viên hiện có95unit offline đạt, cùng kiểm chứng native Claude chưa auth
trong container network-none. Antigravity đo thật version/help:1.2.12; chưa
auth/catalog/model call. Live OAuth qua PAO chưa bật vì provider-eligibility
chưa được xác nhận; không tự chuyển sang API/ADC để coi là dùng thuê bao.
Xem [báo cáo mới và bằng chứng](EA3-ANTIGRAVITY-2026-10-20.vi.md).

**Các mục còn lại dưới đây là snapshot chuẩn bị69unit trước bước native**,
giữ để truy vết; không dùng các câu “chưa probe/không đăng nhập mới” trong
snapshot để phủ nhận kiểm tra native hoặc lần mở auth đã dừng sau đó.

## Quyết định và trạng thái

Người dùng chốt **tạm hoãn Codex dùng chung (EA2.2), tiếp tục EA3**. Không hỏi
lại lựa chọn này, không mua/chuyển gói pay-as-you-go. Codex cá nhân đã nghiệm
thu bằng model thật vẫn giữ nguyên.

**Đã đạt phần chuẩn bị protocol offline; chưa hoàn tất EA3 hoặc kết nối thật.**
Không có adapter Claude/Antigravity đăng ký trong backend đang phục vụ, đăng
nhập mới hoặc model call trong lượt này. UI vẫn ghi chưa hỗ trợ; không biến
nút Kết nối thành thành công giả. Không yêu cầu người dùng dán OAuth/token.

## Kết quả triển khai

- Thêm `packages/client-adapters/pao_client_adapters`: hai parser ứng viên
  `ClaudeStream` / `AntigravityStream`, stdlib-only, không dependency mới.
- Hỗ trợ subset NDJSON text-only, Unicode split theo byte, terminal + exit0,
  model/session đúng, đúng một turn. Chỉ trả text sau kiểm tra toàn luồng.
- Từ chối JSON/UTF-8 sai, khóa JSON trùng, model/session lệch, terminal thiếu
  hoặc lặp, text khác result, usage sai/âm/bool, tool/MCP/plugin/subagent/retry
  hay sự kiện ngoài subset. Không chuyển dòng lạ thành câu trả lời.
- Usage cuối được đọc riêng; thiếu vẫn unknown, số0 có báo cáo khác thiếu.
  Không cộng usage từng step với usage tổng; cache/thinking tách riêng, không
  suy ra hóa đơn hoặc quota thuê bao còn lại.
- `external_dispatch` luôn deny; không có code chạy binary, đọc auth store,
  đăng ký runner hay tự fallback API. Parser không phải sandbox hoặc authority.
- Package đặt ngoài transport Codex đã ghim; không đổi digest rồi cập nhật
  registry để ép chấp nhận. Chưa thêm package mới vào backend/pyproject/CI.
- Đọc tham khảo code `G:\Javis` VERSION0.204.0: Claude dùng Agent SDK, Antigravity
  subprocess/protocol. Không chép code, hooks, MCP, token hoặc cơ chế retry của
  Javis vào PAO; không sửa Javis hoặc backup001.

## Kiểm chứng

- Lượt đầu61unit đạt; sau bổ sung trường hợp surrogate/model thiếu/usage0 và
  đầu vào sai, lượt cuối độc lập **69tests/0failure/error/skip** đạt.
- Lượt cuối dùng interpreter theo pin và `-I -B`; audit hook chặn tạo socket,
  network resolution và spawn subprocess trong test. Không DB/Redis/provider.
- Inventory chỉ xác nhận hai file binary có tồn tại, kích thước và SHA256;
  **chưa probe version/help/auth/catalog hoặc gọi binary**. Không đọc keyring.
- Hash `.env`, registry CLI, Python pin, pyproject, serving service/UI và toàn
  package transport Codex giữ nguyên trong lượt kiểm thử. Source ứng viên giữ
  hash; không cộng61+69 thành130 test riêng.
- Sau kiểm thử: source digest Codex khớp registry; API health/ready/Web đều200.
  Đọc metadata chính chủ thấy gpt-6-astra/profilev6/personalpolicyv2, không setup
  pending hoặc dispatch chưa giải quyết. Không gọi model để kiểm lại Codex.
- Không migration, restart, primary restore, đổi dữ liệu/cấu hình qua SQL, push
  hoặc deploy. Không đo hash mọi bảng nghiệp vụ; không chứng nhận primary đứng
  yên trong toàn phiên người dùng.
- Không cần frontend build/full backend cho code ứng viên chưa được import;
  các gate đó bắt buộc khi tích hợp native, không được dùng69unit thay thế.

## Hồ sơ provider — đối chiếu20/10

### Claude Code

- Nguồn: [headless](https://code.claude.com/docs/en/headless),
  [legal/authentication](https://code.claude.com/docs/en/legal-and-compliance).
- Kỹ thuật: CLI có print/JSON; bare mode bỏ khám phá cấu hình nhưng không dùng
  subscription login. Không chọn bare rồi ngầm đổi sang API. Chạy không bare
  cần xử lý hooks/MCP/plugins/memory cấu hình sẵn và OS isolation trước inference.
- Xác thực: giữ binary nguyên bản; người dùng hoàn tất luồng của Anthropic,
  không nhận/giải mã/copy session trong PAO. Tài liệu phân biệt hosting binary
  chính chủ cho từng người với trung gian đăng nhập và route thuê bao thay users.
- Chưa xác nhận gói/phiên/entitlement trên máy. Không lấy thành công của Javis
  làm quyền thương mại. Không kết luận mọi chạy binary đều bị cấm; cần chọn
  đúng ranh giới native để không biến PAO thành credential proxy.
- Scopes/redirect: do native CLI chính chủ quản lý, chưa dựng OAuth client,
  callback hay khai scope tự đoán. Không xin App ID/secret cho luồng này.
- Rotation/revoke: chưa triển khai PAO disconnect; không logout/thu hồi phiên
  Claude/Javis dùng chung. Tách vô hiệu trong PAO khỏi native logout.
- Limits: chưa đo quota/concurrency thực. Parser chưa xác minh CLI thực tế;
  SDK/CLI auto-retry và cleanup/cancel là chốt cần đo, không giả exactly-once.

### Antigravity

- Nguồn: [headless](https://www.antigravity.google/docs/cli/headless/),
  [authentication](https://www.antigravity.google/docs/install?tab=cli),
  [terms](https://antigravity.google/terms).
- CLI có NDJSON một turn và cached authentication. Keyring/Google sign-in do
  chính CLI xử lý; không lấy token để gọi endpoint khác hoặc giả app Google.
- Điều khoản tài khoản cá nhân hiện nêu hạn chế dùng phần mềm bên thứ ba để
  truy cập service qua OAuth. Nhánh Enterprise áp dụng thỏa thuận khác; không
  được tự coi khách hiện có đã thuộc nhánh đó hoặc chuyển họ sang Google Cloud.
  Vì vậy **live OAuth qua PAO chưa được kích hoạt**; cần cơ chế được provider
  hỗ trợ/xác nhận phù hợp. Headless có thật không tự đóng gate này.
- Không tạo redirect/webhook/scopes/OAuth client riêng, không nhập OAuth token
  vào ô API key. Không enable ADC/Gemini API/fallback credits thay người dùng.
- Ngắt/ký lại phải tách khỏi `/logout` có thể xóa keyring/native session; chưa
  thực hiện rotation/revoke, không động phiên có sẵn của Javis/Antigravity.
- Model catalog/quota chưa đọc. Init mặc định có tool; không dùng permission
  Ask/headless soft-deny hoặc parser phát hiện tool làm rào OS thực sự.

Các đoạn trên là cơ sở thiết kế kỹ thuật theo tài liệu hiện tại, không phải
tư vấn pháp lý hoặc chứng nhận commercial/hosted/entitlement của tài khoản này.

## Các chốt còn lại trong cùng EA3

1. Chọn ranh giới Claude native được hỗ trợ: binary nguyên bản + chính chủ,
   không thu credential hay dùng chung. Làm rõ khác biệt subscription/API/SDK.
2. Đo version/help và khả năng vô hiệu hook/tool/MCP/ghi memory/auto-retry trong
   profile cách ly. Nếu không chứng minh được isolation thì không inference.
3. Chuẩn bị native adapter tái sử dụng Run/ARQ/LlmAttempt/dispatch/lease; actor,
   SME/brand, source/device/model/binary pins; recheck/revoke/cancel/recovery.
   Hiện schema CliModelConnection chỉ chấp nhận codex_cli; không nới enum hoặc
   migration trước checkpoint/compatibility review. Không thêm runner thứ hai.
4. UI từng Client có hướng dẫn riêng, trạng thái install/auth/catalog/test,
   Lưu và Ngắt rõ; lost ACK và SME/actor switching phải được kiểm thử.
5. Regression/contract/history/restore/browser rồi mới native test có đồng ý
   và usage, chỉ khi đã qua gate provider/isolation. Không dùng fixture làm live.
6. Antigravity: giữ provider-eligibility gate riêng; không hứa tích hợp thuê bao
   nếu điều kiện hiện tại chưa cho phép. Không tự đổi billing để đóng EA3.

Chưa có bằng chứng đóng các chốt trên. EA2.2 hoãn theo người dùng; không lấy nó
làm lý do ép luồng cá nhân mua identity tổ chức. VPS/public vẫn hoãn.

## Bằng chứng

- `.runtime/ea3-offline-5a9b090a66bb457f85121a5884cebeec/receipt.json`, `unit.log`:
 69unit, source/config hashes và inventory không chứa credentials.
- `scripts/check_ea3_offline.py`: helper không chạy provider, receipt mới mỗi lần.
- `.runtime/codex-live-acceptance-20261020/ea3-readonly-state.json`: metadata chỉ đọc.
- `.runtime/ea3-completion.json`: trạng thái hiện tại, không ghi đè receipt Codex cũ.
