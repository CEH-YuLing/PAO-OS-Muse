# Goal runner — backend dry-run có giới hạn

Runner mới có profile `p63-runner-v1`, Temporal type `PaoGoalRunnerWorkflow`.
Không sửa runner/histories cũ, không nâng cấp admission cũ ngầm, không bỏ
approval. Đây là runner fixed Echo, **không phải Goal gọi model/tool thật**.
Hoàn tất dry-run không tự đánh dấu Goal kinh doanh M1 là completed.

## Luồng đã nối

1. Tạo Goal và Studio plan; preview admission ghim version, hash và policy.
2. POST `/v1/goals/{id}/dry-run-runners` với Admission đã xác nhận.
   PostgreSQL lưu admission/runner marker/command atomically.
3. Dispatcher thuê command, xác minh provenance rồi start Temporal bằng ID
   `p63-{execution_id}`. Collision phải đúng type/queue/input mới được ACK.
4. Runner dựng trạng thái từ immutable transition journal, chờ quyết định.
   Signal chỉ đánh thức; không chứa quyền, output hay usage đáng tin cậy.
5. POST decision qua API hiện có. Mỗi vòng cần duyệt riêng. Khi launch phải
   kiểm lại owner, approver, plan, gates, budget, deadline và source binding.
6. Một launch intent/iteration, ghim Temporal run ID và command hash; child
   ID `p62-{plan_id}` cố định, reject duplicate. Retry ACK cùng owner không
   tạo lại claim/child; owner/run khác hoặc quyền đã mất bị từ chối.
7. Child chạy qua worker ARQ fixed Echo. Từng bước vẫn cần approval của P6.2.
   Receipt phải khớp native reserve/claim/outcome/attempt, contract, input,
   projection và approval audit; không chấp nhận kết quả từ browser/Redis.
8. Nếu chưa đạt tiêu chí, runner chờ replan. POST
   `/v1/goal-executions/{id}/proposal` với version hiện tại và plan mới.
   Proposal reserve plan atomically và không tự approve hoặc chạy.
9. Chỉ đạt tiêu chí từ receipt đã kiểm chứng mới completed; hết vòng/cost/time
   phải dừng. Không tự chạy lại một plan, không retry execution UNKNOWN.

GET execution hiện có trả profile, state, commands và audit. GET
`/v1/goal-runners/status?workspace_id=...` trả gate của runner, không phải
cam kết mọi process/network đang healthy.

## Hủy và phục hồi

- API cancel giữ quyền workspace; gate admission tắt không chặn cancel.
- Cha lưu sticky child cancellation fence trước signal; chờ child drain.
- Step đã claim cần native cancellation outcome và ARQ cancellation ACK.
  Step chưa reserve phải không có claim/attempt/outcome và bị terminal fence.
- Nếu đã hoàn thành một phần, prefix completed phải được kiểm chứng bằng
  validator receipt đầy đủ; phần còn lại được kiểm độc lập trước release.
- Không có ACK, lost worker, thiếu receipt, source/permission thay đổi hoặc
  kết quả bất định → manual review, giữ ceiling chưa được chứng minh.
- Worker replacement replay cùng child, không cần tab/browser mở. Không coi
  thử thay worker là OS crash, reboot host hay Temporal production failover.
- Journal/projection khác nhau bị từ chối; không sửa DB bằng tay để tiếp tục.
- Idle approval/replan dùng timer tối đa120s, luôn clamp vào deadline; signal
  wake ngay. Chỉ khi child đang chạy mới kiểm stop/revocation mỗi1s, tránh
  tạo history lớn vì poll từng giây suốt một Goal chờ24giờ.

## Cấu hình và biên an toàn

Runtime chính chưa bật runner. `.env` và credentials không được thay đổi trong
lượt này; `.env.example` có `GOAL_RUNNER_ENABLED=false`.

Admission/launch cần đồng thời:

