# Phase 14 — Creative Intelligence

Ngày triển khai: 15/09/2026. Phạm vi theo mục 50–55 và 140 của master spec: creative metadata, creative performance, fatigue đa tín hiệu, creative learning và strategist brief. Phase này chỉ đọc warehouse; không gọi LLM, không gọi Meta và không tạo/sửa/launch quảng cáo.

## Luồng dữ liệu

`ad_entities(ad).creative_id` liên kết creative với daily `ad_metrics(level=ad)`. Mỗi lần phân tích dùng hai cửa sổ liên tiếp: current và baseline. Kết quả lưu theo lineage vào sáu bảng:

- `creative_assets`: creative Meta đã quan sát và nguồn sync;
- `creative_metadata`: product, brand, market, language, format, duration, hook, angle, offer, CTA, creator và landing page; cập nhật có optimistic version;
- `creative_analysis_runs`: request idempotency, cấu hình guardrail, khoảng ngày và source freshness;
- `creative_performance`: current/baseline metrics theo creative;
- `creative_features`: fatigue status/score/signals và refresh brief;
- `creative_learnings`: Advertising Memory có cấu trúc theo hook, angle, format, duration và market.

Reach không được cộng giữa nhiều ad. Frequency chỉ xuất hiện khi creative gắn với đúng một ad; creative tái sử dụng vẫn phân tích được CTR/CPA/CPM/impressions nhưng frequency là `null`.

## Fatigue guardrail

Trạng thái `fatigued` cần đủ dữ liệu ở cả hai cửa sổ, có suy giảm hiệu suất (`CTR down` hoặc `CPA up`), có saturation (`frequency up` hoặc impression threshold), và ít nhất ba tín hiệu độc lập trong: frequency up, CTR down, CPA up, CPM stable, creative age, impression saturation. Frequency tăng một mình không đủ. Mẫu thấp trả `insufficient`; dấu hiệu sớm trả `watch`.

Ngưỡng mặc định: current 3 ngày, baseline 3 ngày, 1.000 impressions/cửa sổ, tuổi 7 ngày, saturation 10.000 impressions, frequency +20%, CTR -20%, CPA +20%, CPM ổn định trong ±15%. API chấp nhận override có giới hạn và lưu nguyên cấu hình trong run.

Khi fatigue đủ điều kiện, `strategy_brief` trả năm hướng hook, ba hướng angle, hai CTA, khuyến nghị duration/format và yêu cầu thử một biến mỗi lần. Đây là brief có cấu trúc để con người biên tập; pipeline tạo asset, user approval, launch và experiment chưa thuộc Phase 14.

Creative age hiện là **tuổi quan sát trong warehouse**, tính từ lần PAO nhìn thấy creative đầu tiên. Meta sync hiện chỉ lấy creative ID/name, nên hệ thống không tuyên bố đây là ngày creative được tạo trên Meta. Khi connection version thay đổi, metadata của cùng connection/account/creative ID được sao chép sang asset generation mới để không mất nhãn thủ công.

## Learning

Learning chỉ sinh khi ít nhất hai giá trị metadata trong cùng dimension đều đạt minimum impressions. Nếu có ít nhất hai nhóm có purchase, hệ thống xếp hạng CPA; nếu chưa đủ conversion, hệ thống dùng CTR và ghi rõ metric/evidence. Statement không được tạo khi thiếu nhóm đối chứng.

## API và UI

- `POST /v1/creatives/analyze`
- `GET /v1/creatives/dashboard`
- `PUT /v1/creatives/assets/{asset_id}/metadata`

Panel **Creative Intelligence · Phase 14** hiển thị creative health, current metrics, metadata editor, fatigue brief và Advertising Memory learnings. Owner/admin được phân tích và sửa metadata; quyền đọc giữ workspace scope.

## Giới hạn nghiệm thu

Kiểm thử local dùng dữ liệu Meta giả lập ở ad level. Production chưa có Meta connection hoặc warehouse row nên các bảng Phase 14 khởi tạo trống. Cần kết nối Meta read-only, sync tối thiểu sáu ngày daily ad data, gắn metadata cho ít nhất hai creative và đối chiếu Ads Manager trước khi dùng learning để ra quyết định. Live Meta Write và cả hai Autopilot gate tiếp tục OFF.

## Bằng chứng triển khai

- Migration `0013`; `alembic check` sạch và toàn bộ **138 backend tests** đạt.
- OpenAPI **60 paths**, TypeScript contracts, Next production build và **8 runtime tests** đạt.
- Browser acceptance đạt toàn bộ luồng cũ và Phase 14: ad performance, `FATIGUED`, brief 5 hooks/3 angles/2 CTA, nhãn read-only, không có browser error.
- Backup cuối `.runtime/pre-phase-14-20260915-171135.dump` (**196.215 bytes**) đọc được bằng `pg_restore --list`; counts 31 bảng cũ trước/sau giống nhau.
- Post-deploy: DB `0013`, API/Web và 8 static assets HTTP 200; sáu bảng Phase 14 trống do chưa có Meta connection; không có provider write.
- `.runtime/phase-14-migration.json`, `.runtime/phase-14-health.json`, `.runtime/phase-14-creative-intelligence-browser.png`.
