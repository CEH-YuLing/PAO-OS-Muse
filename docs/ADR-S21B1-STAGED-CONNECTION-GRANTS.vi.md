# ADR-S2.1B1 — Lưu mapping/quyền bền vững, chưa bật thực thi

Ngày 11/10/2026. Target `F:\PAO-ACOS`. S2.1B gồm B1 storage và B2 worker
integration; B1 không đóng S2.1B. Master roadmap sở hữu thứ tự.

**B1 local_accepted:**172focused+32affected và full1240passed/0failed/0skip;
25Node/typecheck/build21/live317,main0049. Backup/restore/limits và seal cuối tại
[acceptance](S21B1-LOCAL-ACCEPTANCE-2026-10-11.vi.md). B2 vẫn pending.

## Phạm vi và sự khác nhau với S2.1A

S2.1A chỉ xem trước. B1 thêm3bảng và6API operations để lưu reference/grant,
kiểm eligibility local, đọc audit và thu hồi. Secret/token/ciphertext vẫn nằm
trong native provider stores; không nhân bản vault, backfill từ installation
config hoặc ngầm chọn SME/owner. Adapters/auth/transport không thay đổi nên
chưa mở managed/BYO, multi-bot, team access thực tế hay test provider thật.

Tất cả reference/grant mới là **staged**, response luôn `execution_enabled=false`.
Checker là eligibility snapshot cho phần B2, không phải lệnh chạy, approval,
worker pin, signed bearer token hay bảo đảm revoke nguyên tử trong quá trình
external call. Native runtime giữ nguyên quyền cũ cho đến B2; không tuyên bố
người được grant đã dùng được MCP/Ads/model theo quyền mới.

## Schema và quyền

- `tenant_connection_references`: workspace/kind/native source ID/provider/
  explicit manager/native version/internal source fingerprint/revision/status.
  Unique theo workspace/kind/source; native source phải đúng tenant tại INSERT
  bằng trigger truy vấn whitelist4bảng với key-share lock. Không dynamic SQL.
- Không FK cascade vào native connection: khi disconnect xóa native model row,
  reference tombstone vẫn tồn tại, eligibility deny. Đây là polymorphic
  reference có DB insert validation + server recheck, không FK luôn bảo đảm
  source tồn tại. Không tự xóa reference để rơi về legacy fallback.
- Model chưa có native manager/config version: manager phải được nhập rõ và
  bằng actor owner/admin đang apply; native version giữ null. Reference revision
  **không giả thành native credential version**. Source fingerprint nội bộ có
  ciphertext/model/status/default fingerprints; giữ engine hash fence hiện có.
- Native MCP/Meta/Google creator vẫn là manager, không transfer bởi mapping.
  User thuộc nhiều SME không tự được quản lý connection của người khác.
- `tenant_connection_grants`: reference/workspace/brand/account/grantee,
  read_only/TTL1–43200phút/expiry/reference revision/immutable request fingerprint.
  Composite FK reference và brand đúng workspace; user FK không Member FK,
  để remove membership không bị grant chặn. Recheck membership/User.active.
- `tenant_connection_audits`: immutable action/version references do server
  tạo, không body text/secret/fingerprint. Không cho UPDATE/DELETE qua DML.
  Không tuyên bố chống DBA/DDL/TRUNCATE hoặc RLS; các hạn chế đó ở ngoài B1.
- Reference/grant identity, scope, expiry, fingerprint không được sửa; chỉ
  staged→revoked và revision+1. Revoke reference thu hồi mọi staged grants;
  replay request cũ trả bản revoked, không tạo lại hoặc gia hạn.

## Apply và idempotency

Apply cần hash preview S21A hiện hành, native expected version, explicit model
manager, request UUID, TTL và `apply_data_only_ack=true`. Đối chiếu parent/
grantee/account provenance bằng server, khóa workspace/actor/native/reference.
Không chấp nhận UUID bị normalize thành doanh nghiệp khác hoặc username/name
làm tenant. Request extra secret/endpoint không được nhận; JSON8KiB/no-store/
validation không echo vẫn áp dụng tất cả routes inventory.

Unique workspace/creator/request UUID + payload fingerprint; cùng payload
retry/concurrent trả cùng grant/expiry; payload khác409. Grant không kéo dài
thời hạn qua retry. Transaction lỗi rollback reference/grant/audit cùng nhau.
Giới hạn storage100references/500grants mỗi workspace (bao gồm revoked) chống
unbounded writes; đây không phải tenant quota/budget/fairness đã nghiệm thu S2.2.

## Eligibility checkpoint (không chạy tác vụ)

Actor chỉ kiểm grant của chính mình, tenant membership active/nonviewer;
grant/ref staged/chưa expiry và version/brand/account khớp chính xác, không
wildcard. Manager phải còn active/owner-admin ở SME, native ownership/Brain
ACL và source fingerprint còn đúng. Ciphertext/config khác hoặc native source
bị xóa thì deny; không decrypt hoặc thử provider/local fallback.

MCP còn kiểm private Brain ACL **của grantee**, cùng SME/brand, không archive;
grant connection không cấp Brain permission. Ads chỉ account đã quan sát đúng
source job completed/connection/version; Meta token phải còn expiry hợp lệ.
Hai owner/SME cùng account ID không làm account grant dùng được ở SME khác.

DB source fingerprint được tính bằng PostgreSQL SHA256, chỉ hash kết quả được
load vào server rồi hash metadata; không load/decrypt raw credential value.
Fingerprints này không trả ra API/browser/audit. Hash thay đổi làm deny, không
phải auto refresh config/rotate hoặc xóa tombstone; refresh/reapply sau revoke
còn phải thiết kế trong B2/S2.2, không thay history bằng tay.

## Migration và gates

0048→0049 additive: chỉ3bảng/3trigger functions mới, không đổi row/table cũ
hoặc tự tạo mapping. Verified pre-checkpoint và clone up/down/up, exact legacy
row hash/schema rollback; DB chính chỉ upgrade sau gate clone + tests đạt.
Downgrade là clone test; không làm mất grants/audit đã sinh trên DB chính.

Tests phải gồm4provider types/two SMEs/retry/concurrent/revoke/expiry/role and
membership changes/credential changes/source delete/private Brain/CAS/DB DML
tamper/IDOR/body redaction. Không dùng snapshot check như real ARQ acceptance.

**Tiếp theo B2:** nối admit/run/job pins và fresh rechecks vào engine/MCP/Ads
queued execution trước credential resolve và trước publish; registered
connection không trở về legacy access khi grant revoked. Chọn từng adapter,
giữ native role/Brain/tool/approval fences và đọc official docs khi thay
connector/provider behavior theo AGENTS. Real network/Settings UI vẫn gate riêng.
