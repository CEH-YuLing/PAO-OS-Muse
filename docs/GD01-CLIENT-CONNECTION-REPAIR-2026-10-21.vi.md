# GD01 — Sửa kết nối Client trong PAO AI, 21/10/2026

## Kết quả thực tế

Đã sửa và nạp vào `F:\PAO-ACOS`. Codex của chủ sở hữu trong PAO-Business Operating
Systems xuất hiện trong popup PAO AI: `gpt-6-astra`, nút chọn dùng được. Đã thao tác
nút Kết nối trên phiên Chrome đang đăng nhập và kiểm tra lại popup thật. Không đổi
model mặc định OpenAI API, không đăng nhập tài khoản khác hoặc cấp quyền cho nhân sự.
Lượt này không gửi yêu cầu suy luận thật, nên không chứng nhận quota hoặc chất lượng
trả lời hiện tại. Đây không phải hoàn thành toàn GD01, ba Client hay production.

| Nguồn | Tình trạng tại lần kiểm tra này |
|---|---|
| Codex | Đã nối lại hồ sơ local đã đăng nhập; PAO AI chọn được model đã ghim `gpt-6-astra` |
| Claude Code | Bộ thực thi hội thoại chưa được triển khai; tài khoản Pro/Max trước đó được người dùng hoãn |
| Antigravity | Có luồng đọc danh mục native; chưa có bộ thực thi hội thoại được nghiệm thu, chưa đạt cô lập công cụ |
| Muse | Chỉ có vị trí chờ trên UI, chưa có connector |

## Nguyên nhân và bản sửa

1. `/v1/engines` trả sớm khi có tài nguyên API dùng chung. Hồ sơ Codex cá nhân đã
   được chấp thuận bị bỏ sót. Nay hợp nhất nguồn dùng chung và nguồn Codex hợp lệ,
   không gọi provider/Ollama, không tạo quyền khi đọc danh mục.
2. Ngắt kết nối/đăng nhập lại làm đổi phiên bản hồ sơ. Quyền sử dụng cũ ghim phiên
   bản trước nên bị từ chối đúng thiết kế, nhưng nút Kết nối chưa cập nhật thiết lập.
   Nay thao tác Kết nối rõ ràng gọi dịch vụ thiết lập sẵn có cho chính tài khoản đó,
   dùng revision hiện tại, không có màn chọn nhân sự/quyền/thời hạn riêng. Metadata
   hoặc tải trang đơn thuần không kích hoạt. Nguồn cũ/lượt chạy cũ không bị sửa ghim.
3. Popup Chat nghe thêm sự kiện hồ sơ Codex/tài nguyên AI; có nút tải lại danh mục,
   liên kết cài đặt và lời giải thích riêng cho connector chưa có khả năng hội thoại.
4. Giữ nguyên mặc định, ranh giới SME/người dùng, quyền dữ liệu và công cụ. Bấm kết
   nối không chạy AI; gửi chat mới có thể sử dụng hạn mức. Mất ACK không tự gửi lại;
   lần kết nối kế tiếp đọc thiết lập trước để tránh ghi lặp. Đổi SME hủy kết quả cũ.

Chỉ model đang ghim của hồ sơ Codex được cung cấp trong luồng hiện hành. Không suy
ra toàn bộ model từ một lần đăng nhập hoặc từ ảnh Javis. Chọn model tùy ý/effort
theo từng tác vụ và nguồn Client dùng chung vẫn thuộc phần GD01 còn lại.

## Bằng chứng

- `.runtime/gd01-tests-a6c3d4c7ee7140acaedd624c34d8ac04/receipt.json`:
  **475 backend đạt**, 0 lỗi/bỏ qua. Toàn lượt có `pass=false` vì bảng
  `cli_model_connections` thay đổi đồng thời; không được gọi là lượt không đổi dữ liệu.
  Log API ghi nhận đăng nhập PAO 08:23:52Z, ngắt Codex 08:24:09Z, prepare 08:24:12Z
  và đăng nhập 08:24:15Z; hồ sơ từ phiên bản6 thành10. Giữ nguyên thay đổi, không
  phục hồi đè DB. Các bài kiểm thử của lượt này chạy trong pao_test/Redis15.
