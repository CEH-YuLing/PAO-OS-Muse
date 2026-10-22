# PAO

**Hiện tại: S6 chuẩn bị local, chưa nghiệm thu toàn S6/production.** Người dùng
đã hoãn dữ liệu thật. Linux backend2224/2224 đạt; frontend kiểm riêng114Node/
TypeScript/build22 sau sửa archive JSX đạt. Windows/browser/restore đạt;
GitHub CI chưa chạy hosted. Lifecycle tài khoản/dữ liệu còn thiếu mã theo hai
quyết định đã chốt. Không đổi backend/S5 hoặc mở provider.
Xem [sổ S6](docs/S6-COMPLETION-REGISTER.vi.md) và
[hướng dẫn chuẩn bị](docs/S6-LOCAL-PREPARATION.vi.md).

**Toàn S5 đạt local16/10 —0070/live382:** đã nối hồ sơ/kế hoạch có phiên
bản, native Run/Studio job, AI theo job, duyệt nội dung, ledger/hành động mô phỏng
và báo cáo giờ/ngày. Hồi quy backend2224/2224,114Node/build22/browser/restore/
local-quality đạt. API/ready/Web200, worker khỏe, replay3/3 và dữ liệu cũ giữ nguyên.
Chỉ bật S5, không đổi secret/cấu hình kết nối khác. Tiếp theo S6; production
và dịch vụ thật chưa nghiệm thu. Xem giới hạn MVP local trong hướng dẫn.
Xem [sổ S5](docs/S5-COMPLETION-REGISTER.vi.md),
[báo cáo tích hợp](docs/S5-INTEGRATION-2026-10-16.vi.md) và
[hướng dẫn tiếng Việt](docs/S5-USER-GUIDE.vi.md). Không bật Ads/đăng bài thật.

## Điểm bắt đầu hiện hành — cập nhật 16/10/2026

[Master roadmap](docs/PAO-MASTER-GAP-AND-ROADMAP.vi.md) là nguồn duy nhất cho
trạng thái và thứ tự phát triển; [audit/kế hoạch đồng bộ](docs/PAO-UNIFIED-DEVELOPMENT-PLAN-2026-10-11.vi.md)
ghi chi tiết. Ba quyết định SaaS đã được duyệt; thiết kế ghi tại
[ADR-S02](docs/ADR-S02-SAAS-TENANT-AND-CONNECTIONS.vi.md). S0.3 baseline/restore
[đã đạt local](docs/S03-LOCAL-BASELINE-ACCEPTANCE-2026-10-11.vi.md); S1.1 tenant context/
chọn doanh nghiệp [đã đạt local](docs/S11-LOCAL-ACCEPTANCE-2026-10-11.vi.md);
S1.2 client scope [đã đạt local](docs/S12-LOCAL-ACCEPTANCE-2026-10-11.vi.md).
S1.3 server/job/outbox corpus và SSE cleanup [đã đạt local](docs/S13-LOCAL-ACCEPTANCE-2026-10-11.vi.md).

**Mốc lịch sử16/10: toàn S4.1–S4.3 local_accepted; lúc đó tiếp theo S5.** Ứng dụng PAO/BYO theo SME, OAuth/config pins, resolver/worker và Cài đặt tiếng Việt đã rollout0065/live353.2099ca backend có kết quả cuối đạt (full2089/10lỗi fixture,52+82kiểm lại đạt, backend không đổi; không full rerun),114Node/TypeScript/build21/browser Meta+Google/Telegram regression/lock-fresh-process đạt. API/ready/Web200,workerhealthy,current binding/replay3/3/exact restore135business đạt; dữ liệu cũ/.env nguyên vẹn. Không kết nối thật hoặc bật Ads. [Báo cáo S4](docs/S4-INTEGRATION-2026-10-16.vi.md), [sổ S4](docs/S4-COMPLETION-REGISTER.vi.md).

