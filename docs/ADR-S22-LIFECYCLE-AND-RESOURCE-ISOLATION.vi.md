# S2.2 — Lifecycle và native scoped resource isolation đạt local

Ngày12/10/2026. Không sở hữu thứ tự riêng: master/register dispatch sau khi
S2.1B2d đạt. S2.2A đã đạt local/rollout0053 theo S22A acceptance12/10.
S2.2B1 backend model quotas đạt local13/10/0054/live330 theo
[Evidence](S22B1-LOCAL-ACCEPTANCE-2026-10-13.vi.md) và
[thiết kế](S22B1-MODEL-RESOURCE-DESIGN-2026-10-13.vi.md).
B2a native queues đạt local0055/live332 theo [evidence](S22B2A-LOCAL-ACCEPTANCE-2026-10-13.vi.md).
B3 quota UI/integration nay đạt local14/10 theo [evidence](S22B3-QUOTA-SETTINGS-2026-10-14.vi.md);
S2.3A observations cũng đạt local14/10 theo [evidence](S23A-SETTINGS-OBSERVATIONS-2026-10-14.vi.md);
S2.3B cloud lifecycle/help cũng đạt local14/10 theo [evidence](S23B-CLOUD-SETTINGS-2026-10-14.vi.md);
S2.3C MCP lifecycle/help cũng đạt local14/10 theo [evidence](S23C-MCP-SETTINGS-2026-10-14.vi.md);
S2.3D Ads lifecycle/help đạt local14/10 theo [evidence](S23D-ADS-SETTINGS-2026-10-14.vi.md);
S2.3E host lifecycle/scope đạt local14/10 theo [evidence](S23E-HOST-CONFIG-SETTINGS-2026-10-14.vi.md);
checkpoint kế tiếp là S2.3F Team/account & mobile consolidation.
13/10 B2b metadata backend đạt local0056/live334 theo
[evidence](S22B2B-METADATA-QUOTA-2026-10-13.vi.md): durable per-SME admission/leases,
MCP fresh source/actor/Brain fences, no network trong transaction và no replay/refund.
Credential payload/URL logging đạt local356affected/browser3,0056/live334 theo
[evidence](S22B2B-CREDENTIAL-PAYLOAD-2026-10-13.vi.md). Local discovery/selection
quota đạt425affected/browser4/0056/live334 theo
[evidence](S22B2B-LOCAL-DISCOVERY-2026-10-13.vi.md). Legacy unaccounted inference
đã đạt local theo [evidence](S22B2B-LEGACY-ACCOUNTING-2026-10-13.vi.md): không
policy-row exemption/queued repin/ctx bypass; accounted inference và pure knowledge
không bị bỏ. Shared admission/Memory embeddings đạt local0057/live334/189backend/
browser2+1/build21 theo [evidence](S22B2B-MEMORY-EMBEDDINGS-2026-10-13.vi.md).
Knowledge embeddings index/query nay đạtlocal0058/live334/565integrated B2b/browser2+1
theo [evidence](S22B2B-KNOWLEDGE-EMBEDDINGS-2026-10-13.vi.md). B2b native coverage
đóng local; B3 policy/usage/CAS/unknown/mobile/switch đạt local14/10.
S2.3/fullS2/global host fairness và production còn mở. Thiết kế bên dưới là
ranh giới yêu cầu; chỉ native scoped coverage được nghiệm thu, không global host SLA.

## S2.2A: credential lifecycle, không tạo vault thứ hai

Hiện B1 reference cố ý bất biến và unique theo SME/kind/source; credential
rotation/disconnect làm grant cũ mất hiệu lực nhưng chưa có cách reapply an toàn.
Không sửa stamp/history hoặc TTL để làm job cũ chạy lại.

1. Giữ bốn native encrypted stores/resolvers (model, MCP, Meta, Google). Metadata
   authority chỉ chứa identity/version/hash, không nhân bản ciphertext/token.
   Server encryption/JWT/DB/Redis keys không thành Settings của SME.
2. Append reference generation mới cho đúng source/manager. Endpoint reapply
   riêng phải preview/CAS/request UUID/ack; revoke tất cả grant/ref cũ và tạo
   generation mới trong cùng transaction Workspace→source→ref/grant.
3. Old pins/consents/audit không đổi hoặc revive; old queued tasks vẫn deny.
   Generation mới có grant/TTL/consent mới. Null brand không wildcard. Không
   chuyển manager hoặc credential sang SME khác.
4. DB trigger giữ identity/generation/parent immutable; source uniqueness theo
   generation; chỉ tạo kế tiếp nếu previous revoked đúng manager và same SME.
   B1 stage thông thường không tự mở generation hoặc fallback.
5. UI cảnh báo rotation khác PAO grant revoke và provider revoke. Chỉ manager
   reapply, grantee không được token/config/probe. Giữ SSRF/DNS/redirect guards
   native; stale callbacks/config/requests không tự tạo quyền mới.
6. Corpus hai SME, old queued pins, concurrent/CAS/replay, expiry, reconnect,
   append-only SQL, no plaintext/ciphertext/log leak, masking, SSRF/proxy.
   Migration clone/rollback + verified pre/post checkpoint và restart/live.

## S2.2B: quota/resource guard theo SME, tái sử dụng ledger/queues

Native LlmAttempt đã tách estimates/reserved/actual và unknown usage, nhưng
per-run budget không thay per-SME limit. Global local inference cap hiện có
không đồng nghĩa fair resource isolation giữa SMEs.

1. Policy mỗi SME có version và host ceilings; owner/admin chỉ cấu hình trong
   ceiling. Không quota/budget của SME này bằng quota của SME khác, không ghi
   provider price/token quota như số tiền thực hoặc quota subscription.
2. Atomic admission/reservation theo Workspace trước subordinate locks; reuse
   LlmAttempt/ToolCall/native sync jobs. Bounded concurrent/queued call caps,
   daily reservations/calls và conservative unknown accounting. Không ledger/
   scheduler/provider engine thứ hai, không wildcard scope.
3. Ledger sum max(reservation,reported actual) khi thiếu usage; unknown không
   tính zero hoặc tự refund money. Cost chỉ estimate có pricing provenance;
   budget PAO không cam kết provider billing đúng mức estimate.
4. Bounded leases/release/cancel/restart recovery dựa trên durable state; không
   giải phóng slot để gửi lại blind request có kết quả unknown. Global local
   cap giữ nguyên, thêm SME admission fairness bằng queue/cap hiện có.
5. Hai SME tranh nguồn lực: A hết quota/B còn dùng được; concurrent reservation
   không vượt limit; deny không gọi provider; retry không double reserve;
   cancel/expiry/lost-worker/version change/publication/unknown usage đạt.

Sau A và B mới S2.3 hợp nhất status/help/audit/paging/mobile. Full backend,
runtime/SSE/build/browser/live binding/contract và exact restore là final S2
gate; các nhóm test riêng không thay final gate. OAuth thật/S4 và production
S6 là nghiệm thu riêng, không ép mở anonymous/external writes để làm xanh S2.