- `.runtime/gd01-tests-6f14ad239fa14cc597cd5bcc073d63c0/receipt.json`:
  **73 backend đạt**, bao gồm danh mục API+Codex, sai người dùng, stale/disconnect,
  setup đang chạy, nối lại phiên bản mới và giữ lịch sử. DB chính/schema/.env/runtime
  pin không đổi trong lượt xác minh này; không gọi provider.
- `.runtime/model-provider-tabs-frontend-1d0fc09b2118473e98055a6f97dddb8b/receipt.json`:
  **249 Node**, TypeScript/typegen và production build đạt trên source cô lập.
- `.runtime/model-provider-tabs-browser-1792571758112/receipt.json`:
  fixture trình duyệt một nút Kết nối, tái sử dụng đăng nhập, nối lại, không đổi
  mặc định, lost-ACK không lặp; dark/light, 1440/390/320; không forward backend.
- `.runtime/chat-controls-browser-1792571927895/receipt.json`:
  popup/selection đúng source Codex, bàn phím, dark/light, 1600/1024/768/390/320;
  không dịch chuyển ô chat, không forward backend/provider.
- `.runtime/gd01-installed-a9b59729128547eeb515db979f8028c0/receipt.json`:
  bản đã cài, GET-only hai SME, Codex chọn được trên browser, API/ready/Web200,
  worker khỏe, schema0075/161bảng/429operation không đổi; 3 replay archive chỉ đọc,
  hợp đồng source/live/stored khớp, hàng dữ liệu chính không đổi trong lượt này.
  Binding mới: `58d8e89eb2b7639a2ba6a9560156fe50f7878bc3b066a39895fcc5c1f64b1b43`.

Thao tác kết nối thật trên Chrome cập nhật đúng revision thiết lập Codex của chủ
sở hữu để trỏ hồ sơ đăng nhập mới. Đây là thay đổi có chủ đích qua API ứng dụng,
không phải lượt GET-only ở trên. Không sửa trực tiếp DB, không lấy/copy cache đăng
nhập hay token từ Codex/Javis, không đổi `.env`, schema hoặc cài candidate0076.

## Giới hạn nhà cung cấp và việc còn lại

Đã đọc tài liệu chính thức ngày21/10/2026:

- [OpenAI app-server](https://learn.chatgpt.com/docs/app-server): tài khoản,
  managed login và model/list; kết nối local cá nhân khác admission hosted/thương mại.
- [Claude Code authentication](https://code.claude.com/docs/en/authentication):
  đăng nhập qua luồng chính thức, loại tài khoản và sự khác biệt giữa thuê bao/API.
- [Antigravity FAQ](https://www.antigravity.google/docs/faq/): consumer login
  cho wrapper bên thứ ba không phải luồng được hỗ trợ; Google nêu lựa chọn Enterprise
  hoặc API. Không thay bằng Gemini CLI/API tính phí mà không báo người dùng.

Ưu tiên còn lại: bộ thực thi Claude theo luồng chính thức và tài khoản người dùng
khi sẵn sàng; xác định luồng Antigravity được hỗ trợ và đạt cô lập trước hội thoại;
hoàn thiện registry/model/effort theo từng nguồn và admission chia sẻ. Không bỏ kiểm
tra bảo vệ dữ liệu/công cụ để biến trạng thái đã đăng nhập thành hoạt động giả.

Backup trước sửa đã có và đối chiếu source khớp bản lưu trong
`F:\PAO-BOS Backup 001\PAO-ACOS-Backups\20261021T081213Z-bf864e7ef8054a96bcf71309c52545b7`.
Bản sau sửa được tạo riêng theo `infra/backup-storage.json`; không ghi đè bản cũ.
Backup cùng ổ F và khóa DPAPI theo tài khoản Windows không phải offsite/portable DR.
