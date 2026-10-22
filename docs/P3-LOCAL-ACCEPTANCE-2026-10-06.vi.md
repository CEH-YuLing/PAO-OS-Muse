# P3 — Nghiệm thu Engine/Context/Chat/Usage LOCAL MVP

Ngày 06/10/2026, workspace `F:\PAO-ACOS`. **P3.1–P3.7 đạt LOCAL MVP** trong
phạm vi/gate dưới đây. Không đồng nghĩa production24/7, cloud thật hoặc Javis
feature parity. M4 chưa mở; source `F:\Apex\apex`/`F:\Javis OS` không sửa.

## Những phần đã triển khai

| Phần | Kết quả |
|---|---|
| P3.1 | Engine capability contract, session selection, immutable run pin, sanitized errors, no implicit fallback; giữ gate trước |
| P3.2 | Context compiler trước planner/specialist/final/extraction; budget UTF-8/estimated tokens, giữ nguyên prompt/references, loại nguyên history cũ hoặc fail |
| P3.3 | Extractive compaction cache có revision/IDs/hash, immutable UPDATE, source stale/revoked thì không dùng; giữ original history và metadata-only trace |
| P3.4 | local_only mặc định, cloud opt-in riêng + reference opt-in, chốt/recheck policy; không hồi tố quyền cho local history/Knowledge/Memory/intelligence; extraction pin Ollama local |
| P3.5 | 10 management commands có parser dùng chung, không shell/LLM cho thao tác quản lý; `/goal` chặn đến P6, Telegram parser integration chờ P7 |
| P3.6 | PostgreSQL full-text/GIN, pin/group, authenticated Markdown export, P1/P2 text attachment safety, retry run mới có parent/idempotency, giữ history |
| P3.7 | Durable scoped attempts/reservations, reported/estimated/unknown riêng, callback replay không double count; optional versioned/bound pricing, cross-worker local inference cap1 |

Đọc [ADR P3](ADR-P3-CONTEXT-CHAT-USAGE.vi.md) để xem giới hạn/ngữ nghĩa cụ thể.

## Bằng chứng kiểm thử

- Full backend regression cuối: **514 passed, 0 skipped, 423.66s**; trước đó
  509 passed/468.05s. Một ARQ dependency DeprecationWarning (không failure).
- Sau bổ sung final guards/metadata/usage mocks: **74 focused tests passed,
  35.83s**, gồm P3, compiler, engine contract, app factory, gateway và model router.
  Có5 ca bổ sung ngoài full514; không gọi kết quả này là full519.
- Runtime/SSE **8/8**, TypeScript noEmit đạt, production build **18 pages**
  hoàn tất bằng `.pao-build-check`, không phá dev cache. Mock UI **12 routes** đạt.
- Browser P3 với test API18100/ARQ/Redis15/SSE, gateway tổng hợp: pin/group,
  privacy config, search, export download, compaction versions, commands,
  usage và retry tới UI terminal đạt. Screenshot `.runtime/p3-live-ui.png`.
- Restore fixtures P3: **82 bảng dữ liệu** giữ nguyên mọi row hash,
  5 completed runs,1 retry parent,1 compaction,10 attempts (5 reported/5 unknown).
  Chỉ database UUID tạm do checker tạo bị drop; dump được giữ trong `.runtime`.
- Browser Knowledge cũ chạy lại đạt: index/search/citations/plain text renderer,
  Wiki review/edit/diff/publish/revert/graph, opt-in chat/attachments/evidence.
  Restore82bảng giữ nguyên hash; không bật source embeddings thiếu model.
- Migration trên bản phục hồi riêng: **0031→0032→0031→0032** đạt;
  **80 bảng cũ** giữ nguyên row hashes, **199 operations + mọi schema cũ**
  không đổi. Source database không bị migrate trong drill. Sau đó rollout
  database local0032; Alembic check không phát hiện drift.
- Test âm: privacy không cho cloud call trước consent, compiler từ chối local
  references/private intelligence, thiếu usage ở strict policy/vượt call budget
  không success, cancel đóng stream và ghi partial, cache sửa/stale bỏ qua,
  replay usage không cộng lại, command không tạo model run, local cap chặn call2
  và giải phóng sau cancel. Cloud structured usage chỉ kiểm HTTP mocks.

## Ollama thật, chỉ dữ liệu tổng hợp