**Mốc lịch sử: toàn S2 đã đạt local14/10; toàn S3.1–S3.3 đạt local15/10.** Runtime/webhook/report và Settings/pairing/team/hướng dẫn tiếng Việt đã nạp vào bản chạy0064/349.2078ca backend có kết quả cuối đạt (full2077/1lỗi script phục hồi; sửa allowlist rồi27retry đạt, không full rerun);109Node/TypeScript/build21/browser tích hợp đạt. API/ready/Web200,workerhealthy,current binding/replay3/3 khớp; dữ liệu cũ/.env nguyên vẹn. Chưa bật bot thật.

[Báo cáo S3 lịch sử](docs/S3-INTEGRATION-2026-10-15.vi.md), [sổ S3](docs/S3-COMPLETION-REGISTER.vi.md) và [ADR](docs/ADR-S32-TELEGRAM-SCOPED-RUNTIME.vi.md) ghi gate tại thời điểm đó. Không dispatch lại từng primitive đã làm. S4 nay có managed/BYO riêng theo SME, không dùng form host cũ làm cấu hình tenant; bot thật/real OAuth/HTTPS/reboot vẫn external_pending.

### Lịch sử checkpoint — không dispatch lại các bước đã đạt

Các trạng thái/phiên bản/số test dưới đây thuộc thời điểm từng checkpoint;
không thay thế trạng thái hiện hành và bằng chứng tích hợp bên trên.
S2.1A inventory/mapping preview [đã đạt local](docs/S21A-LOCAL-ACCEPTANCE-2026-10-11.vi.md);
S2.1B1 staged identity/grants/audit đạt local theo
[evidence](docs/S21B1-LOCAL-ACCEPTANCE-2026-10-11.vi.md).
B2a model negative fence đạt local theo [evidence](docs/S21B2A-LOCAL-ACCEPTANCE-2026-10-11.vi.md);
B2b explicit model consent/pins/Settings đạt local theo [evidence](docs/S21B2B-LOCAL-ACCEPTANCE-2026-10-11.vi.md);
MCP B2c đạt local0051/live323 theo docs/S21B2C-LOCAL-ACCEPTANCE-2026-10-11.vi.md;
B2d Meta/Google read đạt local0052/live327 theo docs/S21B2D-LOCAL-ACCEPTANCE-2026-10-12.vi.md;
S2.2A đạt local0053/live328 theo docs/S22A-LOCAL-ACCEPTANCE-2026-10-12.vi.md;
S2.2B1 model quotas đạt local0054/live330 theo
[evidence](docs/S22B1-LOCAL-ACCEPTANCE-2026-10-13.vi.md).
B2a native read queues đạt local0055/live332 theo
[evidence](docs/S22B2A-LOCAL-ACCEPTANCE-2026-10-13.vi.md).
S2.2B2b metadata quota/model/MCP discovery backend đạt local0056/live334,
theo [evidence](docs/S22B2B-METADATA-QUOTA-2026-10-13.vi.md).
B2b credential payload/URL logging đã đạt local theo
[evidence](docs/S22B2B-CREDENTIAL-PAYLOAD-2026-10-13.vi.md):356affected/browser3,
không đổi schema/contract hoặc bật provider. Local discovery/selection quota đã
[đạt local](docs/S22B2B-LOCAL-DISCOVERY-2026-10-13.vi.md):425affected/browser4,
0056/live334, generated optional nonce headers. Legacy unaccounted inference
đã [đạt local](docs/S22B2B-LEGACY-ACCOUNTING-2026-10-13.vi.md): không policy-row
exemption, không repin queued unknown work, không gọi model khi kế toán tắt.
Regression472pass/1fixture lỗi rồi focused38/38, Knowledge3/3, browser4/4;
không phải full backend xanh mới. Shared embedding admission và Memory create/edit/
search/recall/extraction đã [đạt local](docs/S22B2B-MEMORY-EMBEDDINGS-2026-10-13.vi.md):
189backend/25runtime/contracts/typecheck/build21/browser2+1,0057/live334;
chung model cap theo SME, unknown usage/debit và lexical fallback giữ riêng.
Knowledge index/query đã [đạt local](docs/S22B2B-KNOWLEDGE-EMBEDDINGS-2026-10-13.vi.md):
565integrated B2b/25runtime/contracts/typecheck/build21/browser2+1,
0058/live334; queued pins/generation và lexical fallback giữ source/Brain ACL.
**S2.3F team/account/mobile đạt local14/10 trước cổng tích hợp cuối.**
63native backend/8browser/80Node/typecheck/build21/0058/live334/exact restore theo
[evidence](docs/S23F-TEAM-ACCOUNT-MOBILE-2026-10-14.vi.md). Không tự invite/grant/
revoke, không tenant App S4 hoặc fullS2 đã nghiệm thu. Vai trò trong phiên không
bảo đảm quyền hiện tại; native team listing không là toàn bộ nhân sự.
**S2.3E host lifecycle/scope trước đó đạt local14/10.**
26affected gồm4browser/77Node/finalTypeScript/build21/0058/live334/exact restore theo
[evidence](docs/S23E-HOST-CONFIG-SETTINGS-2026-10-14.vi.md). Secret/draft clear,
native CAS/manual recovery/readonly/single-owner-workspace gates giữ nguyên;
không .env thật, restart/tenant App S4 hoặc fullS2.
S2.3D Ads lifecycle/help trước đó đạt local14/10:
100native backend+5browser qua affected/focused recovery,71Node/typecheck/build21/
0058/live334/exact restore theo [evidence](docs/S23D-ADS-SETTINGS-2026-10-14.vi.md).
OAuth popup/URL/consent/cached accounts/jobs/unknown recovery giữ native gates;
không Ads writes/provider thật/tenant App S4. Meta official docs429 còn live gate.
S2.3C MCP lifecycle/help trước đó đạt local14/10:
157affected backend/64Node/typecheck/build21/finalbrowser5/0058/live334/binding
không đổi/exact restore theo [evidence](docs/S23C-MCP-SETTINGS-2026-10-14.vi.md).
Native MCP bearer/rotation/permission/discovery/disconnect giữ gates; không server
thật/OAuth upgrade. Tại snapshot S23C, host-config/team/account/mobile/finalS2 còn mở;
các gate local đó đã đóng ở lượt cuối14/10 bên trên.
S2.3B cloud lifecycle/help trước đó đạt local14/10:
147affected trước visual console audit/57Node/typecheck/build21/finalbrowser3,
0058/live334/binding không đổi/restore theo [evidence](docs/S23B-CLOUD-SETTINGS-2026-10-14.vi.md).
S2.3A observations trước đó đạt local14/10:
76affected gồm browser2/49Node/typecheck/build21/9installed snapshots/0058/live334/
binding không đổi/exact restore theo [evidence](docs/S23A-SETTINGS-OBSERVATIONS-2026-10-14.vi.md).
B3 quota Settings trước đó đạt local14/10:
128affected backend+35Node/typecheck/contracts/build21/browserHTTP1,
0058/live334/binding không đổi và restore theo
[evidence](docs/S22B3-QUOTA-SETTINGS-2026-10-14.vi.md). Quota không là billing;
không mở quyền provider hoặc thay secret/flags.
Tại snapshot B3, S2.3/finalS2 chưa đạt; nay đã đóng local. Global host fairness,
Ads thật và production vẫn chưa đạt.
Xem [ADR-S21A](docs/ADR-S21A-CONNECTION-INVENTORY.vi.md).
P6 local đã đạt;
P7.1–P7.4 local đã đạt, P7.5 mic/live channel và production vẫn chưa nghiệm thu.
Sau recovery11/10: API/ready/Web200,workerhealthy,Docker/PG/Redis healthy,
schema0048,checkpoint/restore verified. S1.1 đã đổi tenant UI/read-onlyAPI và restart
API/ARQ:contract309,health200; không đổi secret/gates hoặc bật integration.
S1.2 chỉ frontend/test harness,25pure/runtime,35focused vàS12/S11/P7browser đạt;
không restart backend hoặc thay binding; schema vẫn0048. S1.3 sửa backend SSE và
reload API/ARQ an toàn; contract309/schema0048 giữ nguyên,không đổi .env/gates.
Full S13 ban đầu1177passed/2failed; sửa hai lỗi rồi26corpus/factory+65affected đạt;
25pure/runtime,3browser,build21 và exact restore đạt. Không claim một full xanh mới.
SaaS production/provider isolation vẫn chưa đạt; không lấy full tests10/10 làm lần chạy mới.
S2.1A thêm2API read-only/preview: contract311; schema0048, .env/gates giữ nguyên.
111focused+26S13+43engine,25runtime/typecheck/build21,live match/replay/restore đạt.
Không chạy lại full regression hoặc browser acceptance mới trong S2.1A; UI Settings/grants chưa triển khai.

