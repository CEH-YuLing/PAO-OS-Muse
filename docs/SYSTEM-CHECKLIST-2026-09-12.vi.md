> Checklist hiện tại đã chuyển sang [bản 14/09/2026](SYSTEM-CHECKLIST-2026-09-14.vi.md), bao phủ toàn bộ 154 mục và các lỗi phát hiện. File này giữ nguyên snapshot lịch sử.

> Đây là snapshot trước Phase 2. Cập nhật ngày 13/09/2026: [Phase 2](PHASE-2-RESULT.md), [Phase 3](PHASE-3-RESULT.md), [Phase 4](PHASE-4-RESULT.md) và [Phase 5 — Tool Gateway](PHASE-5-RESULT.md) đã nghiệm thu local. Các bảng bên dưới giữ nguyên để đối chiếu lịch sử; hiện hoàn thành Phase 0–5 trong phạm vi local. Email/lịch chỉ mô phỏng; [Phase 6 — Telegram](PHASE-6-RESULT.md) đã triển khai local và nghiệm thu giao task → nhận kết quả qua bot thật; callback approval Telegram thật chưa thử riêng. Chưa triển khai Ads.

# PAO — Checklist toàn hệ thống

Ngày đối chiếu: 12/09/2026. Đánh giá dựa trên mã nguồn hiện tại và bằng chứng kiểm thử đã ghi nhận, không chỉ dựa trên kế hoạch. Lượt checklist này không triển khai thêm tính năng hay tự chuyển phase.

**Kết luận: hoàn thành Phase 0 và Phase 1 theo acceptance local. Phase 2 và Phase 4 chỉ có phần nền tối thiểu phục vụ mục 153. Hệ thống AI Advertising Operating System và MVP Ads chưa hoàn thành; chưa production-ready.**

“ĐẠT” luôn theo phạm vi ghi ở cột bằng chứng; “MỘT PHẦN” không đồng nghĩa phase đã nghiệm thu. “CHƯA” là chưa có implementation tương ứng. Không quy đổi số phase thành phần trăm khối lượng vì độ lớn từng phase khác nhau.

## 1. Checklist theo lộ trình

| Phase | Phạm vi | Trạng thái | Thực tế / còn thiếu |
|---|---|---|---|
| 0 | Baseline | ĐẠT | Nghiệm thu UI gốc trước chỉnh sửa. |
| 1 | Backend foundation | ĐẠT | FastAPI + DB/Redis + auth + chat/run/SSE; E2E CPU đạt. |
| 2 | Frontend runtime | MỘT PHẦN | Cầu nối tối thiểu có; còn state/event model đầy đủ và trace agent thật. |
| 3 | Memory | CHƯA | Extraction, retrieval, embeddings, structured memory, UI. |
| 4 | Agent runtime | MỘT PHẦN | Một Chief và config; registry/planner/router/specialists chưa có. |
| 5 | Tool Gateway | CHƯA | Registry, permission, approval, audit, tool idempotency. |
| 6 | Telegram | CHƯA | Bot/webhook/whitelist/messages/tasks/approval. |
| 7 | Meta read-only | CHƯA | OAuth/accounts/campaigns/insights/backfill. |
| 8 | Ads Warehouse | CHƯA | Normalized schema, hourly/daily/historical sync. |
| 9 | Ads reporting | CHƯA | Báo cáo ngày/tuần, dashboard và delivery. |
| 10 | Performance intelligence | CHƯA | Rules, anomalies, targets và recommendations. |
| 11 | Meta write | CHƯA | Pause/resume/budget trong Copilot. |
| 12 | Approval | CHƯA | Approve/reject/details và audit mỗi write. |
| 13 | Limited Autopilot | CHƯA | Policy, giới hạn, kill switch/freeze. |
| 14 | Creative intelligence | CHƯA | Metadata, performance, fatigue và learnings. |
| 15 | Attribution + CRM | CHƯA | GA4/CRM/orders, tracking và business value. |
| 16 | Google Ads | CHƯA | Connector và chuẩn hóa warehouse. |
| 17 | Advanced automation | CHƯA | Temporal, durable workflows, approval waits. |
| 18 | Voice | CHƯA | VAD/STT/TTS, interruption, realtime audio. |

TikTok Ads và competitor intelligence có trong yêu cầu tổng thể nhưng chưa được gán phase riêng rõ ràng trong lộ trình 0–18; đều chưa triển khai. Cần bổ sung vào backlog sau khi chốt các phase tương ứng.

## 2. Những gì đang có thật

