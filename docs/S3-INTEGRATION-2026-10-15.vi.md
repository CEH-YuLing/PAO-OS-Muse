# S3 — Nghiệm thu tích hợp Telegram và Cài đặt

15/10/2026, dự án `F:\PAO-ACOS`. Phạm vi S3 trong master gồm **S3.1–S3.3**;
không có S3.4–S3.7. Đây là báo cáo của cùng milestone, không phải roadmap mới.

## Trạng thái hiện hành

**Toàn S3.1–S3.3 đạt local_accepted ngày15/10.** Runtime, webhook, báo cáo và
Settings/team đã triển khai, kiểm thử và nạp vào bản local đang chạy. Primary
0064/live349/134physical tables/3archives; API/ready/Web200, worker healthy,
live binding khớp source. Bot thật/HTTPS/reboot vẫn external_pending, không phải
production_accepted. Bước tiếp theo trong master là **S4 — Meta/Google theo SME**.

Source candidate cố định:
`c44d27b22f4af7457327dc062060fb8faa4c3cdcc7d8d48888524cb87483bff1`.
Schema đã cài0064, contract349. Không đổi `.env` hoặc bật transport thật.
Checkpoint đầu lượt: `.runtime/checkpoints/p0-20261015T124329-c1cfe532/manifest.json`
(1106source/0060/129physical/3archives, verified backup/restore).

## Phần đã triển khai

### Nhận tin và xử lý theo bot

- Kế thừa namespace/legacy mapping, profile mã hóa, identity journal và Channels
  kernel đã kiểm chứng; không dựng agent engine, Run ledger hoặc hàng đợi AI thứ hai.
- Worker Telegram riêng: ticket mỗi doanh nghiệp, luân phiên nhiều bot, PG lease
  theo bot thật, source/generation pin, backoff riêng và ngân sách thời gian hữu hạn.
  Webhook mode chỉ thu kết quả/gửi outbox, không gọi getUpdates song song.
- Webhook tại đường dẫn theo connection, secret header riêng lưu bằng hash,
  so sánh hằng thời gian, không JWT/authority từ body. Body tối đa2MiB, MIME JSON,
  không phản chiếu payload/secret. Chỉ ACK sau durable receipt/admission commit.
- Chọn chế độ là thao tác có consent riêng, phải tắt profile trước; setWebhook/
  deleteWebhook giữ `drop_pending_updates=false`, không tự retry. Mất ACK giữ
  profile tắt, không coi đã cấu hình thành công hoặc tự chuyển mode.
- Polling kiểm webhook conflict; bật webhook yêu cầu getWebhookInfo khớp URL
  HTTPS được quản trị máy chủ cấu hình. Không tự lấy token host làm dự phòng.
- Update lớn trong giới hạn2MiB nhưng quá ngân sách admission64KiB được ghi
  receipt hash/malformed không giữ body, rồi mới ACK; không kẹt mãi trước update
  hợp lệ kế tiếp. Body quá2MiB bị từ chối, không tự bỏ tin hoặc xóa pending updates.
- Sau ít nhất7ngày không nhận update, cursor reset về0 trong epoch mới. Giữ
  receipt/dedup cũ, không dùng offset âm; database kiểm thời gian/epoch/offset
  và ngăn đồng hồ ứng dụng lệch ép reset sớm. Webhook nhận tin sai thứ tự vẫn dedup.

### Danh tính, quyền và lịch sử

- Tạo kết nối cần getMe chứng minh token đúng bot trước khi giữ chỗ ID; không
  cho một SME chiếm bot của SME khác chỉ bằng ID công khai. Lưu token riêng là
  bước mã hóa đang tắt, không tự gọi provider hoặc bật xử lý.
- Một lần liên kết gồm: tài khoản PAO hiện hành tạo mã192bit/10phút cho đúng
  connection/generation/Telegram numeric ID/kho tri thức; Telegram quan sát mã;
  chính tài khoản PAO xác nhận lại; quản trị viên mới cấp quyền rõ ràng.
