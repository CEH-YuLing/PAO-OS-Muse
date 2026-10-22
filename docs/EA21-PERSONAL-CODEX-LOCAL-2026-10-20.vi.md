# EA2.1 — Codex cho chính chủ: nghiệm thu local

Ngày20/10/2026, nguồn/bản cài `F:\PAO-ACOS`.

## Kết quả

Đã thay luồng tự tạo quyền/thời hạn cho chính chủ bằng thiết lập **Dùng Codex
cho tôi** có phiên bản, bật/tắt và lựa chọn mặc định. Người dùng không phải chọn
grantee, tạo mapping, kích hoạt grant hoặc nhập số phút. Đây là cơ chế native
mới, không chỉ ẩn bảng quyền cũ.

Owner/admin chỉ dùng hồ sơ Codex do chính mình sở hữu trong đúng workspace.
Quản trị viên khác không đọc hoặc dùng hồ sơ đó. Thành viên khác không kế thừa
thuê bao cá nhân; EA2.2 dùng chung vẫn cần cơ chế provider phù hợp. Không yêu
cầu tài khoản dịch vụ cho luồng cá nhân. Không thay auth cache, CLI image/binary,
registry, `.env`, Python runtime hoặc gói tính tiền. Không bỏ Ollama bắt buộc
trong các chức năng memory/embedding còn lại chỉ bằng kết quả này.

## Cách sử dụng

1. Chọn đúng không gian làm việc, vào **Cài đặt và kết nối → AI và giọng nói →
   Kết nối AI → Kết nối qua Client**.
2. Nếu chưa đăng nhập, bấm Kết nối ở ô Codex và làm theo luồng OpenAI chính thức.
   Không gửi mật khẩu, token hoặc mã đăng nhập trong chat.
3. Tại **Dùng Codex cho tôi**, Tải lại, chọn hồ sơ đã đăng nhập, bật sử dụng.
4. Giữ **Dùng cho các hội thoại mới của tôi** nếu muốn Codex là mặc định riêng
   của bạn, ưu tiên hơn API dùng chung; đọc cảnh báo tiêu quota, xác nhận và Lưu.
5. Mở hội thoại mới. Lưu không chạy AI; câu hỏi tiếp theo mới có thể tiêu quota.
   Hội thoại cũ, lịch sử local và các job đã ghim không tự chuyển model/quyền.

Nếu không chọn làm mặc định, có thể chọn Codex trong mục Model của hội thoại
đã cho phép gửi dữ liệu ra cloud. Chọn model không tự mở quyền gửi lịch sử cũ,
công cụ, đọc Brain, đăng bài, sửa quảng cáo hoặc chi tiền.

Khi mất phản hồi sau Lưu, Tải lại trước khi tiếp tục; không tự retry. Đổi đăng
nhập, nguồn, vai trò hoặc trạng thái thành viên có thể yêu cầu xác nhận và lưu
lại. Nguồn mặc định lỗi được báo rõ, không âm thầm fallback API. Tắt rồi Lưu
dừng thiết lập mới. Quyền grant cũ là cơ chế riêng; ngắt hồ sơ chặn cả các cách
dùng hồ sơ đó, không đăng xuất ứng dụng Codex khác trên máy.

## Backend và an toàn

- Migration0074 thêm `personal_cli_policies` và `personal_cli_revisions`, không
  chuyển đổi hồ sơ/grant/hội thoại/job cũ. Lịch sử bất biến; downgrade từ chối
  khi đã có consent history. Không lưu token hoặc API key trong hai bảng mới.
- Hai API GET/PUT `/v1/workspaces/{workspace_id}/personal-cli`, no-store, body
  giới hạn8KB, kiểu bool/revision chặt và lỗi không phản chiếu input.
- Lưu cần đúng owner/admin, chủ hồ sơ, source connected và đồng ý rõ ràng;
  request-key/revision xử lý lost ACK, request cũ không bật lại sau khi đã tắt.
- Pin actor/role/brand/auth-version/membership-epoch/policy-revision/source và
  CLI runtime nguyên bản. Kiểm tra trước dispatch, trong watchdog hiện có và
  trước công bố. Thu hồi giữa inference chặn kết quả; không cam kết hoàn tác
  dữ liệu đã gửi hoặc token nhà cung cấp đã tiêu trước lúc thu hồi.
- Tái sử dụng Run/ARQ/LlmAttempt/lease/budget/CliModelDispatch; không thêm runner
  hoặc bỏ hàng rào profile busy/unknown. Không cần grant mới hoặc TTL người dùng;
  lease vận hành ngắn hạn vẫn giữ nguyên.
- Mặc định chỉ cho chính chủ và hội thoại mới. Default hỏng không fallback;
  tạo chat trả409 rõ ràng thay vì500. Chọn engine hỗ trợ source ID cá nhân;
  private Brain/brand và các đường grant cũ vẫn kiểm tra riêng.
- UI tải metadata, xóa state theo SME/actor/role, bỏ response muộn, chặn lưu khi
  ACK không rõ hoặc DTO sai; Client3ô vẫn gọn, biểu mẫu riêng đặt phía dưới.

