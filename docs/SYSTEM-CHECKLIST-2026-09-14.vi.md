# PAO — Checklist toàn hệ thống và tương thích

Ngày kiểm tra lại: **15/09/2026**. Repository: `F:/Apex/apex`. Đối chiếu master spec đính kèm `0d24d7ec-8dce-4b04-a3b0-a6979eecbb8d`, mã nguồn, migration, cấu hình local, database đang chạy và các bộ kiểm thử.

## Kết luận hiện tại

PAO đã triển khai local tuần tự đến **Phase 14**. Phase 0–6 có chức năng local hoạt động; Telegram đã chạy với bot thật và lỗi approval tin nhắn dài đã sửa. Phase 7–14 đã có mã nguồn, migration, API, UI và kiểm thử giả lập; database chính đã lên `0013`. Meta, Meta Write và Autopilot đang tắt, chưa có dữ liệu thật, nên Phase 7–14 mới đạt nghiệm thu kỹ thuật local, **chưa đạt nghiệm thu tích hợp thực tế**.

PAO chưa production-ready và chưa phải Advertising Operating System hoàn chỉnh. Phase 15–18 chưa triển khai. Không dùng số phase để suy ra phần trăm khối lượng vì attribution và automation có rủi ro lớn hơn các phase nền tảng.

## 1. Trạng thái theo phase

| Phase | Phạm vi | Trạng thái | Bằng chứng/giới hạn |
|---|---|---|---|
| 0 | Baseline | **Đạt local** | Repository đã khảo sát; giữ MIT và ghi công nguồn APEX-UI. |
| 1 | Backend foundation | **Đạt local** | FastAPI, PostgreSQL, Redis/ARQ, auth, workspace, chat, SSE, cancel, Ollama local. |
| 2 | Frontend runtime | **Đạt local** | Orb dùng trạng thái runtime thật; replay/reconnect/session isolation/cancel qua kiểm thử. |
| 3 | Memory | **Đạt local** | pgvector 768, scope user/workspace/brand, extraction/retrieval/conflict/tombstone và UI. DB hiện có 0 memory. |
| 4 | Agent Runtime | **Đạt local** | Chief + Researcher/Editor/Marketing, planner tối đa hai specialist, thực thi tuần tự, trace. Các node khác trên Orb vẫn là phần giới thiệu. |
| 5 | Tool Gateway | **Đạt phạm vi phase** | Registry/RBAC/approval/audit/idempotency; web search thật qua SearXNG. Email/calendar vẫn là mô phỏng. |
| 6 | Telegram | **Đạt local với bot thật** | Polling, whitelist, command, task/result, cancel và approval. Chưa fault-test mất DB lock và webhook thật. |
| 7 | Meta read-only | **Đã triển khai, chờ nghiệm thu thật** | OAuth, token mã hóa, accounts/campaigns/adsets/ads/Insights, snapshot atomic, UI. `META_ENABLED=false`, 0 connection/job/snapshot. |
| 8 | Ads Warehouse | **Đã triển khai, chờ dữ liệu thật** | Normalized entities/metrics, hourly/daily/historical, Decimal/NULL semantics, scheduler và UI. 0 entity/metric/schedule. |
| 9 | Ads Reporting | **Đã triển khai, chờ dữ liệu thật** | Daily/weekly snapshot, comparisons, coverage, dashboard, scheduler và Telegram outbox. DB hiện 0 report/delivery/schedule. |
| 10 | Performance Intelligence | **Đã triển khai, chờ dữ liệu thật** | Targets/guardrails, deterministic rules, same-weekday/hour anomalies, dedup alerts, Performance Analyst và structured advisor recommendations. |
| 11 | Meta Write | **Đã triển khai, live write đang khóa** | Copilot pause/resume/daily budget, snapshot/audit/idempotency/lock/compensation/no-blind-retry; dry-run mặc định. `META_WRITE_ENABLED=false`, 0 action/audit. |
| 12 | Ads Approval | **Đã triển khai, live write vẫn khóa** | Inbox/details, UI/Telegram approve/reject, expiry/version, worker handoff và audit; callback không gọi Meta. |
| 13 | Limited Autopilot | **Đã triển khai, đang khóa** | DB policy, bốn mode, global/Meta/workspace gates, sample/freshness/quiet/budget/action caps, worker recheck và emergency freeze. |
| 14 | Creative Intelligence | **Đã triển khai, chờ dữ liệu thật** | Metadata editor, current/baseline performance, fatigue đa tín hiệu, structured learnings và strategist brief; hoàn toàn read-only. |
| 15 | Attribution + CRM | **Chưa** | Chưa GA4, CRM, orders, leads, tracking quality. |
| 16 | Google Ads | **Chưa** | Schema có trường platform để mở rộng nhưng chưa có connector. |
| 17 | Advanced Automation | **Chưa** | Chưa Temporal/durable workflow/approval wait dài hạn. |
| 18 | Voice | **Chưa** | Chưa STT/TTS/VAD/realtime interruption. |

