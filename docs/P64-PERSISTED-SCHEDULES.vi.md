# P6.4 — Lịch workflow đã lưu, fixed Echo local

Cập nhật 10/10/2026. Đây là checkpoint persisted Studio schedules, không phải
toàn bộ P6. Goal runner P6.3 không được làm lại. Kết quả rollout ở cuối tài liệu.
Đây là bằng chứng checkpoint Studio trước0043; trạng thái Goal schedule backend
mới và phần UI còn thiếu đọc tại [checkpoint tiếp theo](P64-GOAL-SCHEDULES.vi.md).

## Đã triển khai

- Một lần hoặc cron số 5 trường; múi giờ IANA, DST gap bỏ qua, DST fold chọn
  lần đầu/lần sau. DOM/DOW theo quy tắc OR. Preview cũ không tạo job.
- Lịch ghim plan đã duyệt/published, snapshot và backend source binding.
  Owner/admin tạo/sửa/điều khiển; member đọc trong workspace của mình.
- Create luôn disabled. Enable là lệnh riêng; không tự backfill thời gian tắt.
  Sửa chỉ khi disabled/manual_review và execution trước đã kết thúc an toàn.
  Archive giữ nguyên audit. Version chống ghi đè; request key chống lặp lệnh.
- Ba bảng additive ở migration0042: studio_schedules (projection),
  studio_schedule_events (audit immutable), studio_schedule_slots (UTC ledger).
- Một owner `runtime.dispatch_studio_schedules.v1`, nối vào cron dispatch hiện
  có của ARQ, không tạo poller thứ hai. Report/sync/automation owners giữ nguyên.
- Transaction slot + plan mới + native start: commit cùng nhau hoặc rollback
  toàn bộ. Unique UTC slot/id cố định, restart không tạo execution trùng.
- Child vẫn chạy P6.2 fixed Echo qua Temporal/ARQ; mỗi step cần approval.
  Không gọi model/tool thật, không tự duyệt hoặc đổi Goal kinh doanh completed.
- UI tại `/automation/review` → “Xem trước lịch”: persisted panel riêng,
  preview pins + checkbox, create/enable/disable/edit/archive, xem slot/audit,
  đọc lại sau reload; lệnh lỗi chỉ retry khi người dùng chọn cùng request key.

## Quy tắc vận hành cần hiểu

`completed` của lịch chỉ nghĩa là hết lần hẹn tương lai, KHÔNG chứng minh
execution đã hoàn tất. Mở execution_id trong slot để xem workflow thật.
Tắt/archive chỉ dừng lịch tương lai, không âm thầm hủy execution đã tạo;
hủy execution bằng panel runner hiện có và chờ ACK/receipt.

Overlap cố định `latest_eligible_skip_busy`: khi child trước chưa resolved,
slot mới bị bỏ qua có audit (manual_review không coi là đã xong). Khi rảnh,
chỉ admit slot eligible mới nhất; không chạy chồng nhiều child từ backlog.
Coalesce gộp backlog; skip chỉ giữ slot còn trong grace_seconds. Batch lớn
hơn20 eligible slot hoặc missed slot cũ hơn7ngày → manual_review, không replay
vô hạn. Lịch thưa không có slot trong nhiều tuần không bị nhầm là offline lâu.
Tối đa100 schedules/workspace,10 lịch due/tick; tìm next tối đa366ngày.

Schema/spec/permission/source pin stale → fail closed. Không tự cập nhật pin
khi thay mã. Sau thay backend: tạo/duyệt plan mới theo binding mới, tắt và drain
child cũ, preview và sửa lịch. Không mở lại bằng việc sửa hash trong database.
Mất mạng không tự gửi lại POST với request key mới; cùng key/body mới an toàn.

Hai cờ mới mặc định false: STUDIO_SCHEDULE_MANAGER_ENABLED và
STUDIO_SCHEDULE_DISPATCH_ENABLED. Dispatcher còn cần đầy đủ Studio/planning/
durable/Temporal/dispatch/worker gates. Không thay `.env` để bật trên main.
Disable/archive vẫn dùng được khi manager/dispatch tắt, với ACL hiện tại.

