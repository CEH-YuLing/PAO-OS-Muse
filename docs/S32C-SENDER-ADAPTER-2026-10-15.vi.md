# S3.2C — Bộ gửi kết quả Telegram có khóa bảo vệ quyền

15/10/2026, `F:\PAO-ACOS`. Một phần của C, không mở milestone/roadmap mới.
Trạng thái: **sender adapter source_verified**; chưa nghiệm thu toàn C hoặc
cập nhật bản đang chạy.
Đây là evidence tại thời điểm đóng sender. Worker được nối sau đó tại
[worker evidence](S32C-WORKER-2026-10-15.vi.md); handoff phía cuối là snapshot
lịch sử. Theo master/register để tiếp tục, không triển khai lại sender.

## Những gì đã nối trong mã nguồn

`telegram_sender.send_once(pin, outbox_id)` đọc đúng profile/credential đã xác
minh và dùng lại Channels outbox/claim/outcome writer của B. Không nhận text,
chat ID, token, callback hoặc outcome từ browser/model. Chưa có route/daemon/job
registration và không nối vào bridge host. Không sửa frontend/schema/migration.

1. Kiểm flag scoped/host/Channels, owner/identity/profile; lấy lease PostgreSQL
   theo bot ID thật cho toàn turn. Không host-token fallback hoặc implicit enable.
2. Lấy khóa các dòng liên quan và kiểm quyền trước claim; lưu `sending`/attempt
   bền vững **trước** khi gọi provider. Không nhận lại row sending/unknown/sent,
   staged không pin hoặc hàng đợi connection khác.
3. Transaction gửi lấy lại đầy đủ khóa, kiểm generation/actor/Brain/session/
   destination/binding/body/result trước HTTP. Khóa được giữ đến khi ghi outcome
   và commit, không gọi preflight rồi gửi payload rời bằng quyền đã cũ.
4. Gọi đúng `sendMessage`, POST/origin/body cố định; không proxy/redirect/retry/
   paid broadcast/parse mode/đổi đích tự động. Mỗi HTTP10giây, transaction20giây,
   ngân sách thực thi40giây (chưa tính dọn lease theo kernel), response64KiB;
   chỉ một PGslot mỗi turn. Kết quả ra ngoài chỉ
   là disposition, không body/token/URL/description của provider.

## Quyền và khóa — phạm vi chứng minh

Owner member→user→connection theo kernel hiện có, trước khi giữ dòng delivery.
Sau ranh giới owner, mọi khóa bổ sung dùng **NOWAIT**, gồm profile, outbox,
binding, actor member/user, peer, session, Brain/grant, Run/inbound và evidence.
Nếu đường revoke/retention/worker đã giữ khóa, sender bỏ transaction trước HTTP,
không chờ theo thứ tự đảo nhau. Không table lock chặn mọi doanh nghiệp.

Citation có khóa RunKnowledge/chunk/version/source/parse job và file hoặc note/
note version, rồi dùng lại kiểm visibility/integrity có sẵn. Không tự cấp grant
hoặc đưa nội dung nguồn sang model/HTTP khác. Evidence list giới hạn4 theo native
chat retrieval; input vượt giới hạn bị chặn, không tự cắt bỏ citation.

- Thu hồi đã commit trước invocation: không gửi. Grant/Brain/source/destination
  thay đổi không tự repin nội dung cũ. Kênh bị tắt cũng kiểm lại sau claim.
- Request HTTP đã được cho phép dưới khóa có thể hoàn tất trước transaction
  thu hồi đang chờ; lần tiếp theo bị chặn. Không hứa thu hồi tin provider đã nhận.
- Contention trước claim: giữ queued/0attempt. Contention sau claim nhưng chưa
  HTTP: chỉ lúc đã xác nhận chưa gọi provider mới dùng shared retryable writer,
  delay1giây và giới hạn3claim; không retry HTTP trong cùng turn. Error code
  `provider_retryable` là tên lịch sử của shared writer, không chứng minh provider
  đã nhận request trong trường hợp contention local này.
- Đây là lock gate của sender. Toàn bộ thứ tự worker/collector/retention/control
  và scheduler fairness vẫn phải audit/tích hợp tại phần còn lại của C.

## Outcome — không đoán rồi gửi lại