TikTok Ads và competitor intelligence xuất hiện trong master spec tổng thể nhưng chưa được gán phase riêng trong 0–18; hiện chưa triển khai.

## 2. Bản local đang chạy

| Thành phần | Kết quả kiểm tra |
|---|---|
| API | PID/start-time khớp hồ sơ runtime; `/ready` trả HTTP 200. |
| Web | PID/start-time khớp; `http://127.0.0.1:3100/` trả HTTP 200; build Phase 13 đã nạp. |
| Worker | PID/start-time khớp; cron dispatch chạy mỗi 10 giây, log không có lỗi hiện tại. |
| Telegram bridge | PID/start-time khớp; polling đang bật. DB có 1 peer, 6 updates và 9 deliveries. |
| Ollama | PID/start-time khớp; có model chat 4B, embeddinggemma 300M và một model cache 4B. |
| PostgreSQL | Container running/healthy, DB revision `0013`, volume `apex_postgres-data`. |
| Redis | Container running/healthy, AOF volume `apex_redis-data`. |
| SearXNG | Container running, image cố định bằng digest, restart `unless-stopped`. |

Database hiện có: 1 user, 1 workspace, 6 sessions, 39 messages, 20 runs, 22 agent runs, 0 active runs. Meta/warehouse/reporting/intelligence/write/approval có 0 connection, sync job, snapshot, entity, metric, warehouse schedule, report, report delivery, report schedule, target, rule, intelligence run, anomaly, recommendation, action và action audit.

## 3. Kiểm thử tương thích vừa chạy lại

| Kiểm tra | Kết quả | Giới hạn |
|---|---|---|
| Backend + schema | **138 passed**, `alembic check` đạt | Chạy migration trên `pao_test` và Redis DB 15; không chạm DB người dùng. |
| Runtime state/SSE | **8 passed** | Lifecycle, replay, duplicate/out-of-order, cancel/fail và UTF-8 chunk. |
| Browser acceptance | **Đạt toàn bộ** | API giả lập riêng; thêm Phase 14 creative performance/fatigue/brief/read-only cùng policy Phase 13 và toàn bộ luồng cũ. |
| TypeScript | **Đạt** | Web và OpenAPI-generated types biên dịch được. |
| Python dependencies | **Đạt** | `pip check` sạch; Python 3.12.14. |
| Node dependencies | **Đạt cấu trúc** | Node 24, Next 15.3.8, React 19.2.8, TypeScript 5.9.3. |
| OpenAPI | **Đạt sinh mã** | 60 paths; có Creative analyze/dashboard/metadata, runtime status, policy APIs và TypeScript contract mới. |
| Migration triển khai | **Đạt** | Backup đọc được bằng `pg_restore --list`; counts 29 bảng cũ trước/sau khớp; DB `0012`. |
| Secret scan | **Đạt phạm vi repo** | Không thấy bot token/App Secret/encryption key thật; `.env` và `.runtime` được Git ignore. |
| Diff hygiene | **Đạt cú pháp** | Chỉ có cảnh báo LF→CRLF, không có whitespace error. Worktree chưa commit. |

