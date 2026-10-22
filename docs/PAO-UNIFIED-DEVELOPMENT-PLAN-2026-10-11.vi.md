# PAO — Audit đồng bộ và kế hoạch phát triển thống nhất

> Điều hướng 21/10/2026: đây là kế hoạch/audit lịch sử, không phải roadmap điều hành thứ hai.
> Theo [master roadmap](PAO-MASTER-GAP-AND-ROADMAP.vi.md) cho thứ tự và phạm vi hiện tại;
> giữ nguyên các kết quả cũ theo đúng source/schema/ngày nghiệm thu.

## Bổ sung tổ chức và tri thức18/10 — theo master, không roadmap mới

Đã hoàn thiện và nghiệm thu nguồn quản lý doanh nghiệp/nhãn hàng và bốn tab Kho tri thức
(hồ sơ doanh nghiệp, hồ sơ nhãn hàng, Skills cho agent, tri thức/bộ nhớ).
Chủ doanh nghiệp hiện có được tạo SME mình sở hữu; invite-only và không sao
chép dữ liệu/kết nối/quyền. Dùng hồ sơ/Studio đã có, không thêm runner hoặc
quyền tự động chạy Ads. [Báo cáo](ENTERPRISE-KNOWLEDGE-LOCAL-2026-10-18.vi.md)
ghi2272full Linux/202Windows/132Node/build23 và browser. Bản cài chỉ chốt khi
`.runtime/organization-completion.json` pass=true; không đổi receipt cũ.
Giữ local trước, S6.1 dữ liệu thật → pilot local → VPS/public sau.

## Cập nhật ưu tiên 18/10/2026

Lát cắt vòng vận hành local S5/M6 đã local_accepted18/10:132Node,125focused
backend/0skip,build23, native business/browser và installed read-only. Theo dõi
job chỉ GET, hủy chờ ACK, phục hồi mất phản hồi, làm lại không sao chép quyền.
[Báo cáo](LOCAL-OPERATING-CYCLE-2026-10-18.vi.md). Bước tiếp theo S6.1 dữ liệu
thật local theo phạm vi được chọn; toàn M6/S6/production chưa đóng.

Người dùng đã tạm dừng VPS/public: hoàn thiện khung local, nghiệm thu dữ liệu
thật trên local và pilot local trước. Thứ tự hiện hành do mục18/10 ở
[master](PAO-MASTER-GAP-AND-ROADMAP.vi.md) sở hữu; các chỉ dẫn production-first
bên dưới là lịch sử. Không mở lại S0–S5 hoặc coi production pending là chặn
cải thiện local. [Báo cáo giao diện sáng/tối](LOCAL-UX-LIGHT-DARK-2026-10-18.vi.md)
ghi phạm vi và bằng chứng riêng; hosted CI commit3151851 không kiểm các file UX
mới. Toàn M6/S6/production chưa đóng; không tự bật kết nối thật hoặc deploy.

## Điều hướng17/10/2026 — kế hoạch kiến trúc đích

[Master](PAO-MASTER-GAP-AND-ROADMAP.vi.md) sở hữu thứ tự mới nhất; chi tiết phát
triển Frontend → PAO Core → Execution/Integrations → Data tại
[kế hoạch17/10](PAO-TARGET-ARCHITECTURE-AND-DELIVERY-2026-10-17.vi.md).
Tài liệu11/10 này giữ audit/lịch sử, không còn sở hữu kế hoạch chi tiết tương lai
nếu trái mục điều hướng17/10. Không sửa ngược bằng chứng, không làm lại S0–S5/P6.

**Hiện hành: Giai đoạn3 local_prepared=true; production/S6 chưa đóng.**
Hosted CI đã đạt: GitHub run39030584315, commit3151851,18stage/2258backend/120Node/
build23 và runtime audit Python57/0/npm0; artifact đối chiếu đúng commit.
Nhánh phase3/hosted-ci, main giữ nguyên; không merge/deploy/bật provider.
Xem [nghiệm thu hosted CI](PHASE3-HOSTED-CI-ACCEPTANCE-2026-10-17.vi.md).
Trạng thái tổng hợp mới `.runtime/phase3-current-status.json`; baseline local:
CI Linux11b0 đạt cùng18stage/2258backend/120Node/TypeScript/build23, audit
Python57/0advisory. Windows focused111 và installed UI/live/worker/replay3 đạt;
runtime pin PyJWT2.15.1/cryptography50.0.2 đã cài, `.venv` cũ giữ nguyên.
Private TLS/minimum-role/non-root/restart và archive clone153tables/3hash đạt;
đọc lịch sử không thay quyền thực thi, không sửa binding. Xem
[xử lý chốt](PHASE3-GATE-REMEDIATION-2026-10-17.vi.md).
Giữ CIbaca FAIL/drift làm lịch sử; lượt xanh mới primary/env không đổi.
Npm runtime0 nhưng5high dev/braces chưa có patch; host/public HTTPS/
keys/storage/alerts/reboot/owner review còn pending, release_promotable=false.
Không tự push/deploy/bật provider hoặc chạy pilot; dữ liệu thật vẫn hoãn.

Baseline: Giai đoạn2 — lát cắt M6 UX local_accepted17/10;120Node/
typecheck/build23, native business browser +12khu vực/SME/nháp/deep-link/mobile,
UI cài thật read-only và live health/worker/replay đạt. Không đổi backend/schema/
dữ liệu nghiệp vụ/`.env`; không coi fixture là nghiệp vụ thật.
[Báo cáo M6](M6-COMMAND-CENTER-UX-LOCAL-ACCEPTANCE-2026-10-17.vi.md).
Giai đoạn3 — CI/private production đang thực hiện theo mục hiện hành ở trên;
không tự push/deploy hoặc hỏi lại dữ liệu thật đã hoãn. Toàn M6/S6 chưa đóng.

