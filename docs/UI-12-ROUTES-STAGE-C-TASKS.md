# Stage C — Tasks & Projects

## Phạm vi đã triển khai

- Route độc lập `/tasks` dùng chung PAO App Shell, phiên đăng nhập và Ask PAO.
- Năm chế độ xem: Board, List, Timeline, Calendar và AI Tasks.
- Project và task lấy từ API thật; không chèn dữ liệu mẫu vào production.
- Tạo project, tạo task, cập nhật trạng thái/tiến độ/ưu tiên/deadline.
- Task detail có mô tả, phân công, liên kết run, bình luận và activity log.
- Dashboard đọc task API để hiển thị tổng số task mở, đang thực hiện và task AI/agent.

## Backend

- Migration `0018_tasks_projects.py` tạo `projects`, `tasks`, `task_comments`, `task_activity`.
- Mọi truy vấn được giới hạn theo workspace membership.
- Viewer chỉ đọc; operator trở lên có thể ghi.
- Update dùng `version` để phát hiện ghi đè đồng thời.
- Dependency được kiểm tra cùng workspace, tự tham chiếu và vòng lặp.
- Task do PAO/agent có thể liên kết với một runtime run trong cùng workspace.

## API

- `GET/POST /v1/projects`
- `PATCH /v1/projects/{project_id}`
- `GET/POST /v1/tasks`
- `GET/PATCH /v1/tasks/{task_id}`
- `GET/POST /v1/tasks/{task_id}/comments`
- `GET /v1/tasks/{task_id}/activity`

## Kiểm tra

- Backend task tests: 3 passed.
- Toàn bộ backend: 159 passed.
- Runtime/SSE frontend: 8 passed.
- Browser acceptance: Orb, 12 routes, auth persistence, Dashboard, PAO AI và Tasks đạt.
- Next production build: 17/17 static/dynamic routes build thành công.

Ảnh kiểm tra: `.runtime/workspace-tasks-route-1920.png`.
