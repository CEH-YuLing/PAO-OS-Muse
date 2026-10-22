# Ô kết nối Client/API — UI local ngày 19/10/2026

## Kết quả và phần chưa xong

Đã hoàn thành tái thiết kế giao diện theo từng nhà cung cấp. **Chưa hoàn thành toàn bộ yêu cầu tự kết nối Client bằng một nút.** Không dùng việc hiển thị ba nút để tuyên bố ba adapter đã hoạt động.

- Client: ba ô Codex, Claude Code, Antigravity cùng một hàng trên desktop, xếp dọc trên điện thoại. Có icon, trạng thái và nút Kết nối. Các nút đang bị vô hiệu cùng lý do rõ ràng: Codex còn thiếu cầu nối đăng nhập trên giao diện; Claude/Antigravity chưa có adapter hoạt động. Nút đọc metadata Codex được tách khỏi ba ô, không đặt tên là Kết nối.
- API: bốn ô OpenAI, Claude (Anthropic), Google Gemini, OpenRouter; bỏ dropdown chọn một provider. Mỗi ô có chỗ nhập khóa, **Lưu cấu hình**, **Xóa khóa**, nhãn trạng thái. Trên desktop là lưới hai cột, điện thoại là một cột.
- Các thao tác model/danh mục/mặc định/kiểm thử có phí được thu gọn vào mục nâng cao. Hướng dẫn và bằng chứng trạng thái cũng có thể thu gọn. Không loại bỏ các chốt quyền hoặc consent.

## Hành vi lưu và xóa khóa

1. Nhập khóa → nhãn **Đã nhập · chưa lưu**, input dạng mật khẩu; chưa gửi request.
2. Bấm **Lưu cấu hình** → xác nhận tên provider, doanh nghiệp và việc lưu khóa/gọi danh mục; hủy không gửi request. Consent này thay checkbox cấu hình cũ cho thao tác lưu khóa. Kiểm thử suy luận và quyền công cụ vẫn tách biệt.
3. Máy chủ xác nhận và GET đối chiếu → **Đã lưu khóa**, box có dạng `••••abcd`, không trả khóa gốc. Giá trị key_hint không đúng mẫu chỉ hiển thị mask chung.
4. Nhập khóa mới để thay; bỏ khóa nháp không ảnh hưởng khóa đã lưu. Lưu ô này không làm mất khóa nháp của ô khác trong cùng SME.
5. Bấm **Xóa khóa** → xác nhận ngắt bản lưu của provider trong SME này. Dùng DELETE API sẵn có và đọc lại trạng thái. Không tự thu hồi khóa ở nhà cung cấp, không tự logout Client hoặc chuyển default sang nhà cung cấp khác.
6. Lỗi/mất ACK → không tự gửi lại, bỏ khóa nháp và yêu cầu đọc lại. Chưa đọc được không đồng nghĩa chưa có khóa. Quyền model/usage cũ không tự sống lại khi lưu lại.

Chỉ owner/admin có trường nhập và thao tác. Không đổi backend/schema/env/default/routing. Giữ xác nhận nháp khi đổi tab; đã lưu hoặc bỏ hết nháp thì không tiếp tục cảnh báo nháp chỉ vì từng gõ vào form. Các mục Settings khác giữ bộ bảo vệ cũ. Khóa nháp chỉ trong bộ nhớ component, xóa khi lỗi/ẩn tab/rời trang/đổi SME hoặc quyền; không lưu sessionStorage/localStorage/URL.

## Nghiệm thu giới hạn

- 164/164 Node tests, 0 fail/skip/cancel.
- Next typegen, TypeScript và production build 23/23 trang đạt trên bản sao nguồn; còn cảnh báo lint sẵn có, không tắt lint hoặc sửa dependency.
- Browser Edge fixture đạt: ba Client chưa hỗ trợ không thể bấm kết nối; bốn ô API, consent hủy/đồng ý, lưu cả bốn provider, xóa hủy/đồng ý và reload, mask không phản chiếu key gốc, nhiều khóa nháp, advanced consent/model/default/probe, mất ACK không retry, response API/CLI muộn, hai SME và một vai trò viewer.
- Sáng/tối, 1440/390/320px, lịch sử, deep link, bàn phím/ARIA, không tràn ngang trang; đã xem ảnh desktop và điện thoại.
- 9 thao tác ghi **chỉ trong fixture**; 0 request chuyển tới backend thật, 0 provider calls và 0 thay đổi khóa thật. Không phải native-provider acceptance, full backend regression mới hoặc whole P8.4/S6/production.

Artefact:

- Trước sửa: `.runtime/model-provider-cards-before-40b77e3ad642443da88f8908a68050f7/`.
- Bản nguồn UI đã kiểm chứng trước đó cũng giữ tại `.runtime/model-provider-tabs-frontend-389c46e255cf4263b7ca6883b660a21a/source/`, gồm SettingsWorkspace/ModelProviderSettings trước thay đổi dirty guard lần này.
- Build: `.runtime/model-provider-tabs-frontend-f4287ede55a0446db9aa19ab82cc5cb3/receipt.json`, Node/typecheck/build logs.
- Browser: `.runtime/model-provider-tabs-browser-1792397564976/receipt.json`, ảnh sáng/tối desktop/mobile.
- Tổng hợp giới hạn: `.runtime/model-provider-cards-completion.json`. Receipt chia tab trước đây giữ nguyên như bằng chứng lịch sử, không thay thành bằng chứng mới.

## Bước còn thiếu: kết nối Client thật

P8.4-C cần API quản lý một phiên đăng nhập có thời hạn, phân quyền theo user/SME/profile/device, bắt đầu/đọc trạng thái/hủy, phục hồi và cleanup. UI sau đó mới mở đăng nhập chính thức, hoặc xác nhận dùng phiên đúng profile được phép. Không mở PowerShell yêu cầu nhập lại mật khẩu PAO, không tự import auth ở Windows, không nhận token trong chat và không gắn arbitrary command vào nút.

Claude Code/Antigravity tiếp tục gate adapter và điều kiện sử dụng P8.4-F. Đăng nhập một lần vẫn có thể cần người dùng xác nhận tại nhà cung cấp; có ứng dụng trên máy không chứng minh profile cách ly trong Docker đã đăng nhập.

Đối chiếu OpenAI Docs ngày 19/10/2026: [App Server](https://learn.chatgpt.com/docs/app-server) mô tả account/read, account/login/start/completed/cancel và giới hạn app-server auth với dịch vụ commercial/hosted; [Authentication](https://learn.chatgpt.com/docs/auth) giải thích credential cache và profile local. PAO SaaS cần đường đăng nhập chính thức phù hợp, không mặc định tái sử dụng tài khoản chủ máy cho các SME/nhân viên. Lần này chỉ đọc tài liệu, chưa triển khai hoặc gọi luồng đăng nhập mới.
