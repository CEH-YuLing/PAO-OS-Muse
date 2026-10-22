# PAO — Checklist toàn hệ thống và tương thích

Ngày kiểm tra lại: **23/09/2026**. Repository: `F:/Apex/apex`. Đối chiếu master spec đính kèm `0d24d7ec-8dce-4b04-a3b0-a6979eecbb8d`, mã nguồn, migration, cấu hình local, database đang chạy và các bộ kiểm thử.

## Kết luận hiện tại

PAO đã triển khai local tuần tự đến **Phase 18**. Phase 0–6 có chức năng local hoạt động; Telegram đã chạy với bot thật và lỗi approval tin nhắn dài đã sửa. Phase 7–18 đã có mã nguồn, migration, API và UI; database chính đã lên `0017`. Temporal và Voice đều đang bật và đã qua smoke test thật. Meta/Google Ads chưa kết nối dữ liệu thật; Meta Write và Autopilot vẫn khóa, nên phần Ads mới đạt nghiệm thu kỹ thuật local, **chưa đạt nghiệm thu tích hợp thực tế**.

PAO đã phủ phạm vi kỹ thuật Phase 0–18 nhưng chưa production-ready và chưa phải Advertising Operating System đã nghiệm thu thực tế. Không dùng số phase để suy ra phần trăm khối lượng vì Ads, attribution và automation vẫn cần dữ liệu/account thật, fault test và vận hành dài hạn.

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
| 15 | Attribution + CRM | **Đã triển khai, chờ dữ liệu thật** | Normalized GA4/CRM/orders ingestion, deterministic attribution, business metrics, tracking alerts và optimization blocker; hoàn toàn read-only. |
| 16 | Google Ads | **Đã triển khai read-only, chờ nghiệm thu thật** | OAuth, refresh token mã hóa, accessible accounts, GAQL bounded `SELECT`, account/history sync và warehouse dùng chung. `GOOGLE_ADS_ENABLED=false`, 0 connection/job. |
| 17 | Advanced Automation | **Đạt local** | Temporal Server/worker self-host đang chạy; workflow thật đã nhận approval signal và hoàn tất. Chưa fault-test workflow chờ nhiều ngày. |
| 18 | Voice | **Đạt local trên CPU** | Browser VAD, Faster Whisper Small CPU int8, Windows SAPI TTS, interruption và Orb voice states; đã smoke test TTS→STT thật. |

TikTok Ads và competitor intelligence xuất hiện trong master spec tổng thể nhưng chưa được gán phase riêng trong 0–18; hiện chưa triển khai.

## 2. Bản local đang chạy

| Thành phần | Kết quả kiểm tra |
|---|---|
| API | PID/start-time khớp hồ sơ runtime; `/ready` trả HTTP 200. |
| Web | PID/start-time khớp; `http://127.0.0.1:3100/` trả HTTP 200; build Phase 18 đã nạp. |
| Worker | PID/start-time khớp; cron dispatch chạy mỗi 10 giây, log không có lỗi hiện tại. |
| Telegram bridge | PID/start-time khớp; polling đang bật. DB có 1 peer, 6 updates và 9 deliveries. |
| Ollama | PID/start-time khớp; có model chat 4B, embeddinggemma 300M và một model cache 4B. |
| PostgreSQL | Container running/healthy, DB revision `0017`, volume `apex_postgres-data`. |
| Redis | Container running/healthy, AOF volume `apex_redis-data`. |
| SearXNG | Container running, image cố định bằng digest, restart `unless-stopped`. |
| Temporal | Server `1.30.6` running/healthy tại `127.0.0.1:7233`; namespace `default` và worker `pao-automation` hoạt động. |

Database hiện có: 1 user, 1 workspace, 7 sessions, 45 messages, 23 runs, 25 agent runs, 0 active runs. Meta/Google Ads/warehouse/reporting/intelligence/write/approval có 0 dữ liệu production; Automation projection có 0 row và Voice audit có 2 metadata row.

## 3. Kiểm thử tương thích vừa chạy lại