- Mã chỉ lưu hash, không đưa vào Run/prompt/lịch sử hội thoại. Mã chuyển tiếp
  từ ID khác bị thu hồi; sai bot/tài khoản, hết hạn, replay, rotation hoặc rời
  doanh nghiệp không cấp quyền. /start và quản trị nhóm không tạo membership.
- Tách giao việc và nhận báo cáo: quyền báo cáo riêng dùng quiet binding nên
  không tạo Run; quyền bot không cấp thêm công cụ, quyền kho tri thức hoặc duyệt.
  Viewer không được dùng đường actor hoặc quảng bá là đã có báo cáo cho viewer.
- Đổi generation do đổi khóa/chế độ/tắt/bật/thu hồi vô hiệu quyền binding cũ
  bằng DB trigger, không tự khôi phục sau bật lại. Liên kết/cấp quyền lại có
  audit/version; không đổi Brain của binding đã có lịch sử để repin dữ liệu cũ.
- Người quản trị kết nối không tự được đọc nội dung vào của actor riêng.
  Kết quả và báo cáo tiếp tục kiểm quyền nguồn/kho/actor ở trước gửi.
- Giữ no-resend: sending/unknown không được tự gửi lại; HTTP đã admitted không
  thể thu hồi tại provider. Các sửa lock contention/retention của worker giữ nguyên.

### Báo cáo và vận hành

- Báo cáo Meta hiện có nhận **binding đích cụ thể**, đúng SME và đúng người sở
  hữu báo cáo; không chọn bot đầu tiên hoặc fallback sang bot host. Queue qua
  native outbox, phân phần UTF-16 và kiểm lại Meta connection/version/quyền
  nhận báo cáo/nội dung trước HTTP. Không mở quyền Ads ghi hoặc S4 grant report mới.
- Lịch báo cáo pin binding/version. Đổi hoặc thu hồi quyền làm lịch dừng, không
  chọn bot khác. Giao diện báo cáo yêu cầu chọn đích và consent trước gửi/bật lịch.
- Launcher/restart hỗ trợ role Telegram riêng khi flag cho phép; phát hiện worker
  không có hồ sơ thì không dừng PID đoán. Health chỉ báo liveness; flag tắt không
  chứng minh provider healthy. Không khởi động daemon Telegram thật trong lượt này.

### Cài đặt tiếng Việt

- Nhãn chính, thanh điều hướng và trạng thái dùng tiếng Việt; enum/URL/ID/API,
  tên sản phẩm, tên công cụ và dữ liệu người dùng không đổi nghĩa ở backend.
- Các nhóm có hướng dẫn phạm vi, quyền, chuẩn bị, trường nhập, lưu/kiểm tra/bật,
  lỗi không rõ kết quả, đổi khóa và ngắt kết nối. Giữ hướng dẫn riêng trong form
  cloud/MCP/Meta/Google và bổ sung hướng dẫn tổng theo tab.
- Telegram có form token bí mật, getMe, chọn mode, bật/tắt/ngắt, mã một lần,
  xác nhận chính mình và bảng cấp/thu hồi quyền. Secret/mã bị xóa khi đọc lại,
  thao tác, ẩn tab/rời trang hoặc đổi SME; không browser storage.
- Trạng thái đã lưu/đã kiểm tra/đang bật/nghiệm thu thật tách biệt. Thanh trạng
  thái chung không còn hardcode API READY hoặc suy flag thành dịch vụ khỏe.
- Ứng dụng riêng Meta/Google từng SME còn ở S4; UI nói rõ cấu hình host hiện
  hành, không làm form TikTok giả. Chưa gọi toàn bộ sản phẩm đã Việt hóa: các
  màn ngoài Cài đặt được xử lý theo checkpoint liên quan, không đổi dữ liệu khách.

## Kiểm chứng đã có

