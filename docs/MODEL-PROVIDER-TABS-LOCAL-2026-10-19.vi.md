# Nhà cung cấp mô hình — Client trước, API sau

## Phạm vi đã hoàn thành ngày 19/10/2026

Tại **Cài đặt và kết nối → AI và giọng nói → Nhà cung cấp mô hình**:

1. **Kết nối qua Client** đứng đầu, được chọn khi mở mục này mà không có liên kết chỉ định API. Có ba thẻ riêng: Codex, Claude Code, Antigravity.
2. **Kết nối qua API** đứng sau. Giữ nguyên biểu mẫu OpenAI, Anthropic (Claude), Google Gemini, OpenRouter cùng các chốt xác nhận hiện có.

Đây là lát cắt tổ chức giao diện của P8.4-E, không phải nghiệm thu toàn E hoặc C/F. Không đổi mô hình mặc định hiện tại, routing, quyền, fallback trả phí, backend, schema hoặc cấu hình môi trường. Chưa thực hiện P8.4-D để bỏ yêu cầu Ollama. Không sao chép phiên đăng nhập Codex trên Windows sang Docker.

## Cách sử dụng và trạng thái thật

- Client là hướng ưu tiên sản phẩm, không phải cam kết gói thuê bao bất kỳ cho phép mọi tác vụ/SaaS. Quyền sử dụng dịch vụ phải được kiểm tra riêng trong từng adapter.
- Codex: có nền tảng hồ sơ local ở backend; nút **Đọc hồ sơ Codex đã lưu** chỉ GET metadata hồ sơ của chính người dùng trong doanh nghiệp đang chọn. Không tự đọc khi mở tab, không chạy CLI/đăng nhập/gọi nhà cung cấp. Chỉ chủ doanh nghiệp/quản trị viên có nút này, theo quyền backend hiện hành.
- Nhãn **Chờ đăng nhập Codex** hoặc **Đã ghi nhận đăng nhập** chỉ phản ánh metadata đã lưu; không xác nhận quota, suy luận AI, job hoặc quyền công cụ. Luồng một nút đăng nhập/kết nối trên giao diện vẫn chưa hoàn tất.
- Claude Code và Antigravity được ghi rõ **Chưa triển khai kết nối**, không có nút kết nối giả hoặc ô nhận token.
- API vẫn dùng khóa riêng theo doanh nghiệp và có thể tính phí riêng với gói thuê bao Client. Không tự chuyển Client sang API.
- Hướng dẫn có thể thu gọn; có xử lý chưa đọc/đang đọc/lỗi/quyền hạn. Lỗi đọc hồ sơ không yêu cầu nhập lại mật khẩu.

## Điều hướng và bảo vệ dữ liệu

- Thứ tự bàn phím/hiển thị: Client → API; hỗ trợ phím mũi tên, Home, End và tabpanel liên kết ARIA.
- Liên kết trực tiếp: `/settings?tab=ai&section=providers&model_connection=api`; không có tham số hoặc tham số sai sẽ chọn Client.
- Giữ lịch sử quay lại/tiến tới, tham số doanh nghiệp/nhãn hàng và các liên kết cũ. Tham số phương thức không được giữ ở các khu vực không liên quan.
- Chuyển khỏi API khi biểu mẫu thay đổi phải xác nhận; hủy thì giữ biểu mẫu. Chấp nhận thì hủy request của component cũ và bỏ khóa API khỏi bộ nhớ biểu mẫu.
- Đổi doanh nghiệp/danh tính/quyền không mang hồ sơ hay khóa sang phạm vi mới. Response muộn và metadata sai SME/người dùng bị loại bỏ. Không lưu raw metadata, device/profile path hoặc setup command vào state hiển thị.

## Bằng chứng nghiệm thu giới hạn

| Kiểm tra | Kết quả |
|---|---|
| Node frontend | 162/162 đạt, 0 fail/skip/cancel |
| Next typegen, TypeScript | Đạt |
| Production build | Đạt, 23/23 trang; còn các cảnh báo lint sẵn có, không tắt lint |
| Browser Edge với fixture | Đạt; không chuyển tiếp API tới backend thật |
| Bảo vệ khóa nháp | Hủy/đồng ý rời tab; bỏ khóa khi unmount, không nằm trong URL/storage |
| Phạm vi/quyền | Hai SME quản lý, một SME người xem; lỗi/sai phạm vi, response muộn, không tự đọc CLI |
| Điều hướng | Default, deep link, reload, back/forward, bàn phím và ARIA |
| Hiển thị | Sáng/tối; 1440, 390, 320px; không tràn ngang trang; đã xem ảnh desktop/mobile |
| API health/readiness và trang Settings local | HTTP 200 |
| Đăng nhập Client/inference thật | Không thực hiện, chưa nghiệm thu |

Build chạy trên bản sao nguồn trong `.runtime`, không đụng output dev đang phục vụ hoặc chạy cài đặt dependency. Browser dùng phiên giả trong context riêng; chặn mọi API ghi và mọi origin ngoài local, không đăng nhập PAO thật. Không chạy lại toàn bộ backend: đây không phải full regression mới hoặc bằng chứng provider thật.

Artefact:

- Checkpoint UI trước sửa: `.runtime/model-provider-tabs-20261019/before.json` và `source-before/`.
- Build/Node/typecheck: `.runtime/model-provider-tabs-frontend-389c46e255cf4263b7ca6883b660a21a/receipt.json` và các log cùng thư mục.
- Browser cuối: `.runtime/model-provider-tabs-browser-1792396671893/receipt.json`, ảnh sáng/tối và desktop/mobile. Bản pass trước đó tại `model-provider-tabs-browser-1792396606586` cũng được giữ.
- Hai lần browser đầu thất bại vì helper chờ option phải visible và mặc định sai về tab sau đổi SME. Giữ nguyên receipt thất bại tại `model-provider-tabs-browser-1792396521108` và `model-provider-tabs-browser-1792396559297`; chỉ sửa giả định của test, không nới quyền hoặc logic ứng dụng để pass.
- Helper tái chạy: `scripts/check_model_provider_tabs_frontend.py`, `scripts/model_provider_tabs_browser.cjs`.

Tiếp theo vẫn là P8.4-C: hoàn thiện onboarding Codex trên giao diện và kiểm chứng đăng nhập/grant/native job đúng phạm vi. Các gate C/D/E/F/G, S6, owner pilot và production không được đóng bằng kết quả chia tab này.
