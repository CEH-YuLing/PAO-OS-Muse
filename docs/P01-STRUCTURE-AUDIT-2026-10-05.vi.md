# P0.1 — Bản đồ cấu trúc, API, dữ liệu và runtime PAO-ACOS

Ngày: 05/10/2026. Phạm vi: `F:\PAO-ACOS`. P0.1 là checkpoint tài liệu, không phải refactor.

## 1. Kết quả và giới hạn

**Hoàn tất bản đồ tĩnh P0.1.** Đã đọc cấu trúc, entrypoints, quyền truy cập, ORM,
migration bootstrap, workers, frontend shell, scripts và các ADR đang có.
Không sửa backend/frontend, không thêm dependency, không migrate, không khởi động
hay dừng process, không gọi Ads/Telegram/Ollama và không triển khai M4.

- HEAD tham chiếu: `e1eb473`. Roadmap đã có chỉnh sửa tài liệu từ lượt trước;
  giữ nguyên và bổ sung trạng thái P0.1, không coi thay đổi đó là code mới.
- 62 file Python trong `apps/api/pao`; 20 file khai báo routes, 20 lần include_router.
- 133 HTTP operations khai báo trong code; 133 trong OpenAPI lưu sẵn.
  Tập METHOD + PATH bằng nhau, không trùng. **Chưa chứng minh schema hoặc runtime tương thích.**
- 64 ORM tables nghiệp vụ. Báo cáo restore M2 ghi 65 bảng vì có thêm
  `alembic_version`; P0.1 không truy vấn DB để xác minh schema live.
- 24 migration files, từ 0001 đến 0024; đọc lịch sử file không chứng minh local
  database đang ở head.
- Snapshot AST, import edges, routes, tables và SHA-256 byte của 177 file:
  [P01-STRUCTURE-SNAPSHOT-2026-10-05.json](P01-STRUCTURE-SNAPSHOT-2026-10-05.json).
  Đây là fingerprint kiểm chứng nội dung source, không phải chữ ký hoặc backup dữ liệu.
- Các lần regression M2/M3 và revision 0024 là bằng chứng lịch sử trong
  [M2 final](M2-FINAL-ACCEPTANCE-2026-10-05.vi.md) và
  [M3 foundation](M3-RECONCILIATION-FOUNDATION-2026-10-05.vi.md), **không chạy lại ở P0.1**.
- Không đọc nội dung `.env`, logs hay dữ liệu hội thoại; không chép secrets vào snapshot.

Công cụ khảo sát phân tích AST bằng Python, không import `pao.main` hay `pao.config`.
Đồ thị chỉ xét relative imports có module đích rõ; bao gồm function-local imports.
Không phát hiện nhóm cycle trong đồ thị đó, nhưng không loại trừ dynamic imports,
import-time side effects hoặc lỗi khi khởi động.

## 2. Bản đồ thư mục hiện tại

```text
PAO-ACOS/
├── apps/api/pao/        Một Python package, phần lớn module đang nằm ngang
│   ├── main.py         FastAPI app, chat/auth routes và router registration
│   ├── runtime.py      Run/SSE state helpers + orchestration + ARQ entrypoint
│   ├── models.py       Toàn bộ 64 ORM tables
│   └── integrations/   Meta và Google Ads có client/API/sync riêng
├── apps/api/migrations/ Alembic; env.py import pao.models.Base
├── apps/api/tests/      40 file trực tiếp trong thư mục, không phải 40 test cases
├── apps/web/            Next.js app routes + components + runtime state
├── apps/worker/         README; chưa có Python worker package riêng
├── packages/            contracts, agent-config, skill-config
├── scripts/             72 scripts hiện tại; pha lịch sử và ACOS đang dùng
├── infra/               Compose ACOS riêng + Compose lịch sử + Dockerfiles
├── docs/                ADR, roadmap, báo cáo nghiệm thu/lịch sử
└── .runtime/.venv/node_modules/   Dữ liệu/môi trường local, không phải source nghiệp vụ
```

Số lượng script và trang frontend được liệt kê đầy đủ trong snapshot; không suy
ra feature hoạt động chỉ vì có file. Thư mục modules/brains/workers đề xuất trong
roadmap **chưa tồn tại như kiến trúc đã migrate**.

## 3. Module và phụ thuộc cần giữ

