# M2 — Attribution preview trên màn hình Skills

Ngày 05/10/2026; chỉ đổi UI, script nghiệm thu và tài liệu tại F:\PAO-ACOS.
Không đổi backend/manifest/API contracts/database trong checkpoint này.

## Đã triển khai

- Menu xem trước có lựa chọn **Đối chiếu attribution đã lưu**. Đây là chế độ
  preview của investigate-ads-drop 1.1.0, không phải skill thứ tư.
- Người dùng nhập nền tảng, account và hai ngày rồi bấm Đọc bản xem trước.
  Không tự gọi preview khi thay trường, không đồng bộ hoặc phân tích mới.
- Bảng riêng: campaign, currency, platform-reported revenue, allocated paid
  order revenue/count và metric source. Null hiện “chưa biết”; 0 vẫn hiện 0.
  Không tính tổng hoặc chuyển đổi tiền tệ; cảnh báo doanh thu chưa xác minh.
- Bảng cuộn ngang trên điện thoại, kèm hướng dẫn. Source/missing reasons và
  raw trace vẫn xem được; không xuất HTML từ dữ liệu nguồn.
- Thay mode/account/platform/ngày/workspace làm vô hiệu kết quả/request cũ.
  Request generation chặn phản hồi muộn ghi đè preview mới; không hủy network
  request nhưng endpoint chỉ đọc và có timeout đã kiểm ở checkpoint trước.
- Lỗi API không giữ bảng kết quả cũ. Form vẫn có required/pattern/date input;
  validation có thẩm quyền và scope vẫn ở backend.

## Kiểm chứng cuối

- Production frontend build đạt, 18/18 pages generated; bản cuối không còn
  cảnh báo flex-end phát sinh ở CSS mới.
- TypeScript noEmit/incremental false đạt; runtime/SSE **8/8**.
- Live Skills: catalog, ba preview cũ và attribution thiếu dữ liệu local đạt.
- UI fixture qua browser: hai currency USD/VND; null không thành zero; zero
  hiển thị nguyên; không auto-read; mobile 390x844 chờ sidebar resize ổn định,
  content không tràn và bảng cuộn tới cột nguồn; phản hồi muộn sau đổi mode bị
  bỏ qua; API 403 không giữ result; không pageerror.
- Browser regression mock **12 màn hình** đạt. API /ready, Web /skills HTTP 200.
- Đã rà ảnh desktop/mobile trong .runtime (không commit screenshot).
- Backend không đổi nên **không chạy lại regression backend**. Số 265/265 là
  kết quả checkpoint attribution API trước, không phải lần chạy mới ở lượt UI.
- Không migration mới; source F:\Apex\apex không sửa. Chỉ dừng/start riêng Web
  cho build; API/worker/Ollama/containers được giữ nguyên.

Các lượt trước có lỗi layout mobile và connection refused do Web chưa ready.
Đã scope CSS xuống dòng catalog/table, chờ animation responsive và thêm readiness
wait 45s vào script. Bằng chứng đạt là lượt cuối sau sửa, không dùng lượt lỗi.
Build kiểm production artifacts; browser chạy Web dev được launcher bật lại,
không phải nghiệm thu production server công khai hoặc toàn layout off-canvas shell.

## Cách dùng

1. Mở http://127.0.0.1:3200/skills, đăng nhập workspace của bạn.
2. Chọn Đối chiếu attribution đã lưu; Meta; account dạng act_123; kỳ báo cáo.
3. Bấm Đọc bản xem trước. Nếu chưa có kết nối/snapshot, đọc lý do thiếu dữ liệu.
4. Nếu có số, kiểm nguồn và tiền tệ; không coi doanh thu phân bổ là tổng doanh
   thu doanh nghiệp. Không nhập credential hoặc PII vào các trường này.

## Còn thiếu

M2 vẫn có điều kiện. Chưa tự nối tool thứ ba vào command plan hoặc tăng tool
budget; checkpoint UI này chưa nghiệm thu ARQ/Redis wall-clock. Checkpoint
[real-clock tiếp theo](M2-ARQ-REDIS-RECOVERY-2026-10-05.vi.md) đã đạt với cấu
hình test; không phải nghiệm thu recovery production. Code archive/replay,
token budget cho skill LLM hoặc đối soát doanh thu ngoài fixture. Bước kế tiếp:
rà deadline recovery theo snapshot và gate M2 trước khi mở M3 dữ liệu thật.
