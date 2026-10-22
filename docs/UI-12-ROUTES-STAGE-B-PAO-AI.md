# PAO — Trang PAO AI

Ngày triển khai: 25/09/2026.

## Phạm vi hoàn thành

- Route độc lập /pao-ai trong App Shell chung.
- Danh sách hội thoại và tạo hội thoại mới.
- Tự chọn hội thoại gần nhất và tải lịch sử từ backend.
- Vùng hội thoại hiển thị message đã lưu và response SSE đang streaming.
- Các chế độ Ask, Analyze, Plan, Execute và Research.
- Tám quick command theo đặc tả sản phẩm.
- Composer hỗ trợ Enter để gửi, Shift+Enter xuống dòng, cancel run và trạng thái active agent.
- Ask PAO ở topbar chuyển câu lệnh sang composer PAO AI, kể cả khi đang ở chính route PAO AI.
- Context Inspector hiển thị workspace, session, memory, run, agent và các layer kết nối.
- Activity Inspector tái sử dụng ExecutionPanel, ToolPanel, MemoryPanel và VoicePanel hiện có.
- Giao diện responsive; màn hình nhỏ ưu tiên vùng hội thoại.

## Nguyên tắc tích hợp

- Không tạo runtime chat mới.
- Tái sử dụng usePaoRuntime và SSE state machine hiện có.
- Hội thoại, run, message, tool approval, memory và voice vẫn dùng API hiện tại.
- Mode được ghi vào prompt để backend có ngữ cảnh thực thi rõ ràng.
- Hành động quan trọng vẫn đi qua Tool Gateway và approval.

## Kiểm thử chấp nhận

- Route PAO AI dùng chung phiên đăng nhập với Dashboard.
- Tự tải session và message hiện có.
- Có đủ năm mode, composer, context và quick commands.
- Orb, Dashboard và module scaffold không bị regression.
- Runtime/SSE test tiếp tục đạt.

## Bước kế tiếp

Triển khai Tasks & Projects với các view Board, List, Timeline, Calendar và AI Tasks. Backend hiện chưa có task/project domain hoàn chỉnh nên cần chốt contract và migration trước khi nối UI.