- `GOAL_RUNNER_ENABLED`, `GOAL_ITERATIONS_ENABLED`, `GOAL_ADMISSION_ENABLED`;
- `STUDIO_ENABLED`, `WORKFLOW_PLANNING_ENABLED`, `WORKFLOW_DURABLE_ENABLED`;
- `WORKFLOW_WORKER_ENABLED`, `WORKFLOW_DISPATCH_ENABLED`, `TEMPORAL_ENABLED`.

Runtime ARQ tái dùng cron dispatch hiện có, không thêm background poller thứ
hai. Worker Studio đăng ký type/activity của runner để tiếp tục drain khi gate
admission bị rollback. Echo worker giữ result60s và hỗ trợ abort khi bật worker;
Redis result không thay thế native DB receipt hoặc audit.

Không đưa Meta/live Ads, cloud model, Telegram send hay executable nội dung
vào profile này. UI Goal đã nối thật tại `/automation/goals`: chọn Goal, nhập
Plan ID đã lưu, xem trước policy/tiêu chí/pins, xác nhận admission, duyệt riêng
từng vòng, duyệt từng bước child, gửi plan mới và hủy. Không có nút bật gates.
Đường dẫn `?execution=<UUID>` mở lại phiên từ DB sau reload; không dùng browser
làm nguồn trạng thái. Mất phản hồi POST có nút thử lại đúng khóa/body, không
tự retry hoặc tạo khóa mới. Child panel do Goal sở hữu không có standalone start.
Chưa có catalog chọn plan hoặc tìm kiếm toàn bộ executions; hiện dùng mã đã
lưu. Model/tool thật và production vẫn là gate riêng chưa nghiệm thu.

## Nghiệm thu

- UI ngày09/10: `p63_browser_acceptance.py` đạt1scenario/48.80s, một cảnh báo
  ARQ close deprecated. Browser → HTTP thật → PostgreSQL pao_test/Redis15/
  Temporal/ARQ: admission mất ACK và retry cùng body, hai vòng với approval
  riêng, replan chưa auto-approve, bốn native attempts, ba child launches
  (hai completed + một cancelled), journal reconstruct, Goal M1 vẫn draft.
  Reload và mobile390px không tràn ngang, zero page errors; gates rollback
  chỉ xem và không POST Goal mới. Không giả receipt hoặc readiness response.
  Harness sửa trùng slug fixture và drain request trước browser teardown;
  các lượt fail trước đó không tính nghiệm thu. `test_backend.py --browser`
  giờ chạy cả P6.2 và Goal acceptance sau backend suite.
- Frontend production build20pages/lint/types đạt, runtime/SSE8/8 đạt. Không
  đổi backend/schema/contract, không chạy lại full1052 chỉ vì thay UI. Giữ
  DB chính0041 và gates off; API/ready/Web200, worker healthy.

- `apps/api/tests/test_goal_runner.py`: actual API/Postgres/Redis15/Temporal/ARQ,
  hai vòng với plan mới, step approvals, completed receipts và history replay;
  cold worker cancellation, gate rollback, claimed abort, partial completion;
  iteration ceiling, duplicate intent, lost launch ACK, missing queue ACK,
  tamper, legacy isolation và approver revocation.
- Chạy chung runner + legacy iteration validator:31passed trước lượt hồi quy
  cuối. Không dùng fixture transport tests làm bằng chứng Temporal end-to-end;
  các ca integration thực chạy cả stack riêng.
- `scripts/check_goal_runner_restore.py` chỉ restore pao_test vào clone tên
  ngẫu nhiên do script tạo, kiểm journal/receipt/hash/immutable trigger. Dump
  được giữ riêng trong `.runtime`, không đưa vào source sạch.
- Full backend1052passed/2skipped trước tối ưu timer; mã cuối đạt71kiểm tra
  liên quan, gồm13ca runner. Dump/restore100business tables, journal và hai
  iteration receipts đạt. Build19pages/runtime8/8 đạt. Live contract/binding,
  health/worker và3M2archive replays đạt sau reload; runner chính vẫn tắt.
  Các lượt bị dừng để sửa code không tính là full pass. Xem sổ hoàn thiện P6
  để đối chiếu chronology và checkpoint; không cộng duplicate test counts.
