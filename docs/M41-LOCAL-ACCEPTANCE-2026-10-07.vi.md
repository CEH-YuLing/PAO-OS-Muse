# M4.1 — Nghiệm thu nền tảng event ledger/outbox LOCAL

Ngày07/10/2026. Checkout duy nhất: `F:\PAO-ACOS`.

## Kết quả

M4.1 đạt local: Task hoàn thành hợp lệ và sự kiện/outbox được lưu cùng transaction.
Đây **không phải hoàn tất toàn bộ M4**, không thay nghiệm thu M3 dữ liệu thật.
Producer vận hành vẫn tắt (`BUSINESS_EVENTS_ENABLED=false`); database0035 có
0business events/0outbox. Không có consumer, outbound effects hoặc P6 runner.

## Đã triển khai

- Module events riêng; hook hai đường create-completed/transition-completed.
- Migration0035 additive: ledger immutable, pending outbox, scope composite FK,
  unique aggregate/version và row lock chống hoàn thành đồng thời.
- Envelope server-generated, payload reference/hash thay vì evidence thô.
- Internal republish idempotent; hash conflict/missing outbox fail closed.
- Transaction rollback bao phủ Task, TaskActivity, ledger và outbox.
- Profile browser `--events`, kiểm tra live read-only và clone migration/restore.
- Checkpoint source archive giữ thêm `AGENTS.md` để không mất quy tắc vận hành.

API/UI nghiệp vụ hiện có được giữ nguyên; không thêm API điều khiển event.

## Bằng chứng kiểm thử

| Gate | Kết quả |
| --- | --- |
| Focused event/Task/characterization | 27passed; FK test được siết SQLSTATE23503 sau lượt này và chạy lại trong full suite |
| Full backend trên pao_test/Redis15 | **595passed, không skip, 489.99s** |
| Runtime/SSE | 8/8 |
| TypeScript | Đạt |
| Production build kiểm tra riêng | 18pages, không thay cache web live |
| Browser mock regression | 12routes |
| Browser M4.1 với API18100/database thật | Create và transition completed, activity/progress, stale409 đạt; 0provider calls |
| Fixture backup/restore | 90business tables byte/hash-exact; 2pending outbox; nguồn không đổi |
| Migration clone0034→0035→0034→0035 | 88bảng nghiệp vụ cũ không đổi hash, 231operations/schema cũ giữ nguyên |
| Alembic check sau restart | Không có upgrade operations mới |
| Live API health/ready và Web | HTTP200; worker healthy |
| Live contract/exact backend binding | Đạt, SHA256 bên dưới |
| Replay artifact M2 cũ | 3/3 sau restart |

Backend binding sau source freeze:
`aa7470086f9e32e27f29c8d510eb234d868a4cfc5f7dcbaefebd2c204b03824f`.
Có 1DeprecationWarning từ ARQ đóng Redis pool; không có test failure.
91bảng vật lý gồm Alembic; 90bảng ORM/nghiệp vụ.

## Backup và vận hành

Checkpoint trước thay đổi đã thử restore:
`.runtime/checkpoints/p0-20261007T061230-fe0bac54/manifest.json` (0034/89bảng vật lý/3artifact).
Backup migration clone: `.runtime/m41-pre-9f0697ef7b364d7299f7d3dc6c74216b.dump`.
Backup fixture: `.runtime/m41-browser-2f09f84f25b749999638342a714ccd6d.dump`.
Screenshot: `.runtime/m41-task-ui.png`.
Các tệp này là bằng chứng riêng trong `.runtime`, không đưa lên Git.
Checkpoint cuối0035 được tạo sau khi cập nhật tài liệu bằng
`scripts/backup_acos_checkpoint.py`; manifest trong `.runtime/checkpoints`
ghi source archive, database backup, hash và kết quả restore.

Chỉ restart API/worker PAO sau idle gate và kiểm executable/start-time; giữ web,
Ollama, containers/volumes và dữ liệu cũ. Docker healthy, không cần sửa thêm.
Không commit/push tự động; giữ nguyên thay đổi có sẵn trong checkout.

## Còn thiếu — bước tiếp theo

M4.2: delivery lease/retry/dead-letter và consumer dedup/crash recovery, bắt đầu
bằng projection nội bộ không LLM. M4.3–M4.5: approval center/permission recheck/
race/revocation và nghiệm thu tổng hợp. Chưa có các producer approval/Ads.
Chưa chọn dữ liệu/credentials để nghiệm thu M3; chưa reboot drill trên VM/VPS.
Không tự bật producer vận hành chỉ vì test fixture đã đạt.

Giới hạn hash/immutable trigger/downgrade tại
[ADR M4.1](ADR-M41-TASK-EVENT-LEDGER.vi.md).
