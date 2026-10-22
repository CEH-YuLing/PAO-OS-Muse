# Phase 4 — Agent Runtime

Theo mục 130 của master spec: Registry, Chief, Planner, Router, Researcher, Editor, Marketing. Agent là cấu hình trong cùng backend; chưa thêm service/tool gateway/18 agent/Ads.

Planner trả JSON goal + tối đa 2 steps, mỗi step gồm agent/task/depends_on. Chỉ 3 specialist được phép, không lặp agent, dependencies chỉ trỏ bước trước. Router xác thực kế hoạch trước thực thi; kế hoạch không hợp lệ hoặc planner lỗi chuyển Chief trả lời trực tiếp và ghi sự kiện fallback.

Thực thi tuần tự trên cùng Ollama CPU. Mỗi specialist có prompt version, usage, output và trạng thái lưu bền trong agent_runs; Chief tổng hợp output như dữ liệu không đáng tin cậy, không chuyển output thành system instruction. Chỉ câu trả lời Chief stream vào hội thoại; UI xem riêng kế hoạch và kết quả các bước, không hiển thị private reasoning.

Memory retrieval giữ nguyên scope của session; specialist nhận context đã lọc và kết quả dependency được chỉ định. Memory extraction chỉ từ prompt người dùng sau run hoàn tất. Không tự gọi tools/web/ghi ngoài hệ thống.

Run budget tối đa 600 giây khi bật Phase 4; mỗi provider call vẫn có timeout riêng. Tối đa 2 specialist, output/context giới hạn; worker vẫn max_jobs=1. Cancel/timeout/restart đóng toàn bộ agent đang chạy, không chạy bước tiếp theo sau revoke/cancel. Không replay bước thất bại để tránh nhân đôi thực thi; stale run thất bại rõ ràng.

Migration 0003 bỏ unique run_id của agent_runs, thêm unique(run_id, step_index), task/output/finished_at và Run.execution_plan. Dữ liệu Chief cũ giữ step_index=0. API registry và execution snapshot kiểm tra đăng nhập/ownership; frontend cập nhật node thực thi và trace từ server.

Trình tự: registry/planner/schema → runtime và tests → frontend/contracts/build/browser → backup/migration local → acceptance model thật. Chỉ nghiệm thu sau khi luồng delegation, fallback, cancel, scope và regression đạt.
