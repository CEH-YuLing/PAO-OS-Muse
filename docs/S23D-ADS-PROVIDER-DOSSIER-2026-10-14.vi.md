# S2.3D — Ads Settings: provider dossier và giới hạn native

Đối chiếu14/10/2026. Settings cho native Meta/Google OAuth hiện có; không triển
khai connector mới, tenant App vault/OAuth S4, Ads writes hoặc live smoke.

## Google — nguồn chính thức đọc được

- [OAuth overview](https://developers.google.com/google-ads/api/docs/oauth/overview)
  và [OAuth internals](https://developers.google.com/google-ads/api/docs/oauth/internals):
  OAuth user flow, adwords scope, offline access và refresh token. Native giữ
  web callback/state/cookie và encrypted refresh token; không nhập Gemini key,
  service-account JSON hoặc refresh token trong form Settings này.
- [Access model](https://developers.google.com/google-ads/api/docs/oauth/access-model):
  scope không tách đọc/ghi; vai trò tài khoản và login-customer-id quyết định
  quyền. UI khuyến nghị vai trò Read-only; vẫn giữ native grant/account/brand/job
  checks. Accessible customers không phải toàn bộ manager hierarchy; cached
  account selection không tự đổi manager root hoặc đích execution.
- [API access migration/developer token](https://developers.google.com/google-ads/api/docs/api-policy/developer-token),
  cập nhật07/10/2026: access quản lý tại Cloud project, không đăng ký mới qua
  API Center cũ. Trang OAuth overview vẫn có summary nhắc token bắt buộc;
  không dùng summary đó làm hướng dẫn mới thay trang policy chuyên biệt.
  Backend hiện v25 và developer-token optional, không cần sửa header/API version
  trong checkpoint UI; fixtures kiểm đường không legacy developer-token.

App/client ID/secret/redirect và API access thuộc host Cloud project hiện tại;
quyền Ads là tài khoản người dùng trong SME. Việc provider có quyền không làm
PAO grant tự hoạt động, không vượt account pin hoặc scope read-only native.
Quota/usage PAO khác Cloud API quota/billing, không hứa có hạn mức còn lại.

## Meta — giới hạn việc đối chiếu phải giữ minh bạch

Đã thử các URL chính thức authorization, ads_read reference, get-started và
manual-login. Công cụ truy cập trả internal-error/429 rate-limit; không đọc được
nội dung hiện hành. Không thay bằng blog cộng đồng để gọi là official verified:

- [Authorization](https://developers.facebook.com/docs/marketing-api/overview/authorization/)
- [Permission ads_read](https://developers.facebook.com/docs/permissions/reference/ads_read)
- [Get started](https://developers.facebook.com/docs/marketing-api/get-started)
- [Manual login flow](https://developers.facebook.com/docs/facebook-login/guides/advanced/manual-flow/)

Vì vậy chỉ giữ contract native đã có và đã kiểm: Graph version từ host config,
OAuth URL yêu cầu đúng ads_read; URL có ads_management bị UI từ chối ở bước này.
Không nâng API version, thêm use-case/scopes hoặc kết luận App đã Review/Live.
Lỗi Facebook Login trước đây vẫn là live gate chưa giải quyết/nghiệm thu.
Trước Meta live smoke/S4 cần đọc lại official docs và xác nhận App/use-case/
business verification/review/account assignments thật, không suy ra từ fixture.

## Hợp đồng/luồng Settings không đổi backend

| Hạng mục | Hiện có / chưa hỗ trợ |
|---|---|
| Host config |Meta form chỉ single-owner/single-workspace/local; Google host settings ngoài form này. Không phải BYO App từng SME; S4 giữ riêng |
| OAuth |Start POST theo user/SME; callback exact path/origin/state/cookie/version/member recheck native. Form mở about:blank từ click trước await, bỏ opener/referrer, validate URL rồi điều hướng |
| Scopes/review |Meta profile ads_read; Google adwords rộng cần provider role + PAO gates. Không auto-review hoặc tăng scope để sửa login |
| Account selection |Meta snapshots cached tối đa50/page hiện tại; Google account cache theo generation. UI guard5000 rows là giới hạn đọc frontend, không quota provider. Chọn để xem ID, không lưu destination/grant |
| Tests/status |GET stored status/accounts/jobs không gọi provider. Không có health/probe route chung để giả lập nút Test xanh. Connected không bằng healthy/accepted |
| Expiry/rotation |Meta trả expiry; Google worker refresh ở backend và có trạng thái expired khi reauth cần. Không trả token hoặc refresh ở browser; reconnect explicit, không retry UI |
| Disconnect/revoke |DELETE purge native token/invalidate state/cancel queued-running jobs. Revoke tại provider riêng; không xóa history/restore grant cũ |
| Redirect/webhook |Native OAuth callback exact provider path, no-store cookies. Không webhook provisioning hoặc event subscription từ Settings này |
| Quota/limits |Native rate limit/admission/resources/worker fences giữ; OAuth/catalog cached không tự thành inference/probe quota mới |

URL OAuth allowlist host/path/redirect-origin/scope/state/client ID/params; không
navigation arbitrary URL, secrets query hoặc scope ghi. Browser chỉ biết start
đã mở, phải manual GET sau callback; không giả xác nhận popup đã thành công.
Đóng popup/đổi tab/abort request không thu hồi server state còn hạn hoặc hủy
callback đã chạy. Các phiên server được native disconnect/expiry/version fences
xử lý; không thêm API cancel/CAS/nonce không tồn tại hoặc retarget ý định cũ.

User không nhập secret vào chat. UI này không có password fields; chỉ quản lý
record của tài khoản hiện tại trong SME. Unknown outcome khóa provider tới manual
GET, không resend. Host config form/legacy Ads module mobile polish là checkpoint
tiếp theo; không nghiệm thu toàn bộ Settings/S2 từ component này.
