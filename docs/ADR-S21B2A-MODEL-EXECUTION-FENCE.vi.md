# ADR-S2.1B2a — Hàng rào model trước kích hoạt authority

Ngày11/10/2026, target `F:\PAO-ACOS`. B2a là checkpoint model enforcement-only,
không đóng S2.1B2/B2 hoặc toàn S2. Mọi grant B1 tiếp tục staged/non-executable.
Master roadmap sở hữu thứ tự, không triển khai thêm MCP/Ads hoặc auth/transport.

**B2a local_accepted:**190focused+81affected (nhóm có test trùng), final29model
corpus/real ARQ2cases,25Node/typecheck/build21 và3browser đạt; live317/0049/M2replay3/3.
Backup/restore/source seal và giới hạn tại [acceptance](S21B2A-LOCAL-ACCEPTANCE-2026-10-11.vi.md).

## Quyết định

B1 apply có `apply_data_only_ack`, không phải sự đồng ý cho nhân viên gọi model
hoặc dùng token. Không dùng eligibility=true, preview hash, owner/admin, hoặc
grant read_only staged làm authorization. Trước thiết kế activation rõ ràng,
mọi native model connection có reference cùng workspace/source bị fail-closed:
`engine_connection_authority_not_activated`. Bao gồm ref/grant revoked, expired,
manager đổi role và native source deleted; không rơi về quyền legacy.

Không auto mapping hay thay credential. Native connection chưa đăng ký vẫn giữ
legacy behavior/tenant checks để không làm gián đoạn toàn hệ thống. Đây không
là multi-SME credential isolation toàn provider đã được nghiệm thu.

## Admission và pin

- Default/choose cloud dùng projection metadata, kiểm reference trước load
  ciphertext; không decrypt nếu deny. Missing default nhưng workspace có model
  reference cũng deny, không ngầm chọn Ollama sau xóa native source.
- Resolver legacy không có actor/source pin bị chặn nếu SME có bất kỳ model
  reference. Đây là chính sách bảo thủ để không chọn default khác lúc retry.
- Explicit chọn Ollama/knowledge vẫn được phép và giữ loopback/privacy guards;
  đó là chọn rõ, không phải tự fallback từ cloud bị thu hồi.
- Run cloud mới lưu immutable `connection_authority` trong engine snapshot:
  `s21b2a-legacy-model-fence-v1`, mode legacy_unregistered, actor/workspace/brand/
  source. Không có active grant ID/revision vì chưa có executable authority.
  Snapshot có digest và DB immutability hiện có; public DTO không xuất pins.
- Snapshot cũ thiếu pin giữ nguyên; worker vẫn kiểm reference mới, không repin
  completed history hoặc sửa source/binding/archives bằng tay.

## Worker và xuất kết quả

- Trước resolve: kiểm scope/native membership/connection status/ciphertext hash.
  Source hash query tính trong PostgreSQL, không load credential vào callback.
- Wrapper kiểm fresh trước/sau plan/extract, trước stream và mỗi chunk/cuối
  stream. Pinned cloud Run kiểm actor/brand/active member nonviewer; resolver
  legacy không có actor pin giữ access checks/poll hiện có của caller, không
  được coi là grant-scoped runner. Không cấp Brain hoặc tool permission.
- Runtime kiểm lại trong transaction trước plan, specialist result, response
  delta và completed; Studio publication tương tự. Memory legacy kiểm trước
  resolver và trước store, không retry lỗi authority/source-change sang key khác.
- Workspace KEY SHARE giữ đến commit admission/publication; B1 apply/revoke
  dùng Workspace FOR UPDATE. Memory publish khóa Workspace trước owner/job
  để không tạo chu trình lock Workspace→User với mapping.
- Không giữ DB transaction suốt network. Không thể rút lại prompt/bytes đã gửi
  hợp lệ trước khi mapping/role/config đổi. Gate trước/sau call không phải native
  provider cancel, exactly-once hoặc revoke nguyên tử qua network. Kết quả muộn
  bị bỏ; phần response đã xuất hợp lệ trước đổi quyền có thể giữ với statusfailed.

## Giới hạn và checkpoint tiếp theo

Không có activation endpoint/state, grant-to-job routing, UI grant chooser,
managed/BYO app, vault/quota mới, MCP/Ads worker fences hoặc remote acceptance.
Không thêm bảng/migration; schema0049 và317operations giữ nguyên. Chỉ đổi
internal model resolver/runtime/memory/studio và tests; provider adapters/auth/
SDK/URL/scopes không thay đổi, không có provider call/dossier mới trong checkpoint.

**B2-model activation/pins kế tiếp:** manager phải đồng ý rõ cho từng grant;
permission/capability/scope/expiry được pin vào run và kiểm lại khi worker gọi.
Không biến staged thành active tự động. Thiết kế additive migration/rollback
trước đổi state, chống revive/replay/widen scope và giữ lịch sử old engine pins.
Không coi model inference permission là quyền tools/Ads/post/email. Sau model
authority, nối từng adapter MCP/Ads, đọc official docs khi đổi connector behavior.
