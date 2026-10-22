# Stage J — Automation

Route `/automation` sử dụng Temporal status và workflow projection hiện có.

## Khu vực

1. Overview: KPI, activity và runtime boundaries.
2. Workflow Runs: trạng thái, approval, timer, version và cancel.
3. Approvals: owner/admin gửi signal approve hoặc reject theo workflow version.
4. Schedules: durable timer đang chờ trong Temporal.

UI chỉ cho phép `approval_wait` và `follow_up`, đúng allowlist backend. Automation không thực hiện provider write.
