# PAO — Kiến trúc đích và kế hoạch phát triển chi tiết

> Điều hướng 21/10/2026: tài liệu này giữ thiết kế và bằng chứng theo thời điểm.
> Thứ tự triển khai, trạng thái hiện hành và gói việc tiếp theo do
> [master roadmap](PAO-MASTER-GAP-AND-ROADMAP.vi.md) sở hữu.
> Không thực thi lại chỉ dẫn “tiếp theo” lịch sử bên dưới nếu khác master.

## Thay đổi thứ tự triển khai — 18/10/2026

Đã nghiệm thu lát cắt vòng vận hành local S5/M6, không xây thêm runner:
132Node/125focused backend/build23, browser native/DB riêng và bản cài thật.
[Báo cáo vòng local](LOCAL-OPERATING-CYCLE-2026-10-18.vi.md) sở hữu phạm vi và
giới hạn. Tiếp theo S6.1 dữ liệu thật local khi được chọn/cung cấp, không suy
fixture thành chất lượng provider hoặc quyền chạy Ads. Toàn M6/S6 chưa đóng.

Kiến trúc modular monolith/hybrid/multi-SME giữ nguyên. Người dùng chọn hoàn
thiện khung local → test dữ liệu thật local → pilot local → VPS/public sau.
Ưu tiên hạ tầng production trong kế hoạch17/10 dưới đây đã được hoãn
`deferred_by_user`, không phải đạt hoặc hủy các điều kiện an toàn. Theo thứ tự
[master18/10](PAO-MASTER-GAP-AND-ROADMAP.vi.md), tiếp tục lát cắt M6 UX và rà soát
vòng vận hành local trên nền S5 đã có, không sinh thêm roadmap/runner cạnh tranh.
Xem [báo cáo UX sáng/tối](LOCAL-UX-LIGHT-DARK-2026-10-18.vi.md). Production/S6
chưa hoàn tất; dữ liệu/credential/provider và action thật cần nghiệm thu riêng.

Ngày17/10/2026, Asia/Saigon. Target ứng dụng: `F:\PAO-ACOS`.
Trạng thái lúc lập kế hoạch: chỉ tài liệu. Lượt triển khai sau cùng ngày đã
nghiệm thu local trọn Giai đoạn1 — S6.2 và Giai đoạn2 — lát cắt M6 UX.
Hiện tại Giai đoạn3 — local_prepared=true, hosted CI đã đạt, production/S6 chưa đóng.
GitHub run39030584315 trên3151851 đạt18stage/2258backend/120Node/build23,
Python runtime57/0/npm0; artifact đã đối chiếu, main chưa merge. Xem
[nghiệm thu CI](PHASE3-HOSTED-CI-ACCEPTANCE-2026-10-17.vi.md).
Baseline CI Linux local:
18stage/2258backend/120Node/TypeScript/build23, audit Python57/0 và Windows111
đạt; runtime pin PyJWT2.15.1/cryptography50.0.2 đã cài/kiểm UI/health/replay3.
Private TLS/minimum-role/restart và clone153tables/3archive đọc tương thích,
execution khác binding vẫn bị chặn. Còn5high dev/braces chưa có patch và gates
host/public HTTPS/storage/keys/alerts/reboot/owner cần quyền/môi trường.
Xem [xử lý chốt](PHASE3-GATE-REMEDIATION-2026-10-17.vi.md);
[báo cáo lịch sử](PHASE3-CI-PRIVATE-PRODUCTION-2026-10-17.vi.md).
Xem [báo cáo M6](M6-COMMAND-CENTER-UX-LOCAL-ACCEPTANCE-2026-10-17.vi.md).
Xem [báo cáo hiện hành](S62-ACCOUNT-DATA-LOCAL-ACCEPTANCE-2026-10-17.vi.md).
Các cụm “chưa triển khai”/“tiếp theo” bên dưới giữ ngữ cảnh lúc lập kế hoạch;
master và báo cáo hiện hành sở hữu trạng thái mới nhất.

## 1. Tài liệu này dùng để làm gì?

