# S2.3E — Host-config Settings lifecycle/scope: local accepted

14/10/2026, `F:\PAO-ACOS`. Chỉ form host App hiện có. Không sửa native backend,
schema/contract hoặc .env/secret/flags thật; không provider/OAuth thật, restart
API/worker, Ads writes hoặc deploy. S2.3/finalS2 còn mở.

## Thay đổi và ranh giới

- MetaAppSettings sở hữu raw HTTP lifecycle, synclock/epoch/abort/deadlines
 15s GET/30s PUT. Không double-submit trong cùng panel hoặc publish response
 cũ sau actor/SME/role change. Wrapper dùng key host namespace; bỏ reload GET
 không sử dụng ở parent, không biến parent observations thành dữ liệu mới.
- Status profile đóng9 fields với installation_local, booleans thật, HMAC
 revision64hex, App ID/version/callback đúng native profile. Missing/truthy
 flags/secret phản chiếu/tenant scope không tạo form có thể lưu. Đây là UI
 validation, không thay server authorization hoặc bảo đảm provider credential.
- Native save revision/CAS/file lock/atomic replace/DACL/key preservation giữ
 nguyên; không thêm nonce hoặc persistence engine/vault mới. PUT chỉ gửi App ID,
 version, callback, revision và optional secret; không input master key/flags.
- Password/bản nháp clear trước request, validation lỗi, refresh, failed response,
 pagehide/hidden-tab hoặc context change. Đổi App ID bỏ secret của App trước;
 mọi field edit bỏ consent. Empty password chỉ giữ key cùng App ID; đổi App
 hoặc chưa có key cần secret mới. Không trim secret âm thầm, storage/URL/log
 hoặc hứa zeroize bản sao JS/network. noValidate dùng helper để lỗi local cũng
 clear draft, không để browser validation chặn submit handler và giữ secret cũ.
- Lost response/error bỏ snapshot/form, khóa save tới manual GET; không resend
 hoặc tự lấy revision mới rồi lưu lại. GET khi request cũ còn chạy chưa chứng
 minh kết quả cuối. Stable help cho CAS/busy/readonly/scope/env override/
 active token/OAuth/job/key-invalid; unknown errors không echo text riêng tư.
- Nêu rõ host App khác connection tài khoản trong SME và BYO App S4. Native
 single-owner/single-workspace/local guard giữ nguyên, nhiều SME form bị từ
 chối; admin/operator không có host form. Không tự disconnect/cancel OAuth/job,
 thay encryption key, restart hoặc đổi flag để vượt gate. Google/Telegram không
 có form secret host giả được thêm ở checkpoint này.
- Readonly/runtime restart gates là server facts: form khóa khi effective
 write/autopilot true; persisted config khác runtime => cần quản trị viên nạp
 API/worker, không tự gọi OAuth hoặc đổi provider status. Native save có thể bật
 META_ENABLED và đặt write/autopilot flags false sau consent, được ghi rõ.
- Loopback request ở native API không tự chứng minh browser remote an toàn
 khi qua proxy. Đây vẫn installation-local profile, không production security
 acceptance hoặc quyền quản trị host cho mọi SME. Tenant-owned app vault,
 public-host admin authorization và OAuth config rotation S4/S6 vẫn gate riêng.
- Đã thử đọc lại Meta official manual-login/basic-settings ngày14/10; nhận429/
 inaccessible, không giả official verified. Không đổi API/version/scopes/auth;
 giữ [dossier và live gates](S23D-ADS-PROVIDER-DOSSIER-2026-10-14.vi.md) trước S4.

## Kiểm chứng

- **26 passed**,149.03s,0skip:22 native Meta App config tests +4 HTTP browser
 (2 S23E host/scope, S23D Ads lifecycle, S23A observations). Không full backend;
 native tests bao gồm3 test mới write/global-autopilot/meta-autopilot từ chối
 PUT409 và không đổi temp file, ngoài ACL/CAS/encryption/DACL/active guards.
- Host browser dùng native API/CAS/atomic temp .env, pao_test/Redis15. Invalid
 secret0PUT; burst submit chỉ1 accepted PUT rồi response lost; manual read;
 same-App empty password giữ secret; changed-App không có secret bị chặn
 local; direct other-tab native save làm stale UI PUT409, không overwrite;
 hidden event bỏ password/version/consent; malformed flag200 và private GET
 failure bỏ snapshot/no echo; readonly true khóa fields/save; mobile recovery.
- Đúng3 UI PUT (2accepted/1stale) +1 direct concurrent-tab PUT trong fixture.
 Temp file cuối App123/versionv26.2/key fixture mới; giữ original encryption
 key/unrelated setting, SAFE_FLAGSfalse. File thật .env hash trước/sau không đổi.
 OAuth start vẫn409 meta_app_restart_required; Meta transport bị forbid.
- Scope browser có2 SME: owner host GET409 form0/password0, delayed GET sau
 switch sang operator không publish, return owner vẫn gate deny,0mutation.
 Không nới counts/role/loopback/private credential boundary để làm xanh.
- Host console0React/hydration/unknown errors,3expected HTTP failures; secret
 không DOM text/browser storage/API response/log. Reports/screenshots:
 `.runtime/s23e-host-browser-3c7f955607d94f07bddfa1563bf43126/` và
 `.runtime/s23e-scope-browser-8299513912e44ca7b908331627a64039/`.
 Screenshot đã xem; mobile interaction/no overflow đạt. Global composer overlay/
 full Settings mobile polish còn F, không full UX/mobile-device acceptance.
- **77 Node/runtime/SSE passed**,0skip (71 baseline+6 host helpers). TypeScript
 trước browser đạt; lượt đồng thời browser sau đó gặp generated-cache TS6053,
 không lỗi source. Chờ browser kết thúc, production build21/21 tái sinh cache,
 rồi final standalone TypeScript đạt. Không sửa tsconfig/disable lint để che
 race; từ đây không chạy typecheck cùng dev browser cache. Warnings cũ còn.
- Installed GET-only9/9 snapshots/0058/live334/binding
 `c136c3aa3f11a5f582fa007f5a5820f6b3d1e68ac5f64ce72cbd5cf01d6b72a9`
 giữ nguyên; native connection hashes/.env không đổi trong live check. API/
 ready/Web200, ARQ workerhealthy, Telegram bridge disabled, không provider calls.
- Source+DB seal sau docs ở .runtime/checkpoints; exact restore clone0058/
 125physical/124business/3archives so row hashes/schema equivalence/main unchanged.
 Giữ source/dump backup, chỉ bỏ clone của invocation; không Git init/commit/
 push/migration hoặc public deploy. Không thay docs để thêm path sau seal.

## Tiếp theo duy nhất

**S2.3E local_accepted; tiếp theo S2.3F — Team/account & mobile consolidation.**
F là phần team/account/mobile đã mở của S2.3: rà lại thông tin account cá nhân
vs SME/role/grants và trải nghiệm Settings desktop/mobile; giữ native permissions,
không tự cấp quyền/invite/revoke hoặc nâng sang tenant App S4. Sau F mới full
integrated S2 regression/release gate, không bắt đầu lại các checkpoint đã đạt.

Chưa Meta login/App Review/provider health, Cloud quota/billing, BYO tenant app,
public admin security, global host fairness hoặc production reboot/HTTPS. Local
form password/CAS tests không đóng các gate đó và không hoàn tất toàn bộ S2.