Baseline S6 vẫn in_progress; **Giai đoạn1 — S6.2 lifecycle local_accepted trọn bốn phần**:
bảo vệ phiên bản, lời mời/thành viên, phiên và dữ liệu. Full Windows2258/2258/
0skip,114Node/typecheck/build23, browser/restore và rollout primary0071/live399/
153physical đạt; health/worker/replay3/3, dữ liệu cũ/`.env` giữ nguyên.
Xem [báo cáo hiện hành](S62-ACCOUNT-DATA-LOCAL-ACCEPTANCE-2026-10-17.vi.md).
**M6 UX đã có lát cắt local_accepted; CI/private production đang triển khai**, rồi
S6.1 live được cấp riêng và S6.3 pilot. P7.5/M8/P8/M7B mở rộng theo nhu cầu sau
pilot, không là quyền bật Ads/Telegram/public deployment từ lượt lập kế hoạch.
Giữ hybrid Ollama/cloud, modular monolith FastAPI/Next.js, authority DB/ARQ/
Temporal và model routing theo job. PWA/Tailwind/shadcn/Groq/coding/media không
được coi là đã triển khai chỉ vì xuất hiện trong sơ đồ mục tiêu.

Lượt lập kế hoạch đầu17/10 chỉ sửa docs; lượt triển khai sau được ghi riêng
trong báo cáo hiện hành. Bằng chứng cũ phía dưới là lịch sử, không đổi ngược.
Các số ngày16/10 bên dưới là snapshot có ngày, không phải kiểm tra live hôm nay.

**Hiện hành16/10 — S6 in_progress, chỉ chuẩn bị local theo lựa chọn người dùng.**
Preflight live/worker/replay đạt. Linux full backend2224/2224; frontend kiểm
riêng114Node/TypeScript/build22 sau sửa archive JSX đạt, giữ pipeline lỗi cũ.
18offline+4archive tests/44Windows focused/9Temporal-ARQ/browser/restore đạt.
Chưa chạy GitHub hosted CI. Không đổi
backend/UI/schema/env hoặc bật provider; S5 baseline0070/live382 nguyên vẹn.
Xem [sổ S6](S6-COMPLETION-REGISTER.vi.md). Tiếp theo lifecycle S6.2 đã chốt;
không làm lại baseline Linux hoặc tự push/deploy/real action.

**Cập nhật mới nhất16/10 — toàn S5.1–S5.6 local_accepted,0070/live382:** đã có native
job adapter/worker, content review, ngân sách/hành động mô phỏng và báo cáo
giờ/ngày. Full backend2224/2224 đạt, backend không đổi;114Node/build22/browser/
populated restore/migration/Ollama local thật đạt. Primary149physical/148business/
3archives; API/ready/Web200, worker khỏe, replay3/3 và dữ liệu cũ không đổi.
Chỉ bật S5/pin0070, secret và cấu hình khác giữ nguyên. Hai model là fixture,
chất lượng thật dùng một model đã cài. Tiếp theo S6, không tự mở hành động thật.
Xem sổ S5; các ghi chép0066–0068 tiếp theo là lịch sử, không triển khai lại.

Xem [sổ triển khai S5](S5-COMPLETION-REGISTER.vi.md) và
[báo cáo tích hợp S5](S5-INTEGRATION-2026-10-16.vi.md); không làm lại S4/P6.

**Mốc lịch sử16/10: toàn S4.1–S4.3 local_accepted, chuyển sang S5.**
2099ca backend có kết quả cuối đạt (full2089/10lỗi fixture,52+82kiểm lại đạt,
backend không đổi, không full rerun);114Node/TypeScript/build21/browser
Meta+Google/Telegram regression/lock-fresh-process đạt. Primary0065/live353/
136physical/3archives;API/ready/Web200,workerhealthy,current binding/replay3/3/
exact restore135business đạt, `.env` và dữ liệu cũ nguyên vẹn. Xem
[báo cáo S4](S4-INTEGRATION-2026-10-16.vi.md) và [sổ S4](S4-COMPLETION-REGISTER.vi.md).
S5 chưa triển khai trong lượt này; real OAuth và production vẫn external_pending.

**Kết quả lịch sử15/10: toàn S3.1–S3.3 đạt local.**
Runtime/webhook/report và Settings/pairing/team/hướng dẫn tiếng Việt đã nạp vào
primary0064/live349;93focused/109Node/build21/browser đạt. Backend2078ca có kết
quả cuối đạt: full2077/1lỗi allowlist script phục hồi, sửa script rồi27retry đạt,
backend không đổi; không gọi full rerun xanh. API/ready/Web200,replay3/3, dữ liệu
cũ/.env nguyên vẹn; bot thật/HTTPS/reboot vẫn external_pending.
Xem [báo cáo S3 mới](S3-INTEGRATION-2026-10-15.vi.md) và [master](PAO-MASTER-GAP-AND-ROADMAP.vi.md).
Các đoạn tiến độ/checkpoint cũ bên dưới là snapshot lịch sử, không lệnh làm lại.

Ngày 11/10/2026, Asia/Saigon. Target: `F:\PAO-ACOS`.
Phạm vi audit ban đầu: đọc source, Git, cấu trúc, migrations, contracts, tests/harness,
tài liệu và kiểm tra HTTP/Docker không mutation; chỉ chỉnh tài liệu kế hoạch.
Không đọc/in lại secret, không sửa code/.env, migration, bật flag hoặc gọi dịch vụ ngoài.

