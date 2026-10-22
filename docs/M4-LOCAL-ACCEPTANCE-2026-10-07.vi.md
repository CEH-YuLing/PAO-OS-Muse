# M4 — Business events và Unified Approval Center LOCAL

Ngày07/10/2026. Checkout: `F:\PAO-ACOS`, protected source không sửa.

## Trạng thái

**M4.1–M4.5 đã đạt LOCAL theo phạm vi hiện hành.** Full regression, browser/
ARQ/restore, clone migration và rollout/live replay đã đạt. Database local0037;
API/Web200, worker healthy; producer/delivery/unified approvals vẫn tắt trên
vận hành. M3 dữ liệu thật và production reboot drill vẫn chưa đạt; **không coi
đây là M4 business/production acceptance**, không mở business writes/P6.

## Những gì đã triển khai

| Lát cắt | Phạm vi |
| --- | --- |
| M4.1 | Task completed ledger/outbox cùng transaction, immutable, idempotent |
| M4.2 | Lease/fencing60s, ARQ hiện có, retry tối đa5/backoff, dead-letter, receipt dedup cùng ack |
| M4.3 | Inbox Task/Tool/Ads qua adapters, snapshot ký actor/workspace/version/input/expiry |
| M4.4 | Decision gọi domain service dưới lock; revoke trước claim; frozen input và executor permission/expiry/policy recheck; producers approval/analysis |
| M4.5 | Diagnostic/ledger bounded theo workspace, UI review/approval, race/rollback/recovery/scope/restore gates và runbook |

Consumer cố định chỉ ghi receipt nội bộ, không AI, email, Ads write hoặc tự tạo
Task/action. Không có scheduler mới; automation_outbox/Temporal hiện có giữ nguyên.
Approval requested bao phủ Task create/transition/attempt, Tool pending, Ads
pending và autopilot chuyển về cần duyệt. Analysis completed sau summary hoàn chỉnh.

Giao diện Approval Center đặt tại Tasks, giữ các surface cũ. Hiển thị nội dung,
thời hạn, input hash và dry-run; checkbox review bắt buộc. Client không giữ quyền
phê duyệt: backend tiếp tục kiểm scope/actor/hash/version/expiry/domain policy.

## Bằng chứng trước rollout

- M4.2:22event/delivery focused đạt; sau thêm ARQ thật,11delivery tests đạt.
- M4.4:38tests unified/Tool/Ads đạt; CHECK/FK và diagnostics M4 focused47đạt.
- Gate bổ sung cuối gồm M4/factory/autopilot: **73passed**,1ARQ deprecation warning.
- Full lượt đầu629passed/1failure: kiểm factory còn đếm32routers/231API; đã cập
  nhật số lượng reviewed33/237, giữ unique/handler assertions. Factory chạy lại6/6.
  Không dùng lượt có failure làm gate đạt. Full chạy lại sau sửa và bổ sung tests:
  **636passed, không skip, 596.05s**,2ARQ deprecation warnings, không failure.
- Runtime/SSE8/8, TypeScript đạt; production build riêng18pages; mock12routes đạt.
- 231API cũ và mọi schema cũ khớp checkpoint M4.1; thêm6operations, tổng237.
- Clone0035→0036→0035→0036 và0035→0037→0035→0037/Alembic check đạt;
  hash90bảng nghiệp vụ cũ giữ nguyên, database nguồn không đổi.
- Browser/API18100/pao_test/worker ARQ/Redis15 thật: approve/reject, checkbox,
  stale input và replay409;4events delivered/4receipts;0provider calls.
- Fixture restore91bảng hash-exact; nguồn không đổi. Browser replay sau CSS/full
  regression cũng đạt; screenshot cuối đã kiểm trực quan.
- Sau scoped restart API/worker: API health/ready/Web200, worker healthy,
  Alembic check đạt,237operations/live exact binding khớp,3/3old M2 archives replay.
- Live flags off được kiểm qua config và HTTP: status trả disabled, inbox/
  diagnostics/ledger409, legacy Tasks200. Event/outbox/receipt vận hành đều0.

## Bằng chứng/backup riêng

Checkpoint trước M4.2 có restore:
`.runtime/checkpoints/p0-20261007T063237-ed37901f/manifest.json` (0035/91bảng vật lý/3artifact).
Clone backup cuối: `.runtime/m4-pre-9427effe664e42f6a7c53dedda724ddf.dump`.
Browser backup đầu: `.runtime/m4-browser-3490c5a7b70948ceb91e212f3793c609.dump`.
Browser backup cuối: `.runtime/m4-browser-31e7ebabaa624c6c8b42007cad7cd1cd.dump`.
Checkpoint dữ liệu0035 mới nhất ngay trước rollout có restore:
`.runtime/checkpoints/p0-20261007T071757-1ee696f6/manifest.json`,599source files,
91bảng vật lý/3artifact. Archive tại checkpoint này là code M4 mới; nếu rollback
code0035 thì dùng source archive baseline `p0-20261007T063237-ed37901f`, kết hợp
backup dữ liệu0035 mới nhất trong môi trường riêng, không restore đè live mù quáng.
Screenshot: `.runtime/m4-approval-ui.png`. Không chia sẻ `.runtime` hoặc credentials.
Checkpoint cuối0037 được tạo sau khi chốt tài liệu bằng
`scripts/backup_acos_checkpoint.py`; manifest ghi source/database/hash và kết quả
restore trong `.runtime/checkpoints`. Không commit/push tự động, giữ dirty edits cũ.

Backend binding freeze:
`cc68e35b220f1b01d9a68688ea7c262eb0d91738b3e68db73b87d58044fa4a62`.
0036 thêm1bảng receipt,0037 thêm FK profile/approval hash;91ORM/92bảng vật lý.
0037 downgrade từ chối profiles mới, không mất dữ liệu; không dùng downgrade live
như một biện pháp rollback mặc định.

## Giới hạn nghiệm thu

Ba flags M4 phải giữ false trên vận hành sau rollout. Không có real Meta/Google/
MCP/Telegram call; dry-run Ads tests dùng FakeMeta, không là gate M3.
Không có purge, automatic dead-letter replay, external exactly-once, business
workflow runner hoặc out-of-order state projection. Consumer receipt không cần
aggregate ordering; consumer nghiệp vụ tương lai phải nghiệm thu ordering riêng.
Revoke chỉ pending/queued; đã executing trả409. Không thể hứa thu hồi external
HTTP write đã gửi hoặc atomic permission check với dịch vụ ngoài.

Xem [ADR M4](ADR-M4-DELIVERY-AND-APPROVALS.vi.md),
[vận hành](M4-OPERATIONS.vi.md) và [M4.1](M41-LOCAL-ACCEPTANCE-2026-10-07.vi.md).

## Files và bước tiếp theo

Events module: producer/delivery/approvals/guards/api; models/migrations0036–0037;
Task/Tool/Ads/Intelligence domain hooks, app/router, runtime worker và config flags.
Frontend: ApprovalCenter/CSS scoped trong Tasks, contracts additive. Tests và
scripts có migration clone, browser worker/profile, restore/live check, factory/
metadata gate cập nhật. Không đổi folder dự án, dependencies hay protected source.

Không tự triển khai M5B/P6 hoặc kết nối tài khoản thật. Bước cần owner chọn tiếp
là nghiệm thu M3 với account/kỳ/export hoặc credentials được cấp an toàn, ưu tiên
read-only; đồng thời production reboot/cold restore cần VM/VPS riêng như gate P0.
