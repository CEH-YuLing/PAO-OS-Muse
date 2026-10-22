# P6 — Thử nghiệm grant → một child Temporal

Ngày 09/10/2026. Chỉ nghiệm thu local cô lập trên pao_test; không mở Goal live.

## Đã triển khai

- `consume_first_grant` khóa ledger, tái kiểm đầy đủ quyền, gates, approval,
  deadline, source binding và child inert ngay khi tiêu thụ. Ghi một GoalEvent
  `execution_grant_consumed` bất biến có ID cố định; yêu cầu cạnh tranh không
  được tiêu thụ lần hai. Không giải phóng ceiling hay hoàn thành Goal.
- `PaoGrantChildTrialWorkflow` là cha thử nghiệm riêng, dùng
  `workflow.start_child_workflow` thật với ID cố định và REJECT_DUPLICATE.
  Không sửa kernel Goal hiện hữu, không đổi receipt allow_iteration:false,
  không đăng ký trong worker live, không thêm endpoint/config/migration.
- Activity tiêu thụ không tự retry. Nếu DB đã commit nhưng mất completion ACK,
  workflow thất bại và không khởi động child. Grant giữ trạng thái đã dùng;
  phải kiểm tra thủ công, không remint hoặc coi rằng chưa có intent.
- Child giữ approval từng bước; cha thử nghiệm không chuyển tiếp quyết định
  duyệt. Thử nghiệm chỉ chờ duyệt rồi hủy bằng custom signal và chờ kết quả.
  Start outbox Studio vẫn dead/goal_parent_owned_start/attempt0.

## Bằng chứng đạt

- 26 tests grant/trial đạt, gồm 7 ca mới: hai consumer cạnh tranh; mất quyền,
  gates, cancellation, sai origin; Temporal parent/child thật và mất ACK.
- Temporal history xác nhận parent ID thật, đúng một child-start initiation;
  replay cha và child đạt. Mất ACK sau tiêu thụ: không child-start initiation.
  Gửi trùng ID workflow bị từ chối, kể cả workflow cũ đã kết thúc.
- Không TaskAttempt, model, Ads, MCP hay tool execution. Ceiling vẫn 5 trong
  fixture; start command không bị tái sử dụng để dispatch độc lập.
- Runtime/SSE 8/8. Kiểm tra read-only database chính revision0039, Goal rows,
  commands/events và active jobs đều 0; admission/execution gates vẫn false.
- 54 tests hồi quy first projection, iteration adapters và dispatcher đạt
  (132.56s); tổng hai lượt là 80 focused tests. API health/ready và Web HTTP200,
  worker healthy, Telegram disabled. Không coi liveness là source-contract
  acceptance của runtime mới; không reload runtime ở checkpoint này.

## Chưa nghiệm thu / giới hạn

Goal admission, parent-start và decision ACK đầu vào của thử nghiệm là fixture,
không phải luồng UI → Goal dispatcher → Goal kernel → child end-to-end.
Thử nghiệm có cha Temporal thật riêng, không chứng minh kernel Goal chính đã
chạy iteration. Không test ARQ đang chạy trong checkpoint này vì không duyệt step.

Đây là **at-most-once consumption**, không phải bảo đảm child luôn chạy đúng
một lần: crash/mất ACK có thể để grant đã dùng nhưng child chưa chạy. Temporal
history/replay bảo vệ lệnh start đã ghi nhận; chưa nghiệm thu mất ACK của RPC
child-start, crash/restart toàn tuyến, phục hồi grant đã tiêu thụ hay kill cưỡng
bức cha. Không tự giải phóng budget khi chưa có bằng chứng drain.

Kiểm tra quyền DB và lệnh start Temporal không phải giao dịch nguyên tử giữa
hai hệ thống. Quyền có thể bị thu hồi sau consume; child projection vẫn tái kiểm
quyền và không có step approval trong thử nghiệm. Không được xem đây là quyền
chạy production. API/worker đang chạy chưa reload source mới; không cần reload
để thực hiện thử nghiệm bằng worker riêng. Chưa full regression toàn repository.

## Bước tiếp theo

Cập nhật tiếp theo: [worker replacement thử nghiệm đã đạt](P63-GRANT-WORKER-RECOVERY-2026-10-09.vi.md),
gồm cancel lưu khi worker tắt và drain sau thu hồi quyền/gates. Không phải OS
crash/reboot hoặc Temporal server restart; các giới hạn khác vẫn giữ nguyên.

Trước khi mở kernel Goal: thiết kế recovery/ownership cho consumed intent,
reauthorization và race cancellation; nghiệm thu cha thật với approval/outbox
thật, hủy active child/ARQ, UNKNOWN giữ reservation, restart/restore và UI.
P6 vẫn chưa hoàn tất; các cổng thực thi thật tiếp tục tắt.
