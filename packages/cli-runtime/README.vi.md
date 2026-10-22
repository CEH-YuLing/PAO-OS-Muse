# CLI PAO — nền móng A/B và candidate C

Package độc lập, chỉ dùng thư viện chuẩn Python 3.12+. Chưa được cài vào backend
đang phục vụ. Nền móng A/B không đổi; C bổ sung parser/preview, worker Codex và
transport Docker dùng image/profile riêng. Backend candidate tích hợp chúng vào
quyền và LlmAttempt hiện có; không thêm business runner ARQ/Temporal thứ hai.

`CliRequest` gắn provider với workspace/actor/brand/connection/profile/device và
một attempt ID. Đây là ngữ cảnh cần kiểm tra, không phải chứng nhận quyền.
`FixtureTransport` chỉ chạy `_fixture.py` của package, bằng Python đang chạy,
không nhận executable/argv/env tùy ý. Cả ba provider chỉ có metadata chuẩn bị.
`external_dispatch()` luôn từ chối; không có biến môi trường bật ngầm.

Giới hạn: input/output/line bytes, thời gian, số profile đồng thời và số attempt
ghi nhớ. Callback quyền bắt buộc trước gửi và trước trả nội dung. Stderr không
được phản chiếu. Usage thiếu là `None`, không phải 0 đồng hay quota còn lại.

Windows dùng Job Object; POSIX dùng process group. Fixture chờ stdin cho tới
khi được gắn containment. Dọn cả hậu duệ khi leader đã thoát, timeout và cancel.
Không dùng tên tiến trình hoặc taskkill theo PID để dọn cây.

**Đây là quản lý vòng đời tiến trình, không phải sandbox filesystem/network.**
Fixture không dùng tài khoản, mạng ngoài hoặc DB. Đây không phải chứng nhận
cách ly cho CLI thật. Thử Codex trực tiếp của operator đã đạt riêng18/10; việc
này không cho phép backend dùng home/token cá nhân hoặc chia thuê bao ngầm.
Profile/cwd riêng không chứng minh cách ly SME. Windows provider launch phải có
biện pháp gắn containment không có race, filesystem/network sandbox và kiểm thử
riêng trước kích hoạt; handshake của fixture không áp dụng cho binary bất kỳ.

Duplicate fence chỉ có hiệu lực trong một instance/event loop và bộ nhớ hiện tại.
Sau restart không có bảo đảm exactly-once. Khi tích hợp phải dùng ledger/grants/
accounting/dispatch hiện có của PAO; không dùng fence này thay cho database.

Chạy offline từ gốc checkout:

```powershell
. .\scripts\get_acos_python.ps1
$p84Python = Get-AcosPython (Get-Location).Path
& $p84Python -B scripts/test_p84_cli_foundation.py
```

Windows asyncio cần socketpair localhost; bộ test cho phép loopback nội bộ và
từ chối mạng ngoài. Sandbox chặn cả loopback sẽ treo trước khi vào test async;
không được coi là test pass. Không đọc hoặc sao chép auth store của Javis.