- [x] Monorepo: frontend Next.js/React và backend Python riêng.
- [x] PostgreSQL + Redis/ARQ, migration Alembic, health/readiness cơ bản.
- [x] JWT/Argon2; workspace membership; hội thoại riêng từng user; viewer không ghi.
- [x] Tạo/chọn hội thoại, gửi tin, lưu user/assistant messages, xem lại lịch sử.
- [x] Run queued/running/completed/failed/cancelled; idempotency tạo run; chống duplicate delivery.
- [x] SSE lưu trong DB, sequence/replay, reconnect; hủy queued/running, giữ partial response.
- [x] Dispatcher phục hồi queued runs, đánh dấu stale worker; timeout/model error handling.
- [x] Một Chief of Staff gọi Ollama qua gateway, model cấu hình bằng env, prompt có version.
- [x] Hook usePaoRuntime nối Orb với run thật; không đưa provider thinking vào trace.
- [x] OpenAPI và kiểu TypeScript sinh tự động, CLI bootstrap, scripts chạy local.
- [x] Đổi thương hiệu UI/code/package/API/container sang PAO, giữ MIT/copyright/credits.
- [ ] Brand entities và brand isolation.
- [ ] Memory dài hạn, embeddings, extraction/retrieval, memory UI.
- [ ] Planner/router, delegation và specialists thực thi.
- [ ] Tools, integrations, approvals, policy, audit business actions.
- [ ] Telegram, user task scheduler, workflow nghiệp vụ.
- [ ] Toàn bộ data/analytics/reporting/action pipeline quảng cáo.

**Các khác biệt dễ hiểu nhầm:** lưu hội thoại không phải memory dài hạn; 18 node không phải 18 agent đang chạy; cron phục hồi worker không phải lịch báo cáo; run_events không phải audit Ads; idempotency chat không bảo đảm idempotency external writes; HTTP /ready chỉ kiểm tra DB/migration/Redis, chưa chứng minh model/worker hoạt động.

## 3. Database và API hiện tại

8 bảng nghiệp vụ: `users`, `workspaces`, `workspace_members`, `sessions`, `messages`, `runs`, `run_events`, `agent_runs`; thêm `alembic_version` để quản lý migration. Chưa có `brands`, `run_steps`, agent registry trong DB, memory, tasks, approvals, integrations, audit_logs hoặc bất kỳ bảng Ads nào.

API hiện có:

- `GET /health`
- `GET /ready`
- `POST /v1/auth/token`
- `GET /v1/me`
- `POST /v1/sessions`
- `GET /v1/sessions`
- `GET /v1/sessions/{session_id}`
- `POST /v1/runs`
- `GET /v1/runs/{run_id}`
- `POST /v1/runs/{run_id}/cancel`
- `GET /v1/runs/{run_id}/events`

Chưa có các API agents/status/run, memory, tasks, approvals, integrations, ads, ads/actions hoặc reports trong mục 83–90.

## 4. Ma trận từng mục trong master specification

Số mục giữ đúng tài liệu đính kèm, kể cả tên APEX lịch sử. Đây là ma trận bao phủ đầy đủ mục 0–153.

