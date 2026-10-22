# Phase 2 — Frontend runtime

Phạm vi: chuẩn hóa observable runtime và biểu diễn UI cho một Chief hiện có. Không triển khai Memory, agent registry/planner, tool execution, Ads hoặc voice.

## Thiết kế

- Backend phát core.processing khi chuẩn bị context, core.reasoning khi bắt đầu gọi model, core.speaking trước delta đầu tiên, response.completed khi thành công và core.standby trước run terminal. Reasoning chỉ là nhãn giai đoạn thực thi, không chứa private chain-of-thought. Listening dành cho khả năng tương lai, không giả lập microphone.
- Runtime state tách khỏi visual state: standby/listening/processing/reasoning/speaking; adapter giữ animation cũ. Không dùng tap-cycle trong đường chạy production.
- Pure event reducer giữ cursor, response, trace, active agent keys từ agent.started/completed/failed/cancelled; bỏ duplicate và foreign-run events. Terminal luôn xóa hoạt động agent.
- Hook quản lý kết nối connecting/connected/reconnecting/disconnected/idle; khôi phục bằng replay và dữ liệu DB; ngăn response cũ cập nhật session mới hoặc sau logout.
- ReasoningWeb dùng danh sách active agent thực, không suy từ trạng thái Orb và không tạo đường delegation giả. Có nhãn trạng thái và danh sách active agent cho người dùng đọc được.

## Files và API/database

Sửa runtime.py, schemas.py, contracts; thêm runtime-state.mjs và declaration/tests; sửa usePaoRuntime, PaoConsole, PaoWorld, ReasoningWeb. API URL giữ nguyên. Event types mở rộng tương thích, không migration, không đổi dữ liệu cũ.

## Kiểm chứng và rủi ro

Test reducer: lifecycle, lỗi/hủy, replay/duplicate, run isolation, active agent đúng event. Integration test: thứ tự event, terminal idle, không speaking khi lỗi trước output. Build/typecheck và kiểm thử foundation; smoke local. Rà soát race khi đổi session/logout/reconnect, partial response và old persisted events không có core states mới. Phải dừng API/worker dự án trước khi restart code, không đụng dữ liệu người dùng. Báo rõ giới hạn kiểm chứng browser/model nếu có.
