# Cloud Model Settings — provider dossier

Đối chiếu14/10/2026. Đây là hướng dẫn các API key native PAO đã hỗ trợ, không
thêm SDK/provider engine hoặc đăng nhập tài khoản thật. Không có key thật trong
tài liệu. Các điểm dưới đây dựa trên trang chính thức đã mở, không chỉ search.

| Provider | Auth/phiên bản native PAO | Hướng dẫn và giới hạn |
|---|---|---|
| OpenAI | API key; Bearer, `https://api.openai.com/v1/models` | Key project với quyền phù hợp, không Admin key. List models trả metadata, không chứng nhận inference/billing. PAO giữ key mã hóa phía server, không browser storage. [API/auth](https://developers.openai.com/api/reference/overview), [Models](https://developers.openai.com/api/reference/resources/models/methods/list) |
| Anthropic | `x-api-key`, `anthropic-version: 2023-06-01`, `/v1/models` | Chọn key single-workspace. Tài liệu mới yêu cầu workspace header với key đa workspace; PAO chưa có trường này hoặc WIF/cloud IAM. Không hứa mọi credential Claude đều chạy. [API](https://platform.claude.com/docs/en/api/overview), [Authentication](https://platform.claude.com/docs/en/manage-claude/authentication) |
| Gemini | `x-goog-api-key`, REST `v1beta/models` | Key AI Studio gắn project; restrict Gemini API/môi trường server. Không đưa key vào query URL; không service-account/Vertex IAM ở form này. Danh mục native lọc generateContent, không tự inference. [Keys](https://ai.google.dev/gemini-api/docs/api-key), [Models](https://ai.google.dev/api/models) |
| OpenRouter | Bearer, `https://openrouter.ai/api/v1/models` | Key có credit limit phù hợp; metadata không xác nhận quyền inference hay credit. PAO không gọi key introspection/billing tự động. [Authentication](https://openrouter.ai/docs/api_reference/authentication), [Models](https://openrouter.ai/docs/api/api-reference/models/list-all-models-and-their-properties), [Limits](https://openrouter.ai/docs/api_reference/limits) |

## Cấu hình trong PAO

- Mỗi SME có bản lưu native riêng theo provider hiện hành; không key chung
  mặc định cho mọi SME. Owner/admin quản lý, member dùng grants riêng. Một key
  provider không tự cấp tool/Brain/Ads hoặc quyền nhãn hàng.
- Form nhập key, không App ID/App Secret. S23B không triển khai provider OAuth,
  redirect callback/webhook/refresh token hoặc app review. Những trường/quyền
  khác nếu cần phải được thiết kế riêng, không giả lập bằng ô key hiện tại.
- Lưu/đổi key gọi discovery metadata và lưu mã hóa sau guard native. Không
  đánh inference tự động; kiểm tra inference yêu cầu consent riêng, có thể
  dùng token/tiền. Registered references giữ refusal legacy probe; dùng Run
  có model grant đúng scope, không tự kích hoạt hoặc tạo Run từ form này.
- Tải danh mục chỉ bằng button và consent; focus/dropdown không network. Chọn
  option chỉ là bản nháp, bấm lưu riêng. API native kiểm source stamp qua I/O
  và actor/membership trước publication. Không tự retry unknown response.
- Metadata connect/catalogue/select gửi UUID Idempotency-Key riêng mỗi ý định,
  nonce replay bị từ chối. Default/delete/probe giữ contract hiện có, không
  tự gắn client version/nonce mà backend chưa hỗ trợ. Không gọi đây là CAS
  phân tán mới cho toàn bộ CRUD.

## Rotation/revoke/quota

Tạo replacement key ở console đúng provider, đổi tại SME đã chọn, kiểm lại
nguồn/quyền và thu hồi key cũ tại provider. PAO disconnect chỉ xóa bản lưu
native và làm nguồn cũ không dùng được; không tự gọi provider để revoke khóa.
Old pins/grants/TTL không được revive. Nếu key lộ qua chat, revoke/rotate tại
provider; không nhập lại khóa đã lộ để thử cho xanh.

Quota PAO là admission policy, không quota subscription/billing provider. UI
không scrape hạn mức/hứa đủ credits hoặc tự bypass bằng key/SME/provider khác.
Tài liệu provider/console là nơi kiểm quyền, account restrictions và hạn mức.
Các giá trị số/giá model không hardcode trong dossier hoặc form này.

## Nghiệm thu

Sources có thể thay đổi sau ngày trên. S23B chỉ kiểm local bằng fetch/gateway
giả lập; official docs không chứng minh tài khoản/key/model trên máy hoạt động.
Anthropic multi-workspace/WIF, Gemini Vertex IAM, provider OAuth, real accounts/
billing/quota và benchmark vẫn ngoài checkpoint. Custom routing theo job giữ S5.3.
