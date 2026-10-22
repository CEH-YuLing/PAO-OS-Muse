# P5 — Nghiệm thu Connector/MCP read-only local

Ngày 06/10/2026. Chỉ sửa `F:\PAO-ACOS`; không sửa source bảo vệ.
User xác nhận: **chưa có server; nghiệm thu local trước**.
Phạm vi thiết kế: [ADR P5](ADR-P5-CONNECTORS.vi.md).

## Trạng thái

**P5 LOCAL MVP đã đạt**, trong phạm vi adapter và fixture; external smoke chưa
đạt. Database local đã lên 0034, adapter bật; không tạo kết nối/credential thật.
Không đánh dấu production hoặc toàn bộ P5 hoàn tất.

## Phần đã triển khai

- Catalog template không tạo kết nối giả; owner tạo draft, credential lưu riêng
  dưới dạng mã hoá, discovery không cấp permission hay chạy tool.
- HTTPS adapter có giới hạn, pin protocol/capability/schema, namespace Tool ID;
  strict schema subset, chỉ read-only có owner grant và fixed bound arguments.
- Published Skill review ghim connector/version/schema; Gateway kiểm tra owner,
  workspace/membership/Brain/Run/Skill, worker recheck và idempotent claim.
- Circuit, timeout, cancel/revoke, purge credential, metadata-only audit bất biến;
  credential rotation thủ công serialized. Unknown không tự retry.
- Settings → Integrations có draft/test/disconnect/schema/grant/audit và manual
  queue read từ owned Studio Run. LLM không tự gọi MCP.
- Migration 0034 additive: 3 bảng và một nullable ToolCall pin; 88 ORM tables,
  231 operations, 32 routers. Hợp đồng API cũ không bị đổi.

## Bằng chứng đã đạt

| Gate | Kết quả |
| --- | --- |
| Full backend `scripts/test_backend.py` | 583/583 passed, không skip, 561.81s |
| Warning | 1 ARQ Redis close deprecation, không failure |
| Test DB | `pao_test`, Redis DB15; không truncate database local |
| Migration clone | 0033 → 0034 → 0033 → 0034, 85 bảng cũ giữ nguyên hash |
| Contract compatibility | 222 operations và toàn bộ schemas cũ nguyên vẹn |
| Saved OpenAPI | Khớp code, 88 ORM tables |
| Runtime/SSE | 8/8 passed, không skip |
| TypeScript | `tsc --noEmit` đạt |
| Production build | Thành công, 18 pages, output riêng `.pao-build-check` |
| Mock UI regression | 12 PAO routes đạt |
| Focused sau thay đổi cuối | 70/70 P5/P4/app factory, 40.66s |
| Browser P5 real API/DB | Draft/revoke/purge/audit đạt; không discovery/tool bên ngoài |
| Restore P5 fixture | 88 business tables giữ nguyên row hashes |
| Browser regressions | P4 real API/ARQ/SSE, P3 chat, P2 Knowledge đạt |
| Restore regressions | P4/P3/P2 88 business tables mỗi lượt giữ nguyên hashes |
| Live readiness sau restart | API health/ready và Web 200; worker healthy |
| Live contract/binding | Khớp toàn bộ OpenAPI; M2 archive replay 3/3 |
| P5 rollout | 0034, adapter true, actual connections 0, external smoke not_verified |

Full backend được chạy trước chuẩn hoá thứ tự lock cuối cùng của connector
completion (connection → call) để đồng nhất với revoke/circuit update. Sau thay
đổi này, focused P5/P4/app factory đạt **70/70**, 40.66s; không gộp thành full run mới.

Fixture protocol dùng httpx MockTransport, không server Internet: JSON/SSE,
timeout/malformed/large/redirect/pagination, private DNS và numeric-IP connect,
drift/flag-off/membership/revoke trước gọi (0 tools/call), revoke in-flight bỏ
kết quả, cipher/purge/audit/revision, circuit và protocol/server-request denial.

## Gate còn lại

- Readiness/live contract và replay M2 sau restart đã đạt. API root PID22968,
  worker root PID8024; chỉ stop process có PID/start-time/executable khớp và idle.
- Backend binding cuối:
  `81df73c55c6f9e145b28aec6dbde3ce16caa4e6f5e5fb9e644f9beec64ae4be6`.
- Checkpoint source + database sau rollout được tạo sau khi tài liệu đóng băng;
  xem manifest mới trong `.runtime/checkpoints`, không chia sẻ runtime private.
- **External MCP smoke CHƯA ĐẠT**: owner chưa chọn server/credential. Không tự
  nối dịch vụ hoặc gửi dữ liệu bên ngoài. Fixture không chứng minh TLS/auth thật.
- Local chưa có INTEGRATION_ENCRYPTION_KEY: encrypted credential create bị từ
  chối 503 đúng thiết kế. Browser dùng Fernet key tạm trong process test; không
  thêm key vào .env thật. Khi owner chọn server, cần tạo và backup key riêng trước
  lưu credential. Draft không credential vẫn được phép, không gọi server.
- OAuth tự refresh, stdio/executable allowlist, multi-protocol, code/plugin packs,
  SSE resume và production reboot/24-7 chưa mở; không thuộc local MVP đã chứng minh.

## Khôi phục và ranh giới

Trước P5 đã có checkpoint private:
`.runtime/checkpoints/p0-20261006T150813-f2ad142d/manifest.json`, revision0033,
553 source files, 86 physical tables, 3 artifacts, verified source/database.
Không copy/upload checkpoint private hoặc secrets. Rollback adapter bằng flag
CONNECTORS_ENABLED=false rồi restart verified API/worker; giữ lịch sử, không retry
unknown và không downgrade live khi chưa phục hồi checkpoint riêng.
M4/Ads writes/public deploy/P6 workflow execution vẫn tắt.

## Kiểm tra thủ công bằng UI

Mở `http://127.0.0.1:3200/settings` → Integrations → Connector/MCP read-only.
Catalog không có actual connection. Chỉ tạo endpoint sau khi owner chọn server;
đừng nhấn Test với URL mẫu. Hướng dẫn grant schema/hash, static arguments và
publish reviewed Skill xuất hiện sau discovery. Read không tự chạy theo LLM.

Các script tái kiểm: `test_backend.py`, `check_p5_migration.py`,
`run_p1_browser_acceptance.py --connectors`, `check_p5_test_restore.py`,
`check_p5_live.py`. Browser harness sinh key Fernet tạm chỉ cho test process;
fixture không được import trong backend production.