| Domain | Files/entrypoints hiện tại | Trách nhiệm và hướng tách |
| --- | --- | --- |
| Identity/config/persistence | auth.py, access.py, config.py, db.py, models.py | JWT, membership, session owner, DB session; giữ một nguồn config/metadata |
| Conversations | main.py, schemas.py, runtime.py | Chat/session/run, cancel, durable events; tách HTTP khỏi state helpers sau contract gate |
| Agents & engines | agents.py, gateway.py, model_router.py, model_api.py | Agent registry, Ollama/cloud routing; không đặt provider calls vào ORM hoặc API factory |
| Memory | memory.py, memory_api.py, memory_schemas.py | Facts theo workspace/user/brand, embeddings và fallback; chưa phải Brain/RAG tài liệu |
| Tasks/goals | task_api.py, models.py | Dependency, attempt, evidence; không tạo runtime nhiệm vụ thứ hai |
| Skills | skills.py, skill_router.py, skill_api.py, skill_artifacts.py | Manifest đã duyệt, deterministic read-only, pin executable, immutable replay |
| Tools | tool_registry.py, tool_gateway.py, tool_api.py, business_tools.py | Schema/policy, audit, business read tools; phân biệt gateway LLM và gateway tools |
| Business | warehouse/report/intelligence/creative/attribution/reconciliation | Domain data và phân tích; scheduler không nên nằm ở HTTP adapters |
| Action/policy | ads_actions.py, ads_action_api.py, ads_policy.py, ads_policy_api.py | Approval/action/audit đã có code; không đồng nghĩa M4 nghiệm thu hoặc live writes được phép |
| Automation | automation.py, automation_api.py, automation_workflows.py | PostgreSQL outbox và Temporal projection; giữ ADR-0001 |
| Channels/voice | telegram.py, voice.py, voice_api.py, scripts bridges | Transport và domain hiện còn pha trộn; giữ liên kết identity, delivery dedupe |
| Platform | platform_api.py, javis_compat.py | Capability metadata và shadow classifier; không phải health/acceptance evidence |

Luồng phụ thuộc hiện tại, giản lược:

```text
Next layout → PaoRuntimeProvider → usePaoRuntime → /v1 proxy → FastAPI
                                                        ↓
                                         auth/access → SQLAlchemy
                                                        ↓
                                             Run row + RunEvent
                                                        ↓
Redis/ARQ dispatch → runtime.py → agents/skills/tools/model/memory/business
                           ├→ report_api.schedule_reports
                           ├→ warehouse_api.schedule_warehouse
                           └→ automation outbox → Temporal → DB projection
```

Hai cạnh runtime → HTTP module là coupling cần cải thiện, không phải bằng chứng
runtime đang lỗi. Test hiện cũng import scheduler từ API file, nên cần shim cho
cả runtime và test khi tách.

Hotspots theo dòng source, không phải độ phức tạp đã đo:
`models.py` 1224; `task_api.py` 870; `runtime.py` 527; `telegram.py` 304.
Không tách models/task API đầu tiên chỉ vì file dài.

## 4. Ai sở hữu dữ liệu và trạng thái?

| Dữ liệu/trạng thái | Authority hiện tại | Thành phần được thay đổi | Không được dùng làm authority thứ hai |
| --- | --- | --- | --- |
| Identity/workspace/role | PostgreSQL User/Member | Auth/API có RBAC | Browser storage hoặc model output |
| Session/message/run/event | PostgreSQL | API nhận lệnh; worker chuyển trạng thái; SSE chỉ đọc | Redis result cache, tab browser |
| Goal/task/dependency/attempt | PostgreSQL | Task domain qua API | Agent tự tuyên bố hoàn tất thiếu evidence |
| Skill manifest executable | JSON reviewed trong packages/skill-config | Source change có review/version | LLM tự ghi manifest hoặc plugin tùy ý |
| Skill result lịch sử | Run execution_plan / TaskAttempt skill_artifact | Ghi terminal theo transaction | Registry/model/business records hiện tại khi replay |
| Memory facts | PostgreSQL scoped facts | Memory service qua kiểm quyền | Markdown/Git chưa có import protocol |
| Queue ngắn | Redis/ARQ dispatch | Worker | Không giữ bản duy nhất của lệnh nghiệp vụ |
| Workflow request/projection/outbox | PostgreSQL | API + dispatcher + guarded activity | Temporal event thay projection terminal tùy ý |
| Durable timer/execution history | Temporal | Temporal workflow/worker | ARQ cron không thay durable workflow |
| Ads snapshot/metric/report | PostgreSQL; provider là nguồn ngoài | Sync/report scoped/versioned | Dữ liệu người dùng nhập không thành official export |
| External Ads state | Nhà cung cấp ngoài | Chỉ gated executor được cấp quyền | Dry-run/rollback proposal không khẳng định undo ngoài đã thành công |
| Telegram inbound/delivery | PostgreSQL dedupe + channel transport | Bridge/channel domain | Process memory hoặc offset đơn lẻ |
| Credentials | Config riêng/encrypted connections | Operator hoặc credential APIs có quyền | Snapshot, Git, Brain hoặc logs |

Nhóm sở hữu toàn bộ 64 bảng (phân nhóm để thiết kế, không đổi schema):