Đây không phải security/CVE audit, penetration test, load test hay chứng nhận dependency tương lai. Browser và Meta HTTP tests dùng dữ liệu giả lập; chưa chứng minh scopes/fields/rate limit của tài khoản Meta thật.

## 4. Checklist theo thành phần

### Nền tảng, auth và dữ liệu

- [x] JWT issuer/audience/expiry; mật khẩu Argon2; login rate limit theo IP và user.
- [x] Workspace RBAC; viewer không ghi; session/run có user/workspace scope.
- [x] UUID, foreign keys, unique/check constraints và row locking ở các luồng chính.
- [x] Health/readiness, migrations và durable DB outbox cho run/tool/memory/Meta.
- [ ] Chưa MFA/SSO, session revocation list hoặc quản trị nhiều workspace hoàn chỉnh.
- [ ] Chưa tenant quotas, retention policy hay export/delete workflow đầy đủ.

### AI runtime và Memory

- [x] Ollama local, không cloud fallback; profile CPU tuần tự, một model/job tại một thời điểm.
- [x] Timeout, cancel, partial output, SSE replay và persisted events.
- [x] Planner/specialists có prompt version và output lưu riêng; Chief tổng hợp cuối.
- [x] Memory có exact scope, opt-out, dedup/conflict và semantic retrieval.
- [ ] GTX 1060 6 GB chưa nghiệm thu do lỗi PTX lịch sử; hiện tắt CUDA/Vulkan.
- [ ] Chưa load test nhiều người dùng; i3-10105F/16 GB phù hợp cá nhân/nhóm nhỏ tuần tự.

### Tool Gateway và Telegram

- [x] Tool allowlist, permission, immutable proposal version, approval/reject, audit và idempotency.
- [x] Worker loss chuyển `unknown`, không tự retry side effect.
- [x] Telegram whitelist, update ledger, delivery outbox, UTF-16 chunk và approval đúng message/version.
- [x] Telegram Ads approval có Approve/Reject/Details; callback chỉ quyết định, worker mới thực thi và kết quả cuối được gửi riêng.
- [x] Telegram cảnh báo emergency freeze riêng cho owner/admin, có dedup theo policy version.
- [x] Không gửi email/calendar thật; test không gọi Telegram ngoài.
- [ ] Bridge chưa nằm trong Compose/app image và chưa có Windows service/supervisor.
- [ ] Advisory lock chưa fault-test/reacquire rõ ràng sau PostgreSQL restart.
- [ ] Delivery `unknown` chưa có UI reconciliation đầy đủ.

### Meta read-only

- [x] Chỉ yêu cầu `ads_read`; allowlist GET, POST duy nhất cho OAuth exchange.
- [x] OAuth state hash, cookie HttpOnly/SameSite, expiry/one-time use và callback log redaction.
- [x] Access token mã hóa Fernet trong DB; App Secret/master key chỉ ở local `.env`.
- [x] Cursor không theo URL provider; host cố định, timeout/retry/page/size/row limits.
- [x] Connection version fence, role recheck, stale-worker generation và atomic publish.
- [ ] Chưa cấu hình App ID/version/App Secret/redirect URI và đăng nhập Meta thật.
- [ ] Chưa kiểm chứng permission review, expiry, field availability và rate limit thực.
- [ ] Chưa long-lived token exchange/refresh; hết hạn phải kết nối lại.

### Meta Write Copilot

