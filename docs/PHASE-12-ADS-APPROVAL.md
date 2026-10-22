# Phase 12 — Ads Approval

Ngày hoàn tất: 15/09/2026. Phase này thay xác nhận trực tiếp của Phase 11 bằng approval nghiệp vụ dùng chung cho UI và Telegram. Phạm vi là Copilot cho nhóm nội bộ; chưa có policy engine hoặc Autopilot của Phase 13.

## Luồng chuẩn

1. Owner/admin tạo Ads action. PAO đọc Meta, lưu `before_state`, `proposed_state`, lý do, nguồn, confidence, compensating action và hạn duyệt mặc định 24 giờ.
2. Approval xuất hiện trong `GET /v1/approvals` và được gửi tới Telegram của owner/admin. Người duyệt có thể xem Details, Approve hoặc Reject.
3. UI/Telegram chỉ gọi Approval Service. Approve chuyển action sang `approved/queued`; Reject chuyển sang `rejected/cancelled`. Callback không gọi Meta.
4. ARQ dispatcher lấy action đã duyệt và worker mới được phép thực thi. Worker kiểm tra lại user, role, connection/version, quyền, khóa resource và provider state.
5. Worker lưu kết quả/audit; Telegram collector gửi trạng thái cuối. Meta POST không retry khi kết quả không chắc chắn.

Endpoint execute cũ `/v1/ads/actions/{id}/execute` bị khóa bằng HTTP 409 để không thể bỏ qua Approval Service.

## Quyền và trạng thái

- Thành viên workspace có thể xem inbox; chỉ owner/admin đang hoạt động được Approve/Reject.
- Approval: `pending`, `approved`, `rejected`, `expired`.
- Execution: `pending`, `queued`, `executing`, `simulated`, `succeeded`, `failed`, `unknown`, `stale`, `cancelled`.
- Quyết định mang optimistic version và kênh `ui` hoặc `telegram`. Callback Telegram còn bị ràng buộc với peer, chat, message đã gửi và callback data thực tế.
- Action quá hạn được dispatcher chuyển `expired/cancelled`. Action đang thực thi mất worker chuyển `unknown`; không tự chạy lại.
- Reject vẫn hoạt động khi connection Meta đã mất hiệu lực. Approve luôn kiểm tra lại connection và `ads_management` nếu là live write.

## API và giao diện

- `GET /v1/approvals?workspace_id=...&status=...`
- `GET /v1/approvals/{id}`
- `POST /v1/approvals/{id}/approve`
- `POST /v1/approvals/{id}/reject`

Panel **Ads Approval · Phase 12** hiển thị inbox/lịch sử, before/proposed state, expiry, decision channel và audit. Telegram gửi các nút **Duyệt dry-run** hoặc **APPROVE GHI META**, **Từ chối**, **Chi tiết**, rồi gửi kết quả cuối riêng.

## Cấu hình và an toàn

`ADS_APPROVAL_TTL_HOURS=24` nhận giá trị 1–168 giờ. `META_WRITE_ENABLED=false` vẫn là mặc định và đang được giữ ở bản local. Phase 12 không thêm policy tự duyệt, không chạy compensating action tự động và không bật provider write.

## Nghiệm thu

- Migration `0011` round-trip đạt; `alembic check` không thấy schema drift.
- Backend: **122 passed** trên DB `pao_test` và Redis DB 15. Bộ test bao phủ RBAC, version/expiry, idempotency, UI/Telegram decision, đúng Telegram message/identity, worker queue, resource lock, state drift, unknown/no retry và audit.
- OpenAPI/TypeScript contract sinh lại thành công; **8 runtime tests**, Next production build, `pip check`, `git diff --check` và browser acceptance đều đạt.
- Browser acceptance xác minh inbox, Details, UI approve, audit và worker handoff `queued`; API giả lập không gọi provider.
- Triển khai local cuối tạo backup `.runtime/pre-phase-12-20260915-161159.dump` (**161.638 bytes**), kiểm tra được bằng `pg_restore --list`, giữ nguyên counts của 29 bảng và xác nhận DB ở `0011`.
- Post-deploy: API ready, web, 8 assets, write-status và approval inbox đều HTTP 200. Inbox/action/audit production đều trống; `META_WRITE_ENABLED=false`; không có provider write trong triển khai.

Phase 13 chỉ được bắt đầu bằng một lát cắt riêng cho policy/kill switch/limited autopilot sau khi Phase 7–12 được nghiệm thu với Meta thật ở dry-run.
