# Kết quả Giai đoạn 3 — Goal và Task nghiệp vụ

Ngày nghiệm thu: 29/09/2026  
Nhánh: `pao-stage-3-goals-tasks`  
Phạm vi: M1 trong PAO Master Roadmap

## Kết luận

M1 **đạt trên môi trường local**. PAO đã có Goal, Task dependency chuẩn hóa,
Task Attempt, success criteria, evidence và điều kiện hoàn thành xác định. Module
Projects/Tasks Phase 18 được nâng cấp, không xây một task engine cạnh tranh.

Không bật Ads write, Autopilot hay side effect bên ngoài. Stage này chưa tự động
chạy skill; đó là phạm vi M2.

## Thành phần đã triển khai

- `goals`: owner, workspace/project, deadline, success criteria, version và state.
- `tasks`: goal/parent, skill hint, input references, budget, required flag,
  evidence và result reference.
- `task_dependencies`: cạnh dependency có foreign key và chống self-reference.
- `task_attempts`: attempt number, idempotency fingerprint, optional Run link,
  result/evidence/error và timestamps.
- State machine tám trạng thái; AI/agent không thể bỏ qua Attempt.
- Goal không thể completed nếu task bắt buộc chưa completed hoặc thiếu evidence.
- Dependency/parent chưa completed thì child không được tạo Attempt.
- Cancel task kết thúc attempt đang chạy; kết quả đến muộn bị từ chối.
- Telegram có `/goals` và `/tasks` read-only theo workspace.
- Tasks UI đọc state machine mới, tạo Goal, nhập success criteria/evidence và
  giữ Projects/board/list/timeline/calendar/AI monitor hiện có.

## Migration và backup

Migration `0022` chuyển trạng thái cũ theo ánh xạ:

| Cũ | Mới |
|---|---|
| backlog | draft |
| todo | ready |
| in_progress | running |
| review | waiting_approval |
| done | completed |

Dependency JSON cũ được backfill sang bảng chuẩn hóa. Backup và restore-test đạt
cho `apex`, `temporal` và `temporal_visibility` trước khi nâng DB. Báo cáo máy đọc
được: `.runtime/stage-3-migration.json`.

| Database | Backup | Restore |
|---|---:|---|
| apex | 317.399 byte | đạt, 62 bảng trước migration |
| temporal | 92.052 byte | đạt, 39 bảng |
| temporal_visibility | 46.043 byte | đạt, 3 bảng |

DB hiện ở `0022`; 61 bảng ứng dụng cũ giữ nguyên số dòng và ba bảng mới được
thêm, thành 64 bảng ứng dụng/65 bảng public khi tính `alembic_version`.

## Nghiệm thu

- Backend: 182 tests dự kiến ở lượt chốt cuối.
- Migration roundtrip `base → 0022`: đạt.
- Chuỗi Goal có ba task phụ thuộc và ba attempt: đạt.
- Completion thiếu evidence, dependency chưa xong, parent chưa xong: bị chặn.
- Attempt replay cùng key/input: trả cùng attempt; khác input: 409.
- Cancel/retry và late-result guard: đạt.
- Workspace isolation và version conflict: giữ nguyên.
- Runtime/SSE: 8/8.
- Frontend production build: đạt.
- Browser acceptance: 12/12 route.
- Health: API/ready/web 200; 101 OpenAPI paths; mọi process alive.

## Giới hạn chuyển sang M2

- Chưa có Skill Registry/version/hash/evaluator.
- Chưa có scheduler tự chọn skill và thực thi task AI.
- UI tạo Goal và quản lý Task cơ bản; chưa có graph dependency trực quan.
- Evidence hiện là reference có cấu trúc do API/worker cung cấp; chưa có object
  storage hoặc cơ chế ký artifact.
