# P6.4 — Lịch bounded Goal, backend và UI fixed Echo local

Checkpoint10/10/2026, tiếp nối persisted Studio schedules. Backend đã nghiệm thu
và rollout0043; **UI Goal schedules đã nghiệm thu local**, đóng P6.4 local cho
Studio và bounded Goal fixed Echo. Không đóng toàn P6 hoặc production.
Không sửa Goal kernel, không bật execution gates hoặc dùng dữ liệu thật để chạy thử.

## Phạm vi đã đạt

- Dùng chung schedule projection/audit/once/cron/DST/misfire/recovery với Studio.
  Giữ owner `runtime.dispatch_studio_schedules.v1` cho cả hai kinds; không poller
  thứ hai. Report/sync/automation owners và API/schema cũ giữ nguyên.
- Goal spec ghim Goal version/content hash/status/due_at, actor/workspace,
  template snapshot/source binding, runner profile và tiêu chí fixed Echo.
  Preview là xác nhận lịch, **không phải approval vòng Goal hay step**.
- Transaction tạo plan mới từ template đã ghim → admission bounded Goal hiện
  có → runner_bound audit → immutable UTC Goal slot → cập nhật cursor. Lỗi ở
  bất kỳ bước nào rollback toàn bộ; không nâng legacy admission thành runner.
- Migration0043 chỉ thêm `goal_schedule_slots`, FK composite scope và trigger
  immutable. Dùng chung quota100schedules/workspace và batch10due/tick.
- Goal chưa bật bị loại trước lấy batch: không làm nghẽn workflow schedules.
  Quyền/pin/Goal due_at được kiểm lại; stale → manual_review, không tự rebind.
- Không overlap trên cùng business Goal, kể cả khác lịch/admission thủ công.
  Pending commands/reservation hoặc manual_review chặn lần mới. Latest eligible
  slot/coalesce/skip/missed7days áp dụng chung, không replay backlog vô hạn.
- Mỗi lần hẹn tạo parent/plan mới; vẫn phải duyệt vòng Goal rồi duyệt từng step.
  Không tự replan/retry unknown. Echo receipt không hoàn thành business Goal.
- Disable/archive dừng các lần hẹn tương lai, không cancel parent đã tạo.
  Cancel bằng API/Goal runner hiện có; cancellation vẫn hoạt động khi gates tắt.

## API và giới hạn

7operations additive tại `/v1/schedules/goals`: status, preview, create, list,
read, control và PATCH. Owner/admin quản lý, workspace member đọc. Workflow
routes chỉ trả lịch workflow, không lẫn Goal specs. Create mặc định disabled;
sửa sau disable/drain, version/idempotency/confirmation hash như lịch Studio.

Goal spec bổ sung goal_id/goal_version, max_iterations1..20,
max_cost_microusd0..1e9, max_elapsed_seconds1..86400,
cost_ceiling_microusd0..1e9, max_duration_seconds1..120 và success_criteria
theo closed contract Goal hiện có. Timeout ceiling phải >= elapsed bound.

Deadline từng parent được backend tính từ lúc admission + elapsed bound và
clamp theo Goal due_at đã ghim. Coalesce không làm sống lại Goal đã hết hạn.
Budget trên là **mỗi lần chạy**, không phải ngân sách trọn đời của lịch cron.
Profile hiện tại chỉ fixed Echo/cost0; chưa dùng cho model/tool thật hoặc chi tiền.
Success criteria hỗ trợ text equals/non_empty; không coi đó là KPI kinh doanh.

Manager/dispatch dùng flags lịch hiện có, Goal dispatch còn cần toàn bộ runner
gates. Main vẫn manager=false/dispatch=false/model_calls=false, `.env` không đổi.
Sau đổi backend/source pins phải preview/duyệt plan mới, không sửa hash trực tiếp.

## Bằng chứng và rollout

- Final focused regression: **134passed,12warnings,194.04s**; gồm Goal schedules,
  Studio schedules, policy, app factory, Goal admission/runner/control. Warnings
  là ARQ close deprecated. Không tuyên bố full1070 cũ kiểm mã Goal adapter mới.
- Cron Goal/coalesce/busy bổ sung riêng: **1passed,3.45s**, không cộng như một
  lượt135. Runtime/SSE8/8; UI code không đổi, không chạy production build lại.
- Real Temporal/ARQ: parent chờ approval, chưa có native child; approve vòng →
  child chờ các step → hai attempts/receipt → parent completed một vòng;
  business Goal vẫn draft. Replay cả parent và child đạt. Cancellation parent
  sau disable + gate rollback có ACK và replay, không tạo attempts.
- Concurrent tick/restart interpreter không trùng admission/slot. Lỗi sau Goal
  admission rollback cả plan/commands/events/slot. Quota và slug fixture đã sửa;
  các lượt thất bại trước đó không được tính là nghiệm thu đạt.
- Browser regression của Studio panel HTTP thật:1passed/21.91s, zero page errors,
  mobile390px; fixture `.runtime/schedule-browser-ccdfd1b477ea4f50b3bc72d1963cfb32/`.
  Đây không phải nghiệm thu UI Goal schedules chưa có.
- Populated dump/restore104business tables: hash exact, schedule audit/Goal slot,
  admission provenance/reconstructed journal/iteration1 receipt/two attempts và
  immutable trigger được kiểm lại trên clone; main không đổi. Seed riêng1pass/
  10.72s chỉ tạo populated fixture, không thêm ca regression độc lập.
