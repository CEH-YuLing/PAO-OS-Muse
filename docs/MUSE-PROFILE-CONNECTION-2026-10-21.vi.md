# Muse Code — kết nối bằng profile PAO riêng

Ngày: 21/10/2026 · nguồn và bản cài: `F:\PAO-ACOS`.

**Biên bản lịch sử bước auth.** Trạng thái mới ngày22/10: chủ sở hữu đã đăng nhập,
adapter văn bản đã cài và chạy thuê bao thật theo phạm vi ghi trong
[biên bản adapter Muse](MUSE-TEXT-ADAPTER-LOCAL-2026-10-22.vi.md).
Các trạng thái/chưa làm bên dưới giữ nguyên để phản ánh thời điểm21/10.

## Trạng thái chính xác

| Phần | Kết quả |
|---|---|
| Gói Muse Code | Chủ sở hữu xác nhận đang có thuê bao; chưa có bài chạy quota trong PAO |
| Profile riêng | Đã tạo `.runtime/muse-profile`, kiểm tra home native nằm trong profile; ACL chỉ tài khoản Windows hiện tại và SYSTEM |
| Đăng nhập chính chủ | Đã triển khai device login trên Settings; thử mở luồng thật và hủy thành công; profile mới chưa được chủ sở hữu đăng nhập tại thời điểm nghiệm thu |
| Kết nối và danh mục | Có card Muse, API metadata/auth, revision/idempotency, mô hình/mức suy luận đọc từ native; không đọc token cũ |
| PAO AI | Hiển thị danh mục đã lưu ở dạng chỉ xem; chưa có lựa chọn Muse thực thi |
| Chat / Agent / Job | **Chưa triển khai xong adapter suy luận**, chưa gửi prompt hoặc tiêu quota Muse thật |
| Toàn GD01 / production | Vẫn chưa hoàn tất |

Không coi thao tác đăng nhập hoặc đọc model thành bằng chứng còn quota hay đã chạy
Chat/Agent/Job. Đây là bước triển khai kết nối/auth, không phải toàn bộ tích hợp Muse.

## Thiết kế đã cài

- Kết nối là tài nguyên bản cài, không thêm grant AI riêng cho từng nhân sự.
  Người có quyền quản trị bản cài hiện hữu mới kết nối/ngắt; thành viên hợp lệ
  xem trạng thái theo quyền ứng dụng. Dữ liệu nghiệp vụ vẫn tách SME.
- Dùng binary Meta chính chủ `1.4.10-R6427.1`, SHA256
  `893a04138b81d844cc53e25216fafe0cbf7c786423534b93aacf1419a840f6b7`
  và fingerprint giao thức native. Không chạy launcher tự cập nhật để thử.
- Muse tự lưu phiên đăng nhập vào profile PAO riêng. Backend không đọc/sao chép
  token, không chuyển tiếp biến API key hoặc `MUSE_AUTH_PATH` từ tài khoản cũ.
  Profile là dữ liệu nhạy cảm trên máy, không đưa vào Git hay source backup.
- Không sửa hoặc bỏ managed hooks, cấu hình, hội thoại trong profile Muse cũ.
  Host đăng nhập chỉ cho phép initialize/account/model metadata và login/cancel;
  từ chối session/turn/settings/logout. Không có prompt nghiệp vụ trên host này.
- Mã device login chỉ trả cho người khởi tạo còn quyền quản trị; không ghi vào
  receipt/log. Phiên chờ tối đa 10 phút. Ngắt PAO không đăng xuất Muse hoặc xóa profile.
- API không nhận đường dẫn binary/lệnh/key từ trình duyệt. Lưu trạng thái nguyên tử,
  recheck quyền sau I/O, có revision và chống lặp yêu cầu. GET không gọi native/model.
- Nút **Kết nối Muse** → trang đăng nhập chính chủ → chủ sở hữu xác nhận →
  **Kiểm tra lại Muse** để lưu danh mục. Không yêu cầu mật khẩu Muse trong PAO.

## Catalog và mức suy luận

Bổ sung kết quả mới sau tài liệu nghiên cứu ban đầu:
`reasoningEffortVariants` chỉ chứa mô tả cho một số mức; **`variants` mới là toàn
bộ lựa chọn native**. Không giữ suy luận cũ rằng mảng mô tả rỗng nghĩa là không có effort.

