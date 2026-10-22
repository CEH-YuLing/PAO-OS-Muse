# P6.3 — Theo đuổi mục tiêu có giới hạn

Ngày07/10/2026. Triển khai từng checkpoint, không bật model/Ads/MCP/business
writes hay production. Không coi pure reducer là một goal runner sử dụng được.

## A — Policy và bộ chuyển trạng thái thuần

Module riêng `pao/modules/goals/control.py`; không import database, cấu hình,
provider, ARQ, Temporal, clock, filesystem hoặc shell. Timestamps là tham số
deterministic, không đọc đồng hồ máy. Không sửa kernel P6.2 hoặc frozen Task guard.

Envelope nội bộ `p63-dryrun-goal-v1` ghim execution/Goal/version/actor/workspace,
initial Plan ID/hash, policy và criteria. Các UUID phải canonical, fields closed,
budget là integer strict, không chấp nhận bool/float/NaN thay số.

- Max iterations1–20, elapsed1–86400s, cost ceiling0–1 tỷ micro-USD.
  1 USD =1 triệu micro-USD; dùng số nguyên để tránh làm tròn tiền.
- Deadline hiệu lực là giá trị nhỏ hơn giữa deadline UTC tuyệt đối và thời điểm
  start + elapsed budget. Replan không gia hạn hoặc thay policy ban đầu.
- Mỗi proposal cần Plan ID/hash, cost ceiling và duration1–120s. Kiểm tra trước
  đề xuất và kiểm tra lại thời gian ngay trước approve. Chưa đủ budget thì dừng.
- Mỗi iteration cần approval mới gắn proposal hash. Duplicate decision/receipt
  không tăng iteration hay chạy thêm. Competing/stale proposal không thay pending.
- Không dùng lại một Plan ID đã approve ở iteration trước: P6.2 chỉ cho một
  execution/plan; proposal mới phải tạo immutable plan mới ở checkpoint sau.
- Criteria chỉ là `text` non_empty hoặc equals giá trị đã ghim, tối đa5; tất cả
  phải đạt. Không eval, chạy code hoặc nhờ model tự đánh dấu mục tiêu đã thành công.
- Unmet -> waiting_replan, không tự đề xuất/thực thi plan khác. Hết lượt ->
  budget_exhausted. Receipt sai/unknown -> manual_review, không tự retry.
- Cancel trước execution -> cancelled. Cancel đang chạy chỉ request; vẫn giữ
  reservation đến receipt xác định. Deadline/unknown không giả định chi phí0
  hoặc side effect chưa xảy ra và không tự giải phóng reservation đang chạy.

### Giới hạn chứng minh của A

Receipt hash chỉ ràng buộc dữ liệu, **không xác thực người gửi**. Pure helper
nhận receipt chỉ có origin fixture_echo, dry_run true, cost0. Caller có thể
fabricate receipt: vì vậy không expose helper trực tiếp như API hay đánh dấu
Goal M1 completed từ nó. Trusted DB adapter/authorization/evidence là checkpoint B.

Cost ceilings là reservation dự trù; tests chưa chứng minh billing/model cost
thật được đo hoặc bị giới hạn. Echo không gọi model và không có chi phí API.
Controller giữ trạng thái trong memory; chưa chứng minh đóng browser hoặc
worker crash vẫn giữ goal ownership. Temporal phải sở hữu điều đó ở B.

## B — Goal workflow bền vững + admission/ledger/API

Chỉ bắt đầu sau khi A qua regression và checkpoint verified.

1. Goal workflow riêng, không sửa P6.2 history. Temporal sở hữu loop/approval/
   deadline; không dùng tab browser hoặc thêm scheduler polling để sở hữu goal.
2. Admission ghim Goal/version/actor/workspace/policy/criteria và published plan
   đúng scope; owner/admin và người tạo plan phải được reauthorize mỗi iteration.
   Không tin actor/success/budget do model gửi. Không tự nâng quyền.
3. Một goal execution có execution ID ổn định, command/outbox/request key/audit
   cùng transaction. Goal active guard chống Task/Goal API sửa identity/policy
   hoặc chuyển completed nhằm vượt ledger. Migration additive cần checkpoint.
4. Mỗi iteration dùng plan mới được duyệt; gọi P6.2 child workflow/adapter qua
   envelope ghim pin và IDs. Goal approval không thay thế approval từng step.
