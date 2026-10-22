# PAO MCP — bản thử local chỉ đọc

Antigravity chính chủ là MCP client, tiến trình Python này là MCP server qua
stdio và chỉ gọi GET vào API PAO local. Không gọi agy/headless, Google OAuth,
model, database trực tiếp hoặc runner công việc. Không import vào backend PAO.

Hướng dẫn: `docs/PAO-MCP-ANTIGRAVITY-LOCAL-2026-10-20.vi.md`.

5 công cụ: `pao_scope`, `pao_list_tasks`, `pao_get_task`, `pao_list_sources`,
`pao_preview_source`. Phải chọn dự án/Brain và đồng ý chia sẻ dữ liệu. Không
có tool ghi/shell/Ads/API tùy ý/legacy memory hoặc tự chọn SME khác.

Phiên PAO mã hóa CurrentUser DPAPI, kiểm lại actor/membership/owner-admin và
phạm vi trước/sau đọc; ACL/trash/hash vẫn qua API PAO. Không phải token MCP
least-privilege phía server hoặc sandbox chống code độc chạy cùng Windows user.
Không dùng cho VPS/public, nhiều người dùng chung tài khoản Windows hoặc
triển khai thương mại khi chưa có lifecycle/consent/UI/hardening tương ứng.

Không cần pip install, schema migration, mở cổng hoặc thay cấu hình Javis.
Thiết lập sinh thư mục Antigravity riêng với `.agents/mcp_config.json`, không
ghi đè global config. Chưa nghiệm thu client thật chỉ từ stdio smoke.
