# Quy tắc làm việc dành cho Muse Code

Đọc AGENTS.md trước. Đây là fork độc lập ở G:, không phải thư mục nguồn ở F:.
Tài liệu lịch sử có thể nói "đã cài/đã chạy" nhưng đó là bản nguồn vào ngày ghi
biên bản. Không dùng lịch sử đó để tuyên bố fork đã đăng nhập AI hoặc đủ dữ liệu.

## Kiến trúc và điểm bắt đầu

- `apps/web/app`, `apps/web/components/workspace`, `apps/web/lib`: Next.js15/
  React19/TypeScript; UI Việt, dark/light/auto, Settings và PAO AI.
- `apps/api/pao/app.py`: ghép router/lifespan; `core_api.py`: auth/session/run/SSE.
- `runtime.py`, `agents.py`: ARQ và điều phối hiện có. Không thêm runner thứ hai.
- `modules/chat`: policy/context/ledger/compaction/usage/privacy; token provider-mode.
- `gateway.py`, `model_router.py`, `modules/engines`, `modules/installation_ai`:
  provider transports, catalog/model/effort, nguồn AI chung, immutable pins.
- `modules/cli_connections`: native Codex, Muse profile/client/execution, Antigravity.
  `packages/cli-runtime`: giao thức và containment Codex. Không tự sửa pin/image.
- `modules/business_planning`: hồ sơ/plan/review/job/routing/report.
- `modules/studio`, `modules/goals`, `modules/schedules`: định nghĩa/version,
  workflow/Goal; trạng thái local không đồng nghĩa autonomous production.
- `modules/brains`, `modules/knowledge`: dữ liệu có scope; không đọc chéo doanh nghiệp.
- `modules/channels`, `modules/connections`, `integrations`: connector/quyền/secret.
- `models.py`, `migrations/versions`: PostgreSQL schema0077; không tạo bảng tay.
- `packages/contracts`: OpenAPI/TypeScript; cập nhật cùng backend khi đổi API.
- `packages/skill-config`, `packages/agent-config`, `evals`: cấu hình/đánh giá có phiên bản.

## Chu trình một thay đổi

1. Đối chiếu roadmap và code; ghi rõ gap, scope, rủi ro và tiêu chí hoàn thành.
2. Tạo checkpoint trong fork trước khi migration hay thao tác dữ liệu rủi ro.
3. Giữ API/DTO/SSE tương thích, runtime dùng một nguồn ledger, không hardcode vendor theo vai trò.
4. Implement toàn bộ phase đã duyệt theo checkpoint tuần tự; báo tiến độ ngắn.
5. Test mock không provider trước; chỉ thử quota/model thật khi chủ cho phép rõ.
6. Kiểm tra UI desktop/mobile, network failure, lost ACK, retry/cancel, SME isolation.
7. Ghi lệnh thực chạy, số test và giới hạn nghiệm thu. Bảo toàn receipt failed.
8. Cập nhật roadmap duy nhất, không tạo roadmap mâu thuẫn hoặc tự đánh dấu production.

## Chạy test an toàn

Không chạy các script operator lịch sử chỉ vì chúng có trong scripts/. Rất nhiều
script còn hardcode F:/PAO-ACOS,8100,3200,15432 hoặc source container. Đọc trước.

Test unit độc lập điển hình:

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s scripts -p test_muse_execution.py
.\.venv\Scripts\python.exe -B -m unittest discover -s scripts -p test_muse_client.py
node --test apps/web/lib/run-failure-message.test.mjs
```

Backend integration cần `PAO_TEST_DATABASE_URL` là DB pao_test ở25432 và Redis15
ở26379; kiểm tra guard và migrate DB test0077 trước. Tests có TRUNCATE nên không
đặt URL vào pao_muse_local hay pao_acos_local. Không gọi full pytest mặc định.
Không chạy test song song trên cùng test DB/Redis. Native containment tests có
thể cần dependency dev đặc thù; chưa cài là thiếu môi trường, không sửa assertion.

## Những điều không được ngộ nhận

- Có binary/login/catalog không chứng minh inference/quota hoặc mọi model chạy được.
- Muse là Meta Muse Code client, không phải dịch vụ tạo ảnh cùng tên.
- Kết nối CLI không cấp quyền công cụ. Bỏ token cap không cấp cloud reference/memory.
- Nhà cung cấp vẫn có context/hạn mức; byte envelopes/timeout/call limits vẫn cần.
- Muse text adapter còn buffered output và overhead~14k input; codec pin1.4.10.
- Codex personal đã có nhiều model trong nguồn, shared identity là gate khác.
- Claude Code đã hoãn vì chưa thuê bao. Antigravity chưa có text inference accepted.
- UI sáng tạo/Ads hiện hữu không đồng nghĩa đã có ảnh/video, CRM hay publishing đầy đủ.

## Nhiệm vụ đầu tiên gợi ý

Chỉ audit fork, kiểm tra baseline G: và đề xuất một gói GD01 kế tiếp. Không triển
khai ngay feature rộng. Ưu tiên tối ưu Muse/context lớn, quan sát lỗi/usage,
hoàn thiện đường provider/model/effort hiện có; sau contract GD01 mới làm GD02 realtime.
Chủ sở hữu sẽ chọn nhánh thử nghiệm, không tự đổi kiến trúc/provider hoặc chi phí.
