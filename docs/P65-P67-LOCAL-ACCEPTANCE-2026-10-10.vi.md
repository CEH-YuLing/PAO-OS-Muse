# P6.5–P6.7 — Hoàn thiện local và nghiệm thu tích hợp

Ngày 10/10/2026, target `F:\PAO-ACOS`. Không sửa source bảo vệ `F:\Apex`.
**P6.1–P6.7 hoàn tất nghiệm thu LOCAL.** Focused, full regression, browser,
populated restore, rollout0046 và live readiness đều đã đạt. Đây không phải
production, real-model/tool hoặc Meta business acceptance.

## P6.5 — Kết quả và thông báo trong ứng dụng

- Inbox nhận cả Studio terminal và Goal terminal đã kiểm chứng journal/admission.
- Read/ack riêng từng người, không suy diễn delivered là người nhận đã đọc.
- Delivery chỉ `in_app`, khóa dedup theo nguồn/hash/người nhận. Persist pending
  trước consume; worker hiện có phục hồi pending, không thêm poller riêng.
- Sender/recipient phải còn active và còn quyền ở thời điểm consume; mất quyền
  hoặc nguồn sai chuyển failed. Người gửi có thể retry rõ ràng, tối đa5 lần.
- UI nhập người nhận UUID, xem trạng thái/attempt/error, thông báo của mình sau
  reload. Mất ACK retry cùng body không tạo thêm delivery.
- Focused checkpoint:13passed,44.42s (8outbox+4inbox+1browser).
  Goal thực chạy qua Temporal/ARQ fixed Echo, không chứng minh kết quả kinh doanh.
- Chưa gửi Telegram/email/push; chưa catalog người nhận, chưa lịch sử audit
  từng attempt ngoài trạng thái/attempt/error cuối.

## P6.6 — Học từ tài liệu có duyệt

- Conversation và artifact plaintext trong Brain có quyền truy cập.
- `quote`: trích nguyên văn; `extractive_summary_v1`: ghép2–5 đoạn đúng nguồn,
  không dùng model suy diễn. Pin SHA/revision/file metadata và từng đoạn.
- Hai bước preview/proposal rồi human review; promote chỉ tạo note data-only.
  Không auto sửa skill, policy, code hoặc thực thi instructions trong tài liệu.
- Quota chung10/user/workspace/day, dedup, fencing nguồn thay đổi, proposal
  identity và audit bất biến. Revert không ghi đè note đã được sửa.
- Screen toàn nguồn với Unicode NFKC, controls/bidi, secret patterns và
  instructions nguy hiểm; đây là phòng vệ có giới hạn, không chứng minh
  mọi prompt injection đã bị loại bỏ. Nguồn không được cấp authority thực thi.
- Focused checkpoint25passed,29.79s, bao gồm browser quote/derived,
  preview/promote/revert/reload/mobile390px; zero page errors.
- Chưa PDF/OCR, semantic model summary, auto promotion hoặc auto skill learning.

## P6.7 — Quan sát outcome có nguồn

- Preview rồi xác nhận lưu snapshot bất biến, request-key dedup và quota.
- Pin action/connection version, execution audit, metric/job và confounders;
  24h/72h/7d so cùng baseline. Trạng thái observed/pending/insufficient rõ ràng.
- Thiếu hourly coverage, DST không xác định, nguồn sync chưa completed,
  dry-run/simulated hoặc không có execution proof không được thành observed.
- Lịch sử mở lại snapshot cũ; nguồn hiện tại thay đổi được báo stale, không
  ghi đè chứng cứ đã lưu. Retry mất ACK cùng command chỉ một observation.
- Focused checkpoint29passed,29.04s (28backend+1browser). Warehouse và execution
  audit trong fixture là synthetic, không phải Meta thật hoặc nghiệm thu M3.
- KPI tăng chỉ association; `causal_effect_proven=false`. Không gọi model,
  không sửa Ads hoặc tự lấy quyền thực thi. New flag mặc định false.
- Raw snapshot giới hạn2MiB, metrics tối đa5000; chưa thống kê causal inference.
  Reads dùng transaction hiện tại; không tuyên bố đã có warehouse MVCC snapshot
  isolation xuyên nhiều truy vấn. Pin revalidation/historical immutable snapshot
  không thay cho production ingest/consistency acceptance.

## Contract, schema và kiểm thử chung

- Migration0044: Goal receipts/deliveries và recovery fields Studio delivery.
- Migration0045: artifact proposals/audits và immutable triggers.
- Migration0046: immutable outcome observations.
- Contract291operations; mọi operation/schema cũ từ checkpoint0043 giữ nguyên,
  thêm10operations. TypeScript contract sinh lại. Không tạo router owner trùng.
- Runtime/SSE8/8 và production build20static-generation entries đã đạt.
- Standalone lint đã có cấu hình chuẩn `next/core-web-vitals`, parser `.mts/.cts`;
  exit0 nhưng còn cảnh báo React Hooks. Không bỏ rules để làm xanh gate.
- Clone migration0043→0046→0043→0046,alembic check đạt;104business tables
  cũ giữ hash và nguồn chính không đổi. Clone do invocation tạo được dọn;
  private dump giữ lại. Không xóa volume hoặc restore đè database chính.
- Pre-rollout checkpoint verified:
  `.runtime/checkpoints/p0-20261010T081757-667919e8/manifest.json`,
  795source files/105physical tables/3M2artifacts/revision0043.
- Full backend: **1136passed,0failed,0skipped**,1421.36s;26 cảnh báo thư viện
  ARQ close deprecated. Hai ARQ kill/restart real-clock opt-in đã chạy, không skip.
