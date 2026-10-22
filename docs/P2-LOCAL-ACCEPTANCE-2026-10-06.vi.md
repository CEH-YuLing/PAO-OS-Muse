# P2 — nghiệm thu local text/Markdown (06/10/2026)

**Trạng thái: P2.1–P2.6 đạt LOCAL MVP text/Markdown.** Không phải nghiệm thu
semantic model thật hoặc production. M4/P3 không triển khai trong lượt này.

## Phạm vi đã triển khai

P2.2 chunk/citation/local embedding queue + FTS fallback; P2.3 scoped retrieval
và grounded-excerpts chat opt-in; P2.4 Wiki draft/edit/diff/review/publish/revert;
P2.5 graph wikilink dẫn xuất; P2.6 upload/links/evidence artifact download.
Giao diện tại `/knowledge` và `/pao-ai`, không thay các interaction cũ.

## Chứng cứ đang có

- 18tests P2 bản cuối đạt, gồm SSE thành công/revoke, claim fencing, quota
  reactivation, injection/conflicting/missing evidence và không gửi đoạn nguồn
  qua history cho provider sau khi tắt opt-in. Full bản cuối **464passed/0skip,
  408.22s**, runtime/SSE **8/8**, TypeScript đạt. Một warning deprecation ARQ
  `close` (dependency), không che hoặc tắt warning. Các lượt460/463 trước sửa
  SSE là lịch sử, không dùng làm proof bản cuối.
- 171API/schema cũ giữ nguyên; thêm24API, tổng195.
- 73table cũ giữ nguyên hash qua0029→0030→0029→0030 trên DB phục hồi riêng.
- Production build18pages bản cuối đạt; TypeScript hợp lệ.
- Browser/API/ARQ/SSE thật đạt index/retrieval/citation/plain-render/Wiki
  draft/review/edit/diff/publish/revert/graph/chat opt-in/attachments/evidence
  download/non-destructive removal. API18100/Redis15/pao_test riêng; đã dừng
  đúng process test. Không ghi fixture vào DB local.
- Full fixture restore80tables giữ nguyên hashes;2chunk,2Wiki versions,
  5Wiki events,1attachment,1RunKnowledge. Dump private:
  `.runtime/p2-browser-29da6db483d143ef997c7ed2e89fb5b8.dump` (bản backend cuối).
- Ollama live có model chat Qwen; embeddinggemma:300m trả404, chưa cài. Không
  tự download; semantic path được test bằng vector fixture, local hiện dùng FTS.

## Live rollout và checkpoint

LocalDB migration**0030**,80ORMtable/81DBtable tính cảAlembic;
`BRAIN_MANAGER_ENABLED`, `KNOWLEDGE_SOURCES_ENABLED`, `KNOWLEDGE_ENABLED` bật.
API health/ready và Web3200 đều**HTTP200**, Worker**healthy**;
full live OpenAPI khớp saved195operations, replay**3/3** artifact M2 cũ đạt.
Execution binding `exact-backend-source-v1`:
`b3eb90edcc91ff42739bba4e839edaa75d17246175e8d4b769b02a82e5c818e2`.
Idle tất cả**0**, bao gồm parse/indexjobs. Ads/Google/Telegram/Temporal/autopilot
giữ tắt qua safe-repair gate; không bật cloud provider mới, không public deploy.
API/worker đã khởi động lại đúng bản; Web/Ollama hiện có được giữ nguyên.
Checkpoint cuối dùng `scripts/backup_acos_checkpoint.py` (manifest private dưới
`.runtime/checkpoints/`), không chứa .env/Git/dependencies/builds trong sourceZIP;
DB dump nhạy cảm cần giữ riêng, không share/public. Protected F:\Apex\apex git status sạch; diff check không lỗi
whitespace (Git chỉ cảnh báo CRLF theo cấu hình Windows).

## Lỗi đã phát hiện và sửa trong nghiệm thu

Gắn lại attachment từng gỡ phải kiểm tra quota như thêm link mới. Checkbox nguồn
chat cập nhật UI ngay nhưng khóa gửi đến khi server xác nhận, rollback UI nếu
API lỗi. SSE enum cũ không chấp nhận event mới: dùng `plan.created` với metadata
`knowledge_retrieval` và lưu RunKnowledge; không đổi schema/enum cũ. Có test happy
path SSE để regression không chỉ kiểm tra DB response. Browser runner chờ
hydration và xử lý abort/close cleanup, không in bearer header trong lỗi.
History đưa cho provider loại bỏ message thuộc run Knowledge; tắt opt-in không
vô tình chuyển đoạn nguồn cũ sang cloud. UI vẫn giữ lịch sử cho owner được phép.

## Dùng thử sau khi local flag bật

1. Vào `/knowledge`, tạo/chọn Brain và upload .txt/.md hoặc viết note.
2. Trong Sources, chọn origin và đăng ký; chờ parse completed, xem trạng thái index.
3. Tìm trong nguồn, xem đoạn trích, version/dòng và kiểm tra citation.
4. Tạo Wiki draft, đọc/sửa/lưu bản mới; tick đã duyệt rồi publish. Có diff và
   revert bản đã từng publish; stale sẽ chặn promote.
5. Viết `[[Tên note/Wiki]]`, xem/rebuild Graph; link thiếu được báo unresolved.
6. Tạo/chọn hội thoại, gắn Brain tại Knowledge. Vào `/pao-ai`, mở Nguồn trong
   chat và bật opt-in; chọn toàn Brain hoặc attachments, upload nếu cần.
7. Chờ index, hỏi theo tài liệu, kiểm tra citation và tải evidence JSON.
   Tắt nguồn để trở lại chat model bình thường. Không tự gửi nguồn qua cloud.

## Giới hạn không giấu

Grounded chat trích nguồn, chưa LLM synthesis. PDF/OCR, Git Brain sync, semantic
benchmark trên model thật chưa nghiệm thu. Model thiếu không làm FTS bịa dữ liệu.
Embedding long docs có thể partial (16chunk/job). Graph tối đa200node/500link,
UI40node. ZIP P1 không thay full DB backup. Production reboot/24h vẫn pending
theo quyết định người dùng chưa có VPS/VM; không deploy công khai, M4/P3 chưa mở.
Chi tiết ràng buộc tại [ADR P2](ADR-P2-KNOWLEDGE-WORKSPACE.vi.md).