| Gate | Kết quả |
|---|---|
| Focused cuối |93passed/0fail/0skip,110.07s; setup/report/scoped/worker; `.runtime/s3-pre-final.xml` |
| Hồi quy trước guard cuối |121passed/18ARQ warnings; không dùng thay vòng cuối |
| Toàn bộ Node thuần giao diện |109passed/0fail/0skip; có13ca Telegram parser/pairing/cross-SME mới |
| TypeScript |`tsc --noEmit -p apps/web/tsconfig.json` exit0 |
| Production build |exit0,21/21 trang; cache `.pao-build-check` riêng; còn cảnh báo React Hook, không tuyên bố lint sạch toàn ứng dụng |
| Browser tích hợp |API/PG thật trong DB mới riêng, HTTP Telegram synthetic; proof-before-reservation/save-not-enable/pairing2phase/report-only/revoke/secret wipe/SME switch/mobile390&320/tất cả tab có hướng dẫn đạt |
| Migration |0063→0064→0063→0064 và0060→0064→0060→0064; old-column hashes/schema rollback exact; populated downgrade refused; `.runtime/s3-migration.json` |
| ARQ thời gian thực |Vòng full cuối phục hồi sau71.45s và96.03s, một tool claim; bật PAO_ARQ_WALL_CLOCK_TESTS=1 |
| Toàn backend cuối |2077passed/1failed/0errors/0skip,1990.14s; ca lỗi là script phục hồi P7 chưa nhận revision0064, không phải lỗi backend. Sửa allowlist tường minh dùng chung rồi chạy lại27ca đạt/0skip.2078 danh tính test có kết quả cuối đạt; backend SHA không đổi. Giữ nguyên XML full có1lỗi, không gọi đây là full rerun xanh; `.runtime/s3-full-final.xml`, `s3-recovery-final.xml`, `s3-regression.json` |
| Primary rollout |0060→0064; hash các cột cũ/row counts/3archives nguyên vẹn,5bảng mới rỗng; alembic check không phát hiện chênh; `.runtime/s3-schema-rollout.json` |
| Live sau restart |API/ready/Web200,workerhealthy;349operations khớp contract/binding;3/3 replay chỉ đọc không gọi tool; business hashes/.env không đổi; Telegram/Ads vẫn tắt; `.runtime/s3-live.json` |
| Exact restore |Checkpoint trước rollout `p0-20261015T142145-c4803bf0` có1128source/0060/129physical/3archives đã phục hồi exact. Checkpoint sau rollout `p0-20261015T142514-f89e3461` có1128source/0064/134physical/3archives:133business row hashes exact/schema tương đương/primary unchanged, không provider call. Bản niêm phong sau cập nhật tài liệu cũng lưu trong `.runtime/checkpoints`, manifest bàn giao được kiểm lại bằng cùng script |

Ca P7 được sửa duy nhất danh sách schema hỗ trợ trong script, không bỏ assert
kiểm dữ liệu, chống trùng, không gửi lại hoặc fresh process. Script đối soát
chỉ chấp nhận đúng ca lỗi này, đủ27ca retry, không skip/error và backend SHA
không đổi; không phải cơ chế miễn trừ lỗi tùy ý. Harness live đầu tiên truy vấn
nhầm `runs.user_id`; đã sửa join Session theo đúng quan hệ chủ sở hữu và chạy
lại toàn bộ gate live đạt, không sửa schema hoặc giảm kiểm quyền API.

## Ma trận hướng dẫn Cài đặt

