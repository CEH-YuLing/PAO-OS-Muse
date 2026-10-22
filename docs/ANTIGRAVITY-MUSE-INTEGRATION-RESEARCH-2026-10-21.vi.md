# Antigravity và Muse Code — kết quả kiểm tra và hướng tích hợp

Ngày kiểm tra: 21/10/2026. Source PAO: `F:\PAO-ACOS`.
Javis chỉ được đọc tại `G:\Javis`; không sửa bản cài hoặc thông tin đăng nhập.

## 1. Kết luận

| Nguồn | Đã xác minh | Chưa đạt |
|---|---|---|
| Antigravity | PAO có native catalog; mã hiện tại không cung cấp general-chat inference. Đã đối chiếu lại driver Javis và tài liệu Google | Adapter suy luận trong PAO; cách ly công cụ; đường consumer wrapper được Google hỗ trợ |
| Muse Code | Binary chính chủ Meta 1.4.10 có chữ ký hợp lệ; bắt tay MSP và đọc catalog thành công qua `muse serve` | Đăng nhập/gói đang dùng, quota, suy luận thật, adapter PAO, UI và Chat/Agent/Job end-to-end |

Không thay backend/frontend, schema, `.env`, profile AI, credential hoặc cấu hình
CLI. Không restart, cài SDK, cập nhật CLI, gửi prompt hoặc tự chuyển API trả phí.
Tài liệu này là kết quả nghiên cứu, không phải biên bản nghiệm thu provider.

## 2. Vì sao Antigravity chưa hoạt động trong PAO

### Phần mềm PAO

- `apps/api/pao/modules/cli_connections/antigravity_native.py` khai báo rõ là
  native catalog, không phải execution adapter; status trả `inference_enabled=false`.
- `antigravity_smoke.py:init_gate` từ chối trước khi gửi prompt nếu registry
  công cụ không rỗng. Chỉ chọn được model không tạo bộ chạy hội thoại.
- Bằng chứng 20/10 trong `ANTIGRAVITY-QUOTA-RECHECK-2026-10-20.vi.md`:
  catalog 6 model; smoke và ba biến thể discovery vẫn có 60 công cụ, dù khai báo
  `tools: []`; không có prompt hoặc suy luận thật. Đây là bằng chứng lịch sử,
  không gọi là một lượt quota mới ngày 21/10.

### Khác biệt với Javis

`G:\Javis\server\antigravity_cli.py:704` dựng tiến trình native và ở chế độ
`auto/full` có thể thêm `--dangerously-skip-permissions`. Chế độ suggest có thể
dùng sandbox nhưng bình luận của chính driver nói không có bảo đảm read-only
như một số CLI khác. Không sao chép lựa chọn tự duyệt này để làm PAO báo thành công.
Tìm kiếm giới hạn trong `G:\Javis\server` chưa tìm thấy driver Muse Python;
không kết luận mọi phiên bản Javis đều không hỗ trợ Muse.

### Phạm vi nhà cung cấp

Google phân biệt script cá nhân/CI trực tiếp với việc nhúng `agy` vào ứng dụng
bên thứ ba. Giải thích 16/10 nói FAQ hiện hành thay thế bình luận diễn đàn cũ
mâu thuẫn: consumer plans không hỗ trợ kiểu wrapper thứ hai, kể cả binary nguyên
bản và không trích OAuth token. Hướng Google đề xuất cho orchestrator ngoài là
Gemini Enterprise hoặc AI Studio API, cần đánh giá điều kiện/chi phí riêng.

