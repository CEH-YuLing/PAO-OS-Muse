# P1.1 — Brain scopes và legacy mapping

Ngày 06/10/2026. Target duy nhất F:\PAO-ACOS. P1 được người dùng cho phép;
M4, public deployment và writes ra dịch vụ ngoài vẫn không được phép.

## Quyết định

- Workspace vẫn là tenant; Brand vẫn là business scope. Brain nằm trong một
  workspace, có UUID, owner, optional brand, revision và archive timestamp.
- Brain riêng tư mặc định. Workspace owner/admin không tự đọc Brain của người khác.
  Explicit brain membership chỉ dành cho files/notes mới, không cấp quyền legacy facts.
- Mọi request luôn kiểm tra workspace membership hiện hành, cả khi biết UUID.
  Workspace viewer không có quyền ghi dù được cấp brain editor.
- Một default legacy Brain trên mỗi (workspace, user, brand hoặc NULL).
  Migration thêm metadata, không copy/update/delete bất kỳ memory nào.
  Legacy facts vẫn được đọc qua user/workspace/brand ACL hiện có; không trở thành
  tài sản chia sẻ chỉ vì người dùng được mời vào Brain.
- Session cũ được liên kết default Brain tương ứng. Run cũ không backfill Brain:
  history/usage/archive không bị viết lại. Run mới pin Brain ID/revision và scope;
  đổi Brain không sửa snapshot run cũ. Không đổi Brain khi có run active.
- Brain không mặc định đưa files/notes vào prompt: ingestion/RAG thuộc P2.
  Custom Brain không được lấy hoặc ghi legacy memory ở default Brain.
- Archive giữ bytes/history, chặn ghi và launch run mới; đọc để phục hồi/export
  vẫn phải có quyền hiện hành. Trash file/note là recoverable, không hard-delete.
- File MVP ưu tiên UTF-8 text/Markdown. Bytes immutable trong PostgreSQL, cùng
  transaction metadata: không có path do user quyết định, không symlink/orphan trên
  filesystem. Quota tính cả trash và tất cả note versions, serialize bằng Brain lock.
  HTML/scripts/archives không preview/thực thi. Nội dung upload là untrusted data.
- Portable export chỉ whitelist files/notes, manifest + hash; không credentials,
  tokens, chat, legacy memory hoặc operational config. Import bounded ZIP,
  dry-run trước confirmation, chống traversal/bomb/duplicates/symlink/unknown entries.
  Confirmation pin archive hash và Brain revision; không chạy code từ import.

## Gate và rollout

`brain_manager_enabled=false` mặc định đến khi nghiệm thu P1 local. Migration
additive; checkpoint DB/source đã verify ở revision0024 trước thay đổi. Tests dùng
pao_test/Redis15, không truncate local. Downgrade chỉ trên test DB; không tự drop
Brain data trên local. P1.1 chỉ nghiệm thu sau isolation + migration check/roundtrip.
P1.2–P1.5 có tests và báo cáo riêng trước bật local. Không đồng nhất code/build
thành công với production acceptance.
