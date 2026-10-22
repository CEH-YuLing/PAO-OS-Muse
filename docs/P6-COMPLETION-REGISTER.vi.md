# P6 — Sổ đóng công việc, không lặp checkpoint đã đạt

Chú thích 11/10/2026: register này giữ bằng chứng theo ngày, không sở hữu thứ tự
triển khai. “Tiếp theo P7.1” bên dưới là quyết định lịch sử, đã được thay thế bởi
toàn S2 đạt local14/10 theo [nghiệm thu tích hợp](S2-FINAL-INTEGRATION-2026-10-14.vi.md);
S3.1A+B đã đóng local15/10 theo [evidence](S31B-LOCAL-ACCEPTANCE-2026-10-15.vi.md);
S3.2A/B đã source_verified; tiếp theo duy nhất S3.2C — bridge/webhook/report integration
trong [master roadmap](PAO-MASTER-GAP-AND-ROADMAP.vi.md).
Không bắt đầu lại P6.

Cập nhật 10/10/2026. Nguồn quyết định nghiệm thu là tiêu chí P6.1–P6.7 trong
master roadmap, không phải số bài test hay số báo cáo được tạo.

**Trạng thái chính thức: P6.1–P6.7 đã hoàn tất nghiệm thu LOCAL 10/10/2026.**
Main0046;1136backend passed/0skip,7browser passed,8/8runtime,lint/typecheck/
build đạt; restore109business tables và pending outbox restart/dedup đạt.
API/ready/Web200,workerhealthy,M2replay3/3. Model/tool thật,Meta/M3 và
production reboot/failover vẫn chưa đạt; feature gates chính giữfalse.
Chi tiết và lệnh tái nghiệm thu:
[P6.5–P6.7 local acceptance](P65-P67-LOCAL-ACCEPTANCE-2026-10-10.vi.md).
Những phần lịch sử bên dưới không thay thế trạng thái này. **Tiếp theo P7.1**,
không chạy lại grant/runner checkpoint đã đạt nếu code/phụ thuộc không đổi.

Checkpoint cuối verified0046:
`.runtime/checkpoints/p0-20261010T084238-e9825984/manifest.json`,
797source files/110physical tables/3M2artifacts. Source snapshot bao gồm
tài liệu nghiệm thu trước dòng tham chiếu này; không đổi code sau checkpoint.

## Quy tắc thực hiện

- Không chạy lại nguyên checkpoint grant/worker nếu code đó và phụ thuộc không
  thay đổi. Hồi quy toàn backend chỉ dùng ở điểm tích hợp nhiều module/schema.
- Không gọi preview, reducer hay fixture là runner hoạt động end-to-end.
- Không đóng P6.3 bằng việc đổi receipt cũ thành true, bỏ approval hoặc xóa
  reservation. Không đóng P6.4 bằng preview cron, P6.5 bằng delivery giả,
  P6.6 bằng regex hay P6.7 bằng số KPI tăng.
- Tách nghiệm thu local khỏi production/external gates đã được người dùng
  chấp nhận hoãn; không lấy gate production làm lý do trì hoãn code local.
- Báo cáo phải nêu phần code, tích hợp và nghiệm thu còn thiếu; không tự thu
  hẹp tiêu chí rồi gọi toàn bộ P6 hoàn tất.

## Ma trận hiện tại

