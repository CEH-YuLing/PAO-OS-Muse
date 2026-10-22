# EA3 — Ứng viên đọc phản hồi Client, chỉ kiểm thử offline

Không được gọi là connector đã hoạt động. Package này chưa được đăng ký vào
backend, pyproject, worker hoặc CLI runtime đang phục vụ Codex. Không có hàm
đăng nhập, đọc keyring/token, chạy binary, gửi prompt hay tự fallback API.

`ClaudeStream` và `AntigravityStream` nhận bytes NDJSON theo một subset giao
thức text-only đã chọn, chỉ trả kết quả sau terminal+exit0+toàn luồng hợp lệ.
Model/session phải khớp; thiếu usage giữ unknown; cache/thinking tách riêng,
không biến thành hóa đơn hoặc quota. Chặn tool/MCP/plugin, retry không được
kiểm chứng, nhiều turn, JSON sai/trùng khóa, output quá lớn, thiếu terminal,
phản hồi khác terminal và sự kiện lạ. Không chuyển dữ liệu lạ thành câu trả lời.

Parser phát hiện tool không ngăn hoặc hoàn tác tool đã chạy. Đây không phải
sandbox, network policy, authorization hay exactly-once. Không dùng nó để
chạy CLI host trực tiếp. Native admission/ledger/cancel/recovery/source-pin và
profile isolation phải được review riêng trước mọi integration live.

Không thêm file vào `packages/cli-runtime/pao_cli_runtime`: digest của package
đó đang ghim Codex thật. Không đổi registry/image/pin để “nhận” ứng viên này.

Chạy không cần DB/provider/dependency mới:

```powershell
& <Python-theo-pin-PAO> -B -m unittest discover -s packages/client-adapters/tests -v
```

Xem `docs/EA3-LOCAL-PREPARATION-2026-10-20.vi.md` để biết gate provider và lộ trình.
