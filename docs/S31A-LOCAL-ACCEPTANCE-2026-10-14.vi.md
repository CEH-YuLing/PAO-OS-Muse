# S3.1A — Foundation namespace Telegram

Ngày14/10/2026. Target `F:\PAO-ACOS`; nguồn Apex giữ nguyên.
Trạng thái **local_accepted — S3.1A**, không gọi đã hoàn tất S3.1/S3 hoặc nhiều bot thật.
[ADR](ADR-S31A-TELEGRAM-NAMESPACES.vi.md),
[provider dossier](TELEGRAM-PROVIDER-DOSSIER-2026-10-14.vi.md),
[register](S3-COMPLETION-REGISTER.vi.md).

## Đã triển khai

Migration0059 thêm credential-free TelegramConnection và connection_id cho
peer/update/delivery/Channel binding/inbound/outbox/audit. Native update receipt
dùng UUID; giá trị update_id/run_id/peer_id/created_at cũ không đổi. Unique mới
scoped theo connection; partial unique giữ namespace legacy NULL.
DB guards giữ namespace parent/child, immutable history, revoked no resurrection.
HMAC có tùy chọn connection UUID, legacy giữ hash cũ.

Không backfill bot/SME hoặc copy `.env`. Actor/helper/legacy ingest/collect/send/
setup chỉ cho namespace NULL; không cho staged namespace dùng token toàn host.
Không tạo bridge mới, không thêm endpoint, frontend hoặc flag. API contract334
khớp file đã lưu. Backend binding mới:
`b9365b680ea05a24c9cdde273ddffdc0de95ae16aeb0262eb9493861f0e94d61`.

## Bằng chứng

| Gate | Kết quả |
|---|---|
| Pre-change S2 installed/backup |0058/live334/binding3d811e0e/hash/.env unchanged; exact restore manifest `p0-20261014T110703-a313d3a0` đạt |
| Focused legacy regression |44passed/2existing ARQ warnings;24.91s; Telegram/helper/Channels/P7ARQ/business delivery |
| Namespace adversarial |25passed;7.28s; `.runtime/s31a-namespaces.xml` |
| Clone migration |0058→0059→0058→0059 đạt; legacy Telegram/Channel seeded, old-row hashes exact, rollback schema equivalent, populated downgrade refused, primary unchanged |
| Pre-rollout checkpoint |`.runtime/checkpoints/p0-20261014T113052-39727bab/manifest.json`;1060source/0058/125physical/3archives; exact restore/current binding đạt |
| Full backend |1709passed/0fail/0errors/0skip;1532.89s; `.runtime/s31a-backend-20261014T112222.xml`; real ARQ wall-clock bật,41existing ARQ warnings |
| Node/runtime/SSE |80passed/0fail/0skip;629ms;11pure test files, không chạy song song browser/build |
| Browser affected |4passed/0fail/0errors/0skip;95.79s; `.runtime/s31a-browser.xml`; S11/S12/P7/S23F |
| Primary rollout/live |0059/live334/current binding/126physical/3archives,old-column hashes exact,.env unchanged,no mapping; API/ready/Web200,workerhealthy |
| Post-rollout exact restore |`.runtime/checkpoints/p0-20261014T115323-228b5652/manifest.json`;1060source/125business/126physical/3archives, row hashes exact/schema equivalent/primary unchanged |

Native25cases kiểm hai bot cùng user/chat/update ID/dedup key độc lập, duplicate
trong cùng namespace vẫn denied; child/SME mismatch, NULL legacy uniqueness,
đổi namespace/history và hồi sinh revoke bị chặn. Staged queue không bị legacy
transport claim/cancel/send; không inference hoặc network provider.

Clone dump giữ lại: `.runtime/s31a-pre-237cb5299db5422a8708ef0d03a775bf.dump`.
Chỉ clone tự tạo bị xóa; database chính và database test không reset.
Rollout kiểm migration digest và backup/current primary trước thay đổi; idle0,
external flags off. API7132/worker16228 thay đúng process records/start-time;
listener8100 thuộc child4944 mới lúc18:51:08VN, không dùng PID cũ làm proof.
Sau đồng bộ docs sẽ tạo thêm final checkpoint và exact restore; handoff cung cấp
manifest cuối, không chỉnh source/docs sau niêm phong để thêm self-reference.

## Chưa triển khai / bước kế tiếp

**Tiếp theo duy nhất S3.1B**: explicit owner mapping và ledger/version/preview/apply.
Peer/binding/
receipt cũ không đổi connection_id tại chỗ; mapping cần generation mới/provenance
giữ history/unknown. Namespace storage chưa phải getMe verified identity, token
vault/resolver, webhook/polling/sender theo bot. S3.2/S3.3 và live gate riêng.

Không chạy build frontend mới vì không đổi frontend hoặc contract. Build21 và
TypeScript là evidence S2 cùng ngày, không gọi là lượt S3.1A mới. Node80 đã kiểm
lại riêng trong lượt này, không dùng pao_test hoặc cache build.
