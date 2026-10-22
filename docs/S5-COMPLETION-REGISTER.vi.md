# S5 — Sổ triển khai và cổng nghiệm thu

## Kết quả cuối — toàn S5.1–S5.6 local_accepted,0070/live382

Hồi quy cuối: **2224/2224 passed,0 failures,0 errors,0 skips**,2112.43s;
61ARQ deprecation warnings. Backend giữ nguyên binding c22f08ca…f94269 trong
suốt lượt chạy; `.runtime/s5-backend.json` và `s5-full.xml`. Không cộng lượt
126focused/29business_operations hoặc114Node trùng lặp thành tổng backend mới.

114Node đạt; production build22/22 đạt, còn React Hooks warnings. Browser/API
thử và populated exact restore đạt; clone migration0065↔0070 giữ dữ liệu cũ
và chặn downgrade populated. Ollama thật hai bước đạt trên dữ liệu giả, một
model đã cài; hai model theo bước được kiểm chứng bằng fixture riêng.

Primary đã nâng0070/149physical/148business;13bảng mới trống. API source/live
khớp382operations/current binding, API/ready/Web200, worker khỏe, replay3/3
nguyên vẹn và business row hashes không đổi. `.runtime/s5-live.json` và
`s5-schema-rollout.json` ghi bằng chứng. Smoke test ban đầu thiếu profile_id
đã sửa script đúng contract; backend không đổi, không thêm dữ liệu giả vào primary.

Chỉ bật BUSINESS_PLANNING_ENABLED và nâng pin hai launcher0070 sau toàn bộ gate.
Hash các dòng cấu hình ngoài S5 trước/sau bằng nhau ff676907…db16ab2; secret và
các cờ Meta/Google/Telegram/host installer không đổi. Không Ads, đăng bài,
gửi tin, cloud inference hoặc public deployment. Đây là nghiệm thu MVP local,
không phải nghiệm thu production/OAuth/pilot. Giới hạn có trong hướng dẫn S5.
S6 là bước tiếp theo; không làm lại S5 hoặc tự mở hành động thật.

## Ghi chép tích hợp trước phát hành — lịch sử, không phải trạng thái mới nhất

Đã có adapter nối native Run/Studio/TaskAttempt (không thêm runner), lựa chọn AI
ghim theo job, kiểm tra lại quyền tại worker và trước công bố kết quả; duyệt
nội dung riêng với duyệt kế hoạch/hành động, dừng theo thế hệ để không hồi sinh
job cũ. Ledger số nguyên theo tiền tệ hỗ trợ giữ/chi/nhả hạn mức mô phỏng,
kết quả chưa rõ phải đối soát; báo cáo nội bộ theo giờ/ngày dùng scheduler P6.
UI tiếng Việt nối toàn luồng; hướng dẫn tại S5-USER-GUIDE.vi.md.

Clone migration0070 và restore populated, browser luồng draft→duyệt→hành động
mô phỏng→unknown→đối soát→báo cáo đã đạt trên bản phát triển. Local Ollama thật
đạt rubric hai bước với một model đã cài; chọn hai model khác nhau chỉ được
kiểm chứng bằng fixture. Có một lượt chất lượng trước đó sai giá và bị chặn,
giữ lại bằng chứng, không tự duyệt nội dung sai. Các lượt này cần chạy lại trên
source cuối sau sửa lỗi hồi quy, chưa phải nghiệm thu phát hành.

Hồi quy toàn bộ đầu:2217 tests,14 failures,0 errors,0 skips. Đây là lượt phát
triển, source đã đổi trong khi chạy, KHÔNG dùng binding_unchanged của lượt này
làm bằng chứng nghiệm thu. Lỗi nạp vòng khi worker khởi động mới đã được tách
sang access.py; fixture Run cần ID thật; restore allowlist bổ sung migration
đã kiểm chứng. Đang chạy lại kiểm thử. Bản lỗi giữ tại
`.runtime/s5-full-development-failed.xml` và `s5-backend-development-failed.json`.

Primary vẫn0065/live353; không sửa .env, không nâng pin launcher, không restart
dịch vụ chính hoặc chạy quảng cáo/đăng nội dung/gửi Telegram thật.
Các ghi chép0066–0068 bên dưới là lịch sử, không phải phần cần làm lại.

## Lịch sử kiểm chứng0066–0068 — không phải trạng thái mới nhất

