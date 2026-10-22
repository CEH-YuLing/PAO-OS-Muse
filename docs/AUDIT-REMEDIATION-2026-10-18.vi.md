# Khắc phục sau kiểm tra PAO local — 18/10/2026

## Phạm vi được duyệt

Bổ sung truy vết yêu cầu API; sửa readiness sử dụng bằng chứng cũ và script
`npm run test:frontend` chưa theo giao diện tiếng Việt/phân nhóm mới. Không
thay đổi database/schema0071, quyền nghiệp vụ, cấu hình model hoặc kết nối;
không xóa dữ liệu, khôi phục primary, bật Ads, gửi tin hay triển khai công khai.

## Truy vết an toàn

Logger `pao.request` ghi JSON với request_id do máy chủ sinh, thời điểm bắt đầu
và kết thúc UTC, HTTP method/status/thời gian, mẫu route do ứng dụng đăng ký,
actor_id sau xác thực/kiểm tra phiên, workspace_id sau kiểm tra membership/quyền
ghi, và client_ip lấy từ ASGI scope. Không đọc ID từ header để gán tài khoản.
Nếu một yêu cầu truy cập nhiều doanh nghiệp đã được kiểm quyền, log đánh dấu
multiple_workspaces thay vì gán nhầm doanh nghiệp cuối cùng.

Không ghi URL/path thật, query, authorization/cookie/header, API key, mật khẩu,
body, nội dung chat, response hoặc nội dung exception. Route không khớp được
ghi null; IP/ID không hợp lệ bị bỏ. Log không được cung cấp qua endpoint công
khai. Giữ quyền truy cập log hạn chế; không gửi toàn bộ log lên chat.

client_ip là giá trị ASGI, KHÔNG chứng minh người, tab hay PID. Uvicorn/reverse
proxy có thể áp dụng chính sách proxy-header trước ứng dụng; cần cấu hình và
đối chiếu trust boundary khi triển khai production. Ứng dụng không tự tin
X-Forwarded-For/X-Request-ID. SSE chỉ ghi sự kiện hoàn tất khi request kết thúc.
Mục đích là đối chiếu thao tác tương lai; không thể bổ sung bằng chứng hồi tố
cho những yêu cầu cũ vốn chưa có các trường này.

Context được tách giữa các request đồng thời và xóa cả khi xảy ra exception;
kiểm thử bao gồm login thực trên fixture, 401/404, membership, giả header,
ngữ cảnh nhiều doanh nghiệp và kiểm tra không lộ thông tin nhạy cảm.

## Readiness

Không chọn UX overlay cũ khi đã có release backend xóa task. Nếu thiếu hoặc
sai binding/bằng chứng hiện tại, CLI trả exit1 với JSON có cấu trúc, đồng thời
thay snapshot chẩn đoán `.runtime/s6-readiness.json` cũ bằng kết quả fail mới.
Các completion/receipt lịch sử không bị sửa. Không bỏ assertion bảo vệ nguồn.

Chỉ `.runtime/current-local-release.json` mới được dùng làm con trỏ bằng chứng
hiện tại. Nó trỏ manifest CI/receipt cài đặt trong `.runtime`, gắn source_files
và binding. Bộ kiểm tra so toàn bộ nguồn hiện tại với ZIP nguồn CI, đối chiếu
test counts/guard primary/.env/cleanup, kiểm tra endpoint/worker/407operations/
153bảng/ba archive. Một bộ test chức năng đạt nhưng primary thay đổi vẫn fail.

Sự cố primary drift trước đó chưa rõ nguồn được giữ là chốt riêng chưa đạt.
Bản sửa này KHÔNG có chức năng tự miễn chốt hoặc đổi nhãn để đóng sự cố. Một
lượt test sạch sau đó không chứng minh nguyên nhân của thay đổi trước đó.
S6/dữ liệu thật/owner pilot/production vẫn chưa nghiệm thu.

## Test frontend

Giữ kiểm tra Orb, bố cục, điều hướng, dữ liệu quảng cáo giả, task/AI, CRM,
creative, analytics, workflow, bộ nhớ và Settings. Dùng nhãn tiếng Việt,
tablist và chế độ xem nhỏ theo giao diện hiện tại, không dịch enum/API.
Toàn bộ /v1 và thời tiết được giả lập trong script synthetic; không cho rơi
xuống backend thật hoặc nhà cung cấp. Browser native dùng database UUID riêng,
khóa giả và API thử riêng; kết quả này không chứng minh OAuth/model/Ads thật.

## Kiểm chứng và trạng thái

Kết quả chạy, hash nguồn, binding, snapshot trước/sau, log thất bại và cleanup
được giữ trong artifact của đợt khắc phục. Chỉ chốt số test đã thực sự chạy;
không kế thừa CI2.293 cũ cho backend đã bổ sung truy vết. Bản cài phải được
khởi động lại bằng đúng runtime pin, qua kiểm tra idle và định danh tiến trình,
sau đó kiểm tra endpoint/worker/contract/replay và UI chỉ đọc.

Không sửa dependency hoặc67cảnh báo lint trong phạm vi này. ECONNRESET ở lượt
browser trước vẫn là lỗi gián đoạn chưa xác định nguyên nhân; không thêm retry
để che lỗi. Kết quả mới, nếu đạt, chỉ là một lượt kiểm tra bổ sung.
