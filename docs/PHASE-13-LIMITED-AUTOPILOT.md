# Phase 13 — Limited Autopilot

Ngày hoàn tất: 15/09/2026. Phạm vi theo mục 22–23, 69, 72–74, 139 và 148–149 của master spec: policy lưu trong DB, bốn Ads mode, pause/resume/budget có giới hạn, kill switch và emergency freeze. Phase này không tạo campaign/adset/ad tự động.

## Mô hình an toàn

Fresh install là `observer`. Một action chỉ được tự duyệt khi đồng thời thỏa tất cả điều kiện:

1. Global gate `ADS_AUTOPILOT_GLOBAL_ENABLED` và Meta gate `META_AUTOPILOT_ENABLED` đều bật.
2. Policy của workspace/account ở mode `autopilot`, workspace không `halted` và không emergency frozen.
3. Proposal do `performance_analyst` tạo, gắn một recommendation đang active, đúng connection/version/account/resource.
4. Action nằm trong allowlist riêng: pause, resume hoặc update budget. Proposal thủ công luôn quay về approval Phase 12.
5. Confidence, impressions, conversions và data freshness đạt mức policy; recommendation không còn blocker chưa giải quyết.
6. Không nằm trong quiet hours, chưa vượt số action/ngày, budget change không vượt percentage cap hoặc daily budget ceiling.
7. Worker kiểm tra lại toàn bộ policy ngay trước Meta. Policy/version thay đổi sẽ trả action về `pending` để người dùng review.

Policy đủ điều kiện chuyển action sang `approved/queued`, ghi `decision_channel=autopilot`, policy id/version/snapshot và audit. Policy engine không gọi Meta; ARQ worker vẫn là nơi duy nhất thực thi. Resource lock, before/after state, compensating action và no-blind-retry của Phase 11–12 vẫn giữ nguyên.

## Policy trong DB

`ads_autopilot_policies` lưu mode, workspace kill switch, allowlist pause/resume/budget, max budget %, daily budget ceiling theo minor units, minimum sample/confidence, freshness, quiet hours, action/day, freeze state và optimistic version. `ads_policy_audits` là lịch sử append-only cho create/update/freeze/unfreeze/automatic freeze.

Daily budget ceiling là trần an toàn áp vào resource được thay đổi. PAO không suy đoán tổng ngân sách account từ campaign/adset vì CBO/ABO có thể làm cộng trùng.

## Emergency freeze

Policy tự chuyển `autopilot → advisor`, đặt `halted=true` và dừng write tự động khi phát hiện:

- recommendation/data quá cũ;
- credential/connection hết hiệu lực;
- ít nhất ba Meta sync job thất bại trong 15 phút;
- critical `TRACKING_DISCREPANCY`;
- critical `SPEND_ANOMALY`.

Owner/admin cũng có nút **EMERGENCY FREEZE**. Unfreeze yêu cầu version và chuỗi xác nhận riêng, nhưng workspace vẫn halted; muốn chạy lại phải lưu policy và xác nhận enable một lần nữa. Telegram gửi cảnh báo freeze riêng cho owner/admin.

## API và UI

- `GET /v1/ads/autopilot/status`
- `GET /v1/ads/autopilot/policies`
- `PUT /v1/ads/autopilot/policies`
- `GET /v1/ads/autopilot/policies/{id}`
- `POST /v1/ads/autopilot/policies/{id}/freeze`
- `POST /v1/ads/autopilot/policies/{id}/unfreeze`

Panel **Limited Autopilot · Phase 13** cho owner/admin cấu hình policy, xem ba runtime gate, trạng thái hiệu lực, version/audit và freeze. Việc bật account cần checkbox xác nhận rõ ràng. Script `python scripts/setup_autopilot.py --enable` yêu cầu nhập `ENABLE LIMITED AUTOPILOT`; `--disable` tắt cả global và Meta gate.

## Nghiệm thu

- Migration `0012` round-trip đạt cả khi DB test đã có action `decision_channel=autopilot`; `alembic check` sạch.
- Backend: **136 passed** trên `pao_test`/Redis DB 15. Test bao phủ default fail-closed, RBAC/version, global/Meta/workspace gates, allowlist, manual-vs-analyst source, minimum sample/confidence/freshness, quiet hours qua nửa đêm, daily action limit, budget percentage/ceiling, worker recheck, manual và automatic freeze, Telegram freeze alert.
- OpenAPI **57 paths**, TypeScript contract, **8 runtime tests**, Next production build, `pip check`, `git diff --check` và browser E2E đều đạt.
- Browser E2E xác minh tạo policy, deliberate enable, effective gates, audit và Emergency Freeze về Advisor.
- Triển khai tạo backup `.runtime/pre-phase-13-20260915-164201.dump` (**161.638 bytes**), kiểm tra bằng `pg_restore --list`, giữ nguyên counts của 29 bảng cũ và nâng DB `0011 → 0012`.
- Post-deploy: API ready, web và 8 assets HTTP 200; policy/runtime APIs HTTP 200; policy/audit/action production đều trống. Default mode `observer`, global và Meta gates đều false; không có provider write.

Phase 13 đã có cơ chế kỹ thuật nhưng chưa được bật. Chỉ bật sau khi nghiệm thu Meta thật theo chuỗi read sync → warehouse → intelligence → Phase 12 approval → worker dry-run và kiểm tra policy bằng dữ liệu account thực.