Ngày 16/10/2026. **Toàn S5 tại checkpoint cũ: in_progress, chưa local_accepted.**
Primary vẫn0065/live353; không rollout candidate0067 hoặc bật flag S5.
Hai launcher start_acos_local/start_local ghim migration0065 thay vì head,
để lần khởi động thường không tự phát hành candidate0066. Chỉ nâng pin sau release gates.

**Mới nhất candidate0068/368:** S5.3 có routing config append-only theo SME,
hierarchy/narrowing, Studio/S2/Brain preflight và UI tiếng Việt. Chưa có job
adapter/inference hoặc durable execution pins; không gọi preflight là đã chạy
hai model. Primary vẫn0065/live353; không bật S5. Chi tiết
[S5.3 preflight](S53-ROUTING-PREFLIGHT-2026-10-16.vi.md).

**Cập nhật candidate0067/364:** đã có owner review gắn version/hash, expiry,
self-review/missing-data confirmation và atomic Project/Goal/Task draft admission.
Task/Goal đã ghim không sửa qua native API hoặc P6 admission, kể cả khi tắt S5.
141focused backend và browser owner-review→native draft đạt; chưa job execution,
money ledger hoặc toàn S5. Các số0066/361/123 bên dưới là checkpoint trước đó.

| Phần | Trạng thái hiện tại | Còn thiếu |
|---|---|---|
| S5.1 hồ sơ SME/brand |source_verified trong phạm vi owner/admin authoring |Release/integration cuối S5, employee/job context theo grant |
| S5.2 kế hoạch tháng |source_verified authoring/version/owner review/atomic native draft admission |Execution pins và timeline nghiệp vụ end-to-end; release integration cuối |
| S5.3 specialist và AI từng job |partial source candidate: cấu hình phiên bản/hierarchy/UI/preflight |Durable job admission/worker/artifact/quota và hai model thực thi theo step |
| S5.4 ngân sách chiến dịch |not_implemented S5 |Ledger/reservation/concurrency/headroom/data age; không lấy profile budget làm ledger |
| S5.5 duyệt và thực thi |partial: plan review và version invalidation đã source_verified |Content/action approval riêng, emergency/unknown và executor |
| S5.6 báo cáo |not_implemented S5; có nền P6 |Nguồn/KPI/progress/spend, schedule theo ownership hiện có và business acceptance |
| Final S5 |pending |Full regression cuối, route/UI/worker/replay/restore/rollout và model quality gate |

## Bằng chứng candidate hiện tại

- Verified pre-change baseline/source backup:
  `.runtime/checkpoints/p0-20261016T081912-eceb5c33/manifest.json`:
  1151source/0065/136physical/3archives; S4 live gates đạt trước sửa source.
- Migration0066 chỉ chạy trên pao_test và clone riêng:4bảng mới, không sửa bảng cũ.
  Clone0065→0066→0065→0066 giữ exact old rows và rollback schema; populated
  downgrade từ chối, primary không đổi. `.runtime/s5-migration.json`.
- 123backend focused đạt/0fail/0skip/2ARQ deprecation warnings,111.44s:
  business_planning/app_factory/tasks/goal_admission/studio/model_grant_activation.
  30ca S5 nằm trong nhóm trên; không cộng lượt42/28 trước thành số ca riêng.
- Lượt đầu27pass/1test lỗi do dùng tên bảng members thay vì Member ORM; sửa test,
  thêm Unicode corpus rồi các lượt42/final123 đạt. Một lệnh nhầm test_goals.py
  không chạy ca nào; không tính là pass. Không chạy full backend regression mới.
- Browser cuối trên API18102/PostgreSQL riêng đạt: profile/KPI/missing budget,
  kế hoạch nháp, lịch sử, stale profile pins, mobile390/320 và role/SME switch;
  no provider calls, primary_rollout=false. `.runtime/s5-browser.json`.
- TypeScript và114Node tests đạt. Production build source UI cuối đạt22/22entries;
  còn React Hooks warnings kế thừa. Không suy nghiệm thu toàn S5 từ build.
- API source candidate46routers/361operations; generated OpenAPI/types đã cập nhật.
  Không gọi saved/source361 là contract đang chạy của primary353.

## Bàn giao kỹ thuật

