# M2 — Recovery theo budget đã pin, 05/10/2026

## Thay đổi

Dispatcher dùng resource_guard.timeout_seconds đã lưu khi chạy skill, cộng
60 giây grace, thay cho timeout chung của worker vừa khởi động. Chỉ chấp nhận
snapshot có hash hợp lệ, timeout manifest là integer 1–600 và budget effective
là integer 1–timeout manifest. Không đọc lại registry để thay budget job cũ.

Kiểm hash được tách khỏi kiểm executable binding: cleanup job cũ không cần
chạy code cũ. Execute/evaluator vẫn yêu cầu exact binding, không tự resume.
Snapshot hỏng, guard thiếu/sai và run thường giữ lease theo timeout chung.
Hash bảo vệ tính toàn vẹn, không phải chữ ký chống người có quyền sửa database.
Job quá lease có cancel_requested kết thúc cancelled; còn lại failed/worker_lost.
Tool đang chạy vẫn dùng lease 90 giây và unknown khi mất worker; không retry.

Đọc candidate theo keyset, 100 rows/batch, skip locked; không cast JSON vào
SQL. Toàn scan trong một transaction, chưa có benchmark tải nhiều worker.
Budget là tương đối từ Run.started_at, không phải deadline tuyệt đối được ký.
Clock lệch giữa máy chưa được kiểm; grace và cron không phải SLA production.

## Kiểm thử

Các ca mới: thay registry/config/executable, guard không hợp lệ, snapshot hỏng,
plan legacy, trước/sau lease và hủy job. Database riêng pao_test, Redis DB15.
Hai ca kill-process ARQ thật vẫn bật opt-in. Worker đầu pin effective 10 giây;
worker recovery đổi global lên 120 giây. Phải kết thúc theo pin cũ, không đợi
180 giây timeout chung + grace. Không clock mock trong hai ca ARQ này.

Kết quả: **284/284 backend**, 346.46 giây (5 phút 46), không skip hai ca
wall-clock. Giữa hai tools: **75.89 giây**; trong read: **96.92 giây**.
Giá trị thứ hai còn phụ thuộc lease 90 giây của tool, không chỉ lease run.
Runtime/SSE **8/8**. Ba Chief skill command demo và browser Skills/attribution
(unknown/zero/currency, mobile, stale response, 403) đạt sau nạp backend mới.
API /ready và Web /skills HTTP 200; database **0023 (head)**. Trước/sau nạp
API/worker đều idle 0 runs/0 tool calls. Web/Ollama giữ process đang chạy;
containers Postgres/Redis được launcher xác nhận healthy, không restart.
Không chạy lại production frontend build vì không đổi frontend ở checkpoint này.

## Giới hạn nghiệm thu

Đây là fail-closed cleanup, không resume hoặc replay executable. M2 còn
artifact archive/replay, token budget cho skill gọi LLM và kiểm chứng kết quả
nghiệp vụ. Không bật Ads/integration thật, không deploy công khai, không sửa
source F:\Apex\apex. Không đổi frontend ở checkpoint này.