## Gate chưa được đóng

- Bounded Goal schedules còn `unassigned`: chưa có persisted admission vào
  parent Goal runner. Không dùng standalone workflow lịch làm bằng chứng này.
- Provider/tool thật, production reboot/failover và external delivery chưa
  nghiệm thu. Meta Login vẫn hoãn. Không bật live Ads/email/Telegram.
- Không có auto-approval, arbitrary shell, ownership transfer hay retry workflow
  đã lỗi bằng cách tự tạo child mới. Owner-first preview; admin không đổi actor.

## Kiểm chứng

Tests backend có CRUD/concurrent idempotency/ACL/gates/stale pins/tamper,
dedup sau restart interpreter mới, busy/misfire, sparse schedule, rollback sau
native admission, policy DST và child Temporal/ARQ thực với history replay.
Browser acceptance dùng Web riêng và HTTP API thật trên pao_test; lifecycle
create→enable→reload→disable→edit→archive, audit và mobile390px, zero page errors.
Không tạo execution ở main hoặc tự kết nối dịch vụ bên ngoài.

`scripts/check_studio_schedule_restore.py` mặc định phục hồi populated pao_test
vào clone tên ngẫu nhiên, so hash mọi bảng, verify journal/slot/native outcome
và trigger immutable. `--migration` thử0041→0042→0041→0042 trên clone main,
giữ hash100 bảng cũ. Chỉ drop chính clone vừa tạo; dump giữ trong `.runtime`.
`--apply --manifest <path>` chỉ migrate main sau checkpoint current đã xác minh,
binding/archive/dump checksum khớp, restore so hash checkpoint với main.
Không restore đè main. Runtime/dumps không đưa vào Git hay chia sẻ công khai.

## Kết quả nghiệm thu local — 10/10/2026

- Full backend trên mã cuối: **1070passed,2skipped,23warnings,1153.08s**.
  Hai skip là ARQ real-clock opt-in; warnings là ARQ close deprecated.
  Không cộng 54focused trước đó hay lượt seed vào1070. Seed riêng1passed/7.30s
  chỉ để tạo populated restore fixture, không phải thêm ca regression khác.
- Frontend production build20pages/lint/typecheck đạt; runtime/SSE8/8.
- Browser HTTP thật đạt1scenario/18.55s; zero page errors, viewport390px không
  overflow. Fixture `.runtime/schedule-browser-0cc7f57aa797430fa1908dbbd39d9027/`.
- Populated restore:103business tables hash khớp; immutable schedule events/slots,
  một UTC slot/native completed và hai attempts được kiểm lại; main không đổi.
- Migration clone round-trip0041→0042→0041→0042 đạt;100 bảng cũ hash nguyên vẹn.
- Checkpoint trước rollout verified:
  `.runtime/checkpoints/p0-20261010T052319-24adf7f1/manifest.json`:
  763source files,101physical tables,3artifacts,0041. Bao gồm mã backend cuối;
  các cập nhật bằng chứng trong tài liệu/roadmap sau checkpoint không đổi code.
- Rollout main0042 đạt:100 bảng cũ hash không đổi; ba bảng mới đều rỗng.
  API/ready/Web200, ARQ workerhealthy, Telegramdisabled. Không tự bật Temporal.
- Live OpenAPI khớp saved contract39routers/274operations;224paths/205schemas
  cũ giữ nguyên so với checkpoint Goal UI. Source binding cuối:
  `d71815b8df29d2e5911b8dc9e539367e78ad3187c068e0d629d5a4ca160d3217`.
- Live GET xác thực manager=false/dispatch=false/model_calls=false. Main
  schedules/events/slots/Studio executions/commands/Goal executions/commands/
  events đều0. M2 archives replay qua API đạt3/3. `.env` không thay.

Đóng checkpoint **persisted Studio fixed Echo schedules local**, không đóng
bounded Goal schedules hoặc toàn bộ P6. Tiếp theo nối lịch với admission
bounded Goal hiện có; không làm lại Goal kernel/grant và không mở live gates.