| Owner logic | Tables hiện tại |
| --- | --- |
| Identity & model connections | `users`, `workspaces`, `workspace_members`, `model_provider_connections` |
| Conversations & runtime | `sessions`, `runs`, `messages`, `run_events`, `agent_runs` |
| Memory | `brands`, `memories`, `memory_jobs` |
| Tools | `tool_calls`, `tool_audits` |
| Telegram | `telegram_peers`, `telegram_updates`, `telegram_deliveries` |
| Ads connectors | `meta_connections`, `meta_oauth_states`, `meta_sync_jobs`, `meta_snapshots`, `google_ads_connections`, `google_ads_oauth_states`, `google_ads_sync_jobs` |
| Warehouse & reports | `ad_entities`, `ad_metrics`, `ad_sync_schedules`, `ad_reports`, `ad_report_deliveries`, `ad_report_schedules` |
| Performance intelligence | `ad_targets`, `ads_rules`, `ad_intelligence_runs`, `ad_anomalies`, `ad_recommendations` |
| Creative | `creative_assets`, `creative_metadata`, `creative_analysis_runs`, `creative_performance`, `creative_features`, `creative_learnings` |
| CRM & attribution | `attribution_sources`, `analytics_events`, `crm_leads`, `crm_stage_events`, `business_orders`, `attribution_runs`, `attribution_metrics`, `tracking_alerts` |
| Action & policy | `ads_autopilot_policies`, `ads_policy_audits`, `ads_actions`, `ads_action_audits` |
| Automation | `automation_workflows`, `automation_outbox`, `automation_workflow_audits` |
| Voice | `voice_interactions` |
| Tasks & goals | `projects`, `goals`, `tasks`, `task_dependencies`, `task_attempts`, `task_comments`, `task_activity` |

Brain/file objects/usage ledger/MCP connections riêng là đề xuất tương lai,
không gán bảng chưa có vào snapshot hiện hành.

## 5. Process, health và đường khởi động

| Thành phần | Entrypoint | Launcher ACOS có chạy? | Giới hạn bằng chứng |
| --- | --- | --- | --- |
| API | uvicorn pao.main:app, loopback 8100 | Có | /health là liveness; /ready thử DB, alembic table và Redis; không kiểm worker/provider/head revision |
| ARQ | pao.runtime.WorkerSettings | Có | max_jobs=1, max_tries=1; startup + cron dispatch mỗi 10s; không có worker health endpoint |
| Web | next dev apps/web, loopback 3200 | Có | PAO_API_URL được launcher đặt 8100; next.config mặc định 8000 nếu chạy khác |
| Ollama | .runtime/ollama/ollama.exe serve | Có | Local CPU, one loaded model/parallel request; launch không chứng minh model request đạt |
| PostgreSQL/Redis | compose.acos-local.yaml | Có | Project pao-acos-local; ports 15432/16379; volumes riêng |
| Temporal worker | scripts/temporal_worker.py | Không | Script có guard temporal_enabled; ACOS Compose chưa khai báo Temporal service |
| Telegram bridge | scripts/telegram_bridge.py | Không | Guard flag/token; advisory lock DB; transport có side effects, không tự chạy ở audit |
| Search | Compose lịch sử/search profile | Không | Không được coi full Compose là profile ACOS được nghiệm thu |

API enqueue lỗi có thể được phục hồi từ durable queued row. Run running stale được
terminal hóa theo timeout pin + recovery grace; không tự replan/re-execute kết quả cũ.
ARQ functions đăng ký: execute_run, extract_memory, execute_tool, sync_meta,
sync_google_ads, execute_action. Việc có đăng ký executor không cho phép bật feature flag.

Import-time constraints cần gate P0.2: `db.py` tạo engine từ settings;
`skills.py` đọc manifest và tính digest source; `runtime.WorkerSettings` đọc Redis config.
Factory mới không được âm thầm làm thay đổi launcher/env/config initialization.
Không kết luận các import này đang mở network connection từ khảo sát tĩnh.

## 6. Frontend và contracts

- Root layout giữ một PaoRuntimeProvider. Workspace shell dùng 12 modules;
  root/about/skills là routes bổ sung, không tính thành 12 business modules.
- `PaoAppShell`, `usePaoRuntime`, runtime-state và SSE là hạ tầng dùng chung.
  Chưa tạo provider riêng mỗi trang; refactor không được mất login/session/stream.
- `PaoConsole` và các panel cũ cần mapping usage trước khi xóa; chưa xác nhận
  dead code. P0.1 không xóa các surface này.
- `packages/contracts/openapi.json` là artifact lưu sẵn;
  `schema.d.ts` sinh từ nó. Không sửa generated types bằng tay.
- `scripts/export_openapi.py` import app và **ghi file**, không chạy ở audit.
  Bước extraction phải so toàn schema trước/sau, không chỉ số route.

Route counts hiện tại:

| Source | HTTP operations |
| --- | ---: |
| `apps/api/pao/ads_action_api.py` | 9 |
| `apps/api/pao/ads_policy_api.py` | 6 |
| `apps/api/pao/agent_api.py` | 3 |
| `apps/api/pao/attribution_api.py` | 9 |
| `apps/api/pao/automation_api.py` | 6 |
| `apps/api/pao/creative_api.py` | 3 |
| `apps/api/pao/integrations/google_ads/api.py` | 8 |
| `apps/api/pao/integrations/meta/api.py` | 7 |
| `apps/api/pao/intelligence_api.py` | 9 |
| `apps/api/pao/main.py` | 12 |
| `apps/api/pao/memory_api.py` | 9 |
| `apps/api/pao/model_api.py` | 7 |
| `apps/api/pao/platform_api.py` | 1 |
| `apps/api/pao/report_api.py` | 8 |
| `apps/api/pao/skill_api.py` | 5 |
| `apps/api/pao/task_api.py` | 18 |
| `apps/api/pao/telegram.py` | 2 |
| `apps/api/pao/tool_api.py` | 4 |
| `apps/api/pao/voice_api.py` | 3 |
| `apps/api/pao/warehouse_api.py` | 4 |

