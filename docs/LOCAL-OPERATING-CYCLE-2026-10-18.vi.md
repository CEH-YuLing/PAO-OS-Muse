# PAO — Hoàn thiện vòng vận hành local trên nền S5/M6

Ngày18/10/2026, Asia/Saigon. Target `F:\PAO-ACOS`.
Trạng thái: **local_accepted — đã cài và kiểm chứng**. Không phải toàn S6,
production hoặc nghiệm thu dữ liệu/provider thật.

## 1. Phạm vi và kết quả rà soát

Giữ Next.js/FastAPI modular monolith, PostgreSQL/ARQ/outbox và các Run/Studio/
TaskAttempt hiện có. Không thêm runner, scheduler, database hoặc backend mới.

| Chặng | Nền đã có, giữ nguyên | Khoảng trống xử lý trong lượt này |
|---|---|---|
| Hồ sơ SME/brand | Scoped profile, phiên bản/CAS, dữ liệu thiếu khác số0 | Remount vùng soạn thảo theo tài khoản/SME/vai trò, bỏ response cũ khi đổi phạm vi |
| Kế hoạch | Kế hoạch có cấu trúc, phụ thuộc, lịch sử và deep-link | Thứ tự mục trùng thanh hành trình; bỏ nhãn “chưa duyệt” viết cứng khi đã có quyết định |
| AI theo công việc | Routing hierarchy, skill/model/grant, pin bất biến | Giữ nguyên cơ chế kế thừa; cập nhật vận hành sau đọc/duyệt/tạo task, không cần đoán trạng thái |
| Thực thi và theo dõi | Native job, queue, policy và source checks | Tự GET trạng thái khi có job queued/running, số liệu tiến độ và thời điểm đọc |
| Hủy/dừng | Cancel signal và control epoch server-side | Phân biệt yêu cầu hủy đang chờ ACK với terminal cancelled; không cho gửi lặp nút hủy đang chờ |
| Làm lại và phục hồi | Backend chặn chạy lại job đã admit; nhân bản kế hoạch đã có | Shortcut làm lại từ job lỗi/hủy/từ chối, dùng chính luồng clone có xác nhận; không tự retry |
| Duyệt và báo cáo | Review riêng plan/content/action, report nội bộ, simulation ledger | Lỗi mất phản hồi buộc đọc đối soát; không gửi lại POST, không suy thiếu dữ liệu thành0 |

Kế hoạch tháng hiện vẫn được soạn/lưu thành dữ liệu có cấu trúc trong UI. AI
chạy các đầu việc văn bản qua skill đã duyệt; không tuyên bố đã có một AI tự
biến mọi mục tiêu kinh doanh thành kế hoạch hoàn chỉnh, tự tạo ảnh/video hoặc
tự vận hành Ads. Chất lượng đề xuất tổng thể và các năng lực mở rộng được
đánh giá riêng, không suy ra từ số test hoặc bản nháp fixture.

## 2. Hành vi mới

- Có bảng tiến độ: đang chờ/chạy, chờ duyệt nội dung, nội dung có phê duyệt còn
  hiệu lực, và job lỗi/hủy/từ chối cần xem xét làm lại. Đây là trạng thái job
  đã đọc, không phải KPI, số dư provider hoặc hiệu quả quảng cáo thật.
- Tự đọc lại operations mỗi5giây chỉ khi có job queued/running, tab đang mở,
  có mạng và không có thao tác đang khóa. Dừng khi terminal, unmount/đổi
  phạm vi hoặc lỗi đọc; khi lỗi phải đọc lại thủ công. Không tự chạy nền sau
  đóng tab và không thay worker/scheduler.
- Auto refresh chỉ GET operations; không gọi model, gửi lại POST, giữ tiền,
  gia hạn quyền hay tự duyệt. Không ghi vào localStorage bản nháp vận hành,
  token, grant hoặc xác nhận đã duyệt.
- `cancel_requested=true` khi job còn queued/running hiển thị “Đã yêu cầu
  hủy — đang chờ xác nhận”. Chỉ trạng thái cancelled từ server mới là “Đã hủy”.
  Terminal completed vẫn là bản nháp, không hứa hủy thành công/hoàn phí.
- Đọc và mutation đều kiểm epoch sau response, kể cả GET sau POST. Đổi SME/
  tài khoản/vai trò tạo vùng soạn thảo mới; không áp response cũ vào vùng mới.
- Phê duyệt/tạo task cập nhật vùng vận hành bằng callback cùng trang, không
  tự gọi AI. Kế hoạch/AI/các quyền còn lại vẫn phải hợp lệ ở server.
