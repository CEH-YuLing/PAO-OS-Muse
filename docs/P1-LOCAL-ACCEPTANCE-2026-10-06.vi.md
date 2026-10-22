# P1 — Nghiệm thu LOCAL MVP ngày06/10/2026

Kết luận: P1.1–P1.5 đạt **phạm vi local text/Markdown** trên `F:\PAO-ACOS`.
Không sửa `F:\Apex\apex`/`F:\Javis OS`; không commit/push/public deploy,
không reboot Windows, không bật Ads/Telegram/email ghi dữ liệu thật.

## Những gì dùng được

| Mốc | Phần đã triển khai | Kiểm chứng |
| --- | --- | --- |
| P1.1 | Brain riêng theo workspace/user/brand; explicit reader/editor; default ánh xạ memory cũ, không copy hay mở quyền | Isolation/RBAC/composite FK; migration rollback/re-upgrade giữ nguyên hash dữ liệu cũ |
| P1.2 | Tạo/list/rename/archive/restore; chọn Brain cho session; pin Brain/revision trên run mới | Optimistic version/active run guards; history run cũ không đổi; custom Brain không kế thừa memory riêng |
| P1.3 | Upload/download/plain preview text/Markdown; metadata+immutable bytes cùng DB transaction; trash/restore | Traversal/device filename/UTF-8/MIME/size/quota/immutability; real UI preview không chạy script |
| P1.4 | Notes CRUD; immutable content versions; ETag/If-Match; trash/restore | Conflict428/412, đọc version cũ, quota tất cả versions, body cap/validation không phản chiếu nội dung riêng |
| P1.5 | Export snapshot ZIP; manifest/hash; import dry-run + xác nhận một lần; không overwrite | ZIP bomb/symlink/traversal/extra script guards, actor/expiry/revision/hash, atomic rollback; real UI roundtrip |

Migrations additive0025–0028. Local database `pao_acos_local` revision0028,
`BRAIN_MANAGER_ENABLED=true`. OpenAPI160operations/70ORMtables. UI Knowledge
giữ Memory/Brands cũ và thêm Brain Manager/Files/Notes/import-export.

## Kết quả nghiệm thu

- Full cuối: **424 backend tests passed,0 skipped,368.28s** trên pao_test/Redis15.
  Real ARQ recovery between74.06s/during96.64s, một tool claim cho mỗi tình huống.
- Runtime/SSE **8/8**; TypeScript đạt; production build **18 pages** đạt trong
  build directory riêng, không phá dev cache đang dùng.
- Browser với **FastAPI thật** trên port18100: login, tạo Brain, upload/plain
  preview, notes/version, export/import dry-run/confirm, trash/restore đạt.
  Fixtures synthetic chỉ pao_test/Redis15; không worker/model/provider/integration.
- Backup browser fixtures restore DB mới: tất cả **70table hashes** giữ nguyên,
  **2files/3note versions** bytes/SHA/size khớp, database local không đổi.
- Migration0025→0028→0025→0028 trên restored DB: hash66tables đã có giữ nguyên.
  P1.1 đã kiểm0024→0025→0024→0025 tương tự; không backfill run/history cũ.
- Sau rollout: API `/health` và `/ready`, Web trả **HTTP200**, workerhealthy;
  Telegram bridge disabled; live full OpenAPI khớp saved contract, fresh/API source
  binding `872289e6d9650c7848cf69267667e677e14bb12b0e9208d6fbac252f88f83c8b`.
  **3/3 artifact M2 cũ** replay HTTP/hash đúng. Alembiccheck không có upgrade mới.
- Local active jobs0, không có Memory/Ads/Automation/Task attempt đang chạy.
- Browser regression12routes hiện có đạt với mock fixtures (không thay thế real
  Brain API acceptance ở trên). `git diff --check` đạt, `.env` vẫn ignored,
  protected Apex Git status sạch; port18100 test API không còn listener.