- Migration clone0042→0043→0042→0043 đạt;103 bảng cũ hash giữ nguyên.
- Verified checkpoint trước rollout:
  `.runtime/checkpoints/p0-20261010T064923-499e72ef/manifest.json`,768source files,
  104physical tables,3artifacts,0042. Đã so hash checkpoint restore với main.
- Main0043 additive giữ hash103 bảng cũ, bảng mới rỗng. Stop/reload đúng API/
  ARQ sau idle0, giữ Web/Ollama/containers/volumes/.env, không reboot/reset.
- API/ready/Web200, workerhealthy; live authenticated Goal schedule status có
  profilep63-runner-v1, iteration/step approval required, manager/dispatch tắt.
  Schedule/events/StudioSlot/GoalSlot/GoalExecution/Command/Event/Studio execution/
  command trên main đều0; Meta/write/Telegram/external gates vẫn tắt.
- Live contract39routers/281operations/binding khớp;229paths/209schemas cũ nguyên
  vẹn. M2replay qua API3/3. Binding cuối:
  `9df3838c301f82dde53920a363da5dde0cec291d3a1931bf70d7649528c81371`.

## UI lịch Goal — checkpoint tiếp nối 10/10/2026

- `/automation/review` → tab **Lịch Goal** riêng; giữ nguyên lịch workflow,
  chat, shell và các tab hiện có. Chọn Goal đang draft/active; nhập UUID plan
  đã lưu từ Studio tại `/automation` (chưa có catalog tìm kiếm plan).
- Xem trước Goal version/source, plan/source pins, tiêu chí text và giới hạn
  từng phiên/vòng. Thay đổi input hủy preview và xác nhận cũ. Chỉ gửi client
  DTO khi tạo/sửa, không gửi lại server pins như input có thể sửa.
- Tạo mặc định disabled, xác nhận rồi bật riêng; disable/archive không hủy
  parent. Owner/admin được điều khiển; member chỉ xem, backend kiểm tra lại.
- Reload đọc lại lịch từ API; mất create ACK giữ đúng request_key/body để
  retry ngay trên màn hình. Không auto retry. Pending chỉ giữ trong memory,
  chưa phục hồi lệnh chưa rõ sau đổi tab/reload: UI cảnh báo kiểm audit trước.
- Đọc slot/audit và mở `/automation/goals?execution=<parent UUID>`; đọc được
  phiên khi gate tắt. completed của lịch không đồng nghĩa Goal completed.
- Browser cuối: **2passed,38.82s**, gồm Goal lifecycle/retry/pin invalidation/
  reload/gate rollback/actual slot → parent và hồi quy Studio lifecycle.
  HTTP thật, pao_test/Redis15; owned Web3201 dùng `.pao-build-check`, không
  ghi runtime/process registry chính. Zero page errors; mobile390px đạt.
  Bằng chứng `.runtime/goal-schedule-browser-7786a3f56fe145778e00119c1a1e1591/`.
- Harness tạo hai lịch test (archived/completed), một immutable Goal slot và
  parent starting chưa được duyệt; StudioExecution0, business Goal vẫn draft.
  Clock test chỉ gọi dispatcher nội bộ, không thêm endpoint chạy slot giả.
  UI này không tự duyệt/khởi động worker. Parent-child/ARQ/receipt/replay thực
  đã được kiểm riêng ở backend checkpoint phía trên, không tuyên bố lượt
  browser này chạy hết parent/child hoặc model thật.
- Các lượt lỗi harness trước final không tính là đạt: refresh race khi kiểm
  nút disable; request lúc teardown che lỗi gốc và unroute-wait bị chờ polling.
  Đã sửa chờ refresh kết thúc và đóng page trước browser, không bỏ assertion
  hoặc làm giả response. TypeScript noEmit đạt, runtime/SSE8/8.
- Lệnh standalone `next lint` chưa chạy được vì thiếu cấu hình ESLint và yêu
  cầu lựa chọn tương tác; không báo lint đạt. Không tạo cấu hình repo toàn cục
  ngoài phạm vi lịch Goal. Production build riêng `.pao-build-check` đạt:
  compile/type validation và generate20/20pages hoàn tất; không đè dev runtime.
- Main read-only check:0043, API/ready/Web200, workerhealthy; contract281 và
  binding không đổi, M2replay3/3. Schedule/slot/Goal/Studio execution/command
  chính đều0; manager/dispatch/runner/Meta/write/Telegram vẫn tắt. Không đổi
  `.env`, schema hoặc backend API trong lượt UI này.
- Checkpoint source/DB đã verified sau UI/build:
  `.runtime/checkpoints/p0-20261010T072247-73c4e1b0/manifest.json`,772source files,
  105physical tables,3artifacts,0043. Source archive có code và báo cáo final,
  chưa gồm riêng dòng tham chiếu checkpoint này; không đổi code sau checkpoint.

## Tiếp theo

Triển khai phần thiếu P6.5: nguồn kết quả Goal, delivery UI và outbox recovery/
permission-loss; không làm lại kernel/grant hoặc adapter lịch đã đạt. Model/tool thật,
production reboot/failover và delivery ngoài vẫn là gate riêng chưa đạt.
