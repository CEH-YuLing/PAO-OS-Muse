# S4 — Hồ sơ Meta/Google và thiết kế cấu hình theo doanh nghiệp

Đọc tài liệu chính thức16/10/2026 trước triển khai tại `F:\PAO-ACOS`.
S4.1–S4.3 là cùng milestone của master, không mở roadmap mới. Không cấp
quyền gọi tài khoản thật, quảng cáo ghi hoặc public deploy.

## Nguồn và giới hạn kiểm chứng

- Google: [OAuth Web server](https://developers.google.com/identity/protocols/oauth2/web-server),
  [authorization headers](https://developers.google.com/google-ads/api/rest/auth),
  [API access/developer token](https://developers.google.com/google-ads/api/docs/api-policy/developer-token),
  [release notes](https://developers.google.com/google-ads/api/docs/release-notes).
  Đã đọc nội dung; giữ REST major `v25`, không tự nâng phiên bản. OAuth client,
  user refresh token và quyền truy cập API của Cloud project là các lớp riêng.
- Meta: đã thử lại [manual login](https://developers.facebook.com/docs/facebook-login/guides/advanced/manual-flow/)
  và [Marketing authorization](https://developers.facebook.com/docs/marketing-api/overview/authorization/);
  trang trực tiếp tiếp tục429/không truy cập được. Đối chiếu bộ tài liệu chính
  chủ [Meta trên Postman](https://www.postman.com/meta/facebook-marketing-api/documentation/0zr4mes/facebook-marketing-api-mapi).
  Không lấy nguồn bên thứ ba thay yêu cầu xét duyệt, không xác nhận `v26.0` là
  phiên bản mới nhất hoặc mọi use case đã được duyệt. Ô API version giữ lựa
  chọn rõ ràng của quản trị viên; real OAuth/App review tiếp tục external_pending.

## Ma trận xác thực và hướng dẫn Settings

| Mục | Meta Ads | Google Ads |
|---|---|---|
| Mặc định |Ứng dụng PAO quản trị ở host, token người dùng riêng SME/actor |OAuth Client PAO quản trị host, refresh token riêng SME/actor |
| Nâng cao |App ID/Secret riêng SME mã hóa trong PostgreSQL |Web OAuth Client ID/Secret riêng SME, API version, optional developer token/manager ID riêng |
| Nơi lấy |Meta for Developers, App settings/use case Facebook Login/Marketing API |Google Cloud OAuth Clients, consent screen, Google Ads API/API access |
| Redirect |Chính xác URL callback máy chủ, HTTPS ngoài loopback |Chính xác URL callback máy chủ, không thay hostname/cổng; không nhận URL tùy ý từ form |
| Scopes |ads_read cho luồng chỉ đọc; ads_management chỉ theo chốt ghi hiện có |adwords bao gồm đọc/ghi ở provider; PAO vẫn giới hạn read-only GAQL và quyền native; ưu tiên role chỉ đọc tại Google Ads |
| State |Nonce192bit+; cookie HttpOnly/SameSite,10phút, một lần, pin app/connection/version |Tương tự, có access_type=offline/prompt=consent; phải có refresh token và scope hợp lệ |
| Quay vòng |Đổi mode/key tăng revision, ngắt mọi connection cùng provider trong SME, hủy state/job cũ |Tương tự; BYO không lấy developer token/manager ID từ host làm fallback |
| Hết hạn |expires_at/token lỗi yêu cầu kết nối lại |Refresh bằng đúng Client tạo token; lỗi401 yêu cầu kết nối lại, không chạy mutate |
| Thu hồi |Ngắt bản lưu PAO không đồng nghĩa revoke provider |Tương tự; revoke toàn provider có thể ảnh hưởng các SME dùng chung app/account, không tự gọi |
| Hạn mức |Giữ bounded response/pages/backoff; không theo paging URL có token |Giữ bounded response/GAQL/pages và tenant read quota; không hứa quota/SLA từ configured |
| Live |App review/Advanced Access/business verification tùy use case và quyền tài sản |Consent verification/API access/manager-customer quyền phù hợp; Cloud access mới có thể không cần developer token theo điều kiện provider |

Lưu ứng dụng là thao tác local, không OAuth, test provider, bật Ads hoặc cấp
quyền team. Đọc lại trạng thái Ads, mở OAuth riêng, đồng bộ tài khoản, rồi chọn
nhãn hàng/tài khoản và grant S2 hiện có. Danh sách Google accessible customers
chỉ quyền trực tiếp, không hứa duyệt toàn bộ manager hierarchy.

## Thiết kế và threat model S4

- Một config `(workspace_id,provider)` có mode/revision và encrypted envelope;
  managed không sao chép khóa host vào tenant. Audit chỉ metadata, không secret.
- Không có config là mặc định managed, không tự cấp quyền cho token legacy:
  token không có app_binding phải OAuth lại. Migration giữ dữ liệu cũ để có
  thể phục hồi; không tự nhận token cũ vào ứng dụng mới.
- Chủ SME không phải quản trị máy chủ, kể cả hệ thống mới có đúng một SME.
  API Meta host cũ mặc định410, không đọc/ghi `.env`. Chỉ giữ tương thích
  installer riêng nếu quản trị host bật rõ `META_INSTALLATION_CONFIG_ENABLED`;
  không bật cờ này trên SaaS dùng chung. Khi opt-in, các điều kiện loopback/
  single-owner/single-workspace/read-only/no-active-token-job vẫn giữ nguyên.
- OAuth state pin HMAC cấu hình (gồm SME/mode/revision/App ID/key/API/callback/
  Google manager/developer context), browser cookie và connection version.
  Consume trước exchange, không retry code nếu mất ACK; callback không in code,
  token hoặc lỗi provider có thể chứa dữ liệu. Duplicate query/state bị từ chối.
- API start/save recheck membership/User sau khi lấy lock; provider callback
  kiểm actor còn active/owner-admin. Không chuyển connection giữa actor/SME.
- Clients nhận bản config riêng, không sửa settings chung hoặc dùng ambient
  ContextVar. Worker/scheduler/action cùng resolver, source version/grant pins.
  Mỗi HTTP request giữ khóa chia sẻ SME/source qua thời điểm gọi provider;
  rotation cần khóa độc quyền. Bắt đầu sau rotation bị từ chối trước HTTP,
  không hứa thu hồi request provider đã nhận trước ranh giới thu hồi.
- Dữ liệu tài khoản/warehouse/report vẫn theo connection/version hiện có;
  quyền read-only không mở discovery toàn bộ tài sản hoặc Ads write. Lịch/
  approval cũ không tự rebind; kết quả cũ còn lưu không là quyền chạy lại.
- Form tiếng Việt, secret write-only, xóa khi lưu/đổi mode/ẩn trang/đổi SME;
  response mất ACK khóa thao tác tới đọc lại, không tự retry hoặc browser storage.

Các chốt Meta/Google/Telegram/Ads trong `.env` thật không được đổi để làm xanh
giao diện. Local fixtures phải chặn đúng transport binding của httpx, kiểm
số lần gọi, không chỉ thay package export. Kết quả fixture không là live.
