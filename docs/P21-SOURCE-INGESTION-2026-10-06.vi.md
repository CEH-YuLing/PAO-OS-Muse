# P2.1 — Source/version/hash và durable ingestion

**P2.1 LOCAL đã đạt ngày06/10/2026. P2 chưa hoàn tất toàn bộ.**

Target `F:\PAO-ACOS`; người dùng cho phép P2. Triển khai theo nguyên tắc một
checkpoint rồi nghiệm thu, chưa gọi toàn bộ P2 hoàn tất.

## Chuẩn bị và thay đổi

- Idle0/external gates tắt, pre-change checkpoint verified:
  `.runtime/checkpoints/p0-20261006T085016-ec509841/manifest.json`,
  474sourcefiles/71DBtables/3artifacts/revision0028. Chỉ dừng đúng API/worker
  process tree từ record starttime/path; Web/Ollama giữ nguyên.
- Module Knowledge riêng; migration0029/3tables, origin compositeFK/immutable
  metadata; Source text/Markdown/File/Note; source versions/dedupe/hash;
  durable parse job/claim fencing/retry3/lease recovery; no provider/parser execution.
- UI Sources trong Brain: register/refresh/archive, trạng thái queued/running/
  completed/failed/stale, retry, preview version+lines/hash plain text.
- Sources flag mặc địnhfalse; RAG/embeddings/Wiki/Graph chưa triển khai.
  [ADR đầy đủ](ADR-P21-SOURCE-INGESTION.vi.md).

## Lịch sử kiểm chứng trước rollout

- Focused lần đầu25passed; thêm RBAC/quota/realARQ thành28cases.
- Real ARQ job đã completed, nhưng focused27passed/1failed tại cleanup Windows
  do SIGUSR1 thiếu. Đọc code ARQ installed, sửa test explicit SIGTERM rồi cleanup
  connections; rerun **28passed,1deprecation warning,24.28s**. Không sửa package
  hoặc skip delivery test.
- Contract đầu bị tên SourceInput/SourceOut trùng Attribution làm OpenAPI ref đổi.
  Đổi tên KnowledgeSource*, regenerate, kiểm **160 APIs+schemas cũ nguyên vẹn**,
  chỉ thêm11APIs. Không coi lượt contract lỗi là PASS.
- Migration0028→0029→0028→0029/check trên DB phục hồi mới PASS,
  hash70legacytables giữ nguyên, source local không đổi. Dump private:
  `.runtime/p21-pre-be3b0646c9044d8ca4da6f8131830100.dump`.
- Frontend production build18pages PASS, build directory riêng.
- Full backend/real ARQ wall-clock/runtime/TypeScript đang chạy; local DB vẫn0028,
  Sources flag chưa bật. Real UI+API+Source-only ARQ và fixture restore là gate
  riêng sau full regression, không chạy concurrent vì cùng pao_test.

## Phần còn lại của P2

| Checkpoint | Trạng thái |
| --- | --- |
| P2.1 source/version/hash/parser jobs | Đạt local ngày06/10/2026 |
| P2.2 chunks/citations/local embeddings/rebuild/full-text fallback | Chưa triển khai |
| P2.3 scoped retrieval/context/RAG evidence tests | Chưa triển khai |
| P2.4 Wiki draft/review/diff/publish/revert/stale | Chưa triển khai |
| P2.5 wikilink derived graph/ACL/unresolved nodes | Chưa triển khai |
| P2.6 conversation attachments/provenance | Chưa triển khai |

Không M4, không Ads/Telegram/email thật, không Git push/commit hay public deploy.
Production reboot/24-7/cold machine restore vẫn pending như người dùng đã chọn.

## Nghiệm thu cuối

- Full **446 backend passed,0skip,395.58s**, một ARQ/Redis deprecated-close
  warning còn ghi rõ, không che. Real ARQ wall-clock between70.84s/during96.64s,
  một tool claim/bài; **runtime8/8 và TypeScript đạt**.