**Cập nhật sau phê duyệt 11/10:** người dùng đã chốt shared SaaS, nhiều brand/team/
connections trong một SME và managed OAuth mặc định + optional BYO. S0.2 mapping/
quyền/threat model đã ghi trong [ADR-S02](ADR-S02-SAAS-TENANT-AND-CONNECTIONS.vi.md).
S0.3 đã đạt LOCAL theo [acceptance](S03-LOCAL-BASELINE-ACCEPTANCE-2026-10-11.vi.md):
Docker/PG/Redis healthy,API/ready/Web200,workerhealthy,0048,verified restore và
source checkpoint. S1.1 nay đạt local theo [acceptance](S11-LOCAL-ACCEPTANCE-2026-10-11.vi.md)
và [ADR-S11](ADR-S11-ACTIVE-ENTERPRISE.vi.md). S1.2 cũng đạt local theo
[acceptance](S12-LOCAL-ACCEPTANCE-2026-10-11.vi.md) và [ADR-S12](ADR-S12-CLIENT-SCOPE.vi.md).
S1.3 cũng đạt local theo [acceptance](S13-LOCAL-ACCEPTANCE-2026-10-11.vi.md) và
[ADR-S13](ADR-S13-SERVER-ISOLATION.vi.md). S2.1A inventory/mapping preview đạt local
theo [acceptance](S21A-LOCAL-ACCEPTANCE-2026-10-11.vi.md) và
[ADR-S21A](ADR-S21A-CONNECTION-INVENTORY.vi.md);
S2.1B1 persisted staged reference/grant/audit và eligibility đã rollout0049,
đạt local theo [evidence](S21B1-LOCAL-ACCEPTANCE-2026-10-11.vi.md), full1240/0fail/0skip.
B2a model execution-denial đạt local theo [evidence](S21B2A-LOCAL-ACCEPTANCE-2026-10-11.vi.md)
và [ADR](ADR-S21B2A-MODEL-EXECUTION-FENCE.vi.md); grant vẫn staged/non-executable.
B2b explicit model consent/grant pins/Settings đạt local0050/live321,
full1298/0failed/0skip và exact restore theo [evidence](S21B2B-LOCAL-ACCEPTANCE-2026-10-11.vi.md).
B2c MCP đạt local0051/live323,234affected/25Node/build21/browser2+3/exact restore
theo [evidence](S21B2C-LOCAL-ACCEPTANCE-2026-10-11.vi.md).
B2d Meta/Google read đạt local12/10,0052/live327/186affected/browser4/restore
theo [evidence](S21B2D-LOCAL-ACCEPTANCE-2026-10-12.vi.md).
S2.2A lifecycle/probe fences đạt local0053/live328/247affected/browser4/restore
theo [evidence](S22A-LOCAL-ACCEPTANCE-2026-10-12.vi.md).
S2.2B1 model resource backend đạt local13/10,171affected/browser4/build21/0054/
live330/exact restore121business theo [evidence](S22B1-LOCAL-ACCEPTANCE-2026-10-13.vi.md).
S2.2B2a native read jobs đạt local13/10 theo [evidence](S22B2A-LOCAL-ACCEPTANCE-2026-10-13.vi.md):
238affected/33focused/browser5/0055/live332, legacy rows exact.
S2.2B2b metadata model/MCP backend đạt local0056/live334 theo
[evidence](S22B2B-METADATA-QUOTA-2026-10-13.vi.md):298affected/browser3/build21,
durable quota/leases/replay/role/source/Brain guards. Credential payload/URL
logging đạt local356affected/browser3,0056/live334 theo
[evidence](S22B2B-CREDENTIAL-PAYLOAD-2026-10-13.vi.md). Local discovery/selection
quota đã đạt425affected/browser4/0056/live334 theo
[evidence](S22B2B-LOCAL-DISCOVERY-2026-10-13.vi.md). Legacy unaccounted inference
đạt local theo [evidence](S22B2B-LEGACY-ACCOUNTING-2026-10-13.vi.md):472pass/1fixture
lỗi rồi focused38/38, Knowledge3/3, browser4/4,0056/live334/bindingd41d7a1d và
exact restore124business. Không phải full backend xanh mới. Shared embedding
admission/Memory coverage đã đạt local theo [evidence](S22B2B-MEMORY-EMBEDDINGS-2026-10-13.vi.md):
189backend/25Node/contracts/typecheck/build21/browser2+1,0057/live334/bindingb79a09f2,
old-column hashes exact. Knowledge index/query nay đạt local0058/live334/bindingc136c3aa
theo [evidence](S22B2B-KNOWLEDGE-EMBEDDINGS-2026-10-13.vi.md):565integrated B2b/
25Node/contracts/typecheck/build21/browser2+1/exact restore124business.
B3 quota Settings nay đạt local14/10,128affected backend+35Node/typecheck/
contracts/build21/browserHTTP1/0058/live334/binding không đổi/exact restore theo
[evidence](S22B3-QUOTA-SETTINGS-2026-10-14.vi.md). Native scoped S2.2B đóng local;
S2.3A observations đã đạt local14/10 theo [evidence](S23A-SETTINGS-OBSERVATIONS-2026-10-14.vi.md):
76affected gồm browser2/49Node/typecheck/build21/9installed snapshots/0058/live334/
binding không đổi/exact restore. S2.3B cloud lifecycle/help nay đạt local14/10 theo
[evidence](S23B-CLOUD-SETTINGS-2026-10-14.vi.md):147affected trước console audit,
57Node/typecheck/build21/finalbrowser3/0058/live334/binding không đổi/restore.
S2.3C MCP lifecycle/help nay đạt local14/10 theo [evidence](S23C-MCP-SETTINGS-2026-10-14.vi.md):
157affected backend/64Node/typecheck/build21/finalbrowser5/0058/live334/exact restore.
S2.3D Ads lifecycle/help đạt local14/10 theo [evidence](S23D-ADS-SETTINGS-2026-10-14.vi.md):
100native backend+5browser qua affected/focused recovery,71Node/typecheck/build21/
0058/live334/exact restore. Meta docs429/live gates giữ riêng.
S2.3E host lifecycle/scope đạt local14/10 theo [evidence](S23E-HOST-CONFIG-SETTINGS-2026-10-14.vi.md):
26affected gồm4browser/77Node/finalTypeScript/build21/0058/live334/exact restore.
Không .env thật/restart hoặc tenant App S4.
S2.3F team/account/mobile đạt local14/10 theo [evidence](S23F-TEAM-ACCOUNT-MOBILE-2026-10-14.vi.md):
63native backend/8browser/80Node/typecheck/build21/0058/live334/exact restore;
không invite/grant/revoke tự động hoặc tenant App S4. **S2/S2.3 tích hợp cuối nay
đạt local14/10:**1684backend/0fail/0skip,21browser/80Node/typecheck/build21,
0058/live334/binding3d811e0e và exact restore theo
[evidence cuối](S2-FINAL-INTEGRATION-2026-10-14.vi.md). Legacy Telegram dùng
shared admission/pins; native SME/member session mismatch bị chặn. MCP có lỗi
route harness thoáng qua chưa rõ nguyên nhân, giữ risk không gọi đã sửa.
S3.1A namespace foundation nay đạt local14/10:1709backend/4browser/80Node,
0059/live334/bindingb9365b68/exact restore theo
[evidence](S31A-LOCAL-ACCEPTANCE-2026-10-14.vi.md). Không mapping/token/transport mới.
15/10 S3.1B và tổng S3.1 đã đạt local theo
[evidence](S31B-LOCAL-ACCEPTANCE-2026-10-15.vi.md):1737backend/0fail/0skip,
5browser/96Node/TypeScript/build21,0060/live338/current binding/exact restore.
S3.2A kernel source_verified15/10 theo [evidence](S32A-KERNEL-2026-10-15.vi.md):
143focused/52kernel, chưa schema/API/worker wiring hoặc rollout. Tiếp theo duy nhất
**S3.2C — bridge/webhook/report integration**; A/B nay source_verified theo
[368affected/25Node/candidate0063](S32B-SCOPED-EXECUTION-2026-10-15.vi.md) và [A/B/C](ADR-S32-TELEGRAM-SCOPED-RUNTIME.vi.md),
C mới full integration/release; không triển khai lại S3.1 hoặc coi kernel là bot thật.
Trong C đã nối [polling/admission adapter](S32C-POLLING-ADAPTER-2026-10-15.vi.md)
ở candidate, sau đó nối [sender giữ quyền sát HTTP](S32C-SENDER-ADAPTER-2026-10-15.vi.md)
source_verified509affected/61sender+25Node. [Worker riêng](S32C-WORKER-2026-10-15.vi.md)
source_verified ở candidate,26worker/535affected+25Node đạt. Tiếp theo webhook/report/oversize/
idle-week/concurrency và release; không chạy daemon thật ở bước này.
Không coi đã có bot thật hoặc chuyển S3.3 sớm.
Quota không là billing hay cấp quyền.
Global host fairness/provider thật/production còn mở, không suy ra từ local S2.
Xem [S2 register](S2-COMPLETION-REGISTER.vi.md).
Không hỏi lại quyết định đã chốt.
Phần audit runtime/Git bên dưới là snapshot trước recovery, không phải live status mới.

