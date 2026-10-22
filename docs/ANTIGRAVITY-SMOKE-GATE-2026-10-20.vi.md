# Antigravity — tương thích CLI mới và lượt thử có chốt công cụ

Ngày20/10/2026, Asia/Saigon. Checkout `F:\PAO-ACOS`.

## Kết luận hiện tại

**Đã cài tương thích catalog với binary mới và nút thử có chốt an toàn.
Chưa nghiệm thu gọi model thật, chưa tích hợp hội thoại/runner Antigravity.**

CLI mới có chữ ký Authenticode Valid của Google LLC, SHA256
`b9ebbc8ae00dec96263979d2947124136cdae990811e27eafef1e7f021269192`.
Chỉ thay pin của provision local đã có; không tự tin mọi hash hoặc cập nhật CLI.
Không suy số phiên bản từ mtime. Giữ provision trước tại
`.runtime/antigravity-smoke-install-20261020/native-provision-before.json`.
Pin/hash/code/profile Codex, Python và dependency không đổi.

Native catalog hiện đọc được6model. Tuy nhiên agent thử khai báo `tools: []`,
không delegation/skills/plugins/MCP, vẫn nhận init có60công cụ, bao gồm
`run_command`, `view_file`, `write_to_file`, `invoke_subagent`.
Đã thử cả cwd có neo project `.antigravitycli`; không vượt chốt bằng cách bỏ
kiểm tra hoặc dùng `--dangerously-skip-permissions`. Init có đúng model/agent
và request-review không đủ chứng minh tắt công cụ. Chưa xác định đây là lỗi
discovery, semantics cấu hình hay giới hạn CLI; không tuyên bố bất khả thi.

Receipt no-prompt có danh mục công cụ đã lọc:
`.runtime/antigravity-text-gate-9b12535e5d714524bb0307509b990bf5/receipt.json`.
Receipt transport cuối:
`.runtime/antigravity-native-smoke-ff06329c5ada4a28b9b13446f5d1b038/receipt.json`.
Native trả `tools_not_disabled`; **prompt_sent=false**, không gửi câu thử model,
không có kết quả/token usage thật. Đây là chốt chặn đạt, không phải model pass.

## Đã triển khai

- Thông báo riêng `binary_changed`: yêu cầu quản trị máy xác minh/cập nhật pin,
  không đánh đồng đổi binary với lỗi đăng nhập và không xin mật khẩu lại.
- POST `/v1/workspaces/{workspace_id}/antigravity-native/test`: owner/admin,
  đúng actor/SME provision, phiên PAO hợp lệ, catalog đã kiểm tra và có model
  cố định. Xác nhận thử riêng `acknowledge_fixed_model_test` bắt buộc; chỉ
  đồng ý đọc catalog không đủ. Giới hạn2lượt/phút, busy/generation fence.
- Transport dùng stdin NDJSON: đọc init **trước khi gửi câu hỏi**; chỉ khi
  tools là mảng rỗng, đúng agent/model/request-review và UUID hợp lệ mới
  kiểm hash + quyền lại rồi gửi đúng một câu cố định. Không gửi dữ liệu SME.
- Chỉ thử `gemini-3.8-flash-low`, yêu cầu đáp `PAO_ANTIGRAVITY_OK`; không
  arbitrary prompt, resume, retry hoặc fallback. Env allowlist không kế thừa
  API keys. Không đọc/copy keyring/token, không chỉnh cấu hình Antigravity toàn máy.
- stdout/stderr hữu hạn, timeout35s; chỉ công bố kết quả sau terminalSUCCESS,
  một turn, response khớp, exit0 và kiểm quyền/pin sau chạy. Usage thiếu là
  unknown, không tự quy đổi quota còn lại hoặc tiền. Không xuất raw diagnostics.
- Tiến trình riêng được kill/wait trong finally kể cả khi chặn init. Cwd thử
  tách biệt và bị dọn sau lần chạy; **không coi cwd/Ask hoặc parser là OS sandbox**.
