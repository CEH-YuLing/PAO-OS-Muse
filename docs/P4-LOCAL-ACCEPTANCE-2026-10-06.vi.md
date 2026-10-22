# P4 — Agent / Skill / Workflow Studio

Trạng thái hiện tại: **P4.1–P4.6 đạt LOCAL MVP và đã bật Studio local**.
Chỉ làm việc tại `F:\PAO-ACOS`. Không sửa `F:\Apex\apex` hoặc `F:\Javis OS`,
không mở M4, không gửi email/Telegram, không gọi Ads hoặc deploy công khai.

## Những phần đã triển khai

| Module | Phần đã có |
|---|---|
| P4.1 | Ba bảng Studio, phiên bản/hash bất biến, audit append-only, lifecycle, optimistic revision, rollback |
| P4.2 | Agent editor, model preference/Brain scope, clone defaults, archive không xóa lịch sử |
| P4.3 | Skill JSON editor, schemas đóng/bounded, allowlist khai báo, timeout/token budget/generation cap, exit criteria, fixture, import dry-run/export |
| P4.4 | `/slug {JSON}` và `/skill slug {JSON}`, published-only, input validation, semantic shadow không thực thi |
| P4.5 | Một generation qua P3 ledger, strict reported usage, hard deadline, cancellation, kiểm tra output trước SSE delta |
| P4.6 | Workflow JSON/DAG editor, published version links, cycle/dependency/schema lint; không có workflow runner |

Studio nằm trên trang `/skills`, giữ nguyên M2 catalog/preview/replay. API dùng
12 operations mới dưới `/v1/studio`, tổng 222 operations, 31 routers. Có 85 bảng
nghiệp vụ trong ORM, cộng bảng Alembic là 86 bảng vật lý.

Xem [quyết định kiến trúc P4](ADR-P4-STUDIO.vi.md) để biết các giới hạn chính xác.

## Bằng chứng đã đạt

- Checkpoint trước P4: `.runtime/checkpoints/p0-20261006T141034-9a2b08eb/manifest.json`.
- Migration trên bản restore UUID: `0032 → 0033 → 0032 → 0033`, Alembic check
  không phát sinh chênh lệch; bảo toàn 210 operations và mọi schema API cũ,
  hash toàn bộ 82 bảng nghiệp vụ cũ (không tính bảng Alembic).
- Runtime/SSE 8/8 đạt. TypeScript và production build 18 trang đạt.
- Mock UI acceptance 12 routes đạt trên cổng 3200.
- Browser Studio với API/DB/ARQ/SSE thật, model giả lập: bootstrap 8 defaults,
  tạo/review/publish Agent và Skill, fixture schema, gọi `/p4-echo` thành công.
- Backup/restore fixture browser: hash 85 bảng giữ nguyên; 1 attempt reported,
  0 tool calls, 2 review events. Ảnh: `.runtime/p4-live-ui.png`.

## Gate cuối đã đạt

- Full backend regression sau sửa harness M2 để tiến trình con không kế thừa
  cờ feature bật từ `.env` của máy: **549 passed, không skip, 467.07s**. Lần đầu
  534 passed / 4 failed đã được sửa nguyên nhân; không bỏ qua recovery gate.
  Còn một warning deprecated close trong thư viện ARQ, không ảnh hưởng test.
- Ollama thật trên `pao_test`: qwen3:4b-instruct-2507-q4_K_M, một `studio_skill`
  attempt reported 276 input / 9 output tokens, TTFT 37.905s, tổng 39.515s;
  JSON schema và equals_input đạt, không tools. Một mẫu cold-start không phải
  benchmark hiệu năng hoặc chứng minh chất lượng mọi skill.
- 62 kiểm thử tập trung final đạt (Studio/factory/chat), bao gồm từ chối dùng
  seed mirror trực tiếp làm custom executable version; cần clone và review.
- Browser P3/restore đạt sau P4: 5 runs, 10 attempts, 1 retry, 1 compaction;
  hash 85 bảng giữ nguyên.
- Browser P2/restore đạt: retrieval/citations, Wiki review/publish/revert,
  graph, attachments và evidence download; hash 85 bảng giữ nguyên.
- Đã áp dụng revision `0033` và bật `STUDIO_ENABLED=true` trong `.env` local.
  API health/ready/Web đều HTTP200, worker healthy. Telegram vẫn disabled,
  production reboot gate vẫn false, không được coi là production-ready.
- Live OpenAPI khớp full contract; 3 archive M2 replay đạt. Exact backend source
  binding: `74de9c5f39687852ac816dc9efc1fabc008fcadc2aceef239df10ef408d512ba`.
- Live Studio bootstrap 8 seeds, lặp lại import=0; workflow execution false,
  các tích hợp bên ngoài vẫn tắt. Không tạo synthetic custom skill trong dữ
  liệu vận hành; ví dụ chạy model/browser nằm trên `pao_test`.

Checkpoint cuối được tạo sau tài liệu này bằng `backup_acos_checkpoint.py`,
manifest được lưu tại `.runtime/checkpoints`. Đây là checkpoint private, không
push backup database hoặc credentials lên Git.

## Cách sử dụng khi phát hành

1. Mở Skills → Studio; import defaults một lần. Defaults là mirror read-only.
2. Tạo Agent draft hoặc clone default. Validate, review rồi publish.
3. Tạo Skill, đặt `agent_version_id` bằng UUID phiên bản Agent đã publish.
   Điền schemas, ngân sách và timeout; không dán keys vào editor.
4. Test fixture chỉ kiểm tra input/output schema, không chạy model. Validate,
   review và publish. Nếu tự review, phải xác nhận rõ checkbox.
5. Gọi trong chat: `/ten-skill {"text":"dữ liệu"}`. Chọn engine session phù hợp
   nếu Agent khai báo model preference; Brain scope phải khớp session.
6. Xem usage/context trace để phân biệt reported tokens với estimates. Output
   JSON là draft AI, không phải bằng chứng đã xác minh hay approval.

Exit criteria hỗ trợ `non_empty:text` và `equals_input:text`. Tool allowlist
không cấp quyền và hiện chưa thực thi. Import chỉ tạo draft; không tự publish.
Workflow ở P4 chỉ định nghĩa/kiểm tra DAG. Chạy dài hạn thuộc P6; semantic
canary, MCP connector thật và gate production/reboot chưa được mở tại P4.
