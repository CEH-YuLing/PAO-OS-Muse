# PAO-ACOS — Ba Chief command workflows chỉ đọc

Checkpoint ngày 05/10/2026. Target `F:\PAO-ACOS`.
Router phiên bản `1.1.0`; manifest ba skill vẫn `1.0.0`, contract giữ tương thích.

## Cách dùng trong PAO AI

```text
Báo cáo doanh nghiệp từ 2026-10-01 đến 2026-10-05
Điều tra hiệu quả quảng cáo giảm meta act_123 từ 2026-10-01 đến 2026-10-05
Đánh giá creative fatigue meta act_123 từ 2026-10-01 đến 2026-10-05
```

Thay `act_123` bằng account của bạn. Không tự kết nối/sync/analyze khi chưa có
dữ liệu. Thiếu account/ngày, sai định dạng hoặc ghép lệnh write/gửi báo cáo
được yêu cầu nhập lại. Google Ads dạng `google_ads 1234567890` nhận route
nhưng trả missing platform; không gọi Meta thay thế.

## Luồng công cụ

| Skill | Hai tool qua durable Gateway |
|---|---|
| daily-business-brief | tasks.read → kpi.read (workspace) |
| investigate-ads-drop | kpi.read (account/platform) → ads.intelligence.read |
| creative-fatigue-review | creative.read → ads.intelligence.read |

Tên thực tế có tiền tố `business.`. Tool plan cố định được kiểm qua skill
allowlist trước khi tạo calls; scope workspace/user lấy từ run/call, không
cho model đưa SQL/URL hay chuyển workspace. Registry KPI nhận period-only
hoặc cặp platform/account hợp lệ; chỉ nhận một trường trong cặp bị từ chối.
KPI có account sẽ lọc đúng account, không đọc báo cáo account khác trong cùng
workspace. Period-only của daily brief giữ hành vi cũ.

## Kết quả và bảo vệ

- Cả ba command đi trước history/memory/LLM planner, không gọi model stream
  để viết lại số liệu. Không phải semantic routing tự do.
- Run giữ route, router version, skill snapshot/hash và skill_result;
  ToolCall/Audit giữ input, lifecycle và nguồn kết quả. Các read handler vẫn
  trong transaction PostgreSQL read-only; lifecycle/audit là ghi kỹ thuật riêng.
- Câu trả lời Ads/creative ghi account/kỳ, snapshot/time, source references,
  platform revenue, anomaly/feature đã lưu. Không kết luận tín hiệu là nguyên
  nhân thật, không gọi platform revenue là doanh thu doanh nghiệp xác minh.
- Mỗi tool chỉ hiển thị tối đa 10 anomaly/features trong câu trả lời; chi tiết
  tối đa 50 ở trace. Result tối đa 50 nguồn và 20 lý do thiếu, summary 4000 ký tự.
- Skill result luôn `insufficient_data` ở checkpoint này do chưa có causal
  validation. Run/tool completed là hoàn tất đọc/trả lời kỹ thuật, không có
  nghĩa đã chứng minh nguyên nhân hay hoàn thành mục tiêu kinh doanh.
- Không tạo Goal/Task/TaskAttempt tự động. Không gửi email/Telegram, không
  sửa Ads/creative, không mở cloud model hoặc connector mới.
- Single-claim/recheck/cancellation của Gateway giữ nguyên; terminal run
  replay không tạo tool call thêm. Không cam kết replay job dở qua mọi thay
  đổi manifest/handler tương lai. Cần nghiệm thu tổng thể M2 trước M3.

## Bằng chứng cuối

| Kiểm tra | Kết quả |
|---|---|
| Backend regression, chỉ database `pao_test` | 233/233 đạt |
| Runtime/SSE | 8/8 đạt |
| Production frontend build/typecheck | Đạt, 18 routes |
| Live chat API → ARQ → cả ba skill/tool workflows | Đạt |
| Live Skills preview desktop/mobile, cả ba lựa chọn | Đạt |
| Browser regression 12 màn hình với API mock | Đạt |
| API ready và trang Skills | HTTP 200 |

Tests mới kiểm hai workflow Ads/creative có nguồn đúng, input account/platform
giữ xuyên suốt, account khác trong cùng workspace không lộ, replay không tạo
call trùng, không gọi LLM, dữ liệu thiếu và Google unsupported không bịa,
account/platform phải đi thành cặp. Bộ cũ gồm auth/isolation/policy/approval,
readonly transaction, snapshot/hash và runtime vẫn đạt.

Live demo runs (hội thoại memory-off):

- Daily: `42b02de5-ff1d-48c9-9cea-6eac30f70327`.
- Ads: `bd2646b6-2ca8-4b5c-bb32-68d4955ff220`.
- Creative: `2daa620d-bdef-4def-8410-5c56a3b09546`.

Live demo không có Ads thật; nghiệm thu thiếu dữ liệu là hợp lệ. Fixtures có
report/intelligence/anomaly nằm ở `pao_test`, không đưa vào database demo.
Không migration mới (vẫn `0023`). Restart sau idle check 0 run/tool-call hoạt
động; source `F:\Apex\apex` không sửa.

## Bước tiếp theo

Nghiệm thu tổng thể M2: bộ câu hỏi/số liệu chuẩn, giới hạn resource, race/fault,
cancel và replay/version của luồng skill; phân biệt correctness với completion.
Xác định rõ phạm vi nào đạt local và phạm vi nào còn thiếu. Sau đó mới lên M3
đối chiếu dữ liệu thật, với credential/account được người dùng cấp rõ ràng.

Kiểm tra lại: backend driver riêng, runtime tests, build (dừng Next dev),
launcher, `verify_chief_skill.cjs` và `verify_skills_ui.cjs`. Credentials demo
chỉ truyền environment process, không lưu vào code hoặc report.