S2.1B1 đã rollout additive0049/317operations:172focused+32affected backend,
25runtime/typecheck/build21 và live gates đạt; full1240/0failed/0skip cũng đạt.
Manifest/restore niêm phong cuối ghi trong báo cáo nghiệm thu.
Secret/.env/gates giữ nguyên, mới chỉ staged data, `execution_enabled=false`;
không có Settings flow hoặc quyền chạy tools của employee mới. Toàn S2.1B/S2 còn mở.

B2a thêm model execution-denial/fresh checks/publication/memory fences;
190focused+81affected/29modelcorpus,25Node/typecheck/build21/3browser/live/replay/
pre-deploy restore đạt; seal cuối trong report. Schema0049/317operations giữ nguyên. Không activate
staged grants, không chạy lại full1240 của B1 như evidence bản mới.

B2b rollout0050/321operations,full1298/0fail/0skip,25Node/typecheck/build21,
model/S12/S11/P7 browser và exact restore đạt. .env/flags không đổi, live consent0.
P7 có một lỗi thoáng qua rồi bốn lượt đạt; chưa xác định root cause, không gọi đã sửa.

Các mô tả Phase0–18 và checklist bên dưới thuộc môi trường/lịch sử kế thừa;
đặc biệt Voice/Temporal/Telegram từng bật không có nghĩa đang bật trên ACOS.
Không dùng các đoạn này như một roadmap hoặc gate nghiệm thu hiện hành.