- [x] Action tách propose/approval/worker execute, lưu before/proposed/after state, lý do, nguồn, confidence và compensating action.
- [x] Owner/admin, user/workspace/connection/version/resource scope được kiểm tra lại khi execute.
- [x] Idempotency key kèm payload hash; Redis lock chặn hai action cùng resource chạy đồng thời.
- [x] Đọc lại provider state trước khi ghi; state drift chuyển `stale`.
- [x] Payload ghi chỉ cho pause/resume hoặc `daily_budget`; budget cap mặc định 20% và dùng minor units.
- [x] POST ghi đúng một lần; lỗi không xác định chuyển `unknown` và không tự retry.
- [x] Dry-run mặc định; approval UI/Telegram dùng version và audit append-only; recovery action `executing` quá hạn.
- [x] Live write bị khóa bởi `META_WRITE_ENABLED=false`; OAuth chỉ xin `ads_management` khi bật write.
- [x] Endpoint execute trực tiếp trả 409; Approve chỉ chuyển `queued`, ARQ worker mới được gọi Meta.
- [x] Approval inbox/detail, owner/admin approve/reject, TTL 24 giờ và các trạng thái rejected/expired/cancelled.
- [ ] Chưa nghiệm thu dry-run/live với Meta account thật; hiện 0 action và 0 audit.
- [x] Phase 13 policy engine chỉ tự duyệt analyst recommendation đủ guardrail; action thủ công vẫn qua Phase 12.
- [x] Global/Meta gates mặc định OFF; workspace halt, emergency freeze, quiet hours, sample/freshness, budget và action/day caps.
- [x] Worker recheck policy/version trước write; policy đổi hoặc freeze trả action về inbox, không gọi Meta.
- [ ] Chưa bật hoặc nghiệm thu Autopilot với account thật; production hiện 0 policy/audit/action.

### Ads Warehouse

- [x] Entity chuẩn hóa cho account/campaign/adset/ad/creative.
- [x] Metrics campaign/adset/ad, daily/hourly, currency/timezone/attribution/lineage.
- [x] Decimal cho tiền, BigInteger cho count; NULL không biến thành 0.
- [x] Tính CTR/CPC/CPM/frequency/CPL/CPA/ROAS có kiểm tra mẫu số.
- [x] Không cộng reach từ ad lên campaign; lấy trực tiếp từng level.
- [x] Restatement thay đúng phạm vi trong transaction; lỗi giữ bản tốt trước đó.
- [x] Scheduler 15–10.080 phút, lookback 1–31 ngày, mặc định tắt.
- [ ] Chưa kiểm chứng timezone/currency/DST/action aliases/attribution với dữ liệu thật.
- [ ] Attribution cố định `7d_click + 1d_view`, report time `impression`.
- [ ] Chưa account aggregate hoặc cross-currency; reporting giữ từng account/currency riêng.

### Ads Reporting

- [x] Daily/weekly report snapshot chỉ đọc normalized daily campaign metrics.
- [x] So sánh kỳ trước; daily thêm trung bình 7 ngày và chỉ tính khi baseline phủ đủ ngày.
- [x] Coverage/source lineage, Decimal/NULL semantics và campaign ranking theo spend.
- [x] Dashboard latest daily/weekly + daily trend; không gọi Meta khi đọc.
- [x] Manual/scheduled Telegram delivery dùng outbox, chunking và idempotency Phase 6.
- [x] Lịch theo timezone account, giờ local và weekday; mất quyền/peer sẽ tự tắt.
- [ ] Chưa có report thật vì warehouse production trống.
- [ ] Monthly/custom cron/email được hoãn; creative fatigue được đọc riêng từ Phase 14, không trộn vào report snapshot.

### Performance Intelligence

