# Kế hoạch tích hợp backend Javis OS vào PAO

## Mục tiêu và nguyên tắc

Mục tiêu là đưa các năng lực backend hữu ích của Javis OS vào PAO mà vẫn giữ
PostgreSQL, quyền theo workspace, approval gateway, Temporal/ARQ và các hợp đồng
API hiện có của PAO. Không chép nguyên khối `server/main.py` của Javis vào PAO:
đó là một monolith khoảng 1 MB, phụ thuộc filesystem/SQLite và cấp quyền rất
rộng cho terminal, plugin và CLI. Cách này sẽ tạo hai nguồn sự thật về dữ liệu,
khó kiểm soát quyền và làm hỏng tính nhất quán của hệ thống hiện tại.

Mã nguồn Javis đã được kiểm tra tại `<JAVIS_PROJECT_DIR>`. Bản đang chạy hiển thị
`v0.64.65`, có 212 file Python/JS/HTML/CSS, khoảng 115.911 dòng và 503 file
test. Javis dùng FastAPI/WebSocket, filesystem Brain, SQLite, nhiều provider/CLI,
skills/workflows, file manager, terminal, Telegram/Zalo, voice, context compiler,
model router và fast-path runtime. PAO hiện có khoảng 12.933 dòng Python/TypeScript,
PostgreSQL, Redis, Temporal/ARQ, API/SSE bền vững, approval/safety gateway và
159 test backend đã đạt.

## So sánh thực tế

Javis mạnh ở local-first, Brain/skills/workflows phong phú, nhiều provider và
CLI, streaming WebSocket có reconnect/outbox, file/terminal/voice/channels và
context compiler có quota, quality gate, tracing. Fast path của Javis bỏ qua
memory/tool discovery cho các yêu cầu đơn giản nên có thể giảm độ trễ.

Javis yếu ở việc state phân tán giữa SQLite, file và process monolith; boundary
quyền của terminal/plugin rộng; behavior phụ thuộc provider/CLI; vận hành và
backup khó tách module. Với một lượt thử Codex trong môi trường hiện tại, trace
quan sát được khoảng 17,8 giây tới completion và input context thực tế rất lớn
(khoảng 983k token usage), nên “local-first” không tự động đồng nghĩa với nhanh.
Classifier fast path cũng cố ý bảo thủ và có thể rơi về legacy path khi intent
không chắc chắn.

PAO mạnh ở dữ liệu có schema và scope workspace, run/event/agent trace bền vững,
approval và tool safety rõ ràng, memory pgvector, Temporal/ARQ, các tích hợp Ads
và bộ test hồi quy. PAO còn thiếu provider router đa nguồn, Brain filesystem,
registry skills/workflows, fast path, file vault/terminal sandbox, nhiều channel
và các tối ưu streaming/reconnect của Javis. Runtime hiện vẫn đi qua planner,
memory và final path; worker mặc định chỉ chạy một job để bảo vệ máy local.

## Ma trận di trú theo giai đoạn

| Giai đoạn | Năng lực Javis | Đích trong PAO | Trạng thái / điều kiện hoàn thành |
|---|---|---|---|
| A | Fast-path policy và capability map | `pao.javis_compat` | **Đã bắt đầu**: classifier và manifest chạy shadow, không đổi output hiện tại |
| B | `model_router`, provider profiles, keep-alive | mở rộng `pao.gateway` | Adapter Ollama trước; thêm provider sau; đo TTFT, timeout, token và fallback |
| C | Brain `MEMORY.md`, facts, wiki, sources | importer vào `pao.memory` + PostgreSQL/pgvector | Import một lần có provenance, workspace/brand scope; không thực thi nội dung file |
| D | `skill_router`, workflow runtime | registry PAO + Temporal | Chỉ import metadata/prompt; workflow phải qua schema, quyền và approval |
| E | Fast path active canary | runtime PAO | Cohort/percentage nhỏ, yêu cầu an toàn mới được bỏ planner; mọi lỗi fallback planner |
| F | Context compiler, quotas, quality gates | context builder/observability PAO | Ngân sách token deterministic, attribution nguồn, redacted trace và budget alerts |
| G | Telegram/Zalo/chatbot/webhook | channel adapters PAO | Telegram hiện partial; thêm channel sau khi có idempotency, auth và rate limit |
| H | voice live/voice brain | `pao.voice` | Chuẩn hóa chunking, backpressure và local CPU/GPU profiles |
| I | file manager/terminal/plugins | vault-scoped tool gateway | Chỉ sandbox thư mục được cấp; cấm unrestricted terminal và plugin tùy ý ở bản đầu |
| J | auto-learning, usage/evals | memory jobs + observability | Job học có approval, provenance, rollback và benchmark latency/quality |

## Phần đã triển khai trong PAO

`apps/api/pao/javis_compat.py` cung cấp classifier độc lập với provider và
capability manifest. `execute_run` ghi quyết định vào `Run.execution_plan` dưới
khóa `javis_compat` ở chế độ `shadow`; các event, response và planner hiện tại
không bị thay đổi. Cờ `JAVIS_COMPAT_SHADOW_ENABLED` (mặc định bật) cho phép tắt
quan sát khi cần rollback. Đây là nền đo lường cho các giai đoạn B–F, chưa phải
lệnh chuyển sang fast path thực tế.

## Cổng nghiệm thu và điều kiện không triển khai

Mỗi giai đoạn phải có test unit, integration và browser/API smoke phù hợp; giữ
đủ 159 backend regression tests, kiểm tra scope workspace/brand, approval,
cancel/revoke, SSE ordering và memory privacy. Canary chỉ được bật sau khi có
so sánh latency p50/p95, tỉ lệ fallback, lỗi provider, token cost và chất lượng
trên tập prompt đại diện.

Không nhập raw plugin/terminal, không cho skill tự cấp quyền, không trộn Brain
file trực tiếp vào context, không thay PostgreSQL bằng SQLite và không bật nhiều
provider/fast path đồng thời trong một thay đổi. Mỗi bước phải có migration
đảo ngược được và tài liệu hóa trong system test.

## Thứ tự đề xuất tiếp theo

1. Hoàn tất B: provider profile và telemetry TTFT/total latency trên gateway.
2. Thực hiện C: Brain importer chạy dry-run, preview provenance rồi mới commit.
3. Thực hiện D: skill/workflow registry với Temporal và approval.
4. Bật E theo canary sau khi B–D đạt cổng nghiệm thu; tiếp đó mới làm F–J.

