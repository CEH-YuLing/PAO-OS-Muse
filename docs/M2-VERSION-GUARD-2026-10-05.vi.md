# M2 — Chặn thực thi bằng executable không tương thích

Ngày 05/10/2026; target `F:\PAO-ACOS`. Checkpoint đạt local, chưa nghiệm thu
toàn bộ M2/M3. Chính sách là từ chối chạy khác phiên bản, không tự resume.

## Đã triển khai

- Snapshot có execution_binding gồm policy exact-backend-source-v1 và SHA256.
  Hash snapshot bao gồm binding này. Dấu code được tính một lần lúc process
  import, từ toàn bộ Python source trong pao và phiên bản Python đầy đủ; nội
  dung CRLF được chuẩn hóa LF. Không đọc .env, không phụ thuộc Git SHA.
- Mỗi business tool được pin binding trong execution plan, keyed bằng call ID,
  cùng transaction tạo call. Không cần migration vì dùng JSON đã có.
- Kiểm tương thích trước claim, trong transaction read và trước lưu result;
  Chief kiểm snapshot trước mỗi tool và evaluator kiểm trước nhận result.
- Queued run đã có skill snapshot không được tự replan: khác binding trả
  skill_version_incompatible; cùng binding vẫn skill_resume_not_supported.
- Snapshot/call cũ thiếu binding bị từ chối, không tự thêm binding mới để hợp
  thức hóa. Terminal run cũ vẫn đọc được; không tự thực thi lại.
- TaskAttempt completion không tương thích trả HTTP 409 và giữ nguyên attempt;
  vẫn cho phép ghi failed/cancelled. Attempt không dùng skill không bị đổi policy.
- Catalog/preview schema và generated OpenAPI/TypeScript types đã cập nhật.

## Kiểm chứng

- Backend toàn bộ **254/254**, 131.45 giây, database pao_test riêng.
- Chín ca mới: legacy/different/tampered snapshots; pinned queued run cùng/khác
  binding; queued business call khác executable; drift trong read; drift giữa
  hai tools; attempt không nhận completed nhưng vẫn có thể ghi failed.
- Hai ca OS-process recovery từ checkpoint trước vẫn đạt trong regression.
- Runtime/SSE **8/8**; TypeScript noEmit/incremental false đạt.
- Live API → ARQ cả ba Chief command đạt: snapshot binding và hai call binding
  khớp, tools completed và business result insufficient_data.
- Live catalog/preflight/ba previews, desktop/mobile đạt. API /ready và Web
  /skills HTTP 200. Không sửa UI; không chạy lại production build ở lượt này.
- Database vẫn 0023, không migration mới; source F:\Apex\apex không sửa.

Lượt đầu có 11 regression lỗi do SkillView forbid extra chưa khai báo trường
execution_binding. Đã sửa response schema và types; các số phía trên là lượt
full regression cuối sau sửa. Không dùng lượt lỗi làm bằng chứng hoàn thành.

Live demo runs cuối, memory tắt:

- Daily: 19bc4469-c70e-4d4b-9740-9316f7eadbe4.
- Ads: f76de753-56fa-46bc-9d7d-538189f0ba56.
- Creative: fa3ff87d-8646-4271-a0fe-b6adff1b694c.

Chỉ restart API/worker sau idle check 0 jobs. Smoke chỉ ghi hội thoại/run/audit
demo; không Ads thật, Telegram/email hoặc thay dữ liệu nghiệp vụ thật.

## Vận hành và giới hạn

Binding là kiểm tra tương thích bảo thủ, không chữ ký bảo mật hoặc artifact
archive. Bất kỳ source backend thay đổi đều có thể chặn job cũ. Không pin toàn
bộ dependency/native binary/config/database schema; không bảo đảm hot-patching
code lúc process đang import. Deploy phải giữ source/runtime ổn định, dừng
nhận job, đợi rảnh rồi restart đồng bộ API/worker. Không sửa code trực tiếp
trong một process đang phục vụ và coi digest là bằng chứng code loaded tuyệt đối.

Tests drift dùng digest giả lập trong process; không chứng minh replay code
phiên bản cũ hoặc thực hiện rolling upgrade toàn stack thật. Recovery ARQ/Redis
theo wall-clock vẫn chưa nghiệm thu. Token budget cho skill LLM tương lai chưa
được cưỡng chế. Call unknown không được tự retry.

Nếu attempt cũ bị chặn: giữ snapshot lịch sử, kiểm tra tác dụng đã xảy ra, ghi
failed/cancelled sau review; nếu cần chạy lại thì tạo attempt mới với request key
mới và snapshot mới. Không đổi snapshot hoặc đưa run cũ về queued bằng tay.

## Bước kế tiếp

Nối wrapper attribution chỉ đọc bằng fixture, phân biệt doanh thu nền tảng,
ước tính attribution và doanh thu doanh nghiệp xác minh. Chưa cấp quyền write,
chưa nối credential thật hoặc nghiệm thu business correctness M3.
