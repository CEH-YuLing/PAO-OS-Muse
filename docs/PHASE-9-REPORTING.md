# Phase 9 — Ads Reporting

Ngày: 14/09/2026. Phạm vi theo mục 44–46 và 135 master spec: báo cáo ngày, báo cáo tuần, Telegram delivery và dashboard PAO. Phase này chỉ đọc normalized warehouse. Không gọi Meta khi mở/tạo báo cáo và không thay đổi quảng cáo.

## Luồng dữ liệu

```text
Meta read-only → Ads Warehouse daily campaign metrics
                          ↓
              deterministic report snapshot
                 ↙                    ↘
          PAO dashboard          Telegram outbox
```

Báo cáo chỉ lấy `ad_metrics` có `granularity=daily`, `level=campaign` và attribution hiện hành. Nó không cộng ad/adset/hourly vào cùng tổng, nên tránh đếm trùng spend, conversions và reach. Mỗi báo cáo lưu connection version, account, currency, timezone, attribution, ngày nguồn mới nhất và thời điểm warehouse cập nhật.

## Database `0008`

- `ad_reports`: artifact báo cáo bất biến gồm kỳ, totals, comparisons, top campaigns theo spend, coverage và source lineage. Request key idempotent trong connection.
- `ad_report_deliveries`: liên kết report với Telegram peer và dedup prefix. Trạng thái được suy ra từ các phần của Telegram outbox: queued/sent/unknown/failed.
- `ad_report_schedules`: lịch daily/weekly theo account, giờ local, weekday cho weekly, destination Telegram và lần chạy tiếp theo.

Totals dùng Decimal/BigInteger từ warehouse: spend, revenue, purchases, leads, impressions, clicks, ROAS và CPA purchase. `NULL` vẫn là chưa có dữ liệu. Không tự biến thành zero.

## Báo cáo ngày và tuần

- Daily: một ngày hoàn tất; so với ngày trước và trung bình bảy ngày hoàn tất trước đó.
- Weekly: bảy ngày kết thúc tại ngày người dùng chọn; so với bảy ngày liền trước.
- Baseline thiếu coverage đầy đủ hoặc bằng zero → phần trăm so sánh là `NULL/—`, không tạo số phần trăm sai.
- Báo cáo có `coverage_days/expected_days`. Cho phép tạo artifact thiếu coverage nhưng UI và Telegram ghi rõ mức phủ dữ liệu.
- Campaigns được xếp theo spend, kèm revenue, purchase và ROAS nếu có. Đây là ranking mô tả, không phải đánh giá winner/loser.
- Underperformers/recommendations để Phase 10; creative winners/fatigue để Phase 14; CAC để Phase 15; budget movement/Ads actions để Phase 11–13. Báo cáo ghi rõ “chưa đánh giá/chưa có” thay vì suy đoán.
- Monthly/custom cron/email được yêu cầu ở kiến trúc báo cáo tổng thể nhưng Phase 9 trong mục 135 chỉ bắt buộc daily/weekly/Telegram/dashboard; các loại đó được hoãn.

## Scheduler và Telegram

Daily/weekly có lịch riêng cho từng account. Giờ gửi dùng timezone của ad account; weekly yêu cầu weekday 0–6. Scheduler chạy trong worker hiện có, bắt các lịch quá hạn, chọn ngày hoàn tất gần nhất và tạo report bằng request key `schedule + period` để chống trùng.

Chỉ owner/admin được tạo báo cáo, gửi Telegram và sửa lịch. Việc bật lịch Telegram yêu cầu bot đang bật và một peer được whitelist cho đúng user/workspace. Scheduler kiểm tra lại Meta connection version, user/role và peer trước khi tạo/gửi; mất quyền sẽ tắt lịch.

Manual và scheduled delivery đều đi qua Telegram outbox Phase 6. Report dài dùng chung cơ chế chia UTF-16; cùng report/peer không xếp hàng hai lần. Network uncertainty vẫn chuyển delivery thành `unknown`, không tự gửi lại gây trùng.

Không có report thật hoặc tin Telegram Ads nào được tạo trong lúc triển khai, vì Meta chưa cấu hình và warehouse production đang trống.

## API và UI

- `POST /v1/reports`: tạo daily/weekly report cho ngày đã hoàn tất.
- `GET /v1/reports`: lịch sử có filter account/kind và phân trang.
- `GET /v1/reports/{id}`: report cùng delivery status.
- `POST /v1/reports/{id}/telegram`: xếp report vào Telegram outbox.
- `GET /v1/reports/dashboard`: latest daily/weekly và trend 30 report ngày, chỉ giữ generation mới nhất mỗi kỳ.
- `GET/PUT /v1/reports/configuration/schedules`: xem và cấu hình lịch.

UI nằm trong Meta → Ads Warehouse → Ads Reporting. Có cards Spend/Revenue/ROAS/CPA, coverage warning, bảng campaigns, trend ngày, gửi Telegram và lịch daily/weekly. Dashboard đọc PostgreSQL, không gọi Graph API.

## Kiểm thử và giới hạn nghiệm thu

- Backend kiểm tra aggregation đúng level/granularity, Decimal/NULL, daily/weekly windows, baseline coverage, idempotency, RBAC/isolation, dashboard generations, ngày chưa hoàn tất, missing data, Telegram outbox/status, timezone/weekday, scheduler dedup và revocation.
- Backend đạt **104 passed** trên `pao_test` và Redis DB 15; migration roundtrip, `alembic check`, 8 runtime tests, TypeScript, `pip check`, OpenAPI contracts và production build đều đạt.
- Browser acceptance đạt toàn bộ luồng Phase 9 bằng API giả lập tách biệt: daily report, coverage warning, dashboard, Telegram queue và report schedule. Ảnh bằng chứng: `.runtime/phase-9-reporting-browser.png`.
- Triển khai local đã sao lưu DB vào `.runtime/pre-phase-9-20260914-204247.dump` (118.035 bytes), kiểm tra được bằng `pg_restore --list`, giữ nguyên counts của 19 bảng cũ và migrate `0007 → 0008`.
- Sau chỉnh sửa kiểm tra Telegram peer bị thu hồi, API và worker đã được nạp lại; PID/start-time khớp hồ sơ runtime, `/ready` và web trả HTTP 200, worker cron hoạt động.
- Meta production vẫn `META_ENABLED=false`, warehouse có 0 rows. Vì vậy chưa thể đối chiếu report với Ads Manager hoặc gửi report Ads thật.
- Báo cáo giữ từng currency/account riêng. Không tổng hợp cross-currency. Attribution hiện kế thừa Phase 8: `7d_click + 1d_view`, report time `impression`.
- Phase 9 không dùng LLM. Điều này giữ báo cáo có thể lặp lại và tránh model tự tạo số liệu; phần phân tích sẽ được thiết kế ở Phase 10 sau nghiệm thu dữ liệu thật.
