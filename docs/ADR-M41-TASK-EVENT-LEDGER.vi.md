# ADR M4.1 — Task event ledger và pending outbox

Ngày07/10/2026. Phạm vi: nền tảng local, không phải M4 business acceptance.

## Quyết định

Module `pao/modules/events` sở hữu producer; Task domain vẫn sở hữu trạng thái,
evidence, version và quyền completion. Không đưa producer vào SSE, không thêm
scheduler, không gọi LLM hay connector từ transaction.

Migration0035 thêm `business_events` và `business_outbox`. `task.completed` chỉ
được tạo ở create-completed hoặc transition-completed hợp lệ; cùng transaction
với Task/TaskActivity. Producer flush nhưng không commit. Flag
`BUSINESS_EVENTS_ENABLED=false` mặc định và vẫn tắt ở database vận hành.

Envelope do server tạo; payload chỉ tham chiếu Task/version và hash evidence,
không sao chép nội dung evidence. Unique workspace/type/aggregate/version và
Task row lock chống trùng. Publish lại cùng envelope trả event cũ; khác hash
hoặc thiếu outbox thì fail closed. Composite FK giữ scope workspace; trigger
chặn sửa/xoá ledger và đổi identity/scope outbox trực tiếp bằng SQL.

Không có API ledger hoặc consumer ở lát cắt này. Pending là trạng thái đã lưu,
không phải đã giao. Những trạng thái outbox còn lại chỉ là schema dự phòng;
lease, retry, dead-letter handling và consumer dedup thuộc M4.2.

## Phân biệt outbox hiện có

`automation_outbox` thuộc command delivery tới Temporal ở ADR-0001, không thay
đổi. `business_outbox` là business event pending mới, chưa nối với Temporal/ARQ.
Không coi hai bảng này là cùng một scheduler hoặc mở automation thông qua M4.1.

## Giới hạn và vận hành

- Đây là additive migration; trước rollout cần checkpoint có thử restore và
  migration clone giữ nguyên dữ liệu/hợp đồng cũ.
- Event ledger bất biến qua UPDATE/DELETE ứng dụng, không phải chống DBA có
  quyền disable trigger hoặc TRUNCATE. Backup và quyền database vẫn cần thiết.
- Hash không phải mã hoá hay chữ ký; không đảm bảo ẩn thông tin có entropy thấp.
- Chưa có retention/export/delivery metrics. Chưa dùng cho business automation.
- Không sửa hành vi progress cũ khi tạo Task đã completed ở checkpoint này.
- Downgrade xoá hai bảng mới; chỉ an toàn sau backup và kiểm tra chưa có sự kiện
  cần giữ. Thử downgrade ở clone không phải quyền xoá ledger vận hành.
- M3 dữ liệu thật chưa đạt; M4.2–M4.5 và P6 runner chưa triển khai.

Xem thiết kế và gate tại [M4.1](M41-DESIGN-AND-BLOCKER-2026-10-07.vi.md).

Quyết định này là snapshot lát cắt M4.1. M4.2–M4.5 về consumer/approval/profile
được bổ sung tại [ADR M4](ADR-M4-DELIVERY-AND-APPROVALS.vi.md).
