# S2.1B2b — Explicit model authority và Settings

Ngày 11/10/2026, F:\PAO-ACOS. **Trạng thái: local_accepted, đã rollout 0050.**
Checkpoint này không đóng toàn S2.1B2 hoặc S2.2/S2.3. Không dùng provider thật,
không thay flags/.env, không activate credential trong database chính.

## Những phần được triển khai

- Migration 0050 thêm đúng một bảng model_grant_activations append-only, giữ
  reference/grant B1 staged/revoked. Consent riêng cho model_inference, không
  biến read_only staged thành permission, đổi TTL, revive/rewrite history.
- Manager consent explicit + CAS/idempotency/concurrent replay/collision.
  Record chỉ xác nhận consent; expiry/revoke/config/role vẫn có thể làm deny.
- Session chọn grant_id rõ; Run giữ immutable actor/SME/brand/source/grant/
  reference/activation/revisions/expiry/capability. Không default/autogrant hoặc
  fallback từ registered credential. Model không cấp Brain/tool/Ads authority.
- Fresh recheck trước credential resolve/call/chunk/publication, cùng Brain
  editor ACL hiện có. Late result bị bỏ; không thu hồi bytes gửi hợp lệ trước
  thay đổi quyền. Không giữ transaction suốt network hoặc hứa exactly-once.
- Settings model có chọn member/brand/TTL, data-only ack và inference ack riêng,
  activate/revoke/reload; EnginePicker chọn scoped grant. Metadata-only options/
  discovery, no-store/auth/validation redaction; catalog không load ciphertext.
- Bốn API operations mới (321 tổng), 42routers giữ nguyên. Public run engine
  không xuất authority IDs/fingerprint; owned selection chỉ trả grant_id cần
  cho chooser. Không sửa adapters/auth/SDK/provider network behavior.

## Gates đã kiểm đến thời điểm viết

- Pre-change verified checkpoint0049:
  `.runtime/checkpoints/p0-20261011T144701-e5ee71c5/manifest.json`,872source/
  118physical tables/3M2archives.
- Clone0049→0050→0049→0050 đạt;117business tables hash exact, rollback schema
  equivalent, primary unchanged. Chỉ invocation-owned clone đã dọn, dump giữ:
  `.runtime/s21b2b-pre-bd37e1420e884cb08e99204cabc52620.dump`.
- 217focused passed trước bổ sung Brain guard. Lượt sau220passed/1fixturefail:
  dùng viewer thay role reader của Brain. Sửa fixture đúng schema rồi final
  **29model authority passed**, gồm four Brain cases và two real ARQ queues.
  Hai SME đều dùng grant registered; revoke A không làm B mất quyền.
- Browser realHTTP/DB một ca Settings mapping/activation/engine selection/
  SME switch/revoke/mobile đạt39.46s. Test đầu dùng selector desktop/mobile
  trùng; test sau chưa mở lại tab AI sau remount. Đã sửa locator/tab, không nới
  server authorization hoặc tăng timeout để làm pass.
- 25Node/runtime/SSE passed; TypeScript passed; production build21/21 passed.
  Build cuối sau mọi UI edits đạt21/21, còn React Hooks warnings (kể cả panel);
  không gọi build không lỗi là đã tối ưu toàn bộ hooks.
- AST8files/whitespace passed. Source binding backend đóng băng:
  `fa91ae9a5a89cb4f1c1ef5629d81183132d45bb42bdee862d57cd489192a0f8f`.
- SHA256.env không đổi:
  `5672F74189BCEF6C110D4C434E956D4F324598EE3901B88BBD56902C945FBEA7`.

Full backend trên source fa91 đã đạt **1298passed/0failed/0skipped**,1670.73s,
33warnings ARQ close deprecated;25Node và TypeScript đạt. Browser S12/S11 đạt
45.68s/27.66s. P7 đầu lỗi tại mobile errors assertion, chưa xác định được căn
nguyên; thêm diagnostics chỉ path không query và error category, không nới
assertion/timeout. Bốn lượt sau đạt35.68s/38.51s/59.29s/38.46s. Đây là lỗi
thoáng qua chưa tái hiện, không ghi thành bug đã sửa. New model browser cuối
đạt45.92s sau mọi UI edits. Các bài test dùng API/DB thật + fixture providers,
không gọi cloud model, channel hoặc mic thật.

## Rollout và phục hồi cuối

- Pre-rollout checkpoint0049: `.runtime/checkpoints/p0-20261011T155850-22f9b7a5/manifest.json`,
  888source/118physical/3archives; exact restore117business tables/schema đạt.
- Guarded0050 primary rollout đạt,117legacy rows hash exact, chỉ thêm bảng consent
  rỗng. Không tạo references/grants/audits/activation trong primary.
- Restart đúng owned API/ARQ sau idle0; PID mới2664/6984. API/ready/Web200,
  workerhealthy; live contract321/schema0050/bindingfa91 khớp, M2replay3/3.
  Discovery/options/auth/no-store/validation redaction đạt, không provider calls.
- Seal0050 `.runtime/checkpoints/p0-20261011T160327-bc5d988c/manifest.json`,
  888source/119physical/3archives; exact restore118business tables/schema đạt,
  primary unchanged. Chỉ invocation-owned restore clone được dọn; giữ dump/ZIP.
- Không dùng full1240 B1 hoặc health trước thay đổi làm evidence source mới.
  Live-provider và production vẫn pending; P7 intermittent chưa có root cause.

## Phần còn lại của S2

MCP/Meta/Google worker authority chưa nối. Native unregistered path vẫn giữ
legacy behavior; không gọi đó là cách ly provider hoàn chỉnh. Lifecycle refresh
generation/vault/key rotation/quota/noisy-neighbor và Settings toàn provider
còn S2.2/S2.3. Model panel chỉ tối đa100options/50references, có cảnh báo phân
trang; audit API chưa hợp nhất consent timestamp/history, còn checkpoint UI sau.
Cloud health không được suy ra từ activation/metadata. Chưa live-provider,
production/remote reboot/managedOAuth hoặc external write acceptance.

Sau khi tất cả gate của model đạt, đi tiếp S2.1B2c MCP theo dossier hiện hành,
rồi Meta/Google → lifecycle/quota → Settings tích hợp. Xem S2 completion register.
