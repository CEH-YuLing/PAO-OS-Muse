# S3.1B — Explicit legacy mapping: mã và kiểm thử cô lập

**Cập nhật15/10:** S3.1B đã rollout và local_accepted theo
[nghiệm thu tích hợp mới](S31B-LOCAL-ACCEPTANCE-2026-10-15.vi.md).
Phần bên dưới là snapshot14/10, không còn là dispatch hiện hành; tiếp theo S3.2.

14/10/2026, `F:\PAO-ACOS`; nguồn Apex giữ nguyên. **in_progress**, chưa
local_accepted/rollout. [ADR](ADR-S31B-TELEGRAM-LEGACY-MAPPING.vi.md),
[S3 register](S3-COMPLETION-REGISTER.vi.md). Không bắt đầu lại phần foundation S3.1A.

## Đã làm

- Migration0060: journal/provenance/audit append-only, source scope và legacy write
  barrier; không tự backfill. Downgrade có lịch sử phải từ chối.
- Bốn API owner-only: preview/mapping/apply/revoke, Closed DTO/no-store/body8KiB,
  version/hash/UUID request-key, transaction/lease và quyền kiểm lại lúc apply.
- Thế hệ peer/binding mới đang tắt, không copy token/Brain/session/history/queue.
  Revoke không hồi sinh host bot. Thu hồi/duplicate/replay không gửi Telegram.
- Sửa lỗi sender cũ cancel queued sau mapping: collect/deliver/send_one dừng trước
  claim/reconcile, giữ queued/unknown và số attempts. Kênh local không bị chặn.
- Settings/Integrations: preview theo SME, hai consent độc lập, revoke riêng,
  lost-response khóa thao tác/manual GET, abort/ticket/closed validation. Nonowner
  không gọi mapping GET; đổi SME xóa form. Không có ô nhập secret.
- Source OpenAPI338operations,43routers; generated TypeScript contracts cập nhật.
- Chuẩn bị apply migration có checkpoint/digest/exact-restore/idle gates và live
  checker0060; **chưa chạy hai script rollout này trên database chính**.

## Bằng chứng mới của lượt này

| Gate | Kết quả |
|---|---|
| Final backend affected |91passed/0fail/0skip,47.79s; `.runtime/s31b-focused.xml`; mapping/namespace/helper/factory/Telegram/Channels |
| Native schema test |pao_test0060, `alembic check` không phát hiện upgrade mới |
| Frontend pure contracts/runtime |96passed/0fail/0skip; 16case mới về closed mapping contracts |
| TypeScript |standalone noEmit đạt; production build có typecheck |
| Recovery helpers |11passed/13.11s; `.runtime/s31b-recovery.xml`; exact-schema normalization, source declarations và populated P7 restore/restart/no-resend |
| New browser genuine HTTP |1passed/34.73s; `.runtime/s31b-browser.xml`; malformed authority, consent, lost committed ACK/no retry, manual GET, scope switch, revoke, mobile390/320 |
| Existing Team Settings browser |1passed trong lượt affected; tab/mobile/đội ngũ không bị mất; tổng lượt đó1passed/1failed trước khi sửa JSON header mới |
| Production frontend build |21/21 pages; final ref-cleanup build đạt; cảnh báo lint lịch sử vẫn còn, không coi là zero-warning |
| Clone migration |0059→0060→0059→0060 đạt; seeded old rows exact/rollback schema equivalent; populated downgrade refused; `.runtime/s31b-migration.json` |
| Primary nonmutation |clone checker so toàn bộ row hashes/schema/revision chính0059 trước/sau; `.env` giữ nguyên; không provider calls |
| Primary health tại bàn giao |API/ready/Web-settings200; live OpenAPI vẫn334; không restart/migration/owner mapping; `.env` hash không đổi |

Các lượt lỗi giữ trong diễn giải: focused ban đầu58/59 phát hiện cancel queued,
đã sửa và91final đạt. Browser ban đầu chưa mở lại Integrations sau tenant reset;
kịch bản sửa theo native reset (không bỏ gate). Browser tiếp theo phát hiện thiếu
Content-Type JSON trong request helper, đã sửa; final thật qua lost committed ACK.
Fixture migration0058 tái dùng sai UUID0059 cũng đã thay bằng ORM0059; final
clone đạt. Một lệnh regression gọi tên file không tồn tại đã dừng trước collection;
đã chạy lại đúng danh sách91tests. Không che các lượt này thành nghiệm thu full xanh.

Browser evidence: `.runtime/s31b-mapping-browser-eb5eeee02337491595f193e0c7ee49d8/browser.json`
và ảnh mobile cùng thư mục. Clone dump giữ lại:
`.runtime/s31b-pre-f49bfd6800cb4afc9ffa922b228cff74.dump`.
Chỉ clone tự tạo bị xóa; database chính, test và backup không bị xóa.

## Gate còn lại — tiếp tục đúng S3.1B

1. Full backend release với real ARQ wall-clock; affected/browser tích hợp S11/S12/P7
   cùng mapping (không chạy đồng thời trên pao_test/Redis15).
2. Checkpoint nguồn cuối/database0059, exact restore trước rollout. Manifest cuối
   được cung cấp ở handoff; backup nguồn0060 không đồng nghĩa database đã0060.
3. Áp dụng0060 sau các gate trên; restart đúng API/worker và Web process đã xác minh,
   kiểm0060/live338/current binding/API-ready-Web200/129tables/3M2archives/idle.
4. Post-rollout checkpoint/exact restore, đồng bộ local acceptance và register.

**Chưa tự chọn SME hoặc apply mapping trên primary.** Database/API chính vẫn
ở baseline0059/live334 cho tới rollout; source contract338 là ứng viên release.
Không chạy lại S2 hay dựng P/M roadmap khác. Sau khi đóng gate S3.1B thì làm
**S3.2 bot-specific runtime**, chưa chuyển ngay S4 hoặc gọi S3 đã hoàn thiện.
Token/getMe/đích/team/Brain ở S3.3; bot thật/public HTTPS/reboot production còn riêng.