- Frontend build18pages đạt; browser12routes mock đạt (không thay real API gate).
- Real browser+FastAPI18100+Source-only ARQ queue Redis15: Source registration,
  dedupe, raw/parsed hash, plain line preview không execute script, Note stale/
  explicit refresh, đọc v1/v2 đúng nội dung đạt. Chỉ synthetic pao_test, không gọi
  local/cloud model hay integration. Cả test API và worker được dừng đúng own tree.
- Browser fixtures backup→restore DB mới: hash**73tables** nguyên vẹn, 2sources,
  3sourceversions,3completedparsejobs, parsed text bytes/SHA đúng. Source local
  không thay đổi. Dump `.runtime/p21-browser-03688488b80f4a7ba8f8cdccc236d287.dump`.
- Real browser P1 CRUD/files/versions/export/import/trash rerun đạt sau thêm
  Sources; fixture restore73tables/2files/3noteversions bytes+hash đạt.
- Gate cuối migration/contract rerun đạt:160existingoperations+schemas nguyên
  vẹn, thêm11Sourcesoperations;70legacytablehashes không đổi qua
  upgrade/downgrade/re-upgrade. Dump `p21-pre-532070db25d74e78b51dd706ab1f44e6.dump`.
- Local idle0 trước rollout, nâng DB**0029**, bật **KNOWLEDGE_SOURCES_ENABLED=true**.
  APIhealth/ready/Web200, workerhealthy, Telegrambridge disabled. Live171operations
  contract khớp saved/source, Sources status/list authenticatedGET đạt/RAGfalse.
  Binding `8a6f7b5f26967394e8e4fe0693c3718929e9409c52dd1911f8354d9c90d1314c`,
  replay3/3artifacts M2 cũ giữhash; Alembiccheck không lệch ORM.
- Activejobs vẫn0, gồm source_ingestion_jobs. Không tạo source trong DB local
  của người dùng để “thử”; workflow writes đã kiểm trên pao_test.
- `git diff --check`/launcher syntax đạt; protected Apex Git status sạch.
  Không commit/push; credentials chỉ local ignored, source backup không mang .env.

## Cách dùng

1. Mở http://127.0.0.1:3200/ → đăng nhập → Knowledge → chọn/tạo Brain.
2. Upload `.txt/.md` hoặc tạo Note bằng P1 trước.
3. Trong Sources, chọn File/Note và origin → Đăng ký nguồn.
4. Job sẽ queued rồi completed; bấm Tải lại Sources để cập nhật. Worker quét
   mỗi10s, không cần cloud API key. Nếu failed xem job/error và Retry tối đa3attempts.
5. Chọn source → Preview source version: chữ thuần có source hash/parser/line range.
6. Sửa Note khiến source stale; Refresh source để capture bản mới. Source version1
   vẫn đọc nguyên nội dung cũ, trừ khi mất quyền/origin trash/source archived.

**Chưa hỏi chat về nguồn này được:** chunking/embeddings/RAG thuộc P2.2/P2.3.
Wiki/Graph/attachments chưa có. Phạm vi này là text/Markdown, không PDF/OCR.
UI100sources đầu; pagination API có nhưng UI pagination chưa triển khai.

## Backup / rollback

Checkpoint private sau cập nhật docs được tạo bằng backup_acos_checkpoint.py,
verify DB restore/source hashes; xem manifest mới nhất `.runtime/checkpoints/`.
Prefixp0 là format checkpoint lịch sử, không chỉ revision0024. Dump có dữ liệu
riêng, không public upload. Encryption/JWT keys cần giữ riêng cho cold recovery.

Tắt Sources flag không xóa job/source hay tự mở ACL khác; cần kiểm idle trước
restart, queued jobs vẫn ở DB khi flag tắt. Giữ additive schema ưu tiên. Downgrade
chỉ sau backup/phê duyệt/restore drill, không drop nguồn để sửa nhanh. Chưa chứng
minh production reboot/24-7 hay graceful ARQ shutdown Windows.

Bước tiếp theo của P2: **P2.2 chunking/citations/embeddings local và fallback**.
