# Phase 10 — Performance Intelligence

Ngày: 14/09/2026. Phạm vi theo mục 37–43, 74, 100–104 và 136 master spec: targets, deterministic rule engine, anomaly detector, Performance Analyst và recommendation engine. Phase 10 chỉ đọc normalized warehouse; không có Meta write, Ads approval hoặc autopilot.

## Thiết kế

```text
Ads Warehouse → targets + statistical guardrails
              → same-weekday/hour baseline
              → anomalies + deterministic rules
              → structured recommendations
              → Performance Analyst / PAO UI
```

Migration `0009` thêm `ad_targets`, `ads_rules`, `ad_intelligence_runs`, `ad_anomalies` và `ad_recommendations`. Mọi kết quả giữ connection version, account, time range, attribution, source job IDs, last sync và data freshness.

Targets cấu hình target CPA/ROAS cùng minimum spend, impressions, clicks, conversions, run days và freshness. Ba rules mặc định được lưu thành dữ liệu, có thể bật/tắt: không có purchase sau 2× target CPA, CPA vượt target 20%, ROAS vượt target 30% và ổn định ba ngày.

Anomaly không chỉ so ngưỡng tuyệt đối. Mỗi campaign/slot hiện tại được so với tối đa bốn mẫu lịch sử cùng thứ và cùng giờ khi dùng hourly. Detector hỗ trợ spend anomaly, CPA spike, ROAS/CTR collapse, CPM/frequency spike, conversion disappearance và tracking discrepancy. Baseline dưới hai mẫu không phát anomaly. Alert có fingerprint, severity, first/last seen, acknowledged, resolved và được deduplicate.

Recommendation có schema cố định: type, confidence, impact/risk, reason codes, explanation, proposed action, lineage và freshness. Sample thấp chỉ tạo `LOW_SAMPLE_SIZE`. Dữ liệu quá cũ hạ confidence và thêm `STALE_DATA`. Scale review vẫn bị chặn khi thiếu budget history, learning state và creative health.

Worker kiểm tra warehouse sau mỗi cron dispatch và tự phân tích đúng một lần cho từng slot daily/hourly hoàn tất mới. Request key gồm target, slot và thời điểm source update: dữ liệu không đổi không tạo run lặp; restatement tạo lần phân tích mới và cập nhật alert/recommendation đã deduplicate.

Mọi `proposed_action` đều `executable=false`. Đề xuất pause/budget chỉ mô tả đối tượng cần review; Phase 10 không có endpoint gửi lệnh tới Meta. Phase 11 và 12 mới xây write/approval.

Performance Analyst có prompt riêng và chỉ nhận structured intelligence đã lưu, được lọc theo workspace, user và Meta connection. Nếu chưa chạy analysis, agent yêu cầu cấu hình targets/chạy dashboard thay vì tự tạo metrics.

## API và UI

- `GET/PUT /v1/ads/targets`
- `GET /v1/ads/rules`, `PUT /v1/ads/rules/{id}`
- `POST /v1/ads/intelligence/analyze`
- `GET /v1/ads/anomalies`, `POST /v1/ads/anomalies/{id}/acknowledge`
- `GET /v1/ads/recommendations`, `POST /v1/ads/recommendations/{id}/dismiss`

UI Phase 10 nằm dưới Ads Reporting: cấu hình target/guardrail, bật tắt rules, chạy daily/hourly analyst, xem anomaly severity/baseline, confidence/reason codes/freshness và lifecycle acknowledge/dismiss.

## Nghiệm thu kỹ thuật

- Migration roundtrip và `alembic check` đạt.
- Backend đạt **110 passed** trên `pao_test` và Redis DB 15.
- Runtime đạt **8 passed**; OpenAPI contracts, TypeScript, production build và `pip check` đạt.
- Browser acceptance dùng API giả lập tách biệt, không gọi Meta/Telegram thật; bằng chứng `.runtime/phase-10-intelligence-browser.png`.
- Triển khai local đã tạo `.runtime/pre-phase-10-20260914-210945.dump` (128.842 bytes), kiểm tra `pg_restore --list`, giữ nguyên counts 22 bảng cũ và migrate `0008 → 0009`.
- Sau triển khai, API/web trả HTTP 200, 8 assets đều HTTP 200, bốn read API intelligence trả HTTP 200, Performance Analyst có trong registry và worker cron không có lỗi. Bằng chứng `.runtime/phase-10-health.json`.
- Meta production vẫn tắt và warehouse trống, nên chưa có target, analysis, anomaly hay recommendation thật. Cần nghiệm thu số liệu Meta thật trước khi dựa vào recommendation để ra quyết định.
