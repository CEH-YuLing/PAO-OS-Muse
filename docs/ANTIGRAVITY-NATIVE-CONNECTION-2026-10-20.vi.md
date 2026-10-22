# Antigravity native — nút Kết nối không nhập lại mật khẩu

Ngày20/10/2026, Asia/Saigon. Target `F:\PAO-ACOS`.

Bản nối tiếp đã cập nhật pin CLI và cài đường thử có chốt; native thật vẫn
bị chặn trước prompt vì còn công cụ. Trạng thái mới nhất tại
[báo cáo smoke](ANTIGRAVITY-SMOKE-GATE-2026-10-20.vi.md); các số426/89/211
và mô tả chưa có endpoint thử dưới đây là lịch sử trước lát cắt mới.

## Kiểm tra sau khi người dùng báo đã kết nối — bản CLI đã thay đổi

GET thật vào backend đang chạy, bằng danh tính chẩn đoán chỉ dùng GET, trả
`not_checked`, models rỗng, observed_at=null, inference_enabled=false cho đúng
actor/SME đã provision. API/ready/Web đều200. Không lấy trạng thái đó làm bằng
chứng người dùng chưa đăng nhập Google hoặc đã POST kết nối thành công.
Receipt: `.runtime/antigravity-connected-check-71383efac2f94db7b9cd241b78411b43/receipt.json`.

Probe với pin cũ dừng ngay tại assertion SHA256, **chưa khởi chạy CLI**.
File hiện tại dài202003608byte, mtime UTC2026-10-20T08:52:59,
SHA256`b9ebbc8ae00dec96263979d2947124136cdae990811e27eafef1e7f021269192`;
Authenticode xác minh Valid, signer Google LLC. Không suy phiên bản mới từ
mtime hoặc help. Chưa xác định tác nhân thay file; không gọi đó là tự cập nhật
đã được chứng minh. Pin backend vẫn là`e137ee4f...`, không tự chấp nhận hash mới.

Một probe metadata riêng với hash mới chỉ định tường minh trả exit0 và đúng
6model như danh sách dưới; binary trước/sau khớp. CLI tự dùng phiên native,
không hỏi lại mật khẩu hoặc đọc/copy token. Receipt mới:
`.runtime/antigravity-native-catalog-43ac1212c87048458baaedfec38dbf51/receipt.json`.
Không đổi provision/backend, không POST thay chủ, không restart gây mất cache.

**Kết quả: danh mục native đạt trên binary mới; PAO chat/model thật chưa chạy.**
Chưa gửi prompt, chưa xác minh quota/usage, chưa đạt inference acceptance.
Hai việc còn thiếu độc lập: xét tương thích/cập nhật pin binary và triển khai
đường inference có chặn công cụ trước thực thi. Chỉ nới pin không tạo ra adapter.
Không thay config toàn máy/keyring hay dùng API/ADC để vượt chốt. Lượt này chỉ
thêm helper GET chẩn đoán và bằng chứng; không sửa ứng dụng/schema/.env.

## Đã cài và giới hạn

Theo yêu cầu dùng cơ chế Javis: thêm nút Kết nối tại Cài đặt và kết nối → AI
và giọng nói → Nhà cung cấp mô hình → Kết nối qua Client → Antigravity.
Nút dùng phiên PAO đang đăng nhập; không mở terminal hỏi lại email/mật khẩu
PAO. CLI nguyên bản tự dùng phiên native trên máy, PAO không đọc/copy token.

**Đã triển khai nhận Client/danh mục; chưa triển khai Antigravity cho chat hoặc
runner PAO.** Không dùng chữ connected hoặc catalog để xác nhận inference,
quota còn lại, quyền tool hoặc quyền thương mại. Bản MCP ngược chiều trước
đó được giữ như thử nghiệm riêng, không yêu cầu tiếp tục setup mật khẩu đó.

