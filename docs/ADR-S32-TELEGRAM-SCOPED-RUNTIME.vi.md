# ADR-S32 — Runtime Telegram theo connection, không fork agent

15/10/2026. Target `F:\PAO-ACOS`. S3.1A+B đã local_accepted; S3.2 triển khai
đúng ba checkpoint A/B/C dưới đây, không mở thêm roadmap P/M hoặc hỏi lại SME design.
S3.3 mới có Settings/token/getMe/destination/activation cho người dùng.

**Cập nhật nghiệm thu tổng:** toàn S3 local_accepted, primary0064/live349;
C và Settings/team có code/fixture/browser,109Node/build21 đạt. Backend2078ca
có kết quả cuối đạt sau sửa allowlist script phục hồi và27retry, không full
rerun; API/ready/Web200/current binding/replay3/3 khớp. Bot thật vẫn tắt.
[Báo cáo mới](S3-INTEGRATION-2026-10-15.vi.md). Các trạng thái A/B/C
bên dưới là lịch sử các checkpoint, không phải lệnh dispatch lại.

Yêu cầu bổ sung15/10: [quyền Telegram và Cài đặt tiếng Việt](PRODUCT-SETTINGS-AND-TELEGRAM-ACCESS.vi.md).
Kernel kiểm owner/admin cho thao tác metadata không thay thế quyền từng nhân
viên. B/C phải dùng actor/membership/grant/Brain hiện hành, tách quyền duyệt và
đích nhận; S3.3 mới cung cấp luồng liên kết người dùng và hướng dẫn tiếng Việt.
Đặc tả không cấp quyền mới, không chứng minh pairing/runtime đã hoạt động.

## Nguồn provider đã đọc trước code