## Bằng chứng

| Phạm vi | Kết quả |
|---|---|
| Backend tập trung bản cuối |385pass,0fail/error/skip,245.09s; gồm29test EA2.1 |
| Node |187pass,0fail/cancel/skip;8test helper mới |
| Typegen/TypeScript/build |Đạt,23trang; declarations kiểm tra lại trước cài |
| Migration trên pao_test |0073→0074→0073→0074; downgrade có lịch sử bị chặn, giữ0074/159bảng |
| Checkpoint trước rollout |Restore clone0073,157bảng,3archive đạt |
| Browser fixture |Self-consent,không grant/TTL,lost ACK,late SME/wrong actor,viewer,trống; light/dark1440/390/320 đạt |
| Bản cài |0074/159bảng/421API; hàng cũ nguyên vẹn;3replay không thực thi tool; API/Web200,worker khỏe |
| Browser bản cài |GET-only1440/390; đúng owner/SME,revision0/tắt,không mutation/provider |

Không cộng các lượt test thành full regression mới. Sáu cảnh báo ARQ deprecation
và cảnh báo hook/Next root có sẵn vẫn giữ; không tắt assertion/lint để làm xanh.

Nguồn sao lưu1487file, không credentials/deps/runtime/Git. Cài đúng27file đã
đối chiếu proof và giữ preimage. `.env`, CLI registry/runtime pin giữ nguyên.
Lần đầu installer dừng trước sửa nguồn vì PID từ hôm trước đã mất; đối chiếu
không có listener/API/worker thay thế. Snapshot mới khớp snapshot đã giữ trước
lượt retry. Sau đó cài/migrate và khởi động đúng PAO, không dừng tiến trình lạ.
Web cũ cũng đã dừng: kiểm tra port trống rồi khởi động, giữ cache sinh ra trong
quarantine. Không factory-reset Docker, xóa volume, restore primary hoặc reboot.

Giữ lịch sử lỗi: lần test đầu phát hiện validation echo input giả lập và đã
bổ sung endpoint vào bộ lọc an toàn/body limit; lần sau fixture messages thiếu
system role, sửa fixture để thật sự đi qua native ledger. Migration helper ban
đầu thiếu JWT giả lập; bổ sung chỉ trong tiến trình test. Giữ các receipt thất
bại, không đổi dữ liệu chính hoặc nới kiểm tra để pass. Bổ sung xử lý409 rồi
chạy lại toàn focused385 trên đúng nguồn cuối, không ghép hai lượt thành một.

## Giới hạn nghiệm thu

**Chưa gọi Codex thật trong lượt này.** Profile đăng nhập được đọc không chứng
minh model đã trả lời, quota còn lại hoặc ổn định 24/7. Lượt thử19/10 từng báo
`cli_provider_failed` vẫn là lịch sử, chưa được dùng fixture20/10 để xóa lỗi.
Thiết lập thật hiện revision0/tắt; agent không thay owner bật quyền, không tự
tạo grant hoặc gửi câu hỏi bằng thuê bao. Cần một native job thật có đồng ý
riêng để đóng gate live. Shared CLI/Claude/Antigravity và production vẫn pending.

Hàng cũ được so khớp ngay sau cài; không suy ra dữ liệu đứng yên toàn phiên nếu
người dùng/công cụ khác thao tác tiếp. Không auto commit/push/deploy hoặc bật Ads.
Đối chiếu hàng/cột cũ loại riêng `alembic_version`, vì marker này phải đổi từ
0073 sang0074. Web ứng viên13209 đã dừng đúng executable/start-time; bản chính
vẫn chạy. Không xóa chứng cứ hoặc cache quarantine.

## Vị trí chứng cứ

- `.runtime/ea21-20261020/before-source.zip`, `before.json`, `source-plan.json`.
- Checkpoint: `.runtime/checkpoints/p0-20261020T023626-85f31514/manifest.json`.
- Backend cuối: `.runtime/ea21-20261020/check-ea79f8b8c59840d78d9bd7767a22d5d7/receipt.json`.
- Backend385 trước xử lý409: `check-67a07ae481984928bb59e8e90f9b926d/receipt.json` trong cùng thư mục.
- Frontend cuối: `.runtime/ea21-20261020/check-da44a36c65134ac5873097a1884e67fe/receipt.json`.
- Migration: `.runtime/ea21-20261020/migration-9ee149eeffcb47c5936145dbf48d47ff/receipt.json`.
- Browser fixture: `.runtime/ea21-20261020/browser-1792464121279/receipt.json`.
- Bản cài: `.runtime/ea21-20261020/installed-check.json`, `installed-ui.json`.
- Ảnh thật: `.runtime/ea21-20261020/installed-ui.png`, `installed-ui-mobile.png`.
- Tổng hợp: `.runtime/ea21-completion.json`.

OpenAI Docs đối chiếu20/10: [Authentication](https://learn.chatgpt.com/docs/auth)
phân biệt đăng nhập ChatGPT và API. Chỉ áp dụng luồng cá nhân hiện có; không suy
thành quyền chia sẻ thuê bao hoặc buộc chuyển sang danh tính/gói tổ chức.