Danh sách METHOD/PATH/handler đầy đủ tại phụ lục và snapshot JSON.

## 7. Phân loại scripts — giữ lại, không chạy nhầm

| Nhóm | Scripts | Cách dùng |
| --- | --- | --- |
| ACOS-current | start_acos_local, stop_acos_local, init_acos_local, check_acos_idle, check_m2_restore, check_m2_test_migration, check_m3_readiness | Có target guard/path ACOS; vẫn phải đọc side effects và xác nhận gate trước chạy |
| Source-history | deploy_phase*, deploy_local_phase*, deploy_stage2/3, verify_phase*, start_local, init_local, start_ollama | Giữ lịch sử; không chạy với ACOS theo tên phase hoặc báo cáo cũ |
| Shared-review | test_backend, export_openapi, verify_workspace_ui, verify_skills_ui, verify_chief_skill, bridges/setup/verify khác | Chốt target API/DB/Redis/env và tác động trước dùng |

Phân loại từng file trong snapshot là policy mặc định, không chứng nhận mọi file
trong nhóm an toàn. Ví dụ deploy_phase15 yêu cầu DB /apex và container pao-postgres-1;
deploy_stage2/3 có backup/restore/migrate cùng target lịch sử. Không chỉnh sửa
chúng thành ACOS trong P0.1. `test_backend.py --roundtrip` downgrade pao_test đến base:
đây là destructive test-only, không chạy tự động. Không gọi `setup_*` trong audit.

## 8. Những điểm cần chốt và bước tiếp theo

1. Giữ modular monolith; tách theo domain, không theo mỗi bảng hoặc mỗi endpoint.
2. Giữ ownership trong ADR-0001/0002 và M2 result replay.
3. Tách scheduler khỏi HTTP sau contract/recovery gates; không đổi job name,
   cadence, lease, timeouts hay terminal semantics cùng lúc.
4. Tách service nhỏ đầu tiên: đề xuất chuyển implementation
   `reconciliation.py` vào business/reconciliation, giữ import shim cũ.
   Module này không cần DB/Redis/provider và có tests scope/decimal hiện có.
5. App factory/router composition làm checkpoint tiếp sau extraction nhỏ;
   không đồng thời tách models.py hoặc db.py.
6. Chưa thêm Brain ACL vào legacy memory. P1.1 phải thiết kế migration scope
   giữ user/brand isolation trước khi CRUD/ingestion.
7. Catalog ready/configured không phải live health hoặc acceptance; P0.4 tách
   các trạng thái này, không tự kết nối tài khoản.

Quyết định và gate chi tiết:
[ADR-P01 — Module boundaries và extraction](ADR-P01-MODULE-BOUNDARIES.vi.md).
**P0.1 hoàn tất về tài liệu; P0.2 chưa triển khai, M4 vẫn chưa được phép triển khai.**

## Phụ lục — Route table snapshot tĩnh

Đường dẫn là literal route/prefix lấy từ AST tại checkpoint, không phải API live.
Không có query/body schema hoặc kết quả RBAC runtime trong bảng này.

