# ADR P3 — Context, privacy, hội thoại và usage

Ngày 06/10/2026. Phạm vi: PAO-ACOS local MVP, không M4/production/cloud smoke thật.

## Quyết định

- `modules/chat` chứa compiler thuần, policy, compaction, command parser,
  ledger và router. `runtime` chỉ nối các bước; giữ DTO/SSE cũ.
- Feature `CHAT_FEATURES_ENABLED` mặc định false, yêu cầu Engine Contract.
  Migration 0032 additive: metadata session, parent retry, compaction và ledger;
  hai bảng mới, không viết lại nội dung lịch sử hoặc artifacts M2.
- Byte budget đo JSON UTF-8; token estimate `utf8-div2-framing-v1` là heuristic,
  không phải tokenizer. Giữ nguyên system/prompt/references, bỏ nguyên message
  history cũ; bắt buộc quá lớn thì fail, không cắt nửa câu hoặc tự fallback.
- Compiler chạy trước planner, specialist, final và extraction. Knowledge P2 và
  các skill deterministic không gọi model, không tạo token usage giả.
- Chỉ model/skill đã chọn vào context; không nạp toàn bộ skill registry bodies.
  Skill, memory, tool results, dependency drafts và cache là dữ liệu không tin cậy.
- Mặc định local_only. Cloud chỉ được chọn sau opt-in session, chốt policy vào
  run và recheck quyền mỗi call. Không tự fallback. Lịch sử local/Knowledge,
  Memory và PAO intelligence không tự rời máy. Cloud references cần opt-in riêng
  và lịch sử gốc đã cloud_allowed; bật sau không cấp quyền hồi tố.
- Extraction dùng Ollama model/endpoint chốt server-side trong run, không gọi
  workspace default cloud. Run cũ thiếu extraction pin sẽ fail closed.
- Compaction `extractive-v1` là cache đoạn trích nguyên message có giới hạn,
  không phải LLM summary. Có revision/source IDs/hash; originals bất biến bởi API.
  DB trigger cấm UPDATE cache. Source sửa/revoke/Brain khác thì bỏ cache.
  Cache không thể thay identity của approval, evidence hoặc tool execution.
- `/help /status /brain /tasks /memory /model /usage /compact /export /stop`
  dùng parser chung, không shell/provider/job cho thao tác quản lý. `/brain UUID`
  và `/model provider model` tái sử dụng guard hiện có. Telegram tái dùng parser
  khi P7 được nghiệm thu; hiện Telegram tắt. `/goal` bị chặn đến P6.
- Tìm toàn văn PostgreSQL simple/GIN, pin/group, fenced Markdown download và
  retry run mới có parent reference. Retry giữ lịch sử, chốt lại model/Brain/
  policy hiện tại, không tiếp tục artifacts/approval của run cũ. Search/export
  kiểm tra Brain/source ACL trước khi dùng message. Limits search100sessions,
  history500messages; export5000messages/2MiB; API báo quá giới hạn, không giả đủ.
- Attachment text/Markdown tiếp tục dùng file service/renderer P1/P2. Không
  thêm HTML thực thi, đọc arbitrary path, PDF/vision hoặc auto-download model.
- Ledger một attempt trước mỗi call, unique run/request key; run lock reserve
  call/token budget. Actual reported nullable tách estimated/reserved/unknown.
  Replay callback không cộng lần nữa; cancel/partial cũng có record. Worker crash
  có thể để attempt started/unknown, không giả completed hoặc zero usage.
- Chi phí chỉ tính khi đủ reported counts và owner-configured pricing có
  version/time/currency/provider/model. Đổi model khác binding làm price unknown.
  Không gọi đây là invoice/quota thuê bao. Giá không tự tra hay tự cập nhật.
- Giới hạn local inference dùng PostgreSQL advisory transaction lock dùng chung
  giữa worker cho Ollama stream/planner/extraction/embedding: 1 call đồng thời,
  chờ tối đa3s, busy thì fail; cancel/connection close giải phóng lock. Không
  cam kết GPU bên Ollama lập tức dừng khi client hủy.

## Giới hạn cần nhớ

Planner/extraction reserve512 output tokens; final/specialist dùng giới hạn output
session. Provider không báo usage thì unknown; strict policy chặn trước bước sau.
Heuristic/reservation không phải giới hạn billing tuyệt đối tại vendor. Context
traces chỉ giữ metadata/IDs/budgets, không prompt hay chain-of-thought; message
gốc và cache vẫn là nội dung riêng tư cần bảo vệ trong database/backup.

Benchmark hai ca recall tổng hợp không chứng minh chất lượng mọi tác vụ. CLI,
goal runner, multi-channel, universal memory summarization, production24/7 và
cloud thật không thuộc gate này. Không tăng quyền Gateway hay mở Ads/email.
