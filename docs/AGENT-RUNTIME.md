# PAO Agent Runtime — Phase 4

Chief là điểm vào của mọi yêu cầu. Planner tạo kế hoạch JSON, router xác thực, runtime thực thi từng specialist theo thứ tự rồi Chief tổng hợp. Không tạo service riêng cho từng agent.

## Agent hiện có

| Agent | Nhiệm vụ |
|---|---|
| Chief of Staff | Điều phối, kiểm tra tính nhất quán và trả lời cuối |
| Researcher | Phân tích thông tin được cung cấp; nêu giả định và dữ liệu còn thiếu |
| Editor | Biên tập, tóm tắt, viết lại nội dung |
| Marketing | Đề xuất chiến lược, đối tượng và nội dung marketing từ context |

Registry nằm trong `packages/agent-config/*.json`, được Pydantic kiểm tra khi khởi động; mỗi cấu hình có key/name/prompt_version/system_prompt. Sửa cấu hình cần restart API/worker. Chưa có giao diện chỉnh prompt hoặc triển khai cấu hình nóng. Các node còn lại giữ compatibility với UI gốc nhưng không được nhận là agent thực thi. Memory vẫn là dịch vụ, không phải specialist độc lập.

Researcher chưa tìm kiếm web. Marketing chưa đọc tài khoản quảng cáo hay thực hiện hành động. Registry API trả tools rỗng. Tool Gateway thuộc Phase 5.

## Planner và router

Planner prompt version `1.0.0`; dùng structured JSON qua gateway, không hiển thị private reasoning. Kế hoạch gồm goal và 0–2 steps; agent chỉ là researcher/editor/marketing. Task tối đa 400 ký tự; không lặp specialist. depends_on chỉ trỏ bước trước, nên không có chu trình hoặc tự gọi lặp.

Yêu cầu đơn giản/ghi nhớ có thể có 0 bước. Planner không hợp lệ hoặc provider planner lỗi sẽ phát `plan.failed`, lưu fallback và để Chief trả lời trực tiếp. Fallback chỉ cho planner; specialist lỗi làm run thất bại, không tiếp tục các bước phụ thuộc hoặc tự tuyên bố hoàn thành.

Hai bước không phụ thuộc vẫn chạy tuần tự để phù hợp RAM/CPU. Specialist chỉ nhận kết quả của dependency được chỉ định. Context hội thoại và Memory đã được lọc theo session trước khi giao việc; model không tự chọn workspace/user/brand.

## Giới hạn và trạng thái

```dotenv
AGENT_RUNTIME_ENABLED=true
AGENT_RUN_TIMEOUT_SECONDS=600
```

Tắt `AGENT_RUNTIME_ENABLED` đưa run mới về đường Chief trực tiếp. Restart cả API/worker khi đổi cấu hình. Khi bật, tổng budget mặc định 600 giây; provider call vẫn chịu timeout riêng, planner tối đa 90 giây theo HTTP timeout. Worker max_jobs=1, không gọi song song nhiều model.

Specialist dùng tối đa 256 output tokens, tối đa 6000 ký tự output được lưu; chuyển tối đa 2000 ký tự mỗi kết quả sang dependency/Chief. Chief dùng OUTPUT_TOKENS hiện có. Dữ liệu từ specialist được coi là reference không đáng tin cậy, không đưa vào system instruction. Kiểm tra chất lượng là phần tổng hợp của Chief, không phải bảo đảm mọi kết luận đúng hoặc hệ thống fact-check độc lập.

Cancel, timeout hoặc revoke quyền dừng tác vụ đang chạy và không bắt đầu bước tiếp theo. Run stale sau restart được kết thúc failed; không tự replay các bước đã chạy. Các bước đã completed giữ kết quả; bước đang chạy giữ partial output và trạng thái lỗi/hủy. Chỉ final output của Chief đi vào response.delta và lịch sử hội thoại. Extraction Memory vẫn chỉ lấy prompt gốc của người dùng.

Chief được đánh dấu đang hoạt động trong toàn bộ run vì giữ vai trò điều phối; khi specialist chạy, hai node có thể cùng sáng. Điều này không có nghĩa có hai lượt inference song song.

## API / UI

- `GET /v1/agents`: cần đăng nhập, trả registry triển khai và trạng thái enabled.
- `GET /v1/runs/{id}/execution`: chỉ chủ hội thoại có quyền workspace đọc được; trả plan và agent_runs có task/output/status/model/prompt_version/usage.
- SSE thêm plan.started/plan.created/plan.failed; agent lifecycle có key và agent_run_id cho specialist. Các event cũ vẫn đọc được.
- Mở **Kế hoạch và kết quả agent** để xem task, dependency và output từng bước. UI đọc snapshot định kỳ khi run đang hoạt động; khi mở lại hội thoại, hiển thị execution của lượt cuối. Không có dashboard quản lý mọi run trong phase này.

Ví dụ: “Nhờ Researcher phân tích dữ liệu sau, rồi Editor viết báo cáo ngắn dựa trên kết quả đó. Dữ liệu: 100 lượt xem, 5 đơn hàng, chưa có chi phí hoặc doanh thu. Chief trả lời trong hai câu.”

## Migration và kiểm thử

Revision 0003 thêm Run.execution_plan; agent_runs bỏ unique run_id, thêm unique(run_id, step_index), task/output/finished_at. Chief cũ giữ step_index=0, dữ liệu hội thoại không bị chuyển đổi/xóa. Có thể xem metadata các lượt cũ nhưng không tự dựng lại kế hoạch chưa từng tồn tại.

Sao lưu DB và dừng API/worker trước upgrade. Downgrade 0003 chủ động từ chối nếu đã có run nhiều agent để không loại bỏ lịch sử bước. Khi cần rollback cài đặt có dữ liệu như vậy, dùng kế hoạch restore bản backup tương ứng; không xóa bảng/volume để ép downgrade.

```powershell
.venv/Scripts/python.exe scripts/test_backend.py --roundtrip
npm run test:runtime
npm run build
npm run test:frontend
.venv/Scripts/python.exe scripts/verify_agents_local.py
```

Backend tests truncate pao_test, không chạy cùng lúc với acceptance model thật. Roundtrip cần database test không có lịch sử nhiều agent, hoặc phải tạo database test sạch có chủ đích. `verify_agents_local.py` chỉ tạo dữ liệu giả trong pao_test, chạy planner/specialists/Chief thật và lưu `.runtime/phase-4-local-acceptance.json`. Browser test dùng API giả lập để kiểm tra UI/replay/cancel/logout, không dùng tài khoản thật.