Trợ lý AI tự host cho cá nhân và nhóm nội bộ. PAO kết hợp giao diện Orb với FastAPI, PostgreSQL, Redis/ARQ và mô hình local qua Ollama.

PAO có đăng nhập, workspace, hội thoại lưu bền, streaming SSE, hủy run và Memory local theo thương hiệu. Chief lập kế hoạch, điều phối Researcher/Editor/Marketing rồi tổng hợp kết quả. Tool Gateway hỗ trợ tìm kiếm web, duyệt email/lịch mô phỏng và nhật ký thực thi. Meta connector, kho dữ liệu, báo cáo, Performance/Creative Intelligence, Meta Write Copilot và Attribution + CRM đã triển khai; write thật bị khóa mặc định và các tích hợp quảng cáo vẫn cần nghiệm thu bằng dữ liệu thật. Các node khác là phần giới thiệu giao diện.

Checklist hiện tại: [toàn hệ thống và tương thích — cập nhật 23/09/2026](docs/SYSTEM-CHECKLIST-2026-09-23.vi.md). [Phase 7 Meta](docs/PHASE-7-META.md), [Phase 8 Warehouse](docs/PHASE-8-WAREHOUSE.md), [Phase 9 Reporting](docs/PHASE-9-REPORTING.md), [Phase 10 Intelligence](docs/PHASE-10-PERFORMANCE-INTELLIGENCE.md), [Phase 11 Meta Write](docs/PHASE-11-META-WRITE.md), [Phase 12 Ads Approval](docs/PHASE-12-ADS-APPROVAL.md), [Phase 13 Limited Autopilot](docs/PHASE-13-LIMITED-AUTOPILOT.md), [Phase 14 Creative Intelligence](docs/PHASE-14-CREATIVE-INTELLIGENCE.md), [Phase 15 Attribution + CRM](docs/PHASE-15-ATTRIBUTION-CRM.md), [Phase 16 Google Ads](docs/PHASE-16-GOOGLE-ADS.md), [Phase 17 Advanced Automation](docs/PHASE-17-ADVANCED-AUTOMATION.md) và [Phase 18 Voice](docs/PHASE-18-VOICE.md) đã triển khai local. Temporal và Voice đang bật trên bản local đã nghiệm thu; Google Ads, live Meta write và Autopilot vẫn tắt.