| Mục | Yêu cầu | Trạng thái | Bằng chứng / giới hạn |
|---|---|---|---|
| 0 | NHIỆM VỤ CỦA CODEX | MỘT PHẦN | Đã có nền tảng chat local; chưa có hệ điều hành quảng cáo. |
| 1 | MỤC TIÊU SẢN PHẨM | MỘT PHẦN | UI → API → worker → Chief → Ollama hoạt động; các nhánh khác chưa có. |
| 2 | NGUYÊN TẮC KIẾN TRÚC | ĐẠT | AI orchestration ở backend riêng; Next chỉ UI/proxy và route weather. |
| 3 | STACK CÔNG NGHỆ | MỘT PHẦN | Next/React/Three, Python/FastAPI, PostgreSQL, Redis/ARQ và SSE có. Chưa kích hoạt pgvector extension, object storage, Temporal, OTel/Sentry. |
| 4 | CẤU TRÚC REPOSITORY | MỘT PHẦN | Monorepo apps/web, apps/api/pao, packages/contracts, agent-config, infra, docs. Worker dùng chung package pao; chưa dựng các module tương lai. |
| 5 | MULTI-TENANT DATA MODEL | MỘT PHẦN | Workspace FK và kiểm tra membership đã có. Chưa có brands/projects, ad accounts hoặc brand isolation. |
| 6 | DATABASE | MỘT PHẦN | Có 8 bảng foundation. Chưa có brands/run_steps; user của run suy ra qua session, usage nằm ở agent_runs, chưa có model_cost. |
| 7 | AGENT DATABASE | MỘT PHẦN | Có agent_runs và một config JSON; chưa có agents, agent_configs, agent_tool_permissions trong DB. |
| 8 | 18 AGENT GỐC | MỘT PHẦN | Giữ 18 node giao diện; chỉ chief_of_staff có runtime thật. |
| 9 | THÊM ADS AGENTS | CHƯA | Chưa có module/API/schema tương ứng trong mã nguồn hiện tại. |
| 10 | CHIEF OF STAFF | MỘT PHẦN | Chief nhận history giới hạn và gọi model; chưa intent classification, planner, delegation, quality gate hay memory extraction. |
| 11 | AGENT RUNTIME | MỘT PHẦN | Một đường thực thi Chief có config, context, timeout, output cap, lưu agent_run. Chưa runtime generic đa agent hoặc tool loop. |
| 12 | MODEL GATEWAY | MỘT PHẦN | Có OllamaGateway.stream, model trong env. Chưa generate/embed/vision/structured_output hoặc multi-provider routing. |
| 13 | MEMORY SYSTEM | MỘT PHẦN | Chỉ recent messages trong cùng session; chưa semantic, structured business memory hay advertising memory. |
| 14 | MEMORY EXTRACTION | CHƯA | Chưa có module/API/schema tương ứng trong mã nguồn hiện tại. |
| 15 | MEMORY RETRIEVAL | CHƯA | Chưa có module/API/schema tương ứng trong mã nguồn hiện tại. |
| 16 | REALTIME EVENT SYSTEM | MỘT PHẦN | Có SSE và persisted sequence/replay. Mới subset run/core.processing/agent/response.delta; chưa đầy đủ core states, memory/tool/approval events. |
| 17 | REASONING TRACE | MỘT PHẦN | Có observable events, không chuyển trường thinking của provider. Trace UI mới tối thiểu cho Chief, chưa đồ thị delegation thật. |
| 18 | SỬA APEX UI | MỘT PHẦN | usePaoRuntime có SSE, reconnect/cancel, Orb backend-driven nhưng vẫn idle/thinking/speaking. activeTools/approvals là mảng rỗng. |
| 19 | AGENT COCKPIT | MỘT PHẦN | Agent cards vẫn INFO static; chưa status API/cockpit động. |
| 20 | TOOL GATEWAY | CHƯA | Chưa có module/API/schema tương ứng trong mã nguồn hiện tại. |
| 21 | TOOL ACTION SAFETY | CHƯA | Chưa có module/API/schema tương ứng trong mã nguồn hiện tại. |
| 22 | APPROVAL ENGINE | CHƯA | Chưa có module/API/schema tương ứng trong mã nguồn hiện tại. |
| 23 | AUTOPILOT POLICY | CHƯA | Chưa có module/API/schema tương ứng trong mã nguồn hiện tại. |
| 24 | TELEGRAM INTEGRATION | CHƯA | Chưa có module/API/schema tương ứng trong mã nguồn hiện tại. |
| 25 | TELEGRAM SECURITY | CHƯA | Chưa có module/API/schema tương ứng trong mã nguồn hiện tại. |
| 26 | TELEGRAM NATURAL LANGUAGE | CHƯA | Chưa có module/API/schema tương ứng trong mã nguồn hiện tại. |
| 27 | TELEGRAM APPROVAL | CHƯA | Chưa có module/API/schema tương ứng trong mã nguồn hiện tại. |
| 28 | TELEGRAM TASK MANAGEMENT | CHƯA | Chưa có module/API/schema tương ứng trong mã nguồn hiện tại. |
| 29 | META ADS CONNECTOR | CHƯA | Chưa có module/API/schema tương ứng trong mã nguồn hiện tại. |
| 30 | META CREDENTIAL MANAGEMENT | CHƯA | Chưa có module/API/schema tương ứng trong mã nguồn hiện tại. |
| 31 | META READ-ONLY PHASE FIRST | CHƯA | Chưa có module/API/schema tương ứng trong mã nguồn hiện tại. |
| 32 | ADVERTISING DATA WAREHOUSE | CHƯA | Chưa có module/API/schema tương ứng trong mã nguồn hiện tại. |
| 33 | METRICS | CHƯA | Chưa có module/API/schema tương ứng trong mã nguồn hiện tại. |
| 34 | DATA SYNC | CHƯA | Chưa có module/API/schema tương ứng trong mã nguồn hiện tại. |
| 35 | SYNC FREQUENCY | CHƯA | Chưa có module/API/schema tương ứng trong mã nguồn hiện tại. |
| 36 | RAW DATA | CHƯA | Chưa có module/API/schema tương ứng trong mã nguồn hiện tại. |
| 37 | PERFORMANCE ANALYST | CHƯA | Chưa có module/API/schema tương ứng trong mã nguồn hiện tại. |
| 38 | FUNNEL DIAGNOSIS | CHƯA | Chưa có module/API/schema tương ứng trong mã nguồn hiện tại. |
| 39 | STATISTICAL GUARDRAILS | CHƯA | Chưa có module/API/schema tương ứng trong mã nguồn hiện tại. |
| 40 | RULE ENGINE | CHƯA | Chưa có module/API/schema tương ứng trong mã nguồn hiện tại. |
| 41 | RULE DEFINITION | CHƯA | Chưa có module/API/schema tương ứng trong mã nguồn hiện tại. |
| 42 | ANOMALY DETECTION | CHƯA | Chưa có module/API/schema tương ứng trong mã nguồn hiện tại. |
| 43 | ALERT ENGINE | CHƯA | Chưa có module/API/schema tương ứng trong mã nguồn hiện tại. |
| 44 | DAILY ADS REPORT | CHƯA | Chưa có module/API/schema tương ứng trong mã nguồn hiện tại. |
| 45 | WEEKLY REPORT | CHƯA | Chưa có module/API/schema tương ứng trong mã nguồn hiện tại. |
| 46 | REPORT SCHEDULER | CHƯA | Chưa có module/API/schema tương ứng trong mã nguồn hiện tại. |
| 47 | ADS DIRECTOR | CHƯA | Chưa có module/API/schema tương ứng trong mã nguồn hiện tại. |
| 48 | BUDGET CONTROLLER | CHƯA | Chưa có module/API/schema tương ứng trong mã nguồn hiện tại. |
| 49 | KHÔNG SCALE CHỈ VÌ ROAS CAO | CHƯA | Chưa có module/API/schema tương ứng trong mã nguồn hiện tại. |
| 50 | CREATIVE DATABASE | CHƯA | Chưa có module/API/schema tương ứng trong mã nguồn hiện tại. |
| 51 | CREATIVE INTELLIGENCE | CHƯA | Chưa có module/API/schema tương ứng trong mã nguồn hiện tại. |
| 52 | CREATIVE FATIGUE | CHƯA | Chưa có module/API/schema tương ứng trong mã nguồn hiện tại. |
| 53 | CREATIVE MEMORY | CHƯA | Chưa có module/API/schema tương ứng trong mã nguồn hiện tại. |
| 54 | CREATIVE STRATEGIST | CHƯA | Chưa có module/API/schema tương ứng trong mã nguồn hiện tại. |
| 55 | CREATIVE PIPELINE | CHƯA | Chưa có module/API/schema tương ứng trong mã nguồn hiện tại. |
| 56 | EXPERIMENT AGENT | CHƯA | Chưa có module/API/schema tương ứng trong mã nguồn hiện tại. |
| 57 | CRO AGENT | CHƯA | Chưa có module/API/schema tương ứng trong mã nguồn hiện tại. |
| 58 | CRO DIAGNOSIS | CHƯA | Chưa có module/API/schema tương ứng trong mã nguồn hiện tại. |
| 59 | ATTRIBUTION AGENT | CHƯA | Chưa có module/API/schema tương ứng trong mã nguồn hiện tại. |
| 60 | TRACKING HEALTH | CHƯA | Chưa có module/API/schema tương ứng trong mã nguồn hiện tại. |
| 61 | CRM INTELLIGENCE | CHƯA | Chưa có module/API/schema tương ứng trong mã nguồn hiện tại. |
| 62 | LEAD QUALITY | CHƯA | Chưa có module/API/schema tương ứng trong mã nguồn hiện tại. |
| 63 | COMPETITOR INTELLIGENCE | CHƯA | Chưa có module/API/schema tương ứng trong mã nguồn hiện tại. |
| 64 | GOOGLE ADS | CHƯA | Chưa có module/API/schema tương ứng trong mã nguồn hiện tại. |
| 65 | TIKTOK ADS | CHƯA | Chưa có module/API/schema tương ứng trong mã nguồn hiện tại. |
| 66 | NORMALIZED ADS MODEL | CHƯA | Chưa có module/API/schema tương ứng trong mã nguồn hiện tại. |
| 67 | ACTION OBJECT | CHƯA | Chưa có module/API/schema tương ứng trong mã nguồn hiện tại. |
| 68 | ACTION TYPES | CHƯA | Chưa có module/API/schema tương ứng trong mã nguồn hiện tại. |
| 69 | APPROVAL WORKFLOW | CHƯA | Chưa có module/API/schema tương ứng trong mã nguồn hiện tại. |
| 70 | BEFORE/AFTER SNAPSHOT | CHƯA | Chưa có module/API/schema tương ứng trong mã nguồn hiện tại. |
| 71 | COMPENSATING ACTION | CHƯA | Chưa có module/API/schema tương ứng trong mã nguồn hiện tại. |
| 72 | AUTOPILOT KILL SWITCH | CHƯA | Chưa có module/API/schema tương ứng trong mã nguồn hiện tại. |
| 73 | EMERGENCY FREEZE | CHƯA | Chưa có module/API/schema tương ứng trong mã nguồn hiện tại. |
| 74 | DATA FRESHNESS | CHƯA | Chưa có module/API/schema tương ứng trong mã nguồn hiện tại. |
| 75 | IDEMPOTENCY | MỘT PHẦN | request_key chống trùng POST runs, phát hiện nội dung khác cùng key; chưa toàn bộ write API và external actions. |
| 76 | LOCKING | MỘT PHẦN | Row locks/unique index cho session/run và chống duplicate delivery. Chưa khóa tài nguyên quảng cáo. |
| 77 | RATE LIMITING | MỘT PHẦN | Rate limit đăng nhập/tạo run và backoff SSE có. Chưa connector retry/jitter/quota monitoring. |
| 78 | SCHEDULER | CHƯA | Cron dispatcher 10 giây chỉ phục hồi run, KHÔNG phải scheduler tác vụ người dùng. |
| 79 | WORKFLOW ENGINE | MỘT PHẦN | ARQ xử lý run và phục hồi queue; chưa workflow nghiệp vụ hoặc chờ approval nhiều ngày. |
| 80 | API DESIGN | ĐẠT | Các API nghiệp vụ dùng /v1. |
| 81 | SESSIONS API | ĐẠT | Đủ tạo/list/detail sessions; detail trả messages và active_run. |
| 82 | RUNS API | ĐẠT | Đủ tạo/get/events/cancel runs. |
| 83 | AGENTS API | CHƯA | Chưa có module/API/schema tương ứng trong mã nguồn hiện tại. |
| 84 | MEMORY API | CHƯA | Chưa có module/API/schema tương ứng trong mã nguồn hiện tại. |
| 85 | TASK API | CHƯA | Chưa có module/API/schema tương ứng trong mã nguồn hiện tại. |
| 86 | APPROVAL API | CHƯA | Chưa có module/API/schema tương ứng trong mã nguồn hiện tại. |
| 87 | INTEGRATION API | CHƯA | Chưa có module/API/schema tương ứng trong mã nguồn hiện tại. |
| 88 | ADS API | CHƯA | Chưa có module/API/schema tương ứng trong mã nguồn hiện tại. |
| 89 | ADS ACTION API | CHƯA | Chưa có module/API/schema tương ứng trong mã nguồn hiện tại. |
| 90 | REPORT API | CHƯA | Chưa có module/API/schema tương ứng trong mã nguồn hiện tại. |
| 91 | OPENAPI CONTRACT | MỘT PHẦN | OpenAPI là nguồn kiểu TS qua openapi-typescript. Fetch wrapper vẫn viết tay; chưa generated client SDK đầy đủ. |
| 92 | AUTHENTICATION | ĐẠT | JWT, Argon2, kiểm tra active user, session owner và workspace membership. Chưa refresh token/UI quản trị. |
| 93 | RBAC | MỘT PHẦN | DB cho phép 5 role; API chặn viewer ghi. Chưa ma trận quyền riêng admin/operator/analyst hay quyền approval. |
| 94 | SECRETS | MỘT PHẦN | Secrets local ngẫu nhiên trong .env được ignore, có .env.example. Chưa production secret manager. |
| 95 | ENCRYPTION | CHƯA | Chưa có module/API/schema tương ứng trong mã nguồn hiện tại. |
| 96 | AUDIT LOG | CHƯA | run_events không thay thế audit_logs cho hành động bên ngoài. |
| 97 | OBSERVABILITY | MỘT PHẦN | Có run IDs, persisted events, usage và logs tiến trình; chưa trace_id xuyên dịch vụ, OTel/Sentry, dashboards/alerts. |
| 98 | AI COST CONTROL | MỘT PHẦN | Giới hạn context/output/timeout và một job; chưa quota chi phí ngày/tháng/per-workspace. |
| 99 | PROMPT MANAGEMENT | ĐẠT | Prompt tập trung trong JSON, phiên bản 1.0.1 được lưu agent_runs. |
| 100 | STRUCTURED OUTPUT | CHƯA | Chưa có module/API/schema tương ứng trong mã nguồn hiện tại. |
| 101 | RECOMMENDATION FORMAT | CHƯA | Chưa có module/API/schema tương ứng trong mã nguồn hiện tại. |
| 102 | REASON CODES | CHƯA | Chưa có module/API/schema tương ứng trong mã nguồn hiện tại. |
| 103 | AI KHÔNG ĐƯỢC TỰ BỊA METRICS | CHƯA | Chưa có module/API/schema tương ứng trong mã nguồn hiện tại. |
| 104 | DATA LINEAGE | CHƯA | Chưa có module/API/schema tương ứng trong mã nguồn hiện tại. |
| 105 | VOICE — GIAI ĐOẠN SAU | CHƯA | Chưa có module/API/schema tương ứng trong mã nguồn hiện tại. |
| 106 | ADVERTISING COMMAND CENTER | CHƯA | Chưa có module/API/schema tương ứng trong mã nguồn hiện tại. |
| 107 | MULTI-PLATFORM VIEW | CHƯA | Chưa có module/API/schema tương ứng trong mã nguồn hiện tại. |
| 108 | DASHBOARD FILTER | CHƯA | Chưa có module/API/schema tương ứng trong mã nguồn hiện tại. |
| 109 | RECOMMENDATION PANEL | CHƯA | Chưa có module/API/schema tương ứng trong mã nguồn hiện tại. |
| 110 | ACTION HISTORY | CHƯA | Chưa có module/API/schema tương ứng trong mã nguồn hiện tại. |
| 111 | HEALTH DASHBOARD | CHƯA | Chưa có module/API/schema tương ứng trong mã nguồn hiện tại. |
| 112 | TESTING STRATEGY | MỘT PHẦN | Có integration/gateway/SSE tests và kiểm tra contract cơ bản, E2E chat thủ công. Chưa bộ kiểm thử hệ thống đích. |
| 113 | UNIT TEST | CHƯA | Các unit tests ưu tiên policy/rules/metrics/memory/recommendations chưa có vì module chưa triển khai. |
| 114 | CONNECTOR TESTS | CHƯA | Chưa có external business connectors để mock; Ollama gateway có fake transport test. |
| 115 | SANDBOX / DRY RUN | CHƯA | Chưa có module/API/schema tương ứng trong mã nguồn hiện tại. |
| 116 | ADVERTISING SIMULATOR | CHƯA | Chưa có module/API/schema tương ứng trong mã nguồn hiện tại. |
| 117 | E2E TEST | CHƯA | Chưa E2E phân tích campaign; chỉ E2E chat local đã có. |
| 118 | APPROVAL E2E | CHƯA | Chưa E2E approval/execute/audit. |
| 119 | FAILURE TEST | MỘT PHẦN | Đã test LLM lỗi/timeout, queue recovery, stale worker và revoked user. Chưa đầy đủ ma trận Redis outage/token expiry/Meta failure. |
| 120 | CI/CD | CHƯA | Chưa có .github/workflows hoặc pipeline staging/deploy. |
| 121 | ENVIRONMENTS | MỘT PHẦN | Có local và database test riêng; chưa staging/production. |
| 122 | DOCKER | MỘT PHẦN | Compose đủ postgres/redis/migrate/api/worker/web. API image build đạt; toàn bộ app profile container chưa E2E với Ollama host. |
| 123 | DATABASE MIGRATIONS | ĐẠT | Alembic 0001_foundation; không create_all ở runtime; đã kiểm thử migration roundtrip. |
| 124 | SEED DATA | MỘT PHẦN | Có bootstrap owner/workspace, một Chief config và test fixtures foundation; chưa seed agent registry/Ads/policies. |
| 125 | DOCUMENTATION | MỘT PHẦN | Có README, kế hoạch/kết quả P0/P1, local runbook và rebrand. Chưa đủ các tài liệu module tương lai trong spec. |
| 126 | PHASE 0 — BASELINE | ĐẠT | Clone, nhánh kiến trúc, baseline build/browser và sơ đồ component đã nghiệm thu. |
| 127 | PHASE 1 — BACKEND FOUNDATION | ĐẠT | Luồng chat → LLM → SSE → UI → lưu hội thoại đã chạy thật trên CPU. |
| 128 | PHASE 2 — FRONTEND RUNTIME | MỘT PHẦN | Cầu nối tối thiểu có; còn state/event model đầy đủ và trace agent thật. |
| 129 | PHASE 3 — MEMORY | CHƯA | Extraction, retrieval, embeddings, structured memory, UI. |
| 130 | PHASE 4 — AGENT RUNTIME | MỘT PHẦN | Một Chief và config; registry/planner/router/specialists chưa có. |
| 131 | PHASE 5 — TOOL GATEWAY | CHƯA | Registry, permission, approval, audit, tool idempotency. |
| 132 | PHASE 6 — TELEGRAM | CHƯA | Bot/webhook/whitelist/messages/tasks/approval. |
| 133 | PHASE 7 — META READ-ONLY | CHƯA | OAuth/accounts/campaigns/insights/backfill. |
| 134 | PHASE 8 — ADS WAREHOUSE | CHƯA | Normalized schema, hourly/daily/historical sync. |
| 135 | PHASE 9 — ADS REPORTING | CHƯA | Báo cáo ngày/tuần, dashboard và delivery. |
| 136 | PHASE 10 — PERFORMANCE INTELLIGENCE | CHƯA | Rules, anomalies, targets và recommendations. |
| 137 | PHASE 11 — META WRITE | CHƯA | Pause/resume/budget trong Copilot. |
| 138 | PHASE 12 — APPROVAL | CHƯA | Approve/reject/details và audit mỗi write. |
| 139 | PHASE 13 — LIMITED AUTOPILOT | CHƯA | Policy, giới hạn, kill switch/freeze. |
| 140 | PHASE 14 — CREATIVE INTELLIGENCE | CHƯA | Metadata, performance, fatigue và learnings. |
| 141 | PHASE 15 — ATTRIBUTION + CRM | CHƯA | GA4/CRM/orders, tracking và business value. |
| 142 | PHASE 16 — GOOGLE ADS | CHƯA | Connector và chuẩn hóa warehouse. |
| 143 | PHASE 17 — ADVANCED AUTOMATION | CHƯA | Temporal, durable workflows, approval waits. |
| 144 | PHASE 18 — VOICE | CHƯA | VAD/STT/TTS, interruption, realtime audio. |
| 145 | CODING RULES FOR CODEX | MỘT PHẦN | Đã giữ boundaries tối thiểu và trình tự P0/P1; nhiều quy tắc external actions chưa đến giai đoạn để nghiệm thu. |
| 146 | MỖI PHASE CODEX PHẢI TRẢ | MỘT PHẦN | P0/P1 có plan/result/runbook. Những phase sau chưa có hồ sơ triển khai. |
| 147 | KHÔNG ĐƯỢC TỰ Ý | MỘT PHẦN | Giữ nguồn UI, MIT và dữ liệu; đổi thương hiệu theo yêu cầu user. Chưa có Ads actions. Không đánh giá toàn bộ quy tắc tương lai là hoàn tất. |
| 148 | DEFAULT SAFETY MODE | CHƯA | Chưa có Ads mode/config; không có khả năng ghi Ads, nhưng cũng chưa triển khai OBSERVER thành policy. |
| 149 | PRODUCTION READINESS | CHƯA | Chưa production-ready: thiếu audit/policy/kill switch, backup định kỳ + restore drill, monitoring, staging và kiểm định tải/bảo mật. |
| 150 | PRODUCT END STATE | CHƯA | Chưa có luồng Ads end-to-end. |
| 151 | VÒNG LẶP AI QUẢNG CÁO CUỐI CÙNG | CHƯA | Chưa có vòng observe → execute → measure → learn. |
| 152 | ƯU TIÊN MVP | MỘT PHẦN | Mới UI, backend, PostgreSQL và Chief; chưa đủ Memory/Meta/Telegram/Reporting/Recommendations để đạt MVP Ads. |
| 153 | YÊU CẦU ĐẦU TIÊN CHO CODEX | ĐẠT | 16 bước acceptance foundation đã thực hiện; bằng chứng E2E thật trước đổi tên, kiểm thử/build/smoke sau đổi tên. |

