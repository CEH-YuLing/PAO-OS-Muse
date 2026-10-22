# S5.3 — Cấu hình AI và kiểm tra lựa chọn trước thực thi

Tài liệu lịch sử checkpoint0068. Candidate0070 đã nối native job/worker và
ghim lựa chọn thực thi; xem S5-COMPLETION-REGISTER.vi.md và báo cáo tích hợp S5
cho trạng thái hiện tại. Không dựng lại preflight hoặc thêm runner thứ hai.

Ngày16/10/2026. **Source candidate0068/368, chưa rollout primary0065/353.**
Đây là phần cấu hình/preflight của S5.3, không phải toàn S5.3 hoặc toàn S5 đạt.

## Đã triển khai

- Một tài liệu cấu hình có phiên bản riêng cho mỗi SME; owner/admin quản lý.
  Workspace lock + CAS + request key/hash/actor ngăn ghi trùng và lost update.
  Bảng `business_routing_versions` append-only; DB từ chối sửa/xóa lịch sử,
  revision nhảy cóc và downgrade khi đã có cấu hình.
- Danh sách model cho phép: tên lựa chọn, provider, model và tham chiếu kết nối
  SME đối với cloud. Không lưu API key, URL tùy ý hoặc grant của người khác
  trong cấu hình dùng chung. Ollama không có tham chiếu cloud.
- Chuyên môn Content/Creative/Ads/Analyst trỏ tới phiên bản kỹ năng Studio
  thực sự đã duyệt/xuất bản, không seed. Trợ lý/Brain gắn theo kỹ năng;
  chưa cho job thay Brain/toolset của phiên bản đã duyệt.
- Thứ tự SME → brand → agent version → workflow version/step → job override.
  Không phụ thuộc thứ tự mảng cấu hình. Lớp con chọn model trong allowlist
  kế thừa, chỉ giảm token/output/time, thu hẹp allowlist/privacy; không mở rộng.
  Kỹ năng có trần nhỏ hơn tiếp tục giới hạn kết quả cuối.
- Kiểm tra lại tenant, brand, phiên bản hồ sơ/kế hoạch, liên kết skill/agent,
  workflow step/skill và model preference. Chọn model xung đột preference
  đã xuất bản bị chặn, không âm thầm sửa trợ lý.
- Cloud cần grant model đã kích hoạt cho chính người đang xem trước, đúng
  brand/reference/provider/model hiện hành. Revoke/expiry/credential rotation/
  model thay đổi làm preflight mới bị chặn. Không giải mã hoặc gọi provider.
- Brain phải qua ACL hiện tại và đúng workspace/brand. Chưa có đường đưa
  private Brain lên cloud: chặn rõ, không fallback. Không lấy nội dung Brain.
- UI tiếng Việt ở candidate `/business-planning`: danh sách model, trần tài
  nguyên, chọn kỹ năng xuất bản, cấu hình riêng từng cấp và xem trước job.
  Có hướng dẫn từng trường, không có ô API key/secret ở màn hình này.
  Chặn preview khi chưa lưu; lựa chọn/plan thay đổi xóa preview cũ, response
  muộn không được gắn vào kế hoạch mới. Mất ACK lúc lưu yêu cầu đọc lại.

## API và ý nghĩa bằng chứng

- GET/PUT `/v1/workspaces/{id}/business-planning/routing`
- GET `/v1/workspaces/{id}/business-planning/routing/versions/{revision}`
- POST `/v1/workspaces/{id}/business-planning/plans/{plan}/routing-preview`

Preview trả lựa chọn/hash và đường kế thừa để giải thích; **không phải durable
job pin, token cấp quyền, phê duyệt, health check hoặc reservation**. Không
được tin client gửi lại snapshot này để chạy. `execution_enabled=false`,
`provider_calls=false`, `model_availability_verified=false`, `quota_reserved=false`.
Danh sách công cụ và fallback hiện rỗng. Creative hiện là ý tưởng văn bản,
không phải tạo ảnh/video. Budget profile vẫn không phải số dư khả dụng.

Local preflight không gọi Ollama `/api/tags` ngoài sổ tài nguyên. Kiểm tra model
đã cài/đang online phải dùng native metadata admission ở bước khởi chạy sau.
Quyền S2 là điều kiện cần, không thay quota/chat privacy/approval/worker checks.

## Còn phải làm để hoàn tất S5.3

1. Adapter admit native Run/Studio từ native Task S5, transaction receipt và
   immutable job pins từ dữ liệu server; không mở khóa native/P6 guards cũ.
2. Model selection qua native engine metadata admission, quota/resource ledger;
   đúng privacy/Brain/caps và credential binding trước mỗi call, cả local/cloud.
3. Worker recheck quyền/plan approval/emergency stop trước gọi và công bố kết
   quả; dispatch/recovery/cancel qua owner hiện có, không thêm runner cạnh tranh.
4. Artifact/draft review và projection Task/Goal có idempotency; dependency
   gate, unknown/lost-ACK/restart/revoke tests. Không tự đánh completed từ preview.
5. Hai bước thực thi hai model đã cấp, cấu hình sửa không repin queued job,
   audit usage và model quality gate thật local. Preflight hai tên model không
   thay thế bài thực thi này. Money caps/reservation S5.4 vẫn chưa có.

Không đổi `.env`, không restart API/worker, không migration primary hoặc gắn menu
phát hành. Giữ launcher migration pin0065. Sổ S5 ghi kết quả kiểm thử hiện hành;
không suy full regression hoặc production acceptance từ các ca focused.