- Browser cuối: **7passed**,172.86s;3 cảnh báo ARQ deprecated. P6.2→P6.7,
  HTTP thật, pao_test/Redis15; approval/hủy, lịch Studio/Goal, delivery/retry/
  notification, artifact quote/derived/revert, outcome/stale/insufficient,
  reload/mobile đạt. Browser không chứng minh kết nối Meta hoặc model thật.
- UI smoke12module gốc +2link P6 đạt (API mocked, không phải business acceptance).
  Phát hiện cache dev stale gây JS404; đã restart chỉ Web được xác minh,
  cache cũ giữ trong runtime quarantine, không xóa volume/data. Harness được
  cleanup browser cả khi lỗi; assertion navigation khớp đúng hai link mới.
- Populated seed riêng1passed,9.00s. Restore kết hợp **109business tables hash
  exact**, kiểm chứng Goal admission/journal, receipt/hash, artifact/file/segment/
  note/audit, outcome snapshot và immutable triggers. Fresh interpreter consume
  pending trên clone đúng một lần; gọi lại không tạo thêm. Nguồn/test/main không đổi.
- Lượt seed đầu lỗi do hai fixture dùng cùng slug, đã sửa để dùng chính Studio
  child thật vừa hoàn tất của Goal. Không bỏ assertion, không sửa backend sau
  full regression; lượt lỗi không tính vào nghiệm thu.
- Checkpoint ngay trước rollout được dùng để restore/so hash lại:
  `.runtime/checkpoints/p0-20261010T084011-468cf6aa/manifest.json`,
  797source files/105physical tables/3artifacts/0043.
- Main rollout0043→0046:104business tables cũ giữ hash nguyên vẹn,5 bảng mới
  rỗng. Chỉ API/ARQ được restart theo executable/start-time đúng; Web và Ollama
  được giữ. Docker PostgreSQL/Redis healthy, không reset/reinstall/delete data.
- Live: health200/ready200/Web200,workerhealthy; contract291operations khớp
  file sinh, source binding SHA256:
  `5003605e700985527fd7b4de968d785db7b6a713a1a38c4ae3259845d083667a`.
  M2 archive replay3/3, main Goal/Studio/schedule/command và5 bảng mới đều0.
  Result/learning/outcome, Goal/schedule/Temporal/Meta/write/Telegram và
  business delivery/autopilot gates chính vẫnfalse. Không sửa `.env`.
- Gate live có thể chạy lại bằng `scripts/check_p6_completion_live.py` và
  `scripts/check_acos_health.py`; các live checker revision0041–0043 là
  checkpoint lịch sử, không dùng thay gate0046.

## Chạy lại nghiệm thu có kiểm soát

Từ target với venv và Docker local đã cấu hình; không chạy hai pytest cùng
`pao_test` vì fixture truncate dữ liệu thử. Không dùng production DB cho pytest.

1. `PYTHONPATH=apps/api`, `PYTHONUTF8=1`, `PAO_BUILD_CHECK=1`,
   `PAO_SCHEDULE_START_WEB=1`; chạy `python scripts/test_backend.py --browser`.
   Script tự chọn `pao_test`/Redis15 và bật real-clock opt-in.
2. `npm run test:runtime`, `npm run lint --workspace apps/web`,
   `npm run build` với PAO_BUILD_CHECK1; `npx tsc --project apps/web/tsconfig.json --noEmit`.
3. `PAO_FRONTEND_URL=http://127.0.0.1:3200/`; `npm run test:frontend` chỉ smoke/mock.
4. Với DATABASE_URL/PAO_TEST_DATABASE_URL cùng trỏ `pao_test`,Redis15, chạy
   `pytest -q apps/api/tests/p6_completion_fixture.py` riêng sau regression.
   Sau đó bỏ test URL override để `python scripts/check_p6_completion_restore.py`
   dùng config ACOS chính và restore *pao_test* sang clone mới, không main.
5. `python scripts/check_p6_completion_restore.py --migration` dành cho source
   revision0043 trước rollout; sau rollout0046 không hạ main để chạy lại gate này.
6. `python scripts/backup_acos_checkpoint.py` xác minh backup/restore main và
   source archive; giữ encryption/JWT keys riêng, không đưa vào archive chia sẻ.
   Không dùng `--apply-manifest` như test thường: đó là thao tác rollout có bảo vệ,
   yêu cầu source0043/idle/verified checkpoint tương ứng.

## Gate ngoài local vẫn chưa đạt

Meta OAuth/M3/live data, provider/tool thật cho Goal, gửi ngoài ứng dụng,
production reboot/failover và causal business outcome không được chứng nhận.
Các feature flags chính vẫn tắt; `.env` không sửa. Không reboot Windows,
không deploy public, không bật quảng cáo thật hoặc thay dữ liệu nghiệp vụ thật.

Checkpoint sau rollout verified:
`.runtime/checkpoints/p0-20261010T084238-e9825984/manifest.json`,
**797source files/110physical tables/3M2artifacts/revision0046**.
Archive đã chứa code/tests/roadmap/register/báo cáo hoàn tất trước khi thêm
dòng tham chiếu checkpoint này; không đổi code sau snapshot. Restore clone
main0046 và source archive hashes đã được kiểm tra, không restore đè main.

## Bước tiếp theo

Sau khi đóng đủ gate local P6, đến P7.1 ChannelAdapter contract và identity/
workspace/Brain/dedup. Không tự mở connector thật hoặc bắt đầu P7 trong lượt
nghiệm thu P6 này. Catalog/pending reload UX và Hooks warnings là nợ kỹ thuật
riêng, không chạy lại grant trials đã đạt mà không có thay đổi phụ thuộc.
