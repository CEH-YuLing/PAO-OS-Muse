# ADR-S31A — Namespace Telegram, không gán ngầm bot cũ

14/10/2026. Target `F:\PAO-ACOS`, nguồn Apex không thay đổi.
S2 đã đóng local; S3.1 triển khai theo A foundation rồi B explicit mapping.
Đây không phải thiết kế OAuth, resolver token hoặc vận hành nhiều poller mới.
[Provider dossier](TELEGRAM-PROVIDER-DOSSIER-2026-10-14.vi.md) được đọc trước code.

## Quyết định foundation

`TelegramConnection` là namespace có SME/owner, loại native/legacy, bot ID,
status staged/revoked và version. **Không có token/secret/transport active**.
Bot ID khai báo chưa là danh tính đã xác minh; getMe/credential ở S3.3.
Một bot ID không thuộc hai SME; legacy host chỉ có một namespace được staging.

- Peer có nullable connection_id + composite FK cùng SME, unique user/chat mỗi
  connection. Hai bot có cùng user/chat không xung đột.
- Update có internal UUID; update_id giữ nguyên, unique theo connection. UUID
  cho receipt cũ sinh xác định từ update ID, không từ token. Không đổi Run/receipt.
- Delivery có connection_id, dedup theo connection; ChannelBinding/Inbound/
  Outbox/Audit cùng pin. Child phải khớp namespace parent, cả trường hợp NULL.
- Legacy NULL giữ partial unique index tương đương các unique cũ. Migration
  không tạo connection hoặc đoán workspace từ email, thứ tự hoặc `.env`.
- DB guards chặn đổi namespace/SME connection, đổi namespace history và hồi sinh
  connection đã revoke. Downgrade từ chối khi có connection mới/mapped history.

## Ranh giới runtime

Các transport cũ chỉ đọc/claim namespace NULL. Actor/permitted chặn namespace
mới; staged queue không bị worker legacy claim, cancel hoặc resend.
HMAC legacy không đổi; helper namespace mới gồm connection UUID, không dùng
token làm identity. Không thêm bridge/scheduler/agent thứ hai, không sửa flags.

S3.1A kiểm storage/dedup/isolation và non-execution; **chưa** gọi ingest/send cho
hai bot qua resolver đúng token. Gate đó thuộc S3.1B/S3.2; fixture DB không là
connector hoặc bot thật đã accepted. API334operations không đổi, frontend không đổi.

## S3.1B kế tiếp — chưa triển khai

Owner xem preview bot legacy/peers/SME/history/unknown deliveries, chọn mapping
explicit có version/hash/request key/audit. Không copy `.env` hoặc gọi provider.
Không đổi connection_id của receipt/binding/peer cũ: tạo mapping và generation
mới, giữ provenance cũ; không tiếp tục queue unknown bằng credential mới.
Nếu legacy peers nằm ở nhiều SME, refuse mapping mơ hồ thay vì chia sẻ secret.
Trước transport phải đóng revoke/member/Brain/private-context và queued pins.
UI token/getMe/destination ở S3.3; provider sends/public webhook vẫn cần gate riêng.