## 1. Một nguồn quyết định, không nhiều roadmap cạnh tranh

- [Master roadmap](PAO-MASTER-GAP-AND-ROADMAP.vi.md) sở hữu thứ tự và checkpoint hiện hành.
- Tài liệu này sở hữu audit và chi tiết thực hiện của phiên bản kế hoạch 11/10.
  Khi master thay đổi, cập nhật hoặc ghi rõ tài liệu này bị thay thế; không tự đặt thứ tự khác.
- ADR ghi quyết định thiết kế; acceptance/register ghi bằng chứng theo ngày, không
  tự quyết định bước kế tiếp. README chỉ dẫn tới master và hướng dẫn vận hành.
- Giữ ID M0–M8, P0–P8 và S0–S6 đã có; không đổi tên mỗi lượt. M là năng lực sản phẩm,
  P là nền tảng/kiểm thử, S là checkpoint SaaS. Một thay đổi có thể phục vụ nhiều ID,
  nhưng chỉ một checkpoint đang thực hiện và một owner của trạng thái thực thi.
- Trạng thái thống nhất: proposed / ready / in_progress / implementation_pending / local_accepted /
  external_pending / production_pending / blocked / superseded. Blocked ghi điều kiện
  cụ thể; một gate external pending không làm mất local acceptance đã đạt.
- Mỗi checkpoint ghi scope, phụ thuộc, file/module ảnh hưởng, tiêu chí đạt, bằng
  chứng, gate còn mở và đúng một việc tiếp theo. Không dùng phần trăm tổng giả định.
- Tài liệu lịch sử chỉ thay đổi bằng chú thích/link supersession, không sửa ngược
  kết quả test ngày cũ. Khi nhận định mâu thuẫn, kiểm source/bằng chứng mới rồi đính chính.

## 2. Kết quả audit hiện tại và giới hạn xác minh

### 2.1. Git và runtime

- Git HEAD `e1eb473`, commit 05/10/2026: Start M3 with scoped read-only reconciliation
  preview and readiness gates. Audit trước chỉnh docs: 44 tracked files thay đổi,
  426 untracked files (`--untracked-files=all`); không có remote name trong `git remote`.
  Có `.git`, nhưng nhiều phần P0–P7 chưa được commit; HEAD không đại diện source hiện tại.
- Có source migrations đến `0048_voice_turns.py`. Không đọc được DB live hôm nay,
  nên không xác nhận primary đang0048 bằng việc thấy file migration.
- HTTP `127.0.0.1:8100/health`, `/ready` và Web `127.0.0.1:3200/` bị connection refused,
  kiểm lại ngoài sandbox vẫn như vậy. Docker client29.4.3, daemon pipe
  `dockerDesktopLinuxEngine` không tồn tại. Chưa xác định nguyên nhân sâu hay sửa Docker.
- Không tự khởi động dịch vụ để làm audit tài liệu. Khi bắt đầu implementation,
  phục hồi Docker theo AGENTS/runbook nếu cần; không reset/delete volumes/reboot.
- Không chạy lại full pytest/build/browser trong lượt này. Số test bên dưới là
  bằng chứng nghiệm thu ngày10/10, không phải health/test hiện tại.

### 2.2. Ma trận nguồn và bằng chứng