Tiến độ0067:7bảng candidate mới so với0065; clone0065→0067→0065→0067 giữ dữ liệu
cũ/schema rollback và từ chối downgrade populated. `.runtime/s5-migration.json`.
141passed/0failed/0skip/2ARQ warnings,131.80s trên business_planning/business_plan_review/
app_factory/tasks/goal_admission/studio/model_grant_activation. Browser cuối0067 có
assert owner approve→tạo1native Task draft, profile stale/history/mobile/SME vẫn đạt.
Backup populated fixture→restore mới giữ exact row hashes/schema và trigger chặn
UPDATE review. `.runtime/s5-browser.json` có populated_restore/restored_review_immutable=true.
Build source cuối0067 đạt22/22entries, TypeScript đạt; còn Hooks warnings kế thừa.
Chưa chạy full regression hoặc rollout primary; không cộng số các lượt test trùng.

Thiết kế: [ADR S5](ADR-S5-BUSINESS-PLANNING.vi.md).
Module `apps/api/pao/modules/business_planning`, migrations0066–0067; UI
`/business-planning` là candidate, chưa gắn menu phát hành hoặc mở primary.
API thật đang chạy chưa có15routes S5 mới; không hướng dẫn khách hàng dùng candidate
URL như một tính năng đã phát hành. Không restart API/worker chỉ để che lệch phiên bản.

Tiếp tục từ S5.3 và các phần S5.2/S5.5 còn mở theo ADR; không làm lại owner
review/materialization đã kiểm chứng, S4/P6 hoặc dựng runner thứ hai.
Chỉ rollout sau gates phù hợp; giữ backup trước migration và idle/process ownership.

## Kiểm chứng bổ sung0068 — cấu hình/preflight S5.3

- 8bảng candidate so với baseline0065,144physical trên database clone; không
  thêm bảng runner/queue. Source contract46routers/368operations khớp generated
  OpenAPI/types; primary vẫn353operations, không đổi .env hoặc launcher pin0065.
- Migration clone0065→0068→0065→0068 đạt exact old rows/schema rollback;
  populated routing downgrade bị từ chối mà không đổi schema/dữ liệu.
  `.runtime/s5-migration.json`; database thử riêng đã dọn, dump giữ lại.
- Browser API18102/DB riêng đạt lưu/đọc lại cấu hình, hai model ở preflight,
  missing specialist denial, owner review/native draft/history/stale/mobile/
  tenant-role switch. Backup populated→restore exact và cả trigger review/
  routing immutable đạt. `.runtime/s5-browser.json`; không provider call.
- 114Node tests và TypeScript đạt; production build22/22entries đạt, còn
  Hooks warnings kế thừa. Không có warning mới từ BusinessRoutingPanel.
- Lượt188ca đầu có187pass/1lỗi test sửa expiry vào immutable grant; chuyển
  sang giả lập đồng hồ, không nới trigger, lượt kế188/188 đạt/2ARQ warnings.
  Sau đó bổ sung ca private Brain→cloud và dùng grant thật của actor khác;
  kết quả bộ cuối được ghi ở phần bàn giao cuối bên dưới, không cộng lượt trùng.
- Kiểm tra socket read-only ban đầu bị sandbox chặn; chạy lại với quyền scoped
  đạt API/ready/Web200. Đây không phải sự cố Docker hoặc lý do restart dịch vụ.

Tiếp theo vẫn là **S5.3 native job adapter/worker**, không làm lại routing config
hoặc review/materialization. Các mục money/content/action/report còn mở;
chưa full backend regression mới và chưa final S5 acceptance/rollout.

### Bàn giao source0068 cuối

189passed/0failed/0skip/2ARQ deprecation warnings,127.79s trên business_routing/
business_planning/business_plan_review/app_factory/tasks/goal_admission/studio/
model_grant_activation. 48ca routing nằm trong189, không cộng các lượt40/188.
Ca grant của actor khác dùng grant thật đã kích hoạt, không chỉ ID không tồn tại;
private Brain local được phép nhưng cloud bị từ chối trước provider factory.
Browser và migration0068 cuối đạt, routing immutable restore được assert thật;
114Node/TypeScript/build22 đạt. Primary API/ready/Web200/live353 được đọc lại,
`.env` hash vẫn5672f741…5fbea7. Chưa chạy full regression toàn hệ thống.

Một source+baseline DB checkpoint mới được tạo bằng backup_acos_checkpoint.py
sau cập nhật báo cáo. Nó bảo vệ source0068 và DB primary0065; không phải minh
chứng đã rollout0068 hoặc toàn S5 local_accepted. Dump populated candidate riêng
đã restore exact trong `.runtime/s5-browser.json`. Bản sao riêng được giữ lại;
chỉ các database/API thử thuộc lượt kiểm tra đã được dọn.