Model có sẵn `qwen3:4b-instruct-2507-q4_K_M`, loopback Ollama. Không download
model mới, không provider cloud. Paired benchmark cùng model/prompt/fact, compiler
loại lịch sử placeholder cũ; giữ fact cần trả lời.

| Ca | Trước → sau context bytes | Trước → sau reported input | TTFT ms trước → sau | Latency ms trước → sau | Đúng |
|---|---:|---:|---:|---:|---|
| Approved budget250 | 3802→917 | 707→177 | 54764→4984 | 55405→5953 | cả hai |
| Project PAO-ACOS | 3782→897 | 705→175 | 2420→1844 | 3843→2827 | cả hai |

Estimated input cũng được ghi riêng:2093→531 và2083→521; output reported4 và6.
Queue wait0 là **serial idle benchmark, không đo task queue**. Ca đầu có cold/warm
cache; không khẳng định tốc độ tăng tương ứng hoặc chất lượng tổng quát. Corpus
chỉ2ca recall, không thay cho đánh giá tác vụ kinh doanh. Report riêng
`.runtime/p3-context-benchmark.json`; helper `scripts/benchmark_p3_local.py`.

Luồng API→runtime→planner→final thật, workspace tổng hợp riêng trong **pao_test**:
run completed, trả PAO OK,2attempts đều reported. Planner input234/output21,
elapsed37280ms; final input203/output4, TTFT4780ms/elapsed5436ms. Không cloud,
tools hay Memory. Helper `scripts/check_p3_ollama_runtime.py` chỉ nhận pao_test/
Redis15, không dùng hội thoại thật. Chưa chứng minh native tool compatibility
hoặc mọi specialist trên model này.

## Rollout và trạng thái local

- `ENGINE_CONTRACT_ENABLED=true`, `CHAT_FEATURES_ENABLED=true` trong `.env`
  local sau gate; `.env.example` vẫn mặc định false. Secrets không sửa/in.
- API rootPID15012, worker rootPID2256 do launcher tạo, Web/Ollama được giữ.
  Health: API/ready/Web **HTTP200**, ARQ worker **healthy**.
- Revision0032, **30 routers/210operations/82ORMtables/83physicaltables**
  (physical gồm Alembic). Full live OpenAPI khớp saved contract.
- Current exact-backend binding:
  `c1d68a8ad64dee80142da7c712e6e675670a5251c8692d9a9232035287dee2da`.
  **3/3 artifacts M2 cũ replay đạt**, không re-execute historical artifacts.
- P3 live GET/profile/usage/help được kiểm non-mutating, local_only mặc định;
  không tạo run/provider call trong database local. Tất cả active job counts0.
- Meta/Google Ads/Telegram/Temporal vẫn tắt. Production reboot gate vẫn false.

## Cách dùng đơn giản

Mở `http://127.0.0.1:3200/pao-ai`, tạo/chọn hội thoại, mở **Hội thoại · quyền
riêng tư và usage** dưới khung chat. Có thể ghim/đặt nhóm, tìm, export, compact,
xem context trace/usage và thử lại run mới. Gõ `/help` để xem10lệnh. `/brain UUID`
và `/model provider model` đi qua guard hiện có; `/tasks` chỉ việc do mình tạo;
`/memory` chỉ private legacy facts được phép xem, custom Brain knowledge dùng
Knowledge panel. Bật cloud consent không tự cấu hình key/provider.

Giá tùy chọn cấu hình qua profile API, không auto-fetch giá nhà cung cấp. Usage
UI hiện latest100 attempts, không giả tổng usage trọn đời hoặc quota thuê bao.
Compaction là đoạn trích chọn lọc, chưa phải semantic LLM summary. CLI, voice,
multi-channel, PDF/vision, goal runner và production nằm ngoài P3 local.

## Backup và gate còn ngoài phạm vi

Backup cuối dùng `scripts/backup_acos_checkpoint.py`, source zip loại secrets,
runtime/dependencies/builds/Git; database dump thử restore trước xác nhận.
Manifest cuối được ghi sau khi tài liệu hoàn tất. Giữ khóa encryption/JWT ngoài
source backup trong quy trình phục hồi riêng. Chưa commit/push Git; giữ nguyên
các thay đổi P0/P1/P2/P3.1 đang có. VM/VPS reboot/cold restore, GitHub remote CI
và production24/7 còn pending theo lựa chọn của người dùng.

Bước kế tiếp theo roadmap là **P4 Agent/Skill/Workflow Studio có review**,
chỉ triển khai khi người dùng yêu cầu; không tự mở M4.
