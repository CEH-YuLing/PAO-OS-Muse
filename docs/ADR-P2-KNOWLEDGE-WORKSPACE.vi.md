# ADR — P2 Knowledge workspace (06/10/2026)

## Quyết định và phạm vi

Giữ PostgreSQL là authority, FastAPI/service là nơi kiểm tra quyền, ARQ là hàng
đợi dẫn xuất. Không thêm SQLite, vector server, framework agent hoặc provider
cloud. P2 dùng nguồn UTF-8 .txt/.md đã được P1/P2.1 kiểm tra; PDF/OCR là một
checkpoint riêng, không coi file PDF là nguồn đã parse được.

Migration0030 bổ sung7table và2cột session, không chuyển/xóa/backfill dữ liệu cũ.
API thêm24operation; các171operation/schema P2.1 phải giữ nguyên. Các module
`knowledge/index.py`, `retrieval.py`, `workspace_api.py`, `conversations.py`
chịu trách nhiệm riêng; runtime chỉ gọi nhánh opt-in và dispatcher.

## P2.2 — Index

`chars1800-v1`: tối đa1800ký tự/chunk,600chunk/source, offset char/line, SHA-256,
UUID xác định theo version/chunker/ordinal. Nguồn gốc/version bất biến; reindex
không sửa file/note hoặc ID chunk. DB lưu vector768 cùng model tag; chỉ mục
không phải authority. Job unique(version,chunker,model), claim fencing,
lease60s, tối đa3attempt và kiểm tra actor/ACL/hash trước và sau tính toán.

Embedding chỉ chấp nhận endpoint loopback, vector finite/nonzero/đúng768 chiều;
timeout2s/request, budget18s và tối đa16chunk/job. Nguồn dài báo partial;
model vắng/offline vẫn hoàn tất lexical index và trả degraded full-text.
Không tự tải model; không chuyển tài liệu sang workspace model/cloud router.
Giới hạn này tránh giữ GPU/CPU của máy lâu, không phải semantic indexing toàn
bộ mọi tài liệu. Muốn semantic coverage lớn cần checkpoint benchmark/tuning.

## P2.3 — Retrieval / grounded chat

Lọc Brain/user/brand, source hiện tại, trash/archive và SHA origin trước ranking.
Full-text PostgreSQL/simple + normalized keyword fallback; vector chỉ cùng model.
Tối đa8chunk,3document,8192byte evidence; API query tối đa1000ký tự,30query/phút.
Recheck quyền/origin bằng session DB mới sau embedding I/O trước disclosure.
Citation chứa source/version/hash/chunker/offset; mở citation kiểm tra raw version
và text slice. Historical citation còn đọc được nếu người dùng vẫn có quyền và
source chưa trash/archive; retrieval chỉ dùng version hiện tại, không stale.

**Chế độ MVP là grounded excerpts**, trả đoạn trích nguyên văn có citation,
không phải LLM tổng hợp/suy luận tự do. Không đủ nguồn trả thiếu bằng chứng;
số liệu khác nhau báo cần đối chiếu, không tự xác định chính sách đúng.
Nội dung chứa lệnh được coi là dữ liệu; nhánh này không chọn skill, gọi tool,
provider hoặc tự extract Memory. Chat mặc định giữ hành vi cũ; từng session
phải opt-in, scope `brain` hoặc `attachments`, pin scope/fileIDs vào run.
Các message của run Knowledge không dùng làm history cho provider khi tắt
opt-in; tránh gửi đoạn nguồn local cũ sang cloud qua một lượt chat thường sau đó.
Sau revoke, API history/run/SSE/evidence không trả lại đoạn nguồn; không thể
thu hồi byte người dùng đã đọc/tải trước đó.

## P2.4 — Wiki

Draft từ1–8chunk có nguồn; không auto-publish. Bản sửa có version/SHA/citations
bất biến, revision conflict, publish bản đã lưu mới nhất sau review explicittrue.
Revert chỉ bản đã từng publish và nguồn vẫn current. Source đổi/trash/archive
làm Wiki stale, chặn promote và loại Wiki khỏi graph. Event draft/edit/publish/
revert append-only. Quota100Wiki/Brain,50version/Wiki,64KiB/version,
10MiB toàn bộ history/Brain. Nội dung người duyệt sửa không tự được xác minh
đúng về ngữ nghĩa chỉ vì có citation; trách nhiệm review vẫn thuộc người dùng.

## P2.5 — Graph

Derived view của note active và Wiki published không stale trong Brain được
phép: tối đa100note+100Wiki,500edge/unresolved; UI vẽ tối đa40node. `[[wikilink]]`
thiếu/trùng tên báo unresolved, không lookup Brain khác hoặc bịa node. Rebuild
không sửa original; checksum ổn định. Không coi graph là authority/retrieval index.

## P2.6 — Attachments / artifacts

File upload dùng service P1: .txt/.md UTF-8,1MiB/file,10MiB/Brain tính cả trash.
Session tối đa10link active; raw upload recheck Brain/version sau I/O và commit
file/source/job/link trong cùng transaction. Gỡ chỉ soft-remove link, không xóa
file. Không đổi context trong queued/running run. Evidence artifact JSON là
authenticated download, no-store/nosniff/CSP sandbox; UI render source/Wiki plain
text, không thực thi HTML/script. Portable Brain ZIP P1 chỉ files/notes active,
**không gồm Wiki/index/attachment/history**; muốn phục hồi đầy đủ dùng DB backup.

## Gate / rollout

Regression trên `pao_test` và Redis15; browser runner trênAPI18100 và queue riêng
chỉ parse/index/RAG. Không Ads/Telegram/email/cloud writes. Drill migration và
restore dùng database sinh tên riêng, không downgrade DB vận hành. Checkpoint
private gồm source allowlist không .env + full DB dump + hashes. Flag
`KNOWLEDGE_ENABLED` chỉ bật local sau gates; production reboot/24h chưa đạt,
không suy diễn P2 local thành production-ready. Không triển khai M4/P3 từ P2.
