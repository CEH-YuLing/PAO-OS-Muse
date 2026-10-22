# Telegram — provider dossier cho S3

Cập nhật kiểm chứng15/10 cho S3.2: đã đọc lại Bot API/FAQ/getUpdates/setWebhook
trước code; trang chính vẫn ghi10.3. Metadata kernel chỉ dùng getMe/getWebhookInfo;
không coi getUpdates là phép đọc vô hại vì offset xác nhận update. Chi tiết
[ADR-S32](ADR-S32-TELEGRAM-SCOPED-RUNTIME.vi.md). Không thử token/provider thật.

S3.2C15/10: đọc lại [getUpdates](https://core.telegram.org/bots/api#getupdates)
trước triển khai adapter; offset ACK phải theo receipt đã commit, timeout dương,
webhook conflict không tự xóa webhook. Provider giữ update tối đa24giờ và có thể
đổi sang ID ngẫu nhiên sau ít nhất một tuần yên lặng. Candidate polling chưa có
cursor epoch reset an toàn cho ID giảm; gate C phải xử lý trước rollout, không
dùng offset âm hoặc bỏ dedup để nhận lại mù. [Evidence/phần còn mở](S32C-POLLING-ADAPTER-2026-10-15.vi.md).

Phần gửi15/10 đối chiếu lại [sendMessage](https://core.telegram.org/bots/api#sendmessage)
và [ResponseParameters](https://core.telegram.org/bots/api#responseparameters):
không thêm paid broadcast; chỉ xác nhận sent khi receipt bot/chat/text khớp.
429 cần retry_after hợp lệ; timeout/5xx hoặc ACK chưa rõ không tự gửi lại theo
quyết định an toàn PAO. [Sender/gates](S32C-SENDER-ADAPTER-2026-10-15.vi.md).

Đối chiếu 14/10/2026; Bot API docs hiện ghi10.3 (24/08/2026).
Nguồn chính thức: [Bot API](https://core.telegram.org/bots/api),
[BotFather](https://core.telegram.org/bots/features#botfather),
[FAQ](https://core.telegram.org/bots/faq). Không thử token/provider thật.

BotFather cấp token cho bot; không phải App ID/Secret hay OAuth SME. `getMe`
kiểm token và trả danh tính bot. HTTPS request chứa token trong URL, nên không
log URL/exception transport. `getUpdates` và webhook loại trừ nhau; offset xác
nhận update, webhook có thể được gửi lại. Secret webhook là header riêng.
ID bot/user/chat cần kiểu64bit an toàn. [API](https://core.telegram.org/bots/api).

Token bị lộ cần cấp lại qua BotFather `/token`; lưu an toàn vì người có token
có thể điều khiển bot. [BotFather](https://core.telegram.org/bots/features#generating-an-authentication-token).
Hạn mức gửi phải theo từng bot/đích; xử lý429 và retry_after, không suy ra quota
còn lại từ PAO. [FAQ](https://core.telegram.org/bots/faq#my-bot-is-hitting-limits-how-do-i-avoid-this).

Thiết kế PAO (suy luận từ transport bot-scoped): namespace connection riêng,
receipt `(connection_id, update_id)`; chat/user giống nhau giữa bot không đồng
nghĩa cùng quyền. Một bot không tự thuộc hai SME; legacy toàn host cần owner
mapping có version/audit, không repin history, không copy credential từ `.env`.

## Settings dự kiến ở S3.3 — chưa phải giao diện đã triển khai

| Trường/thao tác | Hướng dẫn và gate |
|---|---|
| SME | Chọn doanh nghiệp, kiểm owner/admin và quyền actor riêng |
| Bot token | Password input, không browser storage/chat/log; mã hóa server-side; không App Secret |
| Kiểm tra danh tính | Consent gọi getMe; hiển thị bot ID/username đã xác minh, không đánh dấu live accepted |
| Destination | Chat/user allowlist explicit; ban đầu private chat, không tự discover/nhập khách |
| Transport | Một owner mỗi bot; webhook HTTPS/secret riêng hoặc offset/lease polling riêng (S3.2) |
| Team/Brain | Native role/Brain/grant, không cấp tool từ quyền bot |
| Test/status | Tin thử vô hại cần đích được duyệt; saved/configured/verified/healthy/accepted tách riêng |
| Disconnect/rotate | Chặn job cũ, unknown không resend; revoke token tại Telegram riêng |

S3.1A chỉ foundation schema/namespace và guard transport legacy; không credential,
getMe, webhook/polling mới, tin thật, App review hoặc public redirect. S3.1B phải
đóng explicit legacy mapping/version/audit trước S3.2, giữ P7 receipts/no-resend.
