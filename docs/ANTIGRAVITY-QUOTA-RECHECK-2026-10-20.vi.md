# Antigravity — thử lại kết nối và chốt quota thật

Ngày 20/10/2026. Checkout `F:\PAO-ACOS`.

## Kết luận

**Đọc được catalog native 6 model; lượt suy luận thật vẫn bị chặn trước
prompt. Chưa nghiệm thu quota thật, chưa bật Antigravity cho hội thoại/job.**
Đây là kiểm tra mới theo yêu cầu người dùng, không tái sử dụng kết quả cũ
để gọi là lần chạy model mới.

## Bằng chứng mới

- Binary đúng pin
  `b9ebbc8ae00dec96263979d2947124136cdae990811e27eafef1e7f021269192`,
  chữ ký Authenticode Valid, chủ thể Google LLC. Không cập nhật CLI hoặc pin.
- Chạy `scripts/check_antigravity_smoke_live.py` bằng runtime Python đã ghim.
  Script dùng đúng transport của ứng dụng, kiểm tra owner/SME bằng SQL chỉ đọc,
  gọi native catalog, rồi kiểm init trước khi ghi stdin. Không tạo bearer POST
  hoặc thay cho phiên đăng nhập của người dùng.
- Receipt mới:
  `.runtime/antigravity-native-smoke-ea416b83a0434435b374148730c78ef1/receipt.json`.
  Model mục tiêu `gemini-3.8-flash-low`; catalog có 6 model; kết quả
  `blocked/tools_not_disabled`, `prompt_sent=false`,
  `model_quota_test_sent=false`, `inference_verified=false`.
  Không có response/usage thật; không suy ra quota còn lại hay cam kết mức phí.
- Thêm probe không-prompt `scripts/probe_antigravity_agent_discovery.py`:
  so sánh thư mục trống, marker `.antigravitycli`, và Git repository tạm riêng.
  Cả 3 init đúng model/agent/request-review nhưng đều còn **60 công cụ** dù
  agent khai báo `tools: []`. Mỗi tiến trình riêng đã được dừng/wait; thư mục
  fixture tạm được dọn; giữ receipt ngoài thư mục tạm:
  `.runtime/antigravity-agent-discovery-64df4e42967541edb461b8036c3bf106/receipt.json`.
  Không gửi prompt, không chạy subagent hoặc công cụ do model gọi.
- `agy agents` trên thư mục probe cũ trả exit 0 nhưng không có danh sách.
  Không suy ra agent đã được nạp chỉ từ tên agent trong init. Chưa kết luận
  nguyên nhân là discovery, semantics main-agent hay lỗi phiên bản CLI.
- Đối chiếu source `G:\Javis\server\antigravity_cli.py`: Javis dựng tiến trình
  native với model, output stream và prompt. Không lấy cấu trúc đó làm bằng
  chứng cách ly công cụ hoặc quyền nhà cung cấp của PAO; không sửa Javis.
- Không có tab IAB đang mở để cập nhật catalog qua phiên PAO của owner. Không
  tự tạo phiên POST hoặc yêu cầu đăng nhập lại vì đăng nhập không gỡ chốt tool.

## Tình trạng PAO sau thử

Installed GET-only pass:
`.runtime/installation-ai-live-0caef8d245984cae8be468cc6c2a1dc7/receipt.json`.
API/ready/Web 200, worker/contract/pin đạt, replay HTTP lịch sử 3/3, schema
0075/161 bảng/429 operations, binding
`f596abc415cb9e97b18b7da6e5e1d937fe9194ac82896ea73badcc6d3ac1bf3a`.
Primary không đổi trong cửa sổ kiểm installed này; không khẳng định đó là
snapshot đối chiếu dữ liệu của toàn lượt thử trước đó.

Không sửa backend/UI đang phục vụ, schema, `.env`, credential hoặc cấu hình
Antigravity toàn máy. Không restart PAO, không API billing/fallback, không
đọc/copy keyring/token, không provider activation hoặc production pass.
Probe mới được chạy native 3 ca và kiểm cú pháp; không có full regression mới.

## Nguồn chính thức và việc còn thiếu

Đọc lại ngày 20/10/2026:

- [Headless](https://www.antigravity.google/docs/cli/headless/): cached login,
  init ghi công cụ khả dụng, stream và usage. Headless/Ask không tự chặn đọc
  và ghi trong workspace; không dùng exit 0 thay cho kiểm tra an toàn.
- [Custom agents](https://www.antigravity.google/docs/subagents/): vị trí agent
  và giới hạn tools cần đối chiếu với binary thực tế.
- [Permissions](https://www.antigravity.google/docs/permissions?tab=cli):
  có deny/ask/allow toàn máy; không sửa global settings để thử áp dụng cho PAO,
  vì sẽ ảnh hưởng các ứng dụng khác và chưa chứng minh chặn toàn bộ công cụ.
- [FAQ](https://www.antigravity.google/docs/faq/): Google nêu consumer plans
  không hỗ trợ bọc `agy` trong ứng dụng/agent bên thứ ba. Sự tồn tại của Javis,
  chữ ký binary và xác nhận người dùng không tạo chứng nhận hỗ trợ thương mại.

Hai chốt độc lập còn thiếu: (1) cấu hình native hoặc biên cách ly có thể kiểm
chứng trước prompt; (2) đường tích hợp có hỗ trợ từ nhà cung cấp cho mục tiêu
thương mại. Không giải quyết bằng bỏ `init_gate`, auto-approve tools, lấy token
hoặc tự chuyển sang API/Enterprise có tính phí. Nếu chọn phương án API hoặc
gói khác, cần người dùng chọn riêng; không thay đổi chi phí ngầm.

Các bằng chứng smoke0074 trước đây vẫn là lịch sử; bản cài hiện tại là0075.
Toàn đợt AI resource/model/effort vẫn `in_progress`.
