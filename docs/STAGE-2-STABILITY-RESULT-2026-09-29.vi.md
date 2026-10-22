# Kết quả Giai đoạn 2 — Ổn định nền tảng PAO

Ngày nghiệm thu: 29/09/2026  
Nhánh: `pao-stage-2-stability`  
Phạm vi: M0 trong PAO Master Roadmap

## Kết luận

Giai đoạn 2 **đạt trên môi trường local**. Workflow dài hạn không còn phụ thuộc
vào việc API gọi Temporal thành công trước khi transaction database được commit.
Request start/approve/reject/cancel được ghi bền vững trước, worker mới chuyển
tiếp sang Temporal. Các service đã được restart sau migration và đang healthy.

Không bật Meta write, Limited Autopilot hoặc thao tác quảng cáo thật. Không tạo
dữ liệu workflow giả trong database ứng dụng để nghiệm thu.

## Thay đổi đã triển khai

1. Migration `0021` thêm `request_fingerprint` và bảng `automation_outbox`.
2. Start workflow commit row, audit và outbox trong cùng transaction; Temporal
   offline không làm mất request.
3. Fingerprint SHA-256 bao phủ kind, payload, approval requirement, timeout và
   wait time; cùng key/khác nội dung trả 409.
4. Start đồng thời cùng nội dung trả về cùng một workflow thay vì lỗi unique/500.
5. Approval/cancel dùng row lock + version; hai quyết định đồng thời chỉ một
   quyết định thành công.
6. Dispatcher lease hai phút, retry tối đa năm lần với backoff, trạng thái dead
   và failure projection công khai `automation_dispatch_failed`.
7. Workflow ID xác định trước và outbox dedupe key giúp retry start an toàn;
   lease hết hạn được worker khác thu hồi.
8. Timer Temporal có thể bị cancel đánh thức ngay, không phải đợi hết thời gian.
9. ARQ cron gọi automation dispatcher mỗi 10 giây.
10. ADR xác định PostgreSQL/Temporal/ARQ ownership và failure behaviour.
11. Bộ fixture chất lượng đầu ra gồm metric definition, missing data, source
    conflict và permission refusal; correctness được tách khỏi completion.
12. OpenAPI/TypeScript contract được sinh lại từ source hiện tại.

## Backup và migration database thật

Script `scripts/deploy_stage2.py` chỉ chấp nhận local database `apex`, kiểm tra
short jobs đang idle, backup rồi restore thật vào database cô lập có tên an toàn.
Database restore tạm đã được xóa sau kiểm tra; không xóa database ứng dụng/test.

| Database | Kích thước backup | Restore kiểm tra | Bảng restore |
|---|---:|---|---:|
| `apex` | 315.475 byte | Đạt | 62 |
| `temporal` | 92.079 byte | Đạt | 39 |
| `temporal_visibility` | 46.043 byte | Đạt | 3 |

Các file nằm trong `.runtime/pre-stage-2-*-20260929-211559.dump`. Báo cáo máy đọc
được nằm ở `.runtime/stage-2-migration.json`. Database ứng dụng hiện ở revision
`0021`; lần migration đầu xác nhận số dòng của toàn bộ 60 bảng ứng dụng cũ không
đổi, rồi thêm outbox thành 61 bảng ứng dụng (62 bảng public khi tính cả
`alembic_version`).

## Bằng chứng kiểm thử

| Hạng mục | Kết quả |
|---|---|
| Backend + schema | **178 passed**, Alembic check đạt |
| Migration roundtrip trên `pao_test` | `base → 0021`, đạt |
| Race/replay/crash recovery | Đạt: concurrent start, concurrent decision, full fingerprint, offline retry, expired lease |
| Runtime/SSE | **8/8 passed** |
| Frontend production build | Đạt, 17 static/dynamic routes |
| Browser acceptance | **12/12 route passed** |
| Temporal thật | Workflow synthetic hoàn tất trong namespace local |
| API/ready/web | HTTP 200/200/200 |
| OpenAPI | 97 paths; TypeScript contract sinh thành công |
| Dependencies | `pip check`: không có package lỗi |
| Process health | API, web, worker, Temporal worker, Telegram, Ollama đều alive |
| Safety gates | Meta write off; Autopilot global off; không provider write |

## Giới hạn còn lại

- Outbox dead được phản chiếu thành workflow failed nhưng chưa có màn hình vận
  hành riêng để retry thủ công hoặc xem hàng đợi.
- Ca Telegram approve → Temporal completion chưa chạy trên dữ liệu thật; quyết
  định này có chủ ý để không tạo bản ghi thử trong database người dùng.
- Fixture chất lượng hiện là bộ chuẩn máy đọc được và validator; chưa có model
  evaluation runner chấm câu trả lời LLM tự động.
- Backup nằm cùng ổ đĩa dự án. Giai đoạn production phải mã hóa và sao chép sang
  vị trí/host khác, đồng thời kiểm tra restore định kỳ.

## Điểm bắt đầu tiếp theo

Giai đoạn 3 là M1 — Goal và Task nghiệp vụ: bổ sung goal, dependency, attempt,
state machine và evidence-based completion trên nền outbox/recovery vừa ổn định.