- Làm lại đi qua **Chuẩn bị kế hoạch làm lại** hoặc **Nhân bản thành kế hoạch
  mới**. Chỉ tạo nháp trong UI; cần lưu, duyệt, tạo task và xác nhận gọi AI riêng.
  Không chép approval/job/artifact/grant/ledger, không sửa lịch sử cũ.

## 3. Hướng dẫn cho người dùng

1. Chọn đúng doanh nghiệp; vào **Công việc và dự án → Kế hoạch kinh doanh**.
2. Lưu hồ sơ, soạn/mở kế hoạch; kiểm tra phiên bản, phạm vi và dữ liệu còn thiếu.
3. Cấu hình AI theo việc và xem trước; chủ doanh nghiệp duyệt kế hoạch, rồi
   xác nhận tạo công việc nháp. Đây chưa phải lệnh chạy AI/đăng bài.
4. Chọn việc và xác nhận gọi AI. Theo dõi bảng tiến độ và giờ đọc gần nhất.
   Worker/model phải chạy được; UI tự cập nhật không chứng minh backend đã chạy.
5. Muốn hủy: bấm Hủy lượt chạy và chờ trạng thái cuối. Dừng khẩn cấp áp dụng
   đúng SME; mở lại không khôi phục quyền/epoch cũ và không hoàn tác chi phí.
6. Mất phản hồi: **Đọc lại vận hành kế hoạch**, hoặc tải lại đúng liên kết
   kế hoạch để đối chiếu dữ liệu đã lưu. Không tự coi “không thấy job” là chưa
   admit nếu còn quyền Brain hoặc dữ liệu chưa xác minh; không chạy lại mù.
7. Duyệt nội dung đúng bản nháp/hash. Kết quả nguồn phải được duyệt trước khi
   chạy việc phụ thuộc. Duyệt plan khác duyệt nội dung và khác duyệt action.
8. Cần làm lại: chuẩn bị kế hoạch mới, rà cả việc phụ thuộc và xin duyệt riêng.
   Có thể phát sinh phí model sau lần xác nhận chạy mới, không tự giữ kết quả cũ.
9. Tạo báo cáo nội bộ. Số liệu KPI/chỉ tiêu chưa đo và chi Ads chưa có nguồn
   thật vẫn là chưa rõ; không coi báo cáo nội bộ là hóa đơn hoặc dữ liệu Ads.

## 4. Kiểm chứng

- Node **132/132**,0fail/skip; gồm4test mới về pending cancellation, unknown
  status, progress và điều kiện polling. TypeScript và build23trang đạt.
- Focused backend **125/125**,0fail/error/skip,67.82s;2ARQ deprecation warnings.
  Chính các test planning/review/routing/operations đã có, gồm hàng đợi ARQ
  thật với gateway giả, quyền/CAS/phiên bản/phụ thuộc/stop/cancel/report.
  Python3.12.14 và dependency runtime/dev đều đối chiếu requirements lock.
- Hai operator guard kiểm khóa chống chạy chồng và nhả/chiếm lại đạt; không
  cộng chúng vào132Node/125backend. Khóa chỉ phối hợp các probe local-cycle,
  không khóa hoạt động người dùng hoặc mọi công cụ bên ngoài.
- Browser cuối đạt native M6 journey và bộ bổ sung: mất ACK của job/report,
  đối soát không gửi lại, reload, cancel-request rồi terminal ACK, chặn dependency
  trước duyệt và chạy sau duyệt, clone không chép quyền, stop epoch, lịch sử,
  lỗi GET, SME isolation, sáng/tối và mobile320/390. Dùng DB UUID riêng và gateway
  giả; cleanup đạt, không còn DB/cổng thử.
- Installed browser chỉ GET,4màn hình x2theme, tab kết nối và mobile đạt,
  0API mutation/0browser error. Lượt cuối giữ before/after hash từng bảng,
  `.env` và binding đều khớp. Live0071/399operations/153tables, replay3/3;
  API health/ready/Web200, worker healthy.
- Không chạy lại full2258backend: source API/nghiệp vụ/dependencies không đổi.
  Hosted CI3151851 là baseline cũ, không phải CI cho UI mới.

Bằng chứng đã có:

- `F:\Apex\local-cycle-node.log`, `F:\Apex\local-cycle-build.log`.
- `.runtime/local-cycle-focused-5a62a8405ef44029a822eb3b9a601cc7/`:
  `receipt.json`, `junit.xml`, `pytest.log`.
- Candidate source `F:\Apex\local-cycle-candidate`; node_modules là junction
  dùng dependency hiện có, không cài/update dependency hoặc xóa junction.
- Native browser/receipt/cleanup cuối:
  `.runtime/local-cycle-browser-runs/pao_s5_browser_690e7213c0894dfe9b8b7f5924d7e419/`.