Trong UI: Kết nối hỏi xác nhận dùng phiên local và cảnh báo provider, sau đó
đọc danh mục; có Danh sách model và Kiểm tra lại. Ngắt chỉ xóa trạng thái PAO,
không logout Google/Javis. Backend restart mất cache, cần kiểm tra lại, không
tự đẻ subprocess khi GET status hoặc mở Settings. Không có auto retry.

Phạm vi local provision: doanh nghiệp PAO-Business Operating Systems,
workspace`ef221310-5afc-4c21-9f9e-4aa9bf4b3e79`, actor chính chủ
`165b1fa6-f443-4f66-bddb-51eb5b6e6fa5`. `.runtime/antigravity-native.json` chỉ
chứa định danh, binary/hash và cờ catalog, không credential. Không tự chia
phiên máy cho owner/admin khác hoặc SME khác. Chủ SME không có quyền sửa file
provision của quản trị máy qua API này. Chưa phải cấu hình dùng chung SaaS.

## Kết quả thử native trên máy

Binary`C:\Users\o0o_v\AppData\Local\agy\bin\agy.exe`, version1.2.12,
SHA256`e137ee4f362b5b2f2c37141d4d1d1c12298f6b42873ca6867c618a5b945421df`.
Giữ hash trước/sau, không update CLI hoặc chỉnh global settings/keyring.

CLI này **không nhận** `models --output-format json` dù cờ output-format có ở
help cấp cao. Lượt probe đầu exit1; giữ receiptddfee247..., b7481d95... và
8266d98f...; chỉ lưu nhóm/từ lỗi nằm trong từ điển cố định, không raw token.
Đổi đúng cú pháp metadata `agy models` (nhánh tương thích tương tự Javis),
không retry prompt/inference. Receipt thành công:
`.runtime/antigravity-native-catalog-5162dd30947f487b9ebade3929f90c0f/receipt.json`.

Đã nhận6model, không đăng nhập lại:

- `gemini-3.8-flash-high`
- `gemini-3.8-flash-medium`
- `gemini-3.8-flash-low`
- `claude-sonnet-4-6`
- `claude-opus-4-6-thinking`
- `gpt-oss-120b-medium`

Đây là danh mục do CLI trả, không chứng nhận từng model chạy được hoặc gói
thuê bao có quota. Không đọc email/account details hoặc suy danh tính Google
từ actor PAO. Chỉ gọi metadata, không model prompt, API fallback hay chi tiền.
CLI có thể dùng/refresh phiên chính nó; không tuyên bố native auth store bất biến.

## Cấu trúc và bảo vệ

- `antigravity_native.py`:3API GETstatus/POSTconnect/POSTdisconnect; owner/admin,
  phiên PAO và file provision phải cùng actor/workspace. Recheck sau đọc, rate
  limit5/phút, busy fence và generation chặn kết quả sau disconnect/scope change.
- Binary path phải đúng LOCALAPPDATA của backend, không symlink/junction; hash
  pin trước/sau. Chỉ argv cố định `models`, stdin đóng, tempcwd riêng, env
  allowlist không lấy API key, stdout/stderr giới hạn256KiB/luồng, timeout25s.
- Chỉ xuất slug model hợp lệ, không raw stderr/hints/token/unknown lines. Lỗi
  không tự biến thành đăng nhập chưa thành công hoặc phản hồi AI.
- Đây là metadata subprocess, **không sandbox filesystem/network/tool của CLI**.
  Không mở rộng sang inference bằng cách coi tempcwd hoặc permission Ask là OS
  isolation. Không có prompt/shell/plugin/MCP/model-test endpoint trong module.
- Frontend dùng apiRaw hiện tại, không trường password. State/abort/epoch theo
  actor/SME/role; từ chối phản hồi khác phạm vi, không giữ raw response.

## Kiểm thử và cài đặt

