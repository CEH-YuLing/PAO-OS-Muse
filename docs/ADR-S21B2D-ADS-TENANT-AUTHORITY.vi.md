# S2.1B2d — Meta/Google read authority

Implementation plan11/10, local_accepted12/10 theo S21B2D acceptance. Reuse native encrypted stores,
clients/warehouse/ARQ; không đổi OAuth hoặc bỏ guard app installation trước S4.
Provider dossier đọc official Google auth, Meta official SDK (docs429).

Consent dùng connection_read_activations, capability ads_read, kind Meta/Google.
Selected grant exact SME/actor/brand/account/source/version. Chỉ historical
read sync và typed warehouse report; không list all remote accounts, không tools,
không actions/writes/OAuth/config. Native owner còn quản lý kết nối. Registered
source deny legacy sync/schedule/report/action path, kể cả tombstone/expiry.

Sync jobs có authority pin append-only (null giữ legacy history). No repin.
Worker lock Workspace→connection→job, fresh authority trước decrypt; release
transaction trước network; fresh check trước publish. Account provenance lấy
completed discovery đúng source/version; không account ID toàn cục. API version
pin vẫn native. Revoke/rotation/membership deny queued; late result discarded.

Gates: two SME same account/actor, staged/model/MCP grant không Ads, foreign
scope/actor/pin tamper, expired/source rotate/manager/grantee/revoke, queued
no-decrypt, late discard, idempotency, immutable DB pins, existing regressions,
actual ARQ, browser, clone up/down/up, backup/restore/live contract.

OAuth/BYO credentials, remote live read và production vẫn gate S4/S6; fixture
không xác nhận quyền provider thật. S2.2 và S2.3 vẫn phải nghiệm thu riêng.