| Kiểm tra | Kết quả | Giới hạn |
|---|---|---|
| Backend + schema | **156 passed**, `alembic check` đạt | Chạy migration `base → 0017` trên `pao_test` và Redis DB 15; không chạm DB người dùng. |
| Runtime state/SSE | **8 passed** | Lifecycle, replay, duplicate/out-of-order, cancel/fail và UTF-8 chunk. |
| Browser acceptance | **Đạt toàn bộ** | API giả lập riêng; toàn bộ luồng Phase 1–18, gồm Temporal approval UI và Voice capability/VAD controls. |
| TypeScript | **Đạt** | Web và OpenAPI-generated types biên dịch được. |
| Python dependencies | **Đạt** | `pip check` sạch; Python 3.12.14. |
| Node dependencies | **Đạt cấu trúc** | Node 24, Next 15.3.8, React 19.2.8, TypeScript 5.9.3. |
| OpenAPI | **Đạt sinh mã** | 83 paths; có Automation workflow/signal và Voice status/STT/TTS APIs cùng contract TypeScript mới. |
| Migration triển khai | **Đạt** | Backup đọc được bằng `pg_restore --list`; counts 50 bảng cũ trước/sau khớp; DB `0017`, 56 bảng public hiện tại. |
| Local model acceptance | **Đạt** | Memory recall/brand isolation, planner Researcher→Editor→Chief và SearXNG/tool approval đều chạy thật trên `pao_test`. |
| Temporal smoke | **Đạt** | Server/namespace/worker thật; workflow nhận `approve` signal, chạy activity và hoàn tất. |
| Voice smoke | **Đạt** | Windows SAPI tạo WAV 234.830 byte; Faster Whisper CPU int8 trả transcript local. |
| Secret scan | **Đạt phạm vi repo** | Không thấy bot token/App Secret/encryption key thật; `.env` và `.runtime` được Git ignore. |
| Diff hygiene | **Đạt cú pháp** | Chỉ có cảnh báo LF→CRLF, không có whitespace error. Worktree chưa commit. |

Đây không phải security/CVE audit, penetration test, load test hay chứng nhận dependency tương lai. Browser, Meta và Google Ads HTTP tests dùng dữ liệu giả lập; chưa chứng minh scopes/fields/rate limit của tài khoản Meta thật.

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

### Google Ads read-only

- [x] OAuth dùng scope `adwords`, offline access, one-time state/cookie và refresh token mã hóa Fernet.
- [x] Hỗ trợ `customers:listAccessibleCustomers`, login customer ID tùy chọn và Google Ads API `v25`.
- [x] Transport chỉ cho token endpoint, accessible customers và GAQL `SELECT`; không có mutate endpoint.
- [x] Account và historical sync chạy qua worker, giới hạn ngày/row/response, timeout/retry read và atomic publish.
- [x] `AdGroup` map thành `adset`; cost micros dùng Decimal; conversions/value dùng trường platform-neutral, không giả định mọi conversion là purchase.
- [x] Meta và Google dùng chung `ad_entities`/`ad_metrics` với foreign key và check constraint theo platform.
- [x] `GOOGLE_ADS_ENABLED=false`; không có Google write hoặc Autopilot trong Phase 16.
- [ ] Chưa cấu hình Google Cloud OAuth client hoặc kết nối tài khoản thật; production hiện 0 connection/job/entity/metric Google.
- [ ] Chưa nghiệm thu quota, manager-account child hierarchy, timezone/currency và GAQL field compatibility bằng tài khoản thật.

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

### Advanced Automation

- [x] Temporal workflow allowlist cho approval wait và follow-up; ARQ vẫn xử lý job ngắn hiện có.
- [x] Durable timer, approve/reject/cancel signal, query state và execution timeout.
- [x] Idempotent workflow ID/request key, optimistic version và workspace RBAC.
- [x] PostgreSQL projection/audit cho UI; Temporal history là execution authority.
- [x] Compose profile tạo schema/server/namespace và worker riêng; cài mới mặc định tắt nhưng bản local hiện tại đã bật.
- [x] Workflow thật đã nhận signal approval, chạy activity và hoàn tất; Temporal sandbox tách khỏi cấu hình/SQLAlchemy.
- [ ] Chưa fault-test có chủ đích qua restart worker/server giữa lúc workflow chờ hoặc wait nhiều ngày trên máy thật.

### Voice local