- Release8file frontend: `F:\Apex\local-cycle-candidate\.runtime\local-cycle-release.json`;
  `.runtime/local-cycle-installed.json`, `.runtime/local-cycle-completion.json`.
- Installed evidence:
  `.runtime/local-cycle-live-afa5d0589014485ab32bf60a776dfdba/`, gồm
  `before.json`, `after.json`, `verification.json`, browser log và screenshots.
- Source/cache cũ giữ để hoàn tác:
  `.runtime/local-cycle-install-f90ee2745a34465a926f601be197ed75/`.
- So sánh checkpoint qua clone đọc riêng:
  `.runtime/local-cycle-drift-5a86dc050d8a42b883cb1aaa5fe58328/receipt.json`.

## 5. Bảo vệ dữ liệu và lịch sử lỗi

Checkpoint trước đổi source:
`.runtime/checkpoints/p0-20261018T024335-ec6839c1/manifest.json`, verified,
1307source files,153physical tables,3archive,0071; có thử restore riêng.
Không restore đè primary. API/backend binding giữ
`8e9a71b996dee609d36868b8a254073c9ea16d4d78f56cf790d86690cf1b591b`.

Giữ các lượt không đạt để truy vết, không viết lại thành pass:

- `local-cycle-focused-f532...`: interpreter serving không có pytest,0test;
  chuyển sang venv kiểm thử riêng đã có, không pip install vào serving runtime.
- `local-cycle-focused-4770...`: dùng nhầm network guard chỉ cho cổng harness
  Phase3; đã dừng đúng probe, không nới mạng hoặc auth của ứng dụng.
- `local-cycle-focused-ee7c...`:119pass/5fail/1error; thời gian chạy chồng với
  probe trước dùng cùng pao_test có duplicate-email/auth401. Primary/env không
  đổi. Sau khi xác minh pytest cũ thoát, chạy tuần tự đạt125/125, không sửa test
  hoặc auth để bỏ lỗi. Thêm operator lock và guard lấy đúng cổng test cấu hình.
- Browser `c9db...`: native M6 journey đạt nhưng test bổ sung mở deep-link quá
  sớm khi SME chưa được ghi nhận. Sửa test chờ đúng workspace trong phiên;
  không tự chọn SME thay user hoặc nới quyền. Cleanup riêng đạt.
- Browser `d383...`: các ca vận hành đã đi qua nhưng chọn nhầm enterprise
  selector ẩn ở sidebar khi desktop. Sửa test chọn selector header đang hiển
  thị và chờ ngữ cảnh SME mới, không force-click hoặc sửa quyền. Lượt690e...
  sau đó đạt cả native journey và bộ bổ sung; giữ nguyên folder lỗi/cleanup.
- Installed `187c...`: browser chỉ đọc đạt nhưng assert before/after không
  khớp; bản helper lúc đó chưa lưu snapshot trước nên không thể tái dựng chính
  xác thay đổi trong riêng khoảng này. Không coi lần đó là pass hoặc restore
  primary. Đã sửa operator helper giữ before/after/verification kể cả khi fail.
- So sánh checkpoint trước đổi source với hiện tại qua một clone restore mới:
  chỉ `tenant_metadata_leases` khác,13→15dòng; hash/count của các bảng còn lại
  khớp. Bảng này phục vụ quota/lease khi discovery danh mục Ollama trong
  `modules/engines/metadata.py`, không phải kế hoạch/job/approval. Không xác
  nhận tác nhân của từng lease hoặc loại bảng khỏi gate; giữ cả15dòng. Clone
  được dọn đúng UUID, primary không đổi trong audit. Lượt installed mới
  `afa5...` đạt strict snapshot tất cả bảng, không bỏ qua bảng lease.

Không bật Ads/Google/Telegram/Temporal/voice/retention, không gọi cloud hoặc
provider thật, không chi tiền, không deploy công khai hoặc commit/push.
Ảnh/log/dump/runtime giữ local, không đưa secret hoặc dữ liệu thật vào Git.

## 6. Điều kiện chuyển giai đoạn

Browser/native trên DB riêng và bản cài thật đã đạt, đóng lát cắt vòng
vận hành local của S5/M6. Không suy toàn M6/S6 hoặc sản phẩm SaaS hoàn tất.
Tiếp theo theo master là S6.1: người dùng chọn một SME/brand, nền tảng/tài khoản
và kỳ dữ liệu hoặc file báo cáo; bắt đầu đối chiếu read-only. Sau đó pilot
local S6.3; VPS/public vẫn hoãn theo người dùng. Gate chất lượng model, API
thật, hành động thật và production phải có bằng chứng/phê duyệt riêng.