5. Read outcome từ DB immutable receipts, kiểm tra scope/pin/schema/usage trước
   reducer. Synthetic echo0cost không được chuyển thành real-model evidence.
   Chưa có meter tin cậy -> từ chối real-model mode, không ghi chi phí0 giả.
6. Parent cancellation drain child/ARQ và chờ ack; UNKNOWN giữ reservation và
   manual_review. Rollback dừng admission nhưng tiếp tục cancellation/reconcile.
7. Real Temporal histories/replay, worker restart khi wait/approval/iteration,
   duplicates/concurrent commands, permission loss, deadline, budget, child
   uncertainty và restore DB. Đây là gate riêng, A unit tests không thay thế.

## C — UI và nghiệm thu local

- Hiển thị policy không đổi, iteration/usage/reserved/remaining, criteria checks,
  proposal diff/hash, duyệt/từ chối/hủy, manual-review và lịch sử.
- Không tạo nút Run hoặc `/goal` trước B thực sự có durable job; không tự
  start goal bằng cách mở tab. Browser chỉ quan sát/gửi command được phép.
- Browser HTTP thật cùng Temporal/ARQ/DB fixture: đóng/reopen tab không làm mất
  ownership; cancel/reject, duplicate submit, không tự vượt budget/deadline.
- Full regression, source contract/replay, checkpoint/restore, no orphan jobs,
  live gates off. Production/VPS/reboot, Meta M3 và external MCP vẫn gate riêng.

User đã yêu cầu tiếp tục đến hết P6. Các bước P6.4–P6.7 vẫn cần triển khai sau
khi P6.3 qua gate DB/API/worker/UI; không coi kernel hoặc fixture là toàn bộ B.
Không publish skill/model-generated plan/code tự động, không bỏ checkpoint,
không gọi model nhằm chứng minh echo đã chạy.

## B1 — Kernel Temporal độc lập

`goals/workflow.py` sở hữu trạng thái GoalControl trong Temporal history. Worker
khởi động lại có thể replay trạng thái chờ approval/replan; browser không sở hữu
loop. Chỉ ba activity cố định: `p63_project`, `p63_prepare_iteration`,
`p63_read_receipt`. Không nhận tên activity/code/tool tùy ý từ signal.

- Mỗi proposal/decision có một pending slot, bounded và first-wins; signal sai
  không chiếm slot. Proposal không thay envelope/policy/deadline ban đầu.
- Prepare phải trả đúng plan/hash, timeout trong ceiling và mọi step cần duyệt.
- Parent gọi đúng P6.2 child workflow, ID `p62-<plan_id>`, REJECT_DUPLICATE;
  không sửa P6.2 kernel/history. Goal approval không duyệt child step.
- Reauthorize tại projection/approval và sau prepare trước child start.
- Parent không dùng output child để đánh dấu thành công; cần activity đọc
  receipt từ DB. Adapter fixture trong test chỉ chứng minh orchestration.
- Hủy gửi `request_cancel` cho child, chờ drain; timeout không generic-cancel
  child bằng asyncio. Deadline/unknown giữ reservation, không retry execution.
- Generic Temporal cancel parent cũng cố gắng drain child trước khi đóng.
  ABANDON bảo toàn child khi drain không xác định; child vẫn có deadline riêng.

**B1 chưa đăng ký trong live worker/API.** Ba trusted activity adapters, ledger,
command outbox, Goal guard, receipt provenance và worker recovery bằng DB/ARQ
thuộc B2. Không thể start goal qua UI/API đang dùng; đây chưa phải goal runner
hoàn thiện, không thay B2/C hoặc gate kill/restart/restore thật.

## B2a — Admission ledger, chưa nối executor

Migration0039 và module `goals/ledger.py`, `goals/api.py` thêm admission/outbox/
audit, active Goal/Task/attempt guards và plan ownership fence với P6.2. Chỉ ghi
resource admission HTTP201; không start Temporal hoặc claim receipt provenance.
Default gate false, status/view ghi rõ execution disabled/ledger only. Trạng thái
`starting` là pending command, không phải worker đã chạy. B2a không thay B2b
trusted activities/iteration claims/dispatcher/worker/process recovery hay C UI.
Xem [tiến độ B2a](P63B2A-PROGRESS-2026-10-07.vi.md).

## B2b1 — Trusted admission provenance