- [x] Browser MediaRecorder, echo/noise controls, RMS VAD, silence auto-stop và hard limit 30 giây.
- [x] Raw audio content-type allowlist, 10 MiB limit, rate limit và session/workspace RBAC.
- [x] Faster Whisper Small chỉ đọc model local, CPU int8 và không cloud fallback.
- [x] Windows SAPI TTS local, Piper boundary, auto playback và bấm nói để ngắt playback/run.
- [x] Orb hiển thị listening/processing/reasoning/speaking.
- [x] Audit chỉ lưu metadata; không lưu audio, transcript hoặc nội dung TTS.
- [x] Smoke test thật TTS→WAV→STT đạt; lần gần nhất TTS khoảng 0,8 giây và STT khoảng 16,5 giây trên cấu hình hiện tại.
- [ ] Chưa nghiệm thu microphone thật thủ công trong browser; giọng Windows mặc định phát âm tiếng Việt còn hạn chế.

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
- [x] Landing CVR, CRM funnel, actual orders/revenue và tracking discrepancy có ở Phase 15; tracking unhealthy khóa recommendation mạnh.

### Creative Intelligence

- [x] Asset/metadata/performance/features/learnings là bảng chuẩn hóa, có analysis run và source lineage.
- [x] Current/baseline aggregate từ daily ad metrics; không gọi Meta hoặc LLM trong lúc phân tích.
- [x] Fatigue cần suy giảm hiệu suất + delivery saturation + ít nhất ba tín hiệu; frequency đơn lẻ không đủ.
- [x] Creative dùng nhiều ad không cộng reach; frequency trả NULL thay vì số sai.
- [x] Metadata đủ product/brand/market/language/format/duration/hook/angle/offer/CTA/creator/landing page, optimistic version và RBAC.
- [x] Learning chỉ sinh khi có ít nhất hai nhóm metadata đủ minimum impressions, lưu metric/evidence/confidence.
- [x] Fatigue brief định lượng 5 hooks, 3 angles, 2 CTA; không tự sản xuất hoặc launch asset.
- [ ] Chưa có dữ liệu Meta production để đối chiếu winner/fatigue với Ads Manager.
### Attribution + CRM

- [x] Nguồn GA4/CRM/orders chuẩn hóa, batch tối đa 500 rows, idempotency và RBAC.
- [x] Chỉ deterministic campaign/lead link; record thiếu hoặc mơ hồ giữ `unattributed`.
- [x] CRM cohort và stage as-of cuối kỳ; order có thể liên kết lead cũ mà không làm sai cohort.
- [x] Landing CVR, CPL, CPQL, cost appointment, CAC, revenue/lead và actual revenue.
- [x] Tracking discrepancy alert có acknowledge/resolve; unhealthy khóa recommendation mạnh và hạ confidence.
- [x] Identifier người dùng chỉ nhận SHA-256; không nhận email/tên/số điện thoại thô.
- [ ] Chưa có dữ liệu GA4/CRM/orders production hoặc adapter OAuth trực tiếp cho từng vendor.

## 5. Các điểm còn rủi ro

### F2 — Tự phục hồi dịch vụ chưa đầy đủ

PostgreSQL và Redis đang khỏe nhưng Docker restart policy là `no`; SearXNG dùng `unless-stopped`, Temporal dùng `on-failure`. API/ARQ worker/Temporal worker/web/Ollama/Telegram dùng `Start-Process`, chưa có supervisor/service sau process death hoặc Windows reboot. `/ready` chỉ đo DB, migration table và Redis; snapshot `verify_system_local.py` mới kiểm tra thêm process, Voice, Telegram và Temporal nhưng chưa thay thế giám sát liên tục.

### F3 — Native và Docker app chưa tương đương

Native Windows là đường chạy đã nghiệm thu. Docker app profile có API/worker/web nhưng không copy `scripts` vào API image và không có Telegram bridge service. Chưa có E2E cho toàn bộ app container/Linux.

### F4 — Production readiness còn thiếu

Chưa CI, staging, load test, penetration/CVE audit, OTel/metrics/alerting, scheduled backup, restore drill hoặc disaster-recovery runbook. Backup chỉ mới kiểm tra mục lục. `.env` chứa credential plaintext trên filesystem; token Meta trong DB có mã hóa nhưng bot token/App Secret phụ thuộc quyền bảo vệ máy. Audit table không chống DBA sửa.

### F5 — Source control chưa đóng gói

Worktree còn toàn bộ monorepo/rebrand/phases chưa commit, gồm file cũ bị xóa và cây mới chưa tracked. Bản local vẫn chạy, nhưng lịch sử khó review/phục hồi nếu mất workspace. Chưa commit/push vì người dùng chưa yêu cầu.

