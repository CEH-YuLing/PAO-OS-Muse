# S2.1B2d — Meta/Google read authority

**local_accepted12/10/2026**, target F:\PAO-ACOS. Đã rollout0052,
chưa live Ads acceptance. Official provider dossier/ADR bắt đầu11/10.

Reuse native stores/client/warehouse/ARQ. Explicit ads_read consent, exact
SME/actor/brand/account/source version; historical read-only jobs giữ pin bất
biến. Registered/tombstoned source không fallback owner sync/report/action.
Native manager giữ config/OAuth/status, grantee không được probe/rotate/write.
Locks Workspace→source→job; checks trước decrypt và publication, không giữ
transaction suốt network. Report chỉ typed metrics đúng completed provenance;
null spend vẫn null. UI mapping/account discovery/consent riêng và scoped reads.

## Evidence hiện tại

- Docker tắt sau phiên trước. Start báo đúng inaccessible dockerInference;
  stop có deadline20s, kiểm executable/start-time rồi dừng đúng process.
  Giữ socket-only dirs không reparse tại Docker/run.stale-s21b2d-e3ab09f7de144cf98447ff403542da6e
  và docker-secrets-engine.stale-s21b2d-5403d61286fe47438ee7a583ab279326.
  Không xóa/reset/reboot/settings/volumes. Engine29.4.3,PG/Redis healthy.
- Test lần đầu4failed/140passed: fixture Google xóa account discovery khi
  publish empty entities; expiry test cố mutate immutable TTL. Sửa fixture,
  dùng clock giả, không nới trigger/authority. Lượt sau3failed/23passed do
  fixture fetch dùng signatureGoogle choMeta; sửa test,26passed23.94s.
- Thêm discovery authorization và old approved action denial; final affected
  group183passed/0failed/0skipped222.06s,4ARQ close deprecation warnings.
  Hai actualARQ cases đúng dispatch payload/Redis15, cùng actor/account ở hai SME:
  A revoked/cancelled, Bcompleted. 25Node và TypeScript đạt.
- Clone0051→0052→0051→0052:119legacy tables old-column hashes/schema rollback
  exact; primary unchanged; retained `.runtime/s21b2d-pre-f1429361cbb64e1eb224d439d6ebbfbb.dump`.
- Browser lần đầu thấy Meta sync chỉ chấp nhận raw snapshot dù grant đã có typed
  warehouse provenance; sửa đường grant reuse account_known, legacy giữ nguyên,
  thêm test typed account không có raw snapshot. Lượt sau28core đạt/browserfail
  do fixture Meta publish empty entities xóa account; sửa fixture phản ánh payload
  thật. Browser đạt24.64s. Ảnh mobile đầu chỉ skeleton; thêm wait nội dung thật,
  không nới assertion/timeout.
- Review transport phát hiện adapters cũ list tất cả accounts rồi lọc. Đường
  grant nay Meta GET exactaccount/Google refresh→exactcustomer search, không
  me/adaccounts/listAccessibleCustomers; legacy không đổi. MockTransport tests
  kiểm tất cả request paths, response filtering và missing Google costMicros
  giữ null.66focused đạt36.51s; final affected **186passed/0failed/0skipped**,
  158.06s/4ARQ warnings; final Ads/S12/S11/P7 browser **4passed98.30s**.
  Model/MCP browser trước đó2passed trên cùng shared UI, không gọi Meta fix
  thành model/MCP regression mới. Build21/21 và25Node/typecheck đạt; warnings
  React Hooks kế thừa còn nguyên. Mobile nội dung thật đã xem.
- Final binding `592b1fa561b5ac5300a68bb8ad888410d302bb4c17eb12762edee68a070be13c`;
  contract327 generated/live exact. `.env` hash không đổi.
- Predeploy `.runtime/checkpoints/p0-20261012T105459-0804b9c0/manifest.json`:
  914source/120physical/3archives/0051; exact restore119business/schema, primary
  unchanged. Guarded0052 giữ old-column hashes và counts, mọi authority_pin
  legacy null, no auto grants. Source backups/dumps giữ lại.
- Startup owned Ollama20576/API20288/ARQ8744/Web6828; APIhealth/ready/Web200,
  workerhealthy, live327/binding/M2replay3/3; livegrants0, no external calls.
  Meta/Google/write/Studio flags vẫn off, MCP flag trước đó giữ nguyên.
- Final seal `.runtime/checkpoints/p0-20261012T110119-a18b54d6/manifest.json`:
  915source/120physical/3archives/0052; exact restore119business/schema, primary
  unchanged. Chỉ drop invocation-owned clone, không xóa user data hoặc backup.

S2.2/S2.3 và finalfull regression chưa hoàn thành. S4 mới thay installation
app configs/OAuth thành managed/BYO từng SME; không làm việc đó trong B2d.
