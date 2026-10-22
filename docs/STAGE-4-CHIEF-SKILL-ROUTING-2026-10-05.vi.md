# PAO-ACOS — Chief command routing và business Tool Gateway

Checkpoint 05/10/2026, target `F:\PAO-ACOS`. M2 vẫn chưa hoàn tất.

## Cách dùng

Trong PAO AI, gửi:

> Báo cáo doanh nghiệp từ 2026-10-01 đến 2026-10-05

Router v1 chấp nhận câu lệnh đầy đủ với hai ngày ISO. Có biến thể không dấu,
tiền tố “Hãy/Giúp tôi/Cho tôi” và `daily business brief from … to …`.
“Hôm nay”, thiếu ngày, ngày sai hoặc câu lệnh ghép hành động đều yêu cầu nhập
lại; không đoán ngày, không gửi email/Telegram. Câu trích dẫn/dịch, phủ định,
chào hỏi không được chuyển thành lệnh đọc dữ liệu.

## Đã triển khai

- Hai tool `business.tasks.read`, `business.kpi.read` vào registry/Gateway.
  Schema chỉ nhận hai ngày, không nhận workspace/user/URL hoặc câu SQL.
- Chief chọn skill trước history/memory/LLM bằng grammar có giới hạn. Câu lệnh
  này không gọi planner hoặc model stream; không dùng LLM để viết lại số liệu.
- Run giữ `skill_route`, router version `1.0.0`, skill snapshot/hash và
  `skill_result`. ToolCall/Audit giữ đề xuất, bắt đầu, kết quả và hoàn tất.
- Workspace/user do durable ToolCall và parent run cung cấp; worker kiểm lại
  quyền trước claim, trong read transaction và trước lưu kết quả. Không cho
  test/provider override biến business tool thành HTTP connector.
- Query nghiệp vụ chạy trong transaction PostgreSQL chỉ đọc với statement
  timeout 8 giây; Gateway vẫn ghi lifecycle/audit riêng. Vì vậy “chỉ đọc” ở đây
  là không sửa dữ liệu nghiệp vụ, không phải không ghi bất kỳ row nào.
- Dispatcher và inline executor cùng dùng single-claim. Runtime chờ kết quả
  call đã được dispatcher claim, không thực hiện provider call thứ hai.
- LLM planner thông thường không được tự đề xuất business-tool execution.
  Người dùng vẫn có thể đề xuất business tool rõ ràng qua Tool Gateway API
  cho run của mình, với các guard hiện có.
- Tools bị tắt: trả thông báo, không đọc dữ liệu. Skill Ads/creative nhận đúng
  tên nhưng báo chưa nối công cụ, không giả vờ đã phân tích.

## Bằng chứng

| Kiểm tra | Kết quả |
|---|---|
| Backend regression trên `pao_test` | 216/216 đạt |
| Runtime/SSE | 8/8 đạt |
| Production build/typecheck frontend | Đạt, 18 routes |
| Live Chief command → ARQ → hai business tools → result/audit | Đạt |
| Live Skills catalog/preview desktop/mobile | Đạt |
| Browser regression 12 màn hình với API mock | Đạt |

Live run demo: `6ade80a6-84b1-443b-8084-b6a891bed0b8`. Hội thoại mang tên
“Kiểm thử Chief Skill — dữ liệu demo”, memory tắt. Đây là dữ liệu nghiệm thu
trong DB local riêng; không dùng credential/tài khoản Ads thật.
Lần gọi smoke ngay sau restart gặp API chưa mở cổng; script đã bổ sung chờ
`/ready`, chạy lại đạt. Các lỗi mock model ở lượt regression đầu đã sửa;
kết quả 216/216 là lượt cuối với code đã cập nhật.

Các tests gồm 15 câu lệnh/không phải lệnh, replay run không nhân đôi calls,
không gọi model hoặc provider ngoài, nguồn report đúng scope, input thiếu,
skill chưa hỗ trợ, tools off, mất quyền và workspace override, LLM tự đề xuất
business tools bị chặn. Chưa có load/crash acceptance mới cho skill router.

## Giới hạn

- Đây là command router deterministic, chưa là semantic routing tổng quát.
- Không tự tạo Goal/Task/TaskAttempt từ chat. Snapshot route ở Run; cơ chế pin
  TaskAttempt từ checkpoint trước vẫn tồn tại nhưng chưa nối auto dispatch.
- Contract period-v1 và handlers read hiện tại phải giữ nghĩa ổn định. Run/tool
  replay đã hoàn tất không chạy lại. Không cam kết chạy lại job dở với bất kỳ
  manifest/handler tương lai nào; worker kiểm policy hiện hành và fail closed.
- Hoàn tất run/tool nghĩa là hoàn tất đọc/trả lời kỹ thuật. Skill result vẫn
  `insufficient_data` vì chưa có doanh thu doanh nghiệp xác minh. Không đồng
  nghĩa Goal/Task nghiệp vụ hoặc M2 hoàn tất.
- Kết quả giới hạn 50 report/account snapshots, không cộng tiền tệ, ghi nguồn
  và thời điểm cập nhật. Task đếm theo ngày tạo UTC và trạng thái hiện tại.
- AgentRun có metadata model cấu hình nhưng command này không gọi model;
  session memory-enabled khác có thể tạo memory extraction sau run như trước.
- Database vẫn `0023`, không migration mới. Môi trường local đã restart sau
  idle check (không run/tool-call hoạt động); source `F:\Apex\apex` giữ nguyên.

## Bước tiếp theo

Nối wrapper intelligence/creative cho `investigate-ads-drop` và
`creative-fatigue-review`, kiểm quyền/nguồn/thiếu dữ liệu, rồi nghiệm thu M2.
Không sang M3 dữ liệu thật hoặc mở hành động write ở checkpoint này.
Kiểm tra lại: backend driver riêng, runtime tests, production build,
`scripts/verify_chief_skill.cjs` và `scripts/verify_skills_ui.cjs` với credential
demo chỉ trong môi trường process. Không ghi mật khẩu vào source/tài liệu.
