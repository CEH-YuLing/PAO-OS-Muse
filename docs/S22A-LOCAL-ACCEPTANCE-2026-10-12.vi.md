# S2.2A — Lifecycle/vault/version

**local_accepted12/10/2026**, F:\PAO-ACOS. Main đã0053.
Không claim toàn S2, production hoặc real-provider acceptance đã đạt.

## Thay đổi

Append reference generation/supersedes cùng source/manager/SME. Reapply riêng
cần preview/CAS/request UUID và hai acknowledgements; bulk revoke old grant/ref
và tạo mapping mới atomic. Không sửa TTL/history/stamp của bản cũ, không copy
credential, không autoactivate hoặc repin job. Native disconnected/not-ready
không reapply; Ads phải rediscover account ở config version mới. B1 stage
không tự tạo generation; downgrade có populated generation history bị từ chối.

UI dùng form source/member/brand/account/TTL hiện có, checkbox cảnh báo thu hồi
toàn quyền bản cũ; bản mới cần consent riêng. Server master keys không ra UI.

Review phát hiện native cloud model /models và /test cho phép nonmanager;
test inference còn bypass registered fence. Đã giới hạn probes owner/admin,
registered source không dùng native test inference; key resolution dưới source
lock, release trước network, recheck actor/status/model/hash/registration trước
call/results/publication. Authority denial không poison provider health thành
error. Không đổi provider transport, giá hoặc native credential stores.

## Evidence đang có

- Pre-change0052 `.runtime/checkpoints/p0-20261012T110708-bafa1ad3/manifest.json`,
  915source/120physical/3archives, exact restore119business/schema; primary unchanged.
- Lượt lifecycle đầu6failed/167passed: fixture không rediscover sau rotate,
  helper vẫn expected_version cũ và dùng status disconnected không tồn tại cho
  model. Sửa fixture, không nới guards;17lifecycle đạt14.05s. Thêm hai-SME và
  old consent/new generation cases, group175passed171.55s.
- Probe corpus đầu1failed/56passed do EngineFailure chưa chuyển HTTP tại native
  endpoint; bổ sung adapter403 không nới fence. Final affected **247passed/0fail/
  0skip**,216.75s/8ARQ close deprecation warnings. Có actualARQ model/MCP/Ads ở
  affected suite. 25Node và TypeScript đạt.
- Binding backend frozen `42530a2d84b75846c9255738b08dfcaa6b181f04688c8632f6e4cff233f5c305`;
  generated contract328.
- Clone0052→0053→0052→0053:119legacy tables old-column hashes/rollback schema
  exact; synthetic generation2 ở clone làm downgrade bị refuse và toàn row/
  schema/revision giữ nguyên. Primary unchanged. Retained dump:
  `.runtime/s22a-pre-c7a507491e734169a5832b7d6c611c39.dump`.
- S22A/model/MCP/Ads browser4passed126.30s, gồm fixture rotation/reapply/new consent,
  native probe403 và SME switch; mobile thật đã xem. Production build21/21 đạt,
  còn React Hooks warnings kế thừa; không đổi lint/assertions để bỏ lỗi.
- Predeploy `.runtime/checkpoints/p0-20261012T120016-73045cea/manifest.json`:
  924source/120physical/3archives/0052, exact restore119business/schema và primary
  unchanged. Guarded0053 giữ old-column hashes/counts, không auto generations.
- Owned API/ARQ restart17608/18664, APIhealth/ready/Web200, workerhealthy;
  live328/saved contract/binding425/M2replay3/3 khớp, livegenerations0, no provider
  probes/external calls. `.env` hash không đổi.
- Final seal `.runtime/checkpoints/p0-20261012T120614-a2457387/manifest.json`:
  924source/120physical/3archives/0053; exact restore119business/schema, primary
  unchanged. Chỉ drop invocation-owned clone, giữ source/dump/checkpoints.

S2.2B quota/resource và S2.3 status/help/audit/paging/mobile còn mở. Master owns
order; ADR-S22 giữ thiết kế. Không mở anonymous MCP hoặc external writes.
