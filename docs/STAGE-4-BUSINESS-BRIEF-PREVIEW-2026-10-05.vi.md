# PAO-ACOS — Daily business brief: bản xem trước chỉ đọc

Ngày kiểm tra: 05/10/2026. Target: `F:\PAO-ACOS`.
Đây là checkpoint tiếp theo của M2, sau Skill Registry foundation.
M2 chưa hoàn tất; không phải báo cáo doanh nghiệp production.

## Đã triển khai

- `business.tasks.read`: đếm task **tạo trong kỳ UTC**, phân nhóm theo trạng thái
  hiện tại; không giả định đây là lịch sử trạng thái trong kỳ. Không trả title,
  mô tả hay nội dung task.
- `business.kpi.read`: đọc tối đa 50 báo cáo Meta đã lưu, khớp **chính xác** kỳ
  yêu cầu, đúng workspace, người sở hữu và phiên bản kết nối còn hiệu lực.
  Lấy snapshot mới nhất cho mỗi tài khoản; không cộng snapshot trùng hoặc trộn
  tiền tệ. Không gọi Meta API hay tự tạo/sync báo cáo.
- `POST /v1/skills/daily-business-brief/preview` yêu cầu đăng nhập, membership
  và input đúng contract. Không nhận agent/tool/workspace override trong input.
- Transaction PostgreSQL riêng được `SET TRANSACTION READ ONLY`; statement
  timeout 8 giây, thời gian bao toàn bộ preview 10 giây. Không gọi LLM.
- Trả skill snapshot, input, nguồn query/report do server xác định, thời điểm
  đọc, chi tiết tools và kết quả có cấu trúc. Không tạo TaskAttempt hoặc ghi
  audit/execution history cho preview; đây là thao tác đọc, không chạy workflow.
- Trang `/skills` có chọn kỳ và nút “Đọc bản xem trước”, kèm dữ liệu, nguồn và
  lý do thiếu. Preflight cũ vẫn trả `execution_available: false` cho dispatch
  tự động; endpoint preview chỉ chạy khi được gọi rõ ràng.

## Tính trung thực của dữ liệu

- Không có connector hoặc report khớp kỳ: báo thiếu, không tự kết nối/sync.
- Metric NULL giữ nguyên NULL, không thay bằng 0. Coverage thiếu ghi lý do.
- Doanh thu/purchases từ Ads được ghi rõ `platform_reported_*`, không gọi là
  doanh thu doanh nghiệp thực thu. Từng report giữ currency/timezone/attribution.
- Task bằng 0 là kết quả query rỗng đã xác định phạm vi, không phải missing Ads.
- Brief luôn `insufficient_data` trong checkpoint này vì chưa nối nguồn doanh
  thu doanh nghiệp xác minh. Tool KPI có thể completed với report đủ trường;
  điều đó không làm brief doanh nghiệp trở thành hoàn chỉnh.
- Hiển thị thời điểm dữ liệu nguồn/report; chưa có SLA freshness. Nguồn task
  là query có phạm vi, không phải snapshot lịch sử bất biến. Nguồn report là
  ID từ bảng hiện có, chưa phải chứng minh dữ liệu bên ngoài chính xác.
- Khi vượt giới hạn report/lý do/nguồn, kết quả vẫn báo thiếu và giữ chi tiết
  tool. Chưa cam kết bao quát tất cả tài khoản hay nguồn doanh nghiệp.

## Bằng chứng nghiệm thu

| Kiểm tra | Kết quả |
|---|---|
| Backend regression trên database riêng `pao_test` | 195/195 đạt |
| Runtime/SSE | 8/8 đạt |
| Production frontend build, typecheck | Đạt, 18 routes |
| Live Skills acceptance, preview API và UI desktop/mobile | Đạt |
| Browser regression 12 màn hình, API mock | Đạt |
| API `/ready`, trang `/skills` sau restart | HTTP 200 |

Tests mới bao gồm auth/workspace, viewer read, input override sai, thiếu
connector, scope kết nối theo user, giới hạn ngày task, không lộ nội dung task,
NULL/coverage, version kết nối cũ, snapshot mới nhất, kỳ không khớp,
repeated preview không tạo row, PostgreSQL từ chối write và timeout trả 504.
Regression cũ dùng API mock, không phải nghiệm thu dữ liệu 12 module thật.

Database demo vẫn revision `0023`, không cần migration mới. Kiểm tra trước
restart cho thấy 0 run/tool-call queued/running. Không sửa `F:\Apex\apex`.
Không gửi Telegram, email, bật/sửa Ads hoặc gọi API quảng cáo ngoài.

## Kiểm tra lại và bước sau

Chạy `.venv\Scripts\python.exe scripts/test_backend.py` trên cấu hình PAO-ACOS;
script chỉ sử dụng `pao_test`. Chạy `npm run test:runtime`, `npm run build`
(dừng web dev trước build), rồi launcher local.
`scripts/verify_skills_ui.cjs` nhận credential demo qua môi trường process;
không lưu mật khẩu vào source/docs.

Bước tiếp theo: đưa wrapper qua Tool Gateway và nối Chief routing với bộ câu
hỏi chuẩn, giữ nguyên RBAC/allowlist. Chỉ cho phép gọi tool đã nối; không tự
cấp quyền hoặc lấy doanh thu Ads làm doanh thu xác minh. Nghiệm thu định nghĩa
metric/nguồn và dữ liệu thiếu trước khi mở rộng các skill Ads khác.