- Source checkpoint trước thay backend/UI:
  `.runtime/p84-foundation-86d279a1cdce46ed96b30fc23c2c9822/source-baseline.zip`.
  Tên helper cũ không biến đây thành milestone P8.4 mới.
- Backend tập trung89/0fail/error/skip:
  `.runtime/antigravity-native-tests-b5f9072ae8b6448096e1e2b569a73832/receipt.json`.
  Gồm native API/ack/auth/revoke/race/error/catalog và regression Codex/MCP;
  không full regression mới. Test native transport dùng fixture, không quota.
- Failuref55be0c4... được giữ: auto-generated ID của case payload256KiB làm
  PYTEST_CURRENT_TEST vượt giới hạn32767Windows; đặt ID ngắn tường minh, không
  giảm payload hoặc bỏ assertion. Log failure không dùng làm acceptance.
- Frontend211Node/typegen/typecheck/build23 đạt trong bản sao riêng:
  `.runtime/model-provider-tabs-frontend-658a88c83a42476798fa826079373ede/receipt.json`.
- Browser Edge fixture1440/390/320, dark/light, no-password/native connect/
  disconnect, quyền/SME/late-response/API forms/history/lostACK đạt:
  `.runtime/model-provider-tabs-browser-1792485764244/receipt.json`.
  Failure1792485657800 giữ nguyên: harness cũ thiếu GETpersonal-cli có sẵn;
  bổ sung fixture đúng hợp đồng, không bỏ assertion chặn unknown requests.
- Cùng bộ browser fixture trên web đang phục vụ3200 sau cài cũng đạt:
  `.runtime/model-provider-tabs-browser-1792486016347/receipt.json`. Đây vẫn là
  dữ liệu fixture có chặn API thật, không phải owner POST hoặc Google live test.
- Hợp đồngAPI426, schema0074/159bảng không migration. Source transport và
  registry/image/profile Codex, Python/dependency và `.env` không đổi.
- Script restart ban đầu dừng trước mọi Stop-Process do CIM lỗi mapping SID.
  Thử Windows PowerShell5 vẫn lỗi. Dùng API query-limited của Windows để kiểm
  đúng executable/start-time/commandline của API/worker, giữ guard worker lạ;
  không đổi SID/account/privilege/WSL/Docker. Đã xác minh idle trước stop.
- `read_owned_pao_processes.py` chỉ query metadata; fallback restart hẹp tại
  `restart_antigravity_catalog_local.ps1`. Không quét/kill theo tên hoặc bỏ
  kiểm commandline. API/worker khởi động hidden, health/ready/Web200, lease khỏe.
- `.runtime/antigravity-native-installed-20261020/before.json` và `after.json`:
  hash159bảng và3archive giữ nguyên, schema0074, `.env`/CLI registry khớp;
  liveOpenAPI khớp source426, GET chưa auth401. Không restore primary.

## Nhà cung cấp và việc chưa đạt

[FAQ Google](https://www.antigravity.google/docs/faq/) kiểm ngày20/10 nói
wrapping agy trong ứng dụng bên thứ ba không được hỗ trợ dưới consumer plan;
Javis chạy được không tạo ngoại lệ. Nút xác nhận/UI ghi cảnh báo, không tuyên
bố Google-supported hoặc commercial-ready. Không đổi API/ADC/billing để che nó.

Chưa có bài POSTconnect từ phiên owner thật qua UI đã cài trong lượt nghiệm
thu tự động: probe native thật và UI/API fixture là bằng chứng khác nhau.
Không mint JWT chẩn đoán để POST hoặc ghi cấu hình thay phiên người dùng.

**Chưa đạt:** chat/runner Antigravity, gọi model thật, immutable attempts/
accounting/cancel model, tool isolation, quyền dùng chung và nghiệm thu thương
mại. EA3 chưa hoàn tất; Claude/EA2.2/VPS/public tiếp tục hoãn. Không trình bày
bản kết nối danh mục này như hoàn tất toàn bộ khả năng Antigravity của Javis.
