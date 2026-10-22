# S5 — Tích hợp kế hoạch và điều phối nghiệp vụ

Trạng thái cuối: **toàn S5.1–S5.6 local_accepted,0070/live382**.
2224/2224 backend đạt trên source cố định c22f08ca…f94269, không lỗi/bỏ qua;
114Node/build22/browser/restore/migration/local-quality đạt. Primary149physical/
148business/3archives; API/ready/Web200, worker khỏe, replay3/3 và old row hashes
nguyên vẹn. Chỉ bật S5 và ghim launcher0070, không đổi các secret/cấu hình khác.
Kết quả cuối do S5-COMPLETION-REGISTER.vi.md quản lý. S6/production vẫn chưa đạt.

## Những phần đã được nối

| Phần | Cách tích hợp và giới hạn |
|---|---|
| S5.1 — Hồ sơ | Theo SME/nhãn hàng, phiên bản bất biến, dữ liệu thiếu không thành 0 |
| S5.2 — Kế hoạch | Kế hoạch tháng/DAG/hạn/tiêu chí, owner duyệt đúng nguồn; tạo Project/Goal/Task nháp nguyên tử |
| S5.3 — Công việc AI | Kế thừa phân công theo SME/brand/agent/step/job, reviewed Studio Skill; native Run/TaskAttempt/Gateway và usage chung |
| S5.4 — Tiền mô phỏng | Planned cap/reserved/spent/released bằng minor units, khóa chống cấp vượt; account/campaign/currency và tuổi quan sát |
| S5.5 — Duyệt và dừng | Kế hoạch/nội dung/hành động tách riêng; owner, hash/expiry, kiểm tra worker/publication; unknown giữ tiền đến đối soát |
| S5.6 — Báo cáo | Snapshot theo nguồn/window/metric; lịch giờ/ngày do scheduler P6 sở hữu, không gửi ra ngoài |

Không thêm model runner, Redis queue hay scheduler thứ hai. Có thể cấu hình bốn
chuyên môn; Sáng tạo hiện trả brief văn bản, không tự tạo hình/video. Không
hardcode nhà cung cấp theo chuyên môn, không tự fallback cloud hay cấp quyền tool.

## Lỗi phát hiện và đã xử lý trong nghiệm thu

- Vòng import HTTP API ↔ service chỉ xuất hiện khi worker khởi động mới: tách
  quyền/truy cập nguồn sang access.py; có kiểm thử fresh-process riêng.
- Fixture legacy giả lập Run thiếu ID khi thêm rào business-job: bổ sung ID của
  Run thật vào fixture, không bỏ kiểm tra quyền trong code để làm test xanh.
- Restore allowlist chưa nhận migration S5: thêm revision0066–0070 sau kiểm chứng
  clone roundtrip/rollback và restore dữ liệu có bản ghi.
- Nguy cơ kết quả Brain riêng bị sao chép sang child không có cùng phạm vi:
  kiểm tra quyền hiện hành và bắt buộc cùng Brain/local trước admission/worker.
- Stop rồi resume không được làm sống lại job đã xếp hàng trước stop; có control
  epoch. Source backend thay đổi cũng chặn job đã ghim, không tự repin.

## Bằng chứng đã đạt trên backend cuối c22f08ca…f94269

- 126 ca tập trung về worker/model-grant/lịch/restore/khôi phục tiến trình đạt.
- 29 ca business_operations cuối đạt; không cộng các lượt trùng thành tổng mới.
- 114 Node tests đạt; build production riêng22/22 trang đạt, còn Hooks warnings
  kế thừa. Contract đã xuất lại382operations.
- Browser/API/database riêng đạt: hồ sơ→kế hoạch→native job→duyệt nội dung→giữ
  tiền mô phỏng→hành động unknown→đối soát→báo cáo; mobile320/390, đổi SME/role.
- Restore populated khớp rows/schema và trigger chặn sửa/xóa review/routing/
  jobs/events/budgets/actions/entries.
- Clone0065→0070→0065→0070 giữ dữ liệu cũ, schema rollback; từ chối downgrade
  populated. Primary không đổi.
- Ollama local thật hai bước với một model đã cài: đúng tên/giá, nêu thiếu ưu
  đãi, không tự nhận đã đăng, usage được báo. Hai model khác nhau được kiểm
  chứng bằng fixture, không gọi đó là hai model live. Lượt sai giá trước đó
  được giữ và bị chặn, không xóa dấu vết thất bại.
- Checkpoint p0-20261016T131817-057ca661:1191source/primary0065/136tables/
  3archives, đã restore exact riêng. Secret/runtime không nằm trong source ZIP.

Toàn bộ hồi quy cuối đã đạt2224/2224 trên source cố định. Lượt phát triển đầu2217ca
có14failures được lưu riêng; không xóa hoặc gọi đó là pass. Primary chỉ nâng
sau hồi quy và backup/idle/release checks. Không có quảng cáo, đăng bài, cloud
model hoặc gửi Telegram thật trong các kiểm chứng trên.

## Không thuộc nghiệm thu local S5

OAuth thật, provider billing/balance/KPI thật, tạo campaign/posting, ảnh/video,
khách hàng pilot, Linux/HTTPS/reboot/production thuộc adapter/gate S6 riêng.
Không coi nguồn cấu hình hay tiền mô phỏng là đã kết nối/chi tiền thật.
Giới hạn local hiện tại: một admission/task, context native Run tối đa2000ký tự,
không tự retry/fallback; budget observation bất biến, hết tuổi phải chặn.