| Năng lực | Nguồn đã kiểm tra | Trạng thái và gate cần giữ |
|---|---|---|
| FastAPI/Next.js/contracts | apps/api/pao, apps/web/app, packages/contracts, package.json | Giữ stack và shell; API/Web hiện không truy cập được, chưa xác minh live contract hôm nay |
| Brain/knowledge | modules/brains, modules/knowledge; P1/P2 acceptance | Local text/Markdown đã ghi nhận; PDF/OCR/semantic benchmark thật là backlog, không làm lại toàn P1/P2 |
| Engine/chat/usage | modules/engines, modules/chat; P3 acceptance mới hơn P31 | P3.1–P3.7 local đã ghi nhận; P31 ghi P3.2 chưa làm là snapshot cũ, không phải việc hiện tại |
| Agent/Skill/Workflow Studio | modules/studio; P4 acceptance | Definition/version/review có nền; không là quyền arbitrary code hoặc production canary |
| MCP | modules/connectors; P5 acceptance | Workspace + encrypted credentials, owner-scoped; server thật chưa chọn/không nghiệm thu |
| Events/approval | modules/events, ads_actions.py, ads_policy.py; M4 acceptance | Local đạt; mỗi domain vẫn enforcement riêng; chưa có kế hoạch tháng và budget toàn chiến dịch hoàn chỉnh |
| Durable Goal/workflow | modules/goals, modules/studio, modules/schedules; P6 register | P6.1–P6.7 local đạt; Goal runner hiện profile dry-run, không phải chứng minh agent làm việc thật |
| Outcome/learning | modules/learning, modules/business/outcomes; P6 register | Provenance/review/observation đã có; dữ liệu synthetic không chứng minh hiệu quả kinh doanh |
| Channels/voice | modules/channels; P7 register | P7.1–P7.4 local đạt; mic tiếng Việt/tiếng ồn/latency/Telegram thật còn mở |
| Tenant/team/brand | models.py Workspace/Member/Brand/Brain; access.py; usePaoRuntime.ts | Snapshot audit: UI từng lấy workspace đầu tiên. S1.1–S1.3 nay đạt local trong corpus đã định; full SaaS/provider isolation và grants còn S2–S4 |
| Meta/Google | integrations/meta, integrations/google_ads, config.py | Token theo workspace/user; app config còn global, Meta Settings local-only; gate OAuth/data thật chưa đóng |
| Telegram nhiều SME | telegram.py, TelegramPeer/Update/Delivery, scripts/telegram_bridge.py | Một bot/config/transport chung; identity/dedup/poller/report routing cần connection scope |
| TikTok/email/calendar | SettingsWorkspace.tsx, config/platform_api, agents.py/tool_registry.py | TikTok chưa native connector; email/calendar là simulation, không gọi là kết nối thật |
| Kế hoạch tháng/creative production | Brand hiện name+workspace; planning.py/runner.py; agent/tool catalog | Brand profile và planning nghiệp vụ cần bổ sung; chưa có bằng chứng chu trình tháng → ảnh/video → launch thật hoàn chỉnh |
| Vận hành/CI | scripts/check*, infra/compose*, .github/workflows/p0-foundation.yml | Có harness/CI definition; chưa bằng chứng remote CI/reboot/production, file workflow có mặt không là CI xanh |

Bằng chứng cuối trong [P7 register](P7-COMPLETION-REGISTER.vi.md): 1156backend
passed/0failed/0skipped,8browser,8runtime/SSE,build21entries, source migration0048.
P6 có register riêng với1136tests ở thời điểm trước P7; hai con số không mâu thuẫn.
P7 register đính chính tools/agent_runtime/engine_contract baseline true; không
copy nhận định lịch sử “mọi gate tắt”. Feature flags hôm nay chưa đọc hoặc thay đổi.

### 2.3. Lệch tài liệu đã xử lý trong lượt này

1. README dẫn checklist23/09 và trạng thái Voice/Telegram môi trường cũ: thêm
   chỉ dẫn master + đánh dấu phần mô tả kế thừa không là trạng thái ACOS hiện tại.
2. Master mục3 còn gọi inventory trước P0 là hiện hành: đổi thành snapshot lịch sử,
   dùng ma trận audit này cho trạng thái mới. Không xóa lịch sử/nhận định cũ.
3. Master mục12 còn luồng P6→P7→M6→P8: thay luồng hiện hành S0–S6; bảng10checkpoint
   trước đây giữ làm lịch sử, không dispatch lại.
4. P6 register “Tiếp theo P7.1” và P7 register: thêm link nguồn thứ tự hiện hành,
   không thay local/external acceptance hoặc dọn gate để tạo cảm giác đã hoàn tất.

## 3. Kiến trúc phát triển: tái sử dụng lõi, bổ sung nghiệp vụ

- Doanh nghiệp ánh xạ Workspace theo quyết định đã chốt, nhãn hàng dùng Brand và Brain đã có;
  scope brand không mặc nhiên chia sẻ mọi private brain/chat cho đồng nghiệp.
- BusinessProfile/MonthlyPlan/PlanVersion/CampaignBrief/BudgetReservation/AssetReview
  là khái niệm đề xuất. ADR mapping quyết định phần nào bổ sung schema, phần nào
  tham chiếu Project/Goal/Task/StudioVersion/Artifact/Approval hiện có; chưa thêm bảng.
- PostgreSQL giữ quyền, dữ liệu nghiệp vụ, approvals, reservations và audit.
  Temporal giữ waits/children/history dài hạn; ARQ giữ job ngắn. Không thêm scheduler,
  queue hay planner engine sở hữu cùng task với P6.
- Một connection resolver đưa đúng credential/version vào API/worker/provider.
  Không ép mọi provider dùng cùng schema hoặc đổi toàn bộ token bảng cũ một lần.
- Giữ encryption/SSRF/immutable pins/worker recheck; evaluate DB constraints/RLS
  theo threat model. Không tìm thấy RLS policy trong source đã quét, nhưng không
  kết luận có rò rỉ dữ liệu chỉ vì thiếu RLS. Dùng test hai SME để chứng minh từng đường.
- Local/Ollama vẫn ưu tiên trong môi trường self-host; cloud chỉ theo workspace
  policy. Remote local-agent là nhánh sau, không expose Ollama khách hàng công khai.
- UI tối thiểu đi cùng mỗi checkpoint; M6 là hợp nhất/polish, không xây lại Next.js.
  P8/media sandbox chưa triển khai: MVP cho upload/manual creative và draft brief
  trước; không chờ mọi chức năng ảnh/video mới có thể thử kế hoạch tháng.

## 4. Lộ trình duy nhất S0–S6

### S0 — đồng bộ, chốt thiết kế và bảo vệ baseline

