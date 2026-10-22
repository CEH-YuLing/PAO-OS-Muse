# P3.1 — Engine contract / model pin — nghiệm thu local

Ngày: 06/10/2026. Target duy nhất: `F:\PAO-ACOS`.

**Trạng thái: P3.1 đã đạt LOCAL MVP.** Migration0031 và engine flag đã bật local
sau regression; API/worker đã khởi động lại và đạt live contract/binding/health.
P3 tổng thể và production chưa hoàn tất. Checkpoint cuối được ghi riêng bên dưới.

## Bạn nhận được gì

- Chọn model cho từng hội thoại trong PAO AI, không xóa lịch sử hay Brain.
- Khi gửi yêu cầu, PAO chốt provider/model cho run; đổi mặc định không đổi run đó.
- Kết nối bị gỡ hoặc credential thay đổi thì run báo lỗi, không tự đổi provider.
- Capabilities phân biệt text/stream, structured tool planner, chưa hỗ trợ vision
  hoặc native tool-call protocol; quyền Gateway/approval vẫn là lớp riêng.
- Lỗi engine được chuẩn hóa, không phản chiếu URL/key/prompt/provider body.
- Hủy đóng client stream phía PAO. Usage không được báo cáo vẫn là unknown.
- Knowledge opt-in dùng `pao-grounded-excerpts-v1` local, không model/cloud;
  excerpt lịch sử không bị gửi sang cloud khi quay lại normal chat.

## Cách dùng sau rollout

1. Mở PAO AI và tạo/chọn hội thoại.
2. Mở mục **Model**, chọn Ollama/model đã cài hoặc cloud connection đã cấu hình.
3. Nhấn **Áp dụng model**, sau đó mới gửi yêu cầu.
4. Xem dòng **Run** để biết model đã chốt. Khi run đang chạy không đổi model.
5. Nếu mặc định lỗi, chọn lại model hợp lệ một cách chủ động; PAO không fallback.

Không tải model mới, cài CLI hay thêm provider. Cloud model chỉ được liệt kê khi
connection workspace đã có; catalog không xác nhận credential/model đang healthy.
Đổi cloud model có thể đưa prompt/history thường sang provider đã chọn; P3.4
privacy/budget routing chưa triển khai. Không dùng nguồn private với cloud nếu
chưa có quyết định cho phép dữ liệu đó rời máy.

## Bằng chứng và gate

| Gate | Kết quả |
| --- | --- |
| Checkpoint trước P3.1 | `p0-20261006T103115-2deeff6b`, verified; 502 source files, 81 DB tables, 3 M2 artifacts, revision0030 |
| Migration restored-only | 0030→0031→0030→0031 đạt; 80 bảng ứng dụng có row hashes cũ giữ nguyên; DB local không bị đổi trong drill |
| Contract | 195 operations/schema cũ giữ nguyên; thêm4 operations; tổng199/29routers, ORM80tables |
| Regression cuối | 489passed /0skip /456.87s; gồm25ca P3.1;1 ARQ dependency DeprecationWarning |
| Runtime/SSE và TypeScript | 8/8; `tsc --noEmit` đạt trên mã cuối |
| Production frontend build | Đạt18pages; cache `.pao-build-check` riêng, không phá dev cache |
| UI cũ | 12 routes đạt sau sửa duplicate React key |
| P3.1 real browser/API/ARQ/SSE | Đạt apply/pin/active conflict/history/cancel; synthetic gateway,0 real provider calls |
| P3.1 fixture restore | 80 bảng hash giữ nguyên;2runs completed/cancelled,1session pin |
| Knowledge cùng engine flag bật | Đạt real API/ARQ/SSE, index/citations/Wiki/graph/attachments; không model call |
| P2 fixture restore | 80 bảng hash giữ nguyên, chunks/wiki/evidence/source bytes được xác minh |
| Live local và actual Ollama text smoke | API health/ready/Web HTTP200; worker healthy; revision0031; catalog readonly; Qwen4B text thật đạt;0cloud calls/0DB writes |
| Checkpoint nghiệm thu trước chốt tài liệu | `p0-20261006T120823-86db68de`:516source files/81DBtables/3M2artifacts/revision0031, verified:true |

