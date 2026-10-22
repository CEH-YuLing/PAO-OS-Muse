# Xóa công việc tạo nhầm hoặc tạo lỗi

## Cách dùng

Mở **Công việc và dự án**, chọn thẻ công việc để mở chi tiết, bấm
**Xóa công việc**, kiểm tra đúng tên rồi bấm **Xác nhận xóa**.
**Giữ lại** không thay đổi dữ liệu. Sau khi xóa thành công, có thể tạo công việc mới.

Đây là **xóa khỏi bảng**, không phải xóa vĩnh viễn: PAO chuyển công việc sang
đã hủy và lưu dấu xóa, người thao tác, phiên bản và trạng thái trước đó.
Bình luận, hoạt động và dữ liệu gốc vẫn được lưu để đối soát. Chưa có giao diện
khôi phục; không tự phục hồi hoặc xóa vĩnh viễn dữ liệu.

## Phạm vi và quyền

- Chỉ chủ doanh nghiệp hoặc người tạo còn quyền ghi trong doanh nghiệp đó.
  Người chỉ xem và người ngoài doanh nghiệp không được xóa.
- Chỉ công việc tạo thủ công, loại con người, chưa có kết quả hoặc lần thực thi.
  Có thể thuộc dự án nhưng không được thuộc mục tiêu/quy trình, có việc con,
  liên kết phụ thuộc, hoặc gắn lượt chạy. Việc đang chạy/hoàn tất bị chặn.
- Backend là nơi kiểm tra quyền, phiên bản, liên kết và chốt workflow/Goal/
  kế hoạch kinh doanh, không dựa vào trạng thái nút trên giao diện.
- Dữ liệu không bị cascade-delete. Tác vụ đã xóa không được sửa, bình luận,
  khởi chạy hoặc gắn làm việc cha/phụ thuộc mới qua API công việc.
- Khóa hàng tuần tự hóa xóa, cập nhật và tạo liên kết. Phiên bản đã thay đổi
  trả 409; không tự nâng phiên bản rồi xóa. Lặp đúng yêu cầu xóa sau mất phản hồi
  không tạo dấu xóa mới. Không tự thử lại thao tác ghi khi mất mạng.

## Kỹ thuật

`DELETE /v1/tasks/{task_id}?version=N` trả `TaskOut` đã hủy sau khi lưu
`task.deleted` vào `task_activity`. Danh sách lọc dấu xóa bằng EXISTS trên
chỉ mục task_id hiện có; không thêm bảng/cột hoặc migration. Schema vẫn 0071.
Mọi trường hợp bị chặn giữ nguyên công việc. Lịch sử phê duyệt/sự kiện vẫn tồn tại;
phiên bản/trạng thái đã hủy vô hiệu quyết định cũ, không thực thi phê duyệt.

## Nghiệm thu

Kiểm thử trong bản nguồn riêng `F:\Apex\task-delete-candidate` và database test;
không xóa công việc người dùng trong ảnh. Bằng chứng nằm trong `.runtime` của
bản thử và `.runtime/task-delete-browser-runs` của bản local. Chạy focused backend,
Node, TypeScript, build production và browser API native. Giữ cả lần lỗi ban đầu.

Thay đổi backend làm đổi execution binding. Hồi quy đầy đủ trước đây là bằng
chứng lịch sử, không được tự coi là full regression cho phiên bản này. Nghiệm thu
chức năng nhỏ này không đồng nghĩa hoàn tất S6, dữ liệu thật hay production.
