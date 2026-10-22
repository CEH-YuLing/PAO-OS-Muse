# S3.2B — Tiếp nhận công việc và outbox đúng phạm vi

15/10/2026, `F:\PAO-ACOS`. **S3.2B source_verified** (store/identity/admission/
outbox); chưa runtime/local accepted hoặc rollout primary. Tiếp theo S3.2C.
Tài liệu này chốt phần còn lại sau [store](S32B-DURABLE-STORE-2026-10-15.vi.md)
và [identity](S32B-VERIFIED-IDENTITY-2026-10-15.vi.md), không tạo phase B mới.

## Phạm vi triển khai

- Candidate0063 thêm trạng thái enabled có consent, cooldown theo bot, receipt
  liên kết inbound và context bất biến trên ChannelInbound/ChannelOutbox. Không
  tự bật profile, không backfill lịch sử hoặc nâng quyền từ dữ liệu staged.
- `telegram_scoped.control_profile` là hạ tầng nội bộ: enable phải xác nhận,
  getMe đúng credential hiện hành, owner/membership hiện hành, PG lease thật và
  generation CAS. Bật/tắt tăng generation và audit nguyên tử; rotation trở lại
  disabled. Chưa có route/UI và không tự khởi động transport.
- `ingest_update` chỉ dùng cho adapter tin cậy của bot đã xác minh. Tin riêng
  của numeric sender/chat ID phải khớp peer/binding được cấp; không tạo peer,
  membership hoặc liên kết nhân viên từ /start. Nhóm/callback/unknown/unlinked
  không có quyền điều khiển. Giao diện pairing còn ở S3.3.
- Dùng lại Channels/service.ingest và native admit_run: một nguồn Run/session/
  model snapshot/accounting/Brain/tool/approval. Không fork hàng đợi hoặc planner.
  Receipt + run/inbound hoặc quarantine + cursor cùng transaction; commit=False
  để dispatcher gốc phục hồi queued run, không enqueue vào hàng đợi thứ hai.
- Pin doanh nghiệp/connection/owner/version/bot/generation/binding version/
  actor/peer/chat/Brain revision/session policy. Worker dùng check_run gốc để
  kiểm lại scope; đổi JSON Run không thể repin receipt inbound bất biến.
- Thu hồi membership, đổi role, khóa tài khoản, thu hồi Brain grant hoặc peer,
  đổi session policy đều fence binding native liên quan bằng disable/version.
  Cấp lại quyền không tự hồi sinh việc cũ. Binding authority thay đổi có version
  đơn điệu ở DB; model selection vẫn được engine snapshot kiểm soát độc lập.
- `collect_results` tách scoped khỏi collector host cũ, dùng visibility/check_run
  và service.queue gốc. SQL loại kết quả đã có outbox trước limit để tránh kẹt
  ở100kết quả cũ. Mỗi phần tin dài có dedup/pin riêng, không cắt mất nội dung.
- `claim_delivery` persist sending/attempt trước khi C có thể gọi provider;
  `preflight_delivery` kiểm lại actor/Brain/binding/destination/content/policy,
  chỉ trả payload cho adapter nội bộ. Không dùng lại hàng đợi host hoặc context
  NULL từ giai đoạn staged. UI quản lý scoped vẫn bị chặn cho đến setup mới.
- `finish_delivery` chỉ nhận outcome đã phân loại từ adapter tin cậy: sent có
  receipt, unknown không resend, retryable chỉ khi xác nhận chưa gửi, tối đa3claim.
  Cooldown theo bot, kiểm lại sau claim; không chặn bot của SME khác. Mất tiến
  trình sau claim dùng reconciler gốc chuyển unknown, không đoán đã gửi/chưa gửi.

## Giới hạn phải giữ

Đây là primitive/code+DB test, chưa phải adapter gửi HTTP, polling/webhook,
worker epoch hoặc production acceptance. Các hàm nội bộ không được nhận identity,
claim, outcome hoặc transport từ model/plugin/browser không tin cậy. C phải nối
đúng adapter, giữ ownership và kiểm quyền sát lần gọi HTTP thật, kiểm concurrency/
lock ordering kể cả collector/retention/control, fairness, restart/revoke/rotate
và report/scheduler. Không gọi preflight một lần rồi gửi sau bằng quyền cũ.