- [x] Account targets cho CPA/ROAS cùng minimum spend/impressions/clicks/conversions/run days/freshness.
- [x] Ba deterministic advisor rules được lưu trong `ads_rules`, có schema cố định và bật/tắt bằng RBAC.
- [x] Daily/hourly anomaly dùng tối đa bốn baseline cùng thứ/giờ, tối thiểu hai mẫu; alert fingerprint/dedup/ack/resolved.
- [x] Recommendation có confidence, risk, reason codes, explanation, proposed action, lineage và freshness.
- [x] Sample thấp tạo `LOW_SAMPLE_SIZE`; dữ liệu cũ tạo `STALE_DATA`; không dùng LLM làm rule engine.
- [x] Worker tự phân tích slot hoàn tất mới và chống lặp theo source update.
- [x] Performance Analyst chỉ nhận structured records đã lọc theo workspace/user/connection.
- [x] Recommendation Phase 10 vẫn `executable=false`; Phase 11 chỉ tạo action Copilot qua bước propose riêng.
- [ ] Chưa kiểm chứng baseline, target và recommendation với dữ liệu Meta thật.
- [x] Creative health đã có ở Phase 14 nhưng chưa được dùng để tự mở khóa scale action.
- [ ] Landing CVR/CRM attribution còn thiếu đến Phase 15; scale review vẫn ghi rõ blocker.

### Creative Intelligence

- [x] Asset/metadata/performance/features/learnings là bảng chuẩn hóa, có analysis run và source lineage.
- [x] Current/baseline aggregate từ daily ad metrics; không gọi Meta hoặc LLM trong lúc phân tích.
- [x] Fatigue cần suy giảm hiệu suất + delivery saturation + ít nhất ba tín hiệu; frequency đơn lẻ không đủ.
- [x] Creative dùng nhiều ad không cộng reach; frequency trả NULL thay vì số sai.
- [x] Metadata đủ product/brand/market/language/format/duration/hook/angle/offer/CTA/creator/landing page, optimistic version và RBAC.
- [x] Learning chỉ sinh khi có ít nhất hai nhóm metadata đủ minimum impressions, lưu metric/evidence/confidence.
- [x] Fatigue brief định lượng 5 hooks, 3 angles, 2 CTA; không tự sản xuất hoặc launch asset.
- [ ] Chưa có dữ liệu Meta production để đối chiếu winner/fatigue với Ads Manager.

## 5. Các điểm còn rủi ro

### F2 — Tự phục hồi dịch vụ chưa đầy đủ

PostgreSQL và Redis đang khỏe nhưng Docker restart policy là `no`; chỉ SearXNG dùng `unless-stopped`. API/worker/web/Ollama/Telegram dùng `Start-Process`, chưa có supervisor/service sau process death hoặc Windows reboot. `/ready` chỉ đo DB, migration table và Redis; không đo model, worker, bridge hoặc Meta scheduler.

### F3 — Native và Docker app chưa tương đương

Native Windows là đường chạy đã nghiệm thu. Docker app profile có API/worker/web nhưng không copy `scripts` vào API image và không có Telegram bridge service. Chưa có E2E cho toàn bộ app container/Linux.

### F4 — Production readiness còn thiếu

Chưa CI, staging, load test, penetration/CVE audit, OTel/metrics/alerting, scheduled backup, restore drill hoặc disaster-recovery runbook. Backup chỉ mới kiểm tra mục lục. `.env` chứa credential plaintext trên filesystem; token Meta trong DB có mã hóa nhưng bot token/App Secret phụ thuộc quyền bảo vệ máy. Audit table không chống DBA sửa.

### F5 — Source control chưa đóng gói

Worktree còn toàn bộ monorepo/rebrand/phases chưa commit, gồm file cũ bị xóa và cây mới chưa tracked. Bản local vẫn chạy, nhưng lịch sử khó review/phục hồi nếu mất workspace. Chưa commit/push vì người dùng chưa yêu cầu.

### F6 — Ads chưa nghiệm thu với dữ liệu thật

Phase 7–13 tương thích nội bộ qua contract và test giả lập, nhưng chưa có Meta connection, warehouse rows, report, intelligence, policy hoặc action thật. Trước khi bật live write/Autopilot cần chạy một account với khoảng ngày ngắn, đối chiếu warehouse/report với Meta Ads Manager, kiểm tra detector/scheduler một chu kỳ và nghiệm thu approval + worker ở dry-run.