Nguồn:
[giải thích 16/10](https://discuss.ai.google.dev/t/clarification-on-consumer-plan-policy-for-invoking-official-agy-via-local-subprocess/189905),
[FAQ](https://www.antigravity.google/docs/faq/).

Google cũng xác nhận ACP `enabledTools: []` không tắt toàn bộ core tools;
thư mục trống không bảo đảm loại mọi ngữ cảnh ngầm. Đây là chốt kỹ thuật độc lập,
không phải lỗi mật khẩu PAO.
[Nguồn về ACP](https://discuss.ai.google.dev/t/official-acp-1-3-0-supported-consultation-only-controls-on-an-individual-google-ai-pro-account/186726).

Hướng xử lý: giữ trạng thái catalog-only trung thực; không lặp smoke với đầu vào
không đổi, không bỏ init gate hoặc lấy token. Nếu chủ sở hữu chọn Gemini API/
Enterprise, dùng đường tích hợp được hỗ trợ và ghi chi phí/phạm vi rõ, không
đặt tên API trả phí thành quota Antigravity thuê bao. Hướng Antigravity gọi MCP
PAO chỉ đọc là chiều kết nối khác, không làm PAO Chat dùng Antigravity inference.

## 3. Muse đã cài và kết quả metadata thực tế

Đây là **Meta Muse Code**, không phải dịch vụ khác cùng tên.

- Launcher: `C:\Users\o0o_v\AppData\Local\Programs\muse\muse.cmd`.
- Binary đã gọi trực tiếp, tránh cơ chế tự cập nhật launcher:
  `muse-bin-1.4.10-R6427.1.exe` trong cùng thư mục.
- `--version`: `Muse Code 1.4.10 (1.4.10-R6427.1)`.
- Authenticode: `Valid`, signer `Meta Platforms, Inc.`.
- SHA256: `893a04138b81d844cc53e25216fafe0cbf7c786423534b93aacf1419a840f6b7`.

Các lệnh trợ giúp xác nhận `serve`, `schema`, `model-profile`, model override,
reasoning effort và các cờ hạn chế shell/ghi tệp. Đây chưa phải phép đo toàn bộ
công cụ, hook, MCP, memory hoặc ngữ cảnh hiệu lực.

Đã thử giao thức NDJSON/JSON-RPC theo tài liệu chính thức:

1. `initialize` với `clientInfo.name=pao_metadata_probe`.
2. Notification `initialized`.
3. Query `model/list`, không tạo session hay gọi `turn/start`.

Hai host `echo` và `meta` đều trả handshake, catalog và exit 0. Host báo:

```text
serverInfo: muse / 1.4.10
schema.version: 1
schema.fingerprint:
sha256:5d3b43e5ccdb7dc4f5a32c380f5f2cde0f10e3059b93610afb2e73f73b1d914c
catalog_source: providerCatalog
provider_id: meta
```

| modelId thực trả về | reasoningEffortVariants thực trả về |
|---|---|
| muse-wonder-1.0 | mảng rỗng |
| muse-spark-1.3 | mảng rỗng |
| muse-spark-1.2 | xhigh |

Không suy mảng rỗng thành hỗ trợ mọi mức suy luận. Catalog host không chứng minh
tài khoản có quyền chạy tất cả model hoặc còn quota.

Query `account/read` không bật experimental capability trả `-32601`,
`account/read requires experimentalApi capability`. Không đọc credential cache,
không bật experimental trong lượt kiểm này; trạng thái tài khoản/gói chưa xác minh.

Child dùng env allowlist không chuyển tiếp API-key env; không gửi nội dung doanh
nghiệp. Các child do lượt metadata tạo đã kết thúc; kiểm tra sau không còn tiến
trình Muse tương ứng. Lượt asyncio đầu trong sandbox bị treo và đã ngắt; không
tính là pass. Bài thử subprocess có quyền chạy native sau đó mới trả kết quả
thành công nêu trên. Không khẳng định hệ thống chính không có thay đổi từ người
dùng/công cụ khác, vì lượt này không snapshot/đối chiếu toàn database PAO.

## 4. Hướng tích hợp Muse trong GD01

Meta cung cấp MSP qua `muse serve`, SDK TypeScript `@muse-code/sdk` và SDK Python
`muse-code-sdk` cho ứng dụng điều khiển Muse. Ưu tiên giao thức này thay vì mô
phỏng bàn phím hoặc scrape giao diện.
[Tài liệu tích hợp](https://meta-models.github.io/muse-code-sdk/1.4/),
[tài liệu Muse chính chủ](https://dev.meta.ai/docs/muse-code).

| Bước | Phạm vi triển khai và nghiệm thu | Rủi ro/phát sinh |
|---|---|---|
| 1. Contract/candidate | Pin binary/schema; chọn SDK phù hợp hoặc adapter MSP theo schema binary. Không cài vào runtime đang phục vụ để thử | Fingerprint docs hiện khác binary; Python SDK strict có thể từ chối; không bỏ kiểm tương thích |
| 2. Kết nối một lần | Thẻ Muse trong Settings; phát hiện client; đọc status qua interface được hỗ trợ; chỉ mở login chính chủ nếu cần. Không nhập mật khẩu Muse vào PAO, không cấp grant AI từng nhân sự | Backend chạy bằng tài khoản Windows khác không thấy phiên; experimental account surface cần kiểm version/capability |
| 3. Catalog/effort | Dùng nguồn registry hiện có cho Settings và PAO AI; model/effort theo dữ liệu host, có thời điểm/revision; phân biệt đã cài/đã đăng nhập/đã chạy thật | Catalog không phải entitlement; CLI thay model hoặc tự update; không hardcode danh sách 3 model thành cam kết lâu dài |
| 4. Inference adapter | Nối resolver/attempt/dispatch hiện có; MSP session/turn, streaming, lỗi và cancel; không tạo runner nghiệp vụ song song | Tools/memory/hooks ngầm, chết process, duplicate turn sau mất ACK, fallback tính phí |
| 5. Agent/Job | Cùng provider/model/effort và immutable pins cho Chat, orchestrator, Studio/Agent/Job theo contract từng luồng; UI lựa chọn phải khớp attempt thật | Trộn context SME; repin công việc cũ; format JSON planner không đúng |
| 6. Kiểm thử | Offline echo/contract; model không hợp lệ, sai schema, auth hết hạn, quota/429, cancel/timeout/lost ACK, restart, hai SME; rồi một prompt tổng hợp và một job thật có kiểm soát | Bài echo không chứng minh model thật; chưa có evidence thì giữ inference chưa nghiệm thu |
| 7. Cài bản đã kiểm | Checkpoint/backup theo cấu hình đã duyệt; promotion/rollback; cài một lần, người dùng chọn model là sử dụng | Catalog-only không được đổi nhãn thành connected/live; không ảnh hưởng bản CLI người dùng đang dùng |

UX mục tiêu: **Cài PAO → Kết nối Muse → chọn model/mức suy luận → Chat hoặc giao
việc**. Vai trò vẫn kiểm soát cấu hình và hành động nghiệp vụ, không thêm wizard
cấp quyền AI cá nhân. Phạm vi thuê bao/dùng chung thương mại cần xác minh riêng;
SDK hỗ trợ nhúng không tự chứng minh mọi hình thức phân phối đều được chấp thuận.

## 5. Chi phí và dữ liệu phải làm rõ trước suy luận thật

- Subscription Muse áp dụng credential được nối qua CLI onboarding; credential
  đó chỉ dành cho Muse Code. API key tạo thêm tính pay-as-you-go. Không lấy khóa
  CLI để nối cổng API chung. Contributor mode của thuê bao mặc định có thể dùng
  nội dung để huấn luyện; cần giải thích và lựa chọn rõ trước dữ liệu SME thật.
  [Nguồn thuê bao](https://dev.meta.ai/docs/muse-code/subscriptions).
- Muse ưu tiên `META_API_KEY`, rồi stored API key, rồi browser session. Chỉ xóa
  env khỏi child chưa đủ chứng minh dùng quota thuê bao nếu có stored key.
  Phải xác minh đường thanh toán hiệu lực; không tự fallback hoặc mua gói.
  [Nguồn xác thực](https://dev.meta.ai/docs/muse-code/auth).
- Các cờ disable-write/disable-shell không tự chứng minh zero-tool/zero-context.
  Kiểm effective tools, sandbox và ngữ cảnh trước khi gửi dữ liệu doanh nghiệp;
  giữ việc cách ly ở backend thay vì thêm nhiều màn hình cấp quyền cho khách.
  [Nguồn permissions](https://dev.meta.ai/docs/muse-code/permissions).

Toàn GD01 vẫn `in_progress`. Kết quả này không đóng GD01, không phải nghiệm thu
quota Muse/Antigravity, shared-commercial hoặc production.
