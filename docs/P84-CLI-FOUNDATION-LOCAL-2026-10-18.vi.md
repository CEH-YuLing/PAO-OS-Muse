# P8.4-A/B — Nghiệm thu nền móng CLI offline

Ngày: 18/10/2026, Asia/Saigon. Phạm vi được thực hiện: A/B của kế hoạch đã duyệt.
Kết quả: **local_accepted_offline**. Chưa có kết nối Codex/Claude/Antigravity thật.

## Đã hoàn thành

- Hợp đồng provider/scope/attempt/limits/usage, không có credential trong DTO.
- Metadata chuẩn bị cho Codex, Claude Code, Antigravity. Live dispatch luôn deny.
- Package độc lập, không import từ API/worker và không đăng ký engine mới.
- Bounded stdin/stdout/stderr, streaming sự kiện nội bộ, strict JSON/duplicate
  keys/terminal result, lỗi an toàn không phản chiếu stderr hoặc bí mật.
- Recheck callback quyền trước dispatch, trước gửi và trước từng delivery/final.
- Giới hạn byte/time/concurrency, profile busy xuyên workspace và duplicate fence
  trong instance. Không có retry/queue/runner mới, không tuyên bố crash-safe.
- Windows Job Object và POSIX process group dọn con mồ côi; timeout/cancel/cancel
  trong lúc spawn được kiểm. Parent env không bị sửa; child không kế thừa API
  keys/.env/proxy/PATH, không thực thi prompt như lệnh shell.
- Bổ sung stage `cli-foundation-offline` vào CI entry dùng chung. **Chưa chạy lại
  toàn CI hoặc hosted CI**; đây chỉ là chuẩn bị stage và unit Linux độc lập.
- ADR và master roadmap thống nhất thứ tự A/B → C → D → E → F.1/F.2 → G.

## Bằng chứng thực thi

Thư mục: `.runtime/p84-foundation-580085536c144ea397d3a0f4f439ecbe/`.

- `baseline.json`, `source-baseline.zip`: checkpoint source-only trước cập nhật
  docs/CI, sau khi đã thêm package. Không gọi là backup DB trước triển khai.
- `receipt-d0a2a5a914514e83a51807a872f393e4.json`: pass=true.
- Windows Python3.12.14 theo release pin hiện hành: **26/26 unit tests**, lặp
  ba lần, cả ba pass. Không cộng thành78 test chức năng khác nhau.
- Linux: **26/26 unit tests**, image local `44ca806807c3`, network=none,
  read-only root, user65534, cap-drop ALL, no-new-privileges, pids/memory/CPU cap.
  Chỉ bind package/test source read-only, không mount .env/home/auth store.
- Không có fail/error/skip trong bốn lượt unit cuối. Không có live provider call.
- Source giữ nguyên trong các lượt test; protected source/config/launcher và
  runtime pin/release receipt không đổi so với baseline nghiệm thu.
- Binding hiện hành giữ nguyên:
  `225ef02c99913df671fbc382f2baee3614274f130c89890fa8c700094070a22c`.
- Schema0071,153physical tables không đổi; chỉ SELECT metadata trên connection
  server-enforced read-only. Không migration hoặc restore primary.
- API health200, ready200, web200 trước và sau. Không restart dịch vụ.
- Kiểm tra tiến trình sau test: không còn test/fixture P8.4 mồ côi. Container
  test dùng --rm; không thao tác container/volume dịch vụ PAO hiện có.

## Lịch sử lỗi phải giữ

1. Lượt đầu trong sandbox treo trước async setup: Windows asyncio tạo
   socketpair localhost nhưng sandbox không cho vòng accept hoàn tất. Trace
   faulthandler chỉ tới `_fallback_socketpair`/`_make_self_pipe`, chưa chạy child
   fixture. Đã dừng đúng process test được xác minh executable/start-time.
   Lượt này không được coi là pass. Test sau chạy ngoài sandbox với audit hook
   chặn mạng ngoài, chỉ cho phép loopback nội bộ.
2. Lượt Windows đầu ngoài sandbox:22tests,21pass/1fail. Khi stderr/output flood,
   child đã chết nhưng reader bị pause giữ pipe; cleanup timeout làm lỗi thành
   `cli_cleanup_failed` thay vì output-limit. Đã sửa drain/discard pipe đồng thời
   trong cleanup, không tăng timeout hoặc nới assertion. Lượt22 sau pass;
   mở rộng thêm4tests và chạy26 theo receipt ở trên. Không xóa/ghi lại receipt cũ.

## Giới hạn và chưa hoàn thành

- Không chạy binary nhà cung cấp, không đăng nhập hoặc dùng quota thuê bao.
  Inventory chỉ xác nhận đường dẫn/hash; version/auth/inference chưa probe.
- Scope callback trong unit không thay native membership/Brain/grants/ledger.
  Chưa chứng minh queue/restart exactly-once hoặc real-provider cancellation.
- Process containment không phải sandbox filesystem/network. Chưa cho phép
  tool/shell thật, chưa chứng minh launch race-free cho binary bất kỳ.
- Không thay provider enum hoặc engine snapshot reader của backend, không tạo
  migration, không cài SDK/dependency mới. UI/launcher/Ollama chưa thay đổi.
- Không hash nội dung DB nghiệp vụ trong đợt này; schema/source guards không
  giải quyết sự cố primary drift lịch sử và không chứng nhận dữ liệu toàn thời gian.
- Không phải full backend regression2303, browser acceptance, real-data pilot,
  whole P8/S6 hoặc production. Không tự push/deploy/activate Ads/MCP/Telegram.
- G:/Javis và F:/PAO-BOS Backup 001 không được sửa. Không đọc auth store.
- Chốt commercial/hosted và Antigravity third-party OAuth chưa đạt; fixture
  offline không biến thành quyền kích hoạt thật. Xem ADR-P84-CLI-CONNECTIONS.

## Tiếp theo: P8.4-C

Đánh giá Codex binary/version/protocol trên máy trong hồ sơ cách ly, giải quyết
native grants/accounting/snapshot compatibility và OS sandbox trước inference.
Chỉ sau đủ chốt mới chạy dữ liệu mẫu qua tài khoản được phép. Không mở cả ba
provider đồng thời hoặc gỡ Ollama trước khi engine đầu tiên nghiệm thu.

## Chạy lại kiểm chứng

```powershell
. .\scripts\get_acos_python.ps1
$p84Python = Get-AcosPython (Get-Location).Path
& $p84Python -B scripts/test_p84_cli_foundation.py
& $p84Python -B scripts/check_p84_foundation.py verify --folder F:\PAO-ACOS\.runtime\p84-foundation-580085536c144ea397d3a0f4f439ecbe --linux-image 44ca806807c3
```

Mỗi lần verify tạo receipt/log mới, không ghi đè lịch sử. Image phải sẵn có;
không pull. Khi baseline nguồn/config hợp lệ đã thay đổi, không restore primary
để ép pass; lập baseline mới có phạm vi và giữ lần fail/stale để review.