| Phần | Local đã nghiệm thu | Giới hạn, UX và gate ngoài local |
|---|---|---|
| P6.1 | Planning/DAG/pins/task draft, nghiệm thu local 07/10 | Giữ nguyên gate weights/model thật; không làm lại planning |
| P6.2 | Temporal wait/timer, ARQ fixed Echo, cancellation, local UI/process | Không làm lại kernel; production/real-model vẫn gate riêng |
| P6.3 | **Backend + UI dry-run v1 đạt:** API → dispatcher → Temporal parent/child → ARQ → receipt; hai vòng/replan, approval riêng, cancellation/restore; UI admission/pins/child review/hủy/reload/mobile/retry cùng khóa | Catalog/tìm kiếm phiên là UX tiếp theo; model/tool thật và production failover vẫn gate riêng, không mở gates thật |
| P6.4 | **Đóng local Studio và bounded Goal fixed Echo:** backend/UI CRUD/control/pins/budgets, UTC slot atomic admission, restart dedup, parent-child/ARQ/receipt/cancel/restore; browser Goal+Studio, retry cùng khóa/reload/mobile/gate rollback/slot → parent đạt | Production/live-model vẫn gate riêng. UX catalog plan và phục hồi pending sau reload chưa có; không poll lại report/sync cũ |
| P6.5 | **Đóng local:** Studio/Goal verified sources, scoped read/ack, dedup in-app delivery, pending recovery/permission-loss/retry budget, UI delivery/notification/history, browser và populated restore | External send chưa bật; recipient catalog/attempt audit history là UX/nợ tiếp theo |
| P6.6 | **Đóng local:** conversation/artifact quote và derived extractive proposals có pins/diff, shared quota, human review/note/revert/audit, Unicode/poisoning/secret fences, UI/browser và populated restore | Chưa model summary/PDF/OCR/auto learning; không auto sửa code/policy/skill; không tuyên bố regex chặn mọi injection |
| P6.7 | **Đóng local:** immutable pinned observations24h/72h/7d, preview/confirmation/dedup/coverage/confounders, stored history/stale source, UI/retry/reload/mobile và restore | Warehouse synthetic chỉ nghiệm thu cơ chế; Meta/M3 business và production ingest chưa đạt. KPI không chứng minh causal; thiếu nguồn vẫn insufficient |

## Lịch sử checkpoint0041 — không phải trạng thái runtime mới nhất

- `modules/schedules`: numeric cron 5 trường, DOM/DOW OR, fold chọn rõ, skip
  spring gap, coalesce/skip misfires; cửa sổ quá hạn tối đa7ngày, tìm next tối
  đa366ngày, rate limit preview. Không tạo background poller mới.
- `modules/results`: nguồn terminal phải khớp immutable Studio projection;
  receipt riêng từng user, giao trong ứng dụng không đồng nghĩa user đã đọc.
  Workspace/nguồn được ràng buộc ở DB; destination khác bị từ chối.
- `modules/learning`: chỉ đề xuất trích đoạn chính xác từ user message đã được
  quyền truy cập; pin source hash, human review, note data-only, source-change
  fence, quota10/user/workspace/day, immutable proposal identity/audit. Revert
  không ghi đè note đã sửa, không cần nguồn cũ còn nguyên để thu hồi note.
- `modules/business/outcomes`: chỉ quan sát action thật có execution audit;
  dry-run/unknown không thành outcome thật. Chỉ full hourly coverage cùng
  dimension; DST không có fold identity hoặc action giữa giờ là insufficient.
  Khác action cùng resource được báo là confounder; không chứng minh causal.
- Additive10API, old paths/schemas so với source checkpoint giữ nguyên.
  Contract và TypeScript đã sinh lại. Database chính đã migration từ0039 đến
  **0041**, sau checkpoint xác minh; API và ARQ đã reload đúng process thuộc
  PAO-ACOS. Không bật Goal/Temporal, Meta hoặc gửi ra ngoài. Inbox/learning
  trên runtime chính vẫn tắt; nghiệm thu tính năng chạy trên pao_test riêng.

## Bằng chứng và rollout

- 38 focused tests cho các module mới đạt trước lượt tích hợp toàn backend.
- Full backend: **1039 passed,2 skipped** (hai ca ARQ real-clock opt-in),
  13 cảnh báo ARQ close deprecated,1219.19s. Sau đó chạy riêng hai ca ARQ
  real-clock kill/restart và seed restore: **3 passed,183.24s**. Tổng1042 ca
  khác nhau đạt qua hai lượt, không phải một lượt1042. Backend không đổi
  sau regression; thay đổi tiếp theo là UI/harness/tài liệu.
- Runtime/SSE8/8. Production build riêng19pages đạt, lint/typecheck đạt;
  không đè thư mục dev runtime.
- Checkpoint trước schema đã xác minh:
  `.runtime/checkpoints/p0-20261009T104336-9ef92bff/manifest.json`:
  727source files,97tables,3artifacts,revision0039. Không restore đè dữ liệu chính.
- Checkpoint sau rollout đã xác minh:
  `.runtime/checkpoints/p0-20261009T114027-872673c5/manifest.json`:
  741source files,101physical tables,3artifacts,revision0041. Source archive
  bao gồm UI/harness đã nghiệm thu và sổ trạng thái trước khi thêm dòng
  tham chiếu checkpoint này; không thay đổi code sau checkpoint.
