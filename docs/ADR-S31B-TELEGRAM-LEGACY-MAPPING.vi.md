# ADR-S31B — Chuyển Telegram cũ bằng xác nhận owner

14/10/2026, `F:\PAO-ACOS`. Không thay nguồn Apex, `.env`, token hoặc provider.
Theo [S3 register](S3-COMPLETION-REGISTER.vi.md) và
[provider dossier](TELEGRAM-PROVIDER-DOSSIER-2026-10-14.vi.md).
Telegram sử dụng token từ BotFather, không App ID/Secret giống Meta.

## Quyết định

Một bot host cũ chỉ được chuyển sang đúng một SME, do owner xác nhận trực tiếp.
Owner của hai SME không được tự gộp dữ liệu hai bên. Nếu có peer/binding ở SME
khác, trả blocked reason chung; không trả ID, số lượng hoặc nội dung của SME khác.
Phải tắt Telegram host, không có Run đang chạy hoặc delivery đang gửi. Actor phải
active, có membership phù hợp; session phải thuộc cùng SME/actor. Giới hạn
100 peer/binding, 10.000 metadata receipt mỗi loại; không đọc transcript vào preview.

GET preview/mapping không ghi hoặc gọi Telegram. Apply cần hai xác nhận độc lập,
version0/hash bản xem trước và UUID request-key. Hash bao gồm quyền, binding,
session và metadata ledger; apply kiểm lại dưới transaction/row locks và advisory
lease dùng chung với bridge. Replay cùng key/body trả trạng thái đã lưu; key khác
body hoặc preview stale bị từ chối. Không tự retry trên browser.

Migration0060 thêm journal, provenance và audit append-only. Không tự backfill.
Apply tạo connection staged/v1 và thế hệ peer/binding mới **đang tắt**; binding
quiet/outbound false, Brain/session null. Giữ source kind/retention và provenance;
không sao chép token, hội thoại, Brain hoặc hàng đợi. Receipt/payload/namespace cũ
không đổi. Source private Brain không được đưa sang binding mới.

Tồn tại legacy connection tạo barrier vĩnh viễn cho transport host cũ. Revoke
cần version/request-key/xác nhận riêng, staged→revoked/v2 và audit mới; không
phục hồi host token hoặc phát lại unknown/queued. Ingest/collect/sender/bridge/
setup legacy bị chặn; collect/send không claim hoặc cancel hàng đợi cũ. Kênh
local vẫn hoạt động. Retention policy riêng không bị biến thành thao tác mapping.
DB chặn ghi receipt legacy mới, sửa/xóa journal và hạ cấp khi đã có mapping history.

## Settings và phạm vi nghiệm thu

Panel Integrations không có trường secret. Owner đọc preview, xác nhận storage-only
và no-history-replay, có thể revoke rõ ràng. Nonowner không gọi mapping GET.
SME/role switch bỏ form cũ; abort/ticket và validation closed DTO chặn response
đến muộn, authority giả hoặc workspace khác. Hide/pagehide xóa consent. Nếu mất
phản hồi, bỏ snapshot/consent, khóa actions và yêu cầu đối chiếu bằng GET; GET
không đảm bảo một request vẫn đang chạy đã kết thúc, nên không tự POST lại.

S3.1B code/fixture không chứng minh transport nhiều bot hoạt động. Resolver token,
bot-specific lease/offset/webhook/sender ở S3.2; token/getMe/đích/team/Brain/bật bot
ở S3.3. Tin thật, bot thật, HTTPS/reboot và production cần gate độc lập.

## Tham chiếu chính thức

[Bot API](https://core.telegram.org/bots/api),
[BotFather](https://core.telegram.org/bots/features#botfather), đối chiếu14/10/2026.
Không gọi provider để làm xanh trạng thái hoặc tự chọn SME trên database chính.