S0.1 audit/tài liệu: hoàn tất phạm vi đọc và cập nhật docs của lượt này, không
đồng nghĩa S0 đã nghiệm thu sản phẩm. S0.2 đã ghi nhận sau phê duyệt; S0.3 đạt local.

S0.2: ba quyết định đã chốt (shared SaaS; managed OAuth/optional BYO;
workspace/brand/team). ADR-S02 ghi mapping entity, ma trận quyền, threat model,
phân biệt approval nội bộ/external và phạm vi triển khai. Chưa runtime acceptance.
Không hỏi lại quyết định đã chốt hoặc yêu cầu credential trong chat.

S0.3: trước triển khai code, phục hồi runtime an toàn, kiểm live schema/contract/
binding/idle và tạo verified checkpoint. Kiểm ignore + secret scan metadata,
đề xuất commit/tag riêng có owner chấp thuận; không push/commit toàn bộ dirty tree
tự động hoặc lưu secret. Giữ source backup ngoài Git nếu chưa thể commit an toàn.

Gate local đã đạt theo S03 acceptance: quyết định rõ, runtime/schema/contract
verified, backup/restore/row hashes/schema equivalent/source archive đạt; không
đụng protected source. Git commit/offsite backup/production vẫn riêng, chưa đạt.

### S1 — doanh nghiệp đang hoạt động và cách ly quyền

- S1.1: thống nhất tenant context và membership; UI chọn doanh nghiệp, dùng cùng
  scope cho Settings/task/Brain/chat. Không gắn JWT với tenant do frontend tự khai.
  Đã local_accepted11/10: contextAPI309operations,active selector25consumer files,
  scoped role,preference/reload,backend67,pure/runtime12,real browser,build21.
  Evidence tại S11 acceptance; S1.2/S1.3 cũng đã đạt local trong các lượt kế tiếp.
- S1.2: cache/SSE/in-flight response/session switch; discard response scope cũ,
  session/run pin giữ nguyên; quyền riêng/private memory không tự mở cho admin.
  Đã local_accepted11/10:25pure/runtime,35focused backend,S12/S11/P7real browser,
  UI12/build21 đạt; transport ticket/abort/raw body/download và actor-SME storage,
  focus/visible membership refresh fail closed. Không phải instant revocation.
- S1.3: worker/job/outbox/export/files và API negative corpus hai doanh nghiệp,
  một người thuộc hai workspace, mất membership giữa enqueue và execute.
  Đã local_accepted11/10: matrix endpoint/resource/actor hai SME/private Brain,
  history/export/files, queued/inflight worker/outbox/revoke, deny trước provider,
  ARQ/Redis thật; sửa disconnect và timeout SSE cleanup.26corpus/factory+65affected
  regression,25pure/runtime,3browser,build21,live contract/binding/replay3/3 và
  exact restore114business tables đạt. Full ban đầu1177passed/2failed; hai lỗi đã
  sửa/recheck, không gọi đó là một lượt full xanh mới. Provider/grants/quota còn S2.
- File dự kiến: access.py, core/auth APIs, usePaoRuntime/usePao và các workspace
  consumers; sửa backend/frontend lần lượt theo contract, không refactor toàn bộ.
- Gate: không đọc/sửa chéo SME/brand/Brain, không gọi model/provider khi bị deny;
  history hợp lệ vẫn mở đúng quyền sau switch/restart.

### S2 — nền tảng kết nối riêng theo SME

- S2.1: connection identity/ownership/brand-account grants; inventory từng provider
  và migration legacy mapping explicit, không silent credential fallback.
  - S2.1A: inventory theo native ACL và preview local references, không load/
    decrypt credential, cấp grant, migration hoặc provider calls; đã đạt local
    111focused+26S13+43engine (các nhóm có test trùng, không tổng unique),25runtime/
    TypeScript/build21; contract311,0048,live source match và exact restore đạt.
  - S2.1B: local_accepted theo các checkpoint và integration14/10; tách B1/B2
    để không gọi storage là authority.
    B1 persisted reference/explicit apply + brand/account/member grants staged,
    expiry/idempotency/CAS/immutable audit/eligibility;0049 additive rollout sau
    verified checkpoint/clone rollback.172focused+32affected,25runtime/build21,
    live317/full1240 đạt; checkpoint/restore cuối xem evidence, không copy secrets.
    B2 local_accepted: B2a model registration-denial/legacy scope pin/fresh native
    credential+member check/publication/memory fences code đã kiểm190+81backend,
    25Node/typecheck/build21/3browser/live317/replay3/3/restore đạt. Chưa active
    grant từ negative fence riêng. B2b explicit consent/model grant pins đã đạt
    local0050/live321/full1298/build/browser/restore. B2c MCP cũng đạt local0051/
    live323/234affected/build/browser/restore; B2d Ads read cũng đạt0052/live327/
    186affected/browser/restore12/10. S2.2A generation/probe fences cũng đạt0053/
    live328/247affected/browser/restore; B1 model quota nay đạt0054/live330/171affected;
    B2a native read queues cũng đạt0055/live332/238affected/browser5;
    B2b/B3 và S2.3A/B/C/D/E/F đạt local; final integration14/10 cũng đạt. Kế tiếp
    S3.1, giữ native role/Brain/
    tool/approval; registered/revoked không fallback legacy. Không repin history.
- S2.2: encrypted vault/reference, config version, rotation/revoke, masking/log
  redaction, SSRF, quota; server master key không thành input Settings SME.
- S2.3: Settings add/test/health/account selection/team access/disconnect; phân biệt
  saved/configured/connected/healthy/accepted, last check và error có hành động rõ.
  A observations/B model/C MCP/D Ads/E host lifecycle/F team-account-mobile đạt local14/10
  theo S23A/B/C/D/E/F và finalS2 integration14/10; không tenant App/OAuth migration S4.
  Local integration đã đóng; Meta official docs429/live riêng.
- Mỗi connector S3/S4/S6 phải có provider dossier từ tài liệu API chính thức
  hiện hành, ngày/version/auth/scopes/review/redirect/webhook/refresh/revoke/quota;
  UI hướng dẫn các trường và thao tác theo provider, không form secret chung mơ hồ.
