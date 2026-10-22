# M2 — Nghiệm thu local có điều kiện

Ghi chú hiện hành: đây là checkpoint lịch sử. M2 local đã đạt các gate roadmap;
xem [nghiệm thu cuối 298/298](M2-FINAL-ACCEPTANCE-2026-10-05.vi.md).
Artifact result replay/version và pinned recovery đã bổ sung; không nghiệm thu
business data ngoài PAO, production HA hoặc rerun executable cũ.

Ngày kiểm tra 05/10/2026, target `F:\PAO-ACOS`.
Kết luận: các luồng **command/read-only/snapshot** đã đạt các ca local bên
dưới. **Không đánh dấu toàn bộ M2 hoàn tất, chưa chuyển sang M3 dữ liệu thật.**

## Các điều kiện đã kiểm chứng

| Điều kiện | Bằng chứng/phạm vi |
|---|---|
| Chọn skill | Corpus command chuẩn trong `test_skill_router.py`; không khẳng định hiểu mọi câu tự do |
| Input/tool hợp lệ | Schema, tool/agent allowlist, từ chối override workspace/URL/SQL và command ghép hành động |
| Scope dữ liệu | Đúng user/workspace/connection version/account/kỳ; account khác trong cùng workspace không lộ |
| Thiếu dữ liệu | Connector, Google unsupported, snapshot/coverage/stale/NULL trả thiếu, không biến unknown thành 0 |
| Nguồn kết luận | Root snapshot và nguồn chỉ số đang hiển thị được ưu tiên khi cap 50 references |
| Completion và correctness | Run/tool completed là kỹ thuật; skill result thiếu dữ liệu không bị coi là kết luận kinh doanh hoàn chỉnh |
| Hủy/mất quyền | Sau tool đầu: không dispatch tool thứ hai, không công bố skill result/câu trả lời thành công |
| Lỗi tool thứ hai | Run failed, không tổng hợp success, không lộ exception chi tiết |
| Dispatcher | Simulate executor khác thực hiện call; runtime chờ cùng durable call, không thêm calls |
| Replay | Terminal run không tạo calls mới; TaskAttempt giữ version/hash cũ theo test checkpoint trước |
| Chỉ đọc | PostgreSQL chặn write ở read transaction; lifecycle/audit ghi riêng |
| Output bounded | Read limits, summary 4000 ký tự, 50 sources/20 missing reasons; 10 signals mỗi tool trong câu trả lời |

## Sửa trong lượt nghiệm thu

1. Anomaly NULL hiển thị “chưa biết”, không `None%` hoặc giả số 0.
2. Khi quá nhiều nguồn, ưu tiên root snapshot/report của **tất cả** tools và
   source của số liệu hiển thị trước nguồn child còn lại. Trước đó sources của
   tool thứ hai có thể bị cắt khi tool thứ nhất dùng hết 50 slots.

Tests mới nằm trong `apps/api/tests/test_m2_acceptance.py`. Fault/cancel/race
được điều khiển bằng fixture/mocking trên `pao_test`; không phải thử kill
process/hỏng mạng thật và không phải production load test.

## Kết quả lượt cuối

- Backend: **239/239**, 117.10 giây, database `pao_test` riêng.
- Runtime/SSE: **8/8**.
- Live chat API → ARQ: cả ba skill hoàn tất đọc với result `insufficient_data`.
- Live preview API/UI: ba lựa chọn, desktop/mobile đạt.
- Browser regression 12 màn hình với API mock: đạt.
- API `/ready` và Web `/skills`: HTTP 200.
- Frontend không thay đổi trong lượt này; production build đã đạt ở checkpoint
  liền trước, **không chạy lại build trong lượt nghiệm thu này**.
- Database vẫn `0023`, không migration mới. Source `F:\Apex\apex` không sửa.

Live demo runs (memory tắt, không Ads thật):

- Daily `1219ec36-6de6-4504-bd21-53e3e91b375e`.
- Ads `db83e0fe-3475-48d2-b7af-834e1167a8f3`.
- Creative `002c9a84-70ed-4017-9d2a-569f52923248`.

Restart chỉ API/worker sau idle check 0 jobs. Không bật Ads API, gửi email,
Telegram hoặc thay dữ liệu nghiệp vụ; smoke ghi hội thoại/run/audit demo.

## Các phần còn thiếu trước khi kết luận toàn bộ M2

1. **Resource budget:** checkpoint tiếp theo đã cưỡng chế timeout snapshot,
   số tools và output cho command workflow; xem
   [báo cáo resource guard](M2-RESOURCE-GUARD-2026-10-05.vi.md).
   Token budget cho skill LLM tương lai vẫn chưa được cưỡng chế. Kết quả
   239/239 ở trên là checkpoint trước; checkpoint resource đạt 243/243.
2. **Khôi phục process/version:** đã kiểm OS kill/process restart riêng giữa
   hai tools và trong read, dùng clock lease mô phỏng trên pao_test; xem
   [checkpoint recovery](M2-PROCESS-RECOVERY-2026-10-05.vi.md).
   Chưa nghiệm thu toàn stack ARQ/Redis hoặc latency thật. Handler/evaluator
   executable không có version archive để replay job dở qua nâng cấp.
   Snapshot/hash không tự bảo đảm replay code. Backend checkpoint mới 245/245.
   Checkpoint tiếp theo đã có [guard executable](M2-VERSION-GUARD-2026-10-05.vi.md),
   từ chối binding khác/thiếu, không archive/resume code cũ; regression 254/254.
   Checkpoint [ARQ/Redis real-clock](M2-ARQ-REDIS-RECOVERY-2026-10-05.vi.md) đã
   đạt với cấu hình test ngắn, 267/267; không nghiệm thu Redis server mất mạng,
   latency production hoặc resume. Recovery deadline còn theo timeout chung.
3. **Attribution/business services:** đã có
   [wrapper Gateway và explicit API preview](M2-ATTRIBUTION-READ-2026-10-05.vi.md).
   [UI explicit preview](M2-ATTRIBUTION-UI-2026-10-05.vi.md) đã đạt checkpoint;
   chưa tự ghép vào command plan. Platform revenue và deterministic
   allocated order revenue không phải business revenue xác minh.
4. **Evaluation nghiệp vụ:** evaluator hiện kiểm cấu trúc/hash/sources shape.
   Fixture kiểm các số lấy từ record, không xác minh metric bên ngoài hoặc
   quan hệ nhân quả. Brief/analysis đầy đủ cần dữ liệu và nghiệm thu M3.

Không mở quyền write hoặc deploy công khai để bỏ qua các giới hạn trên.

## Bước triển khai kế tiếp

Resource guard command và OS-process recovery harness đã đạt checkpoint riêng.
Guard tương thích version và wrapper attribution API đã đạt checkpoint.
UI explicit attribution preview và recovery ARQ/Redis test đã đạt. Bước tiếp
theo là rà deadline recovery theo snapshot cùng gate M2 trước M3.
Chỉ dùng dữ liệu giả hoặc DB test ở các bước này; credential thật cần được
người dùng cấp cho account/scope rõ ràng.
