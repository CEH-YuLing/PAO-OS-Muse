# S2.1B2b — Kích hoạt model và giữ cố định quyền của tác vụ

Ngày 11/10/2026. Chỉ target F:\PAO-ACOS; không gọi provider thật.

Giữ nguyên reference/grant B1 staged/revoked và mọi pins lịch sử. Thêm bảng
model_grant_activations (0050) append-only: một consent explicit của manager
cho một grant, capability model_inference, request UUID/fingerprint, revision
reference/grant, source_stamp. Không gia hạn TTL, đổi grantee/brand/source,
tự kích hoạt, hoặc dùng read_only của B1 làm inference permission.
Revoke B1 vẫn vô hiệu activation; record không bị xóa/sửa. Model inference
không cấp tools, Brain, email, Ads hoặc quyền chi tiêu. Inference có thể tiêu
token theo policy hiện có; quotas SME đầy đủ thuộc S2.2.

POST activation cần manager hiện hành, CAS và acknowledgement rõ. PUT engine
phải chọn activation grant_id, không ngầm chọn default/active grant. Selection
và Run pin giữ workspace/actor/brand/source/ref/grant/activation IDs, revisions,
expiry/capability. Admission và mỗi call/chunk/publication kiểm lại metadata,
membership hai phía, current source fingerprint, expiry, Brain và chat policy.
Legacy chưa đăng ký giữ nguyên; registered không có pin hợp lệ thì deny, kể cả
snapshot cũ hoặc resolver không có actor. Không fallback sang key/local khác.

Khóa workspace trước consent/revoke; KEY SHARE tại check để serialize với
mapping. Không giữ transaction suốt network; bytes gửi hợp lệ trước revoke
không thu hồi được. Kết quả về muộn bỏ, không sửa phần đã xuất hợp lệ trước đó.

Gate: backup trước schema, clone 0049→0050→0049→0050 giữ rows/schema legacy;
DB trigger chống UPDATE/DELETE và scope tamper; two-SME, CAS/replay/concurrent,
expiry/role/rotation/delete/queued/late-result và no-decrypt-on-deny tests;
regression/contract/build/live/restore. Chưa đạt gate thì không rollout primary.
Không đổi provider adapter/auth/SDK/network nên không mở connector dossier mới.

Checkpoint này chưa đóng B2 (MCP/Ads), S2.2 vault/quota hoặc S2.3 Settings.