- Gate: hai SME cùng provider độc lập; revoked credential chặn cả job queued;
  rollback/migration clone, không mất legacy tokens hoặc trả secret ra browser.
- P3/P5 là thành phần tái sử dụng, không làm lại registry/encryption/transport.
- Yêu cầu đã chốt 11/10: cấu hình AI theo từng job. S2 giữ connection/model
  được cấp cho SME, policy local/cloud, quota và credential version; đây là nền
  cho routing S5.3, không bật workflow nhiều model trong S1.

### S3 — Telegram nhiều bot và đúng đích

- S3.1: peer/binding/update/dedup/outbox có connection identity, migrate bot cũ
  thành explicit legacy connection chỉ khi owner chọn mapping.
  - S3.1A foundation đạt local14/10:0059 credential-free namespace/partial
    legacy unique/child guards, không backfill, mapped namespace chưa transport.
    [ADR](ADR-S31A-TELEGRAM-NAMESPACES.vi.md), [register](S3-COMPLETION-REGISTER.vi.md).
  - S3.1B đạt local15/10: owner preview/version/hash/request key/audit và generation mới,
    không repin receipt/peer/binding/history hoặc reuse unknown queue;0060/live338/
    1737backend/5browser/96Node/build21/exact restore trong evidence15/10.
- S3.2: resolver token, bot-specific webhook secret/route hoặc polling offset/lease,
  scheduler/report sender; chỉ một transport owner cho mỗi bot.
  - A scope/lease/metadata kernel source_verified15/10,143focused/52kernel.
  - B: profile/generation/identity/cursor/ingress/outbox durable, source_verified15/10.
    -15/10 phần store đã source_verified:199focused/56store, candidate0061 chỉ
      clone/pao_test, primary0060 giữ nguyên. [Evidence](S32B-DURABLE-STORE-2026-10-15.vi.md).
      Identity resolver/registry native+legacy cũng source_verified sau đó:
      [238focused/39identity, candidate0062](S32B-VERIFIED-IDENTITY-2026-10-15.vi.md),
      clone roundtrips/exact schema, primary0060 không đổi. B cũng đã có scoped
      admission/outbox pins,41scoped/368affected+25Node/candidate0063 theo
      [execution evidence](S32B-SCOPED-EXECUTION-2026-10-15.vi.md). Không làm lại B.
  - C kế tiếp: bridge/webhook/report integration, restart/no-resend/lock ordering/
    retention và full release/rollout, không coi outcome fixture là gửi tin thật.
  - [ADR A/B/C](ADR-S32-TELEGRAM-SCOPED-RUNTIME.vi.md) là phân kỳ duy nhất;
    primary vẫn baseline S31B đến release, không coi source candidate là installed.
- S3.3: UI token nhập an toàn, getMe identity, destination allowlist, team rights,
  ngắt kết nối; token không qua chat hay artifact.
  - Bổ sung yêu cầu15/10: liên kết Telegram ID với tài khoản PAO bằng xác nhận
    rõ ràng; tách cấu hình/giao việc/duyệt/đích nhận, không tự cấp quyền từ /start.
  - Giao diện PAO dùng tiếng Việt; S3.3 kiểm kê và Việt hóa/hướng dẫn mọi nhóm
    Cài đặt hiện có từng nhóm, không chỉ Telegram. Màn hình mới áp dụng ngay.
    [Đặc tả/gate bắt buộc](PRODUCT-SETTINGS-AND-TELEGRAM-ACCESS.vi.md).
    Đây là yêu cầu mới chưa nghiệm thu, không đổi bằng chứng S2 đã đóng.
- Gate fixture: hai bot có update ID/user/chat giống nhau không đụng; mất ACK
  thành unknown, không resend mù; retry/cancel/restart/revocation đạt.
- Gate live để riêng: bot/đích được owner cấp và tin thử vô hại; không cần mở
  channel thật để đánh dấu code/local đã đạt. Kế thừa P7 thay vì fork bridge mới.

### S4 — Meta/Google tenant-aware

- S4.1: app credential ownership theo quyết định S0, OAuth state/config pin,
  redirects/cookie/replay guards; thay local-only Meta form có migration rõ.
- S4.2: connection/team/account grants, scopes/refresh/revoke; sync/warehouse/
  metrics/report/action dùng cùng selected connection/version.
- S4.3: browser Settings và isolation/rotation/restart tests; app-level keys dùng
  chung chỉ trong managed mode, user authorization token luôn tách tenant.
- Gate local đạt độc lập real OAuth. Meta app chưa được Facebook chấp nhận vẫn
  external_pending; không giả token, bỏ provider rules hay gọi fixture là live.
- TikTok native connector là backlog S6.1 riêng sau pipeline read-only ổn định.

### S5 — MVP điều phối kế hoạch tháng

- S5.1: profile doanh nghiệp/brand, sản phẩm/giọng thương hiệu/mục tiêu/KPI/ngân
  sách/nguồn lực/timezone/currency; thiếu dữ liệu hỏi lại hoặc marked unknown.
- S5.2: kế hoạch tháng có version, campaign briefs/lịch/deliverables; chỉnh kế
  hoạch invalidates approval đúng phạm vi, không sửa ngầm task/run đã pin.
- S5.3: specialist Content/Creative/Ads/Analyst nhận brief rõ, output schema và
  rubric; dùng Task/Studio/Goal hiện có. Adapter công việc thật nối từng skill
  được review, không tháo dry-run guard P6 để coi fixed Echo là business runner.
- S5.3 bắt buộc có setup phân công AI theo job, không hardcode hãng theo vai trò:
  mặc định SME → brand → agent → workflow step → job override. Agent/role, model
  và tools là ba cấu hình riêng. Settings cho chọn provider/model/connection,
  Brain/context, tools, token/cost/time limit, approval và fallback allowlist.
  Override không nâng quyền hoặc vượt quota; private context không tự chuyển
  cloud. Pin lựa chọn/version tại admission và recheck ở worker; thay setup chỉ
  ảnh hưởng job mới. Credential không nằm trong snapshot hoặc prompt.