Ngày08/10/2026. `goals/evidence.py` đọc admission/start command/audits thật,
kiểm tra hash cùng stable IDs/scopes, source Goal content pins và reauthorize
original actor/Plan. Decision API gọi boundary trước idempotency; cancellation
vẫn có thể xử lý khi Goal source thay đổi hoặc admission gate rollback.
827backend tests, populated restore và live contract/replay đạt.
Chưa đăng ký p63 activities/goal worker hoặc cung cấp receipt endpoint.
Boundary này không thay iteration ownership, trusted DB outcomes và crash/drain
acceptance ở các checkpoint tiếp theo. Xem
[tiến độ B2b1](P63B2B1-PROGRESS-2026-10-08.vi.md).

## B2b2a — Pre-child projection

`goals/projection.py` kiểm tra nguồn Temporal metadata + persisted dispatch
attempt trước ghi state. Row lock/sequence/canonical hash/immutable audit và
reauthorization chống retry giả/trùng; deadline cố định, cancel DB không mất.
Scope chỉ iteration0/reservation0, luôn trả allow_iteration:false; không nhận
running/completed/usage hoặc claim child outcomes. Không đăng ký live worker.
852backend tests và1Temporal→real DB opt-in acceptance +populated restore đạt.
Dispatcher ACK vẫn fixture; không thay actual goal executor/drain acceptance.
Không mở allow_iteration chỉ bằng đổi flag: cần child/plan ownership,
approved command evidence và trusted immutable receipts ở checkpoint sau.
Xem [tiến độ B2b2a](P63B2B2A-PROGRESS-2026-10-08.vi.md).

## B2b2b — First-iteration claim và receipt reader

Ngày08/10/2026. `goals/iterations.py` thêm prepare/read transaction helpers và
Temporal wrappers, chưa đăng ký trong live worker. Gate mặc địnhfalse. Scope
chỉ initial proposal/iteration1; admission/source pins, reducer state, approval
audit/authority, immutable pre-child projection và budget/deadline được kiểm.
Plan claim + iteration slot atomic/idempotent, chặn standalone P6.2 chiếm Plan.
Child inert, start command dead/goal_parent_owned_start; không giả transport ACK.

Reader lấy từ mọi immutable P6.2 outcome/claim/lease/projection/TaskAttempt và
step approval; không dùng output child. Receipt immutable cost0/fixture_echo,
không hoàn tất Goal M1 hay clear reservation. Cancel/unknown cần drain proof ở
checkpoint sau. Tests có DB/API/native reserve/claim/finish nhưng parent/ACK
vẫn fixture. Full871tests +runtime8/8 +populated restore +Temporal pre-child1/1
và live contract/replay đạt; chưa phải real goal iteration/process acceptance.
Không đổi kernel/history/schema/contracts/UI hoặc actual `.env`.
Xem [tiến độ B2b2b](P63B2B2B-PROGRESS-2026-10-08.vi.md) cho các gate còn lại.

## B2b2c — First-iteration running/receipt projection

`goals/first_projection.py` kiểm immutable claim/slot/approval/audit/authority,
latest projection/sequence và reconstruct reducer; wrapper route iteration1
sau Temporal metadata check. Luôn allow_iteration:false; chưa đăng ký goal
worker/dispatcher hoặc sửa kernel. Running ledger không chứng minh child start.

Completion phải có immutable receipt đã ghi và tái kiểm native evidence trong
cùng transaction trước release ceiling. Unmet→waiting_replan hoặc budget stop;
deadline/unknown giữ reservation. DB cancel+verified completed-child receipt mới
được cancel_ack; không giả cancelled-child/absence/drain proof. Không hoàn tất
Goal M1. Full898tests/runtime8/8, populated completion restore và live gates đạt.
Temporal pre-child regression1/1 vẫn iteration0, không thay real first-iteration
parent/dispatcher/process acceptance. Xem
[tiến độ B2b2c](P63B2B2C-PROGRESS-2026-10-08.vi.md) và remaining drain/replan/UI gates.

## B2b2d — Late completed-child reconciliation

`goals/recovery.py` nhận closed envelope qua internal helper/metadata wrapper,
chưa có endpoint/poller/worker registration. Chỉ stopped iteration1 với verified
completed child; reauthorize admission/Plan/approval/audit, đọc mọi native receipt
evidence trong cùng transaction rồi release reservation đúng một lần. Status/
reason/sequence vẫn dừng, không resume hay complete Goal M1; cancel request không mất.
Immutable reconciliation audit pin before/after/receipt/ceiling, retry revalidates.

