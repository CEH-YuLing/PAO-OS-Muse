# Stage K — Knowledge

Route `/knowledge` sử dụng memory API đã có của PAO.

## Khu vực

1. Memory Library: fact, importance, status, embedding model và version.
2. Semantic Search: tìm theo ngữ nghĩa trong workspace/brand scope.
3. Brands & Scope: tách tri thức dùng chung và tri thức theo brand.
4. Memory Runtime: trạng thái extraction của hội thoại gần nhất.

Tạo, sửa và xóa memory dùng contract backend; thao tác sửa/xóa giữ optimistic version. Memory đã xóa không tự phục hồi.
