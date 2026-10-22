# P6 — Bằng chứng cấp quyền iteration đầu tiên

Ngày09/10/2026. Checkpoint evidence ledger; chưa nối launch hoặc nghiệm thu
parent → active child → ARQ toàn tuyến. Goal live vẫn tắt.

## Thay đổi

goals/execution_grants.py thêm issue_first_grant, verify_first_grant và metadata
wrapper nội bộ chưa đăng ký worker. Không thêm endpoint, config flag, bảng hoặc
migration; không sửa kernel và receipt allow_iteration:false cũ.

Khóa Goal rồi child, tái kiểm admission/actor/Plan/approval và delivered start/
decision command với immutable audits. Dựng lại reducer từ policy/proposal và
claim, kiểm latest immutable running projection cùng ledger. Chỉ iteration1,
đúng initial Plan, child_id chưa start, không cancellation, còn đủ thời gian
cho max_duration và giữ đúng ceiling đã reserved.

Child phải inert: identity/command/snapshot/actor/workspace đúng, sequence0,
starting, không cờ hủy, start command dead/goal_parent_owned_start/attempt0 và
audit đúng. Không native attempt/reservation/claim/outcome/projection nào được
tồn tại; mất mutable projection không xóa lịch sử immutable.

Grant UUID ổn định ghi GoalEvent execution_grant bất biến; pin claim/slot/
projection/approval/start/child command, deadline, ceiling và exact backend
source binding. Concurrent/retry chỉ một grant, không bump ledger version,
release ceiling, enqueue/start child hoặc complete M1. Verify/retry luôn kiểm
lại gates, quyền, nguồn và thời gian; grant không phải bearer token vĩnh viễn.

## Kiểm chứng

- 73focused tests đạt/không skip/170.17s:19ca grant mới cùng hồi quy projection,
  iteration adapters và dispatcher. Không gọi model/Ads/MCP/outbound.
- Cấp một lần, bất biến, thiếu/mất authority hoặc ACK, gate rollback, cancellation,
  deadline, reservation/state/pin/origin mismatch, child đã chạy/start ACK sai;
  backend đổi hoặc immutable child history còn dù projection mất đều từ chối.
- Runtime/SSE8/8. Populated dump/restore hash exact trên96bảng snapshot, tái kiểm
  quyền/budget/deadline/source, trigger bảo vệ grant và ledger không đổi; ceiling5
  vẫn giữ, child chưa start, Goal M1 vẫn draft. Clone riêng, không restore đè
  database chính. Restore chỉ bật gates trong process verifier của dữ liệu test;
  không sửa .env hoặc gates API/worker thực tế.
- Parent/start/decision ACK trong ca grant là fixtures được khai báo rõ. Ca
  dispatcher Temporal thật riêng trong hồi quy không biến grant thành nghiệm thu
  chạy iteration toàn tuyến. Chưa full regression của toàn repo mã mới.

## Tiếp theo

Cập nhật: boundary consumption và cha thử nghiệm riêng đã có tại
[grant → child trial](P63-GRANT-CHILD-TRIAL-2026-10-09.vi.md). Kết quả không mở
kernel Goal chính và không thay các giới hạn checkpoint evidence bên trên.

Nối grant với boundary tiêu thụ/cấp quyền launch một lần và reauthorization sát
child start. Thiếu consumption/transport ownership proof thì không đổi receipt
thành allow_iteration:true. Sau đó mới nghiệm thu approval → child start → hủy
parent khi child đang chạy, unknown/crash/restart/restore và UI. Không dùng grant
để bỏ qua approval từng step, mở model/provider hoặc tự giải phóng reservation.
