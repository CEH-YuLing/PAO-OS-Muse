# ADR P5 — Connector/MCP read-only local

## Quyết định và phạm vi

Owner chưa có MCP server: nghiệm thu local bằng fixture. Không tự chọn server,
không gửi dữ liệu hoặc credential ra ngoài, không mở M4/write/P6/stdio/code packs.
Template chỉ là dữ liệu cấu hình, không phải kết nối đang hoạt động.

API mới nằm tại `pao/modules/connectors`; UI trong Settings → Integrations.
Ba bảng `connector_connections`, `connector_secrets`, `connector_events` và cột
pin nullable của ToolCall được thêm ở migration 0034. Gateway/ARQ dùng lại claim,
idempotency và ToolAudit hiện hành; không tạo hệ thống execution thứ hai.

## Quyền và version

Discovery không cấp quyền và không chạy tool. Owner phải xác nhận server và
credential chỉ đọc, duyệt Tool ID/schema hash và bộ tham số cố định. Skill cần
validate → review → publish, allowlist phải chứa Tool ID; review ghim cả phiên
bản kết nối và manifest. Gateway kiểm tra membership, owner, workspace, Brain
ACL, Run/Skill pin và permission trước claim, trong khi chờ và trước lưu kết quả.
Client/model không truyền bộ tham số, tenant, mode hay scope thay thế khi gọi.

Schema/capability drift thu hồi grant, tăng version và huỷ call đang chờ/chạy.
Disconnect xoá ciphertext credential nhưng giữ metadata audit bất biến.
Pin/arguments/identity của connector ToolCall không được sửa bằng SQL sau tạo.
Tối đa 4 tool calls/run; idempotency key không chạy lại call đã claim.
Worker bị ngắt để trạng thái unknown, không tự retry kết quả không chắc chắn.

## Transport và giới hạn an toàn

Chỉ HTTPS domain public, port 443, path hạn chế. Không IP literal, userinfo,
query/fragment, redirect, proxy môi trường hoặc retry tự động. Mỗi TCP connection
resolve DNS, từ chối toàn bộ nếu có IP private/link-local/multicast/mapped; kết
nối numeric IP đã kiểm tra, vẫn giữ TLS hostname/SNI và certificate verification.
Giới hạn 64KiB/response, 32 tools, 3 trang, 16 SSE events, 10s/RPC, 30s/exchange.
Circuit tạm chặn 60s sau 3 lỗi. Server-driven sampling/roots/elicitation bị từ chối.
Không log lỗi/response thô của provider; audit chỉ metadata/hash, không credential.
Credential mã hoá Fernet bằng key local hiện hành; xoay bearer thủ công có row lock.

Profile được ghim **MCP 2025-11-25**, initialize + initialized + tools/list/call,
JSON hoặc SSE một response. Không tự negotiate protocol mới. Schema đóng theo
subset an toàn của Studio; tool không có outputSchema/hints read-only phù hợp bị
loại. Hints của server không thay thế quyền owner hoặc credential read-only.

Nguồn giao thức: [transports](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports)
và [tools](https://modelcontextprotocol.io/specification/2025-11-25/server/tools).

## Chưa đạt và không được suy diễn

Fixture MockTransport không xác nhận DNS/TLS/auth của một dịch vụ thật. Browser
test thật chỉ tạo draft/ngắt/purge/audit local, không discovery ra Internet.
Chưa nghiệm thu external smoke, OAuth tự refresh, stdio, plugin code installation,
đa protocol, SSE resume, remote reboot/production. Không gọi là MCP general-purpose.
LLM chưa tự gọi MCP; owner queue read thủ công từ Studio Run qua Gateway.
Endpoint legacy yêu cầu origin/SSE/session behaviour khác có thể bị reject;
phải chọn và thử server thật trước mở quyền sử dụng thường xuyên.

## Rollback

Đặt CONNECTORS_ENABLED=false, restart API/worker theo PID/start-time đã xác nhận.
Giữ bảng/lịch sử; không downgrade live hoặc retry unknown. Nếu cần rollback schema,
phục hồi checkpoint riêng trước P5 sau khi kiểm tra không có thao tác đang chạy.