### F6 — Ads và attribution chưa nghiệm thu với dữ liệu thật

Phase 7–16 tương thích nội bộ qua contract và test giả lập, nhưng chưa có Meta/Google Ads connection, warehouse rows, report, intelligence, policy, action, analytics event, CRM lead hoặc order thật. Trước khi bật live write/Autopilot cần chạy một account với khoảng ngày ngắn, đối chiếu warehouse/report với Meta Ads Manager, kiểm tra detector/scheduler một chu kỳ và nghiệm thu approval + worker ở dry-run.

## 6. An toàn hiện tại

- [x] Meta live write đang tắt; endpoint action chỉ tạo snapshot khi có connection hợp lệ và dry-run là mặc định.
- [x] Lịch warehouse mặc định tắt; owner/admin chỉ bật sau sync thủ công thành công.
- [x] Meta/Telegram secrets không trả về frontend hoặc provider logs.
- [x] Test dùng DB/Redis riêng; fixture chặn nhầm DB chính.
- [x] Deployment Phase 18 có backup/count comparison, không reset volume và không gọi provider write.
- [x] Phase 11 lưu compensating action và khóa write bằng cấu hình.
- [x] Phase 12 buộc mọi quyết định qua Approval Service và giữ Meta write ở worker.
- [x] Phase 13 có policy DB, kill switches và emergency freeze; cài mới Observer và runtime gates mặc định OFF.
- [ ] Chưa fault/load/security test hoặc Meta dry-run thực tế để cho phép bật Autopilot.

## 7. Đối chiếu nhóm yêu cầu master spec

| Nhóm mục | Trạng thái |
|---|---|
| 0–18: nguyên tắc/stack/kiến trúc/runtime | **Một phần đến đạt local**; Temporal đã có, còn thiếu object storage, OTel/Sentry và production ops. |
| 19–28: memory/agents/orchestration | **Đạt phạm vi Phase 3–4**; chưa đủ toàn bộ agent chuyên ngành cuối cùng. |
| 29–36: integrations/Meta/warehouse/metrics/sync/raw | **Đã triển khai Phase 7–8**, chờ Meta thật. Raw chỉ debug; normalized DB là nguồn chính. |
| 37–43: intelligence/recommendations/actions | **Phase 10–11 đã triển khai intelligence, advisor recommendations và Ads action Copilot**; chờ dữ liệu Meta thật. |
| 44–50: reports/delivery/dashboard | **Phase 9 đã triển khai daily/weekly/Telegram/UI**; monthly/custom/email và intelligence trong mục 47–50 chưa có. |
| 51–58: approval/policy/autopilot | Approval Ads **đã có ở Phase 12**; policy và Limited Autopilot fail-closed **đã có ở Phase 13 nhưng đang tắt**. |
| 59–66: write/Google/TikTok/normalized model | Meta write Copilot **đã có nhưng bị khóa**; Google Ads read-only và normalized warehouse dùng chung **đã có**; TikTok chưa. |
| 67–79: action/workflow/locking/rate limit | Durable Ads actions, approval version/expiry, worker queue, resource lock, audit và no-blind-retry **đã có ở Phase 11–12**; Temporal workflow dài hạn cơ bản đã có ở Phase 17, theo dõi Ads 24h/72h/7d chưa có. |
| 80–96: security/audit/secrets/retention | **Một phần**; auth/RBAC/audit/encryption Meta có, production controls chưa đủ. |
| 97–129: observability/tests/CI/deployment/DR | **Một phần**; local tests/health/backup có, CI/staging/monitoring/restore/supervision thiếu. |
| 130–135: Phase 4–9 | **Đã triển khai tuần tự local**; Phase 7–9 chờ Meta/report thật. |
| 136–144: Phase 10–18 | **Đã triển khai tuần tự local**; Temporal và Voice đang chạy local, Voice dùng CPU. |
| 145–153: coding/safety/MVP/end state | Giữ triển khai tuần tự, write khóa mặc định và không commit secret; end-state Ads Assistant chưa đạt. |

## 8. Thứ tự tiếp theo

