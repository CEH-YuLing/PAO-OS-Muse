# Nơi lưu backup PAO đã được chủ sở hữu chốt

Ngày xác nhận: **21/10/2026**.

- Nguồn đang phát triển: `F:\PAO-ACOS`.
- **Nơi lưu backup từ nay: `F:\PAO-BOS Backup 001`.**
- Quy ước thư mục mới: `F:\PAO-BOS Backup 001\PAO-ACOS-Backups\<UTC>-<run-id>\`.
- Cấu hình máy đọc: `infra/backup-storage.json`, chế độ `operator_workflow`.

Thư mục đích đã chứa bản sao dự án cũ. Không chép đè vào `apps`, `docs`, `scripts`,
`_backup` hoặc các file sẵn có tại gốc. Mỗi lượt backup phải có thư mục con mới,
không xóa/di chuyển bản cũ, không tự đặt lịch hoặc tự xóa theo thời hạn.

## Cách áp dụng ở các lượt backup sau

1. Đọc cấu hình này trước khi tạo checkpoint; kiểm tra đích là đường dẫn thật,
   không qua symlink/junction và không nằm trong source đang phát triển.
2. Có thể dùng `.runtime` làm staging cho các công cụ checkpoint/clone hiện có.
   **Staging thành công chưa có nghĩa đã lưu xong ở đích được chọn.**
3. Khi nhận yêu cầu backup, lưu bộ đã kiểm chứng vào thư mục con mới ở đích:
   mã nguồn, dump database, manifest/hash và cấu hình riêng đã mã hóa tách biệt.
   Không sao chép plaintext `.env`, token/keyring của CLI hoặc runtime đang hoạt động.
4. Đối chiếu hash bản nguồn và bản đích, ghi đường dẫn thật của các thành phần để
   phục hồi không phụ thuộc vào staging. Không báo hoàn tất nếu bản đích chưa được kiểm tra.

Đây là **quy ước vận hành đã lưu**, không phải scheduler hay thay đổi tự động mọi
đường dẫn nội bộ của công cụ. `backup_acos_checkpoint.py` và GD00 vẫn giữ staging/
guard phục hồi hiện có; operator phải thực hiện và kiểm tra bước lưu đích riêng.

Các bản GD00 đã tạo trước quyết định này vẫn nằm trong `F:\PAO-ACOS\.runtime`;
lượt lưu cấu hình này **không di chuyển hoặc tạo bản backup mới**. Receipt cũ không bị sửa.
Chưa upload GitHub. Đích vẫn trên ổ F nên không được coi là backup ngoài máy;
DPAPI vẫn phụ thuộc tài khoản/profile Windows cho đến khi có quy trình portable riêng.