## 5. Kiểm thử và giới hạn bằng chứng

| Kiểm chứng gần nhất | Kết quả | Giới hạn |
|---|---|---|
| Backend integration/gateway | 11 passed, 12/09 | Postgres/Redis thật, provider giả lập trong test; cảnh báo quyền cache pytest |
| SSE decoder | 2 passed, 12/09 | UTF-8 chia chunk, CRLF/heartbeat, JSON lỗi |
| Alembic downgrade/upgrade/check | Đạt, 12/09 | Chỉ database pao_test riêng; không rollback dữ liệu ứng dụng |
| Frontend production build/typecheck | Đạt, 12/09 | Output .pao-next để tránh quyền cache cũ |
| Docker API image pao-api | Build đạt, 12/09 | Chưa E2E toàn bộ app profile container |
| HTTP home/about/health/ready | 200, 12/09 | Smoke sau đổi tên, không thay thế inference E2E |
| UI → worker → model → SSE → persisted history | Đạt, 11/09 | E2E thủ công CPU trước đổi tên, không phải bộ browser CI tự động |
| GPU acceleration | Chưa đạt | CUDA lỗi PTX, Vulkan chưa nghiệm thu; CPU đã chạy |
| Load/security/Ads/approval E2E | Chưa làm | Không dùng kết quả 13 test foundation để tuyên bố hệ thống đích hoàn tất |

