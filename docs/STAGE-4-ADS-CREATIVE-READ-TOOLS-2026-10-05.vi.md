# PAO-ACOS — Snapshot Ads/creative read tools

Checkpoint 05/10/2026, target `F:\PAO-ACOS`. Đây là một bước của M2,
không nghiệm thu toàn bộ M2 hay dữ liệu kinh doanh thật.

## Đã triển khai

- `business.ads.intelligence.read`: snapshot intelligence daily mới nhất khớp
  chính xác account/kỳ, đọc số đếm và tối đa 50 anomaly với current/baseline/
  deviation. Không trả action proposal hoặc arbitrary evidence/prompt text.
- `business.creative.read`: snapshot creative mới nhất với cửa sổ current
  khớp chính xác hai ngày yêu cầu, đọc counts và tối đa 50 features với status,
  score/confidence/age. Không đưa strategy brief hoặc nội dung creative vào output.
- Cả hai tool được đăng ký trong durable Gateway; có schema/agent allowlist,
  scope từ parent run/call, permission recheck và audit. Handler nghiệp vụ vẫn
  chạy trong PostgreSQL read-only transaction có statement timeout.
- API `POST /v1/skills/{skill_id}/analysis-preview`, với skill ID là
  `investigate-ads-drop` hoặc `creative-fatigue-review`. Input gồm workspace
  phía ngoài và `start_date/end_date/platform/account_id` trong input.
- Trang `/skills` cho chọn một trong ba bản xem trước; Ads/creative yêu cầu
  account và platform. Không thay đổi registry manifest/version đã pin.

## Guardrails và giới hạn

- Hiện chỉ đọc Meta snapshot của người sở hữu kết nối trong workspace.
  Connector disconnected/expired, version cũ, sai user/account/kỳ bị loại.
  Google Ads trả trạng thái thiếu/chưa hỗ trợ, không truy cập Meta thay thế.
- Không sync, analyze, tạo report, sửa rules/targets/creative hay gửi dữ liệu.
  Preview không tạo ToolCall; đọc qua Gateway ghi lifecycle/audit riêng, không
  sửa dữ liệu nghiệp vụ. LLM planner vẫn không được tự đề xuất business tools.
- Thiếu summary/mẫu/feature hoặc vượt 50 records được đánh dấu missing_data.
  Summary counts sai giữ unknown, không đổi thành 0. Source references tối đa
  50. Nội dung ngoài allowlist từ snapshot không được xuất nguyên văn.
- Anomaly là row có thể bị cập nhật bởi analysis khác; nếu số row hiện còn
  không khớp snapshot count, báo coverage thiếu. Không coi đây là lịch sử bất biến.
- Nguồn quá 24 giờ ghi rõ historical/stale; đây là guard bảo thủ của wrapper,
  chưa phải freshness SLA production. Không xác nhận trạng thái live.
- Tool completed chỉ nghĩa là đọc snapshot đủ trường. Skill preview luôn
  `insufficient_data` vì chưa đối chiếu dữ liệu/baseline để kết luận nguyên nhân.
  Tín hiệu fatigue/anomaly không tự chứng minh nguyên nhân giảm hiệu quả.
- Chưa nối chat routing hai skill Ads/creative. Chưa phối hợp KPI/report và
  intelligence/creative thành workflow đầy đủ, chưa tạo task attempt tự động.
  Daily brief command từ checkpoint trước vẫn hoạt động như cũ.
- Intelligence thường là slot daily riêng, creative có current/baseline riêng.
  Không ghép kỳ khác nhau để giả đáp ứng một yêu cầu tuần/tháng.

## Bằng chứng nghiệm thu cuối

| Kiểm tra | Kết quả |
|---|---|
| Backend regression trên `pao_test` | 224/224 đạt |
| Runtime/SSE | 8/8 đạt |
| Production frontend build/typecheck | Đạt, 18 routes |
| Live API/UI cả ba preview, desktop/mobile | Đạt |
| Browser regression 12 màn hình, API mock | Đạt |
| API ready và trang Skills sau restart | HTTP 200 |

Tests mới kiểm auth/workspace, personal scope, account/kỳ/version, Google
unsupported, dữ liệu thiếu/stale, summary sai, nguồn anomaly có chỉ số,
loại arbitrary evidence, giới hạn payload/references, agent denied và replay
Gateway không gọi provider ngoài. Các tests không tạo/sync snapshot trên DB demo;
fixture chỉ nằm trên `pao_test`. Demo live thiếu connector/data là kết quả hợp lệ.
Hai lỗi locator ở lượt UI đầu do trùng nhãn card/dropdown đã sửa trong script;
lượt cuối có output PASS cả ba preview.

Database giữ revision `0023`, không migration mới. Restart sau idle check 0
run/tool-call đang hoạt động. Source `F:\Apex\apex` không sửa.

## Bước tiếp theo

Nối input account/platform/ngày rõ ràng vào Chief command router cho hai skill
mới, phối hợp các tool đúng contract và kiểm evidence/thiếu dữ liệu. Chỉ sau
nghiệm thu bộ câu hỏi M2 mới chuyển sang M3 dữ liệu thật. Không mở Ads write.

Kiểm tra lại bằng backend driver cho `pao_test`, runtime tests, production build
(dừng Next dev trước build), launcher và `verify_skills_ui.cjs` với credential
demo qua environment process. Không lưu mật khẩu trong source hoặc report.