- Gate routing S5.3: hai SME cùng user có model/connection/Brain độc lập; workflow
  có ít nhất hai step dùng hai model đã cấp; capability mismatch, revoked key,
  budget exceeded và fallback trái policy bị deny trước provider call. Test
  queued job không đổi model khi sửa setup, audit hiển thị đúng model/usage.
  Ảnh/video dùng media adapter và gate riêng; text model không được coi là
  đã tạo ảnh hoặc có quyền đăng social/chạy Ads. Giữ local fixture và nghiệm thu
  model/provider thật thành hai loại bằng chứng riêng.
- S5.4: ngân sách planned/reserved/spent/released bằng Decimal/minor units,
  theo campaign/account/currency; concurrent admission không vượt trần. API chi
  tiêu có trễ nên cần headroom/data-age guard, không hứa tuyệt đối chặn overspend
  tại provider. AI không là nguồn tính KPI hoặc số dư authoritative.
- S5.5: phê duyệt kế hoạch/nội dung/external action riêng; recheck worker,
  emergency stop, action unknown reconciliation. Ads pause/resume/update_budget
  hiện có không chứng minh đã hỗ trợ tạo campaign/creative hoặc đăng Facebook.
- S5.6: báo cáo theo giờ/ngày bằng lịch P6, progress/missing data/spend/KPI và
  đề xuất điều chỉnh; pin metric definitions/source/account/time window.
- Gate mẫu A: dữ liệu fixture có nguồn → kế hoạch → tasks → draft/artifact →
  review → simulated action → báo cáo; SME B không truy cập được. Thêm evaluation
  model thật local cho chất lượng draft, không chỉ assertions có chữ/số. Không
  gọi simulated image/video/send là sản phẩm được tạo hoặc chiến dịch đã chạy.

### S6 — nghiệm thu business thật rồi production có kiểm soát

- S6.1: một SME/brand thử read-only, account/period được cấp; đối chiếu provider
  export, money/timezone/quota/missing data; kết nối MCP/TikTok theo nhu cầu riêng.
  Sau đó một hành động thật có phê duyệt riêng và bounded budget, nếu adapter hỗ
  trợ. Publication/media/campaign-creation là adapter riêng, không suy ra từ Ads
  adjustments. Chưa có authority/destination thì giữ external_pending.
- S6.2: CI Linux thực sự chạy + Windows local gates, secure deployment, HTTPS,
  auth/session hardening, signup/invite/deprovision, quotas/noisy-neighbor tests,
  monitoring/alerts, credential backup/rotation, restore đúng SME, retention/
  export/delete, supervisor/reboot/failover trên môi trường riêng. Không reboot PC.
  Quyết định16/10: chưa public signup, chỉ owner mời; chưa tự xóa dữ liệu,
  export/yêu cầu xóa phải đúng scope và có preview/xác nhận riêng. Các luồng
  lifecycle còn thiếu mã là implementation_pending, không gộp vào chờ VPS.
  Chi tiết tại ADR-S6-ACCOUNT-AND-DATA-LIFECYCLE.vi.md. Linux local full backend
  và frontend kiểm riêng đã đạt, có source ZIP/log/JUnit/overlay hashes; chưa
  coi là một hosted GitHub run hoặc production đã đạt.
- S6.3: pilot có owner nghiệm thu, đo chất lượng và chi phí/resource theo tenant;
  gói thuê bao/billing là backlog sản phẩm riêng nếu cần, không tự nối thanh toán.
- M6 polish sau có workflow thực; P8 coding/media/extensions chỉ khi có sandbox/
  review/restore và nhu cầu rõ. Không ưu tiên đủ tính năng Javis hơn business MVP.

## 5. Những việc được hoãn có chủ đích

- P7.5 mic/giọng TTS tiếng Việt và live channel là gate riêng; không chặn thiết kế
  SaaS, nhưng không gọi voice/customer inbox là production accepted.
- M3 Meta/live warehouse và M5B live outcome giữ external_pending; có thể tiếp
  tục fixture/local không phụ thuộc login Meta, không đưa số liệu giả vào business report.
- P8 arbitrary code/plugin/media, thêm nhiều social channels, cloud local-agent,
  PDF/OCR và K8s/microservices: chưa ưu tiên trước S1/S2 và kế hoạch tháng MVP.
- Không chỉ tối ưu cấu trúc thư mục. Refactor module có scope khi cần; đo latency/
  queue lag/RAM/token cost trên cùng workload, không đặt P95/SLA chưa có baseline.

## 6. Quy trình một checkpoint, kiểm đạt rồi mới chuyển

1. Đọc master, register và changes hiện có; khóa scope, không chạy lại phần đã đạt.
2. Nêu files/contracts affected, rollback và một acceptance scenario trước sửa.
3. Nếu schema đổi: checkpoint/restore verified trước migration; test trên clone,
   không destructive reset pao_acos_local để làm tests.
4. Focused unit/integration + adversarial tenant tests, contract/types, browser
   empty/error/reload/mobile phù hợp; runtime/SSE nếu chạm chat/stream.
5. Full regression/build ở điểm tích hợp/schema/release, không chạy full25phút
   sau mỗi sửa docs. Không skip ca khó để pass; ghi warnings và real vs fixture.
6. Rollout local có chủ đích, health/live contract/binding/replay/idle; chưa có
   runtime thì ghi không xác minh, không tái sử dụng HTTP200 cũ làm status mới.
7. Cập nhật trạng thái ở master và evidence link; archive next-step cũ và ghi
   đúng một việc tiếp theo. Chỉ product/schema/auth decision hoặc external write
   mới cần hỏi; không hỏi lại approval local thông thường đã nằm trong scope.

**Toàn S2/S3.1 đạt local; S3.2A/B source_verified15/10; tiếp theo duy nhất S3.2C — bridge/webhook/report integration.**
Ba lựa chọn đã chốt, ADR-S02 đã ghi nhận và S0.3 verified local; không hỏi lại.
S1.1–S1.3 local đã triển khai; không tuyên bố toàn SaaS/provider isolation đạt. Không
đưa deadline hoặc tỷ lệ hoàn thiện tổng khi chưa biết real-provider approvals,
phần cứng, khả năng chạy CI và phạm vi adapters mà chủ sản phẩm cần.
