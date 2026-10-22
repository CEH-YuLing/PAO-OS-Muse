# S2.1B2d — Provider dossier

Đọc11/10/2026. Đây là tenant read authority bổ sung, không đổi transport/auth.

- Google official [REST auth](https://developers.google.com/google-ads/api/rest/auth)
  và [OAuth](https://developers.google.com/google-ads/api/docs/oauth/overview):
  OAuth2 user grant + developer token; adwords scope; manager login-customer-id
  riêng với client customer. Giữ native v25/refresh/revoke/redaction/timeout/
  bounded GAQL; không coi adwords scope là quyền PAO writes. App/developer config
  toàn installation được thay tenant-aware ở S4, không expose server master key.
- Meta [authorization](https://developers.facebook.com/docs/marketing-api/get-started/authorization/)
  trả429 hai lần. Fallback source chính thức [SDK README](https://github.com/facebook/facebook-python-business-sdk)
  và [AdAccount source](https://raw.githubusercontent.com/facebook/facebook-python-business-sdk/main/facebook_business/adobjects/adaccount.py)
  xác nhận app/token context, app-secret-proof và tách GET account edges với POST
  mutation. README có ví dụ permission cũ, không dùng nó để mở permission mới.
  Giữ native auth/read scopes/version (v26.0 cấu hình), endpoint allowlist, paging/
  expiry/revoke/rate/limits hiện có. OAuth review/redirect/BYO dossier đầy đủ là S4.

Settings S2 chọn connection native đã cấu hình, tài khoản đã discovery thành
công, member và brand, TTL, consent chỉ đọc. Hiển thị rõ saved/configured khác
healthy/accepted, queued khác completed; không nhập credentials qua chat hoặc
auto probe/bật Ads. Revoke PAO grant không hứa đã revoke provider token.