Xem [progress](P1-PROGRESS-2026-10-06.vi.md) cho lỗi ban đầu và các rerun;
không tính các lượt lỗi là PASS. Launcher PID cũ có StartTime null đã sửa
fail-safe và từ chối duplicate start nếu port bị chiếm bởi process không xác minh.

## Cách thử cho người mới

1. Mở `http://127.0.0.1:3200/`, đăng nhập bằng tài khoản local hiện có.
2. Vào Knowledge → Brain Manager → nhập tên, bấm Tạo Brain.
3. Upload `.txt`/`.md` tối đa1MiB hoặc tạo note; Preview chỉ hiển thị chữ.
4. Sửa note → Lưu phiên bản; có thể đọc lại version trước. Trash có thể Restore.
5. Export portable ZIP là bản sao tài liệu hiện tại. Import ZIP → xem dry-run →
   tích xác nhận → import. Không tự thay thế file/note đang có.
6. Có thể gắn Brain với hội thoại không có run đang chạy. **Chat chưa đọc files/
   notes này**: đó là P2, không cần mua API key để dùng quản lý tài liệu P1.

## Giới hạn và phần chưa hoàn tất

- Chưa PDF/images, parser/OCR, antivirus hay persistent quarantine jobs. Validation
  trong memory trước commit; không URL fetch, filesystem extract hay thực thi code.
- Brain10MiBquota gồm files/trash/toàn bộ note versions; note≤256KiB UTF-8,
  typed request≤512KiB; ZIP≤12MiB, expanded≤10MiB. Đây là local MVP, chưa benchmark
  dung lượng lớn hoặc nhiều người dùng production.
- Portable export chỉ active files/current notes, không versions/trash/legacy
  memory/grants/config/credentials. Full DB backup mới giữ toàn bộ lịch sử/trash.
  Người dùng có thể upload thông tin riêng; không có DLP và không bảo đảm nội dung
  export không chứa secret do người dùng tự đưa vào.
- ACL riêng vẫn áp dụng; workspace owner không tự đọc Brain của người khác.
  Grant files/notes không mở legacy facts. Xóa workspace membership có grant cần
  revoke grant trước; chưa triển khai workspace-leave UX.
- P0 Task progress/lock-order/ORM-default debts và phần boundary extraction còn
  dở không được coi là đã sửa bởi P1. Không đổi runtime hay vendor Javis.
- **P2/RAG/graph và M4 chưa triển khai.** Production reboot/service24-7/cold restore
  còn pending vì chưa VM/VPS riêng; GitHub CI chưa được chạy từ remote.

## Backup và rollback an toàn

Private checkpoints nằm `.runtime/checkpoints/`, source ZIP/DB dump có hash;
Checkpoint sau rollout đã verify:
`.runtime/checkpoints/p0-20261006T082759-b7d0d1e2/manifest.json`,
474sourcefiles/71DBtables/3artifacts/revision0028. Sau ghi nhận báo cáo này, tạo
thêm final checkpoint chứa chính báo cáo và roadmap cập nhật; xem manifest mới
nhất trong cùng thư mục. Prefix `p0-` là format script cũ, không có nghĩa DB còn0024.
credentials bị loại khỏi source snapshot, khóa JWT/encryption cần lưu riêng ở nơi
an toàn. Dumps chứa dữ liệu riêng, không upload công khai. Byte-exact fixture
restore không thay thế production cold-machine restore.

Nếu cần rollback: dừng tạo run/write mới, kiểm idle, backup trước, dừng đúng API/
worker process tree. Tắt Brain flag **không tự fallback custom session sang memory
cũ**; custom session fail-closed. Giữ schema additive ưu tiên; chỉ downgrade/restore
trên DB tạm đã xác minh sau khi có phê duyệt, không drop bảng để “sửa nhanh”.
Không reboot/factory reset/delete volume. Các socket Docker lỗi đã được đổi tên
giữ phục hồi trong AppData runtime, không xóa dữ liệu Docker.

Bước kế tiếp đề xuất: **P2.1 Sources/ingestion có nguồn và ACL**, cần người dùng
duyệt checkpoint riêng; P1 này không tự khởi công P2.