| Nhóm | Quyền/phạm vi, nơi lấy trường, vòng đời và tình trạng hỗ trợ |
|---|---|
| Tài khoản/đội ngũ |Email/mã PAO/vai trò theo SME; danh sách đủ điều kiện không phải giao diện mời người; owner/admin không được đọc Brain riêng chỉ từ vai trò |
| Hạn mức |Đơn vị, UTC/07:00 Việt Nam, trần host, policy version/CAS, số liệu chưa rõ không là0; không suy ra hóa đơn/quota nhà cung cấp |
| Quyền kết nối |Nguồn, nhân viên, nhãn hàng, account, thời hạn, consent và kích hoạt riêng; thu hồi phiên bản cũ không tự sống lại |
| Local/cloud model |Ưu tiên Ollama; tài liệu lấy API key từng hãng, trường password, danh mục/model/probe có phí; job routing ở S5.3 |
| MCP |HTTPS endpoint, Bearer, danh mục/schema, giới hạn tham số, Run/key chống trùng, rotate/disconnect; stdio/OAuth refresh không được giả định hỗ trợ |
| Meta/Google |App/Client ID/Secret/callback ở đúng scope, quyền tài sản và OAuth; không nhầm Google Ads OAuth với Gemini key; managed/BYO tenant App còn S4 |
| Telegram |BotFather ID/token/getMe; numeric user ID, Brain ID, code một lần, consent/role/đích nhận riêng; private chat trước, không group-admin authority |
| Giọng nói |Micro, thư viện STT/TTS, thiết bị/kiểu tính toán/thời lượng; readiness thư viện chưa là nghiệm thu giọng thật |
| An toàn/trạng thái |Chỉ đọc chốt máy chủ, không cấp chi tiền/ghi; unknown/manual refresh, không nhập lại secret mù; unsupported TikTok nói rõ |

## Lỗi và giới hạn được ghi nhận

- Hai lượt pytest dùng chung pao_test đã va chạm fixture ở đầu lượt; không dùng
  kết quả đó để nghiệm thu. Sau đó chạy tuần tự; browser dùng DB riêng hoàn toàn.
- Một vòng full tiền nghiệm thu được ngắt để bổ sung guard generation; không
  gọi vòng bị ngắt là passed. Kiểm kê tiến trình cuối chỉ có launcher/child của
  cùng vòng full hiện hành, không có hai suite chạy đồng thời.
- Hai test guard mới ban đầu nhận mã từ chối quá chung do context lease bọc
  HTTPException; đã sửa bảo toàn deliberate domain denial, lỗi provider vẫn che.
  Ca giả mạo Run context được cập nhật để giả cả version sau regrant, giữ bằng
  chứng immutable inbound chặn repin, không giảm điều kiện bảo mật.
- Harness browser ban đầu patch HTTP transport trước import lớp kế thừa và chọn
  sai selector enterprise trên mobile. Đã sửa harness; vòng cuối đi qua menu mobile
  thật và dọn đúng API/DB do runner sở hữu. Không coi lỗi harness là lỗi provider.
- Có cảnh báo thư viện ARQ close và React Hook; không sửa dependency hoặc logic
  ngoài phạm vi chỉ để xóa cảnh báo. Kiểm thử fixture không là benchmark tải lớn/SLA.
- Quản trị viên tạo connection quản lý token/cấu hình của connection đó; quản trị
  viên SME khác trong cùng doanh nghiệp có thể quản lý team, không tự chuyển owner
  bất biến hoặc nhận quyền đọc lịch sử riêng. Bàn giao ownership là luồng riêng.

## Gate bên ngoài không tự thực hiện

Chưa nhập/copy token thật, chưa chọn bot/SME hoặc gửi tin thật; cả host/scoped
Telegram và Channels trên bản dùng thật giữ tắt. Khóa mã hóa host đã kiểm chỉ
bằng boolean sẵn sàng, không in/lưu khóa vào báo cáo. `.env` SHA256 không đổi:
`5672f74189bcef6c110d4c434e956d4f324598ee3901b88bbd56902c945fbea7`.

Tin thử thật cần bot/đích được cấp phép; webhook công khai cần domain/HTTPS và
kiểm chứng provider; production reboot/restore riêng chưa có VM/VPS. Giữ
external_pending, không hỏi lại các lựa chọn đã chốt hoặc lấy fixture làm live.

Nguồn chính thức đọc lại15/10 trước code: [Telegram Bot API/getUpdates](https://core.telegram.org/bots/api#getupdates),
[setWebhook](https://core.telegram.org/bots/api#setwebhook),
[deep linking](https://core.telegram.org/bots/features#deep-linking), Bot API10.3.
Epoch, ticket, consent, giới hạn2MiB và chế độ no-resend là thiết kế PAO, không
phải cam kết của Telegram về quota/không mất dữ liệu.
