# M2 — Resource guard cho Chief command

Ngày 05/10/2026; target `F:\PAO-ACOS`. Checkpoint đạt cho ba command
read-only, chưa nghiệm thu toàn bộ M2 và chưa chuyển sang dữ liệu thật M3.

## Đã triển khai

- Ghi snapshot trước khi chạy; deadline là giá trị nhỏ hơn giữa timeout trong
  snapshot và run timeout cấu hình. Thay registry giữa chừng không kéo dài deadline.
- Tối đa hai tools, không trùng lặp; kiểm allowlist snapshot trước dispatch.
- Response tối đa 32000 ký tự; vượt cap phải failed, không truncate-success.
- Ghi resource_guard trong execution plan. Các command không gọi LLM trong
  bước tổng hợp, nên llm_generated_tokens bằng 0, không phải bộ đếm token chung.
- Lỗi riêng: skill_timeout, skill_tool_budget, skill_output_budget.

## Kiểm chứng

- Backend toàn bộ: **243/243**, 108.99 giây, database `pao_test` riêng.
- Bốn test mới: pinned timeout trước tool thứ hai; vượt số tools trước dispatch;
  vượt output không tạo success; hết deadline khi read đang chạy.
- Khi read bị ngắt, call chuyển unknown/execution_interrupted; không giữ running
  và không tự retry. Unknown cần xử lý theo cơ chế recovery, không phải completed.
- Runtime/SSE **8/8**; live API → ARQ cả ba command đạt, resource_guard đúng,
  mỗi run hai durable tools và skill_result insufficient_data.
- Live catalog/preflight/ba previews trên desktop/mobile đạt.
- Browser regression 12 màn hình với API mock đạt; API /ready và Web /skills
  đều HTTP 200.
- Không sửa frontend; không chạy lại production build (đã đạt checkpoint trước).
- Không migration mới, database vẫn 0023. Dự án gốc `F:\Apex\apex` không sửa.

Live demo runs (memory tắt):

- Daily: 1439a1a5-50f8-4f1e-997c-8e334a68c3b7.
- Ads: 80e849c2-cc41-4834-80ea-e8940288201d.
- Creative: d0ed25f3-e301-404e-8bd5-a91292d34ace.

Chỉ restart API/worker sau idle check 0 jobs; smoke ghi hội thoại/run/audit
demo. Không bật Ads API, Telegram, email hoặc thay dữ liệu nghiệp vụ thật.

## Giới hạn và bước tiếp theo

Deadline bao phủ bước generate command, gồm plan/tools/tổng hợp/lưu response;
không bao phủ thời gian xếp hàng, claim ban đầu hoặc cleanup sau timeout.
Preview riêng vẫn dùng timeout 10s. Token budget cho skill LLM tương lai chưa
được cưỡng chế; memory extraction sau run là luồng riêng, không nằm trong guard.

Tests interruption trong checkpoint resource dùng fixture, không phải OS
kill/restart hoặc load test. Checkpoint tiếp theo đã thêm
[OS-process recovery harness](M2-PROCESS-RECOVERY-2026-10-05.vi.md), có clock
lease mô phỏng; không phải nghiệm thu toàn stack ARQ/Redis.
Chưa có executable-version archive để replay code cũ; worker stale recovery
vẫn theo timeout cấu hình chung. Bước kế tiếp hiện hành: policy tương thích
version và attribution read-only trước khi mở rộng M3.