- Populated dump/restore inbox/learning:100business tables giữ hash, receipt
  read/ack và delivery tồn tại, proposal/note/source/audit giữ pins; immutable
  trigger được thử trên clone. Không restore đè database chính.
- Browser thật + API HTTP thật8101/pao_test đã đạt: login, inbox acknowledgement,
  chọn hội thoại nguồn, propose/promote/revert, schedule preview. Outcome chỉ
  nghiệm thu biểu mẫu, **chưa nghiệm thu action thật hay stored observation**.
  Harness sửa race điều hướng trước khi login xong; form có aria-label rõ.
  Sidebar có lối vào `/automation/review`.
- API chính health200/ready200,Web200,worker healthy; live OpenAPI trùng
  contract và execution_binding trùng source:
  `6ef0c75deea427fa03fa09bf4d8a683cba606e6e6fb01653eac63ea521319ca8`.
  M2 archive replay3/3. Goal/Studio executions và commands trên DB chính đều0.

## Hàng đợi còn lại, không bắt đầu lại việc đã đạt

1. P6.3 backend + UI runner fixed Echo đã nghiệm thu local. Không làm lại grant
   trial hoặc runner; adapter model/tool thật là gate riêng, không dùng receipt
   Echo làm bằng chứng nghiệp vụ. UX catalog/tìm kiếm phiên có thể bổ sung sau.
2. P6.4 local Studio/Goal đã đóng bằng backend và UI/browser; không làm lại
   runner/grant hoặc adapter lịch đã đạt. UX catalog/pending reload và
   production/live-model không tự bật, không chặn phần code local P6.5.
3. P6.5: Goal source, delivery UI và outbox recovery/permission-loss.
4. P6.6: artifact/derived proposals có provenance, review và kiểm tra
   poisoning; không biến nội dung học được thành instructions có quyền.
5. P6.7: stored/pinned observations và nghiệm thu nghiệp vụ sau M3.
6. Tích hợp cuối: regression phù hợp với code đã đổi, restart/replay/restore
   và browser đầy đủ. Không chạy lại grant-only checkpoints không đổi.

Các mục trên là **công việc kỹ thuật còn thiếu**, không phải chờ người dùng
duyệt. Không tiếp tục thêm báo cáo để thay cho runner và persisted lifecycle.

**P6 chưa hoàn tất. Không có quyền mới cần duyệt cho các phần code local còn
thiếu. Production reboot, dịch vụ ngoài và live business writes vẫn nằm ngoài
phạm vi tự bật.**

## Chốt runner Goal — 09/10/2026

- Profile mới `p63-runner-v1`, type `PaoGoalRunnerWorkflow`. Không nâng cấp
  admission cũ ngầm hoặc sửa các denial/history cũ. DB journal là authority;
  signal chỉ wake. Source/plan/approver/gates/budget kiểm lại ở launch/receipt.
- Replan reserve plan mới và cần duyệt mới; không retry một plan đã dùng.
  Child ID cố định; lost launch ACK chỉ replay intent trong cùng Temporal run.
- Hủy thật khi native job đã claim có queue ACK; partial completed prefix
  được kiểm chứng trước release. ACK thiếu → manual review, giữ ceiling.
- Full backend trước tối ưu idle timer: **1052passed,2skipped,21warnings,
  1064.17s**. Các skip là opt-in ARQ real-clock; warnings là ARQ close deprecated.
  Lượt full bị dừng trước đó để bổ sung approver fence không tính là full pass.
- Sau tối ưu idle timer chạy **71passed** trên mã cuối (runner13 + reducer +
  legacy iteration validator),114.21s. Không cộng các ca trùng vào full count.
  Idle chờ120s hoặc deadline sớm hơn, signal wake ngay; active-child check1s.
  Ca deadline không browser chỉ có2polls và không tạo child, history replay đạt.
- Production build19pages và runtime/SSE8/8 đạt; old API paths/schemas giữ
  nguyên. Contract giờ39routers/267operations, chỉ cộng3runner endpoints.
- Populated pao_test dump/restore:100business tables hash chính xác; journal
  dựng lại iteration2, bốn native attempts và hai receipts đã kiểm lại; immutable
  Goal event trigger đạt. Primary hash không đổi, dump riêng được giữ.