## 6. An toàn hiện tại

- [x] Meta live write đang tắt; endpoint action chỉ tạo snapshot khi có connection hợp lệ và dry-run là mặc định.
- [x] Lịch warehouse mặc định tắt; owner/admin chỉ bật sau sync thủ công thành công.
- [x] Meta/Telegram secrets không trả về frontend hoặc provider logs.
- [x] Test dùng DB/Redis riêng; fixture chặn nhầm DB chính.
- [x] Deployment Phase 12 có backup/count comparison, không reset volume và không gọi provider write.
- [x] Phase 11 lưu compensating action và khóa write bằng cấu hình.
- [x] Phase 12 buộc mọi quyết định qua Approval Service và giữ Meta write ở worker.
- [x] Phase 13 có policy DB, kill switches và emergency freeze; cài mới Observer và runtime gates mặc định OFF.
- [ ] Chưa fault/load/security test hoặc Meta dry-run thực tế để cho phép bật Autopilot.

## 7. Đối chiếu nhóm yêu cầu master spec

| Nhóm mục | Trạng thái |
|---|---|
| 0–18: nguyên tắc/stack/kiến trúc/runtime | **Một phần đến đạt local**; thiếu object storage, Temporal, OTel/Sentry và production ops. |
| 19–28: memory/agents/orchestration | **Đạt phạm vi Phase 3–4**; chưa đủ toàn bộ agent chuyên ngành cuối cùng. |
| 29–36: integrations/Meta/warehouse/metrics/sync/raw | **Đã triển khai Phase 7–8**, chờ Meta thật. Raw chỉ debug; normalized DB là nguồn chính. |
| 37–43: intelligence/recommendations/actions | **Phase 10–11 đã triển khai intelligence, advisor recommendations và Ads action Copilot**; chờ dữ liệu Meta thật. |
| 44–50: reports/delivery/dashboard | **Phase 9 đã triển khai daily/weekly/Telegram/UI**; monthly/custom/email và intelligence trong mục 47–50 chưa có. |
| 51–58: approval/policy/autopilot | Approval Ads **đã có ở Phase 12**; policy và Limited Autopilot fail-closed **đã có ở Phase 13 nhưng đang tắt**. |
| 59–66: write/Google/TikTok/normalized model | Meta write Copilot **đã có nhưng bị khóa**; Google/TikTok chưa; normalized Meta đã có. |
| 67–79: action/workflow/locking/rate limit | Durable Ads actions, approval version/expiry, worker queue, resource lock, audit và no-blind-retry **đã có ở Phase 11–12**; theo dõi 24h/72h/7d và workflow dài hạn chưa có. |
| 80–96: security/audit/secrets/retention | **Một phần**; auth/RBAC/audit/encryption Meta có, production controls chưa đủ. |
| 97–129: observability/tests/CI/deployment/DR | **Một phần**; local tests/health/backup có, CI/staging/monitoring/restore/supervision thiếu. |
| 130–135: Phase 4–9 | **Đã triển khai tuần tự local**; Phase 7–9 chờ Meta/report thật. |
| 136–144: Phase 10–18 | **Phase 10–14 đã triển khai local**; Phase 15–18 chưa có. |
| 145–153: coding/safety/MVP/end state | Giữ triển khai tuần tự, write khóa mặc định và không commit secret; end-state Ads Assistant chưa đạt. |

## 8. Thứ tự tiếp theo

