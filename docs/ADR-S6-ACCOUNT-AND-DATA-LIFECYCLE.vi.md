# ADR S6 — Vòng đời tài khoản và dữ liệu doanh nghiệp

Ngày quyết định: 16/10/2026. Trạng thái: **đã được chủ sản phẩm chốt;
đã triển khai và nghiệm thu local trọn giai đoạn ngày17/10**. Production/S6
chưa đạt; không dùng tài liệu này thay cho test hoặc receipt.

Hiện hành xem [báo cáo S6.2](S62-ACCOUNT-DATA-LOCAL-ACCEPTANCE-2026-10-17.vi.md).
Mô tả hiện trạng bên dưới là snapshot lúc ra quyết định16/10, không phải
khẳng định tính năng vẫn thiếu mã sau ngày triển khai.

## Hai quyết định đã chốt

1. Chỉ tham gia qua lời mời của chủ doanh nghiệp. Chưa có đăng ký công khai.
2. Chưa tự động xóa dữ liệu. Cho xuất dữ liệu và yêu cầu xóa với xem trước
   phạm vi, xác nhận riêng. Không tự thực thi xóa khi tạo yêu cầu.

Một người có thể thuộc nhiều SME. Thu hồi quyền SME A không khóa tài khoản,
đổi mật khẩu hay xóa dữ liệu/quyền của người đó tại SME B. Chủ SME không phải
quản trị viên máy chủ và không được xuất Brain riêng của nhân viên khác.

## Hiện trạng đã đọc từ mã nguồn

- `pao/core_api.py`: có đăng nhập, `/v1/me`, membership/context; chưa có
  API mời/nhận lời mời/quản trị nhân viên đầy đủ.
- `pao/auth.py`: JWT có hạn dùng, kiểm `User.active` mỗi yêu cầu; chưa có
  đăng xuất thu hồi phía server, thu hồi từng phiên hoặc tất cả phiên.
- `workspace_members`: vai trò owner/admin/operator/analyst/viewer; BrainMember
  có khóa ngoại ghép đến membership. Không thể xóa membership một cách mù quáng.
- Đã có xuất/backup/restore ở các phạm vi riêng. Chưa phải luồng xuất dữ liệu
  toàn SME đã lọc bí mật và giữ ACL, hay luồng yêu cầu xóa được xác nhận.
- `channels/service.py::purge_expired` hiện có cơ chế retention nội dung kênh.
  Nó không phải chính sách xóa toàn SME. Cần xử lý rõ khi áp dụng lựa chọn
  chưa tự xóa; không bật kênh thật hoặc coi retention hiện có là đã phù hợp.
  `collect()` vẫn gọi purge khi `channels_enabled=false`, vì vậy cờ này
  không phải công tắc tắt retention. Probe chỉ đếm ngày 16/10 xác nhận primary
  có 0 customer bindings; không suy từ đó rằng cơ chế retention đã được sửa.

## Thứ tự triển khai, không tạo roadmap cạnh tranh

Đây là phân rã gate S6.2 trong master, không mở milestone mới.

### A. Lời mời, thành viên và thu hồi quyền theo SME

- Owner hiện tại mới được tạo/thu hồi lời mời, chọn email và vai trò không
  phải owner. Chuyển quyền sở hữu là chức năng riêng; không nhét vào lời mời.
- Mã ngẫu nhiên mạnh, chỉ lưu hash; có hạn, dùng một lần; không đặt trong URL
  query, log, analytics hay thông báo lỗi. Chưa tự gửi email/Telegram.
- Người mới chỉ tạo tài khoản từ lời mời hợp lệ. Người đã có tài khoản phải
  đăng nhập/xác thực tài khoản đó; không cho lời mời đặt lại mật khẩu hiện hữu.
- Giao dịch nhận lời mời khóa và kiểm lại lời mời, chủ mời và workspace;
  xử lý cạnh tranh, trùng email, hết hạn, thu hồi, tái sử dụng và giới hạn số.
- Gỡ nhân viên phải xử lý Brain grants và các tham chiếu/quyền theo SME trong
  một giao dịch có audit; không tắt User toàn hệ thống. Queued worker, pairing,
  result delivery và tool invocation phải kiểm lại quyền trước thực thi.
- UI tiếng Việt giải thích vai trò, phạm vi doanh nghiệp, thời hạn, sao chép
  mã, thu hồi, xử lý lỗi; không báo đã gửi khi chỉ tạo mã.

### B. Phiên đăng nhập

- Đăng xuất hiện tại phải có hiệu lực phía server, không chỉ xóa localStorage.
- Đăng xuất mọi phiên là phạm vi toàn tài khoản, phải giải thích ảnh hưởng tới
  mọi SME. Nó khác với việc gỡ nhân viên khỏi một doanh nghiệp.
- Token không còn quyền bị từ chối sau revoke; kiểm cả refresh/relogin,
  token cũ, nhiều tab, SSE và công việc đã vào queue. Không đổi JWT secret
  máy chủ để thay cho thu hồi một người.
- Không log token/password; giữ login throttling, Argon2 và thời hạn hiện có.

### C. Xuất dữ liệu và yêu cầu xóa

- Bản xem trước nêu loại dữ liệu, SME/brand/Brain, số lượng và quyền; không
  đưa private Brain vào export chỉ vì người yêu cầu là owner SME.
- Xuất có giới hạn dung lượng/pagination, file riêng tư, thời hạn tải, audit;
  loại bỏ mật khẩu, token, secret, ciphertext kết nối, khóa mã hóa và dữ liệu
  doanh nghiệp khác. Backup hạ tầng không phải export tự phục vụ.
- Tạo yêu cầu xóa chưa xóa gì. Xác nhận phải gắn đúng preview/hash/revision,
  phạm vi và thời hạn, không chấp nhận preview cũ hoặc quyền đã đổi.
- Chưa bật job tự xóa toàn doanh nghiệp hoặc tự tắt immutable audit triggers.
  Dữ liệu kế toán/audit, bản sao lưu, unknown action, job đang chạy và dữ liệu
  cùng tài khoản ở SME khác phải được liệt kê trong ngoại lệ/điều kiện chặn.
- Chính sách retention của kênh phải được đồng bộ rõ ràng trước khi bật live;
  không âm thầm áp dụng mặc định cũ trái với lựa chọn không tự xóa mới.

## Bộ nghiệm thu bắt buộc

- Hai SME, một người chung cả hai; owner/admin/operator/viewer/outsider.
- Invite hết hạn/thu hồi/dùng hai lần/nhận đồng thời/đổi vai trò chủ mời,
  tài khoản cũ khác người nhận; không dò tài khoản hoặc rò mã/bí mật.
- Gỡ quyền A: A bị từ chối ở API/Brain/queued execution/Telegram; B còn dùng
  được. Không mất audit và không phá khóa ngoại.
- Revoke phiên hiện tại, mọi phiên, token trước/sau revoke, user inactive;
  đăng nhập lại đúng mật khẩu mới được token dùng được.
- Export không chứa dữ liệu B/Brain riêng/bí mật; vượt giới hạn bị chặn;
  preview xóa không có business write, request/confirmation không tự purge.
- Test schema/migration/restore trên DB dùng một lần; full regression,
  contract, frontend build, browser desktop/mobile và health sau rollout.

Chưa có các bằng chứng trên thì gate lifecycle giữ **implementation_pending**,
không gộp nó vào external_pending vì thiếu tài khoản quảng cáo hay VPS.
