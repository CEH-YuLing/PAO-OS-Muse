# ADR P3.1 — Engine contract và pin model

Ngày: 06/10/2026. Phạm vi: `F:\PAO-ACOS`, local MVP. Không sửa nguồn Apex/Javis.

## Quyết định

Thêm `pao/modules/engines/{contract,service,api}.py` trên gateway/provider registry
hiện có, không tạo runtime mới, không nhập backend Javis. Ollama vẫn là đường
local; chỉ bốn cloud adapter đã có được chọn khi workspace có connection.
Không cài CLI, gọi discovery cloud, tải model hoặc thêm provider trong P3.1.

Migration 0031 thêm `sessions.engine_config`, `sessions.engine_version` và
`runs.engine_snapshot`; không thêm bảng, không backfill model cho lịch sử cũ.
Trigger PostgreSQL giữ snapshot non-null bất biến. Checksum phát hiện metadata
không tương thích; đây là integrity check, không phải chữ ký chống DBA độc hại.

## Vòng đời

1. Hội thoại mới chưa ghim; GET chỉ xem mặc định, không đổi database.
2. PUT chọn model có optimistic version, khóa session và từ chối khi có run
   queued/running. Chỉ owner của hội thoại có membership write được đổi.
3. Run thường đầu tiên ghim lựa chọn mặc định hiện có của workspace (Ollama
   nếu không có cloud default do admin cấu hình). Các run sau giữ model đã ghim.
4. Mỗi run snapshot provider/model/capabilities/session-version trước enqueue.
   Đổi mặc định hoặc model trên connection không đổi run đã chốt.
5. Worker đối chiếu workspace/connection/status/credential-binding rồi tạo
   gateway cho model snapshot. Credential đổi hoặc connection gỡ/error thì
   failed, không fallback. Không giữ raw key/ciphertext trong snapshot/event.
6. Knowledge opt-in có engine `knowledge/pao-grounded-excerpts-v1`: đoạn trích
   local, không gọi model đã chọn. History Knowledge vẫn bị loại khỏi prompt
   của normal provider sau khi opt-out; Brain và lịch sử không bị xóa khi đổi model.

Queued legacy run chưa có snapshot chỉ được pin một lần lúc worker claim nếu
flag bật. Run lịch sử không có snapshot trả `legacy_unknown`, không suy đoán
model đã từng dùng. Engine pin không thay cơ chế pin skill/budget/approval M2.

## Capability matrix: của adapter PAO, không phải lời hứa mọi model

| Adapter | Text/stream | Tools | Vision | Cancel | Usage |
| --- | --- | --- | --- | --- | --- |
| Ollama/OpenAI/OpenRouter/Anthropic/Gemini hiện có | Có | Structured JSON planner → guarded Tool Gateway | Chưa | Đóng client stream phía PAO | Reported nếu có, thiếu = unknown |
| Knowledge excerpts | Có | Không | Không | Hủy task PAO | Không áp dụng LLM |

`native_tools=false`: chưa implement native function-call protocol. Capability
không cấp quyền gọi tool; membership, skill allowlist, policy/approval vẫn kiểm
tra riêng. Guard chặn capability thiếu trước adapter call. Planner/model không
hỗ trợ schema có thể trả lỗi: P3.1 không tự chọn model khác hoặc nâng quyền.
Chưa kiểm chứng capability riêng từng model; catalog chỉ xác nhận cài/config,
không được coi là chứng nhận chất lượng, vision hay tool compatibility của model.

`ManagedEngine` chuẩn hóa lỗi `engine_timeout/engine_unavailable`, đóng async
generator khi cancel và không phản chiếu provider body/URL/prompt/credentials.
Giữ enum SSE cũ; `run.started.data.engine` thêm metadata công khai. Lỗi engine
planner được fail-closed, không che lỗi bằng một lần gọi model thay thế.
Không cam kết ngừng GPU inference trên server chỉ vì HTTP client đã đóng.
Agent usage `{}` giữ nghĩa chưa được báo cáo, không ghi zero/cost/quota giả.

## API và UI

- GET `/v1/engines?workspace_id=...`: membership scoped; Ollama `/api/tags`
  loopback, timeout 3s, cap 256KiB, không proxy/redirect; cloud chỉ model đã cấu hình.
- GET/PUT `/v1/sessions/{id}/engine`: cấu hình riêng và revision conflict.
- GET `/v1/runs/{id}/engine`: public allowlist; không connection/binding/endpoint.
- Chat PAO AI có bộ chọn local/cloud đã cấu hình, Apply, trạng thái pin và snapshot
  run. Khóa đổi model khi active/apply; giữ chat, Voice, Knowledge và các cửa sổ cũ.

## Rollout/rollback

`ENGINE_CONTRACT_ENABLED=false` trong `.env.example`; bật local sau các gate.
Flag off với session/run đã chọn engine trả controlled error, không silently
fallback. Muốn quay lại: safe-idle → dừng đúng API/worker → sao lưu → đổi flag;
giữ database/snapshot để đọc audit. Downgrade 0030 chỉ dùng trên bản phục hồi
riêng hoặc sau quyết định rollback có backup: sẽ mất ba cột pin, không tự chạy
trên database vận hành. Không chỉnh trực tiếp snapshot để "sửa" run cũ.

## Giới hạn có chủ đích

P3.2 context compiler, P3.3 compaction, P3.4 privacy/budget routing, P3.5 commands,
P3.6 search/export và P3.7 ledger/concurrency chưa làm trong lát cắt này.
P3.1 không tạo multi-user production gate, không bật fast-path shadow thành active,
không mở M4 và không gọi cloud thật. Model name cap120 khớp AgentRun hiện có;
cloud model ID dài hơn không được chọn mới ở P3.1, cần migration riêng nếu cần.
Embedding/retrieval Memory/Sources vẫn có cấu hình local riêng, không bị thay
theo chat model. Embedding model còn thiếu là giới hạn P2 hiện có, không tự tải.

## Gate tái chạy

`scripts/check_p31_migration.py` kiểm tra old195 contract/schema và restore-only
roundtrip; `scripts/run_p0_checks.py` kiểm tra regression/runtime/types;
`PAO_BUILD_CHECK=1 npm run build` giữ dev cache riêng;
`scripts/run_p1_browser_acceptance.py --engines` dùng pao_test/Redis15 và synthetic
gateway qua API/ARQ/SSE thật (không có real provider call).
`--knowledge --engine-contract` kiểm tra Knowledge branch cùng flag P3.1 bật.
Chạy browser sau regression, không song song vì fixture test DB bị truncate.
