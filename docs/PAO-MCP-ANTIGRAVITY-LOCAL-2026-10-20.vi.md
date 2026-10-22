# PAO ↔ Antigravity qua MCP — bản thử local chỉ đọc

Ngày20/10/2026, Asia/Saigon. Target `F:\PAO-ACOS`; không sửa Javis/backup001.

## Phạm vi đã được chấp thuận

Người dùng đồng ý thử phương án Antigravity chính chủ gọi công cụ PAO qua MCP.
Không biến Antigravity thành provider cho chat/runner PAO, không bọc agy để gọi
thuê bao cá nhân, không đổi Google billing hoặc lấy token từ Javis/keyring.
Claude tiếp tục hoãn; Codex cá nhân và các pin đang chạy giữ nguyên.

## Đã triển khai và kiểm chứng local

- Package `packages/pao-mcp` độc lập, không SDK/dependency mới; stdio JSON-RPC
  tools-only, không mở listener HTTP. Hỗ trợ wire lifecycle2024-11-05,
  2025-03-26,2025-06-18,2025-11-25 trong subset này; không tuyên bố full MCP.
- `scripts/pao_mcp.py`: setup qua đăng nhập PAO chính thức, serve, check và
  disconnect. `scripts/open_pao_mcp_setup.ps1`: launcher có kiểm Python pin;
  Windows PowerShell thật đã chạy Preflight/--help exit0, không mở login.
- 5tool read-only: phạm vi hiện tại; danh sách công việc trong dự án; chi tiết
  công việc; danh mục nguồn; trích đoạn phiên bản nguồn. Không có ghi nháp,
  duyệt, tạo/xóa công việc, Ads, shell, model hoặc legacy-memory tool.
- Dự án phải được chọn tường minh. Task hiện không có brand scope nên chỉ
  cam kết ranh giới dự án/doanh nghiệp, không giả lọc nhãn hàng cho task. Chi
  tiết task chỉ từ tối đa500task gần nhất trong dự án, thiếu thì deny thay vì
  dò mọi task. Không xuất budget/input references/file/result blobs tự động.
- Brain được chọn tường minh, gắn brand_id tại lúc lưu; kiểm lại danh mục/brand
  trước và sau đọc. API native tiếp tục kiểm Brain ACL, source/origin trash,
  phiên bản/hash và trạng thái parse. Chọn là owner của SME khác không cấp
  quyền Brain cá nhân. Không lấy legacy facts. Không tự bật Brain/ingestion.
- Mỗi call kiểm actor, phiên, membership, owner/admin trước/sau; đọc lại hồ sơ
  để chặn local disconnect trong lúc đọc. Không retry/fallback khi lỗi.
- Giao thức: stdin64KiB/line, HTTP1MiB, result60KB, một request đang chạy,
  call timeout20s và HTTP4s; EOF/cancel được xử lý. Không log raw request,
  nội dung nguồn, token hoặc lỗi upstream. Stdout chỉ là JSON-RPC.
- Base API cố định `http://127.0.0.1:8100`, GET đường dẫn allowlist ghép UUID,
  không URL tùy ý, proxy môi trường hoặc follow redirect. Token không vào
  cấu hình Antigravity, argv, tool schema hay phản hồi model.

Lượt cuối nguồn cuối:
`.runtime/pao-mcp-local-c4af60babdef4b9f8a885f46b6885ecb/receipt.json`:
**28unit/stdio/DPAPI +6integration API thật trên pao_test,0fail/error/skip**.
Integration dùng native auth/session/role/two-SME/task/Brain/source, không
mock authority; HTTP unit dùng MockTransport. Không cộng với95unit EA3 cũ.

Schema chính0074/159bảng không đổi; hash `.env`, serving backend, Python pin,
dependency và transport/registry Codex giữ nguyên trong test. API/ready/Web200.
Không restart/migrate/restore primary, provider call, push hoặc deploy.
Không đo mọi hàng nghiệp vụ chính hoặc tuyên bố primary đứng yên toàn phiên.

Giữ lịch sử lỗi: lượt sandbox unit đứng ở Windows asyncio, chỉ đúng PID test
đã được xác minh/dừng; chạy ngoài sandbox đạt. Receipt6f1b2104... thất bại do
runtime phục vụ không có pytest, không cài thêm vào nó; dùng bộ test-deps đã
có riêng. Receipt46446e42... đạt trước sửa launcher/projection cuối; receipt
c4af60ba... mới là nguồn cuối. Không viết lại failure thành pass.

## Cài thử — người dùng thực hiện phần đăng nhập

1. PAO phải chạy local, tài khoản là owner/admin của doanh nghiệp muốn chọn.
   Mở `scripts/open_pao_mcp_setup.ps1`. Nhập **email và mật khẩu PAO**, không
   nhập Google password/token/API key. Mật khẩu không hiện ký tự khi gõ là
   hành vi bình thường. Không gửi mật khẩu/token trong chat.
2. Chọn một doanh nghiệp, các dự án và Brain được chia sẻ. Enter tại danh sách
   chia sẻ nghĩa là không chọn gì, không tự chọn tất cả. Phiên bản này tối đa
   20dự án/20Brain, chỉ owner/admin; không cấp quyền AI cho người khác.
3. Đọc cảnh báo: dữ liệu bạn chọn có thể được gửi tới nhà cung cấp model khi
   Antigravity gọi MCP. Không chọn secret hoặc dữ liệu không được phép xuất.
   Gõ `DONG Y` mới lưu. Đăng nhập PAO tạo LoginSession bình thường; đây không
   phải thao tác đọc thuần, còn các tool MCP chỉ đọc.