| Bằng chứng | Hành vi PAO |
|---|---|
| HTTP200/ok=true, message ID hợp lệ, bot/chat/private/text khớp | sent + remote receipt |
| HTTP429/ok=false/error_code429, retry_after số nguyên1–3600 | queued/failed theo tối đa3claim; cooldown riêng bot |
| HTTP400/401/403/404 và body xác nhận từ chối đúng code | failed/provider_rejected; không retry hoặc chuyển đích |
| Timeout/connect/5xx/redirect/JSON/MIME/byte limit/receipt sai/429 không rõ | unknown terminal; không tự gửi lại |
| Hủy/mất lease hoặc lỗi lưu sau claim/HTTP | giữ durable sending; reconciler cũ chuyển unknown, không queued |

Success/unknown đặt cooldown bot ít nhất1giây; cố ý bảo thủ hơn giới hạn provider,
chưa phải tối ưu throughput nhiều đích. Hai bot không chia sẻ cooldown. Payload
và response có credential echo bị chặn; log dùng bộ lọc coroutine-local của A.

## Kiểm chứng và phạm vi còn mở

- Checkpoint trước code: `.runtime/checkpoints/p0-20261015T085540-7b674149/manifest.json`,
  1100source/primary0060/129physical/3archives, backup+restore đạt.
- Hồi quy cuối: **509passed/0fail/0error/0skip**,351.65giây;61sender+408previous
  Telegram/Engine/Brain/Voice/S13/resource+40Knowledge workspace/source. Bằng chứng
  `.runtime/s32c-sender-focused.xml`. Ba warning ARQ close deprecation có từ trước;
  3ca Redis/ARQ thật dùng DB15. Không gọi zero-warning hoặc full backend.
- `pao_test`0063; alembic check không có upgrade operations mới, không migration
  mới ở bước sender. Primary vẫn0060, không apply0061–0063.
- 25Node runtime/SSE/tenant:25passed/0fail/0skip,384.7769ms. Isolated import đạt,
  không network/router/legacy bridge và scoped flag vẫn false.
- API/ready/Web200,workerhealthy,Telegram bridge disabled; Docker29.4.3 và
  PostgreSQL/Redis healthy. `.env` hash không đổi:
  `5672f74189bcef6c110d4c434e956d4f324598ee3901b88bbd56902c945fbea7`.
- Live338operations khớp saved contract; API/worker/Web PID+UTC start-time không
  đổi. Candidate binding `16152bce13cf48693afd5f6e040e32d75fb795e90be57ce3f326d8a36fc3d692`,
  khác installed binding S31B; không coi mã mới đã được nạp vào bản chạy.
- Chỉ `pao_test`/RedisDB15/HTTP và LLM synthetic; không primary migration,
  restart/real bot/outside message. Chưa full backend/build/browser tại primitive
  chưa wiring. Các gate này chạy ở release C ổn định.

Fixture ban đầu cố đổi kind của binding (bị DB từ chối đúng) và thiếu workspace
trong BrainMember. Đã sửa cách tạo fixture: cấu hình session rõ trước admission,
tôn trọng trigger thu hồi và grant đúng SME; không nới guard để test xanh.
Hai vòng đầu46pass/4fail rồi55pass/2fail không dùng làm kết quả cuối.

**Tiếp theo duy nhất trong C:** worker/webhook mode/epoch/fair dispatch/backoff,
scoped report/destination resolver, lock audit các đường chung, oversized update/
idle-week cursor policy; rồi full release/restore checker0063/checkpoint/migration/
restart/live binding/contract/replay/exact restore. Chưa chuyển S3.3 hoặc mở gate
provider/public deployment/production reboot.

Nguồn chính thức đọc trước code15/10: [sendMessage](https://core.telegram.org/bots/api#sendmessage),
[ResponseParameters](https://core.telegram.org/bots/api#responseparameters),
[FAQ về giới hạn gửi](https://core.telegram.org/bots/faq#my-bot-is-hitting-limits-how-do-i-avoid-this).
Trang Bot API hiện ghi10.3,24/08/2026. Phân loại unknown/no-resend, timeout và
cooldown bảo thủ là quyết định PAO, không phải tuyên bố quota/billing Telegram.