## Chạy local

Môi trường PAO-ACOS đang dùng web http://127.0.0.1:3200 và API
http://127.0.0.1:8100, PostgreSQL/Redis riêng ở cổng 15432/16379.
Khởi động từ thư mục dự án bằng `./scripts/start_acos_local.ps1`.
Hướng dẫn hiện hành nằm tại
[chạy PAO-ACOS độc lập](docs/ACOS-LOCAL-RUN-2026-10-05.vi.md).
Các lệnh Phase 0–18 bên dưới là hướng dẫn môi trường local lịch sử.

Làm theo [hướng dẫn cài đặt](docs/LOCAL-DEVELOPMENT.md). Với máy đã thiết lập:

```powershell
npm run build
./scripts/start_local.ps1
```

Mở http://127.0.0.1:3100. Cấu hình CPU local hiện tại được giữ nguyên; có thể đổi model và phần cứng sau.

## Cấu trúc

- `apps/web`: Next.js/React, Orb và giao diện hội thoại PAO.
- `apps/api/pao`: API, domain, gateway Ollama và worker ARQ.
- `packages/agent-config`: cấu hình agent và phiên bản prompt.
- `packages/contracts`: OpenAPI và kiểu TypeScript sinh tự động.
- `infra`, `scripts`: Docker, khởi động local và kiểm thử.

Xem [lộ trình Phase 1](docs/PHASE-1-PLAN.md), [kết quả Phase 1](docs/PHASE-1-RESULT.md) và [ghi chép đổi tên PAO](docs/REBRAND-PAO.md).

Frontend runtime Phase 2: [kế hoạch](docs/PHASE-2-PLAN.md) và [kết quả nghiệm thu](docs/PHASE-2-RESULT.md).

Memory Phase 3: [hướng dẫn vận hành](docs/MEMORY.md), [kế hoạch](docs/PHASE-3-PLAN.md) và [kết quả nghiệm thu](docs/PHASE-3-RESULT.md).

Agent Runtime Phase 4: [hướng dẫn vận hành](docs/AGENT-RUNTIME.md), [kế hoạch](docs/PHASE-4-PLAN.md) và [kết quả nghiệm thu](docs/PHASE-4-RESULT.md).

Tool Gateway Phase 5: [hướng dẫn vận hành](docs/TOOL-GATEWAY.md), [kế hoạch](docs/PHASE-5-PLAN.md) và [kết quả nghiệm thu](docs/PHASE-5-RESULT.md).

Telegram Phase 6: [thiết lập bot và whitelist](docs/TELEGRAM.md), [kế hoạch](docs/PHASE-6-PLAN.md), [kết quả triển khai](docs/PHASE-6-RESULT.md). Bản local đã chạy bot Telegram và nghiệm thu task → kết quả thật. Cài đặt mới mặc định tắt, cần token và whitelist riêng.

## Nguồn gốc và giấy phép

PAO phát triển từ [APEX-UI của Ruben Mouradian (Reznikov Engineering)](https://github.com/RubenM1990/APEX-UI). Tên sản phẩm hiện tại là PAO; không đại diện cho thương hiệu hay tác giả gốc.

Mã nguồn được phân phối theo [MIT](LICENSE). Giữ nguyên thông báo bản quyền gốc và [ghi công các thành phần cộng đồng](CREDITS.md). Tên APEX và thương hiệu Reznikov Engineering không được cấp phép theo giấy phép mã nguồn này.