User đã bị thu hồi có thể làm công việc cũ bị chặn; không hứa thu hồi được tin
provider đã nhận hoặc đã gửi. Outcome ghi nhận của fixture không là provider
receipt thật. Quota PAO không phải billing/quota còn lại của Telegram.

## Kiểm chứng

| Gate | Bằng chứng |
|---|---|
| Checkpoint trước code | `.runtime/checkpoints/p0-20261015T075528-444f1943/manifest.json`;1092source/0060/129tables/3archives |
| Intermediate focused |25passed/41.16s rồi39passed/61.40s; bổ sung2ca staged/cooldown trước vòng cuối |
| Hồi quy cuối |368passed/0fail/0error/0skip,245.12s;41scoped+238previous+89shared Engine/Brain/Voice/S13/resource; `.runtime/s32b-execution-focused.xml` |
| ARQ |2ca hàng đợi Redis thật đạt trên DB15, deny SME A sau revoke và SME B tiếp tục;2warning ARQ close deprecation lịch sử, không gọi zero-warning |
| Runtime/SSE/tenant frontend |25Node passed/0fail/0skip,277.896ms; gồm8runtime/SSE lõi và17tenant context/transport; không thay UI/contract |
| Test schema | `pao_test`0063, alembic check không còn upgrade operations |
| Migration cuối |0062→0063→0062→0063 và0060→0063→0060→0063;3alembic checks, old rows exact, rollback schema equivalent, populated downgrade refused, primary unchanged |
| Migration evidence | `.runtime/s32b-execution-migration.json`; backup `s32b-execution-pre-3f10b96fbfb14ca3925c232da0cb157a.dump`; chỉ xóa clone do script tạo |
| Primary/bản chạy |0060/129physical; API/ready/Web200,workerhealthy,Telegram bridge disabled; không restart hoặc apply0061–0063 |
| Cấu hình thật | `.env` SHA256 `5672f74189bcef6c110d4c434e956d4f324598ee3901b88bbd56902c945fbea7`, không sửa |

Toàn bộ token/HTTP metadata/LLM/outcome gửi trong ca mới đều synthetic/fixture.
Kiểm thử dùng `pao_test`, Redis DB15 process-only ở vòng cuối; không sửa `.env`.
Chưa chạy full backend/build/browser hoặc nạp candidate vào API/worker.
Nguồn provider đã đọc trước code:
[getUpdates](https://core.telegram.org/bots/api#getupdates),
[sendMessage](https://core.telegram.org/bots/api#sendmessage).

## Sửa lỗi trong quá trình kiểm chứng

- Sửa cú pháp CASE của trigger evidence trước khi migration clone đạt.
- Sửa fixture đọc `Run.error` thành `Run.error_code`; không nới guard thu hồi.
- Candidate test DB được xóa fixture và down/up khi thêm authority triggers;
  không xóa database thật. Fixture có thể tạo lại từ tests. Downgrade vẫn giữ
  guard lịch sử; DROP IF EXISTS cho các trigger bổ sung hỗ trợ candidate cũ rỗng.
- Vòng rộng đầu355pass/11fail:9ca namespace storage-only cần giữ queue context
  NULL khi scoped flag tắt và trả pending như cũ, nhưng sender mới không được
  adopt chúng.2ca ARQ thật yêu cầu Redis15; sửa process env, không sửa safety test.
  Không dùng kết quả vòng đó để tuyên bố đã xanh.

## Handoff — S3.2B source_verified, tiếp theo duy nhất S3.2C

S3.2C: nối adapter/worker/webhook/polling/report với primitive đã có, kiểm đầy đủ
native adapter fixtures/restart/revoke/rotation/no-resend, runtime/SSE và full
backend ở điểm release; checkpoint/restore trước migration primary, bổ sung
restore checker hỗ trợ candidate0063, xác minh live contract/current binding.
S3.3 mới có giao diện thiết lập, pairing/team grants và hướng dẫn tiếng Việt theo
[yêu cầu đã chốt](PRODUCT-SETTINGS-AND-TELEGRAM-ACCESS.vi.md). Không mở M/S khác.
