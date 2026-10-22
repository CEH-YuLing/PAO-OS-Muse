# Ngữ cảnh và đầu ra theo mô hình — 22/10/2026

## Kết quả và phạm vi

Đã cài trên local: lượt mới mặc định `token_mode=provider`, không áp các trần
token context/output/tổng run riêng của PAO. UI bỏ ba ô Giới hạn context,
Giới hạn output và Ngân sách run. Chọn model/effort không cần cấp quyền AI mới.
Không có model nào có context vô hạn; bỏ trần PAO không làm tăng dung lượng
thật của model và có thể tăng chi phí, thời gian chờ hoặc mức sử dụng thuê bao.

Nguyên nhân lỗi Muse đã xác minh từ metadata: native hoàn thành nhưng ledger
từ chối planner/đầu ra vượt512 token. Bản sửa không sửa lịch sử hoặc gửi lại
prompt của người dùng. Tải lại trang và gửi một lượt mới để dùng chính sách mới.

## Thay đổi đồng bộ

- Chính sách mặc định, compiler context, ledger, planner, specialist, extraction
  và job Studio dùng chung chế độ provider. Không loại lịch sử chỉ vì số token
  hay giới hạn100lượt/12tin cũ trong đường history provider-mode; quyền đọc và
  lựa chọn nguồn/context vẫn áp dụng. Không tự bật memory/Knowledge/cloud reference.
- OpenAI/OpenRouter bỏ tham số giới hạn output của PAO khi ở provider-mode;
  Gemini bỏ `maxOutputTokens`; Ollama không áp `num_ctx/num_predict` riêng của PAO.
- Anthropic bắt buộc `max_tokens`: đọc khả năng model bằng Models API, không đoán
  trần theo tên model; thiếu metadata thì báo lỗi rõ, không tự chọn model khác.
- Muse không còn bị từ chối bởi minimum budget hay512 output của PAO. Usage thực,
  nguồn/model/effort, attempt, replay và dọn native process vẫn được ghi nhận.
- Chat và biểu mẫu routing bỏ token cap khỏi trải nghiệm thường dùng. Numeric
  fields cũ giữ để tương thích API bounded rõ ràng và snapshot lịch sử; không
  âm thầm viết lại hợp đồng đã duyệt, job cũ hoặc execution binding của chúng.
- Quota token mặc định theo ngày không trở thành trần ngầm cho provider-mode;
  chính sách quota do SME thiết lập rõ ràng vẫn được kiểm tra khi nhận việc.
  Đây không phải bảo đảm giới hạn tiền/đầu ra cứng tại nhà cung cấp.

## Những giới hạn không bỏ

Phân tách SME/Brain, quyền dữ liệu, cloud consent, approval, tool permissions,
max_calls chống vòng lặp, concurrency, timeout, cancellation và lease giữ nguyên.
Không tự fallback API tính phí hoặc tự chạy lại một attempt đã gửi.

Giữ bao an toàn bộ nhớ/truyền tải: compiler/stream8MiB, prompt HTTP tối đa1MiB,
Muse wire8MiB và stdout/stderr16MiB. Quá bao thì báo lỗi, không cắt ngầm.
Các schema nghiệp vụ và input validation vẫn có độ dài tối đa riêng.
**Codex container đang cài giữ transport envelope64KiB** và identity gói native
đã xác minh; không đổi image hoặc repin hồ sơ chỉ để mở rộng payload. Không hứa
mọi request1MiB sẽ được mọi CLI chấp nhận. Mở rộng container transport cần candidate
và kiểm thử pin/isolation riêng; đây là phần tối ưu tiếp, không gọi là vô hạn.

Các lượt đã đóng băng chính sách bounded giữ nguyên. API legacy có thể tiếp tục
gửi `token_mode=bounded`; Web mới lưu `provider`. Toàn GD01/production chưa hoàn tất.

## Nghiệm thu

| Phạm vi | Bằng chứng | Kết quả |
|---|---|---|
| Backend rộng | `.runtime/gd01-tests-cbb0ce6c67f5458a9fa14b189c48cd9e/receipt.json` |552test chức năng đạt; **receipt tổng false** vì bảng sessions thay đổi; giữ lỗi, không restore primary |
| Provider-mode và hai job phụ thuộc | `.runtime/gd01-tests-5d8e70a9bae448c5a5e28d1157fa0de4/receipt.json` |10/10 sau khi giữ nguyên package CLI, primary/source/env/schema không đổi; mocked providers, không quota thật; lượt trước fdc5ae56 cũng đạt |
| Frontend | `.runtime/model-provider-tabs-frontend-b72b3e5405224c21bf1923af1600c060/receipt.json` |262Node, typegen/typecheck/build đạt |
| Browser fixture | `.runtime/chat-controls-browser-1792646340395/receipt.json` |Dark/light320–1600, keyboard, không còn3ô cap; save provider-mode |
| Muse High thật | `.runtime/gd01-tests-79dacb6b7a8d48b39ce58ec655e61d56/receipt.json` |Spark1.2/High planner695 và final1369 output token; completed; replay0call; không dữ liệu primary/tool/fallback |
| Bản cài GET-only | `.runtime/gd01-installed-0fa5a68018b4405b8c75e5c56eb34142/receipt.json` |2SME,5Muse/6Codex,3replay; policy provider được API phục vụ, UI mới, dark/light320/390/1440; API/ready/Web200 |

Native profile/execution unit31test đạt. API providers ở chế độ mới mới kiểm thử
wire giả lập, không coi là nghiệm thu quota thật của Claude/Gemini/OpenAI hay
Antigravity. Lượt High là dữ liệu tổng hợp, không phải nghiệm thu chất lượng
kinh doanh, mọi model hay P6 Goal/Temporal.

Giữ các receipt installed thất bại a8483ca1,4024a4dd,0728b1f3: kiểm tra đã phát hiện
pin package native thay đổi và helper chọn nhầm hội thoại lưu trữ. Đã hoàn nguyên
đúng các thay đổi package transport của lượt này, xác minh pin gốc khớp; helper
chỉ chọn chat chưa lưu trữ. Không bỏ validation/pin hoặc sửa dữ liệu để test qua.

## Backup và vận hành

Trước thay đổi đã backup/khôi phục clone, hash161bảng/3archive và private config:
`F:\PAO-BOS Backup 001\PAO-ACOS-Backups\20261022T050201Z-27bb3fb8b7fb4c2c96c83f4b0997600d`.
Không copy native login, không ghi đè backup cũ, không upload/offsite.
API/ARQ đã restart có kiểm tra PID/start-time đúng process; Web dev nhận source mới.
Không migrate0077, đổi `.env`, credentials hoặc phục hồi đè database.

Nếu context vượt sức model, cần chia tài liệu hoặc compact có kiểm soát; không
coi bỏ cap là tự động tối ưu RAG/compaction. Theo dõi usage và độ trễ trước khi
dùng tài liệu lớn. Các job cũ sai binding cần tạo/duyệt phiên bản mới, không tự repin.

## Tài liệu nhà cung cấp đã đối chiếu22/10

- [OpenAI Chat API](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create)
- [Anthropic Models API](https://platform.claude.com/docs/en/api/http/models/retrieve)
- [Gemini GenerateContent](https://ai.google.dev/api/generate-content)
- [Ollama model parameters](https://docs.ollama.com/modelfile)

Hướng dẫn openai-docs được dùng để đối chiếu wire/API, không đổi quyền tool hay
đánh đồng thuê bao CLI với API key.