Biến bản thảo “AI Chief of Staff / Business OS” thành kế hoạch có phụ thuộc,
module và điều kiện đạt, dựa trên hệ thống đã có thay vì viết lại từ đầu.
[Master](PAO-MASTER-GAP-AND-ROADMAP.vi.md) sở hữu thứ tự; tài liệu này sở hữu phân
rã kiến trúc/lộ trình, register sở hữu bằng chứng. Không mở bộ ID cạnh tranh:
S là rollout SaaS, M là năng lực kinh doanh, P là nền tảng. Các mục dưới không
phải milestone mới. Ngày17/10 chỉ đọc source/docs và sửa tài liệu; không chạy lại
regression/health, không đổi code/schema/env, không bật flag hay provider.

Nguồn: [thảo luận kiến trúc](https://chatgpt.com/share/6ad24a40-d050-83ec-a21d-4bc4176e4fcd),
master/unified11/10, AGENTS, [sổ S5](S5-COMPLETION-REGISTER.vi.md),
[sổ S6](S6-COMPLETION-REGISTER.vi.md), [ADR vòng đời](ADR-S6-ACCOUNT-AND-DATA-LIFECYCLE.vi.md),
source model router, web package và inventory modules. Bản thảo là input thiết kế,
không phải bằng chứng nghiệm thu hoặc quyền hành động bên ngoài.

## 2. Đích sản phẩm và nguyên tắc không thay đổi

PAO nhận mục tiêu của một SME/nhãn hàng, đề xuất kế hoạch, chia công việc,
chọn AI theo job, tạo bản nháp, xin duyệt, thực thi trong quyền được cấp,
theo dõi kết quả và đề xuất cải thiện có nguồn. Không hứa tự làm mọi việc.

- Một hệ thống nhiều SME; người dùng có thể thuộc nhiều SME. SME là boundary,
  brand/Brain/resource có ACL bổ sung, không tự gộp memory của cùng owner.
- Invite-only do owner mời; chưa public signup. Không tự xóa dữ liệu; export
  và deletion request có preview/xác nhận riêng. Billing là mở rộng sau pilot.
- Managed PAO app khi provider hỗ trợ, BYO nâng cao; bot/token có setup riêng.
  Một bot chỉ thuộc một SME, SME có thể có nhiều bot; identity khác destination.
- Local và cloud đều là provider tùy cấu hình; không bỏ Ollama hoặc tự gửi
  dữ liệu private ra cloud. Không cố định “content=OpenAI, ads=Claude”.
- Plan approval, content approval và action approval là ba trách nhiệm khác
  nhau; approval gắn version/scope/expiry, quyền phải được kiểm lại lúc execute.
- Mọi UI khách hàng tiếng Việt, giữ nguyên identifier/URL/enum/provider name.
- Không thay stack UI bắt buộc, không nhập backend Javis, không microservices/
  Kubernetes ở giai đoạn này, không tạo scheduler/runner hoặc authority thứ hai.
- Giữ local acceptance đã có. Proposed/implementation_pending khác với
  local_accepted, external_pending và production_pending; không dùng % giả.

## 3. Sáu lớp trách nhiệm và mapping vào source

| Lớp mục tiêu | Nơi hiện có/điểm mở rộng | Phần giữ và phần còn thiếu |
|---|---|---|
| Frontend | apps/web/app, components, lib | Next.js/React/TypeScript và route hiện có; M6 hợp nhất UX. PWA chưa nghiệm thu, Tailwind/shadcn không có trong web package hiện kiểm tra |
| API/identity/tenant | pao/app.py, core_api.py, auth.py, access.py, modules/platform và connections | Một API FastAPI; S6.2 bổ sung lifecycle, không dựng gateway service mới |
| PAO Core | modules/business_planning, tasks, goals, studio, engines, knowledge, events, results, learning, schedules; runtime.py | Phối hợp trách nhiệm, dùng Run/Task hiện có. Không có nghĩa phải tạo pao/core/ rồi chuyển toàn bộ code |
| Execution/agents | Runtime/tool gateway, engine/model adapters, worker entrypoints hiện tại | ARQ/Temporal có vai trò riêng; specialists là role/config + adapter, không tự thành dịch vụ độc lập |
| Integrations/services | integrations/meta, google_ads; modules/connections, connectors, channels, business | Meta/Google/Telegram/MCP có lát cắt local; TikTok/media/coding/CRM đầy đủ còn thiếu |
| Data/memory/operations | ORM/migrations, PostgreSQL/pgvector, validated file objects, infra/scripts | DB nguồn chính theo loại dữ liệu; storage production, key ops, monitoring và restore còn gate |

Repo giữ apps/api, apps/web, packages/contracts/agent-config/skill-config,
infra, scripts, docs, evals. `apps/worker` hiện chủ yếu README; không coi sơ đồ
worker riêng là đã extract hết runtime khỏi API/scripts. Cây đề xuất mục10 master
không phải hiện trạng. Tên thư mục không quyết định quyền hoặc trạng thái nghiệm thu.

### Quy tắc tái cấu trúc tăng dần

1. Inventory route/import/job/schema ownership và lập dependency map mỗi domain.
2. Chọn đúng domain cần cho checkpoint, extract service/schema/policy có shim.
3. Không tạo `runtime.py` cạnh package `runtime/` hoặc `db.py` cạnh `db/` gây shadow;
   không move models.py đại trà, bảo toàn metadata/Alembic registration.
4. API/CLI cũ giữ tương thích, contract diff được review; không đổi ports/URLs/IDs
   hoặc squash migration lịch sử chỉ để cấu trúc đẹp. Model pins cũ không sửa ngầm.
5. Test import/contract/isolation/runtime/replay; có migration thì checkpoint và
   restore clone trước rollout. Source rollback và schema rollback là hai kế hoạch.
6. Refactor domain cùng lát cắt nghiệp vụ, không dành nhiều lượt chỉ tạo file rỗng.

DB giữ identity/ACL/business/run/audit; Redis là transport/cache, không evidence.
Temporal giữ workflow history theo contract và DB projection. Object storage chỉ
lưu bytes/file objects gắn ACL/hash/version, không thay DB bằng thư mục Markdown.
S3-compatible là lựa chọn storage khi deploy, chưa là provider production đã có.

## 4. Điểm xuất phát — không làm lại phần đã nghiệm thu

Snapshot có ngày16/10: S5.1–S5.6 local_accepted, schema0070/live382; backend
Linux2224 đạt, frontend114Node/typecheck/build22 đạt riêng sau sửa archive JSX.
Pipeline lỗi TypeScript được giữ, chưa có một CI hosted end-to-end xanh.
P0–P6 có phạm vi local, P7.1–P7.4 local; provider thật/P7.5/production còn mở.
Không xác nhận lại các số runtime hoặc số Git thay đổi trong lượt lập kế hoạch.

Những thứ chưa phải năng lực thật: TikTok connector, tạo ảnh/video và publishing
trọn vòng, coding executor, PWA, CRM sales đầy đủ, billing SaaS. Groq chưa là
provider native trong router hiện đọc. File/thư mục hoặc nút UI không chứng minh
feature hoạt động. Temporal/Goal/Telegram có code không đồng nghĩa đang bật.

## 5. S6.2 — nền tảng SaaS phải hoàn thiện trước

Chỉ một checkpoint thực thi tại một thời điểm. A/B/C theo ADR đã chốt, không
đổi ID hay hỏi lại các lựa chọn sản phẩm. Từng mục phải có API/UI/tests/runbook.

### Chuẩn bị release và bảo vệ công sức

- Phân loại tracked/untracked và thay đổi liên quan, rà secret bằng công cụ
  không in giá trị. Baseline snapshot mã nguồn và backup DB/key có kiểm soát.
- Đề xuất commit logic/tag và kiểm checkout sạch khi có quyền; không tự add-all,
  commit/push, đổi remote, xóa source cũ hoặc đưa env/secret vào backup source.
- Kết quả: biết đúng source nào đang nghiệm thu, có phục hồi được; không gọi
  dirty workspace là mất dữ liệu, cũng không coi ZIP thay Git review.

### A. Lời mời và thành viên — checkpoint triển khai tiếp theo

- Owner tạo/thu hồi lời mời cho vai trò không phải owner; mã dùng một lần,
  lưu hash, có hạn, không tự gửi email/Telegram. Bootstrap owner là thao tác
  quản trị có kiểm soát, không biến SME owner thành host admin.
- Người mới nhận lời mời hợp lệ; tài khoản cũ xác thực chính mình, không reset
  mật khẩu bằng invite. Quản lý role, chống race/replay/enumeration.
- Gỡ quyền SME A xử lý Brain/grants/references, queued work và Telegram đúng A;
  user/membership SME B còn nguyên. Bảo toàn audit/FK và lịch sử công việc.
- Ảnh hưởng: identity/core API, auth/access/models/migration nếu cần, connections/
  channels/jobs consumers, Settings/team và contracts. Inventory file cụ thể
  khi triển khai, không khóa cứng thiết kế schema chỉ bằng bản kế hoạch.
- Đạt: corpus owner/admin/operator/viewer/outsider, invite hết hạn/thu hồi/trùng/
  nhận đồng thời; browser hai SME/mobile, test clone migration/restore nếu có.

### B. Phiên đăng nhập và thu hồi quyền

- Server-side session/revoke; đăng xuất phiên hiện tại và mọi phiên là hai
  phạm vi rõ ràng. Giữ password hashing/throttling, không lộ token hoặc đổi
  JWT secret host để khóa riêng một thành viên.
- Kiểm token cũ, relogin, nhiều tab, SSE và thời điểm queue/tool/delivery kiểm
  quyền. Không quảng cáo instant cancellation khi side effect đã gửi ra ngoài.
- Ảnh hưởng: auth/core API, session state, SSE/client lib, worker guards/tests.
- Đạt: token revoked bị từ chối, đăng nhập lại hợp lệ; gỡ A khác logout toàn
  tài khoản và không vô tình xóa phiên/quyền B.

### C. Vòng đời dữ liệu theo quyết định đã chốt

- Export theo SME/brand/Brain ACL, filter secrets/private Brain, giới hạn file,
  pagination, link tải riêng tư có hạn, audit và trạng thái job rõ.
- Preview/yêu cầu xóa gắn hash/revision/scope/expiry và xác nhận riêng; request
  không tự purge. Ngoại lệ audit/backup/account chung/job đang chạy được nêu rõ.
- Đồng bộ retention kênh: tắt cơ chế tự dọn trái lựa chọn chưa tự xóa, không
  dùng channels_enabled=false như bằng chứng đã chặn purge_expired.
- Ảnh hưởng: channels/service retention, Brain/files/business ownership,
  operations/export jobs, Settings/privacy, audit và download policy.
- Đạt: không có secret/dữ liệu B/private Brain trái quyền trong export; stale
  preview bị chặn; chạy scheduler/collect không tự xóa dữ liệu theo mặc định mới.

### CI và môi trường production riêng

**Implementation17/10:** profile private và CI chung đã local_accepted;
Linux11b0 đạt trọn18stage/2258backend/120Node/build23/audit Python0, snapshot
primary/env giữ nguyên. Windows111, private TLS/role/restart và3archive clone
đạt; dependency mới đã cài, UI/health/replay xác nhận. Namespace-ready fixture
giữ nguyên assertion outage/backoff. Read archive kiểm hash/scope, execute vẫn
kiểm binding; không sửa reader để ép hash. CIbaca FAIL/drift/probe cũ giữ lịch sử.
local_prepared=true không cho promote: còn5dev advisories và toàn external
production gates; không suy GitHub đã chạy hoặc full keys/blobs/host cold restore.

- Từ source sạch chạy một pipeline Linux backend + Node/typecheck/build +
  contract + populated restore; giữ log thất bại cũ, không cộng stage thành pass.
  Hosted CI chỉ thực hiện khi được phép push/dispatch; chưa có quyền thì pending.
- App DB role tối thiểu tách migration/admin; bỏ sử dụng superuser/bypass ở
  app production. Đánh giá RLS theo threat model, không bật mù mọi bảng.
- HTTPS/reverse proxy, secure cookies/session nếu áp dụng, CORS/CSRF phù hợp
  auth thực tế, private storage, key rotation/revoke, redacted logs, health/readiness,
  backup mã/DB/keys và restore trong môi trường riêng, alert và operator runbook.
- Có supervisor/containers, worker drain/restart, cancel/recovery/unknown action,
  reboot/failover drill trên host riêng được cấp; không reboot Windows hiện dùng.
- Đo tải và fair resource theo SME; cấu hình VPS4vCPU/8GB trong bản thảo là giả
  định khởi đầu, không SLA hay công suất bảo đảm. Không cần GPU nếu dùng API cloud.
- Đạt: clean pipeline + security/restore/recovery evidence đúng source/config;
  thiếu host/cert/keys thì production_pending, không ngăn local độc lập.

## 6. M6 — Command Center và trải nghiệm sử dụng

**Cập nhật implementation17/10: lát cắt Giai đoạn2 local_accepted.**
Đã gom view con dưới12khu vực, thêm hành trình và hướng dẫn kinh doanh,
nháp có phạm vi/revalidate/clear logout, deep-link kế hoạch ghim SME và Settings,
chọn kết nối/quyền cloud từ metadata, dependency checkbox, lịch sử đọc riêng/
nhân bản cần duyệt lại, báo cáo dữ liệu còn thiếu.120Node/typecheck/build23,
browser native12khu vực/SME/role/network/keyboard/mobile và UI cài thật đạt.
Backend0071/399/binding8e9a71b9 giữ nguyên;2258baseline được kế thừa.
[Báo cáo](M6-COMMAND-CENTER-UX-LOCAL-ACCEPTANCE-2026-10-17.vi.md).

Lát cắt trước pilot phục vụ S6, không tuyên bố toàn M6 hoàn thành. Không chờ
media/coding mới sửa UX; cũng không thay toàn bộ frontend trong một lần.

### Mười hai khu vực khách hàng

| Khu vực | Nội dung cần thấy | Giới hạn trung thực |
|---|---|---|
| Tổng quan | KPI có nguồn/thời điểm, việc đang chạy, cần duyệt, kết nối | Thiếu/stale không biến thành số0 |
| PAO AI | Chat/giao mục tiêu, SME/brand/Brain/model context rõ | Chat không tự cấp quyền tool |
| Công việc và dự án | Plan/dependencies/job/progress/history/cancel/retry | Không mở runner khác |
| Meta Ads | Account/campaign/report và action theo quyền | Kết nối thật vẫn gate riêng |
| TikTok Ads | Trạng thái chưa hỗ trợ/setup khi adapter có | Không dùng tasks/demo thay metrics thật |
| Google Ads | Account/report/read/action theo adapter | Không kế thừa quyền từ Meta |
| CRM | Lead/order/attribution, sau đó pipeline sales | Phân biệt import với live sync |
| Nội dung và sáng tạo | Brief/draft/version/asset/review | Ảnh/video/publishing là adapter sau |
| Phân tích | Hiệu quả, coverage, chi phí AI và đối chiếu | Estimate khác invoice/Ads spend |
| Tự động hóa | Workflow/schedule/Goal/inbox và lịch sử | Đang tắt khác lỗi hoặc đã chạy |
| Kho tri thức | Brain/source/wiki/RAG/citation | Private Brain không mặc định owner đọc |
| Cài đặt và kết nối | Team/session/privacy/model/limits/platform setup | Không lộ khóa hoặc host admin UI cho SME |

Agents/Skills/Approvals/Goal/Voice giữ là view con hoặc lối tắt theo quyền, không
xóa route/feature đang dùng chỉ để sidebar đủ12mục. URL/deep-link/session và
draft phải giữ khi đổi tab/SME; UI không được hiển thị stale tenant response.

Settings/Kết nối chia tab con theo nền tảng Meta/Google/TikTok/Telegram/MCP…;
Botcake/Zalo OA thêm bằng catalog, không dồn mọi form vào một trang dài. Mỗi tab
có mục đích, ai cấu hình, prerequisites, field help, lấy giá trị ở đâu, save/test/
activate khác nhau, account/destination, lỗi thường gặp, rotate/disconnect.

Hành trình nghiệm thu: chọn SME/brand → hồ sơ → kế hoạch có version → cấu hình
AI theo job → chạy → review → action preview → báo cáo. Bổ sung retry có kiểm
soát/lịch sử xuyên version, loading/empty/error/offline và accessibility/mobile.
Đạt khi người mới làm trọn flow synthetic hai SME, không lẫn context, không cần
nhập UUID thủ công ở các thao tác phổ biến; không chỉ chụp UI đẹp.

## 7. S6.1 / M3 — một lát cắt kinh doanh thật trước

Sau lifecycle và UX liên quan; người dùng đang hoãn dữ liệu thật, giữ nguyên.
Read-only có thể làm trên môi trường được cấp trước production; remote pilot
phải đạt production tương ứng. Không tự mở action/live vì đã chuẩn bị xong local.

1. Chọn duy nhất một SME/brand/provider/account và kỳ khi được cấp; đọc tài liệu
   provider chính thức lúc triển khai, ghi ngày/version/auth/scopes/review/limits.
2. Kết nối/rotation/revoke và sync read-only; đối chiếu export chính thức cùng
   timezone/currency/attribution/freshness/coverage, có nguồn và sai lệch giải thích.
3. Chief Brief dùng số liệu đã đối chiếu, tạo đề xuất/task/draft có bằng chứng;
   nếu thiếu dữ liệu phải nói thiếu, không bịa nguyên nhân/doanh thu.
4. Một action thật chỉ khi adapter hỗ trợ, phê duyệt đúng input/account/version,
   giới hạn và emergency stop. Timeout/unknown phải đối soát, không resend mù.

Đạt: log đã lọc bí mật, báo cáo đối chiếu và owner nghiệm thu; fixture hoặc
configured không thay real OAuth/account. S6.1 read và action đóng gate riêng.

## 8. S6.3 / M5B — dùng thật, đo thật, học có kiểm soát

- Owner thực hiện một chu kỳ mục tiêu→kế hoạch→nội dung→duyệt→action/report;
  ghi rõ bước thực, simulation hoặc manual. Thiếu real action không đóng toàn S6.
- Theo dõi chất lượng, lỗi dữ kiện, latency, token/chi phí đo hoặc ước tính,
  nguồn pricing, retry/cancel, chi phí theo SME/brand/job và trải nghiệm người mới.
- Outcome gắn action/window/source/confounders; thiếu dữ liệu trả insufficient_data.
  Lesson là proposal có review/diff/revert, không tự sửa policy/prompt/model production.
- Chốt ngưỡng chất lượng/chi phí/latency theo use case trước pilot; không tự bịa
  điểm/SLA. Đạt S6 chỉ khi đủ S6.1, S6.2, S6.3; nhu cầu feature khác vào backlog.

## 9. Sau pilot — các gói mở rộng có điều kiện, không làm đồng loạt

Mỗi gói chọn một use case/adapter để triển khai trọn API→UI→tests→runbook. Không
cài đặt hoặc kích hoạt ngoài hệ thống chỉ vì roadmap được cập nhật.

| Gói / ID kế thừa | Việc triển khai theo thứ tự | Gate hoàn thành |
|---|---|---|
| Kênh/voice / P7.5, M8 | Bot thật: pairing→quyền→lệnh→report; sau đó mic tiếng Việt/STT/TTS/interruption; Zalo OA/Botcake từng adapter riêng | Identity không cấp quyền qua username/group admin; real destination opt-in; webhook/retry/takeover/noise/latency có đo |
| Ads bổ sung / M8 | Sau provider đầu đạt: provider kế tiếp, TikTok read-only trước write | Docs/scopes/app review/account/metrics reconciliation riêng; Settings Việt hóa và disconnect/revoke |
| Media/publishing / P8, M8 | Asset metadata + storage adapter→ảnh→video khi cần→review→lịch publish→kênh thật | Provenance/model/quyền nội dung/cost, sandbox xử lý media, không publish trước approval; lỗi/duplicate/unknown có đối soát |
| CRM nghiệp vụ / M8 | Stage/contact ownership→activity/import/dedup→sales pipeline→vendor sync; profit/LTV sau metric contract | Hai SME/PII/consent/permission; order/refund/cost chuẩn hóa, không suy ROAS thành profit |
| Coding / P8, M7B | Một adapter được chọn→isolated checkout/container→diff/tests/review→PR; merge/deploy tách riêng | Kiểm tài liệu/quyền dùng chính thức lúc chọn engine; repo/path/network/secret/budget/cancel sandbox, không shell host unrestricted |
| SaaS thương mại / M8 | Tenant provisioning có kiểm soát→gói/entitlement→usage/billing→support/offboarding | Không public signup mặc định; payment chỉ khi chọn vendor/quy trình riêng, invoice khác estimate; backup/DR/load/security review |
| PWA/extensions / M6, P8 | PWA nếu có nhu cầu cài trên điện thoại; manifest/update/logout/cache isolation; extensions sau sandbox | Không cache dữ liệu tenant/private offline mặc định, revoke/update an toàn; install/review không mở quyền tùy ý |

Research/Content/Planner/Ads là cấu hình chuyên môn và tool allowlist trong
Studio/runtime dùng chung. Designer/Editor cần media adapter; Finance cần metric
contract/data thật; Developer cần sandbox. Không tạo mười “agent service” rỗng
hoặc xem Orb nodes là executor đã hoạt động. Thêm provider như Groq chỉ khi nhu
cầu/capability/chi phí rõ; không là dependency bắt buộc của kiến trúc.

## 10. Cách nghiệm thu và tránh kẹt vòng lặp

- Mỗi checkpoint có scope/non-goals, dependency, file/module, acceptance và đúng
  một việc tiếp theo; status kèm source/config/evidence, không đếm test thay tiến độ.
- Test theo rủi ro: unit + integration PG/Redis/Temporal khi liên quan, tenant/
  RBAC/revoke, idempotency/concurrency/cancel/unknown/restart, contract và browser
  desktop/mobile. Schema thay đổi phải backup/roundtrip/restore clone.
- Checkpoint nhỏ chạy tests ảnh hưởng; cổng tích hợp chạy full regression/build/
  contracts/browser/restore phù hợp. Không rerun bộ không đổi để thay việc thiếu;
  code/dependency/schema liên quan đổi thì bằng chứng cũ không thay test mới.
- Giữ log FAIL và stage riêng, không gọi skip là pass. Feature off kiểm cả API/
  worker; usage estimate không quota thật, local accepted không production accepted.
- Môi trường/dữ liệu/quyền ngoài thiếu: ghi gate cụ thể, làm việc local độc lập
  còn giá trị rồi dừng; không hỏi lại lựa chọn đã chốt hay tự mở quyền.
- Không đưa .env/secret/token/private prompts/audio vào source/report/CI artifacts.

## 11. Bắt đầu từ đâu sau khi kế hoạch được cập nhật?

**Giai đoạn1 — S6.2 tài khoản/dữ liệu đã local_accepted17/10**. Tiếp theo
**Giai đoạn2 — M6 UX phục vụ S6**, rồi CI/production và S6.1/S6.3 theo dependency.
Không có lịch ngày cố định trước khi biết môi trường,
provider/data/owner pilot; sau một checkpoint đủ scope mới ước lượng phần kế.

Kế hoạch này không triển khai tính năng, không đóng gate, không khởi động hệ
thống hoặc cho phép quảng cáo/chi tiền/nhắn tin/merge/public deploy. Giữ nguồn
bảo vệ F:\Apex\apex và F:\Javis OS nguyên vẹn.
## Bổ sung local18/10: tổ chức và thư viện tri thức

Chủ SME hiện có được tạo SME độc lập do mình sở hữu; tài khoản invite-only,
không sao chép dữ liệu/nhân viên/kết nối/grant. Quản lý tên tại Settings,
hồ sơ tại Knowledge dùng BusinessProfile hiện có, Skills dùng StudioDefinition/
StudioVersion và metadata StudioEvent. Phân loại không thay payload/hash;
gán agent mới tạo draft và cần duyệt/công bố, không repin việc cũ.
Không thêm bảng/runner;0071/153tables, API dự kiến406operations. Đây là lát cắt
local theo master, không phải toàn M6/S6 hoặc production. Trạng thái nghiệm thu
ở [báo cáo18/10](ENTERPRISE-KNOWLEDGE-LOCAL-2026-10-18.vi.md).

