# S2.2B2a — Native read queues: local_accepted

13/10/2026, F:\PAO-ACOS. Main0055/live332, API/ready/Web200, workerhealthy.
Đóng native MCP/Meta/Google read-job checkpoint, không đóng toàn B2/B/S2 hay
production. [Thiết kế/phạm vi](S22B2A-NATIVE-READ-QUEUE-DESIGN-2026-10-13.vi.md).

## Kết quả

Reuse native queues/worker và authority. Per-SME daily admitted jobs/queued/running
caps, policy/CAS owner/admin; DB atomic guard/server immutable admission stamp.
Worker hết slot giữ queued và không decrypt/provider. API request replay trước
quota không double-admit. Cancel/failed/unknown giữ daily count; terminal job
không requeue/refund. Legacy rows giữ NULL stamp và old columns không đổi.
JSONnull không bị tính nhầm như MCP. Daily query dùng statement timeUTC, tránh
transaction bắt đầu ngày trước nhưng chờ lock lâu dùng nhầm ngày.

Dispatcher offer một oldest job/SME/family, không prefill sau SME đang running.
Due scheduler chia trang theo SME/skip quota-blocked, recheck trong admission.
Lost Ads worker thành failed/worker_lost_unknown, không blind resend; nguồn/
generation/status publication fences vẫn giữ. B1 model policy độc lập, không
đổi model pin/grants/secret/provider protocol/global worker parallelism.

## Evidence

- Baseline0054/live330 khớp; Docker/PG/Redis hoạt động, không cần recovery mới.
  Prechange `.runtime/checkpoints/p0-20261013T035730-e5bf96c9/manifest.json`,
  934source/122physical/3archives/0054 verified. Không sửa protected sources.
- Native đầu54passed/1failed vì test cũ mong lost-worker tự resend. Cập nhật
  contract có chủ đích sang no-blind-resend, kiểm không enqueue cả hai tick,
  attempts giữ1 và unknown error. Sau đó78focused đạt.
- Review bổ sung JSONnull-vs-SQLNULL, batch không prefill sau SME bận, statement
  day và scheduler noisy-neighbor. Broad232passed/2failed do preflight membership
  đổi grant tamper denial403 thành404; giữ adapter403, không nới authorization.
  Broad sau236passed/1failed do fixture AdEntity thiếu nguồn job; bổ sung đúng
  provenance, không bỏ DB constraint.
- **Final focused33passed31.38s; final affected238passed/0failed/0skipped207.78s**,
  6 inherited ARQ close deprecation warnings. Có actual ARQ saturated A/B Meta/
  Google, actual MCP/Ads authority ARQ corpus, race/CAS/shared pool, quota trước
  decrypt, replay/cancel/lost-worker/immutableSQL/JSONnull và25-schedule fairness.
- 25Node/runtime/SSE, TypeScript đạt; build21/21 đạt, React Hooks warnings còn.
  Browser đầu4passed/1failed do Settings có hai EnterpriseSelector cùng label;
  fixture chỉ định topbar đúng scope, không nới strict/timeout/assertions. Case
  mới **1passed22.80s**, bốn regression đã đạt cùng backend source. Tổng5case
  đạt, không quota-form UI (B3 pending). Mobile screenshot đã xem:
  `.runtime/s22b2a-browser-6ae5a4605c514aa4b34a4958f28f9111/s22b2a-mobile.png`.
- Final backend binding `83f82a7e2b0dcf31cd19de64f0bf1d166f42c5616e82b5177e5b47f780cb700c`.
  Clone0054→0055→0054→0055 giữ121legacy hashes/exact rollback schema; populated
  admitted job làm downgrade refuse không mất row/schema/revision. Primary
  unchanged. Retained `.runtime/s22b2a-pre-c260ef2b58ec4c30b82c06e58af1c812.dump`.
- Predeploy `.runtime/checkpoints/p0-20261013T044130-4514822a/manifest.json`:
  945source/122physical/3archives/0054, exact121business/schema restore, primary
  unchanged. Guarded0055 giữ old counts/columns/M2archives, không auto policy/stamp.
- Owned API/ARQ restart19192/12236; Web16176/Ollama12836 giữ nguyên. Health/ready/
  Web200, workerhealthy, live332/saved contract/binding83f/M2replay3/3 khớp.
  Live read policy/stamp0; manager/401/foreign404/422redaction/no-store đạt.
  `.env` SHA256 không đổi; Meta/Google/Ads writes/Telegram/Studio flags giữ tắt.
- Dump/checkpoint giữ private dưới runtime; chỉ drop các clone do lượt này tạo.
  Không gọi provider thật, không thử OAuth/writes/chi tiền trên business data.

## Phần chưa đạt và bước tiếp theo

**S2.2B2b metadata/probes và legacy engine coverage** là việc tiếp theo duy nhất.
MCP discovery/model connect/list/model selection và legacy unaccounted engines
chưa phủ đầy đủ. Sau B2b là B3 quota UI/integration, S2.3 và full S2 regression/
restore cuối. Không dùng238affected thay full regression toàn source cuối.

Cap là PAO logical job admission, không RPC/provider quota/billing hay cam kết
physical cancellation/global host QoS. Global Redis backlog cũ/non-read engines,
retention/aggregation scale và production scheduler/CI/VM/HTTPS có gate riêng.
Meta official quota pages chưa đọc được lần này; không suy luận quota hoặc đổi
auth/scopes/v26. Dossier ghi nguồn Google/MCP đã đọc, không claim live acceptance.