1. Nghiệm thu Phase 7–13 với Meta thật theo thứ tự: OAuth/read sync, daily/hourly warehouse, report, targets, anomaly/recommendation, action + approval + worker **dry-run**, rồi policy ở Observer/Advisor; đối chiếu Ads Manager và không bật live write/Autopilot trong bước này.
2. Xử lý F2–F3: restart policy/supervisor, health mở rộng, bridge lock recovery và chọn native hay Compose làm deployment chuẩn.
3. Backup định kỳ + restore drill vào DB tách biệt; thêm CI cho backend/runtime/contracts/build.
4. Chỉ cân nhắc bật Limited Autopilot sau fault/load/security tests và nghiệm thu policy/Phase 12 dry-run bằng tài khoản thật.
5. Nghiệm thu Phase 14 trên warehouse thật: tối thiểu sáu ngày ad-level daily data, gắn metadata cho hai creative và đối chiếu learning/fatigue với Ads Manager.
6. Nghiệm thu Phase 15 bằng export/webhook GA4, CRM và orders đã loại PII; đối chiếu Meta conversions, actual orders/revenue, unattributed và tracking alert trước khi dùng recommendation.
7. Cấu hình Google Cloud OAuth rồi nghiệm thu Phase 16 read-only với một account và khoảng ngày ngắn; đối chiếu cost/click/conversion/value với Google Ads trước khi mở rộng manager hierarchy.
8. Fault-test Temporal trong một cửa sổ riêng: giữ workflow chờ, restart worker/server, xác nhận replay/timer rồi mới dùng cho tác vụ nhiều ngày.
9. Nghiệm thu microphone thật trên trình duyệt, chọn voice tiếng Việt/Piper tốt hơn và đo STT latency trên các độ dài 5/15/30 giây.

## 9. Bằng chứng

- [Phase 7 Meta read-only](PHASE-7-META.md)
- [Phase 8 Ads Warehouse](PHASE-8-WAREHOUSE.md)
- [Phase 9 Ads Reporting](PHASE-9-REPORTING.md)
- [Phase 10 Performance Intelligence](PHASE-10-PERFORMANCE-INTELLIGENCE.md)
- [Phase 11 Meta Write](PHASE-11-META-WRITE.md)
- [Phase 12 Ads Approval](PHASE-12-ADS-APPROVAL.md)
- [Phase 13 Limited Autopilot](PHASE-13-LIMITED-AUTOPILOT.md)
- [Phase 14 Creative Intelligence](PHASE-14-CREATIVE-INTELLIGENCE.md)
- [Phase 15 Attribution + CRM](PHASE-15-ATTRIBUTION-CRM.md)
- [Phase 16 Google Ads](PHASE-16-GOOGLE-ADS.md)
- [Phase 17 Advanced Automation](PHASE-17-ADVANCED-AUTOMATION.md)
- [Phase 18 Voice](PHASE-18-VOICE.md)
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
- Backup `.runtime/pre-phase-15-20260915-214756.dump`, 196.215 bytes; `pg_restore --list` đạt và counts 37 bảng cũ trước/sau khớp.
- `.runtime/phase-15-migration.json`, `.runtime/phase-15-health.json`, `.runtime/phase-15-attribution-crm-browser.png`.
- Backup `.runtime/pre-phase-16-20260922-121237.dump`, 235.162 bytes; `pg_restore --list` đạt và counts 45 bảng cũ trước/sau khớp.
- `.runtime/phase-16-migration.json`, `.runtime/phase-16-health.json`, `.runtime/phase-16-google-ads-browser.png`.
- Backup `.runtime/pre-phase-17-20260922-133046.dump`, 248.573 bytes; `pg_restore --list` đạt và counts 48 bảng cũ trước/sau khớp.
- `.runtime/phase-17-migration.json`, `.runtime/phase-17-health.json`, `.runtime/phase-17-automation-browser.png`.
- Backup cuối `.runtime/pre-phase-18-20260922-181341.dump`, 260.420 bytes; `pg_restore --list` đạt và counts 50 bảng cũ trước/sau khớp.
- `.runtime/phase-17-temporal-smoke.json`, `.runtime/system-health.json`.
- `.runtime/phase-18-migration.json`, `.runtime/phase-18-health.json`, `.runtime/phase-18-voice-browser.png`, `.runtime/phase-18-voice-smoke.json`.

Checklist này thay thế các mô tả audit lịch sử đã lỗi thời. Đây là kiểm tra chức năng/tương thích local, không phải chứng nhận production hoặc bảo mật toàn diện.


