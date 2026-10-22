# Codex cá nhân — Nghiệm thu native local bằng model thật

Ngày 20/10/2026, khoảng 11:41–11:45 giờ Việt Nam. Nguồn/cài đặt: `F:\PAO-ACOS`.

## Kết quả

**Đạt phạm vi chat Codex cá nhân qua PAO bằng quota thuê bao thật.** Sau khi
người dùng đăng nhập lại, toàn bộ thao tác cấu hình và gửi yêu cầu thực hiện qua
UI PAO chính chủ; không dùng SQL/JWT chẩn đoán để thay thế phiên đăng nhập.

- Đúng doanh nghiệp PAO-Business Operating Systems và tài khoản demo@pao.local.
- Đọc danh mục Client bằng nút mới; model cũ `gpt-6.1-sol` không có trong danh mục.
- Chọn `gpt-6-astra` được Client đánh dấu mặc định, xác nhận và Lưu model.
  Hồ sơ tăng v5 → v6; thiết lập cũ yêu cầu lưu lại, không tự repin công việc cũ.
- Xác nhận/Lưu thiết lập cá nhân v1 → v2. Không tạo grant, không chia sẻ hồ sơ.
- Tạo chat mới: memory=false, knowledge=false, cloud_references=false.
  Đặt max_calls=2 và max_output_tokens=256; đây là giới hạn policy/reservation
  PAO, không chứng nhận CLI áp dụng hard cap token phía nhà cung cấp.
- Gửi đúng **một job** với yêu cầu tổng hợp không chứa dữ liệu doanh nghiệp:
  `Chỉ trả lời đúng chuỗi PAO_CODEX_OK. Không dùng công cụ, không đọc tệp, không truy cập dữ liệu doanh nghiệp.`
- UI và DB đều ghi phản hồi chính xác `PAO_CODEX_OK`, Run completed/error=null.

## Ledger thật

- Session: `bedcc41e-4c63-4549-a8b7-ce64a0064c82`.
- Run: `549f5816-5655-4489-a4b6-6bbfa25dfa7d`, authority `personal_cli`.
- `chat_planner`: completed/reported, input2294/output69, 17296ms.
- `chat_final`: completed/reported, input1719/output9, 11452ms.
- Hai attempt đều `codex_cli / gpt-6-astra`; hai dispatch completed.
- Tổng reported input4013/output78 = **4091 token**. Không phải quota còn lại,
  số tiền bị trừ hay cam kết chi phí bằng0; không có giá/hóa đơn trong bài thử.
- ToolCall0, MemoryJob0; không retry, không API fallback hoặc local extraction.
- Đọc cuối: setup_operation_pending=false, unresolved_dispatches=0.

API health200/ready200, Web200; Postgres/Redis local healthy. Docker không còn
container Codex job/metadata sau thử. Các container Temporal lịch sử đang dừng;
không khởi động lại vì không thuộc bài thử chat này. Không suy ra toàn bộ
Temporal/workflow/production healthy từ kết quả trên.

## Giới hạn và bước kế tiếp

Đây là đóng gate **native personal Codex chat sau sửa model/planner**, không
phải full backend regression mới, nghiệm thu dữ liệu thật của doanh nghiệp,
owner pilot, toàn EA2/P8.4/S6 hoặc production. Lượt này không sửa code ứng dụng,
dependency, schema, `.env`, tài khoản Codex, binary/image hoặc credential cache
bằng tay; chỉ lưu cấu hình qua UI, một chat/job thử và tài liệu/bằng chứng.
Không restore primary, sửa backup001, commit/push hay deploy.

Giữ nguyên các failure19/10 và20/10 trước sửa cùng receipt cũ. Report sửa code
vẫn chứa trạng thái pending lịch sử; cập nhật này thay thế gate đăng nhập/chạy
thật đó, không xóa lịch sử. Tests413 backend tập trung/209Node/typecheck/build23
là bằng chứng trước cài của cùng source, không được ghi thành lần chạy mới.

Theo thứ tự roadmap: **EA2.2**, sau đó EA3; Claude Code/Antigravity chưa có adapter
được nghiệm thu, không bật sẵn hoặc giả là đã kết nối. P8.4-D/Knowledge và khả
năng dùng chung có kiểm soát cho cộng sự vẫn là gate riêng.

## Bằng chứng

Trong `.runtime/codex-live-acceptance-20261020/`:

- `configured.json`, `before-job.json`, `during-job.json`, `after-job.json`.
- `native-success.png`: UI PAO hiển thị model và câu trả lời thật.
- `observe.py`: giao dịch SQL read-only, pin đúng actor/workspace/session,
  không xuất credentials hay nội dung chat ngoài prompt kiểm thử đã xác định.
- `completion.json`: tổng hợp phạm vi nghiệm thu và kiểm tra sức khỏe.

Đối chiếu [Non-interactive mode của Codex](https://learn.chatgpt.com/docs/non-interactive-mode)
ngày20/10; nghiệm thu thực tế dựa trên UI và ledger ở trên, không chỉ tài liệu.