914backend/runtime8/8/populated recovery restore và live contract/replay đạt;
Temporal pre-child1/1 vẫn iteration0, parent/transport ACK còn fixture. Không
giả cancelled/absent/unknown thành zero-effect/cost0. Cancelled-child/absence
drain proof, quyền bị thu hồi, replan2+, real dispatcher/worker/process/UI và
P6.4–P6.7 còn phải triển khai. Xem
[tiến độ B2b2d](P63B2B2D-PROGRESS-2026-10-08.vi.md).

## B2b2e — Cancelled-before-claim reconciliation

Internal helper chỉ release khi stopped first iteration có durable parent
cancel request, delivered parent/child cancel commands và immutable audits,
native cancelled projection đúng pin, không TaskAttempt và không immutable
claimed event trên mọi step. Goal→child locks serialize với native job claim;
sticky child cancel/terminal fence chặn delayed claim. Optional reserve/outcome
phải đúng envelope/scope và native cancelled_before_claim. Proof immutable và
retry revalidate authority/absence, release đúng một lần; không đổi terminal
reason/sequence, không resume hoặc complete M1. Wrapper chưa đăng ký worker.

Đây là DB/native-job no-claim proof, **không phải ARQ queue ACK/drain**.
Claimed/UNKNOWN/revoked-authority vẫn giữ reservation.925backend/runtime8/8,
hai populated recovery restore, live reload/contract đã đạt; dispatcher ACK và
parent projections còn fixture. Xem [B2b2e](P63B2B2E-PROGRESS-2026-10-08.vi.md).

## B2b2f — Immutable claim fence khi mất projection

Native claim/recover/fail_pending không được suy luận TaskAttempt thiếu nghĩa
là chưa claim. Immutable claimed event còn tồn tại thì reject409 khi projection
mất, không mint token/attempt mới hoặc known_no_effect outcome. Terminal outcome
có sẵn vẫn quan sát được, không re-execute; trusted Goal reader vẫn cần đủ
evidence. Không tự sửa projection/database hoặc giải phóng reservation UNKNOWN.
6cases mới kiểm claim/recovery boundaries/retry/cancel/rollback và immutable
history.931backend cases qua hai lượt (full929 +2real-clock opt-in), runtime8/8,
populated claim-fence và hai Goal recovery restores đạt. Không thay real
claimed-child ARQ ACK/drain, dispatcher/worker/UI; chưa hoàn tất P6.
Xem [B2b2f](P63B2B2F-PROGRESS-2026-10-08.vi.md).

## B2b2g — Native claimed cancellation fence, không phải queue ACK

Entry point riêng kiểm native fixed-Echo cancellation outcome, immutable claim/
reserve/input binding/lease và mutable TaskAttempt đúng scope/pin/result/timestamp.
Chỉ stopped iteration1, child cancelled với completed_steps rỗng và delivered
cancel commands/audits đúng authority. Missing/UNKNOWN/expired/forged evidence
giữ ceiling; không suy luận cost0 từ absence. Proof known_no_effect:false,
queue_ack_verified:false, native_finish_fenced:true. Cost0 chỉ fixed dry-run
Echo, không model billing. Reconciliation release một lần, retry reauthorize/
revalidate, không resume/complete M1. No-claim entry point cũ không đổi nghĩa.
951backend/runtime8/8/bốn populated restore profiles đạt; real ARQ worker bị giữ
sau claim, native cancel/recover rồi late finish vẫn cancelled. Parent projection/
Temporal command ACK trong ca đó còn fixture. Không endpoint/poller hoặc worker
registration; real parent/drain, partial completion, revoked authority, replan,
worker/UI và P6.4–P6.7 chưa hoàn tất. Xem [B2b2g](P63B2B2G-PROGRESS-2026-10-08.vi.md).

## Queue cancellation ACK → stopped Goal reconciliation (local)

Entry point riêng reconcile_cancelled_queue yêu cầu immutable ARQ ACK trên mọi
reserved step, tái kiểm native cancellation và delivered cancel command evidence.
Chỉ entry point này ghi queue_ack_verified:true, không đổi nghĩa proof native cũ.
Release một lần, không resume/complete M1; UNKNOWN/mất quyền giữ reservation.
43focused tests/runtime8/8 và hai populated queue-ACK restores đạt. ARQ abort
thật; parent/Temporal ACK vẫn fixture, chưa live registration/full regression/
end-to-end. Xem [báo cáo](P63-GOAL-QUEUE-RECONCILIATION-2026-10-08.vi.md).
