# Phase 8 — Ads Warehouse

Ngày: 14/09/2026. Phạm vi: mục 32–36, 66 và 134 trong master spec. Triển khai kho dữ liệu chuẩn hóa, hourly/daily/historical và lịch đồng bộ cấu hình được. Không triển khai báo cáo Telegram, anomaly detection, recommendations hoặc ghi quảng cáo của các phase sau.

## Kiến trúc

Tiếp tục dùng PostgreSQL và worker ARQ `max_jobs=1`. Không thêm database/service hay model AI. Connector Meta đọc dữ liệu → kiểm tra/chuẩn hóa trong bộ nhớ có giới hạn → ghi một transaction → đánh dấu job hoàn tất. Worker kiểm tra lại user, role và version kết nối trước khi công bố dữ liệu.

Migration `0007` bổ sung:

| Bảng | Nội dung |
|---|---|
| `ad_entities` | Account, campaign, adset, ad và creative; ID, tên, trạng thái, parent/creative ID, currency/timezone và job nguồn. |
| `ad_metrics` | Cột số liệu có kiểu dữ liệu rõ ràng, cấp campaign/adset/ad, ngày, giờ, tiền tệ, múi giờ, attribution, job nguồn và thời điểm cập nhật. |
| `ad_sync_schedules` | Lịch từng account/granularity, chu kỳ, số ngày đọc lại, lần chạy kế tiếp, trạng thái bật/tắt. |
| `meta_sync_jobs` | Thêm `warehouse` và `granularity`; các job Phase 7 cũ mặc định không phải warehouse. |

Thay vì tạo sáu bảng metric gần giống nhau, dùng một bảng có `level` và `granularity`, unique key và index theo phạm vi/ngày. Đây là lựa chọn triển khai normalized schema; dữ liệu campaign/adset/ad và hourly/daily vẫn tách biệt khi truy vấn. Metadata entity dùng discriminator `kind`, không dùng JSON làm mô hình chính. Connector Google/TikTok chưa được triển khai; `platform` dành chỗ cho bước mở rộng sau.

Khóa số liệu gồm connection + version + account + level + entity + day + hour + granularity + attribution. Hai user có cùng ad account vẫn không xem kho của nhau. Ngắt kết nối ẩn dữ liệu cũ; kết nối lại tăng version, không tự trộn dữ liệu từ quyền truy cập cũ.

## Ý nghĩa số liệu

- Spend, doanh thu, conversions và chỉ số dẫn xuất dùng `Numeric(24,6)`/Decimal, không dùng float tiền tệ. Counts dùng BigInteger. API trả Decimal dạng chuỗi để không mất chính xác trong JavaScript.
- Các cột: spend, impressions, reach, frequency, clicks, link_clicks, CTR, CPC, CPM, leads, add_to_cart, checkout, purchase, revenue, CPL, CPA, ROAS.
- `NULL` nghĩa là chưa có/không được Meta cung cấp; không tự chuyển sự kiện bị thiếu thành 0. Mẫu số bằng 0 hoặc thiếu → chỉ số dẫn xuất NULL.
- CTR = clicks/impressions × 100; CPC = spend/clicks; CPM = spend/impressions × 1000. CPL dùng lead, CPA dùng purchase; ROAS = purchase revenue/spend.
- Các action alias có thể chồng lấp. Chọn alias tổng quát trước, rồi alias pixel; không cộng purchase với pixel purchase/omni purchase. Không cộng tổng hợp các conversion event khác loại.
- Attribution cố định cho phiên bản đầu: 7 ngày click + 1 ngày view, `action_report_time=impression`, lưu nhãn trong từng metric. Chưa hỗ trợ cấu hình nhiều attribution profile.
- Lấy Insights trực tiếp từ Meta cho từng level. Không cộng reach từ ad lên campaign, không cộng hourly thành daily. Hourly không yêu cầu reach/frequency vì không phải chỉ số có thể cộng hợp theo giờ.
- Ngày và giờ là bucket của múi giờ ad account, không giả định UTC. Daily dùng `hour=-1`; hourly dùng 0–23. Với DST, đây là bucket giờ local Meta đã tổng hợp, không phải từng UTC instant riêng biệt. Currency giữ nguyên của account, không chuyển đổi hoặc cộng nhiều loại tiền.

## Đồng bộ và lịch sử

Trong bảng **Meta Ads · Chỉ đọc**, chọn account đã đồng bộ, mở **Kho dữ liệu quảng cáo · Phase 8**:

1. Chọn ngày/giờ và khoảng ngày. Bấm **Đồng bộ vào kho**; mỗi job tối đa 31 ngày. Để backfill dài hơn, chạy các khoảng liên tiếp sau khi lượt trước hoàn tất.
2. Theo dõi trạng thái job ở bảng Meta. Sau `completed`, bấm **Đọc kho dữ liệu**; thao tác đọc này chỉ truy vấn PostgreSQL, không gọi Meta.
3. Chọn campaign/adset/ad để xem đúng cấp dữ liệu. “—” là NULL; bảng hiển thị currency và múi giờ.
4. Sau khi đồng bộ thủ công thành công, có thể bật lịch. Chu kỳ 15–10.080 phút, đọc lại 1–31 ngày tính theo ngày hiện tại ở múi giờ account. Daily/hourly có lịch riêng; mặc định đều tắt. Ví dụ account hoạt động: 30 phút/3 ngày; ít hoạt động: 1.440 phút/3 ngày. Không có tự phân loại active/inactive ở phase này.