4. Setup ghi profile `.runtime/pao-mcp/profiles/<UUID>.dpapi`, mã hóa bằng
   Windows CurrentUser DPAPI. Sinh thư mục thử riêng
   `.runtime/pao-mcp/workspaces/<UUID>/.agents/mcp_config.json`. File cấu hình
   chỉ có command/argv/cwd/profile path, không bearer hoặc Google credentials.
5. Mở **đúng thư mục thử** bằng Antigravity chính chủ, dùng `/mcp` để xem
   `pao-readonly`. Nếu cần đăng nhập Google, chỉ dùng màn hình chính thức của
   Antigravity. PAO không mở/thu/chuyển OAuth cho Google.
6. Trong Antigravity, trước tiên gọi `pao_scope`; đối chiếu doanh nghiệp và
   danh sách UUID. Sau đó gọi danh sách công việc của một dự án đã chọn hoặc
   danh mục nguồn của một Brain đã chọn. Chỉ sau kết quả thực tế mới ghi nhận
   client/model acceptance. Không dùng script PAO tự gửi prompt vào agy.

**Lưu** chỉ ghi profile/config. **Check** kiểm phiên PAO, không dùng model.
**Client kết nối** cần /mcp handshake thật. **Model nghiệm thu** cần gọi đúng
tool và đối chiếu dữ liệu trong Antigravity; bốn trạng thái này khác nhau.

Kiểm profile đã tạo (thay `<UUID>` bằng giá trị setup in ra):

```powershell
. F:\PAO-ACOS\scripts\get_acos_python.ps1
$paoMcpPython = Get-AcosPython 'F:\PAO-ACOS'
& $paoMcpPython -I -B F:\PAO-ACOS\scripts\pao_mcp.py check --profile 'F:\PAO-ACOS\.runtime\pao-mcp\profiles\<UUID>.dpapi'
```

Ngắt riêng hồ sơ, giữ tombstone mã hóa và không logout Google/Javis:

```powershell
& $paoMcpPython -I -B F:\PAO-ACOS\scripts\pao_mcp.py disconnect --profile 'F:\PAO-ACOS\.runtime\pao-mcp\profiles\<UUID>.dpapi'
```

Để kết nối lại/đổi phạm vi: chạy setup mới, chọn lại; ngắt hồ sơ cũ. Không
copy DPAPI profile sang máy/user/SME khác. Không sửa profile/registry để ép pass.
Ngắt MCP không tự thu hồi LoginSession PAO trên máy chủ; có thể thu hồi đúng
phiên trong PAO. Khi phiên hết hạn, setup lại; chưa có refresh tự động.

## Lỗi thường gặp và giới hạn bảo mật

- 401/phiên hết hạn: đăng nhập PAO lại qua setup, không mint JWT chẩn đoán hoặc
  sửa SQL. Vai trò/membership/Brain thay đổi: chọn lại sau khi được cấp quyền.
- MCP không hiện: mở đúng thư mục thử, kiểm đường dẫn Python/file, reload trong
  `/mcp`. Chưa tự sửa global config hoặc đặt giả trạng thái connected trên UI.
- Nguồn chưa parse/đang trash/khác hash: xử lý ở PAO rồi đọc lại, không bypass.
- Windows khác user không giải mã được profile: tạo profile mới bằng user
  sẽ chạy Antigravity. Không dùng machine-scope DPAPI để chia sẻ credential.
- DPAPI bảo vệ dữ liệu nghỉ và tránh plaintext trong config, **không phải
  sandbox chống phần mềm độc hại hoặc native tool chạy cùng Windows user**.
  Phiên lưu vẫn là bearer PAO thông thường, chưa phải delegated MCP token có
  scope hẹp trên server. Chỉ bridge allowlist hạn chế route; không quảng bá
  rằng bearer tự nó là read-only. Chưa phù hợp shared-host/public/commercial.
- Nội dung nguồn là dữ liệu không tin cậy, không phải chỉ thị nâng quyền.
  MCP này không quản lý quyền shell/file/network khác của Antigravity; giữ
  phê duyệt native và chỉ chia sẻ dữ liệu cần thiết. Không bật skip-permissions.

## Hồ sơ tài liệu nhà cung cấp —20/10

- [Google MCP](https://antigravity.google/docs/mcp?tab=cli): stdio command/args/
  cwd và config workspace `.agents/mcp_config.json`; đây là hướng client
  chính chủ gọi PAO, không PAO dùng thuê bao làm API. Không OAuth callback,
  Google scope, webhook hay credential Google trong server này.
- [Google FAQ](https://www.antigravity.google/docs/faq/): wrapping agy trong
  ứng dụng khác không được hỗ trợ dưới consumer plan; không đóng gate này bằng
  MCP đảo chiều. Chưa bật provider Antigravity trong chat PAO.
- [MCP stdio](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports),
  [lifecycle](https://modelcontextprotocol.io/specification/2025-11-25/basic/lifecycle),
  [tools](https://modelcontextprotocol.io/specification/2025-11-25/server/tools).
- [Microsoft DPAPI](https://learn.microsoft.com/en-us/windows/win32/api/dpapi/nf-dpapi-cryptprotectdata):
  CurrentUser/UI_FORBIDDEN, không LOCAL_MACHINE; roundtrip/tamper tổng hợp đã đo.

## Chốt chưa đạt và phần sau

Local implementation/test đạt; **user setup, native Antigravity MCP handshake
và model acceptance chưa đạt** tại lúc lập báo cáo. Không dùng stdio client
test hoặc saved config làm bằng chứng Google/model thật.

Sau nghiệm thu đọc: mới thiết kế delegated-token/revoke/audit/consent UI; rồi
mới đề xuất tool lưu kết quả nháp với approval/idempotency. Chưa cấp quyền ghi,
chi tiền, gửi tin hoặc bật vòng lặp nền. Toàn EA3/S6/production vẫn chưa đạt.
