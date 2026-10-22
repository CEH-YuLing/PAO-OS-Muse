# P2.1 — Source provenance và text ingestion

Ngày06/10/2026, target `F:\PAO-ACOS`, P2 được người dùng cho phép. Triển khai
theo từng gate, không coi P2.1 là đã hoàn tất P2.2–P2.6.

## Quyết định

- Giữ modular monolith; thêm `pao.modules.knowledge` gồm API/schemas/service/worker.
  Không thêm database, thư viện parser, scheduler hay engine mới.
- P2.1 chỉ UTF-8 text/Markdown đã qua P1 file/note service. Không URL fetch,
  PDF/OCR/image/binary, filesystem extract, shell hay LLM. HTML/Markdown nằm
  trong source là chữ, không là chỉ dẫn; parse không render hay execute.
- Source có đúng một origin file hoặc note trong cùng Brain/workspace. Composite
  foreign keys bảo vệ scope ngay trong DB, pointer origin không thể cập nhật.
  File original immutable. Note cập nhật tạo content version mới, không sửa bản cũ.
- `knowledge_versions` giữ hash/size/origin-version/title tại thời điểm capture;
  không copy raw bytes vào một kho authority khác. Metadata versions bất biến.
  Dedupe trên source+content hash; nội dung revert trùng có thể dùng lại version
  trước. Hai tài liệu khác nhau cùng hash vẫn là hai source/provenance độc lập.
- `knowledge_ingestion_jobs` unique(version_id,parser_version), parsed text là
  derived output. Parser pinned `utf8-lines-v1`: bỏ UTF-8 BOM, chuẩn hóa CRLF/CR
  thành LF, giữ nội dung còn lại. Source hash là raw origin; parsed hash là UTF-8
  text sau parse. Không diễn giải Markdown thành HTML. Line locator bắt đầu từ1.
- API commit job trước; Redis chỉ vận chuyển. ARQ dispatcher scan queued mỗi10s,
  chạy cùng worker hiện có max_jobs1. Không enqueue trực tiếp qua HTTP: Redis
  outage không mất job DB; dispatcher thử lại. Job execution không gọi provider.
- Claim UUID+attempt fencing; parse≤20s, expired lease60s; bounded3attempts.
  Claim/commit theo thứ tự Brain→job để đồng nhất API locks; recovery chỉ lock
  job và không chờ Brain. Redis job id có attempt suffix, stale worker không
  overwrite recovered job. Failed cần retry rõ ràng; exhausted không reset vô hạn.
- Kiểm user active, workspace member/write, explicit Brain owner/editor, Brain
  và Source archive, origin trash/hash **trước và sau parse**. Reader chỉ đọc;
  workspace viewer không được ghi dù có editor grant. Grant không mở legacy facts.
- Source không tự refresh khi note sửa. List báo stale; user refresh tạo/reuse
  version và job. Old preview vẫn đọc đúng origin version sau refresh, nếu scope
  còn quyền và origin chưa trash. P2.3 retrieval phải lọc stale/current/ACL tại
  thời điểm truy xuất, không dùng preview lịch sử làm current evidence mặc định.
- Source archive không xóa origin/version/job; preview chặn archive/trash. Mọi
  đọc cần ACL hiện hành. Không làm mất bytes khi index/parser có lỗi.
- ≤1000sources/Brain, ≤100uniquecontentversions/source, list pagination≤100,
  jobs list100; preview≤200lines/16KiB, không đưa toàn source vào prompt.
  Derived output một parser/version có kích thước không lớn hơn origin đã tính
  quota P1. Parser mới/reindex nhiều phiên bản phải có derived-storage budget riêng.
- `knowledge_sources_enabled=false` mặc định; P1 Brain flag vẫn là dependency.
  Chat/RAG/embeddings/Wiki/graph **không bật trong P2.1**. Không tăng quyền tool,
  business integrations, cloud providers, Telegram hay public deployment.

## Schema và compatibility

Migration0029 thêm3tables; thêm unique keys scope cho brain_files/brain_notes,
không backfill/move/update row cũ. Existing APIs160operations/schemas giữ nguyên;
11API mới dùng schema tên KnowledgeSource để không xung đột Attribution Source.
Contract generated theo script hiện có, không sửa tay types.

## Gate và rollback

Backup private trước thay đổi; idle0; chỉ dừng process tree API/worker đã xác minh
PID/starttime/path. Upgrade/downgrade/re-upgrade trên restored DB trước local.
Tests chỉ pao_test/Redis15; browser dùng test API18100+Source-only ARQ queue riêng.
Production reboot/cold restore/24-7 vẫn pending; không tự reboot host.

Nếu có lỗi: tắt Sources flag, không fallback sang đọc ngoài Brain. Job DB giữ
queued/running để recovery khi bật lại; idle gate tính cả Source jobs. Ưu tiên giữ
schema additive và backup; không drop bảng/mất source versions để sửa nhanh.
Downgrade0029 làm mất derived metadata/job, cần phê duyệt và backup/restore drill.

## Nợ kỹ thuật ghi nhận

ARQ installed Windows `close()` dùng SIGUSR1 không tồn tại khi handle_signals=False.
Test explicit SIGTERM portable rồi pool cleanup; không sửa package cài. Chưa
khẳng định graceful production shutdown Windows. Warning deprecated Redis.close
trong ARQ vẫn có; không che hay nâng dependency chỉ để loại warning.
Source UI local MVP hiển thị100 nguồn đầu; pagination API có, UI pagination chưa có.
Thêm parser/PDF/OCR, semantic chunks/citations, embeddings, Wiki publish/review và
conversation attachments là checkpoint sau, không suy ra đã có từ preview này.
