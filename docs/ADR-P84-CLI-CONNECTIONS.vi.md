# ADR-P8.4 — Kết nối CLI Codex, Claude Code và Antigravity

Ngày quyết định: 18/10/2026, Asia/Saigon. Người dùng duyệt bắt đầu triển khai
kế hoạch P8.4; đợt đầu giới hạn A/B theo lời mở đầu, hoàn thiện trọn nền móng và
kiểm thử trước C. Không phải quyền chạy AI thuê bao, public SaaS hoặc mở shell.

## 1. Mục tiêu và thứ tự

PAO không bắt buộc cài local LLM; Ollama/API vẫn là lựa chọn riêng sau chuyển đổi.
CLI vẫn sử dụng LLM và có quota; không quảng cáo miễn phí hay không giới hạn.
Giữ master roadmap làm nguồn trạng thái duy nhất, không tạo runner thứ hai.

| Chặng | Phạm vi | Chốt |
|---|---|---|
| P8.4-A | Hợp đồng, baseline, kiểm kê và quyết định kiến trúc | Tách kỹ thuật, quyền PAO và quyền nhà cung cấp |
| P8.4-B | Package vận hành tiến trình và kiểm thử offline | Không đăng ký engine hoặc gọi CLI thật |
| P8.4-C | Codex local, ưu tiên exec JSON cho bounded jobs | Phiên bản thực tế, login chính thức, native grants/accounting và sandbox |
| P8.4-D | Gỡ bắt buộc Ollama, tách memory/embedding | Không xóa model; FTS còn hoạt động; không đổi pin job cũ |
| P8.4-E | Settings tiếng Việt, routing, usage | SME/brand/agent/step/job, không kế thừa quyền nhà cung cấp ngầm |
| P8.4-F.1 | Claude Code | Chọn CLI/SDK sau spike; kiểm soát tool, hook/MCP và điều kiện sử dụng |
| P8.4-F.2 | Antigravity | Offline adapter trước; chốt điều kiện tích hợp trước live OAuth |
| P8.4-G | Nghiệm thu tổng thể và chuyển mặc định có phạm vi | Fixture khác live; không tự đóng S6/production |

## 2. Cấu trúc

`packages/cli-runtime/pao_cli_runtime` là thư viện vận chuyển và hợp đồng thuần
Python, chưa nằm trong dependency backend. Không sửa provider enum/snapshot cũ.
Không thay gateway chat, goal, Studio, ARQ hoặc Temporal hiện có. P8.4-C mới nối
adapter vào engine và tái sử dụng admission/grants/accounting/ledger hiện hành.

Phân biệt provider (Codex/Claude/Antigravity), transport (CLI/SDK/RPC), billing
(thuê bao/API), account owner và device/profile. Không đưa OAuth vào
`api_key_ciphertext`. Thêm loại reference/metadata phải được migration review
riêng; chặng A/B không thêm bảng hoặc migration.

Mỗi dispatch cần identity tuple gồm workspace, actor, brand (nếu có), connection,
profile, device, attempt. Tuple là dữ liệu, không phải authority. Khi nối native
phải resolve từ server, kiểm tra grants hiện hành trước gửi và trước trả, đồng
thời chặn queued execution sau thu hồi membership/grant. Không tin header scope.

Engine snapshot mới cần version riêng và reader tương thích lịch sử, pin model,
binary/version, authority revision và cấu hình. Không viết lại snapshot/hash
hoặc đổi model giữa run. Phiên provider không được resume bằng "most recent".

## 3. Chính sách mặc định

- Không nạp .env, PATH, proxy, SSH agent, API keys hoặc home gốc vào child fixture.
- Không nhận arbitrary executable/argv qua UI; command builder phải server-owned.
- CLI tương lai không nhận credential Ads/Telegram, quyền duyệt hay toàn ổ đĩa.
- Một owner có nhiều SME vẫn cấp phạm vi riêng, không trộn memory/file/phiên.
- Không mặc định chia thuê bao cá nhân cho nhân viên hoặc pool nhiều khách hàng.
- Không fallback sang API/credits, mua quota hoặc xoay account để né hạn mức.
- Unknown usage là unknown. Job yêu cầu reported usage vẫn phải từ chối khi thiếu.
- Ngắt kết nối PAO khác logout CLI. Không tự thu hồi phiên ứng dụng khác.
- Thất bại sau dispatch là trạng thái cần đối soát; không tự retry với attempt cũ.