Đối chiếu15/10: [Bot API](https://core.telegram.org/bots/api),
[getUpdates](https://core.telegram.org/bots/api#getupdates),
[setWebhook](https://core.telegram.org/bots/api#setwebhook),
[FAQ](https://core.telegram.org/bots/faq). Trang chính ghi10.3,24/08/2026.
Polling/webhook loại trừ nhau; gọi getUpdates với offset cao hơn xác nhận update.
Webhook retry được và có secret header; token nằm trong đường dẫn gọi Bot API.
Thiết kế dưới đây là quyết định PAO, không là nghiệm thu bot thật.

## A — Scope/credential/lease/metadata kernel

`telegram_runtime.py` không có router, daemon hoặc credential store. Không được
import/nối vào bridge legacy để tự thay transport. Flag scoped mới mặc định false;
host Telegram bật thì scoped probe bị chặn. Không đọc token host làm fallback.

- RuntimePin bất biến chứa SME/connection/owner/version/bot ID. Native connection
  hiện tại phải staged và khớp toàn bộ pin; owner còn active, role owner/admin.
  Legacy chưa có bot identity thì từ chối; không đoán từ `.env` hoặc peer/chat.
- Credential capsule Fernet gồm purpose và toàn bộ pin. Không lưu plaintext hoặc
  capsule ở database/browser tại A. Capsule chỉ là primitive cho server-side store
  tương lai, không là getMe verification, consent, activation hoặc grant công cụ.
- Một PostgreSQL session advisory lock theo bot ID thật cho **mỗi thao tác bounded**;
  không dùng token/SME làm key, không giữ connection thường trực cho mọi SME.
  Probe kiểm PID và pg_locks thật trước/sau đọc credential. Lease hết hiệu lực khi
  context đóng/disconnect; không âm thầm reconnect bằng quyền cũ. Đây chưa phải
  ownership/epoch toàn vòng worker, phần đó ở B/C.
- Owner row locks theo member→user→connection để không đảo thứ tự control/revoke.
  Metadata request đã admitted hoàn tất trước revoke; request sau revoke bị chặn.
- Chỉ getMe/getWebhookInfo. getUpdates/sendMessage/callback/set/deleteWebhook
  bị từ chối trước loader/network. Mỗi request origin cố định, proxy/redirect/retry
  tắt, byte/time bound; getMe phải trả đúng ID/is_bot. Chỉ project metadata allowlist,
  không trả raw URL/error text hoặc nội dung provider.
- HTTPX thấy URL đã che token; diagnostic HTTPCore bị suppress trong context
  của đúng request đó, không đổi level toàn cục cho tenant khác. Credential echo
  trong JSON bị từ chối bằng guard hiện có. Loader/transport là code hạ tầng tin cậy,
  tuyệt đối không nhận callable/URL từ model hoặc plugin không tin cậy.

Không nối kernel vào API/worker thật tại A. Gate A là source_verified bằng native
DB và HTTP fixture; không gọi là full runtime/live acceptance.

## B — Persisted profile, generation, cursor và ingress/outbox

Cập nhật15/10: phần disabled store/generation/audit/quarantine/cursor đã
source_verified,199focused/56store; candidate0061 chỉ chạy trên clone/pao_test,
primary vẫn0060. [Evidence và phần B còn mở](S32B-DURABLE-STORE-2026-10-15.vi.md).
Identity registry/resolver native/legacy nay cũng source_verified theo
[evidence mới](S32B-VERIFIED-IDENTITY-2026-10-15.vi.md):238focused/39identity,
candidate0062 clone roundtrips/schema equivalence, primary0060 không đổi.
Không sửa nghĩa gate A lịch sử: legacy chỉ được dùng metadata sau getMe và
journal/mapping rõ; không host fallback/repin namespace hoặc history. Scoped
admission/outbox pins nay cũng source_verified trong
[B execution evidence](S32B-SCOPED-EXECUTION-2026-10-15.vi.md):368affected/41scoped,
25Node, candidate0063 clone roundtrips. Internal enable có getMe/consent/generation
audit, không tự activation UI. Worker/actual HTTP wiring còn C; không coi fixture
outcome là gửi thật. Tiếp theo duy nhất C, không làm lại primitive A/B.

1. Profile/token envelope riêng connection với credential generation/version,
   trạng thái disabled mặc định; audit append-only/consent-CAS và revoke monotonic.
2. Bot identity registry duy nhất xuyên native/legacy, không repin bot_user_id hoặc
   history cũ. Legacy bot ID phải được xác minh/ràng buộc rõ, không chỉ token prefix.
3. Cursor durable theo connection/generation. Chỉ tiến offset sau transaction
   receipt/admission/quarantine; unknown/non-message cũng không tạo vòng lặp vô hạn.
4. Scoped ingest dùng lại Channels/admit_run/Brain/private context/S2 accounting,
   không đưa authority mới vào legacy fallback. Actor/destination/session/Brain và
   credential generation kiểm lại tại dequeue; persisted pins/dedup đúng connection.
5. Scoped outbox giữ queued/sending/sent/unknown/retryable tách biệt; không claim
   hoặc cancel hàng đợi legacy sau mapping. Mất ACK không phát lại; cooldown429
   thuộc đúng bot/đích, không coi quota PAO là quota còn lại tại Telegram.
6. Clone migration up/down/up và guard populated downgrade trước primary rollout.
   S3.1 history/private Brain giữ nguyên. Token store và activation chưa mở cho UI.

## C — Bridge/webhook/scheduler và nghiệm thu tích hợp

Tiến độ15/10: [polling adapter](S32C-POLLING-ADAPTER-2026-10-15.vi.md) đã nối HTTP
fixture vào native admission/cursor, bounded turn lease theo bot. Sau đó đã nối
[sender authority-at-invocation source_verified](S32C-SENDER-ADAPTER-2026-10-15.vi.md),509affected/61sender+25Node.
Sau đó nối [worker riêng source_verified](S32C-WORKER-2026-10-15.vi.md),26worker/535affected+25Node đạt.
Chưa chạy daemon thật/webhook/report hoặc full release; không đổi gate A/B lịch sử.
Tiếp theo: webhook/mode/report/oversize/idle-week/concurrency và release C còn lại.

1. Worker epoch/lease cho polling hoặc webhook, đúng một owner mỗi bot; mode
   conflict fail closed. Webhook path theo connection, secret riêng/HMAC-safe,
   body bound/no reflection, không dùng public URL chứa bot token.
2. Loop gọi đúng resolver/profile; offset chỉ ACK sau durable transaction. Native
   collect/report/scheduler sender nhận đúng connection, không reuse host token.
3. Restart/disconnect/cancel/revoke/rotate/no-resend và hai bot trùng chat/user/
   update ID/dedup chạy qua actual adapter với HTTP fixture. Fair bounded dispatch
   giữa SME; không chiếm mọi PG slot hoặc bypass S2 quota/grants.
4. Sau A+B+C code ổn định mới chạy full backend/ARQ, browser affected, checkpoint,
   additive migration và runtime rollout/live contract/binding/exact restore.
   Không lặp full release mỗi primitive chưa được nối vào runtime.

Khi chưa có setup được duyệt, cả host/scoped transport giữ tắt. S3.3 sau đó mới
thêm UI nhập token/password, getMe consent, destination/team/Brain/status/rotate/
disconnect. Bot thật, tin thử thật, public HTTPS và production reboot là gate riêng.