Bằng chứng E2E: run `74338025-0cc6-44e3-bcb5-a9b8e381f4ef`, 53 response.delta, 149 input tokens / 54 output tokens, khoảng 29,84 giây từ worker bắt đầu đến hoàn tất. Đây là một mẫu, không phải benchmark.

Sau đổi tên, kiểm tra bảo toàn: 1 tài khoản, 2 hội thoại, 17 tin nhắn, 9 agent_runs. Không đọc/sửa nội dung người dùng để lập checklist. Repo vẫn F:/Apex/apex; email/storage legacy giữ tương thích. Git hiện còn thay đổi chưa commit/push.

## 6. Những điểm cần chốt trước phase tiếp

1. **Phase 2:** lập kế hoạch riêng cho event/state contract, mapping Orb, actual-agent trace và reconnect/reload/cancel/failure UX. Hiện hook còn 3 trạng thái visual, activeAgents suy ra từ state, tools/approvals rỗng và agent cards tĩnh.
2. **Trước Phase 3:** chốt brand model/FK và phạm vi memory theo workspace/user/brand, migration + test isolation trước khi nạp business facts. pgvector image có sẵn chưa có nghĩa memory đã hoạt động.
3. **Phase 4:** mở rộng một runtime thành registry/planner/router có schema, không tạo 18 service/chatbot độc lập.
4. **Trước bất kỳ Ads write:** approval/policy/audit/idempotency phải có và kiểm thử trước hoặc cùng lát cắt write đầu tiên. Master xếp Meta write Phase 11, Approval Phase 12 nhưng cũng bắt buộc approve trước write; cần coi approval tối thiểu là dependency bắt buộc, không chờ Phase 12 mới bảo vệ write.
5. **Trước dùng rộng hơn local:** hoàn thiện quyền theo vai trò, backup định kỳ + restore drill, monitoring/error reporting, deployment/staging, giới hạn tải và quản trị user. Backup một lần trước rebrand không phải chiến lược backup hoàn chỉnh.