1. Nghiệm thu Phase 7–13 với Meta thật theo thứ tự: OAuth/read sync, daily/hourly warehouse, report, targets, anomaly/recommendation, action + approval + worker **dry-run**, rồi policy ở Observer/Advisor; đối chiếu Ads Manager và không bật live write/Autopilot trong bước này.
2. Xử lý F2–F3: restart policy/supervisor, health mở rộng, bridge lock recovery và chọn native hay Compose làm deployment chuẩn.
3. Backup định kỳ + restore drill vào DB tách biệt; thêm CI cho backend/runtime/contracts/build.
4. Chỉ cân nhắc bật Limited Autopilot sau fault/load/security tests và nghiệm thu policy/Phase 12 dry-run bằng tài khoản thật.
5. Nghiệm thu Phase 14 trên warehouse thật: tối thiểu sáu ngày ad-level daily data, gắn metadata cho hai creative và đối chiếu learning/fatigue với Ads Manager.

## 9. Bằng chứng

- [Phase 7 Meta read-only](PHASE-7-META.md)
- [Phase 8 Ads Warehouse](PHASE-8-WAREHOUSE.md)
- [Phase 9 Ads Reporting](PHASE-9-REPORTING.md)
- [Phase 10 Performance Intelligence](PHASE-10-PERFORMANCE-INTELLIGENCE.md)
- [Phase 11 Meta Write](PHASE-11-META-WRITE.md)
- [Phase 12 Ads Approval](PHASE-12-ADS-APPROVAL.md)
- [Phase 13 Limited Autopilot](PHASE-13-LIMITED-AUTOPILOT.md)
- [Phase 14 Creative Intelligence](PHASE-14-CREATIVE-INTELLIGENCE.md)
- [Sửa approval Telegram](TELEGRAM-APPROVAL-FIX-2026-09-14.md)
- Backup `.runtime/pre-phase-8-20260914-155418.dump`, 97.335 bytes; `pg_restore --list` đạt.
- `.runtime/phase-8-migration.json`, `.runtime/phase-8-health.json`.
- `.runtime/phase-8-warehouse-browser.png`, `.runtime/phase-7-meta-browser.png`.
- Backup `.runtime/pre-phase-9-20260914-204247.dump`, 118.035 bytes; `pg_restore --list` đạt và counts 19 bảng cũ không đổi.
- `.runtime/phase-9-health.json`, `.runtime/phase-9-reporting-browser.png`.
- Backup `.runtime/pre-phase-10-20260914-210945.dump`, 128.842 bytes; `pg_restore --list` đạt và counts 22 bảng cũ không đổi.
- `.runtime/phase-10-migration.json`, `.runtime/phase-10-health.json`, `.runtime/phase-10-intelligence-browser.png`.
- Backup `.runtime/pre-phase-11-20260915-110739.dump`, 149.129 bytes; `pg_restore --list` đạt và counts 27 bảng cũ không đổi.
- `.runtime/phase-11-migration.json`, `.runtime/phase-11-health.json`, `.runtime/phase-11-meta-write-browser.png`.
- Backup `.runtime/pre-phase-12-20260915-161159.dump`, 161.638 bytes; `pg_restore --list` đạt và counts 29 bảng trước/sau khớp.
- `.runtime/phase-12-migration.json`, `.runtime/phase-12-health.json`, `.runtime/phase-12-ads-approval-browser.png`.
- Backup `.runtime/pre-phase-13-20260915-164201.dump`, 161.638 bytes; `pg_restore --list` đạt và counts 29 bảng cũ trước/sau khớp.
- `.runtime/phase-13-migration.json`, `.runtime/phase-13-health.json`, `.runtime/phase-13-limited-autopilot-browser.png`.
- Backup `.runtime/pre-phase-14-20260915-171135.dump`, 196.215 bytes; `pg_restore --list` đạt và counts 31 bảng cũ trước/sau khớp.
- `.runtime/phase-14-migration.json`, `.runtime/phase-14-health.json`, `.runtime/phase-14-creative-intelligence-browser.png`.

Checklist này thay thế các mô tả audit lịch sử đã lỗi thời. Đây là kiểm tra chức năng/tương thích local, không phải chứng nhận production hoặc bảo mật toàn diện.
