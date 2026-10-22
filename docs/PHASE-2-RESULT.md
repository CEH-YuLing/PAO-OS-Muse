# Phase 2 — Frontend runtime: kết quả nghiệm thu

Ngày 12/09/2026. Phạm vi chỉ frontend runtime và bổ sung observable events cần thiết ở backend. Không triển khai Memory, multi-agent planner, tool gateway, Telegram hoặc Ads.

## Những gì đã thay đổi

- Hook `usePaoRuntime` dùng projection/reducer theo run_id và sequence; state: standby, listening (dự phòng), processing, reasoning, speaking. Animation gốc dùng adapter, không cần viết lại Orb/Three.js.
- Backend thêm core.reasoning khi context sẵn sàng/model bắt đầu, core.speaking trước delta đầu, response.completed khi thành công, core.standby khi kết thúc. Reasoning là giai đoạn thực thi quan sát được, không chứa chain-of-thought. Không phát listening giả khi chưa có voice.
- activeAgents lấy từ agent.started/completed/failed/cancelled, không suy từ Orb. ReasoningWeb giữ node đang chạy sáng đến khi có sự kiện kết thúc, dừng highlight khi terminal; không tạo đường phối hợp giữa các agent giả, không chạy hạt hoạt động tới các node chưa thực thi.
- Production Orb không đổi state khi click. Hiển thị nhãn giai đoạn, trạng thái kết nối và danh sách agent đang thực thi. Card Chief phản ánh hoạt động ở run đang xem; card agent khác ghi rõ chưa triển khai, không nhận là online/integrated. Đây chưa phải Agent Cockpit API ở các phase sau.
- Kết nối phân biệt connecting/connected/reconnecting/disconnected/idle. Reconnect tự động có giới hạn/backoff, sau đó cho reconnect thủ công; replay không nhân đôi text. Nếu mất kết nối, UI nói rõ trạng thái gần nhất.
- Reload/chọn lại session lấy active_run và replay. Epoch/AbortController ngăn kết quả cũ ghi vào session mới hoặc sau logout. Hết hạn token xóa identity/runtime, yêu cầu đăng nhập lại; draft được xóa khi đổi identity.
- Lỗi/hủy giữ partial response, terminal giải phóng highlight. Trạng thái terminal từ API ưu tiên hơn SSE cũ khi mất kết nối.

## API và database

Không thêm endpoint và không migration. Mở rộng EventOut/RunEvent và sinh lại OpenAPI → TypeScript. Dữ liệu sự kiện Phase 1 cũ vẫn đọc được nhờ fallback agent.started/response.delta/run terminal.

Không thêm biến môi trường vận hành. Provider và profile CPU giữ nguyên. Playwright là devDependency phục vụ test; `PAO_TEST_WEB_URL` và `PAO_TEST_BROWSER_CHANNEL` chỉ là tùy chọn cho browser test.

## Kiểm thử

- 12 backend integration/gateway tests đạt: PostgreSQL/Redis thật, provider giả lập. Kiểm tra thêm chính xác thứ tự lifecycle events; không phát speaking khi model lỗi trước output; cancelled không có response.completed và phải về standby.
- 8 Node tests đạt: 6 projection/lifecycle/replay/agent tests và 2 SSE decoder tests.
- Browser acceptance trên Edge headless, reduced-motion, dùng API HTTP giả lập cô lập: lifecycle và đúng một node Chief; ngắt/replay có duplicate; failure; partial cancel; đổi session; reload active run; hết retry và reconnect thủ công; logout khi request còn chờ; token hết hạn. Không có pageerror.
- Production build/typecheck đạt. Bộ browser test chạy trên bản production local.

Cảnh báo đã biết: pytest không ghi được thư mục cache cũ do quyền NTFS; assertions vẫn pass. Browser acceptance dùng fixture, không phải một lần gọi model thật mới. Bằng chứng model thật CPU của Phase 1 được giữ riêng; không tuyên bố GPU đạt hoặc system production-ready.

## Chạy lại kiểm thử

Từ repo root, máy đã thiết lập theo LOCAL-DEVELOPMENT.md:

```powershell
npm ci
.venv/Scripts/python.exe scripts/export_openapi.py
npm run contracts
.venv/Scripts/python.exe scripts/test_backend.py
npm run test:runtime
npm run build
./scripts/start_local.ps1
npm run test:frontend
```

Backend test chỉ dùng `pao_test` và Redis DB 15; không dùng database ứng dụng. Browser test tạo server fixture trên cổng ngẫu nhiên rồi rewrite `/v1` chỉ trong browser test, không đăng nhập hay ghi dữ liệu người dùng. Trên Windows mặc định dùng Edge đã cài; hệ điều hành khác cần `npx playwright install chromium`. Screenshot kiểm chứng nằm trong `.runtime/phase-2-browser.png` (ignored).

Sau đổi code cần dừng các PID API/worker/web dự án rồi chạy lại script; `start_local.ps1` tái dùng PID còn sống và không tự reload code. Không dừng Docker/Ollama hoặc xóa volumes chỉ để cập nhật frontend.

## Nghiệm thu thủ công

1. Mở PAO local, đăng nhập bằng tài khoản hiện có, tạo/chọn hội thoại.
2. Gửi yêu cầu: processing → reasoning → speaking → standby; chỉ Chief sáng theo sự kiện. Giai đoạn rất ngắn có thể được React gộp render, không thêm thời gian chờ giả để kéo dài hiệu ứng.
3. Hủy yêu cầu khi đang trả lời: trạng thái cancelled, phần đã sinh vẫn được lưu.
4. Reload/đăng nhập lại/chọn active session: đồng bộ lại text và trạng thái; không trùng output.
5. Đổi hội thoại hoặc logout trong khi đang chạy: màn hình mới không nhận text từ session cũ; logout không đồng nghĩa hủy job backend.

Phase 2 hoàn thành trong phạm vi trên. Phase 3 chưa bắt đầu. Listening/voice, tools/approvals, agent registry và dynamic status API không được giả lập là đã có.
