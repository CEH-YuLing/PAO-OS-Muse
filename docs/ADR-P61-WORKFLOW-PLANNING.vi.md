# P6.1 — Biên dịch workflow, không thực thi

Ngày 07/10/2026. Phạm vi: F:\PAO-ACOS, local-only.

## Quyết định

Tái sử dụng Studio, Task, TaskDependency và TaskActivity hiện có. Snapshot nằm
trong StudioEvent với action `p61_plan_created`; trigger bất biến hiện có bảo vệ
ledger này. Không thêm bảng, migration, scheduler, runner hoặc service riêng.
Database giữ revision 0037. API thêm bốn operation vào router Studio hiện hữu.

Owner của definition có thể preview một workflow đã publish và xác nhận hash
để tạo plan. Kiểm tra DAG, scope, phiên bản đã review/publish, kiểu input và
binding trước khi ghi. Thứ tự topo xác định; workflow/skill/agent payload và
hash được ghim vào snapshot. Model chỉ ghim tên/cấu hình Ollama; không gọi
Ollama và không xác minh hash weights (`weights_verified=false`).

Một step tạo một task draft/human/unassigned và execution ID dự trữ ổn định;
chưa tạo TaskAttempt. Evidence chỉ là schema/tiêu chí kỳ vọng, chưa có kết quả
quan sát (`observed=false`). Plan, task, dependency và activity cùng transaction.
Request key UUID và khóa definition chống trùng khi retry đồng thời. Replay
dùng snapshot cũ, không tự đổi sang agent mới publish; đổi input với cùng key
bị từ chối. Hash preview cũ không khớp compile mới thì không tạo task.

Task đã gắn plan bị khóa PATCH và tạo attempt tại API. Guard đọc ledger bất
biến, không phụ thuộc feature flag hoặc metadata task có thể sửa. Tắt flag
không mở đường chạy task. Quyền đọc plan vẫn kiểm tra membership workspace.
Quyền sửa trực tiếp database nằm ngoài bảo vệ API; không cấp quyền DB này cho agent.

## Giới hạn và an toàn

- Không có model/tool call, Ads write, Run, schedule, outbox hoặc delivery mới.
- Cloud model preference bị từ chối trong checkpoint local này.
- Input tối đa 16 KiB, snapshot 256 KiB, 100 plan/definition; kiểm tra tên trường
  secret và mẫu nguy hiểm chỉ là heuristic, không phải bảo đảm DLP đầy đủ.
- Snapshot chứa input người dùng: không nhập secret; bảo vệ database/backup.
- Không sửa hoặc xóa snapshot khi republish definition. Workflow runner P6.2
  phải được thiết kế và nghiệm thu riêng trước khi thay đổi frozen guard.

## Vận hành

Mặc định `WORKFLOW_PLANNING_ENABLED=false`; installation local này chỉ bật sau
regression/checkpoint. Mở `/skills`, chọn Workflows, publish definition đã review,
nhập input JSON, preview rồi xác nhận tạo task nháp. Không có nút Run mới.
Rollback: tắt planning flag và khởi động lại đúng API/worker; giữ ledger/task
và khóa execution. Không reset database hoặc xóa lịch sử.

Meta tạm tắt bằng `META_ENABLED=false`; App ID/secret/encryption key được giữ
nguyên. Không bấm lưu Meta App Settings trong thời gian pause vì thao tác lưu
cấu hình hiện có sẽ bật lại Meta. M3 dữ liệu thật vẫn chưa nghiệm thu.
