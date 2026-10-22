# M2 — Attribution snapshot chỉ đọc

Ngày 05/10/2026; target `F:\PAO-ACOS`. Không nối credential thật hoặc thay
dữ liệu nghiệp vụ. Chưa kết luận toàn bộ M2/M3 hoàn tất.

## Phạm vi triển khai

- Tool business.attribution.read vào durable Gateway, SELECT-only, RBAC,
  statement timeout 8s, Gateway timeout 20s và executable binding đã có.
- Skill investigate-ads-drop tăng manifest **1.0.0 → 1.1.0**: thêm allowed tool.
- API riêng: POST `/v1/skills/investigate-ads-drop/attribution-preview`, cần login
  và body workspace_id/input (platform, account_id, start_date, end_date).
  Transaction READ ONLY, preview timeout 10s; không gọi analyze/ingest/acknowledge.
- Chỉ đọc snapshot Meta mới nhất khớp chính xác user/workspace/account/kỳ và
  phiên bản connection đang connected, chưa expired. Google trả thiếu dữ liệu.
- Tối đa 49 metrics + một root source reference; 50 nguồn hiện bật. Không xuất
  arbitrary summary/evidence, tên campaign, PII hoặc provider credentials.
- Không cộng metrics/currencies. Lưu nguồn từng metric; đánh dấu cap, stale,
  thiếu snapshot, summary count không khớp và unattributed coverage.
- Nguồn orders thiếu/disabled/sai scope/currency/thay đổi sau snapshot: doanh
  thu/count orders trả null, không diễn giải 0 là doanh thu thật.
- Luôn insufficient_data, verified_business_revenue false. Ba trường khác nhau:
  platform_reported_revenue; attributed_paid_order_revenue; doanh thu doanh
  nghiệp xác minh (chưa có). Không gọi giá trị phân bổ là tổng doanh thu thật.

**Checkpoint API này chưa đổi UI hoặc SKILL_TOOLS command plan.** UI đã có
[checkpoint tiếp theo](M2-ATTRIBUTION-UI-2026-10-05.vi.md). Ba lệnh Chief vẫn gọi hai tools
như trước. Wrapper mới dùng qua explicit API preview hoặc Tool Gateway; chưa
tự tạo tool thứ ba hoặc nới resource guard. Không tạo snapshot phân tích mới.

## Giới hạn dữ liệu hiện có

Attribution analyst cũ dùng tổng deterministic campaign_id/UTM/lead_link và
loại orders chưa phân bổ. Một số platform metrics bị coalesce null thành zero.
Snapshot không pin lịch sử version từng source hoặc chứng minh ingest đã đối
soát với hệ thống doanh nghiệp. Wrapper không sửa analyst hay chứng nhận số liệu.
Cảnh báo này luôn giữ trong result ngay cả khi cap missing reasons.

Nguồn được kiểm scope/trạng thái hiện tại, không thể xác minh toàn bộ lịch sử
source tại lúc tạo snapshot. Không có live GA4/CRM/orders ingestion mới trong
checkpoint này. Source references là record IDs nội bộ, không external truth.

## Vận hành và bước kế tiếp

Kiểm chứng lượt cuối:

- Backend **265/265**, 131.37 giây, database pao_test riêng. Thêm 11 ca kiểm
  auth/scope/input, Google/missing snapshot, nguồn orders không hợp lệ, read-only
  Gateway không gọi provider, bounded output/currency và latest exact-period.
- Runtime/SSE **8/8**, TypeScript noEmit/incremental false đạt.
- Live explicit attribution API preview đạt với thiếu dữ liệu local; không
  seed fixture nghiệp vụ vào database local. Dữ liệu có số kiểm trên pao_test.
- Ba lệnh Chief qua API → ARQ vẫn đạt, mỗi lệnh hai tools, result thiếu dữ liệu.
- Live catalog/preflight/ba previews cũ trên desktop/mobile đạt; browser mock
  regression 12 màn hình đạt. API /ready và Web /skills HTTP 200.
- OpenAPI/TypeScript contracts đã generate lại. Không chạy lại production build;
  không sửa UI trong checkpoint này.

Live demo runs:

- Daily: 2f345561-d37a-46a9-8a91-4de6f2f6bd11.
- Ads: 77f50d01-00c6-4eaf-8d55-a4d106a615ae.
- Creative: 78927a19-f2bd-4c68-9277-d1e832bc970b.

Backend code đổi nên executable digest đổi; không tự gắn binding mới vào job
cũ. API/worker được restart sau idle check 0 jobs. Smoke memory tắt, chỉ ghi
hội thoại/run/audit demo, không Ads/email/Telegram thật. Database không đổi
schema, vẫn revision 0023; source F:\Apex\apex không sửa.

Bước UI tiếp theo đã đạt checkpoint liên kết phía trên. Không tự nới command
budget hoặc công nhận
business correctness. Toàn stack ARQ/Redis wall-clock, artifact replay và token
budget skill LLM vẫn còn giới hạn đã ghi trong các checkpoint M2 trước.