- Checkpoint verified trước reload:
  `.runtime/checkpoints/p0-20261009T141131-47273e9e/manifest.json`:
  748source files,101physical tables,3artifacts,revision0041. Bao gồm mã cuối;
  cập nhật kết quả trong tài liệu này sau checkpoint không thay backend code.
- Reload đúng API/ARQ thuộc PAO-ACOS, giữ Web/Ollama/volumes/.env. Live contract
  và binding khớp source, M2 archives replay3/3; API/ready/Web200,workerhealthy.
  Binding cuối: `28ec65b2ae4e84a4f15bd5857dff5f10d790a93cd8f396a2b6c67ab55cc52119`.
- Live runner status đúng profile, execution/model_calls=false. DB chính có
  goal_executions/goal_commands/goal_events đều0. Không bật Goal, Meta, Telegram
  hoặc live writes; không tự hoàn thành Goal kinh doanh M1 từ Echo.

Chi tiết vận hành: [Goal runner](GOAL-RUNNER.vi.md). Kết quả trên đóng **backend
runner dry-run local**, không đóng toàn bộ P6 hoặc nghiệm thu production/LLM.

## Chốt Goal UI — 09/10/2026

- Trang `/automation/goals` và sidebar riêng, dùng API runner hiện có, không
  thêm schema/router/migration. Preview pin + checkbox admission không thay
  approval từng vòng; child do Goal sở hữu không có standalone start button.
- Mất admission ACK sau commit thật: retry cùng request key/body, một row;
  URL execution giữ identity để reload đọc lại DB. Không tự POST retry.
- Browser actual HTTP/Temporal/ARQ/DB đạt1scenario/48.80s, zero page errors,
  mobile390px không tràn ngang. Hai vòng completed, replan approval riêng,
  cancel child waiting-approval, ba launches/bốn native attempts, journal
  reconstruct và business Goal vẫn draft. Gates rollback vẫn xem được phiên,
  không admission/decision mới. Một warning ARQ close deprecated không fail.
- Production build20pages/lint/types đạt; runtime/SSE8/8. Backend không đổi
  nên không chạy lại full1052/restore đã đạt. Không nâng phiên legacy hoặc sửa
  database chính. API/ready/Web200, worker healthy, Telegram disabled.
- Tiếp theo: P6.4 persisted schedules, không quay lại runner/grant. P6 chưa
  hoàn tất; model/tool thật, production reboot và external services vẫn hoãn.
- Browser standalone P6.2 regression đạt1scenario/36.87s (approve/reject/
  cancel), chứng minh mở rộng child panel không bỏ đường standalone cũ.
- Checkpoint mới verified:
  `.runtime/checkpoints/p0-20261009T152228-4cfcf9ee/manifest.json`:
  753source files/101physical tables/3artifacts/revision0041. Archive gồm UI,
  harness, roadmap trước dòng tham chiếu này. Main dump restore chỉ trên clone
  riêng; không restore đè dữ liệu thật. Đây không phải chạy lại populated
  runner restore. Sau đó GET status xác thực: runner execution=false,
  model_calls=false; goal_executions/commands/events chính đều0, revision0041.

## Chốt persisted Studio schedules — 10/10/2026

- CRUD/control đã lưu + một ARQ cron owner + UTC ledger, atomic slot/plan/native
  start, hash/source/ACL fences, disable không ngầm cancel child, audit immutable.
  Temporal/ARQ fixed Echo thực phải chờ per-step approval trước attempts.
- Full backend1070passed/2skipped/23warnings,1153.08s; build20pages/lint/types,
  runtime8/8, browserHTTP thật1scenario/18.55s/mobile390px/zero errors đạt.
  Two skipped là ARQ real-clock opt-in, không tuyên bố đã chạy hai gate đó lượt này.
- Populated restore103business tables hash khớp + trigger/slot/native outcome;
  migration clone round-trip đạt; primary không đổi trong clone tests.
- Checkpoint trước schema763source/101physical tables/3artifacts/0041 verified:
  `.runtime/checkpoints/p0-20261010T052319-24adf7f1/manifest.json`.
- Main0042 additive,100 bảng cũ hash không đổi; API/ready/Web200, workerhealthy,
  saved/live contract39/274/binding khớp, M2replay3/3. Schedule/Studio/Goal
  executions/commands/events chính đều0; manager/dispatch/model calls và các
  live writes/Meta/Telegram vẫn tắt. Không sửa `.env` hoặc protected source.
