# S3.2B — Xác minh danh tính bot cũ và bot mới

15/10/2026, `F:\PAO-ACOS`. **Phần identity registry/resolver: source_verified**.
Toàn S3.2B vẫn in_progress; scoped admission/outbox pins chưa triển khai, chưa
rollout primary hoặc nối worker. Kế thừa [store đã đạt](S32B-DURABLE-STORE-2026-10-15.vi.md),
không làm lại S3.1/A hoặc tạo checkpoint cạnh tranh ngoài B.

## Đã triển khai trong lượt này

- Migration candidate0062 thêm `telegram_bot_identities`: journal append-only,
  một bot ID/một connection, pin SME/owner/connection version và request MAC.
  Không lưu token, raw provider response hoặc tự backfill danh tính.
- `telegram_identity.verify_identity` là hàm hạ tầng nội bộ, chưa có route/UI.
  Chỉ owner của connection còn active và có role owner/admin trong SME được
  admitted; cần consent, PG lease thật theo bot ID, token capsule đúng scope và
  `getMe` trả đúng ID/is_bot. Token prefix/username không là bằng chứng danh tính.
- Bot cũ phải có mapping rõ ràng đã được owner chốt. Registry lưu danh tính
  mới riêng; `telegram_connections.bot_user_id` cũ vẫn NULL, version/history/
  peer/session/Brain/queued hoặc unknown delivery cũ không được repin/import.
- Dùng chung adapter metadata của kernel A: origin cố định, timeout/byte bound,
  không redirect/proxy/retry, không lộ token URL/log/payload. Registry không có
  method tùy chọn, chỉ gọi getMe; không nhận input tự khai `verified=true`.
- Native/legacy dùng chung ràng buộc bot identity. Trigger khóa theo actual bot
  ID ngăn claim mâu thuẫn giữa registry và lần tạo namespace native sau này.
  Disconnect/revoke không nhả identity để doanh nghiệp khác chiếm hoặc dùng lại
  history. Native staged đã tồn tại cũng giữ reservation, không tự chuyển chủ.
- Retry đúng request trả lại journal mà không gọi provider lần nữa. Đổi token,
  bot hoặc nội dung cùng request key bị chặn; một identity đã gắn không được
  thay bằng request mới. Muốn kiểm lại khóa hiện hành dùng metadata probe riêng,
  không coi journal cũ là xác minh khóa sau rotation.
- Resolver và store metadata hỗ trợ legacy đã xác minh; profile vẫn disabled.
  Runtime scope kiểm lại membership/user/connection và mapping/identity trước
  dùng token. Không có quyền nhân viên/công cụ/job/approval từ identity journal.

## Kiểm thử đã thực hiện

| Gate | Bằng chứng |
|---|---|
| Checkpoint trước code | `.runtime/checkpoints/p0-20261015T074105-3962de07/manifest.json`;1087source/0060/129tables/3archives, backup/restore đạt |
| Identity bước đầu |27passed/11.24s, `.runtime/s32b-identity.xml`; sau review thêm DB scope/revoke/lease/gates/concurrency |
| Tích hợp liên quan cuối |238passed/0failed/0error/0skip,93.13s;39identity+199store/kernel/Telegram/namespace/mapping/helpers/Channels/factory; `.runtime/s32b-identity-focused.xml` |
| Migration clone |0061→0062→0061→0062 và0060→0062→0060→0062; old rows exact, rollback schema equivalent kể cả body trigger0061;3lần alembic check đạt |
| Populated downgrade |Có identity journal thì từ chối downgrade0061; revision/data/schema clone giữ nguyên |
| Migration evidence | `.runtime/s32b-identity-migration.json`; retained dump `s32b-identity-pre-3c7ea4020bbb48e5925711c3f528c423.dump`; chỉ xóa clone do lượt thử tạo |
| Test DB | `pao_test`0062, alembic check không có upgrade operations |
| Primary và bản chạy |0060/129physical/không có candidate tables; API/ready/Web200,workerhealthy,Telegram bridge disabled,OpenAPI338 khớp file contract |
| Process |API13356/worker11032/Web18248 đúng timestamp UTC đã ghi; không restart/reload |
| Cấu hình | `.env` SHA256 `5672f74189bcef6c110d4c434e956d4f324598ee3901b88bbd56902c945fbea7`, không sửa |

Toàn bộ HTTP là fixture với token synthetic; chưa thử credential/provider thật.
Provider docs đã đọc trước code: [getMe](https://core.telegram.org/bots/api#getme),
[getUpdates](https://core.telegram.org/bots/api#getupdates). Đây là code/DB gates,
không phải nghiệm thu bot thật hoặc chứng minh luồng tin nhắn đã vận hành.

Các ca từ chối gồm provider ID sai/is_bot sai/echo secret/response quá lớn/
timeout/429/redirect/cancel; thiếu consent/lease, wrong SME/owner/version/bot,
người dùng bị khóa/rời SME/viewer/operator, legacy chưa mapping; registry UPDATE/
DELETE, native claim sau verified legacy/revoke và forged DB references. Bot A/B
cùng owner vẫn có scope khác. Membership/connection bị thu hồi chặn resolver và
retry cũ; journal vẫn được giữ. Metadata không tạo profile hoặc bật mapped peer.

Không chạy full backend/build/browser trong phần hạ tầng chưa nối API/worker và
không đổi UI; không quảng bá full1737 hoặc toàn bộ S3 đã xanh mới. Script clone
hiện hành là `check_s32b_identity_migration.py`, thay script0061 trước đó cho
candidate head0062; không sửa ngược bằng chứng test migration0061 đã đạt.

## Tiếp theo duy nhất — scoped admission và outbox trong cùng S3.2B

Đây là next-step của snapshot identity. Sau đó admission/outbox B đã
[source_verified368affected/25Node](S32B-SCOPED-EXECUTION-2026-10-15.vi.md);
thứ tự hiện hành do master sở hữu: S3.2C. Không làm lại B.

1. Tiếp nhận tin hợp lệ dùng Channels/admit_run/S2 accounting; receipt/admission/
   cursor cùng transaction, actor/session/Brain/grant đúng scope. Không dùng
   quarantine-only làm bằng chứng đã giao việc hoặc tự bật quyền từ /start.
2. Outbox pins theo bot/generation/actor/binding/session/Brain/đích; recheck khi
   dequeue và gửi, unknown không resend, retryable và cooldown theo bot/đích.

Sau B mới S3.2C worker epoch/polling/webhook/report, full integration/rollout và
exact restore; cập nhật restore checker cho candidate head khi tích hợp C.
S3.3 mới có thiết lập/liên kết nhân viên/phân quyền/thu hồi trên giao diện và
hướng dẫn tiếng Việt theo [yêu cầu](PRODUCT-SETTINGS-AND-TELEGRAM-ACCESS.vi.md).
