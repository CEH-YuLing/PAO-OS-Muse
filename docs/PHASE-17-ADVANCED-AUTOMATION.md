# Phase 17 — Advanced Automation

Phase 17 thêm boundary Temporal cho workflow dài hạn. ARQ tiếp tục xử lý chat, memory, sync và Ads action ngắn; PAO chỉ chuyển use case có durable timer, approval wait hoặc external signal sang Temporal.

## Phạm vi đã triển khai

- Workflow allowlist `approval_wait` và `follow_up`; payload giới hạn 16 KB.
- Temporal workflow ID idempotent theo workspace/request key, execution timeout tối đa theo cấu hình.
- Durable approval bằng signal `approve`/`reject`, durable timer, cancellation và query state.
- PostgreSQL projection và append-only audit phục vụ RBAC/UI; Temporal history là execution authority.
- Owner/admin quyết định, operator được tạo workflow, viewer/analyst chỉ đọc theo workspace.
- Temporal Server `1.30.6` và worker Python self-host; cấu hình cài mới vẫn mặc định `TEMPORAL_ENABLED=false`.
- Không gọi Meta/Google write và không thay thế các ARQ job đang ổn định.

## Vận hành

Biến cấu hình nằm trong `.env.example`. Compose profile `automation` tạo schema PostgreSQL bằng công cụ chính thức, khởi động server và đăng ký namespace `default`; `scripts/temporal_worker.py` chạy worker riêng khi gate được bật. Workflow deterministic được tách khỏi cấu hình/SQLAlchemy để tương thích Temporal sandbox.

Thiết kế dùng signal vì Temporal ghi signal vào workflow history và workflow có thể chờ bằng durable condition/timer theo [Temporal Python message passing](https://docs.temporal.io/develop/python/workflows/message-passing). Tổng quan SDK chính thức mô tả Workflows, Activities, Workers, timers và cancellation tại [Temporal Python guide](https://docs.temporal.io/develop/python).

## Xác minh

- Migration roundtrip `base → 0016` và Alembic check.
- RBAC, idempotency, optimistic workflow version, approval signal, cancel, projection terminal guard và rollback khi Temporal không sẵn sàng.
- Backend Phase 1–17: 152 tests passed.

## Kết quả triển khai local

- Backup `.runtime/pre-phase-17-20260922-133046.dump` có 248.573 bytes và đọc được bằng `pg_restore --list`.
- Counts của 48 bảng cũ giữ nguyên; database lên revision `0016`.
- Production build và browser acceptance Phase 1–17 đạt; API/Web/assets HTTP 200.
- Temporal local đang bật tại `127.0.0.1:7233`; server healthy và worker `pao-automation` đang chạy.
- Smoke test thật đã tạo workflow, ghi run ID, nhận signal `approve`, chạy activity projection và hoàn tất; bằng chứng ở `.runtime/phase-17-temporal-smoke.json`.
- Chưa nghiệm thu workflow chờ nhiều ngày hoặc fault/replay có chủ đích qua restart worker/server giữa lúc workflow đang chờ.
