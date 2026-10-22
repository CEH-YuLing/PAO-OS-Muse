# PAO-ACOS — Checkpoint nền móng Skill Registry

Ngày kiểm tra: 05/10/2026. Dự án triển khai: `F:\PAO-ACOS`.
Đây là bước đầu của M2, không phải nghiệm thu toàn bộ M2.

## Đã triển khai

- Ba manifest phiên bản `1.0.0`: `daily-business-brief`,
  `investigate-ads-drop`, `creative-fatigue-review` trong `packages/skill-config`.
- Registry chỉ nạp danh sách file cố định; không tải hoặc chạy code skill ngoài.
- Input/output schema, agent/tool allowlist, permission, approval class,
  timeout/token budget và evaluator ID được đưa vào snapshot SHA-256.
- API catalog và preflight yêu cầu đăng nhập và membership đúng workspace.
  Input sai bị từ chối; agent/tool ngoài allowlist không được chấp nhận.
- TaskAttempt lưu snapshot tại lúc tạo. Replay cùng request key giữ bản cũ,
  không chuyển sang manifest mới. Attempt cũ không gắn skill vẫn tương thích.
- Attempt gắn skill không được completed nếu kết quả sai cấu trúc hoặc thiếu
  source references. `insufficient_data` phải ghi là attempt failed, không
  được coi là hoàn thành. Completed vẫn đi qua quy trình approval hiện có.
- Trang `/skills` hiển thị ba contract, quyền và hash; nói rõ chưa tự thực thi.
- OpenAPI và TypeScript contracts đã cập nhật.

## Bằng chứng kiểm tra

| Kiểm tra | Kết quả |
|---|---|
| Backend regression, database `pao_test`, migration roundtrip | 189/189 đạt |
| Runtime/SSE | 8/8 đạt |
| Production frontend build | Đạt, 18 routes, gồm `/skills` |
| Browser regression 12 màn hình với API mock | Đạt |
| Skills acceptance với API demo thật | Catalog, preflight, desktop/mobile đạt |
| API `/ready`, Web `/skills` sau restart | HTTP 200 |
| Database demo | Revision `0023` |
| Git nguồn `F:\Apex\apex` | Không có thay đổi |

Trước migration đã kiểm tra không có run/tool-call queued hoặc running,
sao lưu database riêng vào `.runtime/acos-pre0023-20261005-133838.dump`,
và đọc được mục lục 540 entries bằng `pg_restore --list`.
Đây là kiểm tra định dạng backup, **chưa phải restore drill**.
API/ARQ/Web được restart; Ollama đang chạy được giữ lại.

## Giới hạn cần hiểu rõ

- Bốn tên business tool chỉ mới là contract allowlist, chưa đăng ký execution.
- Preflight luôn trả `execution_available: false`. Chief chưa tự chọn skill.
- Chưa đưa dữ liệu Ads/CRM thật vào skill; không gửi Telegram hoặc bật quảng cáo.
- Timeout/token budget chưa phải giới hạn được runtime cưỡng chế.
- Evaluator `source-result-v1` chỉ kiểm cấu trúc, hash và sự có mặt của nguồn;
  chưa xác minh nguồn tồn tại, đúng workspace, hay nội dung kết luận chính xác.
- Contract/evaluator ID đã pin phải giữ nguyên nghĩa; thay đổi không tương thích
  cần ID/version mới và kiểm thử replay tương ứng.
- Browser regression dùng mock; không chứng minh 12 module có dữ liệu thật.
- Migration downgrade sẽ bỏ cột snapshot. Không downgrade khi cần giữ lịch sử
  skill; nếu rollback phải có kế hoạch bảo toàn dữ liệu và kiểm tra backup.

## Cách kiểm tra lại

Trong thư mục dự án, dùng `.venv\Scripts\python.exe scripts/test_backend.py
--roundtrip` cho database test riêng; `npm run test:runtime`; `npm run build`.
Không build đồng thời với Next dev dùng chung build directory.
Sau khi khởi động local, chạy `scripts/verify_skills_ui.cjs` với
`PAO_SMOKE_EMAIL` và `PAO_SMOKE_PASSWORD` chỉ trong môi trường process.
Không ghi credential vào source hoặc report. Browser regression cũ nhận
`PAO_FRONTEND_URL=http://127.0.0.1:3200/`.

## Bước kế tiếp, chưa triển khai trong checkpoint này

Nối một business tool đọc dữ liệu PAO với RBAC và giới hạn workspace,
trước tiên cho `daily-business-brief`. Kiểm thử dữ liệu thiếu/khác workspace,
nguồn xác thực và không có write side effect rồi mới nối Chief routing.