- P6.4 **chưa đóng mọi kind**: bounded Goal schedules chưa có. Tiếp theo là
  adapter lịch → bounded Goal admission hiện có, không quay lại kernel/grant.

Chi tiết: [P6.4 persisted schedules](P64-PERSISTED-SCHEDULES.vi.md).

## Chốt backend bounded Goal schedules — 10/10/2026

- Dùng chung projection/audit/cron owner, thêm immutable Goal slot ở0043.
  Fresh plan + bounded admission + runner binding + UTC slot commit atomically;
  vẫn approval từng vòng/từng step, không auto hoàn thành business Goal.
- 134focusedpassed/12warnings/194.04s; cron bổ sung1passed/3.45s và runtime8/8.
  Real parent-child/ARQ receipt + cancellation khi gates tắt/replay đạt.
  Browser Studio regression1pass/21.91s; chưa nghiệm thu UI Goal schedules.
- Populated restore104business tables hash exact/journal/receipt/slot/trigger;
  migration clone round-trip giữ103 bảng cũ, main không đổi trong clone tests.
- Verified pre-rollout768source/104physical tables/3artifacts/0042:
  `.runtime/checkpoints/p0-20261010T064923-499e72ef/manifest.json`.
- Main0043 giữ hash103 bảng cũ, idle0 trước reload đúng API/ARQ; API/ready/Web200,
  workerhealthy, contract39/281/livebinding khớp, M2replay3/3. Schedule/Goal/Studio
  slots/executions/commands/events chính đều0; execution/live gates tắt.
- P6.4 còn UI Goal schedules; **không còn quay lại backend adapter/kernel/grant**.
  Sau UI/browser mới đóng local P6.4. Không đóng toàn P6 từ checkpoint này.

Chi tiết: [Goal schedules backend](P64-GOAL-SCHEDULES.vi.md).

## Chốt UI lịch Goal — tiếp nối backend 10/10/2026

- **P6.4 local đóng cho Studio và bounded Goal fixed Echo**. Tab Lịch Goal tại
  `/automation/review`: chọn Goal/plan ID, preview nguồn và giới hạn, xác nhận
  lịch tắt, bật/tắt/sửa/lưu trữ, slot/audit và mở parent runner. Giữ nguyên
  Studio/chat/shell. Member chỉ xem; backend vẫn kiểm quyền với mỗi mutation.
- Browser cuối Goal+Studio **2passed,38.82s**, HTTP thật/pao_test/Redis15:
  mất create ACK rồi retry exact request_key/body tạo đúng một lịch, thay
  input hủy preview, reload/control/edit/archive, actual slot → parent
  starting, gate rollback vẫn đọc được và disable còn khả dụng; mobile390px
  không tràn, zero page errors. Parent không tự được duyệt; worker/receipt
  end-to-end đã nghiệm thu ở backend, không gán cho lượt browser này.
- Runtime/SSE8/8, TypeScript noEmit và production build20/20pages đạt.
  Standalone `next lint` yêu cầu cấu hình tương tác chưa có: chưa coi là đạt.
  Những lượt harness lỗi trước final không tính vào proof: đã sửa race refresh
  và đóng page để dừng polling, giữ nguyên assertions/HTTP thật.
- UX catalog plan, phục hồi pending sau đổi tab/reload còn thiếu; màn hình
  cảnh báo pending chỉ giữ ở memory. Đây không phải production acceptance.
- Main0043: health/ready/Web200, workerhealthy, contract281/binding không đổi,
  M2replay3/3; schedule/slot/execution/commands chính0, gates vẫn tắt. Không
  sửa `.env`, schema/backend hoặc source bảo vệ.
- **Tiếp theo P6.5: Goal source → inbox, delivery UI, outbox recovery và
  permission-loss.** Không chạy lại P6.3/P6.4 đã đạt; không tuyên bố hết P6.

Chi tiết: [Lịch Goal backend và UI](P64-GOAL-SCHEDULES.vi.md).

Checkpoint UI verified: `.runtime/checkpoints/p0-20261010T072247-73c4e1b0/manifest.json`,
772source files/105physical tables/3artifacts/0043. Source đã chứa code/báo cáo,
trừ dòng tham chiếu checkpoint bổ sung này; không đổi code sau snapshot.
