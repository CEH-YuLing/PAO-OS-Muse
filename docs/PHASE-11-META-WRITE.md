# Phase 11 — Meta Write

Ngày hoàn tất: 15/09/2026. Phạm vi theo mục 67–77, 89, 101–104 và 137 master spec: pause, resume và cập nhật daily budget ở chế độ Copilot. Phase 11 không có autopilot. Approval inbox/Telegram đã được bổ sung ở Phase 12; phần xác nhận trực tiếp mô tả dưới đây là hành vi lịch sử đã được endpoint approval thay thế.

## Ranh giới thực thi

Mỗi thay đổi là một `ads_actions` object. Owner/admin tạo action trước để PAO GET resource hiện tại từ Meta, xác minh resource có trong warehouse, lưu `before_state`, `proposed_state`, reason/confidence/source và compensating action. Action dùng UUID request key và payload hash để chống dùng lại idempotency key với nội dung khác.

Execute là bước riêng, yêu cầu version hiện tại và chuỗi `CONFIRM`. Đây là xác nhận Copilot tối thiểu bắt buộc cho Phase 11. Phase 12 sẽ bổ sung approval queue, approve/reject/details qua UI và Telegram; không được coi xác nhận Phase 11 là autopilot policy.

Dry-run mặc định và vẫn đọc lại resource để phát hiện state drift, nhưng không gửi POST. Live write chỉ mở khi `META_WRITE_ENABLED=true`, token có cả `ads_read` và `ads_management`, user/role/connection/version còn hợp lệ. OAuth yêu cầu thêm `ads_management` khi write được bật, nên phải kết nối lại Meta sau khi đổi cấu hình.

Budget dùng `daily_budget` theo **minor units** của Meta để tránh tự đoán số chữ số thập phân tiền tệ. Update chỉ áp dụng campaign/adset có daily budget hiện tại, khác giá trị cũ và mức thay đổi tuyệt đối không vượt `META_WRITE_MAX_BUDGET_CHANGE_PCT` (mặc định 20%). Ad không có budget trực tiếp.

Execute khóa Redis theo connection/resource. PAO đọc lại state ngay trước POST; state cần sửa đã đổi thì action thành `stale`. POST write không retry. Network/response không chắc chắn hoặc đã POST nhưng chưa đọc lại được state sẽ thành `unknown`, không tự chạy lại. Worker phục hồi action `executing` quá hạn thành `unknown`.

Sau write thành công, PAO GET resource lần nữa, xác minh proposed state và lưu `after_state`. `compensating_action` mô tả cách hoàn tác nhưng không tự chạy. Mọi transition ghi append-only `ads_action_audits`; result 24h/72h/7d được dành cho phase theo dõi sau.

## API và UI

- `GET /v1/ads/write-status`
- `POST /v1/ads/actions`
- `GET /v1/ads/actions`
- `GET /v1/ads/actions/{id}`
- `POST /v1/ads/actions/{id}/execute`

Panel **Meta Write · Phase 11** nằm dưới Performance Intelligence: chọn resource/action, nhập reason, giữ dry-run hoặc chọn live, xem before/proposed state rồi xác nhận riêng. Action history hiển thị trạng thái và audit.

## Cấu hình

Phase 11 triển khai với live write mặc định tắt. Sau khi Meta read hoạt động và đã nghiệm thu warehouse, có thể chạy `python scripts/setup_meta_write.py --enable`, nhập chính xác câu xác nhận, restart API/worker rồi kết nối lại Meta. `--disable` tắt write ngay sau restart.

## Nghiệm thu kỹ thuật

- Backend kiểm tra OAuth scope, RBAC/isolation, allowlist payload, warehouse scope, snapshot, budget cap, idempotency/version, Copilot confirmation, dry-run, live success, state drift, compensating action, audit, resource lock, unknown/no retry và recovery.
- Migration roundtrip và backend: **118 passed** trên `pao_test` cùng Redis DB 15; `alembic check` không phát hiện schema drift. Test riêng xác nhận dry-run vẫn hoạt động với `ads_read` khi live write tắt, còn action live bị từ chối.
- OpenAPI sinh lại **48 paths** và TypeScript contract thành công; `npm run build`, **8 runtime tests**, `pip check` và browser acceptance đều đạt.
- Browser acceptance xác minh snapshot, xác nhận Copilot, audit và dry-run bằng API giả lập. Không gọi Meta thật trong test.
- Triển khai local đã tạo backup `.runtime/pre-phase-11-20260915-110739.dump` (**149.129 bytes**), kiểm tra được bằng `pg_restore --list`, giữ nguyên counts của 27 bảng cũ và nâng DB lên revision `0010`.
- Post-deploy: `/ready`, web, 8 assets, write-status và action-list đều HTTP 200. API báo `enabled=false`, `mode=copilot`, `dry_run_default=true`; database có 0 action/audit.
- Production hiện `META_ENABLED=false` và `META_WRITE_ENABLED=false`; không có provider write nào được thực hiện trong quá trình triển khai.