Worker xử lý từng lượt, mỗi connection có tối đa một job queued/running. Lịch quá hạn tạo một job hiện tại, không tạo hàng loạt lượt đã bỏ lỡ khi máy ngủ. Request key chống tạo trùng. Hết quyền/connection version đổi → lịch tự tắt khi scheduler kiểm tra.

Daily fetch từng cửa sổ tối đa 7 ngày; hourly từng ngày. Giới hạn chung vẫn là timeout 300 giây, 20 trang/endpoint, 2 MB/response, khoảng 10.000 bản ghi và 16 MB payload/lượt. Job vượt giới hạn báo lỗi để người dùng giảm phạm vi. Không có âm thầm bỏ trang hoặc lưu một phần.

Khi đồng bộ lại, thay thế chính xác phạm vi ngày/granularity/attribution đã tải đầy đủ trong một transaction. Số liệu Meta được điều chỉnh lại sẽ thay số cũ; dòng biến mất khỏi kết quả mới cũng được loại khỏi phạm vi tương ứng. Phạm vi khác và granularity khác được giữ nguyên. Lỗi fetch/validate/publish không xóa bản dữ liệu hoàn chỉnh trước đó. Không tự chuyển các snapshot Phase 7 cũ thành dữ liệu warehouse vì thiếu metadata/grain/attribution cần thiết.

## API

- `POST /v1/integrations/meta/sync`: `kind=historical`, `warehouse=true`, `granularity=daily|hourly` cùng workspace/account/ngày/request_key.
- `GET /v1/warehouse/metrics`: lọc workspace/account/ngày/level/granularity, phân trang 50, tối đa 366 ngày/query.
- `GET /v1/warehouse/entities`: đọc normalized entities theo account/kind, phân trang 50.
- `GET /v1/warehouse/schedules`, `PUT /v1/warehouse/schedules`: xem/đổi lịch. Owner/admin được sửa; truy vấn luôn giới hạn kết nối của user hiện tại.

OpenAPI và TypeScript contracts đã cập nhật. Phần dữ liệu chính không đọc từ raw snapshots. Phase 7 vẫn giữ API snapshot phục vụ kiểm tra dữ liệu nguồn.

## Kiểm chứng và triển khai

- 96 backend tests đạt; bao gồm 15 trường hợp mới về số thập phân, NULL/zero, alias, scope/currency/date, request hourly, restatement, atomic failure, daily/hourly isolation và scheduler idempotency/revocation.
- TypeScript và `pip check` đạt. `tzdata==2026.4` được thêm để ZoneInfo hoạt động trên Windows.
- Migration downgrade → upgrade → `alembic check` trên `pao_test` đạt; 96 backend tests đạt lại sau roundtrip. 8 runtime tests đạt.
- Production build sạch và browser acceptance đạt: bảng Decimal/NULL, đồng bộ warehouse, bật/tắt lịch; regression Meta/Telegram/agents/tools/Memory/SSE/logout đều đạt, không có browser errors. Ảnh `.runtime/phase-8-warehouse-browser.png`.
- Đã triển khai local tuần tự `0005 → 0006 → 0007`. Backup `.runtime/pre-phase-8-20260914-155418.dump` (97.335 bytes), đã kiểm tra mục lục bằng pg_restore. 12 bảng cũ được đối chiếu số bản ghi trước/sau migration, không thay đổi; gồm 6 sessions, 37 messages, 19 runs và 21 agent runs tại thời điểm triển khai.
- API/worker/web/Telegram đã khởi động lại. `/ready`, trang 3100 và 8 assets trả HTTP 200; API warehouse metrics/schedules có xác thực trả 200. Meta vẫn chưa cấu hình và lịch chưa bật. Bằng chứng `.runtime/phase-8-migration.json`, `.runtime/phase-8-health.json`.
- Build lần đầu kẹt tại bước cleanup của Next.js. Đã lưu artifact cũ trong `apps/web/.pao-next-previous-*` (Git/TypeScript bỏ qua), rồi build sạch; web chính hiện đã nạp bản mới, không còn lệch asset.
- Cấu hình Meta thật còn thiếu, nên chưa nghiệm thu với account thật. Những tổ hợp trường/hourly không được Meta App/API version hỗ trợ sẽ báo lỗi; không giả lập thành dữ liệu thật.

Quy trình local: build khi web đã dừng; chạy `scripts/deploy_local_phase8.ps1`. Script kiểm tra idle, xác minh PID/start time, sao lưu DB, áp dụng `0006` nếu còn thiếu rồi `0007`, kiểm tra số bản ghi cũ và khởi động lại dịch vụ. Không xóa volume hoặc chạy test trên DB chính.

Nguồn đối chiếu: [Meta SDK AdsInsights](https://github.com/facebook/facebook-python-business-sdk/blob/main/facebook_business/adobjects/adsinsights.py), [bộ yêu cầu Marketing API chính thức của Meta](https://www.postman.com/meta/facebook-marketing-api/documentation/0zr4mes/facebook-marketing-api-mapi). Giới hạn vận hành và semantics chuẩn hóa nêu trên là thiết kế PAO, không phải cam kết của Meta.
