# PAO — mở chức năng nội bộ cho phát triển thực tế trên local

Ngày 20/10/2026. Phạm vi được người dùng xác nhận: mở chức năng thực tế,
gỡ khóa demo, giữ bảo mật/cách ly doanh nghiệp và duyệt hành động bên ngoài.
Không có công tắc bỏ qua toàn bộ kiểm tra.

## Phạm vi cấu hình

Tám công tắc được chọn sau khi đọc đường xử lý thực tế:

| Công tắc | Tác dụng | Không đồng nghĩa với |
| --- | --- | --- |
| `RESULT_INBOX_ENABLED` | Xem, đánh dấu và nhận kết quả trong PAO | Gửi tin ra ngoài; chứng minh mục tiêu kinh doanh đã đạt |
| `LEARNING_REVIEW_ENABLED` | Đề xuất/duyệt/hoàn tác ghi chú từ nguồn được phép | Tự sửa chính sách, quyền công cụ hoặc ghi nhớ không cần duyệt |
| `OUTCOME_OBSERVATIONS_ENABLED` | Lưu đối chiếu kết quả theo bằng chứng hiện có | Kết nối Ads thật hoặc chứng minh quan hệ nhân quả |
| `BUSINESS_EVENTS_ENABLED` | Ghi sự kiện nội bộ cùng transaction nghiệp vụ | Tự tạo/chạy hành động bên ngoài |
| `BUSINESS_EVENT_DELIVERY_ENABLED` | Xử lý receipt `internal.audit.v1` | Gửi Telegram, webhook hoặc email |
| `UNIFIED_APPROVALS_ENABLED` | Duyệt tập trung bằng dịch vụ quyền hiện có | Tự duyệt, bỏ hạn dùng/phiên bản hoặc bỏ quyền Ads |
| `GOAL_ADMISSION_ENABLED` | Lập/xem bản tiếp nhận mục tiêu theo giao thức hiện có | Goal AI tự thực thi; giao thức này vẫn là dry-run |
| `STUDIO_SCHEDULE_MANAGER_ENABLED` | Quản lý lịch và bản xem trước đã ghim | Worker thực thi lịch; dispatcher vẫn tắt |

Chat, Brain, Knowledge, Studio, lập kế hoạch, runtime agent/công cụ và tài
nguyên AI chung đã bật từ trước; không coi chúng là tính năng mới được xây
trong đợt này. API và CLI vẫn dùng tài khoản/kết nối đã cấu hình, không tự
đổi model, bật API dự phòng có phí hay gỡ giới hạn nhà cung cấp.

## Những gì giữ nguyên

- Đăng nhập, vai trò, mã hóa khóa, quyền Brain và cách ly SME/nhãn hàng.
- Quyền riêng tư, kiểm quyền lại trước dispatch, audit, idempotency, cancel/
  stop, giới hạn tài nguyên chống treo và phê duyệt tác động bên ngoài.
- Ads write/autopilot, Telegram/auto-reply, xóa tự động và public deployment
  vẫn tắt; không tự bật token hoặc phát lại công việc từ hàng đợi cũ.
- Temporal/Studio durable/Goal runner và schedule dispatch không được mở chỉ
  bằng đổi boolean. Những giao thức dry-run có sẵn phải tiếp tục ghi đúng
  `dry_run`/`model_calls`, không đổi nhãn mô phỏng thành thực thi AI.
- Antigravity còn thiếu cách ly công cụ; shared CLI adapter còn thiếu đường
  hỗ trợ/triển khai. Không xóa lỗi `adapter_pending` hoặc kiểm `tools_not_disabled`
  để che thiếu phần xử lý. Claude chưa có thuê bao vẫn hoãn.
- Không sửa backend/UI đang phục vụ, schema, dependency, model/CLI pins hoặc
  khóa; chỉ thay tám dòng công tắc `.env` khi kiểm thử và preflight đạt.

## Kiểm tra và vận hành

**Nghiệm thu cài đặt ngày21/10: tám công tắc trên đã bật trên bản local.**

- Bộ test chức năng20/10:148passed/0failure/error/skip,264.56s;1cảnh báo
  ARQ deprecated close. Test chạy pao_test/Redis15 serial, nguồn/env/primary
  không đổi trong lượt test:
  `.runtime/local-feature-tests-3bb89c1d99f440898d33eb7c4706f593/receipt.json`.
- Bản cài21/10: GET thật trên2doanh nghiệp owner, gồm kết quả/phê duyệt,
  trạng thái sự kiện nội bộ, quản lý lịch/tiếp nhận mục tiêu, outcome status
  và đọc learning của1Brain có quyền. Không gửi POST bằng token chẩn đoán.
  OpenAPI429 khớp đầy đủ, API/ready/Web200, worker lease khỏe. Receipt:
  `.runtime/local-feature-activation-bcb68e46df2844f3bf2687a27b9bd775/verification-897f5cef57a94db0b909cb432a40a618/receipt.json`.