Thứ tự tiếp tục: **chốt Phase 2 → nghiệm thu → Phase 3 → nghiệm thu → Phase 4…**. Không mở đồng thời Ads, Telegram và Memory. Lượt hiện tại chỉ cập nhật checklist.

## 7. Nguồn kiểm chứng trong repo

- `apps/api/pao/models.py`, `main.py`, `auth.py`, `runtime.py`, `gateway.py`.
- `apps/api/migrations/versions/0001_foundation.py`, `apps/api/tests/`.
- `apps/web/lib/usePaoRuntime.ts`, `apps/web/components/PaoConsole.tsx`, `PaoWorld.tsx`.
- `packages/contracts/openapi.json`, `schema.d.ts`, `packages/agent-config/chief_of_staff.json`.
- `docs/PHASE-0-RESULT.md`, `PHASE-1-RESULT.md`, `phase-1-evidence.json`, `REBRAND-PAO.md`.
- `infra/compose.yaml`, `scripts/start_local.ps1`, `docs/LOCAL-DEVELOPMENT.md`.

Tài liệu đối chiếu: attachment `pasted-text.txt`, ID `0d24d7ec-8dce-4b04-a3b0-a6979eecbb8d`; SHA-256 `bd86549d76b5e3428bbfe3865f5ea35a2e9a4cdb1a8b8652da7bc5612fa81102`.
