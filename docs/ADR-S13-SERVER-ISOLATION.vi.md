# ADR-S13 — corpus cách ly server và cleanup SSE

Ngày11/10/2026, target `F:\PAO-ACOS`. Phạm vi S1.3; không triển khai S2.
Thứ tự/checkpoint do [master roadmap](PAO-MASTER-GAP-AND-ROADMAP.vi.md) sở hữu.

## Thiết kế và ranh giới

- Reuse Workspace/Member, private Brain ACL, composite parent FKs và quyền của
  từng domain. Không thêm platform-admin bypass hoặc thay private legacy memory.
- Shared owner thuộc A/B được đọc nguồn A khi chọn A rõ ràng và còn quyền. Không
  coi việc này là IDOR. Danh sách/search/retrieval theo B không được chứa nguồn A;
  ID của file/source/chunk A dưới parent B phải bị từ chối dù actor có cả hai quyền.
- Worker/outbox dùng principal và tenant đã pin, không lấy doanh nghiệp đang
  chọn trên UI. Revoke membership A không mất quyền B, cũng không dùng role B
  để chạy job A. Permission check trước model/parser/transport và trước publish
  kết quả chậm được kiểm bằng DB/spy; không gọi provider thật để chứng minh deny.
- RLS không được bật ở đây. Constraints chống sai parent, authorization trong
  application chống đọc trái quyền. Đây là corpus các đường rủi ro hiện có,
  không chứng nhận mọi endpoint hoặc mọi đường SQL độc lập đều an toàn.
- Connection ownership/version/brand-account grant, credential rotation,
  tenant quota/fairness là S2–S4; corpus S1.3 không thay gate các bước đó.

## Ma trận kiểm chứng

Fixture chung: A/B, một owner thuộc cả hai, một user chỉ thuộc A, một owner chỉ
thuộc B; private Brain của shared owner trong mỗi SME. Cùng từ khóa, tên và
marker khác nhau. Chỉ `pao_test`, Redis15, queue `pao-test:s13:<uuid>`.

| Đường dữ liệu/thực thi | Được phép | Phải từ chối/cách ly |
|---|---|---|
| Context/session/chat search/task lists | Shared actor chọn A hoặc B rõ | A-only→B, B-only→A; B không liệt kê A |
| Session/run/history/export/usage/SSE | Actor sở hữu session và có membership | Nonmember không đọc ID/export/events/usage; private session không mở cho coworker |
| Brain/file/download/preview/notes/source/export/legacy memory | Brain owner hoặc grant đúng | Workspace owner không tự đọc Brain đồng nghiệp, foreign tenant trả404 |
| File/source/version/ingestion IDs | Parent Brain khớp | File/source/job A dưới Brain B trả404 trước parse |
| Retrieval/citation | Chunks của đúng Brain, không embeddings cloud | Cùng keyword không trộn A/B; foreign chunk404; revoke A vẫn dùng B được |
| Brand/session/run parent | Composite tenant khớp | API foreign brand404; FK Brain-brand và Run-session reject sai SME |
| Queued chat/memory | Actor còn quyền tenant đã pin | Remove/downgrade A trước execute: resolver/stream/extract không được gọi |
| Queued ingestion và parse đang chạy | Actor/source đúng quyền | Remove/viewer trước parse: parser0; revoke trong parse: không publish vào A hoặc B |
| Internal business outbox sau claim | Còn membership/nonviewer | Lease đã claim không vượt revoke; receipt0; sự kiện B vẫn được consume |
| Result delivery pending | Sender/recipient/source còn quyền | Sender mất quyền A không dùng quyền B; delivery failed, không có delivered_at |
| Channel pending send | Bound actor/destination/profile còn quyền | Revoke A trước send: transport0/cancelled; không chuyển reply vào B |
| Redis/ARQ thực | Hai job A/B enqueue trước permission change | Sau revoke A, worker thật chỉ parse B; không dùng queue production |
| SSE disconnect/timeout/revoke | Stream nhận event ban đầu hợp lệ | Abort không cancel run; revoke chặn event ở poll tiếp theo; pool không giữ checkout/lỗi cleanup |

Suite nền hiện có còn kiểm Brain grants, private legacy facts, knowledge/context,
compaction, role từng workspace, outbox retries và Goal/Studio quyền/recovery.
Ma trận mới là cửa kiểm thống nhất, không thay hoặc giảm assertion suite nền.

## Lỗi SSE và quyết định sửa

Tái hiện bằng PostgreSQL thật: AnyIO cancel scope ngắt lúc `pg_sleep(0.15)` sau
owned-run check làm SQLAlchemy log `Exception terminating connection`. Test ban
đầu1failed/1passed, không coi browser acceptance trước đó là đã sửa lỗi này.

Probe timeout bổ sung đã tìm lỗi thứ hai: nested AnyIO deadline hủy lặp lại
SQLAlchemy ngay lúc invalidate driver. Pool checkedout0 nhưng PostgreSQL còn
transaction của SQL ngủ10s, làm fixture TRUNCATE kế tiếp chờ relation lock.
Chỉ connection pao_test có PID/start-time/state/query đã xác minh được đóng để
cho regression chạy tiếp; không đóng session tùy ý hoặc động database chính.

`core_api.events` shield riêng DB poll và session rollback/close khỏi level
cancellation do disconnect. Timeout5s dùng `asyncio.timeout` (edge cancellation),
nằm trong session và kết thúc trước cleanup; timeout/auth-deny kết thúc stream.
Không đặt một AnyIO level-cancel deadline bên trong shield: driver có thể cần
await để invalidate ngay trong call bị timeout, trước khi session __aexit__ chạy.
Không shield network send, sleep hoặc cả đời stream; không sửa run status/
cancel_requested khi browser đóng.

Probe6 lần cancel trong DB,8 lần abort HTTP thật, revoke khi stream mở, query
`SELECT 1` sau đó và pool checkedout0. Thêm SQL ngủ10s để kiểm poll kết thúc
ở timeout5s, cleanup không lỗi và server không còn transaction của probe.
Test harness pin SQL PID/start-time/query và tự cleanup đúng probe kể cả assertion
fail, để một phép thử lỗi không khóa các fixture sau. Timeout5s là deadline cho poll, không SLA
toàn bộ transport/driver cleanup khi DB/network ngừng đáp ứng.

Quyền được kiểm lại theo poll (chu kỳ chờ0.2s), không instant global revocation.
Payload đã gửi/buffered không thể thu hồi. Snapshot đã authorize có thể có cửa
sổ race với revoke đồng thời; không hứa serialize mọi revoke với network send.

## Rollout

Không đổi schema0048 hoặc OpenAPI309. Bản sửa backend đổi exact execution binding;
checkpoint trước reload, idle gate và verify PID/executable/start time cho API/ARQ
thuộc ACOS. Không repin job/archive cũ, không chạm Web/Docker nếu khỏe, không
đổi `.env`/secret/gates và không mở connector thật. Nghiệm thu và checkpoint cuối
ghi tại [S13 acceptance](S13-LOCAL-ACCEPTANCE-2026-10-11.vi.md).