- Schema0075/161bảng và3archive giữ nguyên. Binding backend vẫn
  `f596abc415cb9e97b18b7da6e5e1d937fe9194ac82896ea73badcc6d3ac1bf3a`.
  Phần `.env` ngoài8công tắc khớp hash trước thay đổi; không đổi credential
  hoặc ứng dụng đang phục vụ. Không có build UI/full backend regression mới.
- Có9test riêng cho bộ kiểm tra manifest/cache và so sánh config, không gộp
  vào148backend. Bộ kiểm tra chỉ bỏ cache/build do `next.config.mjs` khai báo
  (`.pao-next`, `.pao-build-check`), vẫn kiểm source/auth/lockfiles/runtime pin.

### Giới hạn bằng chứng và lỗi đã giữ lại

Lượt bị gián đoạn không được chuyển thành all-green. Receipt đầu
`.runtime/local-feature-activation-bcb68e46df2844f3bf2687a27b9bd775/receipt.json`
giữ `pass=false`: bộ kiểm tra đã tính cả output/cache Next.js là source.
Lượt `verification-0a52b62013984f6bad49dcdd59c11edd` cũng giữ fail: đọc
OpenAPI không chỉ định UTF-8 trên Windows làm hỏng giá trị tiếng Việt khi
so sánh. Bản OpenAPI và API thật không cần sửa; đã sửa riêng bộ đọc UTF-8,
không bỏ kiểm contract hoặc đổi kết quả lịch sử.

Sau thời gian gián đoạn có6bảng khác snapshot trước chuẩn bị:
`installation_ai_resources`, `installation_ai_revisions`,
`model_provider_connections`, `tenant_metadata_leases`,
`tenant_metadata_policies`, `tenant_read_policies`. Giữ nguyên dữ liệu mới;
không xác nhận tác giả/nguyên nhân từng thay đổi, không restore hoặc sửa hash
để khớp baseline. Receipt mới ghi rõ
`primary_unchanged_since_preparation=false`, danh sách6bảng và hash hiện tại.
Chỉ cửa sổ GET nghiệm thu mới có `primary_rows_unchanged=true`; không dùng
điều này khẳng định primary không đổi trong toàn thời gian gián đoạn.

### Khởi động lại21/10

Các tiến trình PAO cũ không còn chạy; Docker PG/Redis khỏe và các cổng trống.
Đã giữ log/process records cũ ở
`.runtime/local-feature-resume-20261021-eb493af92a6441f08964e7a963f31a61/`,
khởi động bằng launcher local/runtime đã ghim, vẫn0075, không restore primary.
API, worker, Web và Ollama đã chạy lại; Telegram/Studio durable vẫn tắt.

Thông báo readiness trước đây không phải bằng chứng API chưa khởi động:
log ghi /health200 trong lúc poller báo fail. Đã tái hiện Windows PowerShell
`Invoke-WebRequest` ở NonInteractive ném lỗi vì đòi prompt. Sửa poller dùng
`-UseBasicParsing`; cùng GET trả200 và parser PowerShell đạt. Không dừng lại
dịch vụ chỉ để chạy lại helper; chưa gọi đó là thử reboot/production recovery.

Checkpoint đã kiểm tra trước thay đổi:
`.runtime/checkpoints/p0-20261020T150539-75587956/manifest.json`, schema0075,
161 bảng, 3 archive; restore thử trên clone, không primary restore.

Helper `scripts/check_local_feature_activation.py` là công cụ nghiệm thu/cài
cấu hình, không phải business runner mới. Test dùng pao_test/Redis15 serial,
chặn mạng provider; kiểm tổ hợp bật mới, 401/404, kết quả/learning/observation/
event/approval/admission/schedule và giữ bằng chứng lỗi nếu có. Preflight kiểm
checkpoint, source, idle, native leases và chính xác executable/start-time/
command trước khi dừng riêng API/worker để tải lại cấu hình. Không dừng web,
Ollama, Docker hoặc tiến trình không thuộc PAO.

Đối chiếu `.env` bằng hash phần ngoài tám công tắc, không xuất secret hoặc
chép credentials vào báo cáo. Installed acceptance dùng GET-only với token
chẩn đoán, không dùng token đó để POST hay thay cho sự đồng ý của owner.
Không tự gộp fixture vào nghiệm thu model/quota/provider thật.

Muốn quay lại cấu hình trước: đặt riêng tám công tắc trên về `false`, sau đó
tải lại API/worker khi idle theo đúng kiểm tra tiến trình. Không restore DB,
không xóa sự kiện/ghi chú/kết quả đã có. Tắt giao diện không hoàn tác dữ liệu
do người dùng tạo trong lúc dùng tính năng mới.

Đợt này không xác nhận toàn hệ thống đã bỏ mọi giới hạn hoặc hoàn thiện toàn
bộ Goal/CLI/connector; các phần thiếu triển khai và chốt bên ngoài vẫn phải
được phát triển/nghiệm thu riêng, không được tuyên bố đạt bằng thay cấu hình.
