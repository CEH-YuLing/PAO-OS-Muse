# S3.2C — Bộ nhận Telegram bounded theo bot/doanh nghiệp

15/10/2026, target `F:\PAO-ACOS`. Đây là một phần của checkpoint C hiện hành,
không phải milestone/roadmap mới hoặc nghiệm thu toàn S3.2C.
Trạng thái: **polling/admission adapter source_verified**; toàn C in_progress.
Đây là evidence lúc đóng phần nhận. Phần gửi được triển khai sau đó tại
[sender evidence](S32C-SENDER-ADAPTER-2026-10-15.vi.md); mục handoff dưới đây là
snapshot lịch sử. Master/register quyết định đầu việc hiện hành, không làm lại polling.

## Phạm vi đã triển khai

`apps/api/pao/modules/channels/telegram_polling.py` nối HTTP getUpdates thật với
store/identity/admission của B; kiểm thử thay đường HTTP bằng fixture, không thay
database, quyền hoặc admission bằng bản giả. Không đăng ký daemon/job/router,
không import bridge host hoặc tự bật flag. A/B không được triển khai lại.

- `poll_once` tự lấy lease PostgreSQL theo bot ID thật, giữ cùng lease từ fetch
  đến hết batch. Không nhận token/offset/generation từ caller hoặc trình duyệt.
  Mọi lần gọi đọc profile mã hóa, registry, quyền owner và generation hiện hành.
- Kiểm getWebhookInfo trước getUpdates; có webhook thì chặn, không tự gọi
  deleteWebhook/setWebhook hoặc đổi chế độ. Cả flag scoped tắt và host bật đều
  chặn trước network. Không fallback `.env`/token host.
- Một turn tối đa5update/30giây/1PGslot; long poll5giây, mỗi HTTP10giây, mỗi
  transaction20giây. Kết thúc turn trả slot; đây chưa phải scheduler công bằng.
  Response batch tối đa320KiB, admission từng update giữ64KiB của B. Không ép
  cả5message vào ngân sách64KiB của một update.
- Origin/POST/body cố định; không proxy/redirect/retry. Tái sử dụng URL che token
  và log filter coroutine-local của kernel, chặn credential echo. Chỉ trả số
  lượng/offset, không trả raw update/body/token/URL hoặc lỗi provider.
- Batch sai kiểu/ID/size/thứ tự bị từ chối trước admission. Mỗi update hợp lệ
  đi qua transaction receipt+Channels/admit_run+cursor có sẵn; không eager enqueue
  hoặc fork engine. Lượt fetch kế tiếp chỉ ACK offset đã commit tại database.
- Hỏng giữa batch giữ prefix đã commit; restart/lease mới đọc lại cursor. Hủy,
  hết thời gian, mất PG session/lock hoặc đổi generation không tự ACK phần chưa
  lưu. Quyền actor/Brain/session vẫn kiểm lại khi admission; user lạ/nhóm/callback
  không tự được tạo tài khoản, membership hoặc quyền chạy.
- Tin khi phiên đang chạy được Channels lưu `busy`, không tạo Run thứ hai. Đây
  không là lời hứa tự chạy lại tin busy; không nới bảo vệ phiên/quota để test xanh.

## Nguồn provider đọc trước code

Đối chiếu15/10: [Bot API10.3,24/08/2026](https://core.telegram.org/bots/api),
[getUpdates](https://core.telegram.org/bots/api#getupdates),
[FAQ](https://core.telegram.org/bots/faq). Telegram xác nhận update khi gọi offset
cao hơn ID; polling/webhook loại trừ nhau; nên dùng timeout dương. Thông số batch,
time/byte bound và fail-closed ở trên là quyết định PAO, không phải quota provider.

Provider chỉ giữ update24giờ và có thể chọn ID ngẫu nhiên sau ít nhất một tuần
không có update. Chưa có cơ chế đổi epoch/cursor an toàn cho ID giảm: không tự
reset cursor, dùng offset âm hoặc bỏ dedup để vượt gate. Phải xử lý/kiểm chứng
trong C trước rollout; fixture monotonic không chứng minh trường hợp idle-week.

## Kiểm chứng

- Checkpoint trước code: `.runtime/checkpoints/p0-20261015T083723-4d7d9e03/manifest.json`;
  1097source, primary0060/129physical/3archives, backup+restore đạt.
- Hồi quy cuối: **408passed/0fail/0error/0skip**,221.14giây;40polling+368affected
  của B/namespace/Channels/Engine/Brain/Voice/S13/resources. Bằng chứng:
  `.runtime/s32c-polling-focused.xml`. Hai cảnh báo ARQ close deprecation có từ
  trước; không tuyên bố zero-warning. Hai ca hàng đợi ARQ thật dùng Redis DB15.
- `pao_test`0063, alembic check: không có upgrade operations mới. Chỉ schema
  candidate được dùng trong test; không apply0061–0063 lên primary.
- 25Node runtime/SSE/tenant passed,0fail/0skip,359.7509ms; không thay UI/contract.
- Syntax và isolated import đạt: không network/router/legacy bridge hoặc tự bật.
- API/ready/Web200,workerhealthy,Telegram bridge disabled; live338operations khớp
  saved contract. PID/start-time API/worker/Web không đổi; không restart/migrate.
- `.env` SHA256 vẫn `5672f74189bcef6c110d4c434e956d4f324598ee3901b88bbd56902c945fbea7`.
- Bản chạy vẫn S31B0060; code candidate qua0063, không coi binding source mới đã
  nạp vào API/worker. Không chạy full backend/build/browser ở primitive chưa wiring.
- Candidate source binding:
  `0bbbd55013f73df6cc35605a874febb9a1ab1b475a2897bb4d9a6ae4810991c0`;
  không phải installed binding S31B. Docker29.4.3 và PostgreSQL/Redis healthy.

Trong quá trình test, kỳ vọng Run thứ hai sai đã được sửa theo hành vi native:
1run+2receipt+tin thứ hai busy, không phải2run hoặc quarantine mất tin. Vòng rộng
trước sửa cuối406pass/1fail/2ARQdeprecationwarnings; không dùng vòng đó để báo xanh.

## Phần C còn mở — đầu việc tiếp theo duy nhất

1. Adapter gửi kết quả giữ/recheck authority sát HTTP invocation; classification
   sent/unknown/confirmed-no-send/429, không resend khi mất ACK. Không gọi preflight
   một lần rồi gửi payload tách rời bằng quyền cũ.
2. Worker scheduling/epoch ownership và mode webhook/polling theo connection,
   fair dispatch/backoff nhiều SME; webhook secret/path/body guards. Adapter này
   chỉ chứng minh một turn, không phải worker/HTTP webhook đã hoạt động.
3. Scoped report/scheduler/destination resolver; kiểm lock ordering cả retention/
   control/worker/collector; xử lý update quá lớn đơn lẻ, idle-week ID discontinuity
   và giới hạn provider. Không bỏ thông điệp âm thầm để làm health xanh.
4. Full backend/ARQ và affected acceptance ở release C ổn định; restore checker
   hỗ trợ0063, checkpoint/migration/restart/live binding/contract/replay/exact restore.

Chưa chuyển S3.3. Pairing/team grants, Settings token/getMe/status/disconnect và
hướng dẫn tiếng Việt vẫn là gate riêng. Không token thật/tin thật/public deploy.