| Method | Path | Source | Handler |
| --- | --- | --- | --- |
| GET | `/v1/ads/write-status` | [apps/api/pao/ads_action_api.py:122](../apps/api/pao/ads_action_api.py#L122) | `write_status` |
| POST | `/v1/ads/actions` | [apps/api/pao/ads_action_api.py:127](../apps/api/pao/ads_action_api.py#L127) | `propose` |
| GET | `/v1/ads/actions` | [apps/api/pao/ads_action_api.py:135](../apps/api/pao/ads_action_api.py#L135) | `actions` |
| GET | `/v1/ads/actions/{action_id}` | [apps/api/pao/ads_action_api.py:145](../apps/api/pao/ads_action_api.py#L145) | `get_action` |
| POST | `/v1/ads/actions/{action_id}/execute` | [apps/api/pao/ads_action_api.py:153](../apps/api/pao/ads_action_api.py#L153) | `execute` |
| GET | `/v1/approvals` | [apps/api/pao/ads_action_api.py:165](../apps/api/pao/ads_action_api.py#L165) | `approvals` |
| GET | `/v1/approvals/{action_id}` | [apps/api/pao/ads_action_api.py:174](../apps/api/pao/ads_action_api.py#L174) | `approval_detail` |
| POST | `/v1/approvals/{action_id}/approve` | [apps/api/pao/ads_action_api.py:188](../apps/api/pao/ads_action_api.py#L188) | `approve` |
| POST | `/v1/approvals/{action_id}/reject` | [apps/api/pao/ads_action_api.py:193](../apps/api/pao/ads_action_api.py#L193) | `reject` |
| GET | `/v1/ads/autopilot/status` | [apps/api/pao/ads_policy_api.py:90](../apps/api/pao/ads_policy_api.py#L90) | `runtime_status` |
| GET | `/v1/ads/autopilot/policies` | [apps/api/pao/ads_policy_api.py:105](../apps/api/pao/ads_policy_api.py#L105) | `policies` |
| GET | `/v1/ads/autopilot/policies/{policy_id}` | [apps/api/pao/ads_policy_api.py:112](../apps/api/pao/ads_policy_api.py#L112) | `get_policy` |
| PUT | `/v1/ads/autopilot/policies` | [apps/api/pao/ads_policy_api.py:120](../apps/api/pao/ads_policy_api.py#L120) | `put_policy` |
| POST | `/v1/ads/autopilot/policies/{policy_id}/freeze` | [apps/api/pao/ads_policy_api.py:167](../apps/api/pao/ads_policy_api.py#L167) | `freeze` |
| POST | `/v1/ads/autopilot/policies/{policy_id}/unfreeze` | [apps/api/pao/ads_policy_api.py:172](../apps/api/pao/ads_policy_api.py#L172) | `unfreeze` |
| GET | `/v1/runs/{run_id}/skill-replay` | [apps/api/pao/agent_api.py:48](../apps/api/pao/agent_api.py#L48) | `skill_replay` |
| GET | `/v1/agents` | [apps/api/pao/agent_api.py:63](../apps/api/pao/agent_api.py#L63) | `registry` |
| GET | `/v1/runs/{run_id}/execution` | [apps/api/pao/agent_api.py:70](../apps/api/pao/agent_api.py#L70) | `execution` |
| POST | `/v1/attribution/sources` | [apps/api/pao/attribution_api.py:109](../apps/api/pao/attribution_api.py#L109) | `create_source` |
| GET | `/v1/attribution/sources` | [apps/api/pao/attribution_api.py:119](../apps/api/pao/attribution_api.py#L119) | `sources` |
| POST | `/v1/attribution/sources/{source_id}/analytics` | [apps/api/pao/attribution_api.py:125](../apps/api/pao/attribution_api.py#L125) | `import_analytics` |
| POST | `/v1/attribution/sources/{source_id}/leads` | [apps/api/pao/attribution_api.py:137](../apps/api/pao/attribution_api.py#L137) | `import_leads` |
| POST | `/v1/attribution/sources/{source_id}/stages` | [apps/api/pao/attribution_api.py:149](../apps/api/pao/attribution_api.py#L149) | `import_stages` |
| POST | `/v1/attribution/sources/{source_id}/orders` | [apps/api/pao/attribution_api.py:164](../apps/api/pao/attribution_api.py#L164) | `import_orders` |
| POST | `/v1/attribution/analyze` | [apps/api/pao/attribution_api.py:186](../apps/api/pao/attribution_api.py#L186) | `analyze_now` |
| GET | `/v1/attribution/dashboard` | [apps/api/pao/attribution_api.py:201](../apps/api/pao/attribution_api.py#L201) | `dashboard` |
| POST | `/v1/attribution/alerts/{alert_id}/acknowledge` | [apps/api/pao/attribution_api.py:205](../apps/api/pao/attribution_api.py#L205) | `acknowledge` |
| GET | `/v1/automation/status` | [apps/api/pao/automation_api.py:72](../apps/api/pao/automation_api.py#L72) | `status` |
| POST | `/v1/automation/workflows` | [apps/api/pao/automation_api.py:77](../apps/api/pao/automation_api.py#L77) | `start` |
| GET | `/v1/automation/workflows` | [apps/api/pao/automation_api.py:116](../apps/api/pao/automation_api.py#L116) | `listing` |
| GET | `/v1/automation/workflows/{workflow_id}` | [apps/api/pao/automation_api.py:121](../apps/api/pao/automation_api.py#L121) | `get` |
| POST | `/v1/automation/workflows/{workflow_id}/decision` | [apps/api/pao/automation_api.py:124](../apps/api/pao/automation_api.py#L124) | `decision` |
| POST | `/v1/automation/workflows/{workflow_id}/cancel` | [apps/api/pao/automation_api.py:137](../apps/api/pao/automation_api.py#L137) | `cancel` |
| POST | `/v1/creatives/analyze` | [apps/api/pao/creative_api.py:104](../apps/api/pao/creative_api.py#L104) | `analyze_now` |
| GET | `/v1/creatives/dashboard` | [apps/api/pao/creative_api.py:122](../apps/api/pao/creative_api.py#L122) | `dashboard` |
| PUT | `/v1/creatives/assets/{asset_id}/metadata` | [apps/api/pao/creative_api.py:127](../apps/api/pao/creative_api.py#L127) | `update_metadata` |
| GET | `/v1/integrations/google-ads/connection` | [apps/api/pao/integrations/google_ads/api.py:39](../apps/api/pao/integrations/google_ads/api.py#L39) | `status` |
| POST | `/v1/integrations/google-ads/oauth/start` | [apps/api/pao/integrations/google_ads/api.py:45](../apps/api/pao/integrations/google_ads/api.py#L45) | `start` |
| GET | `/v1/integrations/google-ads/callback` | [apps/api/pao/integrations/google_ads/api.py:53](../apps/api/pao/integrations/google_ads/api.py#L53) | `callback` |
| DELETE | `/v1/integrations/google-ads/connection` | [apps/api/pao/integrations/google_ads/api.py:66](../apps/api/pao/integrations/google_ads/api.py#L66) | `disconnect` |
| POST | `/v1/integrations/google-ads/sync` | [apps/api/pao/integrations/google_ads/api.py:70](../apps/api/pao/integrations/google_ads/api.py#L70) | `sync` |
| GET | `/v1/integrations/google-ads/jobs` | [apps/api/pao/integrations/google_ads/api.py:81](../apps/api/pao/integrations/google_ads/api.py#L81) | `jobs` |
| GET | `/v1/integrations/google-ads/accounts` | [apps/api/pao/integrations/google_ads/api.py:84](../apps/api/pao/integrations/google_ads/api.py#L84) | `accounts` |
| GET | `/v1/integrations/google-ads/metrics` | [apps/api/pao/integrations/google_ads/api.py:93](../apps/api/pao/integrations/google_ads/api.py#L93) | `metrics` |
| GET | `/v1/integrations/meta/connection` | [apps/api/pao/integrations/meta/api.py:55](../apps/api/pao/integrations/meta/api.py#L55) | `status` |
| POST | `/v1/integrations/meta/oauth/start` | [apps/api/pao/integrations/meta/api.py:66](../apps/api/pao/integrations/meta/api.py#L66) | `start` |
| GET | `/v1/integrations/meta/callback` | [apps/api/pao/integrations/meta/api.py:87](../apps/api/pao/integrations/meta/api.py#L87) | `callback` |
| DELETE | `/v1/integrations/meta/connection` | [apps/api/pao/integrations/meta/api.py:118](../apps/api/pao/integrations/meta/api.py#L118) | `disconnect` |
| POST | `/v1/integrations/meta/sync` | [apps/api/pao/integrations/meta/api.py:128](../apps/api/pao/integrations/meta/api.py#L128) | `sync` |
| GET | `/v1/integrations/meta/jobs` | [apps/api/pao/integrations/meta/api.py:152](../apps/api/pao/integrations/meta/api.py#L152) | `jobs` |
| GET | `/v1/integrations/meta/snapshots` | [apps/api/pao/integrations/meta/api.py:159](../apps/api/pao/integrations/meta/api.py#L159) | `snapshots` |
| GET | `/v1/ads/targets` | [apps/api/pao/intelligence_api.py:155](../apps/api/pao/intelligence_api.py#L155) | `targets` |
| PUT | `/v1/ads/targets` | [apps/api/pao/intelligence_api.py:162](../apps/api/pao/intelligence_api.py#L162) | `set_target` |
| GET | `/v1/ads/rules` | [apps/api/pao/intelligence_api.py:177](../apps/api/pao/intelligence_api.py#L177) | `rules` |
| PUT | `/v1/ads/rules/{rule_id}` | [apps/api/pao/intelligence_api.py:185](../apps/api/pao/intelligence_api.py#L185) | `set_rule` |
| POST | `/v1/ads/intelligence/analyze` | [apps/api/pao/intelligence_api.py:193](../apps/api/pao/intelligence_api.py#L193) | `analyze_now` |
| GET | `/v1/ads/anomalies` | [apps/api/pao/intelligence_api.py:214](../apps/api/pao/intelligence_api.py#L214) | `anomalies` |
| POST | `/v1/ads/anomalies/{anomaly_id}/acknowledge` | [apps/api/pao/intelligence_api.py:224](../apps/api/pao/intelligence_api.py#L224) | `acknowledge` |
| GET | `/v1/ads/recommendations` | [apps/api/pao/intelligence_api.py:231](../apps/api/pao/intelligence_api.py#L231) | `recommendations` |
| POST | `/v1/ads/recommendations/{recommendation_id}/dismiss` | [apps/api/pao/intelligence_api.py:241](../apps/api/pao/intelligence_api.py#L241) | `dismiss` |
| GET | `/health` | [apps/api/pao/main.py:34](../apps/api/pao/main.py#L34) | `health` |
| GET | `/ready` | [apps/api/pao/main.py:39](../apps/api/pao/main.py#L39) | `ready` |
| POST | `/v1/auth/token` | [apps/api/pao/main.py:50](../apps/api/pao/main.py#L50) | `login` |
| GET | `/v1/me` | [apps/api/pao/main.py:63](../apps/api/pao/main.py#L63) | `me` |
| POST | `/v1/sessions` | [apps/api/pao/main.py:70](../apps/api/pao/main.py#L70) | `create_session` |
| GET | `/v1/sessions` | [apps/api/pao/main.py:86](../apps/api/pao/main.py#L86) | `list_sessions` |
| DELETE | `/v1/sessions/{session_id}` | [apps/api/pao/main.py:94](../apps/api/pao/main.py#L94) | `delete_session` |
| GET | `/v1/sessions/{session_id}` | [apps/api/pao/main.py:108](../apps/api/pao/main.py#L108) | `get_session` |
| POST | `/v1/runs` | [apps/api/pao/main.py:120](../apps/api/pao/main.py#L120) | `create_run` |
| GET | `/v1/runs/{run_id}` | [apps/api/pao/main.py:150](../apps/api/pao/main.py#L150) | `get_run` |
| POST | `/v1/runs/{run_id}/cancel` | [apps/api/pao/main.py:155](../apps/api/pao/main.py#L155) | `cancel` |
| GET | `/v1/runs/{run_id}/events` | [apps/api/pao/main.py:167](../apps/api/pao/main.py#L167) | `events` |
| GET | `/v1/brands` | [apps/api/pao/memory_api.py:35](../apps/api/pao/memory_api.py#L35) | `brands` |
| POST | `/v1/brands` | [apps/api/pao/memory_api.py:41](../apps/api/pao/memory_api.py#L41) | `create_brand` |
| PATCH | `/v1/sessions/{session_id}` | [apps/api/pao/memory_api.py:54](../apps/api/pao/memory_api.py#L54) | `toggle_memory` |
| GET | `/v1/memory/status` | [apps/api/pao/memory_api.py:62](../apps/api/pao/memory_api.py#L62) | `memory_status` |
| GET | `/v1/memory` | [apps/api/pao/memory_api.py:73](../apps/api/pao/memory_api.py#L73) | `list_memory` |
| POST | `/v1/memory` | [apps/api/pao/memory_api.py:82](../apps/api/pao/memory_api.py#L82) | `create_memory` |
| POST | `/v1/memory/search` | [apps/api/pao/memory_api.py:96](../apps/api/pao/memory_api.py#L96) | `search_memory` |
| PATCH | `/v1/memory/{memory_id}` | [apps/api/pao/memory_api.py:106](../apps/api/pao/memory_api.py#L106) | `edit_memory` |
| DELETE | `/v1/memory/{memory_id}` | [apps/api/pao/memory_api.py:132](../apps/api/pao/memory_api.py#L132) | `delete_memory` |
| GET | `/v1/model-providers` | [apps/api/pao/model_api.py:51](../apps/api/pao/model_api.py#L51) | `listing` |
| POST | `/v1/model-providers/{provider}/connect` | [apps/api/pao/model_api.py:57](../apps/api/pao/model_api.py#L57) | `connect` |
| GET | `/v1/model-providers/{provider}/models` | [apps/api/pao/model_api.py:76](../apps/api/pao/model_api.py#L76) | `models` |
| PUT | `/v1/model-providers/{provider}/model` | [apps/api/pao/model_api.py:86](../apps/api/pao/model_api.py#L86) | `set_model` |
| POST | `/v1/model-providers/{provider}/default` | [apps/api/pao/model_api.py:95](../apps/api/pao/model_api.py#L95) | `set_default` |
| POST | `/v1/model-providers/{provider}/test` | [apps/api/pao/model_api.py:103](../apps/api/pao/model_api.py#L103) | `test` |
| DELETE | `/v1/model-providers/{provider}` | [apps/api/pao/model_api.py:117](../apps/api/pao/model_api.py#L117) | `disconnect` |
| GET | `/v1/platform/catalog` | [apps/api/pao/platform_api.py:23](../apps/api/pao/platform_api.py#L23) | `catalog` |
| POST | `/v1/reports/{report_id}/reconciliation-preview` | [apps/api/pao/report_api.py:110](../apps/api/pao/report_api.py#L110) | `reconciliation_preview` |
| POST | `/v1/reports` | [apps/api/pao/report_api.py:124](../apps/api/pao/report_api.py#L124) | `create` |
| GET | `/v1/reports` | [apps/api/pao/report_api.py:143](../apps/api/pao/report_api.py#L143) | `reports` |
| GET | `/v1/reports/dashboard` | [apps/api/pao/report_api.py:154](../apps/api/pao/report_api.py#L154) | `dashboard` |
| GET | `/v1/reports/{report_id}` | [apps/api/pao/report_api.py:169](../apps/api/pao/report_api.py#L169) | `get_report` |
| POST | `/v1/reports/{report_id}/telegram` | [apps/api/pao/report_api.py:174](../apps/api/pao/report_api.py#L174) | `send_telegram` |
| GET | `/v1/reports/configuration/schedules` | [apps/api/pao/report_api.py:185](../apps/api/pao/report_api.py#L185) | `schedules` |
| PUT | `/v1/reports/configuration/schedules` | [apps/api/pao/report_api.py:193](../apps/api/pao/report_api.py#L193) | `set_schedule` |
| POST | `/v1/skills/investigate-ads-drop/attribution-preview` | [apps/api/pao/skill_api.py:70](../apps/api/pao/skill_api.py#L70) | `attribution_preview` |
| POST | `/v1/skills/{skill_id}/analysis-preview` | [apps/api/pao/skill_api.py:95](../apps/api/pao/skill_api.py#L95) | `analysis_preview` |
| POST | `/v1/skills/daily-business-brief/preview` | [apps/api/pao/skill_api.py:124](../apps/api/pao/skill_api.py#L124) | `preview` |
| GET | `/v1/skills` | [apps/api/pao/skill_api.py:142](../apps/api/pao/skill_api.py#L142) | `catalog` |
| POST | `/v1/skills/{skill_id}/validate` | [apps/api/pao/skill_api.py:148](../apps/api/pao/skill_api.py#L148) | `preflight` |
| GET | `/v1/goals` | [apps/api/pao/task_api.py:437](../apps/api/pao/task_api.py#L437) | `list_goals` |
| POST | `/v1/goals` | [apps/api/pao/task_api.py:447](../apps/api/pao/task_api.py#L447) | `create_goal` |
| GET | `/v1/goals/{goal_id}` | [apps/api/pao/task_api.py:466](../apps/api/pao/task_api.py#L466) | `get_goal` |
| PATCH | `/v1/goals/{goal_id}` | [apps/api/pao/task_api.py:475](../apps/api/pao/task_api.py#L475) | `update_goal` |
| GET | `/v1/projects` | [apps/api/pao/task_api.py:515](../apps/api/pao/task_api.py#L515) | `list_projects` |
| POST | `/v1/projects` | [apps/api/pao/task_api.py:525](../apps/api/pao/task_api.py#L525) | `create_project` |
| PATCH | `/v1/projects/{project_id}` | [apps/api/pao/task_api.py:538](../apps/api/pao/task_api.py#L538) | `update_project` |
| GET | `/v1/tasks` | [apps/api/pao/task_api.py:562](../apps/api/pao/task_api.py#L562) | `list_tasks` |
| POST | `/v1/tasks` | [apps/api/pao/task_api.py:581](../apps/api/pao/task_api.py#L581) | `create_task` |
| GET | `/v1/tasks/{task_id}` | [apps/api/pao/task_api.py:619](../apps/api/pao/task_api.py#L619) | `get_task` |
| PATCH | `/v1/tasks/{task_id}` | [apps/api/pao/task_api.py:624](../apps/api/pao/task_api.py#L624) | `update_task` |
| GET | `/v1/tasks/{task_id}/attempts` | [apps/api/pao/task_api.py:703](../apps/api/pao/task_api.py#L703) | `list_attempts` |
| POST | `/v1/tasks/{task_id}/attempts` | [apps/api/pao/task_api.py:710](../apps/api/pao/task_api.py#L710) | `create_attempt` |
| PATCH | `/v1/tasks/{task_id}/attempts/{attempt_id}` | [apps/api/pao/task_api.py:771](../apps/api/pao/task_api.py#L771) | `update_attempt` |
| GET | `/v1/tasks/{task_id}/attempts/{attempt_id}/skill-replay` | [apps/api/pao/task_api.py:830](../apps/api/pao/task_api.py#L830) | `attempt_skill_replay` |
| GET | `/v1/tasks/{task_id}/comments` | [apps/api/pao/task_api.py:849](../apps/api/pao/task_api.py#L849) | `list_comments` |
| POST | `/v1/tasks/{task_id}/comments` | [apps/api/pao/task_api.py:855](../apps/api/pao/task_api.py#L855) | `create_comment` |
| GET | `/v1/tasks/{task_id}/activity` | [apps/api/pao/task_api.py:867](../apps/api/pao/task_api.py#L867) | `list_activity` |
| POST | `/v1/telegram/webhook` | [apps/api/pao/telegram.py:271](../apps/api/pao/telegram.py#L271) | `webhook` |
| GET | `/v1/telegram/status` | [apps/api/pao/telegram.py:297](../apps/api/pao/telegram.py#L297) | `status` |
| GET | `/v1/tools` | [apps/api/pao/tool_api.py:66](../apps/api/pao/tool_api.py#L66) | `registry` |
| GET | `/v1/runs/{run_id}/tools` | [apps/api/pao/tool_api.py:72](../apps/api/pao/tool_api.py#L72) | `snapshot` |
| POST | `/v1/runs/{run_id}/tools` | [apps/api/pao/tool_api.py:80](../apps/api/pao/tool_api.py#L80) | `create` |
| POST | `/v1/tools/calls/{call_id}/decision` | [apps/api/pao/tool_api.py:88](../apps/api/pao/tool_api.py#L88) | `approval` |
| GET | `/v1/voice/status` | [apps/api/pao/voice_api.py:21](../apps/api/pao/voice_api.py#L21) | `status` |
| POST | `/v1/voice/transcriptions` | [apps/api/pao/voice_api.py:30](../apps/api/pao/voice_api.py#L30) | `transcribe` |
| POST | `/v1/voice/speech` | [apps/api/pao/voice_api.py:49](../apps/api/pao/voice_api.py#L49) | `speech` |
| GET | `/v1/warehouse/metrics` | [apps/api/pao/warehouse_api.py:102](../apps/api/pao/warehouse_api.py#L102) | `metrics` |
| GET | `/v1/warehouse/entities` | [apps/api/pao/warehouse_api.py:116](../apps/api/pao/warehouse_api.py#L116) | `entities` |
| GET | `/v1/warehouse/schedules` | [apps/api/pao/warehouse_api.py:126](../apps/api/pao/warehouse_api.py#L126) | `schedules` |
| PUT | `/v1/warehouse/schedules` | [apps/api/pao/warehouse_api.py:133](../apps/api/pao/warehouse_api.py#L133) | `schedule` |

