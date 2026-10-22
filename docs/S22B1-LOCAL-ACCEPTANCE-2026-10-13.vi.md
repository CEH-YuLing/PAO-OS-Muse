# S2.2B1 — Hạn mức model theo SME: local_accepted

13/10/2026, F:\PAO-ACOS. Main0054/live330, API/ready/Web200, workerhealthy.
Chỉ đóng backend model resource checkpoint; không đóng toàn S2.2B/S2/production.

## Đã triển khai

Per-SME daily calls/token reservations/concurrent slots, owner/admin policy
CAS trong host ceilings; reuse LlmAttempt, thêm resource leases không thêm
usage ledger/engine/scheduler. Atomic Workspace→quota lock→subordinate rows;
completion cùng lock. Calls failed/cancelled/unknown không refund reservations.
Deadline180s/close10s/lease240s, durable restart/expiry không resend old request.
Native inference probe cùng pool, quota deny trước decrypt/network; registered
grant/role/source/brand/Brain/publication checks vẫn giữ. Không đổi credential
stores/.env/provider transport hoặc bật integrations/Ads writes.

Tenant có policy không thể đi qua unaccounted legacy resolver khi chat accounting
tắt. Metadata model discovery/connect chưa thuộc inference quota. Legacy chưa
cấu hình policy và accounting tắt chưa instrument; coverage API báo rõ.
Chưa có quota Settings UI, chưa áp caps vào MCP/Ads queues, chưa global queue
fairness nghiệm thu. Xem [thiết kế/phạm vi](S22B1-MODEL-RESOURCE-DESIGN-2026-10-13.vi.md).

## Evidence

- Docker tái xuất hiện inaccessible dockerInference; verified processes/runtime
  socket-only directories và quarantine recoverable, giữ volumes/settings.
  Engine29.4.3 và đúng ACOS PG/Redis healthy. Không reboot/reset/reinstall.
- Prechange `.runtime/checkpoints/p0-20261013T032439-185098c2/manifest.json`:
  924source/120physical/3archives/0053, backup/restore verified.
- New corpus đầu20passed/2failed do fixture thiếu system message đúng compiler;
  sửa fixture, không nới compiler. Broad group164passed/1failed phát hiện S22A
  source check vô tình vô hiệu durable model pin khi chỉ đổi native default.
  Sửa model comparison chỉ áp management probe; registered stamp/credential/
  role/rotation/revoke fences giữ nguyên. Thêm late probe model change denial.
- Final code trước rollout170passed,25Node/runtime/SSE,TypeScript đạt. Build21/21
  đạt, giữ React Hooks warnings. Browser4passed110.80s. Không full S2 regression.
- Clone0053→0054→0053→0054 giữ119legacy row hashes/rollback schema exact. Có policy
  history thì downgrade refuse không mất rows/schema/revision. Retained dump
  `.runtime/s22b1-pre-5006e85b349a4bf7b1e30b6c91378589.dump`; chỉ drop owned clone.
- Predeploy `.runtime/checkpoints/p0-20261013T034255-dd11b207/manifest.json`:
  933source/120physical/3archives/0053; exact119business hashes/schema restore,
  primary unchanged. Guarded rollout0054 giữ old rows/counts/M2archives, không
  tự tạo policy/lease/authority, idle0 và external flags không đổi.
- Live gate đầu phát hiện route mới chưa nằm trong safe_validation/body limiter:
  extra input có thể echo marker trong422. Đã thêm redaction/no-store/body8192,
  thêm test secret-like malformed input và oversized JSON. Không bỏ assertion.
- **Final171passed/0failed/0skipped,120.74s**,4 inherited ARQ close deprecation
  warnings; có actual ARQ model authority corpus. **Final browser4passed80.78s**
  trên cùng code cuối, model/MCP/Ads/rotation/new consent/SME switch; không provider.
- Final backend binding `633a423848e0a71c7d51f73bb68993e255d89365059cda707e116db14c02e051`.
  Code-final checkpoint `.runtime/checkpoints/p0-20261013T034834-ed06b391/manifest.json`:
  933source/122physical/3archives/0054, exact121business/schema restore,
  primary unchanged. Các bảng resource mới còn0 trên main.
- Owned API/ARQ restart20340/8620; Web16176/Ollama12836. APIhealth/ready/Web200,
  workerhealthy; live330 khớp saved contract/source binding/M2replay3/3.
  Live policy/lease/ref0, auth/foreign404/422redaction/no-store đạt. Không live
  inference/probe/external writes. `.env` SHA256 giữ nguyên như trước checkpoint.

## Việc tiếp theo duy nhất

**S2.2B2:** quota admission/queued/concurrent caps và fair dispatch theo SME cho
native MCP/Meta/Google, metadata requests/legacy chưa phủ, retry/cancel/expiry/
restart/noisy-neighbor corpus. Sau đó B3 quota UI/integration, S2.3 Settings
và final S2 full regression/backup-restore. Không quay lại các checkpoint đã đạt
trừ regression thực hoặc source/authority thay đổi có bằng chứng.
