# Phase 4 — Agent Runtime: nghiệm thu local

Ngày 13/09/2026. Phạm vi theo mục 130 master spec: Registry, Chief, Planner, Router, Researcher, Editor, Marketing. Chưa mở Phase 5/Tool Gateway/Ads.

## Đã triển khai

- Registry cấu hình và phiên bản prompt cho bốn agent; endpoint có xác thực. Các agent dùng chung gateway/runtime, không tạo thêm service.
- Planner structured JSON, router chặn agent ngoài danh sách, chu trình, dependency không hợp lệ, lặp agent hoặc quá hai bước. Planner lỗi có fallback Chief trực tiếp, trạng thái thể hiện trên UI.
- Specialist chạy tuần tự, nhận đúng dependency và Memory đã lọc theo session. Chief tổng hợp; chỉ response Chief vào hội thoại, kết quả specialist lưu riêng. Memory extraction vẫn dựa vào prompt người dùng.
- Mỗi bước lưu task, output/partial output, model, prompt_version, usage, trạng thái và thời điểm kết thúc. Cancel/revocation/lỗi dừng các bước tiếp theo; giữ kết quả bước đã hoàn thành.
- UI registry/active nodes và bảng **Kế hoạch và kết quả agent**; snapshot có kiểm tra quyền sở hữu, refresh/replay không trộn session. Memory vẫn là dịch vụ, các node chưa triển khai không được báo là đang thực thi.

## Kiểm chứng

- **42 backend tests đạt**, gồm 27 tests nền/Memory và 15 tests Phase 4. Kiểm tra chuỗi Researcher→Editor→Chief, Marketing, dependency độc lập, final-only streaming, quyền xem execution, scope Memory, planner fallback, cancel/revocation, lỗi specialist/Chief và bảo vệ lịch sử khi downgrade.
- Migration roundtrip trong **pao_test** và Alembic schema check đạt. Migration từ chối downgrade nếu đã có lịch sử nhiều agent, thay vì xóa bước để ép unique cũ.
- **8 Node runtime tests đạt**; production build/TypeScript đạt.
- Browser Edge headless với API giả lập đạt: planner, highlight Researcher rồi Editor, kết quả từng bước, final synthesis; toàn bộ regression lifecycle/reconnect/failure/cancel/session/reload/logout/token expiry và Memory CRUD/brand isolation. Không có pageerror. Đã xem ảnh `.runtime/phase-4-browser.png`.
- **Model thật đạt** với qwen3:4b-instruct-2507-q4_K_M trên CPU, dữ liệu giả lập trong pao_test. Planner tạo đúng Researcher→Editor phụ thuộc bước 0; cả hai specialist và Chief completed. Chief kết luận 5 đơn/100 lượt xem tương ứng 5%, đồng thời nêu thiếu doanh thu/chi phí để đánh giá tài chính. Không gọi web hoặc tài khoản Ads. Tổng thời gian ca thử **144,1 giây**, không phải benchmark chung.

Artifact model thật: `.runtime/phase-4-local-acceptance.json`; script tái lập: `scripts/verify_agents_local.py`. Kiểm thử browser dùng mock chỉ chứng minh UI; bằng chứng inference thật là ca riêng nói trên.

## Dữ liệu và triển khai

Database chính nâng từ 0002 lên **0003**, có backup `.runtime/pre-phase-4-20260913.dump` (53.737 byte, pg_restore đọc được). Đối chiếu trước/sau:

| Bảng | Trước | Sau |
|---|---:|---:|
| users | 1 | 1 |
| sessions | 3 | 3 |
| messages | 23 | 23 |
| runs | 12 | 12 |
| agent_runs | 12 | 12 |
| memories | 0 | 0 |

Chief cũ giữ step_index=0; không tạo kế hoạch giả cho lịch sử. Tài khoản/mật khẩu không đổi, không backfill hội thoại hoặc nhập dữ liệu test vào database chính. Số liệu lưu tại `.runtime/phase-4-migration.json`.

Docker gặp lại lỗi socket sau phiên bị dừng: đã xác minh và đổi tên dự phòng ba file socket rỗng trước khi khởi động lại; không factory reset hoặc xóa volume. Các container được phục hồi và migration hoàn tất.

## Giới hạn và cách sử dụng

Planner không bảo đảm luôn chọn specialist tối ưu. Tối đa hai specialist, chạy tuần tự; tổng run timeout mặc định 600 giây. Researcher chỉ phân tích tài liệu/context được cung cấp, Marketing không đọc/ghi tài khoản Ads. Kiểm tra chất lượng do Chief thực hiện, chưa có fact-check độc lập. GPU chưa được nghiệm thu.

Mở http://127.0.0.1:3100/, tải lại trang và đăng nhập. Ví dụ: “Nhờ Researcher phân tích dữ liệu này rồi Editor viết báo cáo ngắn dựa trên kết quả.” Mở **Kế hoạch và kết quả agent** để theo dõi.

Xem [hướng dẫn Agent Runtime](AGENT-RUNTIME.md) và [kế hoạch Phase 4](PHASE-4-PLAN.md). Phase tiếp theo là **Phase 5 — Tool Gateway**, chưa triển khai trong đợt này.