Native profile cũ đã trả Wonder 1.0 và Spark 1.3 với
`minimal/low/medium/high/xhigh/max`, Spark 1.2 với
`minimal/low/medium/high/xhigh`; mặc định high. Đây là snapshot metadata, không
hardcode thành quyền sử dụng hoặc quota. Profile PAO còn loggedOut nên không
nhận catalog chưa đăng nhập làm catalog đã xác thực.

## Bằng chứng

| Kiểm tra | Bằng chứng / phạm vi |
|---|---|
| Backend regression | `.runtime/gd01-tests-01b6c7250f88440991c3e169c46fb243/receipt.json`: 535 pass, 0 fail/error/skip; schema0077/161 bảng, dữ liệu chính/source/env không đổi |
| Unit kết nối/profile | `scripts/test_muse_client.py`: 22 pass; synthetic, không DB/network/quota |
| Frontend | `.runtime/model-provider-tabs-frontend-c5c82a150c664277927596705bcbd8a2/receipt.json`: 255 Node, typegen/typecheck/production build đạt |
| Browser giả lập | `.runtime/model-provider-tabs-browser-1792592624948/receipt.json`: login, mất ACK, vai trò, ngắt có xác nhận, sáng/tối1440/390/320; 0 request backend/provider thật |
| Bản cài chỉ đọc | `.runtime/gd01-installed-5589c8dbfdf84f0f8f6c058a73adc637/receipt.json`: API/ready/Web200, worker khỏe, contract source/live/stored bằng nhau, 2 SME/3 replay, 4 card Client và 6 model Codex; dữ liệu chính không đổi |
| Native metadata/auth | Profile riêng loggedOut; official device flow pending tại auth.meta.com rồi hủy, child đã đóng; không sao chép phiên cũ hoặc gửi prompt |
| Echo cách ly | `muse exec --preset empty` trong môi trường rỗng trả echo tổng hợp; không phải suy luận thật hoặc nghiệm thu toàn bộ tool registry |

Lệnh restart backend báo quá hạn ở vòng kiểm HTTP của script. Log native đã
ghi API phục vụ HTTP200; kiểm tra health và installed acceptance độc lập sau đó
đạt. Giữ nguyên lỗi gốc, không gọi script restart là một lượt pass toàn bộ và
không khởi động lặp chỉ để thay bằng chứng.

Backup trước thay đổi:
`F:\PAO-BOS Backup 001\PAO-ACOS-Backups\20261021T134724Z-d0d39788bcaa4c3f981f2acf1e177657`.
Đã đối chiếu hash; không ghi đè bản cũ. Bản này là mốc trước code kết nối mới,
không chứa phiên Muse mới. Không restore database chính, không đổi `.env` hay schema.

## Những việc còn phải hoàn thiện (không phải chỉ chờ tài khoản)

1. Chủ sở hữu đăng nhập profile mới và kiểm tra catalog được xác thực.
2. Hoàn thiện adapter suy luận vào resolver/attempt/dispatch hiện có, không thêm
   runner nghiệp vụ; pin model/effort/nguồn theo revision cho Chat/Agent/Job.
3. Xác minh công cụ/ngữ cảnh thực tế, containment của child trước dispatch,
   cancellation/timeout/mất ACK/không retry ngầm, quyền hiện tại và tách SME.
   Không lấy echo hay `disable-shell` làm bằng chứng toàn bộ công cụ đã tắt.
4. Tích hợp output/JSON planner và usage trung thực. Native1.4.10 có thể thiếu
   token usage; không biến số ước lượng thành token được provider báo cáo.
5. Chạy prompt tổng hợp và job nhỏ bằng thuê bao thật sau khi adapter đạt;
   kiểm tra không fallback API trả phí, trạng thái/effort chọn khớp attempt.
6. Nghiệm thu Chat/Agent/Job/recovery rồi mới bật lựa chọn thực thi và ghi hoàn tất.

Contributor mode có thể chia sẻ nội dung cho Meta; kiểm tra lựa chọn chính chủ
trước khi thử dữ liệu doanh nghiệp thật. Không tự đổi lựa chọn riêng tư của khách.

Tài liệu chính thức đối chiếu21/10:
[Muse Code](https://dev.meta.ai/docs/muse-code),
[đăng nhập](https://dev.meta.ai/docs/muse-code/auth),
[thuê bao](https://dev.meta.ai/docs/muse-code/subscriptions),
[quyền](https://dev.meta.ai/docs/muse-code/permissions),
[SDK/MSP](https://meta-models.github.io/muse-code-sdk/1.4/).
