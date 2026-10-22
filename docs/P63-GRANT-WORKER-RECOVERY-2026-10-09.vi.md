# P6 — Phục hồi worker của thử nghiệm grant → child

Ngày 09/10/2026. Checkpoint local trên pao_test và Temporal server cô lập.
Không mở Goal live; không sửa backend, schema, config hay runtime chính.

## Phần bổ sung

Thêm ba ca kiểm thử Worker replacement trong `test_goal_grant_trial.py`:

1. Cha thử nghiệm dùng grant thật trong ledger, tạo child Temporal thật.
2. Child dừng tại waiting_approval; không đăng ký activity thực thi step.
3. Dừng Worker thử nghiệm có kiểm soát, không dừng Temporal server.
4. Giữ nguyên quyền, hoặc tắt Goal/admission/Temporal gates, hoặc đổi owner
   thành viewer trong database test.
5. Gửi custom cancel signal khi không có worker polling. Temporal lưu signal.
6. Tạo Worker instance mới với cache mới; replay cha/child, nhận signal đã lưu,
   hủy và chờ child trả kết quả cancelled.

Xác nhận run_id của child trước/sau giống nhau, đúng một child-start initiation,
đúng một child workflow started và parent ID đúng cha thử nghiệm. Replayer độc
lập cũng đạt cho cả cha và child. Không nhận kết quả từ một workflow trùng tên.

Bổ sung kiểm tra lost consume ACK: sau commit grant consumption nhưng activity
thất bại, gọi consume lại bị từ chối `goal_grant_already_consumed`. Không grant
mới, không child start. Bỏ catch Exception rộng ở vòng chờ child; chỉ bỏ qua
RPC NOT_FOUND lúc child chưa xuất hiện, lỗi khác phải lộ ra.

## Kết quả hiện tại

- 29 tests grant/trial đạt, không skip, 74.96s: 10 trial + 19 grant evidence.
- Runtime/SSE 8/8 đạt. Không gọi model, Ads, MCP hay dịch vụ ngoài.
- Sau worker replacement: một consumed event, không TaskAttempt, ceiling vẫn 5,
  Studio start command vẫn dead/goal_parent_owned_start và attempts0.
- Database chính revision0039, Goal executions/commands/events đều 0;
  admission/execution false. API health/ready và Web HTTP200, worker healthy,
  Telegram disabled. Runtime chính không restart/reload.

## Giới hạn bắt buộc giữ

Đây là shutdown có kiểm soát và thay Worker instance trong cùng process kiểm
thử, không phải kill process, crash Windows, reboot VPS hay restart Temporal
server. Không kiểm mất RPC child-start ACK; không có crash giữa DB commit và
Temporal command trong ca worker replacement. Ca lost consume ACK là lỗi giả
lập sau DB commit thật và vẫn fail closed, không tự phục hồi bằng launch lại.

Admission và parent/decision ACK đầu vào vẫn fixture như checkpoint trial
trước. Chưa nghiệm thu Goal kernel chính end-to-end, ARQ active-step drain,
phục hồi database có consumed grant, UI, source-contract reload hoặc full
regression toàn repository. Hủy child trong trial không giải phóng reservation
hay đánh dấu Goal thành công.

## Tiếp theo

Kiểm tra dump/restore populated consumed-grant ledger và quyền/source/pins sau
restore; giữ nguyên consumed fence kể cả không biết child đã start hay chưa.
Sau đó mới thiết kế/kiểm thử nối kernel Goal thật và xử lý crash/UNKNOWN toàn
tuyến. P6 chưa hoàn tất, mọi cổng chạy thật tiếp tục tắt.
