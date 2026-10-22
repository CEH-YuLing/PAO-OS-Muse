# Cấu hình Meta App trong Settings — 07/10/2026

Phạm vi: F:\PAO-ACOS, bản cài local một workspace/một owner. Không sửa source
F:\Apex\apex. Không đăng nhập OAuth hoặc gọi Meta trong checkpoint này.

## Sử dụng

1. Đăng nhập PAO bằng owner, mở Settings → Integrations → Cấu hình Meta App.
2. Nhập App ID, phiên bản Graph API được App hỗ trợ và App Secret mới.
   Secret là password input hỗ trợ dán; để trống giữ nguyên khóa hiện có.
   Đổi App ID hoặc cấu hình lần đầu phải cung cấp secret.
3. Callback phải khớp địa chỉ đã đăng ký trong Meta. Nút “Dùng địa chỉ PAO
   đang mở” lấy host/cổng hiện tại; không tự đăng ký URI bên Meta.
4. Xác nhận phạm vi bản cài và bấm Lưu Meta App chỉ đọc.
5. Nếu báo cần nạp lại, khởi động lại API/worker khi không có job đang chạy,
   rồi Tải lại cấu hình. OAuth bị backend chặn khi cấu hình UI chưa được nạp.
6. Sau đó mới đăng nhập Meta bằng nút Kết nối. Sync account/kỳ cần được chọn
   riêng; lưu App không đồng nghĩa connector đã được nghiệm thu.

Nhiều máy truy cập cùng một PAO server dùng chung cấu hình server. Mỗi máy tự
host PAO riêng phải cấu hình riêng và đăng ký callback tương ứng; không copy
.env qua bản source chia sẻ. Không hứa OAuth HTTP local sẽ được Meta chấp nhận
cho mọi App; phải kiểm chứng thực tế. Không tự mở tunnel hoặc deploy công khai.

## An toàn và giới hạn

- Hai endpoint GET/PUT /v1/integrations/meta/app-config yêu cầu JWT và owner.
  Vì .env dùng chung server, từ chối bản cài nhiều workspace hoặc nhiều owner;
  không cho workspace admin/operator sửa cấu hình toàn hệ thống.
- PUT chỉ nhận client trực tiếp loopback. Reverse proxy/triển khai remote cần
  gate quản trị host riêng; không coi kiểm tra loopback là bảo vệ đầy đủ khi
  proxy có thể che địa chỉ client. Chưa nghiệm thu remote production.
- Secret không có trong response/error/OpenAPI example, không hiển thị hint,
  không dùng localStorage/sessionStorage. Validation lỗi được redaction và body
  giới hạn 8 KiB. Request tracing hiện có không ghi body/header/query.
- App Secret lưu plaintext trong .env riêng trên host theo cơ chế hiện có;
  không tuyên bố secret trong .env được mã hóa. Token Meta trong DB vẫn Fernet.
  Giữ nguyên khóa mã hóa hiện có, không rotate ngầm. Khi chưa có, tạo khóa mới
  local; key lỗi thì dừng. Không lưu secret vào Git/docs/checkpoint source.
- Ghi atomic, giữ permissions/DACL file Windows, lock chống hai PUT đồng thời,
  revision HMAC để từ chối form cũ. Không tự xóa lock còn lại sau crash.
- Chặn đổi App khi còn token, job sync hoặc OAuth state chưa hết hạn. Phải ngắt
  kết nối/chờ việc hiện tại kết thúc; không âm thầm vô hiệu hóa token.
- Không chấp nhận biến môi trường ghi đè các trường Meta khi lưu từ UI.
  Quyền ghi/Autopilot phải đang tắt; saved flags đều false, chỉ Meta read enabled.
- Không tự restart, OAuth, sync, Telegram hay gọi provider sau Lưu. Không thay
  schema database; revision giữ 0037. Hai API mới additive, API cũ giữ nguyên.

## Kiểm chứng

Focused backend Meta/settings/factory 40 passed trước vòng regression cuối;
runtime/SSE 8/8; browser dùng API riêng18100, pao_test và .env tạm với khóa giả:
password input, confirmation gate, ghi thật file tạm, clear secret ngay khi lưu,
readback không secret, không browser storage và OAuth pending-restart409 đạt.
Không gọi provider. Screenshot private .runtime/meta-app-settings-ui.png đã xem.
Full regression đạt **655 passed**, không skip, 598.28 giây, hai cảnh báo
ARQ deprecated close. Sau sửa helper DACL Windows, focused cuối **40 passed**
và browser temp-config chạy lại đạt. Protected DACL cũng được kiểm riêng bằng
file giả. Production frontend build cuối **18 pages**, mock regression **12 routes**.

Checkpoint trước rollout: .runtime/checkpoints/p0-20261007T085007-b20cc56b/manifest.json,
609 source files, 92 physical tables, 3 artifacts, revision0037, restore verified.
API/worker đã nạp source mới khi idle, Web/Ollama giữ process cũ; health/ready/Web200,
worker healthy (liveness), full live contract và replay archive **3/3** đạt.
237 operation/schema cũ giữ nguyên; thêm GET/PUT app-config thành239.

GET Settings live trả200, App ID/API version khớp cấu hình owner đã nhập,
secret_present=true nhưng không có trường secret; restart_required=false,
write/Autopilot=false, connection disconnected. Chỉ kiểm format/local configuration,
chưa xác thực App/version/quyền với Meta. Không save lại .env thật trong nghiệm thu
feature này; giữ cấu hình owner hiện có. Không gọi provider, không hoàn thành M3.
Checkpoint cuối lưu dưới .runtime/checkpoints (private, secrets excluded).