Sau chốt tài liệu chạy checkpoint thêm lần cuối để source ZIP chứa báo cáo hoàn
chỉnh; manifest nằm ngoài ZIP tại `.runtime/checkpoints/` để không tự tham chiếu
hash. Giữ cả checkpoint trước P3.1 và checkpoint sau rollout, không ghi đè.

Live source binding:
`3f3aba86e4d8c784b588ac32ff77defb536fdad3ed78b8739ad81b19f5e2d074`.
M2 historical archive replay3/3 đạt; các hàng đợi local kiểm tra đều0, integrations
vẫn tắt. API PID22892 và worker PID9160 tại thời điểm rollout; không dùng PID này
để stop về sau nếu chưa đối chiếu start-time/runtime path với record hiện hành.

Actual Ollama smoke dùng model `qwen3:4b-instruct-2507-q4_K_M`, prompt tổng hợp,
max16outputtokens: text7chars, usage reported. Một lần đổi default trong process
test vẫn gọi đúng model đã ghim (TTFT33.375s, latency34.734s); lần sau rollout
TTFT28.031s, latency28.734s. Đây là hai số đo smoke, không phải benchmark chứng
minh tối ưu tốc độ. Local đang chậm; chưa smoke planner/tool compatibility thật.
Không in raw prompt người dùng, response riêng tư hoặc private reasoning.

Script/gates: `check_p31_migration.py`, `run_p0_checks.py`,
`run_p1_browser_acceptance.py --engines`, `--knowledge --engine-contract`,
`check_p31_live.py --local-smoke`, `check_p1_live.py`, `check_acos_idle.py`,
`check_acos_health.py`, `backup_acos_checkpoint.py`. Browser chạy sau regression,
không song song vì database fixture `pao_test` bị truncate.
Ảnh nghiệm thu: `.runtime/p31-live-ui.png` (fixture tổng hợp, không dữ liệu thật).

## Phạm vi chưa đạt / không mở

- P3.2–P3.7 chưa triển khai: context compiler, compaction, privacy/budget router,
  commands, session search/export và usage ledger/concurrency.
- M4, Ads writes, email thật, Telegram bridge, Temporal execution và public deploy
  không bật. Không credential onboarding/real cloud smoke.
- Capability trong P3.1 là của adapter. Chưa xác minh mọi model/tool compatibility;
  model không hỗ trợ schema trả lỗi, không tự thay engine hay nâng quyền.
- Cancel không cam kết dừng server GPU inference; usage không phải invoice/quota.
- Model name cap120; model ID dài hơn cần migration riêng.
- Embedding local `embeddinggemma:300m` còn thiếu; P2 vẫn dùng FTS fallback.
- Production reboot/recovery, VPS/VM và remote CI chưa có bằng chứng; không reboot
  Windows đang dùng. Git chưa commit/push; dirty changes P0/P1/P2 được giữ nguyên.

## Rollback và bước kế tiếp

Giữ snapshot/database để audit. Flag off với session/run đã ghim trả controlled
error, không silently fallback. Dừng đúng PID sau safe-idle rồi mới đổi source/
flag; dùng checkpoint riêng để phục hồi. Không downgrade DB vận hành tự động vì
0031→0030 xóa ba cột pin. Backup DB có thể chứa dữ liệu nhạy cảm: giữ private.

Sau gate P3.1 local: **P3.2 — tách context builder và kiểm soát kích thước prompt**,
vẫn một lát cắt mỗi lần; không tự chuyển sang P4/M4 hoặc production deployment.
Chi tiết quyết định: [ADR P3.1](ADR-P31-ENGINE-CONTRACT.vi.md).