## 4. Giới hạn nền móng A/B

`FixtureTransport` chỉ có thể chạy fixture nguồn đi kèm; `external_dispatch`
luôn từ chối. Metadata cả ba nhà cung cấp không chứng minh live entitlement.
Không có quyền công cụ, sandbox filesystem/network hoặc native authority adapter.

Windows Job Object / POSIX process group chỉ kiểm soát vòng đời. Fixture đợi
stdin tới khi gắn containment; launch race-free cho binary thật là gate C/F.
Không dùng prompt "chỉ đọc", cwd hay profile riêng thay cho rào OS thực sự.

Duplicate fence bộ nhớ chỉ chống trùng trong một instance; không chứng minh
exactly-once qua restart. Native durable ledger là việc bắt buộc ở C/F, không
thêm database/queue riêng trong package. API/worker chưa import package này.

Không tuyên bố 26 unit tests thay cho hồi quy backend, owner pilot hoặc kết nối
thật. Baseline source-only chụp sau khi thêm package và trước cập nhật docs/CI,
không phải backup DB trước triển khai. Schema đọc SELECT-only; không đo hash
nội dung nghiệp vụ, không kết luận về sự cố primary drift lịch sử.

## 5. Settings dự kiến (E, chưa triển khai)

AI và giọng nói: Tài khoản AI / Thiết bị chạy / Phân công AI / Giới hạn sử dụng /
AI trên máy. Tách cài đặt, đăng nhập, danh mục, suy luận và quyền thương mại.
Hướng dẫn từng trường, lỗi thường gặp, save/test/activate/disconnect bằng tiếng
Việt. Không yêu cầu token trong chat hoặc ô nhập OAuth session.

## 6. Nguồn đối chiếu ngày18/10/2026

- OpenAI CLI: https://learn.chatgpt.com/docs/cli/reference
- App Server, local auth và hạn chế thương mại/hosted:
  https://learn.chatgpt.com/docs/app-server
- SIWC plan usage, nhánh local/OSS khác ứng dụng paid/remote:
  https://developers.openai.com/siwc/token-sharing-open-source
- Claude Code headless/SDK và lưu ý bare mode không dùng subscription login:
  https://code.claude.com/docs/en/headless
- Claude binary nguyên bản, customer authentication, giới hạn credential routing:
  https://code.claude.com/docs/en/legal-and-compliance
- Antigravity headless/JSON: https://antigravity.google/docs/cli/headless/
- Antigravity OAuth/third-party và phạm vi điều khoản Enterprise khác tài khoản
  cá nhân: https://antigravity.google/terms

Chưa có xác nhận quyền commercial/hosted hoặc Antigravity third-party OAuth.
Hỗ trợ headless không tự chứng minh quyền cung cấp sản phẩm. Các chốt này không
chặn unit fixture nhưng chặn live activation tương ứng. Không lấy token/giả client.

Javis local G:/Javis báo VERSION 0.204.0: Claude factory dùng Agent SDK;
Codex/Antigravity có adapter subprocess. Git HEAD local chưa xác minh vì quyền
Git, không gán commit GitHub cho bản local. Chỉ đọc code, không auth store.
GitHub tham khảo aaa470d7fccb4ff0d24a4d1f23d63f0d471fa1ae, license MIT;
không chép implementation Javis vào package mới. Nếu tái sử dụng sau phải giữ
copyright/license, và điều khoản provider vẫn độc lập.

## 7. Rollback

A/B không thay DB/config/engine đang phục vụ. Vô hiệu bằng việc không đăng ký
package; không cần restore primary hoặc gỡ Ollama. Archive/source manifests
giữ để đối chiếu. Không xóa file mới/untracked tự động hoặc reset Git.