- UI có “Thử model an toàn”, xác nhận quota/rủi ro riêng, giải thích lỗi Việt
  ngữ, giữ trạng thái catalog khi thử bị chặn; không tự thử lại. Không thêm
  Antigravity vào model mặc định hoặc chat/runner đang phục vụ.
- Thu hồi/chuyển actor/SME/config trước dispatch hoặc sau kết quả chặn trả
  thành công. Chốt không hoàn tác một prompt đã gửi; đây chưa phải hệ thống
  accounting/cancel/recovery tổng quát cho chat hoặc background jobs.

Đây là đường smoke bị chặn trên CLI hiện tại, chưa phải immutable dispatch
ledger dùng chung SaaS. Không bật cho nhiều người/SME hoặc đưa vào job routing
trước khi hoàn thiện isolation, attempt/accounting/cancel và nghiệm thu thật.

## Kiểm thử và cài đặt

- Checkpoint trước sửa ứng dụng:
  `.runtime/p84-foundation-44c6d3e27b29404d9ff1b737b014eabc/source-baseline.zip`.
  Tên helper lịch sử không tạo một milestone P8.4 mới.
- Backend cuối108/0fail/error/skip, chạy serial pao_test/Redis15:
  `.runtime/antigravity-native-tests-dc0e7872950f4e96aad41051c11fbf98/receipt.json`.
  Gồm chặn stdin trước prompt, authority revoke, kết quả/malformed JSON,
  late tool, catalog/race và regression Codex/MCP. CLI trong test dùng fixture.
  Giữ failure5f9f14e6...: fixture tạo StreamReader ngoài event loop; sửa thành
  async fixture, không giảm assertion hoặc payload. Không full regression mới.
- 212Node/typegen/typecheck/productionbuild23 đạt trong source-only copy:
  `.runtime/model-provider-tabs-frontend-827c077cb1274d6c82892ccdcb861865/receipt.json`.
- Edge fixture trên web3200: xác nhận/dismiss thử, tools-blocked, không retry,
  no-password, phân quyền/SME/API forms/lostACK/dark-light/1440-390-320 đạt:
  `.runtime/model-provider-tabs-browser-1792487614632/receipt.json`.
  Không forward backend/provider thật; không gọi đó là owner native POST pass.
- Trước restart giữ log cũ trong thư mục install; kiểm idle và đúng
  PID/executable/start-time/commandline. Chỉ restart API/ARQ, giữ web/Docker.
- Sau cài API/ready/Web200, worker lease khỏe; OpenAPI427 khớp, schema0074
  giữ nguyên. Hash159bảng/3archive/.env/Codexregistry không đổi:
  `.runtime/antigravity-smoke-install-20261020/after.json`. Không migration,
  restore primary, pip update, push/deploy hay Ads/Telegram activation.
- Binding backend cuối:
  `9e5e6b393ec2129741fe8bc527e20f451d44bb909a4c82f1391fbcaba0167391`.

## Nguồn và chốt còn lại

Đã đọc lại tài liệu chính thức20/10:

- [Headless](https://www.antigravity.google/docs/cli/headless/): native cached
  session, stream-init/result, tools và usage; exit0 không tự chứng minh tool denied.
- [Custom agents](https://www.antigravity.google/docs/subagents/): vị trí Markdown,
  mainAgent/tools/MCP/skills; cấu hình trong tài liệu phải đối chiếu native thật.
- [FAQ](https://www.antigravity.google/docs/faq/): consumer third-party wrapper
  không được hỗ trợ. Cảnh báo và xác nhận không tạo quyền nhà cung cấp hoặc
  chứng nhận thương mại. Không tự chuyển sang API/ADC/Enterprise hoặc billing.

Chốt thực tế tiếp theo là chứng minh khóa công cụ/native configuration hoặc
biên cách ly phù hợp **trước** prompt. Không giải quyết bằng password PAO,
đọc token, bỏ parser hoặc nới quyền tool. Sau đó mới nghiệm thu một model
thật/usage, rồi thiết kế attempt/ledger/cancel để nối vào chat/routing hiện có;
không tạo thêm business runner hoặc tuyên bố toàn EA3 hoàn thành.
