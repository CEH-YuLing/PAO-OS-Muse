# S2.2B1 — Hạn mức AI theo SME (backend checkpoint)

Không thay thứ tự master. S2.2B1 là phần đầu của S2.2B, không phải nghiệm thu
toàn S2.2B hay S2. B1 đạt local theo [nghiệm thu](S22B1-LOCAL-ACCEPTANCE-2026-10-13.vi.md);
B2/B3 chưa đạt. Không dùng thiết kế bên dưới thay bằng chứng kiểm thử.

## Thiết kế

- `TenantResourcePolicy` theo workspace: version/CAS, owner/admin đang hoạt động.
  Mặc định 500 lượt/ngày, 1.000.000 token dự trù/ngày, 2 lượt đồng thời. Đây là
  cấu hình local ban đầu, không gói giá SaaS. Ceilings local 10.000 lượt,
  10.000.000 token, 8 concurrent; chưa phải global host capacity planning S6.
- `LlmAttempt` tiếp tục là sổ usage duy nhất cho chat/planner/specialist/memory
  qua AccountingEngine. Tính `max(input reservation, actual input)` cộng
  `max(output reservation, actual output, output estimate)`; partial/unknown
  không coi là zero. Giá thực trả và quota thuê bao provider luôn unknown/null.
- `TenantModelLease` chỉ đặt chỗ tài nguyên. LLM lease dẫn đến đúng attempt
  cùng SME, không sao chép token ledger. Native management inference probe
  không có Run: envelope cố định96 token, usage unknown, tính cùng pool/cap.
  Request key/SME/actor/attempt/policy version/deadline không sửa/xóa/revive.
- Workspace KEY SHARE → advisory lock riêng SME → Run/Attempt/Lease. Admission
  và completion serialize cùng lock; không nâng KEY SHARE thành FOR UPDATE.
  Không giữ các transaction này trong khi chờ provider. Quota không cấp grant,
  không thay native source/brand/Brain/actor/revocation/publication checks.
- Invocation hard deadline180s, close10s, lease240s. Recovery chỉ lease có
  deadline checkpoint này; expired attempt thành failed/unknown, không replay
  hay refund. Client cancellation không cam kết provider đã dừng compute hoặc
  hoàn tiền. Legacy started attempts không deadline vẫn giữ slot bảo thủ.
- Hạ hạn mức không giết call đang chạy, không reset ngày/count, không đổi model
  pin. Admission mới bị chặn đến khi đủ slot/tokens/calls. Ngày tính UTC, không
  múi giờ chiến dịch. Lượt thất bại/hủy vẫn tính reservation đã tạo.
- Test model chặn quota trước decrypt/provider, hard timeout/output bound,
  release bằng transaction riêng; authority thay đổi không ghi health giả.
- Tenant đã cấu hình cap không đi qua legacy unaccounted model resolver khi
  chat accounting bị tắt. Đây là fail-closed, không implicit cloud/local fallback.

## API và phạm vi chưa xong

GET/PUT `/v1/workspaces/{id}/resources/models`: manager only, no-store, DTO
đóng/strict/CAS và báo rõ coverage/pending coverage. Chưa có Settings UI quota.
Metadata discovery/connect/model-selection requests chưa thuộc inference cap.
Legacy không cấu hình policy và cờ chat accounting tắt chưa được instrument;
không tuyên bố tất cả các engine/path đã đạt isolation từ checkpoint này.

Sau B1: S2.2B2 admission/queued/concurrent caps cho native MCP/Meta/Google,
đường metadata/legacy còn lại, dispatcher/noisy-neighbor/recovery; sau đó
S2.2B3 UI và nghiệm thu tích hợp quota. Giữ global local inference cap cũ;
model concurrency guard không thay scheduling fairness toàn host.

S2.3 hợp nhất Settings/audit/help/mobile và final S2 full regression/restore
vẫn là gate riêng. Không gọi provider thật, không bật business writes để test.
